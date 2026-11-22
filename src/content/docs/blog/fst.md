---
title: "A Map of Blocks"
subtitle: "How a search engine keeps every word it knows in a few bytes each."
description: "fst is a header-only C++20 finite state transducer, a compact ordered map from byte strings to 64-bit numbers that is read in place, and termdict is the term dictionary built on it: sorted, prefix-compressed blocks of words with a small fst over each block's first word. On the 235,976 words of /usr/share/dict/words the fst takes 6.20 bytes per word against 56 to 73 for hash maps, and the whole term dictionary, values included, takes 11.04, with an index of 52 KB."
excerpt: "A search engine has to remember every word it has ever seen, keep them in order, and find any one of them in a fraction of a microsecond, often from a file it has not even read yet. The thirtieth familiar is really two: a tiny machine that spells out a whole vocabulary in about six bytes a word, and the dictionary that uses it as a table of contents."
date: 2026-11-02
authors: kronuz
series: "Familiars"
seriesOrder: 30
chapter: "Bytes"
tags:
  - familiars
  - cpp
  - search
  - data-structures
---

*Part of [**Familiars**](https://kronuz.github.io/cpp-libraries/), my collection of standalone C++ building blocks. This one is two libraries that only make sense together: [fst](https://github.com/Kronuz/fst), a compact ordered map, and [termdict](https://github.com/Kronuz/termdict), the dictionary built on top of it.*

Every search engine keeps a list of every distinct word it has indexed, each with a little record: how many documents contain it, and where to find them. That list is the **term dictionary**. Type "apple" in a search box and the first thing the engine does is look "apple" up in it.

It sounds like a job for a hash map, and for one lookup it is. But the dictionary is asked for more than exact words. "Everything starting with *app*" is a question about order. Merging two indexes means walking both dictionaries alphabetically, side by side. And an engine with thousands of indexes would like to open each dictionary straight from a file on disk without first rebuilding it in memory.

## The answers you reach for first

A **hash map** turns each word into a number and jumps straight to it. On an Apple M4 Pro, Abseil's hash map finds a word in about 18 nanoseconds. It also spends 73 bytes per word, it has no idea that "apple" comes before "apply", and it has to be rebuilt in memory every time you load it.

A **sorted list** fixes the order and can be squeezed: neighbors share their beginnings ("apple", "applet", "apply"), so you store only what changes, about 6 bytes per word. But finding a word means a binary search, halving the list again and again, each step landing somewhere new in memory.

## A machine that spells words

Picture the dictionary as a set of paths, one letter per step. "cat" and "cats" share the path c, a, t. That much is a trie, the tree behind many autocompletes. A **finite state transducer**, an FST, goes one step further: it shares *endings* too. "in", "on" and "tin" all finish with n, so after the n they can all arrive at the same spot. Merge every path that looks the same from some point on, and a whole vocabulary folds into a small graph.

The "transducer" part is how each word gets its number. Steps carry small amounts, and a word's value is the sum of the amounts on its path. The builder pushes those amounts as close to the start as it can, so words that share a beginning share most of their sum.

The builder takes words in sorted order and, whenever a branch is finished, reuses an identical branch if one already exists (a method from a 2000 paper by Daciuk and colleagues). The result is one flat run of bytes that the reader searches right where it lies, in a string or a file mapped into memory. Order comes for free: taking the smallest letter at each step visits the words alphabetically, which answers prefixes, ranges, and "the nearest word at or before this one".

## Why an FST alone is not the answer

An FST maps a word to one 64-bit number. A real dictionary entry is more than that: counts, offsets, a few varying bytes. Store a row number and keep the records elsewhere, and you have built a second table anyway. And reading every word in order through the FST means walking its graph, which on an Intel i9 takes about 58 nanoseconds a word.

## A table of contents

termdict cuts the sorted word list into **blocks** of 32 to 64 words, each stored compactly with its records right next to it. Then it builds a small FST over just the **first word of each block**, with the block's position as its value. That FST is the table of contents.

```d2 alt="An FST of each block's first word sends a lookup for apply to the block that starts at amen, and only a few words of that block are read."
direction: down

index: "Look up apply in the FST of first words" {style.bold: true}
blocks: "Blocks of 32 to 64 sorted words" {
  direction: right
  b1: "aardvark ..."
  b2: "amen ..."
  b3: "april ..."
}
run: "Read a few words of that block"

index -> blocks.b2: "block starting at amen"
blocks.b2 -> run
```

A lookup asks the FST for the last block whose first word is at or before the target, then reads at most 32 words of that block. Inside a block, shared beginnings are skipped and letters are packed tight: words that use only 27 different characters spend 5 bits per letter instead of 8. For all 235,976 words of the standard macOS word list, the table of contents is **52 KB**. For a Wikipedia vocabulary of almost 4 million words, it is 709 KB in front of 39 MB of blocks.

Walking the words in order now means reading blocks front to back, which on the same i9 takes about **16 nanoseconds** a word, under a third of the FST's walk.

## The numbers

Here are size and lookup time on the macOS word list, on an Apple M4 Pro. The FST takes a twelfth of a hash map's space and looks up almost nine times slower; termdict adds its records on top:

| Structure | Bytes per word | Lookup (ns) |
| --- | ---: | ---: |
| Abseil hash map | 73.32 | 18 |
| `std::map` (a sorted tree) | 64.00 | 422 |
| marisa-trie (a compact trie) | 3.15 | 331 |
| fst | 6.20 | 152 |
| termdict, 6-byte records included | 11.04 | 239 |

The honest reading: if all you ever do is look up exact words, use a hash map, and termdict is the slowest thing in its own [comparison](https://github.com/Kronuz/termdict/blob/main/docs/perf/lookup.md). What it buys is order, records, and a dictionary that opens from a file. The methods and an Intel i9 column are in the [fst notes](https://github.com/Kronuz/fst/blob/main/docs/perf/comparators.md); both benchmarks check that every structure gives the same answer for every word before timing anything.

## The gnarly bit: bytes you did not write

Reading in place has a catch. The reader follows positions stored inside the file, and if the file is damaged, or crafted by someone hostile, a position can point anywhere. Worse, two positions can point at each other, and a lookup would walk in circles forever.

So opening an FST checks every node once. Each jump must land exactly on the start of an earlier node, and since every jump goes backward, the graph cannot contain a loop. A `trusted` option skips this for bytes already verified by a checksum, because the check is not free: it is nearly all of the 5.8 milliseconds it takes to open the Wikipedia dictionary. termdict then checks every length inside a block as it reads it.

The tests try every truncation and every single-bit flip of whole indexes, plus fuzzing: 13.6 million random inputs over 35 minutes, nothing found. A script also breaks fst in 21 deliberate ways and demands a failing test for each. It also shows why one odd test exists: it gives every branch the same fingerprint, forcing a byte-by-byte comparison each time, and without it 10 of the 11 breaks in that comparison get past the others.

## Where it fits

Reach for this pair when you have a large, sorted, mostly read set of words or keys that needs order, prefixes, or merging, and you want to open it straight from a file. Use fst alone when a number per key is enough. Skip both when the set changes all the time (they are built once and rebuilt, never edited) or when exact lookups are the only question you will ever ask.
