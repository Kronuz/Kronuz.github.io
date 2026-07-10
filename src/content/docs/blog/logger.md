---
title: "The Line You Usually Cancel"
subtitle: "Arming a 'this is taking too long' log on every operation, and paying only for the one that fires."
description: "logger is Xapiand's deferred, lock-free logging library, and the original reason the stash timer wheel exists. Many threads arm log lines without blocking each other, one thread drains and writes them in order, and a scheduled 'this operation is taking too long' line is cancelled with a single atomic when the operation finishes in time, so the common fast path logs nothing at all. The trick only pays because arming and cancelling are each one atomic on the lock-free wheel; on a locked scheduler you would add lock traffic to every fast path just to catch the rare slow one."
excerpt: "You want to know which operations are slow, but logging every operation is noise you pay for on the hot path. So you invert it: arm a 'log this if it is still running in 200 ms' line on every single operation, and cancel it, free, the instant the operation finishes, which is almost always. The seventh familiar logs the exceptions by speculating on everything, and it is the reason the wheel two posts ago was built at all."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 7
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one closes a loop: [logger](https://github.com/Kronuz/logger) is the original reason [the wheel](/blog/the-sparse-wheel/) two posts ago exists.*

Here is a thing you want and cannot easily have: to know which operations in a busy server were slow, without logging the ones that were fast. The fast ones are almost all of them, and they are on the hot path, so logging every operation to catch the rare slow one means paying for the common case to observe the exception. Most systems give up and sample, or log nothing, or log everything and drown.

[logger](https://github.com/Kronuz/logger) does something better, and slightly absurd. For every operation, it **arms** a log line that says "print me if this is still running in two hundred milliseconds," and then, the instant the operation finishes, which is almost always well under that, it **cancels** the line. The common case logs nothing. The only lines that ever reach the output are the ones that outlived their deadline: the actual slow operations, and nothing else. You find the exceptions by speculating on everything and throwing the speculation away.

## Why that is normally too expensive

Arm-and-cancel-on-everything sounds wasteful because on any normal scheduler it is. Arming a timed line means inserting into a schedule; cancelling means removing from it; and if that schedule is a mutex-guarded heap, then every operation, the fast ones included, now takes a lock twice, to arm and to cancel, just so the rare slow one can be caught. You have moved the cost of observing the exception onto the common case, and worse, you have put a contended lock on the hot path, where its occasional stall leaks straight into the latency you were trying to measure. The cure poisons the patient.

logger gets away with it because its schedule is not a locked heap. It is the [stash timer wheel](/blog/the-sparse-wheel/), where arming and cancelling are each a **single lock-free atomic** that never waits on another thread. So you really can arm a deferred line on every operation and cancel almost all of them, and the cost on the fast path is one atomic to arm and one to cancel, no lock, no stall, nothing that touches the operation's own tail. That is not a coincidence: logger is the reason the wheel was built. The strangest data structure in the engine exists to make this one logging pattern affordable.

## Three paths for a line

Not every line is deferred. A log entry takes one of three routes, chosen by what you are asking for:

- **Severe lines write inline**, on the calling thread, right now. When something is on fire you do not want it queued behind a background writer; you want it out before the process maybe dies.
- **Routine lines are handed to a single LOG thread**, keyed at *now*, and written in order off the hot path. Many threads produce; one thread consumes and serializes; the producers never block each other.
- **Deferred lines are keyed at *now + delay*** and fire only if nothing cancels them first. This is the slow-op line, the debounce, the "warn me if this is still stuck later."

One consumer writing ordered output, many lock-free producers, and a deferred lane you arm and usually cancel. Everything host-specific, the exception formatting, the real backtraces (that is [another familiar](/blog/the-haunted-handler/)), the thread names, the timestamp format, comes in through hooks, so the core depends only on the scheduler beneath it.

## Where it fits

Reach for it when logging is on a hot path with many threads, when you want slow-path or debounced lines you arm and usually cancel, and when a single thread writing ordered output is what you want. Reach for something simpler if you have one thread, or no notion of *when*, or you need pluggable structured sinks and severity routing beyond what its handlers give you. This is a fast lock-free arm with a deferred-cancel trick, not a logging framework.

The next familiar lives one layer down, at the wire itself. It reads an HTTP request that arrives in pieces, a few bytes at a time, and it has to resume mid-header without ever looking past the bytes it was actually handed. It once looked sixteen bytes too far.
