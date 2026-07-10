---
title: "A Search Engine from Scratch"
subtitle: "A distributed search engine in C++, built on Xapian."
description: "A tour of Xapiand's real internals: a libev async core, Raft for cluster and shard-primary election, a Haystack-style LZ4 log store, and HTM geospatial indexing. With links to the actual code."
excerpt: "Dubalu needed search, so I wrote one in C++. Xapiand is not a new inverted index, it is the distributed, RESTful, storage-backed daemon I wrapped around Xapian: Raft consensus, a log-structured store, and a triangular mesh for the whole planet. Here is how it really fits together."
date: 2026-06-08
draft: true
series: "Opening Boxes"
seriesOrder: 5
tags:
  - opening-boxes
  - distributed-systems
  - cpp
---

*Part of the **Opening Boxes** series, technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This one opens [Xapiand](https://github.com/Kronuz/Xapiand).*

At [Dubalu](/blog/the-boy-who-kept-opening-the-box/), my company, we needed search. Not "grep over a column" search, real search: full-text relevance, faceting, geo queries, across a cluster, fast. The honest move would have been to run Elasticsearch and get on with the product.

I did not do the honest move. I wrote my own, in C++, and called it **[Xapiand](https://github.com/Kronuz/Xapiand)**.

I want to be precise about what that means, because "wrote my own search engine" usually invites an eye-roll, and it should. I did **not** reimplement the hard, beautiful core, the inverted index, the relevance scoring, the query parser. That part is [**Xapian**](https://xapian.org), a mature C++ search library I deeply respect. The name is the joke and the thesis at once: *Xapian* plus *d*, for daemon. Xapiand is everything you have to build *around* a good index to make it a **distributed, highly available, RESTful search and storage server**: the network layer, the cluster, the replication, the storage, the geometry. That is the box this post opens.

## The shape of it

```d2 alt="Xapiand's layered architecture: clients talk REST or a binary protocol, into a Xapian-backed query/index core, with a log-structured store, a Raft-based cluster layer, all on a libev async core"
direction: down
clients: "Clients"
rest: "HTTP / REST\n(JSON, MessagePack)"
binary: "Binary remote +\nreplication protocol"
core: "Query + index core\n(built on Xapian)" { style.bold: true }
store: "Document store\n(log-structured, LZ4)"
geo: "Geo index (HTM)"
cluster: "Cluster layer: Raft\n(discovery, sharding)" { style.bold: true }
ev: "Async core (libev)"
clients -> rest
clients -> binary
rest -> core
binary -> core
core -> store
core -> geo
core -> cluster
cluster -> ev
core -> ev
```

Everything sits on a single-threaded-per-loop **libev** event core (the same family of event loop that backs nginx and Node), with thread pools behind it. Nothing in the hot path blocks. Let me take the three pieces I am proudest of.

## Clustering: Raft, twice

A distributed search engine has to answer two questions constantly: *who is in charge of the cluster?* and *who owns this particular shard right now?* Both are consensus problems, and rather than invent a protocol (the classic way to introduce a subtle, unfixable bug), I implemented **Raft**.

The whole state machine is in [`src/server/discovery.h`](https://github.com/Kronuz/Xapiand/blob/master/src/server/discovery.h), and it is textbook Raft, in the good sense:

```cpp
enum class Role {
    RAFT_FOLLOWER,
    RAFT_CANDIDATE,
    RAFT_LEADER,
};

enum class Message {
    RAFT_HEARTBEAT,            // same as APPEND_ENTRIES, empty
    RAFT_APPEND_ENTRIES,       // leader replicating its log
    RAFT_REQUEST_VOTE,         // candidate gathering votes
    RAFT_REQUEST_VOTE_RESPONSE,
    RAFT_ADD_COMMAND,          // tell the leader to append to the log
    ELECT_PRIMARY,             // promote a primary shard
    // ...
};
```

```d2 alt="Raft state machine: follower times out to candidate, wins a majority to become leader, leader sends heartbeats and can call ELECT_PRIMARY to promote a primary shard"
direction: down
f: "Follower"
c: "Candidate"
l: "Leader"
s: "Primary shard"
f -> c: "election timeout"
c -> l: "majority of votes\n(RequestVote)"
c -> f: "sees higher term"
l -> f: "AppendEntries /\nheartbeat"
l -> s: "ELECT_PRIMARY"
```

Two `libev` timers drive it: `raft_leader_election_timeout` (a follower that stops hearing from a leader becomes a candidate) and `raft_leader_heartbeat` (the leader keeps everyone calm). The detail I like is the last message in that enum: `ELECT_PRIMARY`. The same machinery that elects the cluster leader is reused, at a finer grain, to elect the **primary copy of an individual shard**. Consensus is not just a one-time "who's boss"; it is how every shard decides who currently takes its writes. Dynamic sharding falls out of running Raft at two levels.

## Storage: a small Haystack

Search gives you back document IDs. Something still has to hold the *documents*, durably, and hand them back by the million without thrashing the disk. For that I wrote a log-structured store, in [`src/storage.h`](https://github.com/Kronuz/Xapiand/blob/master/src/storage.h), modeled on the ideas in Facebook's **Haystack** paper: append, do not seek; pack many small objects into large block-aligned volumes; compress.

The on-disk format is deliberately boring, which is what you want from a format that holds your data:

```cpp
#define STORAGE_MAGIC             0x02DEBC47
#define STORAGE_BIN_HEADER_MAGIC  0x2A   // '*' starts every stored object
#define STORAGE_BIN_FOOTER_MAGIC  0x42   // 'B' ends it

#define STORAGE_MIN_COMPRESS_SIZE 100
constexpr int STORAGE_FLAG_COMPRESSED = 0x01;
constexpr int STORAGE_FLAG_DELETED    = 0x02;  // tombstone
```

A volume opens with a block-padded `StorageHeader` carrying `STORAGE_MAGIC`. Each object ("bin") is wrapped in a header/footer pair with their own magic bytes so corruption is caught at read time, compressed with **LZ4** when it is larger than 100 bytes (small things are not worth the CPU), and deletes are **tombstones**, a flag flip, not a seek-and-rewrite. Writes stay sequential; the engine appends and moves on.

## Geometry: a triangular mesh for the planet

"Find me documents within 5 km of here" is not a text query, and you cannot answer it well by scanning. The standard trick is to turn the surface of the Earth into a hierarchy of cells, encode each cell as a number, and let the *text* index do the work on those numbers. Xapiand uses the **Hierarchical Triangular Mesh (HTM)**: start with an octahedron projected onto the sphere, then recursively split each spherical triangle into four. Every point on Earth becomes a path down that tree, a 64-bit trixel ID, and a region becomes a set of trixel ranges you can feed straight into Xapian as terms.

That lives in [`src/geospatial/htm.h`](https://github.com/Kronuz/Xapiand/blob/master/src/geospatial/htm.h) and `cartesian.h` (lat/long to unit-sphere Cartesian and back). It is the piece that let a *text* search engine answer real geo queries, polygons, circles, EWKT geometries, without a separate spatial database bolted on the side.

## What it cost, and what it was for

I will not pretend this was free. Building your own distributed datastore is a decision you pay for in nights. But Xapiand was not a toy: it was **Dubalu's core data infrastructure** for years, the thing our product actually ran on. It is MIT-licensed, around 360 stars on GitHub, and I was still pushing commits to it in 2025, long after Dubalu, because some boxes you never fully close.

There is a straight line from here to the rest of my career. The instinct that built Xapiand, *I want to understand the whole stack, down to the bytes on disk and the votes on the wire*, is the same one that, a few years later, had me elbow-deep in CPython's dictionary internals making imports lazy. If you want that story, it is in [the longer one](/blog/the-boy-who-kept-opening-the-box/). Xapiand is where I learned, for real, how much "make it distributed" actually asks of you.

Xapiand also turned out to be a quarry. Years after Dubalu I went back and cut its sharpest pieces out into standalone libraries, each a small creature that can stand on its own: a [lock-free timer wheel](/blog/the-sparse-wheel/), a [crash tracer that photographs every thread's stack at once](/blog/the-haunted-handler/), the HTM mesh, the cluster bus, a [fantasy-name generator for the node names](/blog/rolling-for-a-name/), thirty-odd of them. I am opening them one at a time in a series of their own, **Familiars**. If this post was the dungeon, that series is the loot.

---

*Everything above is from the real source: [github.com/Kronuz/Xapiand](https://github.com/Kronuz/Xapiand), specifically [`server/discovery.h`](https://github.com/Kronuz/Xapiand/blob/master/src/server/discovery.h) (Raft), [`storage.h`](https://github.com/Kronuz/Xapiand/blob/master/src/storage.h) (the store), and [`geospatial/htm.h`](https://github.com/Kronuz/Xapiand/blob/master/src/geospatial/htm.h) (the mesh). Copyright Dubalu LLC, 2015-2019.*
