---
title: "Many Ways to Be Similar"
subtitle: "A family of string-distance metrics behind one interface, because there is no single answer to 'how close.'"
description: "string-similarity is a header-only C++20 suite of string metrics: Levenshtein edit distance, Jaro and Jaro-Winkler, longest common substring and subsequence, Jaccard, Sørensen-Dice, and a Soundex-backed wrapper. They share one CRTP base, StringMetric<Impl>, so every metric exposes the same surface: a distance() and a similarity() in [0,1], a name(), and a description(). You pass both strings, or bind one and compare many against it. The point is that 'how similar are two strings' has many right answers depending on whether you care about edits, prefixes, shared tokens, or sound, and the uniform interface lets you pick and swap between them freely."
excerpt: "There is no such thing as the string-similarity metric. A typo wants edit distance; a name wants prefix weighting; a set of tags wants token overlap; a misspelling wants sound. The twenty-second familiar admits this and ships a whole family, edit distance, Jaro-Winkler, Jaccard, Dice, and more, all behind one interface, so choosing the right notion of close is a matter of picking a class."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 22
tags:
  - familiars
  - cpp
  - text
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one measures closeness a dozen ways: [string-similarity](https://github.com/Kronuz/string-similarity).*

Ask "how similar are these two strings" and the honest first response is a question back: similar *how*? `color` and `colour` differ by one inserted letter, so they are close under **edit distance**. `Jon` and `Jonathan` share a prefix, which **Jaro-Winkler** rewards and edit distance does not. `{red, blue, green}` and `{green, blue, yellow}` are two sets that overlap, which **Jaccard** and **Sørensen-Dice** measure and character metrics cannot see. And `Smith` and `Schmidt` are close only if you listen, which needs [sound](/blog/double-metaphone/). There is no single "string similarity," only a shelf of metrics, each one right for a different shape of data, and the mistake is picking one and using it for everything.

[string-similarity](https://github.com/Kronuz/string-similarity) is that shelf, made uniform. It is a header-only suite, Levenshtein edit distance, Jaro and Jaro-Winkler, longest common substring and subsequence, Jaccard, Sørensen-Dice, and a Soundex-backed wrapper, and its design move is to put every one of them behind the **same interface** so they are interchangeable.

## One shape, many metrics

The base is a CRTP template, `StringMetric<Impl>`, and every metric is a subclass that fills in one calculation. They all present the same surface: a `distance()`, a `similarity()` normalized to `[0, 1]`, and a `name()` and `description()` so a metric can introduce itself. You use any of them two ways, and the second is the one that matters in practice:

```cpp
Levenshtein lev;
lev.similarity("kitten", "sitting");   // compare two strings ad hoc

Levenshtein fixed("kitten");            // bind one side once
fixed.similarity("sitting");            // compare many others against it
```

Binding one string and comparing a stream of candidates against it is the real workload, fuzzy-matching a query against a column, deduplicating a list, ranking suggestions, and the uniform surface means the *choice* of metric is a one-line swap, not a rewrite. This is the same philosophy as [compressors](/blog/compressors/) a chapter ago: when a problem has several legitimate answers with different tradeoffs, the library's job is not to pick for you, it is to make switching between them cost nothing, so you can choose per use and change your mind cheaply. Edit distance for typos, Jaro-Winkler for names, Jaccard for tag sets, all the same shape.

## Where it fits

Reach for it whenever "close but not equal" is a real requirement: typo-tolerant search, record linkage, autocomplete ranking, near-duplicate detection. Pick the metric that matches your data's notion of similarity, character edits, shared prefixes, token overlap, or sound, and swap freely as you learn what works. Skip it if exact matching is enough, or if you need semantic similarity (meaning, not surface form), which is an embeddings problem, not a string-distance one.

The next familiar goes back to the lock-free chapter with a quieter kind of cleverness: a shared pointer you can swap atomically, written so that it politely deletes itself the day the standard library grows its own.
