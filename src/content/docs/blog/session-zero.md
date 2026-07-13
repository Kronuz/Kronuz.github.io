---
title: "Session Zero"
subtitle: "Sixty small libraries, one search engine, and the campaign to open them."
description: "An introduction to Familiars, a series of standalone C++ libraries carved out of Xapiand, a distributed search engine I built. Each post opens one library on its own terms: what it does that nothing else does, the constraint that forced its shape, the gnarly bit it ships with, and where it is the right tool. This is the setup: the world, the party, and the rules of the campaign."
excerpt: "I spent years building a distributed search engine, and when I finally stepped back from it I did not keep the engine. I kept the tools. Sixty-odd small, sharp libraries fell out of Xapiand, each one a self-contained idea worth knowing on its own. This is the campaign to open them, one familiar at a time."
date: 2026-07-10
draft: true
featured: true
series: "Familiars"
seriesOrder: 0
chapter: "Prologue"
tags:
  - familiars
  - cpp
---

*This is the opening of **Familiars**, a series of self-contained C++ libraries I pulled out of [Xapiand](https://github.com/Kronuz/Xapiand). [A Search Engine from Scratch](/blog/a-search-engine-from-scratch/) tells the story of the engine itself; this series opens the small creatures I found living inside it.*

I spent the better part of a decade building a distributed search engine. [Xapiand](https://github.com/Kronuz/Xapiand) wraps a daemon around [Xapian](https://xapian.org): the cluster, the replication, the storage, the geometry, the network, everything you have to build *around* a good index to make it a real server. That story is [its own post](/blog/a-search-engine-from-scratch/). This is not that story.

When I finally stepped back from the engine, I did not keep the engine. I kept the **tools**. Over the years, whenever a piece of Xapiand grew sharp enough and self-contained enough to live on its own, I carved it out into its own repository, gave it a real README and a test suite, and let it stand up by itself. There are about sixty of them now, scattered across [github.com/Kronuz](https://github.com/Kronuz): a lock-free timer, a signal-safe crash tracer, a fantasy-name generator, a triangular mesh for the whole planet, a big-integer type that does its arithmetic before the program runs. Small things. Sharp things.

This series opens them, one at a time.

## What a familiar is

In a game, a familiar is a small companion bound to something larger: not the hero, but the creature at the hero's shoulder that does one strange thing unreasonably well. That is exactly what these libraries are. Each is a single idea, extracted from a system big enough to have needed it in anger, and each earns a post the same way:

- **The one thing it does that nothing else does.** Not "a queue," but *the* property that made me reach for this instead of the obvious thing.
- **The constraint that forced its shape.** Every one of them exists because two normal answers failed, and the failure is the interesting part.
- **The gnarly bit.** The bug, the trap, the oozing thing sewn into the lining. A footgun in a data table. A `malloc` hiding inside a function that looked safe. The same register spelled nine different ways across three operating systems. This is where the learning is, so it stays in.
- **Where it is actually the right tool**, and, just as often, where it is not.

You can read any one of these on its own. None of them needs the search engine, or the one before it, to make sense. They are a party, not a plot.

## The map

The campaign runs through the engine in loose chapters, each a cluster of related familiars:

- **Little languages.** Small compilers and grammars: the [name generator](/blog/rolling-for-a-name/) that names every node, a boolean-expression parser, a perfect hash built entirely at compile time.
- **The forbidden layer.** The libraries that live where the normal rules stop applying: the [crash tracer](/blog/the-haunted-handler/) that runs inside a signal handler, the EINTR-safe POSIX layer, the machine-introspection code that has to be portable across every OS the server runs on.
- **The lock-free jewels.** The concurrency crown of the codebase: the [timer store](/blog/the-sparse-wheel/) whose insert never stalls another thread, the deferred logger built on it, an atomic `shared_ptr`, a bounded blocking deque.
- **The network path.** One request's whole journey: the thread-per-core reactor, the HTTP framework, the streaming parser, the router that matches a URL to a handler without ever walking the whole tree.
- **Bytes and persistence.** How data survives a crash and a wire: a crash-safe append-only store, three interchangeable compression codecs, a MessagePack value type, a condensed sortable UUID.
- **Space and sound.** Domain algorithms: the Hierarchical Triangular Mesh that turns the planet into terms, geodetic coordinate math, phonetic matching, string similarity.
- **Compile-time magic.** The things that run before `main` does: arbitrary-precision integers, compile-time hashing and character classification, reflective enums.
- **The bag of holding.** And a heap of tiny, honest helpers too small for a post of their own, tipped out onto the table together at the end.

## The rules of this table

A few, and they are the same as the rest of this blog:

- **Real numbers.** When a familiar is fast, or small, or exact, the measurement says so, not an adjective. When it is a wash, I say that too.
- **The messy parts stay in.** The bug I shipped, the design that failed first, the thing I only caught by staring at it too long. Those are the point.
- **Everything is real and open.** Every familiar is a public repository you can clone, read, and use. Most are MIT or public domain. The code in each post is the code that runs.

The party is [already assembled](https://github.com/Kronuz). Three of them are on the table: a [jester who names the world](/blog/rolling-for-a-name/), a [tracer that works in a haunted room](/blog/the-haunted-handler/), and the [strange lock-free thing](/blog/the-sparse-wheel/) I would keep over all the others. The rest are waiting.

Roll for initiative.
