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

## The answers you reach for first

Before a perfect hash, you reach for what the language hands you. Say you are dispatching on a token, a field type, an operation name, one of a fixed set you know at build time. The two idiomatic answers are an `if`/`else if` ladder of comparisons, or, once the token is hashed to an integer, a `switch` on that hash. Both work. Both come apart as the set grows.

An `if`-ladder is a linear scan: on average it tests half the cases before it hits, and every test is a branch the predictor can miss. A `switch` *looks* like it should become a jump table, but a jump table needs dense labels, and hashes are the opposite of dense. Handed a few hundred scattered 32-bit values, the compiler does the only thing it can and turns the `switch` into a **binary search** of comparisons: `O(log n)` branches, still branching, still growing. The reflexive escape, a [`std::unordered_map`](https://en.cppreference.com/w/cpp/container/unordered_map), trades the branches for a hash, a probe, a pointer chase, and a likely cache miss.

Here is what each costs per lookup as the set grows, on a fixed set of sparse keys (the hashes you actually dispatch on), at `-O3`:

| keys | `if`-ladder | `switch` (binary search) | `unordered_map` | `phf` |
| ---: | ---: | ---: | ---: | ---: |
| 6 | 2.4 | 4.0 | 3.2 | 1.2 |
| 46 | 14 | 8.2 | 3.1 | 1.2 |
| 192 | 38 | 26 | 3.1 | 1.2 |
| 1000 | 162 | 40 | 3.2 | 1.3 |

The ladder is fine at six keys and hopeless at a thousand, where it spends 160 nanoseconds walking comparisons. The `switch` grows with the logarithm and never stops branching, past 40 nanoseconds by the time the set is large. The map flattens out around three nanoseconds but never gets cheaper than that, because a hash-plus-probe-plus-indirection has a floor. Only the perfect hash is **flat and low**: the same ~1.2 nanoseconds at a thousand keys as at six, because it runs the same fixed arithmetic every time. Its worst case is its best case. The next section is why.

## What the lookup costs

The construction uses the CHD scheme (compress, hash, displace): a two-level design that splits the keys into buckets with a first hash, then, bucket by bucket from largest to smallest, finds a small displacement value for each that slots all its keys into free positions without collision. That search is real work, but it is the compiler's work, done once at build time. What survives into your binary is a `buckets` array and an `index` array of `constexpr` data. So at runtime, resolving a key is not a search at all. It is a couple of multiplies, a shift, and **two array reads**: hash the key to pick a bucket, read that bucket's displacement, combine, read the final slot. No collisions to resolve, no unpredictable branch on the hot path, no heap, no probing, no chain. The same handful of instructions for every key, always, with a worst case identical to its best case.

That reduction into the table is a **multiply-shift**, not a modulo: the table is sized to a power of two, so choosing the final slot is a multiply and a shift with no division anywhere on the path, and division is one of the slowest things a CPU does. The one key set that defeats a pure multiply, distinct powers of two, is caught at build time and routed through one extra mixing step, so a pathological set stays correct without taxing the common one. Every real key set takes the plain fast path.

## How it compares

The engine is integer-only and never sees a string: you pick a hash, it takes the integer. So for string dispatch you hash the key, look the integer up in a `phf`, and (when the input might not be a member) compare against the one key at the slot to verify. On Xapiand's 192 field-type names (2 to 23 characters, a real mix of short and long), nanoseconds per lookup:

| dispatch on 192 field-type names | ns/op |
| :-- | ---: |
| `gperf` (separate codegen step) | 14 |
| **constexpr-phf**, hash-only | 18 |
| **constexpr-phf**, hash + verify | 21 |
| compile-time trie | 28 |
| `std::unordered_map` | 29 |
| `frozen::unordered_set` | 40 |
| `std::set` | 82 |

Two phf rows, two honest ways to use it. Hash-only is the fast path Xapiand runs: hash, index, done, no compare, which can misdispatch a stranger, so you feed it only members or guard the shape first. Verified adds the one compare at the slot and never false-matches, the apples-to-apples number against gperf, frozen, and the containers, which all verify. The hash is yours to pick and it matters: a word-at-a-time hash reads eight bytes a step, 21 ns verified on these longer names where byte-at-a-time FNV-1a takes 25. Both beat every container, the immutable `frozen` set, and a compile-time trie, and trail only [gperf](https://www.gnu.org/software/gperf/), which needs a separate codegen step constexpr-phf does not. And that is gperf's best case: on an all-short key set, the 570 English stop words, constexpr-phf edges ahead of gperf too, because a short key is a couple of hash steps and one compare while gperf still runs its generated `strcmp`. All of it is reproducible: the [comparison benchmarks](https://github.com/Kronuz/constexpr-phf/tree/master/bench) live in the repo.

## Where it came from

Its home, and the reason it exists, is [Xapiand](https://github.com/Kronuz/Xapiand), which dispatches on names constantly: field types, query operators, cast functions, the reserved words of its query language, dozens of small fixed sets, each one a `switch` on the far side of a hash. The pattern that recurs is worth showing whole, because it is prettier than a bare `switch` on an integer. You hash a set of names into a `phf`, then use the phf's dense output as the *values of an `enum`*, so the dispatch reads as a `switch` over named constants and the compiler gets the dense jump table it wanted all along:

```cpp
// A fixed set of cast-operator names, listed once.
#define HASH_OPTIONS() OPTION(INTEGER) OPTION(FLOAT) OPTION(POINT) /* ...and ~30 more */

// Build the perfect hash over their hashes, at compile time.
constexpr static auto cast_hash = phf::make_phf({
    #define OPTION(name) hh(RESERVED_##name),
    HASH_OPTIONS()
    #undef OPTION
});

// The phf's dense slots ARE the enum values.
enum class HashType : uint32_t {
    #define OPTION(name) name = cast_hash.fhh(RESERVED_##name),
    HASH_OPTIONS()
    #undef OPTION
};

// Dispatch: hash the word once, switch on a dense enum.
switch (static_cast<HashType>(cast_hash.fhh(word))) {
    case HashType::INTEGER: return FieldType::integer;
    case HashType::POINT:   return FieldType::geo;
    // ...
}
```

That is the whole idea in one place: a set of known names becomes a collision-free, branch-free index into a table of what to do about them. It is the machinery under the [string switch](/blog/compile-time-magic/) from the compile-time opener and under the [enum reflection](/blog/enum-reflection/) in the next post.

One honesty note, the same one every perfect hash carries. It removes collisions *among the keys you gave it*; it cannot tell a stranger from a member. Hand it a word that is not in the set and it still reads some slot and returns whatever sits there. When the input might not be a member, you verify: keep the original strings and compare against the one at the slot, or guard the shape first, the way the cast dispatch throws on a word that does not begin with the reserved marker before it ever hashes. For a genuinely closed set, where the input is always one of the keys, you pay for neither.

## Where it fits

Reach for it when you have a fixed set of integer keys known at compile time and want a dense, collision-free index into a parallel table: dispatch on tokens, opcodes, reserved words, enum members. To key on strings, hash them to integers first with [hashes](/blog/compile-time-magic/) and build the `phf` over the results, verifying the hit yourself when the input is open. If you specifically want a *string* perfect hash and do not mind an extra build step, [gperf](https://www.gnu.org/software/gperf/) generates one as a separate code-generation pass; `constexpr-phf` stays inside the compiler with no tool to run. Do not reach for it as a general dynamic map: there is no insert or erase, the key set is frozen the moment you build it, and because the table is *searched* at compile time, a very large key set grows your build time and template-instantiation cost. It is a scalpel for known keys, not a container for unknown ones.

The next familiar is the most common thing you build with this scalpel, and the one C++ stubbornly refuses to give you on its own: the ability to turn an enum value back into the name you wrote it with.
