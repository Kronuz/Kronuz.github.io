---
title: "The Names Enums Throw Away"
subtitle: "Getting an enum's name back at compile time, which the language keeps refusing to give you."
description: "enum-reflection is a header-only C++20 reflective enum library. Its ENUM_CLASS macro defines a strongly-typed enum class and, alongside it, constexpr accessors that reflect it: turn a member into its source-code name, look a name back up to its member, both through a compile-time perfect hash, so the mapping is branch-light, heap-free, and usable in a static_assert. It exists because C++ throws enum names away: the compiler knows them and does not keep them, so every codebase re-solves logging and parsing enums by hand. The sibling utype adds toUType(e), the missing inverse of static_cast, returning an enum's value as exactly its underlying integer type without silently widening."
excerpt: "The compiler knows the names of your enum members, you just wrote them, and then it throws them away, leaving you to hand-maintain a switch that maps each value back to its own name for every log line and every parse. The twenty-seventh familiar gives the names back, at compile time, through a perfect hash, so an enum and its strings are one constexpr mapping you can even check in a static_assert."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 27
tags:
  - familiars
  - cpp
  - compile-time
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one gives back what the language discards: [enum-reflection](https://github.com/Kronuz/enum-reflection).*

Here is a small, permanent annoyance in C++. You write `enum class Method { GET, POST, SEARCH, COMMIT };`, and the compiler reads those names, understands them, and then **throws them away**. At runtime there is no way to ask "what is `Method::SEARCH` called," because the string `"SEARCH"` does not exist in the program anymore; only the integer does. So every codebase does the same tedious thing, by hand: a `switch` that maps each member back to a string literal of its own name, for logging, and another mapping the other way, for parsing, both of which you must remember to update every time you add a member, and which drift out of sync the first time you forget. The names were right there at compile time. The language just does not keep them.

[enum-reflection](https://github.com/Kronuz/enum-reflection) keeps them. Its `ENUM_CLASS` macro defines a strongly-typed `enum class` and, in the same breath, generates a set of `constexpr` accessors that **reflect** it: turn a member into its source-code name, look a name back up to its member. Everything is `constexpr`, so the enum-to-string mapping is not a runtime table you build at startup; it is compile-time data you can use in a `static_assert`.

## Reflection through a perfect hash

The interesting part is *how* the name-to-member direction works, because that is a lookup from a string to an enum value, exactly the kind of dispatch the last two posts were building toward. The generated accessors route it through a compile-time [perfect hash](/blog/perfect-hash/) over the member names, built with the [hashes](/blog/compile-time-magic/) macros. So looking a name up is not a chain of `if (s == "GET")` comparisons; it is a hash and a couple of array reads into a collision-free table, materialized at build time. The reflection is branch-light, heap-free, and constructs no runtime tables at all. This is the payoff of the whole compile-time chapter arriving in one place: a string switch wants a [hash](/blog/compile-time-magic/), the hash wants to be [collision-free](/blog/perfect-hash/), and enum reflection is what you build once you have both, the enum names dispatched through a perfect hash the compiler computed for you.

It is also why this library sits at the top of a small stack of the others: it pulls in `perfect-hash` for the dispatch and `hashes` for the hashing macros, and those pull their own siblings in turn. A reflective enum is not one idea; it is three of the smaller familiars standing on each other's shoulders.

## The one-liner sibling

Alongside it lives [utype](https://github.com/Kronuz/utype), which is almost too small to mention and too useful to leave out. `toUType(e)` returns an enum's value as its **underlying integer type**, the missing inverse of `static_cast<EnumClass>(int)`:

```cpp
enum class State : std::uint8_t { Idle = 0, Running = 2 };
auto n = toUType(State::Running);   // std::uint8_t, value 2, exactly
```

It is `constexpr` and `noexcept`, and its whole point is that the result type is *exactly* `std::underlying_type_t<E>`, so it never silently widens the way a bare `static_cast<int>` would. It is one line of code, it has no dependencies, and it removes a paper-cut you feel every time you need an enum's raw value without lying about its width. Some familiars are grand; some are just the right small thing.

## Where they fit

Reach for `enum-reflection` whenever you serialize, log, parse, or debug enums and are tired of hand-maintaining two switch statements that drift. Reach for `utype` any time you want an enum's underlying value with its exact type. Skip the reflection if your language or framework already has enum reflection (some do now), or if the enum is tiny and private and a hand-written pair of functions is genuinely less machinery than a macro.

That closes the compile-time chapter, and very nearly the campaign. One familiar remains, and it is not one familiar. It is the whole bag of small, honest tools too little for a post of their own, tipped out onto the table at once, and a look back at the party we have assembled.
