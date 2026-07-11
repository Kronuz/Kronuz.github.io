---
title: "No Collisions, Ever"
subtitle: "A hash table for a fixed key set, built entirely at compile time, that never collides and never branches."
description: "perfect-hash is a header-only, fully constexpr minimal perfect hash for a fixed set of integer keys. It builds a CHD-style minimal perfect hash function over a known key set at compile time, materializing the buckets and index arrays as constexpr data, so resolving a key at runtime is a couple of multiplies, a modulo, and two array reads, with no collisions, no branches on the hot path, and no heap. It is the machinery under a compile-time dispatch table: hash a set of tokens to integers, build a phf over them, and index a parallel array of handlers. Not a dynamic map, the key set is fixed and integers only, but for known keys it is a hash table with no bad days."
excerpt: "An ordinary hash table has bad days: two keys collide, the lookup degrades to a probe or a chain, and worst-case is worse than average. If you know all your keys at compile time, you can eliminate the bad day entirely. The twenty-seventh familiar builds a minimal perfect hash over a fixed key set while the program compiles, so every lookup is a fixed handful of arithmetic and two array reads, forever, with no collision possible."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 27
tags:
  - familiars
  - cpp
  - compile-time
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is a hash table that cannot collide: [perfect-hash](https://github.com/Kronuz/perfect-hash).*

Every ordinary hash table carries a worst case it hopes you never hit. Two keys hash to the same bucket and now the lookup is a probe sequence or a linked chain; the average is `O(1)` but the tail is not, and an adversary who can choose your keys can arrange for the tail on purpose. That risk is the price of not knowing your keys in advance. But sometimes you *do* know them in advance, all of them, at compile time: the set of HTTP methods, the reserved words of a query language, the operation names a server dispatches on. For a fixed, known key set, you can pay a little at build time to buy away the worst case completely.

[perfect-hash](https://github.com/Kronuz/perfect-hash) does exactly that. It builds a **minimal perfect hash function** over a known set of integer keys, entirely at compile time. "Perfect" means no two keys collide, ever, by construction. "Minimal" means the keys map onto a dense range with no gaps, so the table is exactly as big as the key set and not a byte more. And because the whole thing is `constexpr`, the search that *finds* such a hash function, which is the expensive part, happens during compilation and leaves behind only the finished lookup tables as constant data.

## What the lookup costs

The construction uses the CHD scheme (compress, hash, displace): a two-level design that splits the keys into buckets with a first hash, then, bucket by bucket from largest to smallest, finds a small displacement value for each that slots all its keys into free positions without collision. That search is real work, but it is the compiler's work, done once at build time. What survives into your binary is a `buckets` array and an `index` array of `constexpr` data. So at runtime, resolving a key is not a search at all. It is a couple of multiplies, one modulo, and **two array reads**: hash the key to pick a bucket, read that bucket's displacement, combine, read the final slot. No collisions to resolve, no branches on the hot path, no heap, no probing, no chain. The same handful of instructions for every key, always, with a worst case identical to its best case.

The classic use, and the reason it exists in Xapiand, is a **compile-time dispatch table**. Take a set of tokens, hash them to integers, build a `phf` over those integers, and use its dense output to index a parallel array of handlers or metadata. That is the exact machinery under the [string switch](/blog/compile-time-magic/) from the last post and under the [enum reflection](/blog/enum-reflection/) in the next one: a set of known names turned into a collision-free, branch-free index into a table of what to do about them.

## Where it fits

Reach for it when you have a fixed set of integer keys known at compile time and want a dense, collision-free index into a parallel table: dispatch on tokens, opcodes, reserved words, enum members. To key on strings, hash them to integers first (with [hashes](/blog/compile-time-magic/), say) and build the `phf` over the results. Do not reach for it as a general dynamic map: there is no insert or erase, the key set is frozen the moment you build it, and because the table is *searched* at compile time, a very large key set will grow your build time and template-instantiation cost. It is a scalpel for known keys, not a container for unknown ones.

The next familiar is the most common thing you build with this scalpel, and the one C++ stubbornly refuses to give you on its own: the ability to turn an enum value back into the name you wrote it with.
