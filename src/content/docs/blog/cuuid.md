---
title: "Packing a UUID"
subtitle: "Shrinking a 128-bit id by noticing how much of it is not random."
description: "cuuid is Xapiand's condensed UUID value type: it generates, parses, formats, and serialises UUIDs, but its trick is a condensed binary encoding for RFC 4122 version-1 UUIDs. A v1 UUID is not random; it is a timestamp, a clock sequence, and a node id packed into 128 bits, and much of that is redundant across a stream of ids from the same machine. cuuid exploits that structure to put the same identifier on the wire in fewer bytes, byte-for-byte compatible with Xapiand's format, across the platform UUID backends (libuuid on Linux and Darwin, the native API on FreeBSD)."
excerpt: "A UUID is sixteen bytes, always, and we treat those bytes as if they were sixteen bytes of pure randomness. A version-1 UUID is nothing of the sort: it is a timestamp and a clock and a machine id wearing a hex costume, and a stream of them from one server repeats itself enormously. The ninth familiar reads that structure and packs the same id smaller."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 9
tags:
  - familiars
  - cpp
  - encoding
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is an identifier that weighs less than it should: [cuuid](https://github.com/Kronuz/cuuid).*

A UUID is 128 bits, and the reason we love it is that we can pretend those bits are random: generate one anywhere, never coordinate, and trust that it will not collide. That mental model is right for a *version-4* UUID, which really is random. It is quietly wrong for a **version-1** UUID, which is the kind you get when you want ids that also sort by time. A v1 UUID is not random at all. It is a 60-bit timestamp, a 14-bit clock sequence, and a 48-bit node identifier (historically the machine's MAC address), packed into the same 128 bits and dressed up in the familiar hyphenated hex.

That distinction is worth money on the wire, because a *stream* of v1 UUIDs from one server is enormously repetitive. The node id is identical for every id the machine ever mints. The high bits of the timestamp barely move from one id to the next. Storing all sixteen bytes, every time, is storing the same node id and nearly the same timestamp prefix over and over. [cuuid](https://github.com/Kronuz/cuuid) is the value type that stops doing that.

## Condensing the structure

cuuid does the ordinary things a UUID type should: generate, parse from and format to the canonical string, validate, and expose the v1 field accessors (node, time, clock sequence, variant, version). Its interesting move is **serialisation**. The plain form is honest and simple: a tag byte `0x01`, then the sixteen UUID bytes. But when it recognizes an RFC 4122 v1 UUID whose node, time, and clock fields can be represented in less space, it emits a **condensed** encoding instead, packing those fields smaller and dropping what is redundant, so the same identifier goes onto the wire in fewer bytes. Unserialise reverses it exactly; the round-trip is byte-for-byte identical to the value you started with, and byte-for-byte compatible with Xapiand's own format, which is the whole reason the encoding had to be preserved exactly when I pulled the library out.

This matters in a search engine specifically because ids are *everywhere*: every document has one, every posting references one, they are stored, indexed, replicated, and sent across the cluster constantly. Shaving bytes off the id representation is not a micro-optimization you do once; it is a saving that recurs on every document in the system, which is exactly the kind of place a value type earns its keep.

## The portable part

Generating the UUID in the first place is where the operating systems disagree, as they always do. cuuid uses the platform UUID backend rather than rolling its own: `uuid/uuid.h` (libuuid) on Linux and Darwin, the native `uuid.h` on FreeBSD, selected at build time. Its two small dependencies are other familiars in this series, [endian](https://github.com/Kronuz/endian) for byte-order handling and [char-classify](https://github.com/Kronuz/char-classify) for parsing and rendering hex, and the host-specific seams (tracing, exceptions, local-node salting) are left as override points so the core carries nothing it does not need.

## Against the field

Here is the fair question, the one I would ask if someone showed me this library today: it is 2026, we have [UUIDv7](https://www.rfc-editor.org/rfc/rfc9562) and [Snowflake](https://github.com/twitter-archive/snowflake) and a dozen other time-sortable ids, so where does a custom v1 codec actually stand? I owed the library an honest answer, so I [benchmarked it](https://github.com/Kronuz/cuuid/blob/main/COMPARISON.md) against the ids people actually reach for.

The size result is real but smaller than the folklore. cuuid's compact wire is **8 bytes** for any present-day timestamp. That is half of UUIDv7's sixteen and equal to a 64-bit Snowflake, and unlike Snowflake it needs no worker-id coordination to get there. The famous 4-byte figure only appears for timestamps within about a year of cuuid's 2016 epoch, because the encoding works by stripping leading zero bytes off a rebased timestamp, and today's timestamps no longer have many to strip. The old in-repo benchmark hit 4 bytes only because it fed near-zero times. So: 8 bytes, coordination-free, honestly good.

Can it sort by time, the way a Snowflake does? On the wire, **yes**. The condensed form puts the timestamp in the most-significant bytes, so a raw lexicographic sort of the encoded ids is a sort by creation time, down to a resolution floor of about **1.64 milliseconds** (below that, the low timestamp bits get folded into the clock field and order dissolves, which is the same class of limitation UUIDv7 and ULID have below their millisecond floor). The catch is that this is true of the *wire* form, not the canonical sixteen-byte v1 bytes, which carry the classic v1 curse: sort them and you get a full-range backward jump every seven minutes when the low timestamp field wraps. That is the exact wart [UUIDv6](https://www.rfc-editor.org/rfc/rfc9562) was invented to fix.

And then the number that stung. The compact path costs about **900 nanoseconds to encode and another 900 to decode**. UUIDv7, UUIDv6, ULID, and Snowflake all do their equivalent in single-digit nanoseconds.

| | wire size | sortable (wire) | encode + decode |
| --- | --- | --- | --- |
| cuuid compact | 8 bytes | yes, ~1.64 ms | ~900 ns + ~900 ns |
| Snowflake | 8 bytes | yes, 1 ms | ~1 ns + ~2 ns |
| UUIDv7 | 16 bytes | yes, 1 ms | ~1 ns + ~0.5 ns |
| UUIDv6 | 16 bytes | yes, 100 ns | ~0 ns |

Two to three orders of magnitude, and it turns out to be almost entirely one thing: reconstructing the compacted node runs a `std::mt19937`, and constructing a Mersenne Twister means initializing its 624-word state, every single time, on both encode and decode. I swapped in a splitmix64 mixer that does the identical job (a deterministic node derived from the same inputs) and it ran in **2 nanoseconds**, about 440 times faster. The cost was never the idea, it was the dice we chose to roll it with.

So, is it worth it? In the place it was born, yes without hesitation: a search engine that keeps billions of ids as keys, wants them small and time-sortable, cannot pay for coordination, and owns both ends of the wire. Eight coordination-free sortable bytes at that scale is real money. Away from that niche, in a greenfield service in 2026, I would reach for UUIDv7 (standard, sortable, no MAC leak, a library in every language) or a Snowflake if a 64-bit id and a worker registry are fine. And the Mersenne-Twister cost is not a law of the design, it is a fixable wart: a future version could reconstruct the node with the cheap mixer, store the data as v6 so even the canonical bytes sort natively, and keep the variable-length size trick, all behind a new tag so the old ids still decode. That is the version I would build starting over. The full write-up, the wider landscape (ULID, KSUID, ObjectId, and the rest), and the numbers to reproduce all live in the repo's [COMPARISON.md](https://github.com/Kronuz/cuuid/blob/main/COMPARISON.md).

## Where it fits

Reach for it when you want time-sortable unique ids and you care about their size on the wire or on disk, which in a storage or search system you should. Skip it if random v4 ids are what you want (there is nothing structural to condense in true randomness), or if a plain UUID library already does everything you need and the bytes are not worth counting.

The next familiar turns from bytes to grammar. It takes a human-written boolean query, `a OR (b AND NOT c)`, and reshapes it, in a single pass over two stacks, into something a machine can walk without ever recursing.
