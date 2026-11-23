---
title: "Store, Then Search"
subtitle: "One segment lifecycle, two very different jobs."
description: "strata owns immutable segments, manifests, commits and merges; prospect supplies the inverted search layout, scoring and queries. They share an index without making the storage core know what a search term is."
excerpt: "A storage engine needs to know when a segment is durable and when it can be removed. A search engine needs to know which documents contain a term and which of them should rank first. I split those jobs between strata and prospect, and made the boundary a segment layout."
date: 2026-11-22
authors: kronuz
series: "Familiars"
seriesOrder: 38
chapter: "Bytes"
tags: [familiars, cpp, storage, search]
---

*Part of [**Familiars**](https://kronuz.github.io/cpp-libraries/), my collection of standalone C++ building blocks. This pair is [strata](https://github.com/Kronuz/strata) and [prospect](https://github.com/Kronuz/prospect).*

A search index has two kinds of work that happen to live in the same files. One kind decides when bytes become durable, which readers can still see an old segment, and when it is safe to reclaim a file. The other turns a query into terms, postings, scores, and a ranked list of documents. The first set of rules matters to any persistent index. The second is specific to search.

I had already watched those concerns grow together inside [Xapiand](https://github.com/Kronuz/Xapiand), where [Xapian](https://xapian.org/) supplies the index underneath. The new pair is meant to replace that part of Xapiand and serve its successor, Elysian. That provenance explains the compatibility work, but neither library depends on the rest of the engine. `strata` is an embeddable segment store; `prospect` is a search layout built on it.

## A boundary in the file

`strata` accepts batches, assigns document IDs, flushes immutable segments, merges them in the background, and publishes snapshots. A layout names the plugins that fill a segment. Its document layout needs only keys and stored records, which makes a key-value store. The core does not have a search term type or a BM25 score tucked into it. [The architecture](https://github.com/Kronuz/strata/blob/main/docs/ARCHITECTURE.md) puts those sections in `prospect`'s ownership.

`prospect` supplies the inverted layout: a term dictionary, postings, positions, lengths, document values, and the machinery that reads them. It can change how those sections compress or how a scorer traverses them without inventing another commit protocol. One segment still has a table of contents and a versioned, checksummed footer. The same manifest records which segments form a committed index.

```d2 alt="An application chooses either a document layout with keys and stored records or prospect's search layout with postings; both use strata for segments, manifests, and merges."
direction: down
app: Application
document: "Document layout\nkeys + stored records"
search: "prospect layout\nterms + postings\nBM25 scoring"
core: "strata core\nsegments\nmanifests + merges" { style.bold: true }
app -> document
app -> search
document -> core
search -> core
```

This boundary matters most during a merge. Merging is not merely concatenating files: live documents may move to new segment ordinals, postings need encoding again, and readers holding an older snapshot must still see its files. `strata` owns the file lifecycle and the ordinal map. `prospect` owns the meaning of its search sections and can reorder documents to improve compression and pruning. A storage concern stays in one place, and a search concern gets a hook where the bytes are written.

## The moment a commit is real

There is a tempting shortcut in a segment store: finish writing a new file, rename a manifest into place, and call the commit done. A power cut can make that manifest survive without the segment it names if the relevant sync and directory ordering are missing.

The commit sequence in `strata` syncs segment data and live-document state, writes and syncs the manifest, then syncs the directory. Recovery checks the manifest and the files it names; it fails on corruption instead of quietly opening an older view. Snapshots, manifests in use, and journal checkpoints also hold references that prevent premature reclamation. These rules are shared whether the segment contains only keys or a full inverted index.

The [lifecycle gate](https://github.com/Kronuz/strata/blob/main/docs/gates/phase-3-lifecycle.md) exercised 10,000 crash points across 31 seeded workloads with zero lost commits or inconsistent opens. In a separate reclamation sweep it checked 16,274 manifests over 3,635 cut points. When the directory barrier was deliberately removed, 93 manifests named missing files. [faultlab](/blog/faultlab-crash-states/) supplies the model and replayable cuts. That last number is useful because it shows the test can detect the failure the barrier is there to prevent. It is evidence for this modeled IO contract, not a promise about every real filesystem.

## Search without a second engine

Once a snapshot exists, `prospect` can read immutable segments while writes continue. Its term dictionary points to compressed postings blocks. A query resolves terms, requests the ranges it needs, and walks document IDs in windows. BM25 supplies scores; block maxima let a top-k query skip work that cannot beat its current threshold. Phrase queries also need positions. Aggregations and exact totals can turn pruning off when they need to see every matching document. [The read path](https://github.com/Kronuz/prospect/blob/main/docs/ARCHITECTURE.md) spells out where each decision is made.

The query coroutine runs on the caller's reactor. It can suspend for residency and yield between windows instead of parking a reactor thread behind disk access or a long scorer loop. This is an integration choice as much as an algorithm choice: the host remains responsible for scheduling, while the search code has explicit places to give time back.

The result is not yet a production replacement for Xapian. `strata`'s API and on-disk format are still changing. `prospect`'s [status](https://github.com/Kronuz/prospect/blob/main/docs/STATUS.md) records query performance rows that have not met their target, even as later format work proceeds. In a [format gate](https://github.com/Kronuz/prospect/blob/main/docs/perf/format13-gate-vm.md), 1,162 query lines produced no result mismatches, but some speed and size comparisons still lost. Correct results are necessary; they do not make the performance case by themselves.

For now the pair is most useful as an explicit way to build and test an index: one durable segment lifecycle, with a search layout that can evolve independently. That is the seam I wanted to keep.
