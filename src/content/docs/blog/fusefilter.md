---
title: "Certainly Absent"
subtitle: "A filter that says no in three reads, and is wrong about yes once in 256."
description: "fusefilter is a header-only C++20 binary fuse filter, after Graf and Lemire's 2022 paper: a fixed set of 64-bit keys that answers \"maybe present\" with no false negatives and a 1 in 256 false-positive rate, in about 9 bits per key and three memory reads per lookup. It is built by peeling, grows its table when a set will not peel, and looks for duplicate keys only when they get in the way. At a million keys it answers in 1.6 nanoseconds and builds in 9.7 nanoseconds per key on an Apple M4 Pro."
excerpt: "Most of the keys a search engine looks for in a given segment are not there, and finding that out the slow way is most of the work. The thirty-first familiar answers in three memory reads and about nine bits per key: certainly absent, or probably present, and wrong about the second one time in 256."
date: 2026-11-03
authors: kronuz
series: "Familiars"
seriesOrder: 31
chapter: "Bytes"
tags:
  - familiars
  - cpp
  - filters
---

*Part of [**Familiars**](https://kronuz.com/cpp-libraries/), my collection of standalone C++ building blocks. This one is new, written for the engine underneath it, and it stands at the door of every dictionary: [fusefilter](https://github.com/Kronuz/fusefilter).*

Picture a library with fifty reading rooms, each with its own card catalog. You want one book, and it is in exactly one room. What you want is a cheap sign on each door that says either "definitely not here" or "maybe here, go check".

A search engine has the same problem. Its data lives in many *segments*, chunks of the index written once and never changed, and each segment has a *dictionary*, a sorted list of the keys it holds. Looking up a document asks segment after segment, and in all but one the answer is no. Reading a dictionary to learn that costs real work every time. So in front of each one, the engine puts a *filter*: a tiny summary of the keys that answers "certainly not" (always true) or "maybe" (true except about one time in 256). Only a maybe goes on to the dictionary.

## The usual answer

The classic sign on the door is a [Bloom filter](https://en.wikipedia.org/wiki/Bloom_filter). It is a long row of bits; each key flips a handful of them on, and a query checks whether all of its bits are on. It accepts new keys at any time, and that flexibility costs space. To be wrong only 1 time in 256, a Bloom filter needs **11.54 bits per key** (that is what [Boost.Bloom](https://www.boost.org/doc/libs/release/libs/bloom/) sizes it to), when the theoretical floor is 8.

A segment never changes, so the engine does not need that flexibility. Thomas Mueller Graf and Daniel Lemire designed a filter for exactly this case, first the xor filter and then its refinement in "[Binary Fuse Filters: Fast and Smaller Than Xor Filters](https://arxiv.org/abs/2201.01174)" (2022). The idea below is theirs; fusefilter is my C++ version of it.

## Three bytes that add up

The filter is an array of bytes. Each key is scrambled by a *hash function* (a recipe that turns a key into a random-looking 64-bit number), and that number picks three positions in the array plus one byte called the key's *fingerprint*. The array is filled so that, for every stored key, its three bytes combined with XOR (a bitwise "add without carrying") give exactly its fingerprint.

Checking a key means reading three bytes and comparing. A stored key always matches, so the filter never says "not here" about a key that is there. A missing key reads three bytes that were set for other keys, and they happen to match its fingerprint by pure chance: one time in 256, or 0.39%. The array has about 1.125 bytes per key, which is where the **9 bits per key** come from.

## Peeling the knot

Filling that array is the clever part, and it works like solving a puzzle from its easiest square. Find a byte that only one key uses. That key can be settled last: whatever its other two bytes end up holding, this one is free to make the sum come out right. Set the key aside, which may leave another byte with only one key, and keep going. Like untying a knot by always pulling the loose end, this is called *peeling*. If every key comes off, put them back in reverse order, setting each key's free byte as you go.

Sometimes a few keys tangle into a knot with no loose end. Then the build tries again with a different *seed*, a number mixed into the hash so every key lands somewhere new.

## Where it broke

The first surprise was a set of **11,509** perfectly ordinary random keys that refused to build. At that size, the table the paper's formula picks was just a little too tight, and all 100 seeds failed. [The fix](https://github.com/Kronuz/fusefilter/commit/e9eadcc583000d6b16fa6a1ad020d7677d973f45) gives the table one more stretch of bytes after 100 failures, up to 8 times.

The second was duplicates. Two copies of the same key land on the same three bytes, so neither ever becomes a loose end, and no seed can ever work. The first version sorted every key up front to remove copies. Later, to cut the engine's memory use during merges, the build [learned to take over the caller's list](https://github.com/Kronuz/fusefilter/commit/755b392408384635a889bb30cc83918fe9442535) and sort it in place instead of copying it, which dropped its working memory from about 46 to 24 bytes per key.

Staring at that sort exposed the real waste: most sets have no duplicates, and they paid for a full sort to find none. The build [now peels the keys as given](https://github.com/Kronuz/fusefilter/commit/08686a53c11add5eebb07990fcfaf232d976c957) and only looks for copies if the first attempt fails, checking just the few keys left in the knot, the only place a copy can hide. That, plus reading memory in a friendlier order, made the build **3.9 times faster**: 37.2 to 9.6 nanoseconds per key at a million keys on an Apple M4 Pro.

## The numbers

Here is fusefilter beside the paper authors' own C implementation ([xor_singleheader](https://github.com/FastFilter/xor_singleheader)) and a Bloom filter tuned to the same error rate, at one million random keys on an Apple M4 Pro. Times are in nanoseconds, lookups for a key that is present; fusefilter matches the authors on lookups and uses 22% fewer bits than the Bloom filter.

| Filter | Bits per key | Wrong "maybe" | Build, per key | Lookup |
|---|---:|---:|---:|---:|
| fusefilter | 9.04 | 0.39% | 9.7 | 1.6 |
| xor_singleheader | 9.04 | 0.39% | 18.8 | 1.5 |
| Bloom filter | 11.54 | 0.39% | 6.2 | 4.2 |

The Bloom filter builds faster, since adding a key is one quick step with no puzzle to solve. For a segment built once and read millions of times, that is a fine trade. Every row, a second machine and ten million keys are in the repo's [comparators page](https://github.com/Kronuz/fusefilter/blob/main/docs/perf/comparators.md).

## How I know it works

The tests check that no stored key is ever reported missing at sizes from zero up to a million keys, and that the error rate stays near 1 in 256. A second test builds sets in every awkward shape (half duplicates, all keys equal, keys picked to break a seed) and checks each against the old, slower build: the same seed and size, no missing key, and the same bytes whatever order the keys came in. A script breaks the build in 16 deliberate ways and requires a test to catch each one. A fuzzer (a tool that generates random input) fed **227 million** byte strings to the loader, and every one was either read safely or rejected.

## Where it fits

Reach for fusefilter in front of a slow lookup over a set that never changes: index segments, on-disk tables, anything written once and asked about often, mostly for things that are not there. It is one header file with no dependencies. Skip it if your set changes, since every change means a rebuild (a Bloom filter takes additions), or if you need fewer than 1 in 256 wrong answers.
