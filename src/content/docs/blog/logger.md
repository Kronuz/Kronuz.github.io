---
title: "The Line You Usually Cancel"
subtitle: "Arming a 'this is taking too long' log on every operation, and paying only for the one that fires."
description: "logger is a deferred, lock-free logging library, and the original reason the stash timer wheel was built. Each thread writes its lines into its own queue without blocking any other, one LOG thread merges the queues and writes them in order, and a 'this operation is taking too long' line is cancelled with a single atomic when the operation finishes in time, so the common fast path logs nothing at all. The trick only pays because arming and cancelling are each that cheap; on a locked scheduler you would add lock traffic to every fast path just to catch the rare slow one."
excerpt: "You want to know which operations are slow, but logging every operation is noise you pay for on the hot path. So you invert it: arm a 'log this if it is still running in 200 ms' line on every single operation, and cancel it, free, the instant the operation finishes, which is almost always. The seventh familiar logs the exceptions by speculating on everything, and it is the reason the sparse wheel was built at all."
lastUpdated: 2026-11-15
date: 2026-08-16
series: "Familiars"
seriesOrder: 7
chapter: "Lock-Free"
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of [**Familiars**](https://kronuz.com/cpp-libraries/), my collection of standalone C++ building blocks. This one closes a loop: [logger](https://github.com/Kronuz/logger) is the original reason [the sparse wheel](/blog/the-sparse-wheel/) was built.*

Here is a thing you want and cannot easily have: to know which operations in a busy server were slow, without logging the ones that were fast. The fast ones are almost all of them, and they are on the hot path, so logging every operation to catch the rare slow one means paying for the common case to observe the exception. Most systems give up and sample, or log nothing, or log everything and drown.

[logger](https://github.com/Kronuz/logger) does something better, and slightly absurd. For every operation, it **arms** a log line that says "print me if this is still running in two hundred milliseconds," and then, the instant the operation finishes, which is almost always well under that, it **cancels** the line. The common case logs nothing. The only lines that ever reach the output are the ones that outlived their deadline: the actual slow operations, and nothing else. You find the exceptions by speculating on everything and throwing the speculation away.

## Why that is normally too expensive

Arm-and-cancel-on-everything sounds wasteful because on any normal scheduler it is. Arming a timed line means inserting into a schedule; cancelling means removing from it; and if that schedule is a mutex-guarded heap, then every operation, the fast ones included, now takes a lock twice, to arm and to cancel, just so the rare slow one can be caught. You have moved the cost of observing the exception onto the common case, and worse, you have put a contended lock on the hot path, where its occasional stall leaks straight into the latency you were trying to measure. The cure poisons the patient.

logger gets away with it because neither step touches a shared schedule. Arming a deferred line writes a small reference into the calling thread's *own* queue, published with one store, so no two threads ever contend for it. Cancelling is one compare-exchange on the line's record: whoever gets there first, the operation finishing or the LOG thread firing, wins, and the other does nothing. No lock, no stall, nothing that touches the operation's own tail.

The schedule itself lives on the other side. The LOG thread files each deferred line in its own timer wheel, [wheel](https://github.com/Kronuz/wheel), a wheel of one-millisecond slots that only that thread ever touches, so it needs no lock and no atomic at all. A cancelled line just sits in its slot until the LOG thread reaches it and drops it.

That was not always the shape. logger is the reason I built [the sparse wheel](/blog/the-sparse-wheel/), stash, whose insert never waits on another thread, so that every worker could arm a timer directly. Years later the deferred lines moved into a wheel owned by the LOG thread alone, and stash is retiring; [Who Owns the Wheel](/blog/retiring-the-sparse-wheel/) tells why.

## Three paths for a line

Not every line is deferred. A log entry takes one of three routes, chosen by what you are asking for:

- **Severe lines write inline**, on the calling thread, right now. When something is on fire you do not want it queued behind a background writer; you want it out before the process maybe dies.
- **Routine lines go into the thread's own queue**, formatted in place, with no lock and no allocation. The single LOG thread merges every thread's queue in the order the lines were logged and writes them off the hot path.
- **Deferred lines are due at *now + delay*** and fire only if nothing cancels them first. This is the slow-op line, the debounce, the "warn me if this is still stuck later."

Many producers that never wait on each other, one consumer writing ordered output, and a deferred lane you arm and usually cancel. Everything host-specific, the exception formatting, the real backtraces (that is [another familiar](/blog/the-haunted-handler/)), the thread names, the timestamp format, comes in through hooks. Underneath sit only wheel, [workpool](https://github.com/Kronuz/workpool) for the LOG thread itself, [term-color](https://github.com/Kronuz/term-color) for the colors, and the small [cppcodec](https://github.com/tplgy/cppcodec).

## Where it fits

Reach for it when logging is on a hot path with many threads, when you want slow-path or debounced lines you arm and usually cancel, and when a single thread writing ordered output is what you want. Reach for something simpler if you have one thread, or no notion of *when*, or you need pluggable structured sinks and severity routing beyond what its handlers give you. This is a fast lock-free arm with a deferred-cancel trick, not a logging framework.

The next familiar lives one layer down, at the wire itself. It reads an HTTP request that arrives in pieces, a few bytes at a time, and it has to resume mid-header without ever looking past the bytes it was actually handed. It once looked sixteen bytes too far.
