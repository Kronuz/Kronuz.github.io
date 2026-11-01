---
title: "The Sparse Wheel"
subtitle: "A lock-free timer from Xapiand whose insert never stalls another thread."
description: "stash is a hierarchical timer wheel from Xapiand, built on a sparse, lazily grown array of atomic pointers. Many threads insert without a lock and one thread drains what is due in key order, so the insert tail stays flat under contention where a locked heap or an Asio timer spikes. How it works, what it costs, the catches it ships with, and the narrow job it is the right tool for."
excerpt: "One thread in Xapiand sleeps while every other thread drops timed work onto its schedule: log lines, fsyncs, commits, replication. The drop can never take a lock, and more than that, it can never stall. The little data structure that makes both true is the strangest, best thing in the whole codebase, and the familiar I would keep if I could keep only one."
date: 2026-08-06
series: "Familiars"
seriesOrder: 3
chapter: "Lock-Free"
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). [A Search Engine from Scratch](/blog/a-search-engine-from-scratch/) opened the whole engine, and a [jester](/blog/rolling-for-a-name/) and a [tracer](/blog/the-haunted-handler/) came out of it first. This one opens the jewel I would pull out of it before any other: [stash](https://github.com/Kronuz/stash).*

Somewhere in a running Xapiand there is a thread that does almost nothing. It sleeps. Every so often it wakes, looks at a clock, runs whatever is due, and goes back to sleep. It is the laziest thread in the server, and on a busy node it is also the busiest, because every *other* thread keeps dropping work onto its schedule: a log line to write, an fsync to run, a database to commit, a replication trigger to fire. They all hand it something to do later, and they hand it over constantly.

One rule shaped all of it: that hand-off can never take a lock. If dropping a task onto the schedule blocked, every thread in the server would eventually queue behind one sleeping thread, and the search engine would grind to a halt waiting to schedule the very work it was trying to do.

A lock-free hand-off is the easy half of the story, though, and on its own it would not be worth a post; any decent concurrent queue clears that bar. The half that earns the writeup is quieter, and it is about the tail.

## The one thing it does that nothing else does

A lock is slow occasionally, and badly. Put fourteen threads on one mutex and most acquisitions cost next to nothing: in the run below, the median insert into a mutex-guarded heap holding 1,024 timers took **83 ns**. But every so often a producer arrives just as the holder is preempted, and then it waits out a whole scheduler quantum. The 99th percentile of that same run is **151 µs**, nearly two thousand times the median. On a path every thread in the process touches, that stall does not stay local. The thread that hit it is now late with whatever it was carrying, and the lateness fans out. So the number that decides whether a scheduler can sit on the hot path is its worst insert under load. The average hardly matters.

That is the one thing stash does that nothing else I know of does at once: **its insert never waits on another insert, so the tail stays flat under contention, and it still answers "what is due now?"** Hold a realistic backlog, arm it from fourteen threads while one thread drains, and the 99th-percentile insert looks like this (Apple M4 Pro, the run recorded in the repo at [`a42e173`](https://github.com/Kronuz/stash/blob/a42e173/bench/RESULTS.md)):

| pending depth | stash p99 | heap + mutex p99 | Asio timer p99 |
| --- | --- | --- | --- |
| 64 | **1.6 µs** | 1.2 ms | 1.2 ms |
| 1,024 | **1.4 µs** | 151 µs | 188 µs |
| 16,384 | **1.8 µs** | 65 µs | 182 µs |

The same job, tens to hundreds of times apart on the tail, across the whole range a real scheduler lives in, dozens to thousands pending. The heap and Asio are not badly written. They are *locked*, and under contention a lock spikes. stash does not, because no producer ever blocks another.

A lock-free queue keeps a flat tail too. But a queue is first in, first out, with no notion of *when*. It cannot tell you what is due before a deadline, which is the entire job. So the field splits cleanly:

- The structures with a flat tail under contention (queues) cannot order by time.
- The structures that order by time (a heap, Asio's timers) spike under contention.

stash sits on both sides of that line. That is the whole reason it exists.

## The thing it cannot be

Two obvious designs fail, and their failures are what force this one.

A priority queue, a binary heap of `(wakeup_time, task)` behind a mutex, is what most code reaches for. It is `O(log n)` to insert and to pop the soonest, and under one writer it is fine. Under many writers that single mutex is the whole game: inserts serialize, the lock becomes the hottest thing in the process, and the lazy sleeping thread turns into a global chokepoint. That is the table above, in source form.

A flat timer wheel, a fixed array of buckets swept as the clock advances, inserts in `O(1)` and never spikes. The catch is the array. Xapiand schedules up to twenty-four hours out and wants millisecond resolution. A flat array covering 24 hours at 1 ms is 86.4 million buckets, preallocated, mostly empty, sitting in memory forever on the off chance you schedule something for tomorrow afternoon. Absurd for a schedule that holds dozens to thousands of tasks at a time.

So the constraints are: insert without locking, and don't preallocate a continent of empty buckets. stash answers both at once.

## A sparse store of atomic pointers

The trick is to make the wheel's backing store *sparse* and *lazily grown*, and to make every growth step a lock-free compare-and-swap.

The primitive, `Stash<T, Size>`, is a chunked array of `std::atomic<T*>`: a chain of nodes, each holding one fixed-size chunk of atomic pointers, and none of it allocated until something touches it. When a producer needs a slot that doesn't exist yet, it doesn't lock to extend the array. It allocates the missing piece, then tries to publish it with a `compare_exchange` into a pointer that was null. If two producers race for the same missing slot, both allocate, both attempt the swap, exactly one wins, and the loser sees it was beaten and frees what it just made.

That is the whole lock-free insert. **Loser deletes.** Here it is one level up, where a keyed level grows a child, abridged from `stash.h`:

```cpp
// StashSlots::put, abridged: grow a child level without ever taking a lock
auto ptr = atom_ptr.load(std::memory_order_acquire);
if (!ptr) {
    auto tmp = std::make_unique<_Tp>();
    if (atom_ptr.compare_exchange_strong(ptr, tmp.get(),
            std::memory_order_release, std::memory_order_acquire)) {
        ptr = tmp.release();  // won: the slot owns our level now
    }  // lost: ptr is the winner's level, and unique_ptr frees ours
}
ptr->put(ctx, key, std::forward<Args>(args)...);
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

`Stash` is only the sparse store. To make a timer wheel you nest it. `StashSlots<T, Size, Div, Mod>` is a keyed level: a key maps to slot `(key / Div) % Mod`, and each slot holds the next, finer level, so levels stack from coarse to fine. At the bottom, `StashValues` is an append-only leaf, where a producer claims the next slot with one atomic fetch-add on the leaf's write cursor. Xapiand keys on nanoseconds of the steady clock and stacks four `StashSlots` over one `StashValues`:

```text
key (ns)  ─►  4800 × 18s  ─►  36 × 500ms  ─►  10 × 50ms  ─►  50 × 1ms  ─►  task list
              └─ 4800 × 18s = 86,400s = exactly 24 h, addressed all the way down to 1 ms
```

A task due in three minutes lands in the right 18-second slot, then the right 500 ms, 50 ms and 1 ms slots, then onto the leaf. Only the path it touches gets allocated. The wheel is twenty-four hours wide and almost entirely made of nothing. A key past its far edge is refused.

A sparse structure sounds slow to *read*: if almost all of it is empty, walking it should mean scanning an ocean of nothing. It isn't, because of one piece of bookkeeping. The structure carries a pair of atomic bounds, the first and last keys that can hold anything, and the walk never looks outside them. Inside them, a range nobody touched is one null pointer to step over. Sparse buys cheap memory; the bounds buy a cheap walk on top of it.

The leaf carries one more idea, and it is what lets a producer claim a slot before its value is there. Every slot of a new leaf chunk starts out holding a sentinel, so each slot is in one of three states: *reserved* (claimed, value still on its way), *filled*, or *drained*. A producer claims with the fetch-add, then swaps its value in over the sentinel. The walk reads the state straight off the slot. It takes what is filled, and when it meets a reserved slot it parks its cursor there until the value lands, so a claimed slot is never skipped.

The consumer works a key window in three modes. *Walk* drains everything due and returns it. *Peep* reads the soonest upcoming entry without touching anything, so the thread can compute exactly how long to sleep. *Clean* frees whole subtrees once the walk has passed them. Put one thread on top that peeps, sleeps on a condition variable until the soonest deadline or until someone adds an earlier one, walks, cleans, and goes back to sleep, and you have a scheduler.

## Who rides it

stash never shows up by name in the parts of Xapiand that use it. It sits under a scheduler, and the scheduler has two front doors. (Strictly, there is more than one sleeping thread: the logger has its own scheduler, and so does each debouncer. They are all the same machine.)

The first door is the **logger**, the original reason stash exists. Most of Xapiand's log lines are not written by the thread that logs them. They become tasks on the logger's scheduler, and its one LOG thread writes them out in order, so a worker spewing logs never blocks on the disk or on a lock around the file. Some lines are armed for the future on purpose: a "this is taking too long" line, armed when an operation starts and cleared when it finishes in time, which is almost always. The console stays quiet in normal operation and speaks up during a stall, and the clear is one compare-and-swap on the task.

The second is the **debouncer**. Xapiand debounces its background side effects: the asynchronous fsync, the database committers, the discovery layer's updaters. A burst of touches of one key collapses into one eventual call. A throttle puts a floor on how often a key can fire, and a randomized force window makes sure that a key touched forever still fires, and that a herd of keys due at once spreads out instead of landing on one instant.

Both doors arm from many threads and fire from one, which is the shape the wheel was built for.

## How it compares

The bones first, because the columns are what decide it. `n` is live tasks, `p` concurrent producers, `range/res` the wheel's span over its resolution (24 h at 1 ms is about 86 million).

| | insert, 1 producer | insert, p producers | drain due | live memory | time order |
| --- | --- | --- | --- | --- | --- |
| **stash** | `O(1)` amortized | `O(1)`, **lock-free** | `O(1)` amortized | `O(n)`, **sparse** | slot-quantized |
| heap + mutex | `O(log n)` | `O(p·log n)`, one lock | `O(log n)` | `O(n)` | exact |
| flat timer wheel | `O(1)` | `O(1)` | `O(1)` | **`O(range/res)`** preallocated | slot-quantized |
| lock-free queue | `O(1)` | `O(1)`, near-linear | n/a (no *when*) | `O(n)` | **none** |
| `asio::steady_timer` | `O(log n)` | serialized on `io_context` | `O(log n)` | `O(n)` + per-timer | exact |

The asymptotics barely separate them; two columns do. *Insert under many producers*: the heap's `O(p·log n)` of waiting behind one lock is the tail from the top of the post, and stash's is a non-blocking `O(1)`. *Memory*: stash is `O(n)` in what is live where a flat wheel preallocates the whole continent, and that single trade is what makes a 24-hour millisecond wheel affordable at all. The repo's [`test/longevity.cc`](https://github.com/Kronuz/stash/blob/main/test/longevity.cc) shows it over time: without `clean` the structure grows without bound, and with it memory stays bounded.

The cost is in a column the table doesn't have: **code**. A heap behind a mutex is a dozen lines and obviously correct; you can read it and believe it. stash is a header of lock-free machinery with a contract you have to honor. For most schedules the heap is the right call precisely because it is boring. stash earns its keep only when the tail under many writers is the thing that breaks.

## The catches, kept in

I called stash the best thing in the codebase. I did not call it safe to grab without reading the label, and the label is the honest part of this post.

It is **lock-free on the producer side and single-consumer on the walk side**, by contract. Many threads insert; exactly one thread walks, peeps and cleans. That asymmetry is the whole reason inserts are so cheap, and it is a hard constraint: point two consumers at it and they corrupt the walk's cursors, which are plain fields.

Its **reclamation rests on that one consumer**. The consumer frees a subtree by swapping its pointer to null and deleting it. That is safe only because a single walker decides what has been passed, and `clean` frees nothing the walk has not passed or a producer may still be filling.

It **allocates on the hot path**. The lock-free insert calls `new`, and `new` can block in the allocator. Here "lock-free" means the insert never takes a lock of *its own*; the allocator may still take one. Fine for a scheduler; wrong for a hard-real-time audio callback.

Its **cancel is a flag**. stash has no remove. A caller cancels by marking its value dead (the scheduler's `clear()` is one compare-and-swap), and the entry, along with whatever object it points to, stays in its slot until the walk reaches it, which can be the whole remaining delay. Moving a deadline means a cancel plus a fresh insert, and leaves a dead entry behind. At any moment, the dead entries pending are about the cancel rate times the delay.

Its **time is quantized**. A slot drains whole once the walk reaches it, so an item can fire up to one finest slot early (1 ms on Xapiand's wheel), and items that share a slot come back in arrival order, whatever their exact deadlines.

It **must not lap its own cleaner**. The wheel reuses each physical slot once per revolution (24 hours in Xapiand's configuration), and the consumer has to finish a clean pass within one. If it falls a whole revolution behind, because the span is far too small for the load or the consumer is starved of CPU, a producer reusing a slot writes into the previous lap's subtree while `clean` is freeing it: a use-after-free. With a 24-hour span the margin is enormous; shrink the span and hammer it and you will hit it. Every hierarchical timer wheel has this property, but lock-free reclamation means you meet it as a crash instead of a stale read.

It **moves contention somewhere cheaper**. Inserts still share a few hot words, among them the upper key bound and the append cursor of whichever leaf they land in. Both are atomic read-modify-writes that never put a thread to sleep, and keys spread across the future spread across leaves. Force every insert onto one key, though, and every producer lands on the same leaf, bouncing its cursor between caches: cheaper than a stall, still not free.

## Where it fits, and where it doesn't

The shape stash wants is specific: an integer key, usually a clock tick; many threads inserting; one thread draining in key order; pointer-like values; and **most entries firing rather than being cancelled**. That last one is the cancel catch turned into advice. Arming is one non-blocking insert and cancelling is one compare-and-swap, but a cancelled entry stays until its slot drains, so a timer that is usually cancelled pays for its whole delay anyway.

| fits | why stash |
| --- | --- |
| deferred work armed from many threads: log lines, flushes, commits | request and worker threads arm it, one thread fires it, and nearly all of it fires. Xapiand's logger and its fsync and commit debouncers are this shape. |
| per-key debouncing | many threads touch a key; one thread walks the wheel and dispatches the single call that survives. |
| many timers at millisecond resolution, armed from many threads | say, a flush deadline for each of tens of thousands of open indexes, armed when an index first gets dirty, so an idle index holds no timer. One shared wheel, one walker. |

The thread through all of them: **many threads arming, one draining, most of it firing, and a tail you cannot let spike.**

Xapiand's own logger bends the cancel rule, and the arithmetic says why it gets away with it. Its slow-operation lines are cleared far more often than they fire, but its ready-made ones are armed 100 ms to a second out, so a cleared line lingers for a second at most. A connection idle timeout, minutes out and pushed back on every request, would pile up minutes' worth of dead entries.

Reach past stash the moment the shape breaks. There is a better-understood tool in every direction it breaks in:

| the job | reach for instead, and why |
| --- | --- |
| a general map or queue, or more than one consumer | a real map, or a queue (a Vyukov MPSC, or one queue per producer). stash has one walker by contract, its values must be pointer-like, and a null or zero value reads as absent. |
| timers owned by one event loop: connection idle timeouts, request deadlines, protocol ticks | the loop's own timers, such as Asio's `steady_timer`, one per connection and re-armed lazily. There is no producer contention to remove, and the loop's timers cancel exactly. |
| timers that are usually cancelled or moved | the same owner-loop timers, or a heap owned by one thread. In stash every cancel and every move leaves a dead entry until its old deadline. |
| a handful of timers, exact deadline order, or sub-millisecond deadlines | a binary heap owned by the thread that fires them. stash drains a whole slot at once, in arrival order. |
| keys past the horizon (24 hours on Xapiand's wheel) | one more level on top (each level's span is the next level's slot width, so the reach multiplies), or re-arming in hops. |
| no budget to `new` on insert | a preallocated pool or a flat wheel. The lock-free insert allocates, and the allocator can block. |

It is the honest mirror of the fit table: stash is the right answer only where the *when* is the point, the writers are many, and the tail matters. A plainer, better-known structure wins everywhere else.

## The one new idea in the pile

Plenty of the [sixty-odd familiars](/blog/session-zero/) have a well-known stand-in: a thread pool is `std::jthread` and a real queue, strict numeric parsing is `std::from_chars`. I would have put the scheduler on that list too. *A scheduler is an [Asio](https://github.com/chriskohlhoff/asio) timer*, I assumed, until I measured it under fourteen writers and watched its p99 climb past a hundred microseconds at every depth I tried. And the scheduler is only stash wearing a hat; the idea is the wheel underneath.

So stash is the one familiar I could not swap for something better known, and its novelty is narrow: a timer structure whose insert never stalls another thread while it still answers what is due. It started life as the reason one thread in a search engine could afford to sleep. It deserves a wider audience than that.

## How this was measured

The harness in [`bench/`](https://github.com/Kronuz/stash/tree/main/bench) builds the real `stash.h` wheel in Xapiand's four-level configuration and races it against a mutex-guarded binary heap and Asio's `steady_timer` (one timer per arm, the only way to ask Asio to "run this at time T"), with one consumer draining the whole time. The table at the top is `bench_steady`, which holds the pending set near a fixed depth and times every insert. It is the run recorded at [`a42e173`](https://github.com/Kronuz/stash/blob/a42e173/bench/RESULTS.md): Apple M4 Pro (10 performance and 4 efficiency cores), AppleClang 17, `-O3 -DNDEBUG`, best of two. The repo's throughput panels let the pending set grow to millions, which inflates the heap's `O(log n)` far past anything a real scheduler sees, so trust them for the shape of the tail only. Your numbers will differ; the latest run lives in [`bench/RESULTS.md`](https://github.com/Kronuz/stash/blob/main/bench/RESULTS.md).

That is the familiar I would keep if I could keep only one: a lock-free slot store that also knows what time it is. The next one lives closer to the door and meets every request before anything else does. It is the router, and its whole job is to decide, in the time it takes to read a URL, which of a thousand handlers a request belongs to, without ever walking the whole tree to find out, and without falling apart on the one input an attacker would send on purpose.
