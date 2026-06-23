---
title: Xapiand
tagline: Search and Storage Engine
description: A fast, simple, and modern search and storage engine, written in C++.
tech: [C++]
repo: https://github.com/Kronuz/Xapiand
website: https://Kronuz.github.io/Xapiand
docs: https://Kronuz.github.io/Xapiand/docs
status: shipped
featured: true
order: 1
related:
  - a-search-engine-from-scratch
---

Xapiand is a fast, simple, and modern search and storage engine, built from scratch in
modern C++. It started as the data layer behind a product at Dubalu and grew into a
distributed engine of its own: a RESTful API over a schemaless document store, full-text
search, geospatial and range queries, and replication across a cluster.

The interesting parts live below the API. Storage is an append-only log with a B-tree
index; search is built on a compact inverted index; and the cluster coordinates with a
Raft-based protocol so nodes can come and go without losing data. The goal throughout was
to keep the moving pieces few and the defaults sane, so a single binary does something
useful out of the box and still scales out when you need it to.
