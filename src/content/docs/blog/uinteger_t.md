---
title: "The Long Division"
subtitle: "An arbitrary-precision integer, and why division is the part everyone gets wrong."
description: "uinteger_t is a single-header arbitrary-precision unsigned integer for C++ that reads like an ordinary int: construct from native integers or strings in any base 2 to 36, do the usual arithmetic, print in the base of your choice. Under the hood it stores 64-bit limbs little-endian and uses the real tuned algorithms, Karatsuba for big multiplications and Knuth's Algorithm D for division. Division is the one nearly everyone gets subtly wrong, because of the quotient-digit estimate and the rare add-back correction you must handle or ship a bug that fires once in billions."
excerpt: "Sixty-four bits runs out. A 256-bit hash, a base conversion, a counter that must never wrap, and suddenly you want a number with no ceiling that still reads like a * b + c. The sixth familiar is that number. Addition is easy and multiplication has a famous trick, but division is the operation that separates a bignum that works from one that is wrong two times in a billion and you will never know which."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 6
tags:
  - familiars
  - cpp
  - algorithms
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one has no ceiling: [uinteger_t](https://github.com/Kronuz/uinteger_t), an integer as big as memory allows.*

Sixty-four bits is a lot of headroom until it isn't. A hash wider than a machine word, a base-62 id, a factorial, a counter that must never silently wrap: all of them run past `uint64_t`, and when they do you want a number that keeps going, without giving up the thing that makes integers pleasant, which is that they read like arithmetic. `a * b + c`, not `bignum_add(bignum_mul(a, b), c)`.

[uinteger_t](https://github.com/Kronuz/uinteger_t) is that number: a single-header arbitrary-precision unsigned integer that behaves like a built-in one. You build it from a native integer or a string in any base from 2 to 36, do the usual arithmetic, bitwise, shift, and comparison operations, and render it back out in whatever base you like. Inside, the value is a `std::vector<uint64_t>` of limbs in little-endian order, and where the compiler is willing, the whole thing folds at compile time.

## The easy two thirds

Two of the four operations are almost free. **Addition** and **subtraction** are the grade-school algorithm on 64-bit limbs: walk the limbs low to high, add with a carry, subtract with a borrow. Nothing subtle.

**Multiplication** starts as the grade-school algorithm too, long multiplication, limb by limb, which is `O(n²)`. That is fine until the numbers get big, at which point uinteger_t switches to **Karatsuba**, the classic divide-and-conquer trick: split each number into a high and low half, and notice that the four half-products a naive split needs can be computed from only *three* multiplications plus some additions. Recurse, and `O(n²)` becomes about `O(n^1.585)`. It is one of the first algorithms that makes you feel the difference between "correct" and "fast," and the crossover point, small numbers stay long, big numbers go Karatsuba, is the whole tuning.

## The operation everyone gets wrong

And then there is division, which is where bignum libraries go to die.

Long division of large numbers is the hardest of the four basic operations by a wide margin, and the reference implementation is **Knuth's Algorithm D**, from *The Art of Computer Programming*, volume 2. It looks like the long division you learned, but every step hides a trap. You **normalize** first, shifting both operands so the divisor's top limb has its high bit set, because the whole thing only works when the leading limb is large enough. Then, for each output digit, you **estimate** the quotient digit from just the top two limbs of the running remainder and the top limb of the divisor, an estimate that is provably at most two too high. And then the part that everyone skips: sometimes the estimate is still one too high after you correct it once, and you have to **add the divisor back** and decrement the digit.

That add-back fires rarely, on the order of two times in every `2^63`, which is exactly what makes it dangerous. Leave it out and your bignum division passes every test you will ever bother to write, ships, and then produces one wrong quotient somewhere in a billion operations, silently, with no crash to tell you where. Getting Algorithm D *entirely* right, normalization, the two-limb estimate, and the add-back you will never see fire, is the difference between a bignum you can trust and a landmine. It is the reason a "simple" arbitrary-precision integer is not simple at all.

## Where it fits

Reach for it when you need exact integer math past 64 bits and you want a small header-only dependency that reads like ordinary integer code: big hashes, cryptographic-sized values, base conversions, counters that must never wrap. Skip it when a fixed-width type (`uint64_t`, `__int128`) already covers your range, or when you need signed values, rationals, or modular arithmetic. It is unsigned only, and with no fixed width there is nothing to overflow, so subtraction below zero wraps the way unsigned always does.

The base-conversion corner even grew a sibling. The built-in `2` to `36` handles the plain digit alphabets; when you want the *encoding* side of that idea, arbitrary alphabets and the human-friendly bases past 36, that is [base-x](https://github.com/Kronuz/base-x). It stacks straight on top of uinteger_t, treating a byte buffer as one big unsigned integer and rewriting it in whatever alphabet you hand it: base58, base62, Bitcoin, Ripple, Crockford, with optional check digits and checksums for ids people copy and type by hand. The base-62 id from the opening of this post is one of its jobs.

The next familiar goes back into the running server and does something that sounds wasteful and is precisely the opposite: it arms a log line on every single operation, and throws almost all of them away.
