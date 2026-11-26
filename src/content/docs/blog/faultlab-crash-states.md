---
title: "When Power Leaves"
subtitle: "A reproducible crash is a better test than a lucky one."
description: "faultlab models the durable IO contract, records real calls, and replays a chosen crash state so storage recovery can be tested at the exact cut that broke it."
excerpt: "A storage test that kills a process once tells you almost nothing about the state the disk might leave. faultlab cuts after each operation, chooses which unsynced bytes and names survive, and gives each failure a replayable seed."
date: 2026-11-22
authors: kronuz
series: "Familiars"
seriesOrder: 39
chapter: "Trust"
tags: [familiars, cpp, testing, storage]
---

*Part of [**Familiars**](https://kronuz.com/cpp-libraries/), my collection of standalone C++ building blocks. This one is [faultlab](https://github.com/Kronuz/faultlab).*

The most reassuring storage test is also one of the weakest: write a record, kill the process, reopen the database, and find the record still there. A process exit usually leaves the operating system and its caches alive. Even a real power cut gives you just one outcome from a large set. The state that breaks recovery might require the new manifest to survive while one of its files does not, or a name to persist while half an unsynced append does not.

I wanted to make those outcomes test inputs. `faultlab` puts an in-memory filesystem behind [completion](https://github.com/Kronuz/completion)'s `journal::IO` interface. A program runs its ordinary IO through that seam. A test can snapshot the model after a call, cut power at that point, choose a seed, and ask whether recovery accepts exactly the states it promised to accept. When a seed fails, the same seed takes you back to the same state.

## What survives?

The model keeps current bytes separate from durable bytes. A write changes the current view. A file sync makes its bytes durable. A directory sync settles names and the ordering they require. Until then, a crash may keep or lose unsynced changes according to the [crash model](https://github.com/Kronuz/faultlab/blob/main/docs/mechanisms/crash-model.md).

`crash(seed, policy)` makes the choices in a fixed order. An ordering point decides which earlier epochs survive as a whole. Namespace operations replay in order; an unsynced create, link, rename, or unlink can survive or disappear, with rename atomic. Then a file's size and its 512-byte sectors choose old or new data. An append may have its new size but zeroes where some new data did not survive. The point is to admit awkward states, not just the tidy old-file-or-new-file pair a test author thought to write down.

```text
 real operation ──▶ journal::IO ──▶ storage code
                         │
                         └──▶ faultfs snapshot
                                  │ cut + seed
                                  ▼
                              crash state ──▶ reopen + invariant check
```

There are fixed picks too. A test can force all sectors to their old bytes or all names to survive, then vary one dimension at a time. The seed still records a concrete case. `power_off_after(n)` cuts every later mutation after the nth call, so a test can sweep all call boundaries without changing production code.

## A failure you can replay

The recorder decorates real IO and shadows each call in `faultfs`. It snapshots after mutating primitives and checks the real directory against its shadow. That last check matters: a storage path that quietly opens a file outside `journal::IO` would otherwise make the crash test look complete while skipping the dangerous write.

A failed run can be named by one scenario line, `faultlab/1 name=... seed=...`, and replayed with `FAULTLAB_SCENARIO`. An event log carries operations and faults to one history checker, which can check properties such as a written value surviving, a prefix of writes, or linearizability. The same kit also has Linux network and device-mapper labs for cluster faults. Their packets and blocks pass through the kernel; the Python tools configure faults and record them. The portable Python network proxy is useful for fault injection, but its extra hop makes it the wrong place to measure latency.

The payoff is visible in [strata's lifecycle gate](https://github.com/Kronuz/strata/blob/main/docs/gates/phase-3-lifecycle.md). It checked 3,635 reclamation crash cuts and 16,274 manifests. With the directory barrier in place, no manifest pointed at a missing file. Removing the barrier produced **93** such manifests. That is the sort of bug a single kill-and-reopen test can miss for a very long time, and the sort of counterexample a seeded model can hand back immediately. [Store, Then Search](/blog/strata-prospect/) follows the segment lifecycle those tests protect.

## The boundary of the model

This is a test of the **IO contract**, not a simulator for every behavior of ext4, XFS, or APFS. The model can allow states a particular filesystem would never leave. It assumes the sync operations it is given provide their promised durability; it cannot certify a weakened `fsync` implementation or a platform mapping that violates that promise. Real device tests remain useful for that boundary.

The useful claim is narrower and stronger: if recovery cannot survive a state that the contract allows, `faultlab` can make that state repeatable. A crash bug stops being a story about timing and becomes a fixture with a cut, a seed, and a failing invariant.
