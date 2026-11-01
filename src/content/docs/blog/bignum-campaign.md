---
title: "One Fun Task"
subtitle: "A day of agents chasing GMP with my old bignum"
description: "On a Friday evening I asked whether uinteger_t, the header-only C++ bignum I mostly wrote in 2017, could be made substantially faster. About twenty-three hours later, a campaign of AI coding agents I directed had it printing decimals up to 530 times faster than before and faster than GMP on numbers from 256 to 4,096 bits, with most other operations at 1.2 to 2.3 times GMP's time. What landed, what the reviewers rejected, and the two rules that kept it honest: measure everything, and have someone else check it."
excerpt: "\"One fun task. Can it be substantially optimized?\" I asked that about my old bignum header on a Friday evening. By Saturday evening a team of AI agents had rebuilt its insides, reviewers had rejected three of their branches, a benchmark run had gone in the bin, and the library sat within striking distance of GMP."
date: 2026-11-01
authors: kronuz
tags:
  - cpp
  - performance
  - algorithms
  - ai
  - agents
---

"One fun task," I typed on a Friday evening. I pasted the link to [uinteger_t](https://github.com/Kronuz/uinteger_t) and asked: "Can it be substantially optimized?"

uinteger_t is an arbitrary-precision unsigned integer in a single C++ header, a number with no ceiling that still reads like `a * b + c` (its [Familiars post](/blog/uinteger_t/) has the tour). [base-x](https://github.com/Kronuz/base-x), my base58 and base62 codec, does its math on it. It started as Jason Lee's `uint128_t`, a fixed 128-bit type; in 2017 I turned it into the arbitrary-precision monster it is, and until this campaign most of its code was mine. Nothing was broken and nobody was waiting on it. It was a fun question for a Friday night.

About twenty-three hours later the answer was yes. Printing a 262,144-bit number in decimal went from 1.5 seconds to under 3 milliseconds. uinteger_t now prints decimal faster than [GMP](https://gmplib.org/) 6.3 on numbers from 256 to 4,096 bits, though GMP pulls ahead from 16,384 bits. Most other operations take 1.2 to 2.3 times GMP's time. base-x encodes a 32-byte key in base58 in 74 nanoseconds, against 48.5 for [Firedancer](https://github.com/firedancer-io/firedancer)'s fixed-size codec.

I did not write the new kernels. A team of AI coding agents did, in what I call a campaign: I set the goals and the rules, and I made the calls when asked. The lead agent ran on Claude Opus 5.5, and the developers, reviewers and explorers on Claude Sonnet 5.5. This post is about both halves, what it took to get a small header within striking distance of GMP, and what it was like to direct the work instead of doing it.

## The monster

The original `str()` printed a number by calling the full long division once for every digit, and the parser did a full multiply and a full add for every character. That is two heap-allocated temporaries per character. On an Apple M1 Pro, printing those 262,144 bits in decimal took 1.52 seconds.

Eighteen minutes after my question, there was [a first commit](https://github.com/Kronuz/uinteger_t/commit/aeeeb67): divide in place by the largest power of ten that fits a 64-bit limb, 10 to the 19th, and peel off nineteen digits per pass. Decimal printing got 15 to 39 times faster and parsing about 76 times. base-x got the same treatment, and encoding a 32-byte key in base58 got about ten times faster.

Early on I asked for a running list of the lessons I should learn from all this, since I had written most of the monster myself. It ended at twenty-six. The first one reads: "A generic op in a loop is the quadratic trap."

## Assembling the party

The goal I gave was blunt: optimize both libraries to the maximum, the generic parts of uinteger_t included, keep the benchmarks, match or beat GMP, Boost.Multiprecision and the usual base58 codecs, and push each piece once it is verified. I had suggested a quick campaign from the start, so it became one.

A lead agent holds the plan and splits it into workstreams. Each one goes to a developer agent on its own branch, in its own git worktree, with a ledger of what is done and what blocks it. Explorers take cheap, measured shots at one question. A researcher took one hard piece, fast base conversion at small and medium sizes, to the literature. Once the campaign was running, every new algorithm and everything that parses input went to reviewers who had not written it (a code reviewer, and a security reviewer wherever untrusted bytes come in). They built the branch from a fresh context, ran the tests under sanitizers, wrote their own probes and mutants, and ruled APPROVE, APPROVE WITH CONDITIONS, or REJECT. A few small kernel tweaks landed on the lead's own tests and timing.

```d2 alt="Inside my goals, rules and calls, the lead hands each workstream to a developer on its own branch, explorers feed the developer measured wins, and the branch goes to code and security reviewers, who send a REJECT back to the developer and an APPROVE on to master."
direction: down
rules: "My goals, rules and calls" {
  label.near: outside-top-left
  lead: "Lead agent: plan and timing"
  explorer: "Explorers: quick experiments"
  dev: "Developer: own branch and worktree"
  review: "Reviewers: code, security" { style.bold: true }
  lead -> dev: workstream
  explorer -> dev: measured win
  dev -> review: branch
  review -> dev: REJECT
}
master: "master, pushed"
rules.review -> master: APPROVE
```

By the end, the plan's workstream table had 31 rows, uinteger_t had 146 new commits and base-x more than 50, and the reviewers had written 19 reviews. While I was away, status reports landed in my terminal.

My part was to say what "done" meant and what counted as proof, and to make the calls that were mine. When I stepped away in the afternoon, the lead wrote down the calls it made in my place, for me to review later, and left the one that would change the output of Bitcoin's base58 preset for me. I took it that evening: `bitcoin()` and `ripple()` [keep leading zero bytes](https://github.com/Kronuz/base-x/commit/27be05e), as Bitcoin and the XRP Ledger do.

## Table rules

Four rules did most of the work.

**Measure, or it did not happen.** If you have read [One More Benchmark](/blog/one-more-benchmark/), this one will not surprise you. Every speed claim needed a number, and the number had a protocol: an A/A run first (the same build against itself, to learn the noise), then the change interleaved against master, on a quiet machine under an exclusive hold, at the sizes people use. The early timings ran on an Apple M4 Pro, and the A/B runs and the final tables on an Apple M1 Pro and an Intel Core i9-9980HK laptop.

**The faster path wins.** When I asked whether Newton division would replace the recursive one, I said I would choose the faster, and that even a 10% win is a good one ("benchmarking, obviously, when it matters"). The plan wrote it down as: keep anything measurably faster, and simplify only when the gain is within about 3%, near the noise. Toom-4 squaring measured 0.6% faster than Toom-3 at 1,024 limbs, with an A/A spread of 0.2%, so it went, along with [51 lines of the header](https://github.com/Kronuz/uinteger_t/commit/2bde294). Toom-4 multiplication, 5.9% faster at the same size, stayed. A variant of addition for tiny sums won a nanosecond or two on the M1 Pro and lost one or more on the Intel, so it stayed on its branch.

**Docs describe the present.** "'What changed' belongs to a changelog, not README.md," I said, and the campaign kept to it: the READMEs say what the code does today, and the before-and-after numbers live in the changelogs and the commit messages.

**MIT means papers.** uinteger_t is MIT and GMP is LGPL. "Note uinteger_t is MIT, so be careful," I said, and the prompts for the algorithm work spelled it out: write from the papers and first principles, and do not read GMP's source. GMP went into the benchmark as a yardstick and into a local fuzzer as an oracle, and nowhere else. That makes this a clean-room optimization: every kernel was written from published algorithms and first principles, and no line of GMP is in either library. Boost, Firedancer and libbase58, all permissively licensed, appear only as yardsticks in the benchmarks, built from their own checkouts.

## What landed

Base conversion was the biggest win, in three steps. Chunking came first. Then the researcher came back with a division-free kernel: Bouvier and Zimmermann's [division-free binary-to-decimal conversion](https://doi.org/10.1109/TC.2014.2315621) from 2014, with its one remaining division replaced by a cached reciprocal, so the inner loop is all multiplications the CPU can overlap. Base58 of 32 bytes [went from 156 to 34 ns](https://github.com/Kronuz/uinteger_t/commit/8486c75). Above 8,192 bits a tree of divisions and multiplications takes over, and [decimal printing of 65,536 limbs went from 9.2 seconds to 145 ms](https://github.com/Kronuz/uinteger_t/commit/6e74834).

Early on I had written: "Who knows, we may even come up with our very own novel algorithm and a new paper!" The researcher checked. Every ingredient was published or folklore, and its verdict was that the result is "worth a blog post, not a paper." So here we are.

Multiplication climbs a ladder by size: a schoolbook that does two rows per pass, Karatsuba from 24 limbs, Toom-3 from 140, Toom-4 from 400, and from 1,400 limbs a [number-theoretic transform over three primes](https://github.com/Kronuz/uinteger_t/commit/ee0a379), which took multiplying two numbers of 256K limbs (16.8 million bits each) from 372 to 52.7 ms, against GMP's 48.1.

Division got a ladder too: recursive division after Burnikel and Ziegler from 2,048-bit divisors, Newton iteration for the largest ones, and for `a / b` alone, a schoolbook division that, for each quotient digit, subtracts only the top part of that digit times the divisor, and repairs its state when a digit lands too close to call. That last one came with a written proof in five lemmas, and reviewers re-derived them, the repair line by line against the code, before [it landed](https://github.com/Kronuz/uinteger_t/commit/a9af8cf). Small values got an inline buffer: up to 8 limbs (512 bits) live inside the object and never touch the heap, so `a + b` on them [now takes 2 to 5 ns instead of 16 to 19](https://github.com/Kronuz/uinteger_t/commit/8f1345e).

Then the two changes I like best. Both came from explorers, and both are tiny.

Every multiplication of numbers under about 90,000 bits, where the transform takes over, ends in the schoolbook loop: long multiplication as taught in school, one 64-bit limb at a time. Karatsuba and Toom split bigger numbers into pieces until the pieces are small enough for it. At the loop's core sits a multiply-add, `x * y + a + c`, written as one 128-bit sum. The compiler added `a + c` first, which put three dependent operations on the carry chain of every limb. Adding the carry last leaves two:

```diff
 // _multadd at 64-bit limbs, simplified from 5ee8586
-auto r = (u128)x * y + a + c;
-*lo = (digit)r;
-return (digit)(r >> 64);
+auto p = (u128)x * y;
+digit l = (digit)p, h = (digit)(p >> 64);
+digit s = l + a;  h += s < l;   // add a first,
+digit t = s + c;  h += t < s;   // the carry last
+*lo = t;
+return h;
```

Same value, shorter chain: multiplication got 8 to 11% faster from 16 to 1,024 limbs, and squaring 6 to 10%, for [a twelve-line change](https://github.com/Kronuz/uinteger_t/commit/5ee8586).

Addition had the same disease in another spot. With one limb per pass, the compiler moved the carry through a general register, `adds; cset; adds; csinc` on arm64, two cycles per limb, where GMP's chain of `adcs` runs at one. Eight `_addcarry` calls per pass let it keep the carry in the CPU's flag: [29 lines](https://github.com/Kronuz/uinteger_t/commit/bd83419), 30% faster from 256 limbs. Nobody planned that one. It came out of the final benchmark table, where addition had the worst ratio to GMP.

## Three times no

Of the 19 reviews, three said REJECT, and only one came back with a plain APPROVE.

The first REJECT hit `digits()`, the new API base-x converts through. The security reviewer found its size arithmetic unguarded: on a 32-bit `size_t`, a 512 MiB input wraps the limb count, and the packing loop writes past the end of a heap buffer. It had no 32-bit toolchain, so it modeled the wrap, said exactly that, and crashed the model. It also found base-x's checksum sums kept in an `int`, which overflows at about 34 million characters. Both were fixed and rechecked before anything landed. Hours later, the subquadratic conversion tree added a new path through the same code, repeated the same class of bug on it, and its review rejected it for the same reason. The third REJECT was the inline buffer: if allocating the carry limb failed, `x += y` could leave `x` an invalid value.

The one I keep thinking about was not a REJECT. The quotient-only division is exact only while the quotient is shorter than B limbs, where B is the limb base, and a guard enforces it. The guard compared the quotient's length with `~static_cast<digit>(0)`, meant to be the largest digit. At 64- and 32-bit limbs, it is. At 16-bit limbs, C++ promotes the `uint16_t` to `int` before applying `~`, so the expression is -1, the cast to `size_t` turns it into `SIZE_MAX`, and the guard reads `qn > SIZE_MAX`: never true. The reviewer also showed the guard was load-bearing, with a small model in base 4 where a quotient two digits too long produced a wrong digit, unflagged, once in 40 million cases. [One expression and one test fixed it](https://github.com/Kronuz/uinteger_t/commit/392c7f8).

The reviewers caught the lead, too. Resolving a merge conflict in `CMakeLists.txt`, the lead's script took the branch's side and silently dropped the Debug arguments of 39 test targets; the Newton review found it. CI's ThreadSanitizer job broke twice on landing, the second time on the lead's own fix, because a test replaced `operator new` and the TSan runtime defines it too. Each miss went into a calibration file, next to the check that would have caught it.

And the hunters, explorers sent to look for bugs behind the landings, found five that were already in my original headers, two in uinteger_t and three in base-x. They reproduce byte for byte against them. My favorite: after `x >>= 64`, `x *= 1` handed back the bits the shift had dropped.

The measurement had bugs of its own. The Intel laptop also runs another session's benchmarks, and the campaign's lock only ordered its own runs, so one final run overlapped that session's exclusive A/B and went in the bin. Later, two holds with the same name turned out not to exclude each other, so an A/B ran beside a division run. Its clean rerun gave the same numbers, and only the rerun counts.

## The scoreboard

The comparison with the original header ran on the M1 Pro in the afternoon, before the last two landings (the eight-limb addition and the quotient-only division):

| 262,144 bits, ms | original | after | GMP 6.3 | Boost `cpp_int` |
|---|---:|---:|---:|---:|
| `a.str(10)` | 1,522 | 2.87 | 1.62 | 152 |
| `uinteger_t(s, 10)` | 171 | 1.41 | 0.76 | 5.71 |
| `a * b` | 4.65 | 0.58 | 0.43 | 2.60 |
| `a * a` | 4.77 | 0.42 | 0.28 | 2.59 |
| `a / b`, b half of a | 3.94 | 0.89 | 0.39 | 13.0 |

Milliseconds per call for random operands, Apple clang 21 at `-O2`, the best of two runs of [`bench/bench.cc`](https://github.com/Kronuz/uinteger_t/blob/master/bench/bench.cc). Across sizes from 128 to 262,144 bits, decimal printing is 43 to 530 times faster than the original, parsing 57 to 121 times, multiplication up to 8 times and squaring up to 11.

The final numbers are in the [README](https://github.com/Kronuz/uinteger_t/blob/a383e37/README.md#-performance), from 256 bits to a million. Decimal printing beats GMP at every size measured from 256 to 4,096 bits, and [GMP is faster from 16,384 bits on](https://github.com/Kronuz/uinteger_t/blob/631e4a5/docs/perf/gmp-boost.md), with nothing measured in between. Elsewhere uinteger_t takes 1.2 to 2.3 times GMP's time, with one outlier: a fresh 4,096-bit sum takes 3.4 times, because allocating the result costs more than the addition. When I read "GMP reuses its output, we allocate" in the plan, I asked what it meant. GMP writes each result into an `mpz_t` you already have, while uinteger_t's operators return a new value; `mul(r, a, b)` and `divmod(q, r, a, b)` write into existing values for callers who want that. [Boost.Multiprecision](https://www.boost.org/doc/libs/release/libs/multiprecision/)'s `cpp_int` takes 2 to 4 times uinteger_t's time at 256 bits, and at a million bits 8 times as long for a multiplication and 118 times for decimal printing, but up to 4,096 bits it parses decimal faster than uinteger_t, which pulls ahead from 16,384 bits. The Intel laptop shows the same pattern.

base-x's final numbers are in [its README](https://github.com/Kronuz/base-x/blob/919698e/README.md#-performance): on the M1 Pro it encodes a 32-byte key in base58 in 74 ns (52 when it writes into a string it reuses), against 48.5 for Firedancer, and decodes it in 72 against 63. At 64 bytes it decodes in 98 ns, half of Firedancer's 198. [libbase58](https://github.com/bitcoin/libbase58) takes 7 to 200 times as long as base-x from 32 to 256 bytes. On the Intel laptop, base-x takes about twice Firedancer's time at 32 bytes and matches it decoding 64. Getting there took two steps: chunking made the 32-byte encode about ten times faster, and [the division-free kernels](https://github.com/Kronuz/base-x/commit/2c21ec4) then took it from 203 to 73 ns.

## Why not just use GMP?

If you need the fastest big-number arithmetic there is, use GMP. It is faster at almost everything, and the reason is not a better algorithm: [its manual](https://gmplib.org/manual/Binary-to-Radix) describes the same divide-and-conquer conversion that uinteger_t uses above 8,192 bits. GMP's edge is underneath, in division and multiplication kernels written in assembly for each CPU and tuned per machine. Big conversions are mostly big divisions, and uinteger_t's division takes about twice GMP's time, so above 4,096 bits its conversions fall behind, by up to about as much.

uinteger_t is for the other case: a number wider than 64 bits inside a C++ program that should not grow a dependency. It is one MIT-licensed header with no build step, where GMP is an LGPL library you build and link for every target. A value of up to 512 bits never touches the heap, and that is where its users live: base-x's keys and Xapiand's ids. It prints decimal faster than GMP from 256 to 4,096 bits, and it divides a 128-bit number by a 64-bit one in 2 nanoseconds, against GMP's 12, on the M1 Pro. And against the other header-only choice, Boost's `cpp_int`, it is 2 to 4 times faster at 256 bits, parsing decimal aside, and up to 118 times faster at a million.

What it is not for is cryptography. My question about that came from my student days, when I learned how keys like RSA's work by building them with big integers: pick two large primes, multiply them, and raise numbers to huge powers modulo the result. A bignum library does all of that math, so I asked what uinteger_t would need to be decent at it. The answer was that it cannot be, not as it is built. Every operation's time depends on the values it touches: a carry here, a number trimmed shorter there, a shortcut in a comparison. Someone who can time those operations learns bits of the key. Cryptographic code works on numbers of a fixed width in constant time, never branching on a secret, and earns trust through its own reviews and timing tests. That would be a second type in its own header, so the README now says to keep keys out of uinteger_t. Modular arithmetic for public values would still fit the library, and whether to build it is my call.

## What is left

Plenty, and each repository's OPEN-WORK.md says so ([uinteger_t](https://github.com/Kronuz/uinteger_t/blob/master/docs/OPEN-WORK.md), [base-x](https://github.com/Kronuz/base-x/blob/master/docs/OPEN-WORK.md)).

- Addition still takes 0.43 ns per limb against GMP's 0.31. The last of that gap needs assembly.
- A short quotient against a long divisor is slow: a 4-limb quotient by a 2,048-limb divisor takes 1.3 microseconds on the Intel laptop, against GMP's 0.09.
- On the Intel, a `malloc` and `free` pair costs 37 ns, so the `std::string` that base-x returns is about a third of its encode time, and the digit-to-character map there is scalar.

## The part I did

I wrote none of this campaign's code. The library it reworked is the one I built in 2017 on Jason Lee's `uint128_t`: the arbitrary-precision type, its operators and its base conversion. The campaign kept that shape and that API and replaced the arithmetic underneath. Of everything I asked for, the two rules that paid for themselves were the plain ones: believe no speedup until it beats the noise on a quiet machine, and have someone who did not write a branch try to break it before it lands. The agents were fast. The reviewers are why I trust what they wrote.

Thanks to Jason Lee, whose `uint128_t` I grew uinteger_t from. Thanks to the classics it all stands on: Knuth, whose second volume of *The Art of Computer Programming* is cited all over the header, Karatsuba, Toom and Cook, and Brent and Zimmermann's *Modern Computer Arithmetic*. And thanks to the people whose papers did the heavy lifting: Bouvier and Zimmermann, Burnikel and Ziegler, Bodrato and Zanoni, Pollard, Montgomery, Möller and Granlund, Shoup, Harvey, and Barrett. The header cites each one where its idea is used. The code, the benchmarks, and the changelogs with every number and commit are on GitHub: [uinteger_t](https://github.com/Kronuz/uinteger_t/blob/master/CHANGELOG.md) and [base-x](https://github.com/Kronuz/base-x/blob/master/CHANGELOG.md).
