---
title: "Bytes You Can Type"
subtitle: "A binary blob, rewritten as one big number in an alphabet a human can actually type."
description: "base-x is a header-only, constexpr base-N encoder/decoder for C++. It treats a byte buffer as one arbitrary-precision integer and rewrites it in any base from 2 to 66 by long division, so non-power-of-two bases like base58 and base62 work the same as base16. It ships ready-made alphabets (Bitcoin, Ripple, Flickr, Crockford, the RFC 4648 variants) and adds the things you want when a person handles the result: check digits and checksums that reject a mistype, character translation so look-alike glyphs decode the same, and case-insensitive alphabets. It builds on uinteger_t for the big integer underneath, and it is the encoder behind Xapiand's base59 short-id text form."
excerpt: "Sooner or later a pile of bytes has to face a human: an id in a URL, a hash in a log line, a key read off a screen and typed into another. Hex is twice too long, base64 carries characters that break in URLs and look alike on paper. The tenth familiar makes bytes typeable by treating the whole blob as one enormous number and rewriting it in a friendlier base."
date: 2026-07-11
draft: true
series: "Familiars"
seriesOrder: 10
chapter: "Bytes"
tags:
  - familiars
  - cpp
  - encoding
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one turns a blob into something you can type: [base-x](https://github.com/Kronuz/base-x).*

Sooner or later a pile of bytes has to face a human. An id in a URL, a hash in a log line, a key someone reads off one screen and types into another. Bytes are not built for that. Raw, they are unprintable. As hex they are honest but twice as long as they need to be and a featureless wall of `a` to `f`. As base64 they are shorter, but they carry `+`, `/`, and `=`, which break in a URL, and they mix `0` with `O` and `1` with `l` and `I`, which break the moment a person copies them by eye.

[base-x](https://github.com/Kronuz/base-x) is the small header that makes bytes typeable. Hand it an alphabet, any alphabet, and it rewrites your bytes in that base: base58, base62, base32, a Bitcoin address, a Crockford id. The friendly presets it ships exist for exactly the complaints above. base58 is base62 with the four look-alike characters (`0`, `O`, `I`, `l`) taken out. base62 is base64 without the `+`, `/`, and padding that make base64 awkward anywhere but email.

## Not chunks, one number

The obvious way to encode bytes is in fixed groups. base64 slices the stream into 6-bit chunks and maps each to a character, which is exactly why base64 only reaches bases that are powers of two, and why it needs `=` padding when the last group comes up short. base-x does something else, and it is the whole trick: it treats the entire input as **one enormous unsigned integer** and rewrites that number in the target base by long division, one digit at a time, most significant first.

That is why base58 works at all. Fifty-eight is not a power of two; you cannot reach it by grouping bits. But you can reach it by dividing a big number by 58 over and over and reading off the remainders, which is exactly what you did in grade school to write a number in base ten. The number here just happens to be a few hundred bits wide, so base-x reaches for [uinteger_t](https://github.com/Kronuz/uinteger_t), the arbitrary-precision integer from a few familiars back, to hold it and divide it. That is why `base-x` is two headers: `base_x.hh` for the codec and the alphabets, `uinteger_t.hh` for the number underneath. And because uinteger_t folds at compile time, so does base-x: an encode can be a `constexpr`.

Treating the blob as one number has a sharp edge worth naming, because a number does not remember its leading zeros. `007` and `7` are the same integer, so a buffer that starts with zero bytes encodes to the same text as the same buffer without them, and the decode cannot put them back. Whole-number base58 schemes deal with this two ways. Bitcoin's spends a character on it, prepending one `1` (the zeroth digit) for every leading zero byte. Xapiand's cuuid, from the last post, does the cheaper thing: it *shapes* the value so the problem never arises, keeping the first wire byte nonzero on purpose so its base59 text form has nothing to lose. That nonzero-first-byte rule in cuuid's format and this encoder are two ends of the same wire.

## Catching a typo

If a person is going to type the thing, encoding it is only half the job; you also want to know when they get it wrong. base-x has two modes for that, both a flag on the same encode and decode path. A **check digit** appends one extra symbol derived from the value, so a single wrong character, or two swapped, fails to verify instead of quietly decoding to a different, equally valid id. A **checksum** does the same with more bytes for more confidence, the way a Bitcoin address carries a four-byte hash of itself so a fat-fingered address is rejected at the door rather than sending coins into the void.

Two smaller touches serve the same "a human is in the loop" goal. **Character translation** lets visually ambiguous glyphs decode to the same value, so an id someone wrote down with a capital `O` still resolves even though the canonical alphabet used a zero. And **case-insensitive** alphabets let `ABC` and `abc` mean one id, for the times an identifier passes through something (a hostname, a careless copy) that does not preserve case.

## Where it fits

Reach for base-x when you have binary that has to meet a person: short ids, hashes, keys, anything that lands in a URL, gets read aloud, or gets typed. Pick the alphabet for the audience (base58 or base62 for clean URL-safe ids, Crockford for something read off a label), and turn on a check digit if they are going to type it back. It is the encoder behind the base59 `~` text form Xapiand gives a [cuuid](/blog/cuuid/), and behind short human-facing ids in general.

Skip it when you want standard, byte-aligned output. The plain `base16()` and `base64()` alphabets here are whole-number encodings and will not line up with `xxd` or a stock base64 library, though the `rfc4648()` presets do produce the standard, padded form through a block-padding path. And skip it for data that does not fit in memory: base-x materializes the entire value as one integer in order to divide it, so it is the wrong tool for streaming a gigabyte past.

The next familiar turns from bytes to grammar. It takes a human-written boolean query, `a OR (b AND NOT c)`, and reshapes it, in a single pass over two stacks, into something a machine can walk without ever recursing.
