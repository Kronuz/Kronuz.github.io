---
title: "No Collisions, Ever"
subtitle: "A hash table for a fixed key set, built entirely at compile time, that never collides and never branches."
description: "constexpr-phf is a header-only, fully constexpr minimal perfect hash for a fixed set of integer keys. It builds a CHD-style minimal perfect hash function over a known key set at compile time, materializing the buckets and index arrays as constexpr data, so resolving a key at runtime is a couple of multiplies, a shift, and two array reads, with no collisions, no unpredictable branch on the hot path, and no heap. It is the machinery under a compile-time dispatch table: hash a set of tokens to integers, build a phf over them, and index a parallel array of handlers. Not a dynamic map, the key set is fixed and integers only, but for known keys it is a hash table with no bad days."
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

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is a hash table that cannot collide: [constexpr-phf](https://github.com/Kronuz/constexpr-phf).*

Every ordinary hash table carries a worst case it hopes you never hit. Two keys hash to the same bucket and now the lookup is a probe sequence or a linked chain; the average is `O(1)` but the tail is not, and an adversary who can choose your keys can arrange for the tail on purpose. That risk is the price of not knowing your keys in advance. But sometimes you *do* know them in advance, all of them, at compile time: the set of HTTP methods, the reserved words of a query language, the operation names a server dispatches on. For a fixed, known key set, you can pay a little at build time to buy away the worst case completely.

[constexpr-phf](https://github.com/Kronuz/constexpr-phf) does exactly that. It builds a **minimal perfect hash function** over a known set of integer keys, entirely at compile time. "Perfect" means no two keys collide, ever, by construction. "Minimal" means the keys map onto a dense range with no gaps, so the table is exactly as big as the key set and not a byte more. And because the whole thing is `constexpr`, the search that *finds* such a hash function, which is the expensive part, happens during compilation and leaves behind only the finished lookup tables as constant data.

## What the lookup costs

The construction uses the CHD scheme (compress, hash, displace): a two-level design that splits the keys into buckets with a first hash, then, bucket by bucket from largest to smallest, finds a small displacement value for each that slots all its keys into free positions without collision. That search is real work, but it is the compiler's work, done once at build time. What survives into your binary is a `buckets` array and an `index` array of `constexpr` data. So at runtime, resolving a key is not a search at all. It is a couple of multiplies, a shift, and **two array reads**: hash the key to pick a bucket, read that bucket's displacement, combine, read the final slot. No collisions to resolve, no unpredictable branch on the hot path, no heap, no probing, no chain. The same handful of instructions for every key, always, with a worst case identical to its best case.

## The division it used to pay

The original version had a hidden tax in that hot path: a modulo. It reduced the displaced hash into the table with `% index_size`, where `index_size` was a prime. A modulo is a division, and integer division is one of the slowest things a CPU does, tens of cycles where a multiply is a few. This season I took it out. Size the table to a power of two instead of a prime and the reduction becomes a **multiply-shift**: multiply by the bucket's constant and keep the top bits with a shift. No division at all. On the same key sets that is about 20% faster on arm64 and up to 37% faster on x86, where the division hurt most.

There is one catch, and it is a good one. Multiply-shift has a blind spot: keys that are distinct powers of two. For those, `key * multiplier` is a pure left shift, so a small multiplier never pushes any entropy into the top bits and every key lands on top of every other. Multiplication cannot dig itself out, because a product of shifts is still a shift. The only cure is a non-linear step. So the build is **adaptive**: it tries the fast path first, with no extra mixing, and only if the multiplier search cannot place the keys does it fall back to a version that runs each key through one cheap xorshift before the multiply. It records which path it took, and the lookup mirrors it. Every real key set I have takes the fast path. The pathological ones quietly pay for their own robustness, at build time, and nobody else is taxed for a problem they do not have.

The classic use, and the reason it exists in Xapiand, is a **compile-time dispatch table**. Take a set of tokens, hash them to integers, build a `phf` over those integers, and use its dense output to index a parallel array of handlers or metadata. That is the exact machinery under the [string switch](/blog/compile-time-magic/) from the last post and under the [enum reflection](/blog/enum-reflection/) in the next one: a set of known names turned into a collision-free, branch-free index into a table of what to do about them.

## The string switch, made safe

That [string switch](/blog/compile-time-magic/) two posts back had a quiet flaw. It hashed the input and switched on the hash, so a word that was *not* one of your keywords could still hash into a real case and dispatch to the wrong branch. A perfect hash removes collisions among the keys you gave it, but by itself it cannot tell a stranger from a member either: it always reads *some* slot, and hands back whatever sits there.

So this season I wrote one more small library, [keywords](https://github.com/Kronuz/keywords), that marries the two and closes the gap. You hand it a fixed set of strings; it hashes them, builds a `constexpr-phf` over the hashes, and keeps the original strings indexed by slot. Look one up and it does the perfect-hash lookup, then a single compare against the one keyword stored at that slot. Match, and you get a dense index in `[0, N)` you can `switch` on. No match, and you get `npos`. One comparison, not one per case, and no false dispatch. Two more tricks fall out of knowing the whole key set at build time. It picks the hash function once, from the longest keyword: a plain byte-at-a-time FNV when the keys are short, a word-at-a-time hash when they run long, decided at compile time so the lookup carries no per-call branch. And it knows the shortest and longest keyword, so a query outside that length range is rejected in a single compare before it is ever hashed.

I measured it against the usual suspects on the real thing: Xapiand's 192 field-type names, a genuine mix of short and long. Verified membership, nanoseconds per lookup:

| lookup | ns |
| --- | ---: |
| `keywords` (verified) | 13 |
| `gperf` | 10 |
| compile-time trie | 18 |
| `std::unordered_map` | 19 |
| `frozen::unordered_set` | 22 |
| `std::set` | 52 |

`keywords` beats the trie, `frozen`, and every standard container, and lands a hair behind `gperf`, which needs a separate code-generation step `keywords` does not. On an all-short key set it quietly picks the cheaper hash instead, and stays at the front of the same pack. The honest summary: for a fixed set of strings you want to dispatch on, this is as fast as anything and faster than most, it pulls in no external tool, and it hands you the `switch` C++ never gave you.

## Where it fits

Reach for it when you have a fixed set of integer keys known at compile time and want a dense, collision-free index into a parallel table: dispatch on tokens, opcodes, reserved words, enum members. To key on strings, reach for [keywords](https://github.com/Kronuz/keywords), which does the hashing and the verification for you, or hash them to integers yourself (with [hashes](/blog/compile-time-magic/), say) and build the `phf` over the results. Do not reach for it as a general dynamic map: there is no insert or erase, the key set is frozen the moment you build it, and because the table is *searched* at compile time, a very large key set will grow your build time and template-instantiation cost. It is a scalpel for known keys, not a container for unknown ones.

The next familiar is the most common thing you build with this scalpel, and the one C++ stubbornly refuses to give you on its own: the ability to turn an enum value back into the name you wrote it with.
