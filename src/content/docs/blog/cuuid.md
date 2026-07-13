---
title: "Packing a UUID"
subtitle: "Shrinking a 128-bit id by noticing how much of it is not random."
description: "cuuid is Xapiand's condensed UUID value type. It mints time-sortable ids and puts them on the wire in 8 bytes instead of 16, by noticing that a time-based UUID is not random: it is a timestamp, a clock, and a node, mostly redundant across a stream from one machine. Its current format, cuuid v6, reconstructs the node with splitmix64 (nanoseconds, where the old code paid a Mersenne Twister) and stores the bytes in UUIDv6 order so the canonical form sorts by time; the older v1 format lives on only as the --legacy-ids compatibility mode."
excerpt: "A UUID is sixteen bytes, and we treat them as sixteen bytes of pure randomness. A time-based UUID is nothing of the sort: it is a timestamp and a clock and a machine id wearing a hex costume, and a stream of them from one server repeats itself enormously. The ninth familiar reads that structure and packs the same id into eight bytes, decoded in nanoseconds and sortable by time."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 9
chapter: "Bytes"
tags:
  - familiars
  - cpp
  - encoding
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is an identifier that weighs less than it should: [cuuid](https://github.com/Kronuz/cuuid).*

A UUID is 128 bits, and the reason we love it is that we can pretend those bits are random: generate one anywhere, never coordinate, and trust that it will not collide. That is the right mental model for a *version-4* UUID, which really is random. It is quietly wrong for a **time-based** UUID, the kind you reach for when you also want ids that sort by when they were made. A time UUID is not random at all. It is a 60-bit timestamp, a 14-bit clock sequence, and a 48-bit node identifier, packed into the same 128 bits and dressed up in the familiar hyphenated hex.

That distinction is worth money on the wire, because a *stream* of these from one server is enormously repetitive. The node is identical for every id the machine ever mints. The high bits of the timestamp barely move from one id to the next. Storing all sixteen bytes, every time, is storing the same node and nearly the same timestamp prefix over and over. [cuuid](https://github.com/Kronuz/cuuid) is the value type that stops doing that. This post is about the format it mints today, **v6**: an 8-byte, time-sortable, coordination-free id. There is an older v1 format underneath it, and I will get to why it is still there.

## Condensing the structure

cuuid does the ordinary things a UUID type should: generate, parse, format to the canonical string, validate, expose the field accessors. Its interesting move is **serialisation**. The plain form is honest and simple, a tag byte `0x01` then the sixteen UUID bytes. But when the fields can be represented in less space, it emits a **condensed** encoding instead, packing them smaller and dropping what is redundant, so the same identifier goes onto the wire in fewer bytes. Unserialise reverses it exactly; the round-trip is byte-for-byte identical to the value you started with.

How small? **8 bytes** for any present-day timestamp, half of UUIDv7's sixteen and equal to a 64-bit Snowflake, and unlike Snowflake it needs no worker-id registry to get there. The folklore 4-byte figure is real only for timestamps within a year or so of cuuid's 2016 epoch: the trick strips leading zero bytes off a rebased timestamp, and today's timestamps have few left to strip.

This matters in a search engine specifically, because ids are *everywhere*: every document has one, every posting references one, they are stored, indexed, replicated, and shipped across the cluster constantly. Shaving bytes off the id is not a one-time win, it is a saving that recurs on every document in the system.

## Sorting, and the 1.64 ms floor

Can it sort by time, the way a Snowflake does? Two answers, because there are two forms.

On the **wire**, yes: the condensed bytes put the timestamp most-significant-first, so a raw lexicographic sort of the encoded ids is a sort by creation time, down to a resolution floor of about **1.64 milliseconds**. That floor is not arbitrary, and it is worth understanding because it is a direct consequence of the size trick. To reach 8 bytes, the compact form does not store the low 14 bits of the 100-nanosecond timestamp; it folds them into the clock field to save the space. What is left sorts cleanly only down to 2^14 ticks, which is 2^14 x 100 ns = 1.6384 ms. Above that, order is exact; below it, the low bits are hiding inside a scrambled clock field, and two ids from the same 1.64 ms window can come back in either order. It is the same class of floor UUIDv7 and ULID have below their millisecond resolution, and you buy past it only by spending bytes: keeping a real sub-millisecond tie-breaker costs the space the fold just saved.

In the **canonical sixteen-byte form**, v6 does better: it keeps the full 100-nanosecond timestamp in most-significant order, so those bytes sort at **100 ns**. This is a big part of why v6 exists, because the older v1 layout was the opposite. Sort raw v1 bytes and you get a full-range backward jump every seven minutes, when the low 32 bits of the timestamp wrap and yank the sort back to the start. That wart is exactly what [UUIDv6](https://www.rfc-editor.org/rfc/rfc9562) was standardized to cure, by moving the timestamp to the front, and it is the layout cuuid stores now. So the 8-byte wire sorts to 1.64 ms, the 16-byte canonical form sorts to 100 ns, and you index whichever representation fits.

## The node, and the dice

Rebuilding the shared node on decode is where cuuid used to embarrass itself. The compact form does not store the 48-bit node; it stores a 7-bit salt and *reconstructs* a synthetic node deterministically from the timestamp, clock, and salt. That reconstruction needs a mixing function, and the original code reached for the obvious one: seed a `std::mt19937` and pull two draws. Constructing a Mersenne Twister initializes its 624-word state, every single time, on both encode and decode, and it dominated everything. The compact path cost about **880 nanoseconds each way**, two to three orders of magnitude more than Snowflake, UUIDv7, or ULID.

The node's actual value is arbitrary; it only has to be deterministic, carry the salt, and set the multicast bit. So I swapped the Mersenne Twister for a **splitmix64** mixer that does the identical job from the same seed, and the whole compact path fell with it: about **9 nanoseconds to encode and 12 to decode**, down from ~880 apiece. (Decode owed a little more to a byte-at-a-time loop unpacking the wire; folding that into a single machine byteswap took it from ~16 down to ~12.)

| | wire size | sortable (wire) | encode + decode |
| --- | --- | --- | --- |
| cuuid v6 | 8 bytes | yes, ~1.64 ms | ~9 ns + ~12 ns |
| cuuid v1 (legacy) | 8 bytes | yes, ~1.64 ms | ~880 ns + ~880 ns |
| Snowflake | 8 bytes | yes, 1 ms | ~1 ns + ~2 ns |
| UUIDv7 | 16 bytes | yes, 1 ms | ~1 ns + ~0.5 ns |
| UUIDv6 | 16 bytes | yes, 100 ns | ~0 ns |

A different mixer reconstructs a different node, so the wire bytes move with it: swapping the dice makes a new format. That is what makes this **v6**, told apart from v1 by the version nibble, rather than a silent change slipped under the old ids.

## Two formats, one nibble

So cuuid carries two condensed formats now, and tells them apart by the one field a UUID already has for the purpose: the **version nibble**. A v1 value stays version 1 and decodes with the Mersenne Twister; a v6 value is version 6, decodes with splitmix64, and lays its bytes out in UUIDv6 order. On encode the nibble picks the codec for free. The condenser underneath (the bit layout, the salt derivation, the variable-length fold) is shared between them, so v6 is a small, understandable delta on the code v1 already proved: the same machine, minus the dice, with the timestamp bytes reordered.

v1 is still in the box for one reason, compatibility. New ids are v6, but an old v1 id still resolves by its bytes, because lookups and the `~`base59 text form never crack the fields open. What changes is its *canonical rendering*: decoded as v6 it prints a v6 string, not the v1 string it was born with. That is a real, deliberate break, scoped to the field-decoding representations and written into the upgrade notes; it buys never carrying two decoders in the hot path. A deployment that cannot take it starts with **`--legacy-ids`**, which pins the pure v1 codec at both ends and is byte-for-byte what it always was. [Xapiand](https://github.com/Kronuz/Xapiand) mints v6 by default.

## The portable part

Minting the id in the first place is where the operating systems disagree, as they always do. cuuid uses the platform UUID backend rather than rolling its own: `uuid/uuid.h` (libuuid) on Linux and Darwin, the native `uuid.h` on FreeBSD, selected at build time. Its two small dependencies are other familiars in this series, [endian](https://github.com/Kronuz/endian) for byte order and [char-classify](https://github.com/Kronuz/char-classify) for hex, and the host-specific seams (tracing, exceptions, local-node salting) are override points so the core carries nothing it does not need.

## Where it fits

Reach for it when you want time-sortable unique ids and you care about their size on the wire or on disk, which in a storage or search system you should. Eight coordination-free bytes that sort on the wire to 1.64 ms and in canonical form to 100 ns, decoded in nanoseconds without rolling any dice, is a genuinely good place to be. In a greenfield service I would still reach for [UUIDv7](https://www.rfc-editor.org/rfc/rfc9562) first, the boring standard answer with a library in every language, or a [Snowflake](https://github.com/twitter-archive/snowflake) if a 64-bit id and a worker registry suit you. Skip cuuid if random v4 ids are what you want, since there is nothing structural to condense in true randomness, or if a plain UUID library already does what you need and the bytes are not worth counting. The full write-up, the wider landscape (ULID, KSUID, ObjectId, and the rest), and the numbers to reproduce live in the repo's [COMPARISON.md](https://github.com/Kronuz/cuuid/blob/main/COMPARISON.md).

The next familiar is the maker of the other face a cuuid wears: the `~` and the string of base59 it turns into when a person has to read it. A base-N encoder that treats a blob as one big number and spells it out in an alphabet built for human eyes.
