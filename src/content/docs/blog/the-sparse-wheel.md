---
title: "The Sparse Wheel"
subtitle: "A lock-free timer from Xapiand that pays for only the slots it uses."
description: "How Xapiand schedules a flood of timed events without the scheduler thread ever taking a lock: a sparse, lazily-grown array of atomic pointers, grown by allocate-then-CAS, stacked into a four-level timer wheel. With the catches it ships with, and the narrow spot where it still beats a heap, a queue, or an Asio timer."
excerpt: "One thread in Xapiand sleeps while every other thread drops timed work onto its schedule: log flushes, fsyncs, commits, replication. The drop can never take a lock. The little data structure that makes that true is the strangest, best thing in the whole codebase, and the only piece I would publish entirely on its own."
date: 2026-06-26
draft: true
series: "Opening Boxes"
seriesOrder: 10
tags:
  - opening-boxes
  - cpp
  - concurrency
---

*Part of the **Opening Boxes** series, technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). [A Search Engine from Scratch](/blog/a-search-engine-from-scratch/) opened [Xapiand](https://github.com/Kronuz/Xapiand); this one opens a single jewel I found inside it and pulled out into its own box: [stash](https://github.com/Kronuz/stash).*

Somewhere in a running [Xapiand](https://github.com/Kronuz/Xapiand) there is a thread that does almost nothing. It sleeps. Every so often it wakes up, looks at a clock, runs whatever is due, and goes back to sleep. It is the laziest thread in the server, and on a busy node it is also the busiest, because every *other* thread is quietly dropping work onto its schedule: every delayed log line, every queued fsync, every database commit, every replication trigger. They all hand it a thing to do later, and they hand it over constantly.

One rule shaped all of it: that hand-off can never take a lock. If dropping a task onto the schedule blocked, every thread in the server would eventually queue up behind one sleeping thread, and the search engine would grind to a halt waiting to schedule the very work it was trying to do. The producers have to be able to drop tasks in parallel, all of them, while the one consumer walks the schedule in order and runs what is due.

The data structure that makes that true is **[stash](https://github.com/Kronuz/stash)**, and it is the most novel thing in the entire Xapiand codebase. It is the one piece I looked at, after pulling a dozen reusable libraries out of that project, and thought: this one is actually worth publishing on its own. So I did. This is what it is, why it exists, where it bites, and the narrow spot where I would still reach for it over anything newer.

## The thing it cannot be

Start with what does not work, because that is what forces the design.

The obvious schedule is a priority queue: a binary heap of `(wakeup_time, task)`, ordered by time, with a mutex around it. It is `O(log n)` to insert, `O(log n)` to pop the soonest, and it is what most code reaches for. Under one writer it is fine. Under a few hundred threads all inserting at once, that single mutex is the whole game: insertion serializes, the lock becomes the hottest thing in the process, and the lazy sleeping thread is now a global chokepoint. Exactly the failure we are trying to avoid.

The other obvious schedule is a timer wheel: a fixed array of buckets, one per tick, where you drop a task into the bucket for its due time and the consumer sweeps buckets as the clock advances. Inserting is `O(1)` and lock-free-ish. The catch is the array. Xapiand schedules things up to twenty-four hours out, and it wants millisecond resolution. A flat array covering 24 hours at 1 ms is 86.4 million buckets, preallocated, mostly empty, sitting in memory forever on the off chance you schedule something for tomorrow afternoon. That is absurd for a structure whose whole point is to hold a handful of pending fsyncs.

So the constraints are: insert without locking, and don't preallocate a continent of empty buckets you will never use. stash is the answer to both at once.

## A sparse store of atomic pointers

The trick is to make the wheel's backing store *sparse* and *lazily grown*, and to make every growth step a lock-free compare-and-swap.

The primitive, `Stash<T>`, is a chunked array of `std::atomic<T*>`. It starts tiny. When a producer needs a slot that doesn't exist yet, it doesn't take a lock to extend the array. It allocates a new chunk, then tries to publish that chunk by `compare_exchange` into an atomic pointer that was null. If it wins, the slot is live and points at its chunk. If two producers race for the same missing slot, both allocate, both attempt the swap, and exactly one wins. The other one's `compare_exchange` fails, it sees that someone beat it, and it quietly deletes the chunk it just made.

That is the whole lock-free insert, and it is where the title comes from. **Loser deletes.**

```cpp
// the heart of it: grow a slot without ever taking a lock
std::atomic<T*>& slot = /* (key / Div) % Mod, materialized lazily */;
T* expected = nullptr;
T* fresh = new T(/* ... */);
if (!slot.compare_exchange_strong(expected, fresh)) {
    delete fresh;   // someone else published first: the loser frees its own work
}
```

No mutex appears anywhere on the producer side. A hundred threads can be growing different parts of the structure at the same moment, and the only cost of a collision is one wasted allocation by whoever lost the race. The array materializes only where there is actually something to hold, so the 86-million-bucket continent never gets built. You pay for the slots you use.

There is a diagram in my head every time I read this code, and it is just two hands reaching for the same empty drawer:

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

`Stash<T>` is just the sparse store. To turn it into a timer wheel you nest it.

`StashSlots` is a keyed level: a key maps to slot `(key / Div) % Mod`, and the value at each slot is itself a `Stash`, so levels stack to give coarse-to-fine resolution. At the bottom is `StashValues`, an append-only list of the actual tasks with an atomic write cursor, so producers append to a bucket lock-free too. Xapiand's scheduler keys on nanoseconds since the machine booted and stacks four `StashSlots` over one `StashValues`:

```text
key (ns)  ─►  4800 × 18s  ─►  36 × 500ms  ─►  10 × 50ms  ─►  50 × 1ms  ─►  task list
              └─ 4800 × 18s = 86,400s = exactly 24 h, addressed all the way down to 1 ms
```

A task due in three minutes lands in the right 18-second slot, then the right 500 ms slot inside it, then 50 ms, then 1 ms, then onto the list at the leaf. Only the path it touches gets allocated. The wheel is twenty-four hours wide and almost entirely made of nothing.

The consumer walks a key window in one of three modes, and they are the nicest part of the API. *Walk* drains everything due now and runs it. *Peep* looks ahead at the soonest upcoming task without touching anything, so the scheduler thread can compute exactly how long to sleep. *Clean* garbage-collects slots that have been emptied and aged out, chasing the walk cursor without ever colliding with it. One mutex, one condition variable, a lock-free queue, and a thread that mostly sleeps. That is the entire scheduler.

## Who rides it

stash never appears in Xapiand by name in the places that matter. It hides under two front doors.

The first is the **logger**. Xapiand's logging runs on its own dedicated thread, and a surprising amount of logging is *scheduled* rather than immediate: error-level messages, delayed lines, the "log this now but unlog it if the operation finishes cleanly within 200 ms" pattern that keeps the console quiet during normal operation and loud during a stall. Every one of those is a cancellable task on a `stash`-backed scheduler, and the cancel is a single atomic store.

The immediate lines, the ones with no delay at all, never reach the wheel. They run inline on the thread that logged them. Only the *scheduled* lines land on `stash`, and that split matters more than it looks, because it means the structure never sees a mob of threads all converging on the same instant. Every key it gets sits somewhere in the future, spread across a delay window, which is exactly the shape its slots want. The one access pattern that would hurt it is routed around it by construction, and that is a large part of why it holds up.

The second is the **debouncer**. Xapiand debounces almost every background side effect: the asynchronous fsync, the database committers, the `DB_UPDATED` multicast on the discovery layer, the schema and settings updaters. Debouncing means rapid repeated touches of the same key collapse into one eventual call, with a throttle floor and a randomized force-window so a key that is touched forever still fires eventually and a thundering herd of due keys gets spread across time instead of all firing at once. Here stash sits one layer down, not on the front line. The collapse itself runs under a small mutex on a hash map, because deciding whether a key already has a firing pending means looking it up and replacing it, and most touches return right there without scheduling anything new. What comes *out* of the collapse, the firings that actually survive, is far less traffic than the raw touches, and the force-window scatters them across the future on purpose. Those surviving, time-scattered firings are what land on the wheel. So the debouncer is not stash swallowing a firehose. It is something upstream shaping the firehose into exactly the spread-across-the-future key pattern the wheel is happiest with, which is the same thing the logger does by running its immediate lines inline. Both of stash's front doors hand it the workload it is good at and keep the workload it is bad at away from it.

## The catches, kept in

I called stash the best thing in the codebase. I did not call it safe to grab without reading the label, and the honest part of this post is the label.

It is **lock-free on the producer side, single-consumer on the walk side**, by contract. Many threads insert; exactly one thread walks. That asymmetry is the whole reason the inserts can be so cheap, and it is a real constraint, not a soft suggestion. Point two consumers at it and the carefully lock-free machinery turns into undefined behavior. The README says so in bold, and I left it in bold.

It **allocates on the hot path**. The lock-free insert calls `new`, and `new` can block in the allocator. So "lock-free" here means "never takes one of *our* locks," not "never waits on anything ever." For a scheduler that is fine. For a hard-real-time audio callback it is not, and you should know which one you are writing.

It has **no safe memory reclamation**. The consumer frees a node by swapping in null and deleting the old pointer, and that is correct only because there is exactly one consumer and the single-consumer invariant holds. There are no hazard pointers, no epochs, no RCU. Concurrent erase-and-read would be a use-after-free. The whole edifice rests on that one-walker rule.

It **moves contention, it does not remove it**. Against a heap behind a mutex the win is real and large: no producer ever blocks, parks, or waits on another. But lock-free is not contention-free, and there are two shared atomics the producer side keeps touching. The first is the pair of valid-key bounds: every insert nudges them through a compare-exchange loop, and since the clock only moves forward the upper bound gets rewritten on almost every add, however the keys are spread. The second is the leaf cursor: appends do a single `atom_end++`, and tasks landing in the *same* slot all bounce that one counter between caches. The saving grace is that the wheel's real workload spreads its keys across the future instead of piling them on one instant, so that second hotspot mostly stays cool. Both are non-blocking, which is categorically better than a contended lock: an atomic that retries still makes progress and never sleeps a thread. But this is not a hundred cores writing with zero coordination. Force every insert onto a single key and the wheel saturates right where those two atomics do, and a structure built for that workload will walk straight past it. The coordination did not vanish, it moved out of a mutex and into the cache traffic over a couple of atomics, where it is far cheaper but not free.

## The skip that makes it fast

A sparse structure that grows only where there is work sounds like it should be slow to *read*. If the wheel is twenty-four hours wide and almost all of it is empty, walking it ought to mean scanning across an ocean of nothing to reach the few slots that matter. It doesn't, and the reason is the one piece of bookkeeping I have not mentioned yet.

The structure carries a pair of atomic bounds: the first and last keys that currently hold anything, threaded through the walk context alongside the key window. The consumer never scans the empty stretches. It jumps from the first live key to the last and ignores everything in between. Sparse buys cheap memory; the bounds buy a cheap walk on top of it. That pairing is the real trick, more than the lock-free insert on its own. The wheel can be enormous and almost entirely empty, and a sweep still touches only the handful of slots that hold tasks, because it is told exactly where they begin and end.

It is also what keeps the consumer honest about its one job. The walk doesn't hunt; it follows the bounds, drains what is due, advances the lower bound past the drained range, and goes back to sleep. The clean pass chases behind it, recycling emptied slots, and the two cursors never collide because there is only ever one of each.

## When the wheel wins

So where does it stand against the things you would actually reach for today?

The bones first, so the comparison is fair. stash inserts in `O(1)` amortized and lock-free, drains in `O(1)` amortized per fired task, and holds `O(n)` memory in the number of *live* tasks, not the width of the wheel. A binary heap is `O(log n)` per operation and orders exactly, but every insert serializes on its one lock, so under a crowd of producers it is really `O(p log n)` of waiting. A flat timer wheel matches the `O(1)` insert but pays `O(range / resolution)` memory up front, the 86-million-bucket continent. A lock-free queue is `O(1)` and scales better than any of them, but it has no notion of *when* and cannot tell you what is due. The asymptotics are close; what differs is which of those costs you actually pay. stash is built to pay none of the ones that hurt at scale: no lock, no preallocated continent, memory only for what is live, in trade for slot-quantized time instead of an exact order and a single consumer on the drain.

A binary heap behind a mutex, `std::priority_queue` and a lock, is the textbook scheduler and the right answer most of the time. It orders arbitrary times exactly, it is `O(log n)`, and it is a dozen lines. Use it. stash only starts to pull ahead when the insert rate from many threads turns that one mutex into the hottest lock in the process, and when you can live with time quantized into slots rather than ordered to the nanosecond. Below a handful of producers the heap is simpler and just as quick, and the lock never heats up enough to matter. I measured the crossover. With a dozen threads dropping timed tasks at once, the wheel and the heap reach roughly the same insert throughput, but they get there by opposite means: the heap hits its number by making producers queue behind its one lock, so its tail insert latency ran about ten times the wheel's. The wheel's producers never wait on each other, so a slow insert stays a slow insert instead of becoming a stall. That tail, not the average, is the reason to reach for it.

A lock-free queue, [moodycamel's `ConcurrentQueue`](https://github.com/cameron314/concurrentqueue) and its kin, is a lovely piece of engineering and the wrong shape for this. It is a queue: first in, first out, no notion of *when*, no way to ask for everything due before a deadline. For a hand-off channel it is the better tool, and not by a little. I benchmarked a queue that gives each producer its own shard against the wheel on pure many-to-one hand-off, no ordering, just moving items between threads, and it scaled almost linearly with cores while the wheel flattened out at the ceiling of its two shared atomics. That is exactly why Xapiand runs its immediate log lines inline and only ever hands the *scheduled* ones to the wheel: a queue is the right tool for work with no *when*, and the wheel is the right tool for work that has one. Neither replaces the other, because a queue cannot answer "what is due now."

[Asio](https://github.com/chriskohlhoff/asio)'s timer service is the grown-up general answer, and if I were wiring up async I/O today I would reach for it without thinking. It composes with executors and coroutines, it is hardened by a decade of use, and it keeps more careful per-timer bookkeeping than stash does. That bookkeeping is the cost: its timer queue was not built to swallow a firehose of inserts arriving from arbitrary threads at once. stash wins in one narrow place and only there. Thousands of timed events a second, dropped in from every thread in the process, drained by a single owner, where the insert has to be nearly free and you do not care that two events landing in the same millisecond come back out in some arbitrary order.

The hierarchical timing wheel underneath all of this is the one everyone uses; Varghese and Lauck wrote it up in 1987 and I am not claiming to have invented the wheel. The difference is only the backing store: the sparse, lock-free, atomic-pointer array in place of fixed per-level arrays. That single substitution is the whole contribution, and it is enough.

The honest rule is short. Reach for stash when you are bucketing values by an integer key, usually a clock tick, with many producers and one consumer, draining in key order, and pointer-like values suit you. Reach for something else the moment any of that stops holding: concurrent consumers, exact ordering, arbitrary value types, a general-purpose map or queue, or a path where you cannot afford the `new` on insert. It does one job, and inside its envelope I have not found anything that does that job for less.

## Why it is worth keeping

I pulled fifteen-odd libraries out of Xapiand this season: a perfect-hash, a constexpr string toolkit, a thread pool, a timer scheduler, an ISO-8601 parser, a reflective enum. Most of them are good, honest, useful code, and most of them are also things you could replace with something the standard library or a well-known dependency already does better. A thread pool is `std::jthread` and a real queue. Strict numeric parsing is `std::from_chars`. Those extractions are worth doing because they shrink the project and make the pieces reusable, not because the world was missing them.

The scheduler I would have put on that same list, and I would have been wrong. *A scheduler is an [Asio](https://github.com/chriskohlhoff/asio) timer*, I assumed, until I benchmarked it. Asio's `steady_timer` is genuinely faster than the wheel when one or two threads arm it, and then it falls off a cliff: point eight or fourteen threads at it, all arming timed work at once, and every arm serializes on the `io_context`'s lock until throughput drops *below* its single-threaded number. On that same load the stash-backed scheduler ran several times faster with a fraction of the tail latency, and kept scaling. So the scheduler is not replaceable for the load Xapiand actually puts on it. But it is not a second novel idea either. It is just stash wearing a different hat, and its one good trick is the wheel underneath.

stash is the exception, then, the only genuinely new idea in the pile. The others are clean implementations of problems plenty of people have solved well, and the language keeps catching up to them, which is fine. This one I have not seen done elsewhere, and that idea is the thing worth lifting out and handing to a stranger.

So it is its own box now: [github.com/Kronuz/stash](https://github.com/Kronuz/stash), one header, depending on three standard includes, with the label written honestly on the front. Lock-free producers, single consumer, allocates on insert, drop a pointer-like value keyed by a clock tick and drain it in order. If you are building a scheduler, a timer wheel, a debounce or coalescing table, a deadline tracker for a few hundred thousand in-flight requests, a retry-with-backoff queue, a sliding time-window of counters, anything where many threads arm timed work and a single thread fires it, and you want the insert side to disappear into the noise no matter how many threads are hammering it, this is the strange little thing for the job.

It started life as the reason one thread in a search engine could afford to sleep. It deserves a wider audience than that.

## How this was measured

The claims above come from a small harness that builds the real `stash.h` wheel with Xapiand's exact four-level configuration and runs it against the alternatives under the two patterns that actually occur: keys spread across a delay window, the real deferred-log and timer pattern, and keys all converging on `now`, the pathological case. Apple M4 Pro, ten performance cores and four efficiency, AppleClang 17 at `-O3`, one consumer draining concurrently, best of three runs.

One caveat, because it changes how to read the numbers. The harness lets the pending set grow to millions of entries, which inflates the heap's `O(log n)` at low thread counts more than a real scheduler ever would. So the signal to trust is the tail latency and the *shape* of the scaling, not the single-threaded throughput. The heap's real problem is not its `log n`, it is that every producer waits behind one lock, and that is what the `p99` column shows and what makes Asio's throughput run *backwards* as threads pile on.

The scheduler comparison: many threads arming timed tasks with keys spread across a 100 ms window, one consumer firing them.

| scheduler, spread keys | 1 thread | 8 threads | 14 threads | p99 at 14 |
| --- | --- | --- | --- | --- |
| stash | 2.2 | 5.2 | 6.1 | 4.5 µs |
| heap behind a mutex | 2.7 | 4.7 | 5.1 | 40 µs |
| `asio::steady_timer` | 2.7 | 1.5 | 1.5 | 59 µs |

Throughput in million arms per second, higher is better. Asio is the quickest of the three with one or two threads and the slowest by far once a handful contend, arming slower than it does single-threaded. The full harness, the data-structure panel (stash against a mutex deque, a lock-free Vyukov queue, and a per-producer sharded queue), and the complete tables are in the [repo](https://github.com/Kronuz/stash/tree/main/bench).
