---
title: "The Sparse Wheel"
subtitle: "A lock-free timer from Xapiand whose insert never stalls another thread."
description: "A hierarchical timer wheel from Xapiand backed by a sparse, lazily-grown array of atomic pointers. Its insert never waits on another insert, so its tail latency stays flat under contention where a locked heap or an Asio timer spike into the milliseconds, and it still answers 'what is due now', which a queue cannot. One header, three standard includes. With the realistic-depth numbers, how it compares on memory and complexity, the catches it ships with, and the narrow set of jobs it is the right tool for."
excerpt: "One thread in Xapiand sleeps while every other thread drops timed work onto its schedule: log flushes, fsyncs, commits, replication. The drop can never take a lock, and more than that, it can never stall. The little data structure that makes both true is the strangest, best thing in the whole codebase, and the only piece I would publish entirely on its own."
date: 2026-06-28
draft: true
series: "Opening Boxes"
seriesOrder: 10
tags:
  - opening-boxes
  - cpp
  - concurrency
---

*Part of the **Opening Boxes** series, technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). [A Search Engine from Scratch](/blog/a-search-engine-from-scratch/) opened [Xapiand](https://github.com/Kronuz/Xapiand); this one opens a single jewel I found inside it and pulled out into its own box: [stash](https://github.com/Kronuz/stash).*

Somewhere in a running [Xapiand](https://github.com/Kronuz/Xapiand) there is a thread that does almost nothing. It sleeps. Every so often it wakes, looks at a clock, runs whatever is due, and goes back to sleep. It is the laziest thread in the server, and on a busy node it is also the busiest, because every *other* thread is quietly dropping work onto its schedule: every delayed log line, every queued fsync, every database commit, every replication trigger. They all hand it a thing to do later, and they hand it over constantly.

One rule shaped all of it: that hand-off can never take a lock. If dropping a task onto the schedule blocked, every thread in the server would eventually queue behind one sleeping thread, and the search engine would grind to a halt waiting to schedule the very work it was trying to do.

But a lock-free hand-off is the easy half of the story, and on its own it would not be worth a post; any decent concurrent queue clears that bar. The half that earns the writeup is quieter, and it is about the tail.

## The one thing it does that nothing else does

A lock is not mainly slow on average. It is slow occasionally, and badly. Put fourteen threads on one mutex and most acquisitions are cheap, but every so often a producer arrives just as the holder is preempted, and then it does not wait a microsecond, it waits a scheduler quantum: hundreds of microseconds, sometimes a whole millisecond. On a path that every thread in the process touches, that stall does not stay local. The thread that hit it is now late with whatever it was carrying, and the lateness fans out. So the number that decides whether a scheduler can sit on the hot path is not its average insert time. It is its worst insert time under load.

That is the one thing stash does that nothing else does at once: **its insert never waits on another insert, so the tail stays flat under contention, and it still answers "what is due now."** Hold a realistic backlog and arm it from fourteen threads, and the worst-case insert looks like this:

| pending depth | stash p99 | locked heap p99 | Asio timer p99 |
| --- | --- | --- | --- |
| 64 | **1.6 µs** | 1.2 ms | 1.2 ms |
| 1,024 | **1.4 µs** | 151 µs | 188 µs |
| 16,384 | **1.8 µs** | 65 µs | 182 µs |

The same job, two to three orders of magnitude apart on the tail, and the gap is widest exactly where a real scheduler lives, at a few dozen to a few thousand pending. The heap and Asio are not badly written. They are *locked*, and under contention a lock spikes. stash does not, because no producer ever blocks another.

A lock-free queue keeps a flat tail too; its p99 on the same hardware is tens of nanoseconds. But a queue is first-in-first-out with no notion of *when*. It cannot tell you what is due before a deadline, which is the entire job. So the field splits cleanly:

- The structures with a flat tail under contention (queues) cannot order by time.
- The structures that order by time (heap, Asio) spike under contention.

stash is the one thing on both sides of that line. That is the whole reason it exists.

## What that lets you build

The flat tail is not an abstract nicety. In two shapes it changes what you can afford, and those are the cases to actually reach for it.

**A timeout on every request that never touches the request's own tail.** Give every in-flight request a deadline, armed by its handler thread and fired by one reaper. With a locked scheduler, each request takes the lock once to arm and once to cancel, so at a hundred thousand requests a second that one mutex carries two hundred thousand operations a second from every worker, and because the arm sits *on the request path*, the scheduler's lock spikes leak straight into your request p99. You armed a timeout to protect your tail and contaminated it instead. stash's arm and cancel are each one non-blocking atomic, so the scheduler's contention never reaches the request. At the depths and thread counts a busy server runs, that is the hundred-to-seven-hundred-times tail gap above landing exactly where an SLO is measured.

**Speculative arm-and-cancel, cheap enough to do on everything.** The Xapiand logger arms a "log this if it is still running in 200 ms" line on *every* operation and cancels the ones that finish fast, which is almost all of them. That pattern only pays if arming and cancelling are nearly free, because you spend them on every operation and throw most away. On a locked scheduler the arm-and-discard would add lock traffic to every fast path, the common case, just to catch the rare slow one. On stash each is a single atomic, so you can speculate on everything and keep the cost off the 99% that never fire. The same shape powers idle-connection sweeps and backoff retries: arm freely, cancel freely, fire rarely.

The mechanism under both is the one above: arm and cancel never block, so a scheduler can sit on a hot path that a locked one would throttle. Outside that shape stash's edge is real but incremental, a tighter tail you may or may not need. Inside it, it changes what you can build. The rest of this is how it works, how it stacks up, and where the shape breaks.

## The thing it cannot be

Two obvious designs fail, and that is what forces this one.

A priority queue, a binary heap of `(wakeup_time, task)` behind a mutex, is what most code reaches for. It is `O(log n)` to insert and to pop the soonest, and under one writer it is fine. Under a few hundred threads all inserting at once, that single mutex is the whole game: insertion serializes, the lock becomes the hottest thing in the process, and the lazy sleeping thread is now a global chokepoint. That is the tail spike from the table above, in source form.

A flat timer wheel, a fixed array of buckets swept as the clock advances, inserts in `O(1)` and never spikes. The catch is the array. Xapiand schedules up to twenty-four hours out and wants millisecond resolution. A flat array covering 24 hours at 1 ms is 86.4 million buckets, preallocated, mostly empty, sitting in memory forever on the off chance you schedule something for tomorrow afternoon. Absurd for a structure whose whole point is to hold a handful of pending fsyncs.

So the constraints are: insert without locking, and don't preallocate a continent of empty buckets. stash answers both at once.

## A sparse store of atomic pointers

The trick is to make the wheel's backing store *sparse* and *lazily grown*, and every growth step a lock-free compare-and-swap.

The primitive, `Stash<T>`, is a chunked array of `std::atomic<T*>`. It starts tiny. When a producer needs a slot that doesn't exist yet, it doesn't lock to extend the array. It allocates a chunk, then tries to publish it by `compare_exchange` into a pointer that was null. If two producers race for the same missing slot, both allocate, both attempt the swap, exactly one wins, and the loser sees it was beaten and deletes the chunk it just made.

That is the whole lock-free insert. **Loser deletes.**

```cpp
// the heart of it: grow a slot without ever taking a lock
std::atomic<T*>& slot = /* (key / Div) % Mod, materialized lazily */;
T* expected = nullptr;
T* fresh = new T(/* ... */);
if (!slot.compare_exchange_strong(expected, fresh)) {
    delete fresh;   // someone else published first: the loser frees its own work
}
```

No mutex appears anywhere on the producer side. A hundred threads can be growing different parts of the structure at once, and the only cost of a collision is one wasted allocation by whoever lost. The array materializes only where there is something to hold, so the 86-million-bucket continent never gets built. You pay for the slots you use.

The picture is two hands reaching for the same empty drawer:

```d2 alt="Two producers race to grow the same empty slot: both allocate a chunk and compare-and-swap into one atomic pointer. The winner's chunk is published into the slot; the loser's CAS fails and it deletes its own chunk."
direction: down
a: "Producer A"
b: "Producer B"
slot: "slot: atomic<T*>\n(currently null)" { style.bold: true }
a -> slot: "allocate + CAS"
b -> slot: "allocate + CAS"
win: "winner:\nslot now owns its chunk"
lose: "loser:\nCAS fails, deletes its chunk"
slot -> win
slot -> lose
```

## Stacking it into a wheel

`Stash<T>` is just the sparse store. To make a timer wheel you nest it. `StashSlots` is a keyed level: a key maps to slot `(key / Div) % Mod`, and each slot holds another `Stash`, so levels stack into coarse-to-fine resolution. At the bottom, `StashValues` is an append-only leaf of tasks with an atomic write cursor, so producers append lock-free too. Xapiand keys on nanoseconds since boot and stacks four `StashSlots` over one `StashValues`:

```text
key (ns)  ─►  4800 × 18s  ─►  36 × 500ms  ─►  10 × 50ms  ─►  50 × 1ms  ─►  task list
              └─ 4800 × 18s = 86,400s = exactly 24 h, addressed all the way down to 1 ms
```

A task due in three minutes lands in the right 18-second slot, then 500 ms, then 50 ms, then 1 ms, then onto the leaf. Only the path it touches gets allocated. The wheel is twenty-four hours wide and almost entirely made of nothing.

A sparse structure that grows only where there is work sounds slow to *read*: if almost all of it is empty, walking it should mean scanning an ocean of nothing. It doesn't, because of one piece of bookkeeping. The structure carries a pair of atomic bounds, the first and last keys that hold anything. The consumer never scans the empty stretches; it jumps from the first live key to the last and ignores the gap. Sparse buys cheap memory; the bounds buy a cheap walk on top of it.

The consumer works a key window in three modes. *Walk* drains everything due and runs it. *Peep* looks ahead at the soonest upcoming task without touching anything, so the thread can compute exactly how long to sleep. *Clean* reclaims emptied, aged-out slots, chasing the walk cursor without ever colliding with it. One mutex, one condition variable, a lock-free hand-back queue, and a thread that mostly sleeps. That is the entire scheduler.

## Who rides it

stash never appears in Xapiand by name in the places that matter. It hides behind two front doors, and both are worth seeing, because both shape the workload into the thing the wheel is good at.

The first is the **logger**. A surprising amount of logging is *scheduled*, not immediate: error-level messages, delayed lines, the "log this now but unlog it if the operation finishes cleanly in 200 ms" pattern that keeps the console quiet in normal operation and loud during a stall. Each is a cancellable task on a `stash`-backed scheduler, and the cancel is a single atomic store. The immediate lines never reach the wheel; they run inline on the thread that logged them. That split matters: the structure never sees a mob of threads converging on one instant. Every key it gets sits in the future, spread across a delay window, which is the shape its slots want.

The second is the **debouncer**. Xapiand debounces almost every background side effect: the async fsync, the database committers, the discovery-layer multicast, the schema and settings updaters. A burst of touches of one key collapses into a single eventual call, with a throttle floor and a randomized force-window so a forever-touched key still fires and a herd of due keys spreads across time. The collapse runs under a small mutex on a hash map, and most touches return there without scheduling anything. What survives, far less than the raw touches and scattered across the future on purpose, is what lands on the wheel. So the debouncer is not stash swallowing a firehose; it is something upstream shaping the firehose into the spread-across-the-future pattern the wheel is happiest with, the same thing the logger does by running its immediate lines inline. Both front doors hand stash the workload it is good at and keep the workload it is bad at away from it.

## How it compares

The bones first, because the columns are what decide it. `n` is live tasks, `p` concurrent producers, `range/res` the wheel's span over its resolution (24 h at 1 ms ≈ 86 million).

| | insert, 1 producer | insert, p producers | drain due | live memory | time order |
| --- | --- | --- | --- | --- | --- |
| **stash** | `O(1)` amortized | `O(1)`, **lock-free** | `O(1)` amortized | `O(n)`, **sparse** | slot-quantized |
| heap + mutex | `O(log n)` | `O(p·log n)`, one lock | `O(log n)` | `O(n)` | exact |
| flat timer wheel | `O(1)` | `O(1)` | `O(1)` | **`O(range/res)`** preallocated | slot-quantized |
| lock-free queue | `O(1)` | `O(1)`, near-linear | n/a (no *when*) | `O(n)` | **none** |
| `asio::steady_timer` | `O(log n)` | serialized on `io_context` | `O(log n)` | `O(n)` + per-timer | exact |

The asymptotics barely separate them; two columns do. *Insert under many producers*: the heap's `O(p·log n)` of waiting behind one lock is the tail spike from the top of the post; stash's is non-blocking `O(1)`. *Memory*: stash is `O(n)` in what is live where a flat wheel preallocates the whole continent, and that single trade is what makes a 24-hour millisecond wheel affordable at all. On memory stash sits with the heap and the queue, all `O(n)` in live items; Asio is heavier, a full `steady_timer` per arm; the flat wheel is the outlier nobody ships at this resolution. In the stress runs stash's peak memory tracked the live working set, not the millions of total inserts, which is the sparse store doing its job.

On **scaling**, the spread workload climbs with threads and then flattens as the box runs out of performance cores (1.96 to 5.54 M arms/s from 1 to 14 threads); the heap reaches the same neighbourhood, 5.65, by the other road, making its producers queue. They tie on average and split on the tail: stash holds a few-microsecond p99 across the range while the heap and Asio sit at tens of microseconds and blow out to a millisecond at depth. A lock-free queue out-scales all of them, tens of millions a second, and is the honest ceiling for raw movement, but it cannot order by time. stash does not win the throughput race; it wins the one number a hot-path scheduler is graded on, the worst case, and holds it as threads are added instead of degrading.

The cost is in a column the table doesn't have: **code**. A heap behind a mutex is a dozen lines and obviously correct; you can read it and believe it. stash is a header of lock-free machinery with a contract you have to honour. For most schedules the heap is the right call precisely because it is boring. stash earns its keep only when the tail under many writers is the thing that breaks, and then the trade flips.

## The catches, kept in

I called stash the best thing in the codebase. I did not call it safe to grab without reading the label, and the label is the honest part of this post.

It is **lock-free on the producer side, single-consumer on the walk side**, by contract. Many threads insert; exactly one walks. That asymmetry is the whole reason inserts are so cheap, and it is a hard constraint: point two consumers at it and the lock-free machinery becomes undefined behavior.

It has **no safe memory reclamation**. The consumer frees a node by swapping in null and deleting the old pointer, correct only because there is exactly one consumer. No hazard pointers, no epochs, no RCU. Concurrent erase-and-read would be a use-after-free.

It **allocates on the hot path**. The lock-free insert calls `new`, and `new` can block in the allocator. "Lock-free" means "never takes one of *our* locks," not "never waits on anything." Fine for a scheduler; wrong for a hard-real-time audio callback.

It **must not lap its own cleaner**. The wheel reuses each physical slot once per revolution (the full span, 24 hours in Xapiand's config), and the single consumer has to finish a clean pass within one revolution. If it ever falls a whole revolution behind, because the span is sized far too small for the load or the consumer is starved of CPU, a producer reusing a slot writes into the previous lap's subtree while clean is freeing it, and that is a use-after-free. With a 24-hour span against microsecond inserts the margin is colossal and it never happens; shrink the span and hammer it and it will. It is a property of every hierarchical timer wheel, but lock-free reclamation means you meet it as a crash rather than a stale read. Size the span to your horizon, keep one consumer that keeps up, and the margin is enormous.

It **moves contention, it does not remove it**. Two shared atomics stay warm: the valid-key bounds (every insert nudges the upper bound, since the clock only moves forward) and the leaf's append cursor. Both are non-blocking, categorically better than a contended lock, an atomic that retries still makes progress and never sleeps a thread. The real workload spreads keys across the future, so the leaf cursor mostly stays cool. Force every insert onto one key and every producer lands on the one leaf, bouncing that counter between caches; it is cache traffic, not a stall, but it is not free.

## Where it fits, and where it doesn't

The shape stash wants is specific: an integer key, usually a clock tick; many producers; one consumer; draining in key order; pointer-like values. Inside that shape the best fits share one more trait, that **cancelling is the common case**, because arm and cancel are each one non-blocking write where a locked heap puts a mutex on both.

| quintessential use case | why stash specifically |
| --- | --- |
| deferred / conditional logging ("log slow ops only") | most operations finish fast, so most armed lines are cancelled before they fire; arm and cancel are each one cheap atomic on the request's hot path. The original Xapiand use. |
| per-request deadline / timeout tracking | hundreds of thousands of in-flight requests, each armed with a timeout by its handler thread, fired by one reaper; the arm rides every request and must never stall. |
| connection / session idle sweeps | every connection arms "close if idle past T"; activity cancels far more often than it fires; one sweeper drains. |
| retry with backoff | failed work re-arms at `now + backoff` from many workers; one dispatcher drains it in time order. |
| debounce / coalescing | a burst of events landing in one slot folds into a single entry, which is what one leaf does. |
| textbook timer wheels: TCP retransmit, heartbeats, metric flushes | arm a future action from many sources, fire from one, cancel far more often than you fire. The job the wheel was invented for. |

The thread through all of them: **many threads arming on a hot path, one draining, cancel more common than fire, and a tail you cannot let spike.** When all four hold, I have not found anything that does it for less.

Reach past it the moment the shape breaks, and there is a better-understood tool for every direction it breaks in.

| the job | reach for instead, and why |
| --- | --- |
| pure hand-off, no *when* | a per-producer sharded queue (~47 M ops/s here, near-linear) or a Vyukov MPSC. stash is competitive on this load now but still carries time-ordering you would not use; the queue is the right shape. |
| exact order, even within a tick | a heap + mutex, or Asio. stash quantizes time to its slot resolution, so two items in the same slot come back in arbitrary order. |
| async I/O timers, light contention | Asio. At one or two threads its `steady_timer` is faster and the lock never heats; its per-timer bookkeeping and composition are worth it when contention is light. |
| concurrent consumers draining | any queue or a sharded map. stash is single-consumer by contract; its reclamation rests on one walker, with no SMR to relax it. |
| a general map, cache, arbitrary values | a real hash map or container. stash holds pointer-like values keyed by a clock tick and drained in order; it is not a key-value store. |
| no budget to `new` on insert | a preallocated pool or a flat wheel. the lock-free insert allocates, and the allocator can block. |

It is the honest mirror of the fit table: stash is the right answer only where the *when* is the point, the writers are many, and the tail matters; a plainer, better-known structure wins everywhere else.

## The one new idea in the pile

I pulled fifteen-odd libraries out of Xapiand this season: a perfect-hash, a constexpr string toolkit, a thread pool, an ISO-8601 parser, a reflective enum. Most are good, honest code, and most you could replace with something the standard library or a well-known dependency already does better. A thread pool is `std::jthread` and a real queue. Strict numeric parsing is `std::from_chars`. Worth extracting to shrink the project, not because the world was missing them.

The scheduler I would have put on that same list, and I would have been wrong. *A scheduler is an [Asio](https://github.com/chriskohlhoff/asio) timer*, I assumed, until I measured it. Asio's `steady_timer` is genuinely faster at one or two threads, and then it stops scaling: point eight or fourteen threads at it and every arm serializes on the `io_context`'s lock, throughput sags, and the tail climbs past sixty microseconds and into the milliseconds at depth. The stash-backed scheduler holds a flat single-digit-microsecond tail across the same range. The scheduler is not a second idea, though; it is stash wearing a hat. The idea is the wheel underneath.

So stash is the exception, the one genuinely new thing in the pile, and the novelty is narrow and precise: not "faster than everything," but the only timer structure I know of whose insert never stalls another thread while it still answers what is due. One header, three standard includes, with the label written honestly on the front. For the work it is built for, the insert side disappears into the noise no matter how many threads are hammering it, and the tail stays flat where the alternatives spike.

It started life as the reason one thread in a search engine could afford to sleep. It deserves a wider audience than that.

## How this was measured

The harness builds the real `stash.h` wheel in Xapiand's four-level configuration and runs it against the alternatives under the patterns that actually occur: keys spread across a delay window (the real deferred-log and timer pattern) and keys all converging on `now` (the pathological hand-off case). Apple M4 Pro, ten performance and four efficiency cores, `-O3`, one consumer draining concurrently, best of three.

One caveat changes how to read it. The throughput panels let the pending set grow to millions, which inflates the heap's `O(log n)` at low thread counts far past what a real scheduler ever sees. So the signal to trust is the tail and the *shape* of the scaling, not single-thread throughput. The bounded-depth panel is the honest one: it holds a realistic backlog and reports per-insert latency, which is where a scheduler lives.

**Bounded depth, 14 threads arming, one draining.** Insert latency, lower is better.

| depth | stash p99 / p999 | heap p99 / p999 | Asio p99 / p999 |
| --- | --- | --- | --- |
| 64 | **1.6 µs / 13 µs** | 1.2 ms / 4.9 ms | 1.2 ms / 8.2 ms |
| 1,024 | **1.4 µs / 16 µs** | 151 µs / 757 µs | 188 µs / 953 µs |
| 16,384 | **1.8 µs / 28 µs** | 65 µs / 253 µs | 182 µs / 1.5 ms |

The tail is flat across depth and one to three orders of magnitude under the locked alternatives. That is the whole case.

**Scheduler, spread keys (the real pattern),** million arms/sec, p99 underneath:

| threads | 1 | 8 | 14 | p99 at 14 |
| --- | --- | --- | --- | --- |
| **stash** | 1.96 | 4.60 | 5.54 | **4.3 µs** |
| heap + mutex | 1.94 | 3.82 | 5.65 | 49 µs |
| `asio::steady_timer` | 3.16 | 2.52 | 3.82 | 67 µs |

A dead heat on throughput; the difference is the tail, 4.3 µs against 49, because stash's producers never queue behind a lock. Asio is quickest at one thread, then sags and spikes.

**Hand-off, convergent keys (the case Xapiand routes around),** million ops/sec at 14 threads, the fairest place to be skeptical:

| structure | 14 threads | note |
| --- | --- | --- |
| per-producer sharded queue | 47.0 | nothing shared; near-linear. The right tool for hand-off. |
| Vyukov lock-free MPSC | 14.3 | one atomic exchange |
| mutex + deque | 7.7 | one lock, nothing else |
| **stash** | **6.8** | every producer converges on one leaf |
| heap + mutex | 5.9 | one lock, plus `log n` |

This used to be the *slowest* row, behind even a mutex and a deque, because a per-leaf commit loop serialized the converging producers. Replacing it with a three-state slot (reserved / filled / drained, read directly by the walker) moved it to mid-pack: it now beats the heap and ties a locked deque, while a queue still wins hand-off by a wide margin, as it should. The lesson is not that stash got good at hand-off; it is that its one ugly facet is no longer ugly, and a queue is still the right tool when there is no *when*.

The full harness, every thread count, both patterns, and the complete percentile tables are in the [repo](https://github.com/Kronuz/stash/tree/main/bench).
