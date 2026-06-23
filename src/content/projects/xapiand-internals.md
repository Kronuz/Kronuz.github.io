---
title: Xapiand Internals
tagline: Storage, search, and the cluster
description: How Xapiand stores documents, builds its search index, and coordinates a cluster.
tech: [C++]
repo: https://github.com/Kronuz/Xapiand
docs: https://Kronuz.github.io/Xapiand/docs
status: active
series: Xapiand
seriesOrder: 2
---

The interesting parts live below the API. Storage is an append-only log with a B-tree
index, so writes are sequential and durable and reads stay fast. Search is built on a
compact inverted index, the same shape that powers full-text engines, kept lean so it fits
comfortably in memory.

The cluster coordinates with a Raft-based protocol: a leader sequences writes, followers
replicate them, and the group keeps making progress as long as a majority is up, so nodes
can come and go without losing data. Few moving pieces, sane defaults, and a single binary
that scales from a laptop to a cluster.
