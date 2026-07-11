---
title: "The Bag of Holding"
subtitle: "The small, honest tools too little for a post of their own, and a look back at the whole party."
description: "The closing of Familiars. A grab-bag of the smallest libraries carved out of Xapiand, the ones too little for a deep-dive on their own, tipped out and catalogued so none of them is lost: time helpers (times, time-point, epoch, nanosleep, datetime), string and byte tools (split, strings, static-string, stringified, escape, repr), digests (md5, sha256), number helpers (math, random, strict-stox), containers (lru-cache, bloom-filter, iterators, lazy), and the systems odds and ends (errno-names, located-exception, fs, allocators, scheduler, url-parser). Then a look back at what it means to take a whole system apart into small, standalone, honest tools."
excerpt: "Not every tool earns its own chapter. This is the last of the campaign: the bag of small, honest libraries too little for a post apiece, tipped out onto the table so none of them is lost, and then a look back at the whole party we assembled from one search engine, and what it meant to take it apart."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 29
tags:
  - familiars
  - cpp
---

*The closing of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This is the last one, and it is really a table full of them.*

Every adventuring party accumulates a bag of small things that never get their own scene: the rope, the chalk, the ten-foot pole, each one dull until the exact moment it saves you. A codebase is the same. Most of what falls out of a big system is not a jewel with a story; it is a small, honest tool that does one plain thing correctly so you never have to think about it again. There are a lot of these in Xapiand, too small for a deep-dive apiece, and they deserve better than to be lost, so here they are, tipped out onto the table at once.

## Time, which nobody gets right the first time

- **[times](https://github.com/Kronuz/times)** and **[time-point](https://github.com/Kronuz/time-point)**: monotonic and wall-clock helpers, and the `std::chrono::time_point` conveniences the standard library makes you write yourself. Monotonic for measuring durations, wall-clock for stamping them; confusing the two is a classic bug, and keeping them separate types keeps you honest.
- **[epoch](https://github.com/Kronuz/epoch)**: time since the epoch, header-only and dependency-free, for when you just want the number.
- **[nanosleep](https://github.com/Kronuz/nanosleep)**: an EINTR-safe sleep, because even sleeping is a syscall a signal can interrupt, and [io](/blog/io/)'s lesson applies here too.
- **[datetime](https://github.com/Kronuz/datetime)**: a real date/time parser and formatter, the largest of this group, and honestly a full post's worth of pain (time zones, formats, the calendar's cruelty) waiting to be written.

## Strings and bytes

- **[split](https://github.com/Kronuz/split)**: a tiny string splitter, the function everyone re-writes.
- **[strings](https://github.com/Kronuz/strings)**: a toolkit of `std::format`-style general string utilities.
- **[static-string](https://github.com/Kronuz/static-string)** and **[stringified](https://github.com/Kronuz/stringified)**: a `constexpr` compile-time string, and a small `string_view` wrapper, the leaves a lot of the [compile-time chapter](/blog/compile-time-magic/) grows from.
- **[escape](https://github.com/Kronuz/escape)** and **[repr](https://github.com/Kronuz/repr)**: turn an arbitrary byte buffer into a printable, escaped string, one for a log line, one for a single-line debug `repr`. The tools you reach for at 2 a.m. to see what is actually in a buffer.

## Digests and numbers

- **[md5](https://github.com/Kronuz/md5)** and **[sha256](https://github.com/Kronuz/sha256)**: the two message digests, buffer in, fixed-size hash out, for checksums and content addressing (md5 for the non-adversarial cases, sha256 for the rest).
- **[math](https://github.com/Kronuz/math)**: small integer-math helpers, the safe versions of the arithmetic you keep getting subtly wrong.
- **[random](https://github.com/Kronuz/random)**: a dependency-free random-number helper, because the standard `<random>` is powerful and unpleasant to use, and most code just wants a number.
- **[strict-stox](https://github.com/Kronuz/strict-stox)**: strict numeric parsing, the `stoi` that actually rejects `"12abc"` instead of quietly returning `12`, which the standard one does not.

## Containers and iteration

- **[lru-cache](https://github.com/Kronuz/lru-cache)**: an intrusive LRU cache, a doubly-linked list threaded through the nodes themselves, so eviction is `O(1)` with no separate bookkeeping structure.
- **[bloom-filter](https://github.com/Kronuz/bloom-filter)**: a header-only Bloom filter, the probabilistic set that answers "definitely not present" or "maybe present" in a few bits per element.
- **[iterators](https://github.com/Kronuz/iterators)** and **[lazy](https://github.com/Kronuz/lazy)**: lazy iteration adaptors and deferred-evaluation helpers, small pieces of the "compute it only if someone asks" habit that runs through the whole engine.

## Systems odds and ends

- **[errno-names](https://github.com/Kronuz/errno-names)**: map an `errno` to its symbolic name and human description, so a failure logs as `EAGAIN` and a sentence, not `11`.
- **[located-exception](https://github.com/Kronuz/located-exception)**: an exception base that remembers where it was thrown and formats itself with a stack trace, the connective tissue between an error and [the tracer](/blog/the-haunted-handler/) that can describe it.
- **[fs](https://github.com/Kronuz/fs)**: filesystem helpers, the path and directory operations that sit just above [io](/blog/io/).
- **[allocators](https://github.com/Kronuz/allocators)**: an STL-compatible allocator toolkit, for the places where the default allocator is not the right one.
- **[scheduler](https://github.com/Kronuz/scheduler)**: the timer-wheel scheduler and per-key debouncer built directly on [the wheel](/blog/the-sparse-wheel/), the layer between the raw lock-free structure and [the logger](/blog/logger/) that rides it. It half-earned its own post; you have already met its heart and its best client.
- **[url-parser](https://github.com/Kronuz/url-parser)**: splits a URL path and query string into their parts, the small companion to [the router](/blog/radix-router/) that decides where the path goes.

## What the party was for

That is the whole bag, and with it, the whole party. Sixty-odd libraries, from a jester that names your servers to a tracer that works in a haunted room to the ten-foot pole of a strict `stoi`, all of them pulled out of one distributed search engine and made to stand on their own.

Here is what I actually take from having done it. A big system does not feel, from the inside, like a collection of small ideas. It feels like one large, tangled thing you hold in your head all at once, and are a little afraid to touch. But when you finally pull a piece out, give it its own repository, its own README, its own tests, and make it earn its keep alone, the piece turns out to be *smaller and clearer than it ever looked while it was load-bearing*. The lock-free wheel was never really about Xapiand. The perfect hash was never really about search. They were general ideas that happened to be born under pressure, and the pressure is exactly what made them sharp. Taking the engine apart was not demolition. It was finding out how many separate, reusable, understandable things I had actually built while I thought I was building one.

That is the honest reason this series exists. Not to show off an engine, that story is [its own post](/blog/a-search-engine-from-scratch/), but because the tools were the better souvenir. Every familiar here is real, open, and on [github.com/Kronuz](https://github.com/Kronuz); most are MIT or public domain; the code in each post is the code that runs. Clone the ones that solve a problem you have. That is what they are for, and it is why I bothered to carve them out at all: a thing you build alone, and understand completely, you can hand to someone else.

The campaign is over. The party is yours now.
