---
title: "Asking the Machine"
subtitle: "Reading a host's own limits, on systems that each hide the answer somewhere different."
description: "system is Xapiand's process- and machine-level resource introspection: open and maximum file descriptors against the rlimit, total and per-process RAM and virtual memory, disk and inode capacity, and compiler, OS, and architecture identification strings. It is a small library whose entire difficulty is portability, because every operating system keeps these numbers somewhere different (proc files on Linux, sysctl on the BSDs and macOS, task info on Apple), and a server that wants to know how close it is to running out of descriptors or memory has to ask each of them in its own dialect."
excerpt: "A long-running server should know its own limits: how many file descriptors it is burning against the cap, how much RAM the process holds, how much disk is left before writes start failing. None of those numbers has a portable source. The nineteenth familiar is the small, unglamorous library that asks each operating system for them in its own dialect, so the rest of the engine can just ask once."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 19
chapter: "Forbidden Layer"
tags:
  - familiars
  - cpp
  - portability
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one asks the host about itself: [system](https://github.com/Kronuz/system).*

A server that runs for months needs a kind of self-awareness that a short program never does. It has to know how close it is to the walls. How many file descriptors am I holding against my limit, so I can refuse a connection before `accept` starts failing? How much resident memory is the process using right now? How much disk and how many inodes are left before a write turns into an error I cannot recover from gracefully? These are not exotic questions. They are the difference between a service that degrades politely under pressure and one that falls over.

[system](https://github.com/Kronuz/system) is the small library that answers them: open and maximum file descriptors versus the rlimit, total RAM and current per-process usage, total and free disk and inodes, and human-readable compiler, OS, and architecture strings for logs and diagnostics. The API is boring on purpose, `get_total_ram()`, `get_open_files_per_proc()`, `get_free_disk_size()`, and boring is exactly what you want from the code that tells you whether you are about to hit a wall.

## The whole difficulty is portability

There is no interesting algorithm here. The entire challenge is that **not one of these numbers has a portable source.** Linux keeps them in the `/proc` filesystem, as text files you parse. macOS and the BSDs keep them behind `sysctl`, a typed key-value interface you query with numeric MIB arrays. Apple has its own `task_info` and `host_statistics` for process and machine memory. The rlimit is `getrlimit`, mostly, but what counts as "open files system-wide" differs again. So a function as innocent as "how much RAM does this machine have" is three or four completely different implementations wearing one name, selected at compile time, and the library's job is to keep that mess on the inside so callers see a single honest number.

That is the same shape as [io](/blog/io/), its neighbor in this chapter: a thin, dependency-free layer whose value is entirely in absorbing the ways operating systems disagree. And like io, it is where the portability paper-cuts land. This is the very library whose `memory_stats.cc` once broke a FreeBSD build for a reason that had nothing to do with memory: it used `std::pair` without including `<utility>`, and got away with it on Linux and macOS only because their standard headers happened to pull `<utility>` in transitively. FreeBSD's libc++ trims those transitive includes, so the missing header surfaced there and nowhere else, and the fix was one unconditional `#include` that the other two platforms never needed. That is the texture of portable systems code in one line: the bug is not in the logic, it is in an assumption three platforms let you make and the fourth does not.

## Where it fits

Reach for it when a long-lived process needs to watch its own resource headroom, back-pressure on descriptor or memory limits, log the build and host it is running on, or expose capacity in a metrics endpoint. Skip it if you are on a single platform and happy to read `/proc` (or call `sysctl`) directly, or if your runtime already surfaces these numbers for you.

The next familiar leaves the machine for the planet it might be sitting on. It turns a latitude and a longitude into a vector you can do real geometry on, across an Earth that is stubbornly not a sphere.
