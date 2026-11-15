---
title: "Sorted as Bytes"
subtitle: "A number codec whose bytes compare like the numbers they hold."
description: "sortable is a header-only C++20 codec that turns any int64, uint64 or double into 1 to 10 bytes whose memcmp order is the numeric order. The same number in any of the three types gives the same bytes, every 64-bit integer is exact, and a value is a tag byte for its binary exponent followed by its fraction, so a document id takes about 2 bytes and encodes in about 3 nanoseconds. It has two decoders: a strict one that accepts exactly what the encoder writes, for bytes from outside, and a trusted one for bytes read back from your own storage that keeps only the bounds checks and decodes 24 to 38 percent faster on real values."
excerpt: "An index compares keys as raw bytes, and it does not care that some of those bytes were an integer and some were a double. The thirty-first familiar makes that blindness safe: any number, in any of three types, becomes a short string whose byte order is the numeric order, exact down to the last bit of a 64-bit integer."
date: 2026-11-15
authors: kronuz
series: "Familiars"
seriesOrder: 31
chapter: "Bytes"
tags:
  - familiars
  - cpp
  - encoding
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is a way of writing numbers down so that a byte comparison gets them right: [sortable](https://github.com/Kronuz/sortable).*

A search engine sorts and ranges over numbers constantly, and it almost never does it with numbers. It does it with bytes. A sort key, a value slot, a term in the index: each is a byte string, and the storage layer orders them with `memcmp`, the dumbest and fastest comparison there is. It knows nothing about signs, exponents, or types. So every number has to be written down in a form where the byte order *is* the numeric order, or the index will happily put 10 before 9.

That much is a classic trick. The part that makes it interesting in a JSON search engine is that a field does not have one type. A `price` field gets `5` from one document, `5.0` from another, and `4.99` from a third, and the parser hands those to the engine as an `int64`, a `double`, and a `double`. Document ids are integers until someone sends one past 2 to the 53rd. Whatever the codec writes, those three kinds of number have to land in one order, and two different integers must never become the same key, because in an index two equal keys are one document.

## The answers you reach for first

The textbook encoding for a single integer type is eight big-endian bytes with the sign bit flipped. It sorts perfectly, it is trivial, and it is the right answer when a column is one fixed type forever. But it is always eight bytes, even for the number 1, and an `int64` column and a `double` column written that way do not share an order: the same 5 comes out as two unrelated strings.

The textbook encoding for doubles flips the sign bit of positives and every bit of negatives, and the IEEE 754 layout does the rest. The tempting move is to push every number through it, integers included, and get one order for free. It almost works. A double has 53 bits of significand, so above 2 to the 53rd it cannot hold every integer: 9,007,199,254,740,993 rounds to 9,007,199,254,740,992, and two ids that differ by one become one key. A codec that squeezes integers through a float, or one that trims a tail to save space, is wrong in exactly the places nobody tests, at the top of the range and at the boundaries between negative powers of two.

I wanted all of it at once: one order for all three types, every 64-bit integer exact, short for the numbers people actually store, and a decoder I would trust with bytes off a user's disk.

## A tag for the exponent

The shape that gets there is old floating-point wisdom turned into a byte layout. Any finite nonzero number is 2 to some power, times one plus a fraction. sortable writes the power, the binary exponent, as one tag byte, and the fraction after it as big-endian bytes, dropping the trailing zero bytes:

```
1      be                    tag only: 2^0, fraction 0
5      c0 40                 2^2 x 1.25: the fraction .25 is the byte 40
0.01   b7 47 ae 14 7a e1 47 b0
-inf   01 00 00     +inf  fe ff ff     NaN  ff     zero  80
```

Tags rise with the exponent, so across exponents the first byte decides. One tag per exponent covers every power from 2 to the minus 60th up to 2 to the 63rd, which is every integer and almost every double anyone stores, in a single byte; only the far ends of the double range spend a two-byte escape field. Inside one exponent, the fraction decides, and here the dropped zeros pay for themselves twice. A shorter tail is a longer tail with zeros after it, and `memcmp` puts a prefix first, so the shorter one sorts first, which is exactly right.

An integer is just a number whose fraction ends early. 5 is `c040` whether it came in as an `int64`, a `uint64`, or a `double`, so a mixed column needs no type byte and no conversion. Every `uint64` and every `double` fits in a fraction of at most 63 bits, so nothing rounds: the codec is exact for every value of every type it takes, and the longest encoding is 10 bytes.

## The gnarly bit: negatives

Negative numbers are where codecs like this quietly break. The obvious move is to complement everything, so bigger magnitudes sort lower. Complement the tag, fine. Complement the tail, and the trimmed zeros turn into trailing `ff`s you would rather not store, so you trim those too, and now a shorter negative is a prefix of a longer one and sorts first. That puts -(2^30) before -(2^30) - 1, which is backward, and only for the values that happen to end on a byte boundary.

sortable mirrors the tag but writes the tail as one minus the fraction, under the tag of the next power up. A bigger magnitude has a smaller one-minus-fraction, so it sorts lower; and the lowest set bit of one minus a fraction is the lowest set bit of the fraction itself, so the tail keeps both its length and its nonzero last byte. No trailing junk, no terminator, and the most negative value of each exponent, an exact power of two, has the empty tail and sorts first in its tag. The whole order, top to bottom, is minus infinity, the negatives, zero, the positives, plus infinity, and then every NaN as the single byte `ff`.

## Two decoders

Encoding never fails. Decoding has to decide what to do with bytes it did not write, and I ended up with two answers, because there are two kinds of bytes.

`decode` is the strict one. It takes any byte string, reads only inside it, allocates nothing, never throws, and accepts exactly the outputs of `encode` and nothing else. That last part is nine rules: no tag that is never written, nothing after a zero or a NaN, no escape field for an exponent a plain tag covers, no tail ending in a zero byte, no value outside what a `double` or a 64-bit integer can hold, and so on. A string either is an encoding or it is rejected, which is what you want for bytes that came from a client or a wire.

Then I measured it, and on macOS the strict decoder was slower than I liked on real double values. The obvious suspect was the intermediate `number` the decoder builds before converting. It was not. I built a variant that kept only the three rules that bound memory reads (an empty input, a missing escape field, a tail longer than eight bytes) and dropped the six that only prove an encoding is canonical, and nearly all of the cost went with them. The canonical checks were the price.

Bytes your own program wrote and read back from its own index do not need proving canonical. So the trusted conversions, `to_double`, `to_int64`, and `to_uint64` straight from bytes, keep those three rules and skip the other six. On anything `encode` wrote they return exactly what `decode` would, rounding included. On anything else they still stay inside the input and never misbehave, but the value they return is unspecified. You pick the decoder by where the bytes came from.

## The numbers

Here is the codec on Linux x86-64, built with GCC 13 at `-O3`, in nanoseconds and bytes per value, on real field values from a corpus of 434,977 numbers and on uniformly random 64-bit integers. Encoding is the fastest column, and the trusted decoder sits between it and the strict one:

| Values | Encode | Strict decode | Trusted decode | Bytes |
| --- | ---: | ---: | ---: | ---: |
| Document ids | 3.0 | 6.7 | 5.1 | 2.23 |
| Account numbers, as doubles | 7.0 | 12.8 | 8.0 | 3.74 |
| Balances | 6.9 | 12.6 | 8.2 | 7.82 |
| File modification times, microseconds | 6.6 | 12.5 | 8.5 | 6.27 |
| Random unsigned 64-bit | 5.4 | 11.1 | 7.4 | 8.97 |
| Random signed 64-bit | 8.9 | 13.0 | 9.5 | 8.94 |

A document id, the most common number in a search engine, is about **2.2 bytes** and **3 nanoseconds** to write. The trusted path takes 24 to 38 percent off the strict decode on the real sets. Every set, the macOS run, and how to reproduce them are in the repo's [performance notes](https://github.com/Kronuz/sortable/tree/main/docs/perf).

## Proving it

A codec like this is the kind of thing that is right on every value you think of and wrong on one you did not. So the proof does not lean on examples. A small Python reference model, [`tools/model.py`](https://github.com/Kronuz/sortable/blob/main/tools/model.py), is the definition of the bytes; it writes **113,491** test vectors, and the C++ tests check every one on every platform CI runs. A property test checks round trip, order, and cross-type equality at every power-of-two boundary and over millions of random values. Every input of up to three bytes is decoded exhaustively. An opt-in pass walks all 2 to the 32nd `float` bit patterns and fails unless it counted all of them. A mutation script drops each of the nine reject rules in turn and requires a test to fail. And a libFuzzer target under ASan and UBSan runs both decoders on arbitrary bytes, checking the trusted one against the strict one whenever the strict one accepts: **674 million inputs** over a little more than one CPU-hour, with nothing found.

## Where it fits

Reach for sortable when integers and floating-point numbers share an index and compare as raw bytes, and when range bounds on 64-bit integers have to be exact. It is one header with no dependencies, and a small command-line driver lets other languages test against the same bytes.

Skip it for a column that is one fixed 64-bit type forever: eight big-endian bytes with the sign bit flipped are fixed-width and simpler. Mind that the encoding is not prefix-free, so if you concatenate several numbers into one key, frame each one. And it stops at 64 bits on purpose. The layout already has room for 128-bit integers, a longer tail under the escape tag, without changing a single byte it writes today; it stays unbuilt until something actually sends one.
