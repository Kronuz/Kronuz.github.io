---
title: "A Tree Made of Types"
subtitle: "A word lookup the compiler builds letter by letter, and why it lost the race."
description: "ctrie is a one-header C++17 compile-time trie: it turns a fixed list of words into nested template types, one per letter, and maps any string to that word's position in the list, or to npos when it is not there. There are no tables, no hashing and no allocation, and a lookup of a constant string can run inside a static_assert. Measured against a compile-time perfect hash on 192 real field-type names, it takes about 1.4 times as long per lookup, which is why it stays a reference and a benchmark contender."
excerpt: "A dictionary does not make you read every word to find one; you follow the letters. The thirty-second familiar builds that path out of the compiler's own type system, one letter at a time, so a fixed word list becomes a tree that exists only while the program compiles. It is exact, simple, and slower than a perfect hash, and the numbers say by how much."
date: 2026-11-04
authors: kronuz
series: "Familiars"
seriesOrder: 32
chapter: "Compile-Time"
tags:
  - familiars
  - cpp
  - compile-time
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is a word list the compiler turns into a tree: [ctrie](https://github.com/Kronuz/ctrie).*

Think of how you find a word in a paper dictionary. You do not read it from the first page. You open to the **P** section, then look for **PO**, then **POS**, and each letter throws away most of the book. A *trie* (pronounced "try", from re*trie*val) is that idea as a data structure: a tree where every step down is one letter, and words that start the same way share the same path for as long as they agree.

Programs often look words up in a *fixed* list known before they run: an HTTP server asking whether a request is `GET`, `POST` or `PUT`, a query language checking its reserved words. Since the list never changes, the compiler can do the work once, at build time.

[ctrie](https://github.com/Kronuz/ctrie) does that. You hand it the words, and it gives back an object whose `find()` returns each word's position in your list, or `ctrie::npos` (a special "not found" value) for anything else:

```cpp
// The trie is built while compiling; these checks run in the compiler too.
constexpr auto methods = ctrie::build("GET"_cword, "POST"_cword, "PUT"_cword);
static_assert(methods.find("POST") == 1);
static_assert(methods.find("PATCH") == ctrie::npos);
```

A `static_assert` is a check the compiler performs while building. If either line were wrong, the program would not compile. The same `find()` works at run time on a string a user typed.

## A tree with no memory

Most tries live in memory: nodes allocated on the heap, pointers from parent to child. ctrie keeps none of that. Every node is a C++ *type*, the kind of thing the compiler tracks the way it tracks `int` or `std::string`, and the tree is those types nested inside each other. For the three words above, the shape the compiler builds looks like this:

```
root
 ├─ G ─ E ─ T ─ (end) = 0
 └─ P ─┬─ O ─ S ─ T ─ (end) = 1
       └─ U ─ T ─ (end) = 2
```

`POST` and `PUT` share the `P` node and split after it. Each word also gets an invisible end marker, and the word's position is stored there, so `PO` walks two letters, finds no end marker, and comes back as not found. A prefix is not a word, and neither is `POSTS`; the tests check both.

The `_cword` suffix is what makes this possible. It is a *literal operator*, a small function that the compiler calls on a string literal, and this particular form hands the function the string's characters one by one as compile-time values. That is how `"GET"` becomes three letters the type system can arrange into a tree. When the program runs, the tree is gone. What is left is the code that walks it: compare the next character, step into the matching child, repeat. No tables, no allocation, nothing to initialize at startup.

## Why the perfect hash wins

The [perfect hash](/blog/perfect-hash/) from earlier in this chapter solves the same problem a different way. It turns the word into a number with a hash function, then jumps straight to that number's slot, a fixed handful of arithmetic no matter how many words there are. A trie cannot jump. At every letter it tries the children one after another until one matches, so at the root of a list of 570 English stop words it may compare the first letter against many candidates before it takes a single step.

The [constexpr-phf benchmarks](https://github.com/Kronuz/constexpr-phf/blob/master/docs/BENCHMARKS.md) time ctrie beside the perfect hash and the standard containers on two real word sets: Xapiand's 192 field-type names, looked up 200,000 times with half of them misses, and the 570 stop words filtered out of the whole text of *The Count of Monte Cristo*. Here is the perfect hash with its membership check, ctrie, and `std::unordered_set` (the standard library's hash table), on an Apple M4 Pro and an Intel Core i9:

| Contender | Names, M4 (ns) | Names, i9 (ns) | Stop words, M4 (ms) | Stop words, i9 (ms) |
| :-- | ---: | ---: | ---: | ---: |
| Perfect hash, verified | 14.1 | 21.4 | 4.53 | 6.74 |
| ctrie | 19.8 | 30.9 | 7.60 | 12.1 |
| `std::unordered_set` | 20.0 | 40.9 | 7.07 | 15.7 |

The perfect hash wins every column. ctrie takes about **1.4 times as long** on the names and **1.7 to 1.8 times as long** on the stop words. Against the standard hash table it is a tie on the M4 and clearly ahead on the Intel machine, which is respectable for a structure with no hash function at all.

So when does a tree of types beat a perfect hash? Not on speed, in any of these runs. Its advantages are of a different kind. It needs no hash function, so there is no choice of hash to tune and no chance of two words colliding. It is always exact: the perfect hash's fastest mode skips the final string comparison and can mistake a stranger for a member whose hash it shares, while ctrie compares every letter and cannot. And a miss can end at the first letter that no word in the set starts with. Those make it a clear, honest reference, and the right yardstick to keep the faster thing truthful.

## The gnarly bits

Three things bite, and all three come from living inside the compiler.

**Every word costs build time.** Building the tree is the compiler instantiating types, one step per word and one node per new letter, so a bigger list means a slower build, paid on every compile. The steps also nest, one inside the last, and compilers cap how deep that nesting may go. The 570 stop words fit under the default; a list of many thousands is the wrong job for this tool.

**The literal operator is not standard C++.** The form of `_cword` that receives a string's characters is an extension that Clang and GCC accept and MSVC rejects, and Clang warns about it. The header silences that warning around the one line that needs it. For a while it switched the warning off and never switched it back on, so every file that included ctrie had the warning quietly disabled for its own code too, like a "do not disturb" sign left on a door after the meeting ended. The header now restores the setting right after the operator.

**Release builds deleted the tests.** The run-time checks were plain `assert`s, which a Release build removes. With them gone, one test variable was left unused, the warnings-as-errors build failed, and in any case nothing was being checked. The test now forces its asserts on in every build type, so Debug and Release both run every lookup.

## Where it fits

Xapiand does not call ctrie today. Its keyword dispatch runs on constexpr-phf, and ctrie lives on as the contender in that library's benchmarks, where it keeps the perfect hash honest. It is one C++17 header with no dependencies, tested in CI on Linux, macOS and FreeBSD.

Reach for it when you want the simplest exact answer to "which of these few words is this?", checkable in a `static_assert`, with no hash to pick, or as a readable reference for how a type-level trie works. Skip it for production dispatch, where the [perfect hash](/blog/perfect-hash/) is faster on every measured set, for large word lists, and for MSVC.
