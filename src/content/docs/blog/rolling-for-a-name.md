---
title: "Rolling for a Name"
subtitle: "The pattern-compiler behind every Xapiand node name."
description: "Xapiand names its cluster nodes with a fantasy-name generator: a tiny pattern language that compiles a string like !<b<||v|V><||s|S|b>> into a tree of choose-and-concatenate nodes, one header, public domain, that can name 7.6 million nodes without repeating. How the compiler works, the trick where strings are generators, the name space it can count for itself, and the adjacent-string-literal footgun that was hiding in its word tables."
excerpt: "Boot a Xapiand cluster and the nodes wake up with names like Manaugh, Chorurn, and Nielsion. They come from a fantasy-name generator I maintain: a pattern language that compiles into a tiny tree and can name seven and a half million nodes without repeating itself. The first familiar I pulled out of the engine."
date: 2026-07-09
draft: true
series: "Familiars"
seriesOrder: 1
tags:
  - familiars
  - cpp
  - compilers
---

*Part of a new series, **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand) and set loose in their own repositories. [A Search Engine from Scratch](/blog/a-search-engine-from-scratch/) opened the engine; each of these opens one creature that used to live inside it. Every campaign starts by naming the party, so this one starts with the thing that does the naming: [fantasyname](https://github.com/Kronuz/fantasyname).*

Boot a small Xapiand cluster and the nodes introduce themselves. Not `node-0`, `node-1`, `node-2`. They come up called **Manaugh**, **Chorurn**, **Nielsion**, **Cualei**. Kill one and a new one joins as **Dielque**. They read like a party sheet from a campaign nobody ran, and that is on purpose: a machine you have to think about for the next three years may as well have a name you can say out loud.

The names are not a lookup table. There is no file of ten thousand fantasy words that Xapiand picks from. There is a **grammar**, and a tiny compiler that turns that grammar into a machine that can produce **7,654,050** distinct node names and never say the same one twice until it has to. That compiler is [fantasyname](https://github.com/Kronuz/fantasyname), and it is the first familiar I want to show you.

## A string that is a program

fantasyname is my C++ port and maintenance fork of the old [RinkWorks](http://www.rinkworks.com/namegen/) fantasy name generator. You hand it a **pattern**, a short string in a little language, and it hands you a generator that spits out a fresh name every time you ask.

```cpp
NameGen::Generator generator("sV'i");
generator.toString();  // "tono'bump"
generator.toString();  // "kalo'numb"
generator.toString();  // "dania'ankle"
```

The pattern `sV'i` reads left to right. `s` is a generic **syllable**, `V` is a vowel or vowel combination, the `'` is a literal apostrophe produced as-is, and `i` is an **insult** ending (the word lists are exactly as silly as they sound). Most letters are a class of random replacement; a handful of punctuation marks are operators:

- `()` wraps text produced **literally**. `s(dim)` is a random syllable followed by `dim`.
- `<>` wraps a **group** of the pattern symbols above.
- `|` is a **random choice**. `(foo|bar)` is `foo` or `bar`; `<c|v|>` is a consonant, a vowel, or, because the last option is empty, nothing at all.
- `!` **capitalizes** what follows, `~` **reverses** it.

That is the whole language. It is enough to write the pattern Xapiand actually uses for a node name:

```text
!<b<||v|V><||s|S|b>>
```

Capitalize the whole thing (`!`), then: a name **fragment** (`b`), then a slot that is *empty, or a vowel, or a vowel combination* (`<||v|V>`), then a slot that is *empty, or a syllable, or a bigger syllable, or another fragment* (`<||s|S|b>`). Run it a dozen times and you get the roster from the top of this post. The empty alternatives are the trick that keeps the names varied in length: **Can** and **Rama** and **Lumi** fall out of the same pattern as **Claudetu** and **Nielsion**, because two of the three slots rolled empty.

## The pattern is compiled once, not parsed every time

The naive way to build this is to walk the pattern string on every single call, branching as you go. fantasyname does not. It compiles the pattern **once**, into a tree, and then generating a name is just a walk of that tree with a die in your hand.

Two kinds of node do all the work. A **Sequence** holds children and concatenates them: its `toString()` is every child's `toString()` glued together, in order. A **Random** holds children and picks exactly one: its `toString()` is a single child's, chosen at random. Everything the grammar can express is some nesting of *concatenate these* and *choose one of these*. A symbol like `s` becomes a Random over the 115 words in the syllable list. A `|` becomes a Random over the alternatives. Plain letters between them become a Sequence.

The leaves are the part I find quietly beautiful. In this design **a generator is anything with a `toString()`, and a bare string qualifies**. The literal `dim` in `s(dim)` is not wrapped in a special LiteralNode class; it is just the string `"dim"`, sitting in the tree as a generator whose `toString()` returns itself. And because the constructors collapse the trivial cases, a Random with one child is *replaced by that child*, a Sequence of one string *is* that string. The tree that survives compilation is the smallest one that still produces the right names.

```d2 alt="The pattern sV'i compiles to a Sequence of four children stacked in order: a Random over 115 syllables, a Random over vowel combinations, the literal apostrophe string, and a Random over insult endings. Each Random picks one child at toString() time; the Sequence concatenates them into a name."
direction: down
seq: "Sequence  (concatenate in order)" {
  grid-columns: 1
  s: "Random · s   (115 syllables)"
  v: "Random · V   (vowel combos)"
  lit: "literal  \"'\""
  i: "Random · i   (insult endings)"
}
out: "\"tono'bump\""
seq -> out: "toString()"
```

Generating a name is then dirt cheap: descend the tree, and at every Random roll for a child, at every Sequence append. No parsing, no allocation of a new structure, no lookups by name. The expensive, branchy work happened at compile time; the hot path is a walk.

## It can count its own names

Because the tree is just *concatenate* and *choose*, it can measure the size of the world it can produce, exactly, without generating anything. Sequences **multiply** their children's counts (every combination of the parts), Random nodes **add** theirs (this alternative or that one). One recursive pass:

| pattern | what it is | possible names |
| --- | --- | --- |
| `s` | one syllable | **115** |
| `sV'i` | the RinkWorks demo | **118,910** |
| `!<b<||v|V><||s|S|b>>` | a Xapiand node | **7,654,050** |

Seven and a half million is not a number I picked. It is the tree counting itself: the product of the fragment list, the *empty-or-vowel* slot, and the *empty-or-syllable-or-fragment* slot, summed across the empty branches. It is also the answer to the only question that actually matters for node names, which is "how long until a collision is likely?" With 7.6 million names and the birthday bound, you are into even odds of two nodes rolling the same name at a few thousand nodes, and a real cluster is nowhere near that. The whimsy is free; the uniqueness is arithmetic.

## The two symbols I added

RinkWorks names are gnomish and jokey by design (the `i` list really is insults). Xapiand nodes wanted the same *shape*, pronounceable and human, but a little more like a person and a little less like a punchline. So the one change I made on top of the upstream grammar was two new symbol groups: **`S`**, a larger set of open syllables (`bra`, `cie`, `dria`, `gua`, `lio`...), and **`b`**, a set of name fragments (`bel`, `chor`, `claud`, `nio`, `rama`...). The node pattern leans on both. Because the compiler reads its symbol table by name, adding a class was purely data: drop two lists into the map, and `S` and `b` immediately became usable anywhere in a pattern. No parser change, no new node type. The grammar extended itself.

## The comma that wasn't there

Here is the oozing bit, and it is a good one, because it is invisible until it isn't.

The word lists are C++ initializer lists of string literals, hundreds of them, wrapped to fit the page:

```cpp
"des", "det",
"dieg", "dic", "diel", "dier", "dil", "din",
```

C and C++ have a rule most of us learned once and then filed away: **two string literals with nothing but whitespace between them are concatenated into one**. `"foo" "bar"` is `"foobar"`, at compile time, silently, on purpose. It is how you split a long literal across lines. It is also a loaded gun pointed at any hand-maintained list of literals, because the thing that separates two entries is a single comma, and if your finger slips, the compiler does not complain. It just glues them together and moves on.

Two commas had slipped, buried in the middle of a few hundred fragments. `"dieg", "dic"` had at some point been typed `"dieg" "dic"`, and the list quietly held a single Frankenstein word, `"diegdic"`, where two were meant to be. Same for `"sac" "sal"` becoming `"sacsal"`. Nothing crashed. Nothing warned. The generator kept producing perfectly good names, and then, once every few thousand rolls, it produced a node called something like **Diegdicion**, which is not a name so much as a typo wearing a name's clothes. You would see it, blink, and assume the random generator had simply rolled something ugly, because rolling something ugly is literally its job.

I only caught it by staring at the raw fragment list long enough for the two runts to look wrong next to their neighbors. The fix is a comma. The lesson is that a data table of adjacent string literals has no syntactic floor: every entry is one typo away from silently merging with the next, and no tool in the normal build will tell you. If you keep word lists this way, the entries are worth *reading*, not just compiling.

## Why keep a name generator in your toolbox

It sounds like a toy, and for its first thirty years it mostly was one. But a compiled, self-counting generator of pronounceable strings turns out to be a genuinely useful small tool, and not only for cluster nodes:

- **Memorable identifiers for things humans have to talk about.** A node you name Chorurn is a node you can page a colleague about; `10.2.44.7:8880` is not.
- **Test fixtures that look like data.** Seeding a database with a thousand users named from `sV'i` reads far more like the real thing than `user_0001`, and it is one line.
- **World-building on tap**, which is where it started, and where the D&D-shaped part of my brain is delighted it ended up again.

The whole thing is one header and a source file of word lists, public domain, with ports in JavaScript, TypeScript, C, Perl, and Elisp riding along in the same repo. It asks for nothing and it is fun to have around.

That is the first familiar. Small, self-contained, a little compiler wearing a jester's hat, with one genuine trap sewn into its lining. Next time I will pull out one that is not fun at all: the one that has to run **inside a signal handler**, where almost everything you would normally reach for is quietly forbidden.
