---
title: "Smith and Schmidt"
subtitle: "Matching names by how they sound, across spellings that share no letters."
description: "double-metaphone is a standalone C++20 implementation of Lawrence Philips' Double Metaphone phonetic encoder, the 2000 successor to Soundex. It reads a word the way it is pronounced, understanding silent letters and non-English spellings, and emits two phonetic keys per word: a primary key for the dominant English reading and an alternate for a plausible foreign one. Two keys are what let Smith (SM0/XMT) and Schmidt (XMT/SMT) collapse onto a shared key, XMT, a pair Soundex never catches. It is the phonetic backbone for matching names and words by sound rather than spelling."
excerpt: "Smith and Schmidt are the same name, and they share not one meaningful letter. Any system that matches on spelling will never connect them, which is a problem if you are searching for people, whose names arrive spelled every possible way. The twenty-first familiar reads a word the way it is said, not written, and emits two keys so that a name and its foreign cousin finally meet."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 21
chapter: "Space"
tags:
  - familiars
  - cpp
  - text
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one matches by sound: [double-metaphone](https://github.com/Kronuz/double-metaphone).*

`Smith` and `Schmidt` are the same name. They share not a single meaningful letter. If you index people by the spelling of their names, as any literal text index does, those two will never find each other, and neither will `Catherine` and `Kathryn`, or `Jon` and `John`. That is fine until the thing you are searching *is* names, at which point it is a disaster, because names are the most spelling-unstable words there are: transliterated, anglicized, typo'd, and written a dozen ways for one sound. The fix is to stop matching letters and start matching **sound**.

[double-metaphone](https://github.com/Kronuz/double-metaphone) is that: a standalone C++20 implementation of Lawrence Philips' Double Metaphone, the 2000 successor to Soundex. Where Soundex looks only at the surface letters (keep the first, map the rest to a few digit classes, and hope), Double Metaphone reads a word the way it is *pronounced*. It knows about silent letters, the many ways English writes one sound, and common non-English spellings, so it turns a word into a short key from a tiny sound alphabet, `A B F H J K L M N P R S T W X` plus `0` for the "th" sound, where words that sound alike land on the same key even when their spellings have nothing in common.

## Why two keys

The name is "Double" for the sharpest idea in it: it emits **two** keys per word, not one.

- The **primary** key captures the dominant English pronunciation.
- The **alternate** key captures a plausible *foreign* reading, often Slavic, Germanic, or Romance. When a word has only one likely pronunciation, the alternate just equals the primary.

That second key is exactly what catches names that crossed a language on their way to you. `Smith` encodes as `SM0` / `XMT`; `Schmidt` encodes as `XMT` / `SMT`. Their primaries differ, but they **meet on `XMT`**, because Double Metaphone knows that the German `Sch` and the English `Sm` can both reach that sound. A single-key scheme like Soundex has no room to represent "this could be pronounced two ways," so it simply never connects the pair. Two keys give a word a chance to match through either of its plausible pronunciations, and that is the whole reason it works on real, messy, multilingual name data where Soundex quietly fails.

## Where it fits

Reach for it whenever you match human names or words by how they sound: people search, deduplicating records that were typed by different hands, fuzzy lookups that should survive transliteration. Index a word under its metaphone keys and a query encodes the same way, so `Schmidt` finds `Smith` for free. Skip it for non-name text where spelling is stable and semantic similarity, not phonetic, is what you want; a phonetic key will happily collide words that merely rhyme.

The next familiar zooms out from one comparison to a whole toolbox of them. Sounding alike is only one way two strings can be close, and there is no single right answer to how close, so it offers a family of them behind one interface.
