---
title: "Who Owns the Wheel"
subtitle: "Why stash and scheduler retire, and what replaces them."
description: "stash, the lock-free timer wheel from Xapiand, and scheduler, the library on top of it, are being retired. Measured on the timers my systems actually run, which are re-armed and cancelled far more often than they fire, a single-owner wheel with a striped inbox costs 3.6 to 30 times less per timer and 9 to 17 times less per arm from another thread. How it was measured, where stash's time goes, how the new wheel library works, and what stash still does better."
excerpt: "Three months ago I wrote that stash was the familiar I would keep if I could keep only one. In the same post I wrote a table of when not to use it, and the first row was timers that are usually cancelled or moved. Then I built a system made almost entirely of those."
date: 2026-11-11
authors: kronuz
series: "Familiars"
seriesOrder: 30
tags:
  - familiars
  - cpp
  - concurrency
---

I am retiring [stash](https://github.com/Kronuz/stash) and [scheduler](https://github.com/Kronuz/scheduler). Measured on the timers my systems run today, a timer wheel owned by one thread costs **3.6 to 30 times less** per timer than stash, and with a striped inbox for other threads it arms **9 to 17 times cheaper** than stash does from those threads, with no allocation at all. The replacement is a new library, [wheel](https://github.com/Kronuz/wheel). This post is how I got there, and what stash still does better.

## The table I wrote myself

In [The Sparse Wheel](/blog/the-sparse-wheel/) I called stash the strangest, best thing in Xapiand, the familiar I would keep if I could keep only one. I meant it. Its insert never waits on another insert, so fourteen threads can arm timers while one thread drains them, and the tail stays flat where a locked heap spikes.

That post also had a table of when to reach past stash. Its first rows were timers owned by one event loop, and timers that are usually cancelled or moved, because stash cannot take a timer back out. A cancel marks the entry dead and leaves it filed until its slot drains.

Then I started building [Detent](https://github.com/Kronuz/Detent), and its timers are almost all that second kind. A consensus heartbeat re-arms every follower's election timer, every time. A request deadline is armed and then cancelled when the request finishes first, which is nearly always. A debounced fsync is pushed back again and again before it fires once. Nothing was broken; the old shape simply never had to carry this load. The new system is made of the timers I had warned against, so before choosing a wheel for it I measured whether my favorite familiar still won.

## How it was measured

Six candidates went into one harness with one interface: arm, cancel, expire, and arm from another thread where the candidate allows it.

1. A single-owner prototype wheel: 4,096 slots of one millisecond, a 32-byte entry that lives inside the object that owns the timer, and only the owner thread touching it.
2. stash as it is, in Xapiand's four-level configuration.
3. stash with a new leaf that leaves nothing behind on cancel, to see whether a fixed stash would do.
4. The prototype with one shared lock-free inbox for other threads.
5. The same inbox, threaded through the entry's own link so the entry stays 32 bytes.
6. That inbox split into 64 stripes, one cache line each.

The decision rule was written and committed before the first measured run: one shape wins only if it is within 10% of the best on the single-loop path and within 10% of stash on stash's own cross-thread path. Every number came from a job that had the machine to itself, with paired same-code runs to show the noise, on a 16-thread Intel laptop under macOS and again in a Linux VM. Every candidate first matched a reference model and passed the cross-thread tests under AddressSanitizer and ThreadSanitizer. The full record, with job ids, is Detent's [wheel evidence](https://github.com/Kronuz/Detent/blob/main/docs/design/wheel-evidence.md).

## Where stash's time goes

The single-loop score is one entry's whole life: arm it, re-arm it, cancel it, then arm it again and expire it. This table gives the median nanoseconds per entry on macOS, at a thousand and at a million live entries, and the ratio to the best candidate.

| Candidate | 1,000 entries | ratio | 1,000,000 entries | ratio |
|---|---:|---:|---:|---:|
| owner-only prototype | 37.3 | 1.00 | 352.7 | 1.06 |
| stash as is | 1,106 | 29.7 | 1,201 | 3.60 |
| stash, fixed leaf | 857 | 23.0 | 594 | 1.78 |
| prototype, 64-stripe inbox | 44.4 | 1.19 | 333.3 | 1.00 |

Most of stash's cost sits in one step. Expire costs it **835 nanoseconds per entry** at a thousand entries, because every re-arm and every cancel left a stale filing behind, and the walk has to visit each one, notice that it no longer counts, and drop it. The owned wheel stores each timer as a node with two pointers, so a cancel unlinks it in two writes and leaves nothing to visit.

The fixed leaf was the fair test of that diagnosis. With nothing left behind, its expire drops to 157 nanoseconds at a million entries, close to the prototype's 106. It still loses badly at a thousand, because stash walks all four of its levels on every tick, even when they are nearly empty: 664 nanoseconds per entry.

Then there is the heap. stash allocates as it files, and frees only when its cleaner passes the old slot, so each re-arm costs **101 bytes** of heap at a thousand entries and 27 at a million until the old deadline goes by. The owned wheel allocates nothing, ever: the entry is part of its owner.

## The surprise: stash was right about sharing

The cross-thread run is stash's home ground: many producer threads arm, one owner fires. This table gives each producer's cost per arm in nanoseconds.

| Candidate | 1 producer | 4 producers | 14 producers |
|---|---:|---:|---:|
| stash as is | 157 | 196 | 292 |
| stash, fixed leaf | 126 | 158 | 216 |
| one shared inbox | 15 | 267 | 1,379 |
| 64-stripe inbox | 13.6 | 11.6 | 32.6 |

The shared inbox is the row that taught me something. With one producer it is ten times cheaper than stash. With fourteen it is **almost five times worse**, because one inbox head is one cache line, and fourteen cores fighting over one cache line spend their time passing it around. stash's whole design is a refusal to put every producer on one word, and that instinct was correct.

Splitting the inbox into 64 stripes gives each producer thread its own head on its own line. A push is one compare-and-swap that nobody else contends, and the owner drains only the stripes that hold something. At fourteen producers that is 32.6 nanoseconds against stash's 292. The Linux VM agreed: at one, four and seven producers the striped wheel cost 8%, 4% and 5% of what stash did.

## How the wheel works

The winning shape became [wheel](https://github.com/Kronuz/wheel), one C++20 header with no dependencies. Every timer is an entry of 32 bytes that lives inside whatever owns it: a link, a back-link, a deadline in nanoseconds, and the function to call.

```d2 alt="Two halves. In stash, every producer thread writes into the shared wheel with atomic operations, and one consumer drains it, skipping stale copies. In the new wheel, producer threads push into their own stripe of a 64-stripe inbox, the owner thread moves those entries into a private wheel, and the owner alone arms, cancels and fires."
direction: down
stash: "stash" {
  direction: down
  p: "producer threads"
  w: "shared wheel\natomics on every slot" { style.bold: true }
  c: "consumer\nskips stale copies"
  p -> w: "insert"
  w -> c
}
wheel: "wheel" {
  direction: down
  p: "producer threads"
  i: "64-stripe inbox"
  w: "private wheel\nno atomics" { style.bold: true }
  f: "owner\narms, cancels, fires"
  p -> i: "push"
  i -> w: "drain"
  w -> f
}
```

The wheel itself is a level of 4,096 slots of one millisecond, the next four seconds, with six levels of 64 slots above it, the coarsest of them spanning 142 years per slot. Arming picks the lowest level whose slots reach the deadline, at most six comparisons, and links the entry into that slot. A deadline far in the future moves down at most once per level as its time approaches, and no tick ever walks an entry that is not due: a million timers a day out cost a run of one-millisecond ticks nothing.

Using it looks like this: one entry, armed 250 milliseconds out on the owner's clock, and a loop that sleeps until the wheel says it has work.

```cpp
wheel::timer_wheel w(0);  // nanoseconds on the owner's clock
wheel::timer_entry e;
e.fire = [](wheel::timer_entry& x, bool expired) noexcept { /* ... */ };
w.arm(e, 250'000'000);
for (std::uint64_t now = 0; w.size(); now = w.next()) { w.expire(now); }
```

The wheel never reads a clock. A reactor hands it `steady_clock` time; a simulator hands it a counter and runs a day of timers in no time. Expire moves every due entry to a detached list before any of them fires, so a fire may cancel or re-arm anything, itself included. An entry never fires early and fires at most one tick late.

## How it differs

The whole difference is one rule about who may touch the wheel. Only the owner thread arms, re-arms, cancels and expires. Any other thread may arm an entry that is not armed, by pushing it into its stripe, and after that only the owner touches it. This table compares the two libraries on the points where a caller would notice.

| | stash | wheel |
|---|---|---|
| who writes the wheel | every producer, with atomics | the owner only |
| cancel and re-arm | a dead flag, filed until its slot drains | unlink, two pointer writes |
| heap per timer | allocates as it files | none |
| horizon | 24 hours in Xapiand's configuration | any 64-bit nanosecond deadline |
| firing | up to one slot early | never early, at most one tick late |
| cancel from another thread | one compare-and-swap, any thread | post it to the owner, or a flag the fire checks |

## What stash still does better

That last row is real, and it matters for the logger. The [logger](/blog/logger/) arms a "this is taking too long" line on every operation and cancels it from the worker thread when the operation finishes, which is almost always. On the wheel a worker cannot cancel; it sets a flag the fire checks, and the entry stays filed until its deadline, much as it does in stash. Whether the cheaper arm still wins that workload is a measurement I have not run yet.

It is not the only open item.

- **Fire lag under a burst.** In the wheel the owner files every remote arm itself. When a million arms landed within ten milliseconds, the striped wheel's last fire came 4.3 milliseconds after its deadline at fourteen producers, against stash's 1.0.
- **The tail.** The Sparse Wheel's headline was stash's flat 99th-percentile insert. These runs measured medians, not the tail of a striped push.
- **One bound missed.** On macOS the striped wheel is 1.19 times the owner-only prototype at a thousand entries, over the 10% rule, because its re-arm costs 9.7 nanoseconds against 5.9. The noise band at that size is 31%, so the gap is small, but it is real and it is the new library's first job.
- **Stash's own best case.** A separate run is measuring stash where it should shine, fire-and-forget timers from many threads over a 24-hour horizon, under a rule written before it ran. If stash wins a use there by 10% or more, it keeps that use.

## Why scheduler goes too

Scheduler is stash's front door: a threaded scheduler, a debouncer and scheduled tasks, running stash-timed callbacks on threads. With an owned wheel, a debounce is one entry re-armed in place, which is the operation the wheel is cheapest at, and a callback runs on the loop that owns the wheel. Where something must fire while every loop is busy, a small thread owns a wheel of its own. Keeping scheduler beside that would mean two ways to do one thing.

## Before anything is archived

Retirement has three conditions, and nothing is archived until all three hold.

1. The replacement is its own library, which wheel is. My task library, the logger and Xapiand will depend on it rather than carry a copy.
2. It is measured better on every current use: the logger's deferred and slow-operation lines, and Xapiand's fsync and manager debouncers, each with its own before-and-after.
3. Nothing uses stash or scheduler. A search across every one of my repositories comes back empty, and only then are the two archived.

This one stings a little. I wrote stash by hand, over a long time, and it was a good answer to the question it was built for: many threads schedule, one fires, and nobody may block. The new wheel keeps both of its best ideas, nested levels of slots and producers that never wait on each other. What it drops is the shared structure everyone writes into, because the question changed: the owner re-arms constantly, and the owner should not have to pay for sharing.
