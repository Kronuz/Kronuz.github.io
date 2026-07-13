---
title: "Before the Program Runs"
subtitle: "Switching on a string, classifying a character, and coloring a terminal, all resolved at compile time."
description: "Three tiny header-only C++20 libraries that move work to compile time. hashes gives constexpr hash functions (FNV-1a, djb2, a constexpr xxHash-64) and user-defined literals, so you can write a switch over strings whose case labels are hashes computed by the compiler, the string switch C++ does not have. char-classify is table-driven constexpr character classification with no <cctype> and no locale, so classifying a byte is a masked lookup, correct and locale-independent. term-color expands a named color into stacked ANSI escapes (16-color, 256-color, truecolor, worst first) so one compile-time constant renders at the best tier any terminal supports."
excerpt: "The cheapest work is the work you do before the program starts. This is the compile-time chapter, and it opens with three small libraries that each move a runtime cost to zero: a way to switch on a string, a way to classify a character without the standard library's locale baggage, and a way to color a terminal with a single portable constant. All of it resolved by the compiler, none of it paid at runtime."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 26
chapter: "Compile-Time"
tags:
  - familiars
  - cpp
  - compile-time
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This opens the compile-time chapter with three tiny ones: [hashes](https://github.com/Kronuz/hashes), [char-classify](https://github.com/Kronuz/char-classify), and [term-color](https://github.com/Kronuz/term-color).*

The fastest code is the code that never runs, and the closest thing to that in C++ is code the compiler runs *for* you, before `main` ever starts. `constexpr` turned that from a party trick into a tool: a value computed at compile time costs nothing at runtime, and a mistake in it becomes a compile error instead of a bug. Three of the smallest familiars live entirely in that world, and each one takes a cost you would normally pay every time the program runs and pays it once, at the build.

## A switch over strings

C++ lets you `switch` on an integer and, pointedly, not on a string. The idiomatic workarounds are an `if`/`else if` ladder of `==` comparisons, which is `O(cases)` and ugly, or building a `std::map` at startup, which allocates and is `O(log n)`. [hashes](https://github.com/Kronuz/hashes) offers the third way: a header of `constexpr` hash functions, FNV-1a, djb2, a `constexpr` xxHash-64, integer mixers, jump-consistent hashing, plus `_fnv1a` and `_xx` user-defined literals. Because the hash of a string literal is a compile-time constant, you can hash the input once and `switch` on it, with case labels like `"commit"_fnv1a` that the compiler folds to integers:

```cpp
switch (hash(verb)) {
    case "commit"_fnv1a:  return do_commit();
    case "search"_fnv1a:  return do_search();
    // ...
}
```

That is a real jump table over strings, `O(1)`, no allocation, the case labels checked at compile time. It is the trick that turns a request verb or a token into a branch without a map or a ladder, and it is exactly how a search engine dispatches its dozens of operation names.

## A character table with no locale

Underneath a lot of parsing sits the humble question "is this byte a digit? a letter? whitespace?", and the standard answer, `<cctype>`'s `isdigit` and friends, carries baggage most parsers do not want: it is **locale-dependent**, so the answer can change under you, and it is a function call, not a constant. [char-classify](https://github.com/Kronuz/char-classify) replaces it with one 256-entry table of packed flags and a set of `constexpr` masked lookups, `is_digit`, `is_alpha`, `is_space`, `is_hexdigit`, `tolower`, `toupper`, and a byte-to-hex `char_repr`, with nothing behind them but the standard library. Every classification is a compile-time-capable array read, locale-free and deterministic, so a lexer built on it is faster, portable, and cannot be quietly changed by a `setlocale` somewhere else in the process.

## Color that stays portable

[term-color](https://github.com/Kronuz/term-color) has the cleverest trick of the three. A named color like `RED` or `STEEL_BLUE` expands, at compile time, into an ANSI escape sequence, but the problem is that terminals disagree about which escapes they understand: some do 16 colors, some 256, some 24-bit truecolor. So term-color emits **three escapes back to back, worst first**: the 16-color code, then the 256-color code, then the truecolor code. A terminal applies each escape it recognizes in turn and ends on the last one it supports, so the richest tier it can render wins, and a *single compile-time constant* is portable across every terminal without any runtime detection. When you do need one guaranteed tier, to honor a `--color` mode, the `NO_COLOR` convention, or a plain log file that should get no escapes at all, `collapse()` / `apply()` resolve the stacked string down at runtime. The default is a constant that just works; the runtime path is there for when "just works" is not precise enough.

## The compile-time shelf

These three are one corner of a larger idea, and the chapter they open is the rest of it: the Familiars that mainly live at build time, each moving a cost you would otherwise pay at runtime onto the compiler. Sorted by the job they do:

- **Hashing.** [hashes](https://github.com/Kronuz/hashes): `constexpr` FNV-1a, djb2, a `constexpr` xxHash-64, integer mixers, jump-consistent hashing, and the `_fnv1a` / `_xx` literals. The string switch above stands on it.
- **Perfect hashing.** [constexpr-phf](https://github.com/Kronuz/constexpr-phf): a minimal perfect hash over a *fixed* set of integer keys, built while the program compiles, so a known set of keys becomes a dense, collision-free, branch-free index into a table. The [next post](/blog/perfect-hash/) is all about it.
- **Character classification.** [char-classify](https://github.com/Kronuz/char-classify): the locale-free `constexpr` byte tables above, `is_digit` and its siblings with nothing behind them but a masked array read.
- **Enum reflection.** [enum-reflection](https://github.com/Kronuz/enum-reflection), with [utype](https://github.com/Kronuz/utype): turn an `enum` value back into the name you wrote it with, and the name back into the value, both resolved at compile time. Its [post](/blog/enum-reflection/) closes the chapter.
- **Terminal color.** [term-color](https://github.com/Kronuz/term-color): the worst-first stacked ANSI constant above, portable across terminals with no runtime detection.
- **Wide-integer arithmetic.** [uinteger_t](https://github.com/Kronuz/uinteger_t): arbitrary-width unsigned integers with `constexpr` arithmetic, so a 256-bit constant is folded by the compiler instead of computed at startup. Its post is [The Long Division](/blog/uinteger_t/).

Different jobs, one habit: the answer is a constant the compiler already worked out.

## Where they fit

Reach for these when a cost you keep paying at runtime, a string dispatch, a character check, a color code, could be a constant the compiler folds instead. Skip them where the input is genuinely dynamic and no compile-time form exists. They are small, but they are the honest shape of the idea the rest of this chapter runs on: do it once, at the build.

The next familiar is the machinery under that string switch, made exact: a hash table for a fixed set of keys, built entirely at compile time, that is guaranteed to never collide.
