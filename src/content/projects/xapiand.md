---
title: Xapiand
tagline: Search and Storage Engine
description: A modern, distributed RESTful search and storage engine, written from scratch in C++.
tech: [C++]
logo: /img/projects/xapiand.png
repo: https://github.com/Kronuz/Xapiand
website: https://Kronuz.github.io/Xapiand
docs: https://Kronuz.github.io/Xapiand/docs
status: shipped
featured: true
order: 1
related:
  - a-search-engine-from-scratch
---

Xapiand started as the data layer behind a product at Dubalu, the startup where I was CTO,
and grew into a distributed search and storage engine of its own. It speaks a RESTful API
over a schemaless document store: you throw JSON (or MessagePack) at it, and it indexes
everything for full-text search, geospatial and range queries, and exact retrieval. A
single binary does something useful out of the box and still scales out across a cluster
when you need it to.

The interesting parts live below the API. Search is built on top of Xapian's inverted
index. Per-index storage is an append-only design modeled on Facebook's Haystack, so the
small-file problem that bites most document stores never shows up. The whole thing is
event-driven and asynchronous on `libev`, geospatial queries run over a Hierarchical
Triangular Mesh on WGS84 coordinates, and the cluster replicates asynchronously so you can
read or search against any replica and let it reroute automatically when a node comes or
goes.

This was the big one for me. Set the few hundred stars aside; the real measure is the
codebase: well over 200,000 lines of modern C++ across more than 800 source and header
files of my own, the custom storage, the clustering, the geospatial math, the query layer,
written lovingly and stubbornly, mostly by hand. It never had SublimeCodeIntel's user numbers, and it didn't need
to. It was the largest thing I'd built, and building it taught me more than any single
project before or since. I've told the longer version of how it came together (and why
building a search engine from scratch is both a terrible idea and one of the most
instructive things I've ever done) in [a separate write-up](/blog/a-search-engine-from-scratch/).
