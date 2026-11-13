---
title: "Who Owns the Wheel"
subtitle: "Why stash and scheduler retire, and what replaces them."
description: "stash, the lock-free timer wheel from Xapiand, and scheduler, the library on top of it, are being retired. On the timers my systems actually run, which are re-armed and cancelled far more often than they fire, the landed single-owner wheel costs 3 to 26 times less per timer than stash and arms 10 to 16 times cheaper from another thread. Where stash's time goes, how the wheel works inside, and what stash still does better."
excerpt: "Three months ago I wrote that stash was the familiar I would keep if I could keep only one. In the same post I wrote a table of when not to use it, and one of its rows was timers that are usually cancelled or moved. Then I built a system made almost entirely of those."
date: 2026-11-11
authors: kronuz
series: "Familiars"
seriesOrder: 30
tags:
  - familiars
  - cpp
  - concurrency
---

I am retiring [stash](https://github.com/Kronuz/stash) and [scheduler](https://github.com/Kronuz/scheduler). On the timers my systems run today, a timer wheel owned by one thread costs **3 to 26 times less** per timer than stash, and it arms **10 to 16 times cheaper** than stash does from other threads, with no allocation at all. The replacement is a new library, [wheel](https://github.com/Kronuz/wheel). This post is how I got there, what is inside it, and what stash still does better.

*Updated 2026-11-12: every number here is the landed library measured against stash, from [one record with its job ids](https://github.com/Kronuz/Detent/blob/main/docs/perf/wheel-vs-stash.md).*

## The table I wrote myself

In [The Sparse Wheel](/blog/the-sparse-wheel/) I called stash the strangest, best thing in Xapiand, the familiar I would keep if I could keep only one. I meant it. Its insert never waits on another insert, so fourteen threads can arm timers while one thread drains them, and the tail stays flat where a locked heap spikes.

That post also had a table of when to reach past stash. Two of its rows were timers owned by one event loop, and timers that are usually cancelled or moved, because stash cannot take a timer back out.

Then I started building [Detent](https://github.com/Kronuz/Detent), and its timers are almost all of that kind. A consensus heartbeat re-arms every follower's election timer, every time. A request deadline is armed and then cancelled when the request finishes first, which is nearly always. A debounced fsync is pushed back again and again before it fires once. Nothing was broken; the old shape simply never had to carry this load.

## Why stash cannot take a timer back

Xapiand's wheel is four nested levels over a leaf, keyed on nanoseconds: 4,800 slots of 18 seconds, then 36 of 500 milliseconds, 10 of 50 milliseconds and 50 of one millisecond. A slot holds the next, finer level, allocated by whichever producer touches it first with a compare-and-swap. At the bottom, the leaf is an append-only array: a producer claims the next index with one fetch-add, then swaps its value into the cell.

Append-only is what makes it lock-free, and it is why nothing can come back out. Removing a value from the middle of a leaf means changing a cell that another producer may be claiming next to. So stash never removes anything. A cancel clears a flag on the task. A re-arm clears the flag and files the task again at its new deadline. The old filing stays, a *stale filing*, until the walk reaches that slot, checks the flag and the deadline, and drops it.

For timers that mostly fire, that is cheap. For timers re-armed on every heartbeat, every re-arm is a new filing and a future visit.

## What was measured

The landed wheel and stash ran in one harness, on the same workloads, on a 16-thread Intel laptop under macOS (Linux was not measured). Every number is a median over interleaved rounds, each run in its own process, from a job that had the machine to itself, and stash runs against itself as a twin to show the noise. Both match a reference model and pass the cross-thread tests under AddressSanitizer and ThreadSanitizer. I quote a stash number only where both do the same work.

## Where stash's time goes

One repetition arms every entry, re-arms it, cancels it, arms it again and expires in one-millisecond steps until the last one fires. Only the whole life is the same work in both: stash's cancel is a flag and its cost moves to expire. This table is nanoseconds per entry for that whole life.

| Entries | stash | wheel | stash over wheel |
|---|---:|---:|---:|
| 1,000 | 1,110 | 42.0 | 26 |
| 1,000,000 | 1,231 | 407 | 3.0 |

Most of stash's cost sits in expire: **871 nanoseconds per entry** at a thousand entries and 849 at a million, because the walk visits every stale filing, about two of every three it meets. The wheel's expire touches only live entries and costs 23 and 107.

At a thousand entries everything fits in cache and the wheel arms in 6.2 nanoseconds where stash takes 134. At a million both are bound by cache misses on entries visited in random order, and an arm costs 141 against 180.

Then there is the heap. stash allocates as it files and frees when the cleaner passes, so each re-arm costs **101 bytes** of heap at a thousand entries and 27 at a million. The wheel allocates nothing per entry. Per entry, with its own 32 bytes, it holds 98 bytes at a thousand entries against stash's 269, and 32 against 44 at a million.

## Arming from other threads

The cross-thread run is stash's home ground: 1, 4 or 14 producer threads arm a million entries while one owner fires them. This table gives each producer's cost per arm in nanoseconds.

| Producers | stash | wheel |
|---|---:|---:|
| 1 | 148 | 14.8 |
| 4 | 199 | 12.1 |
| 14 | 307 | 31.8 |

stash was right that producers must not share one point: it spreads them over many slots and leaves. The wheel's inbox does the same. One shared head would make every push a compare-and-swap on a single cache line, so the inbox is 64 stripes, one line each, and every producer thread has a head of its own.

For timers that are only filed and forgotten, a million keys spread over 24 hours, insert plus drain costs the wheel 211 to 239 nanoseconds per key against stash's 2,237 to 3,315, and holds 32 bytes per key against 382.

## Inside the wheel

[wheel](https://github.com/Kronuz/wheel) is one C++20 header with no dependencies. The diagram puts the two designs side by side.

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

Every timer is this struct, embedded in whatever owns the timer, so the wheel never allocates.

```cpp
struct timer_entry {
	timer_entry* next = nullptr;    // the slot's list, or the inbox while a remote arm waits
	timer_entry** pprev = nullptr;  // the pointer that points here; null while unarmed
	std::uint64_t deadline = 0;     // nanoseconds on the wheel's clock
	void (*fire)(timer_entry&, bool expired) noexcept = nullptr;
};
```

The interesting field is `pprev`. It points at whatever points to the entry: a slot's head, the previous entry's `next`, or the head of the due list. Unlinking is the same three stores wherever the entry is, with no search, and "is it armed" is just `pprev != nullptr`. That is what makes cancel and re-arm cost a few nanoseconds instead of a filing and a future visit.

Level 0 is 4,096 slots of one millisecond. Above it sit six levels of 64 slots, each slot 64 times wider than the one below, out to 142 years, so every 64-bit nanosecond deadline has a slot. Filing is a few shifts, and one bit per slot in a parallel array of 64-bit words marks the occupied ones.

`expire(now)` first files whatever other threads queued, then moves the cursor. When the cursor crosses into an upper slot, that slot's entries are filed again a level lower, so an entry moves at most six times in its life, and a million timers a day out cost a run of one-millisecond ticks nothing. Then it moves every due entry to a detached list before any fire runs, which is what lets a fire cancel or re-arm any entry, itself included. An entry fires at most one tick late and never early.

A reactor wants one number, when to wake up, and `next()` reads it from the bitmaps with `std::countr_zero`. A wake that jumps far ahead walks the occupied slots by bitmap word, at most 65 words, which cost 201.6 nanoseconds per wake against 264.4 for the bit-by-bit walk it replaced. The wheel never reads a clock, so a simulator feeds it a counter and runs a day of timers in no time.

This is how a thread that is not the owner arms a timer, abridged.

```cpp
void arm_remote(timer_entry& e, std::uint64_t deadline) noexcept {
	e.deadline = deadline;
	const unsigned s = stripe();  // this thread's stripe, chosen on first use
	auto& head = inbox_[s].head;  // one cache line per stripe
	timer_entry* first = head.load(std::memory_order_relaxed);
	do { e.next = first; }
	while (!head.compare_exchange_weak(first, &e, std::memory_order_release, std::memory_order_relaxed));
	if (!first) { queued_.fetch_or(std::uint64_t{1} << s, std::memory_order_release); }
}
```

The push threads the entry through its own `next`, so the inbox needs no node. Only a push that finds its stripe empty touches the shared word of stripe bits, and the owner takes that word with one exchange. None of the wheel's own state is atomic, because of two rules a Debug build asserts:

1. Only the owner thread arms, re-arms, cancels and expires.
2. Any other thread may arm an entry that is not armed, through the inbox; after that only the owner touches it.

## What stash still does better

Rule 2 is the honest cost, and it shows up in the measurements.

- **Cancel.** In stash a cancel is a flag clear: 0.66 nanoseconds against the wheel's 3.7 at a thousand entries, 5.9 against 28.8 at a million. The wheel pays a real unlink, and then has nothing stale to pay for later, which is why its whole life still wins. From another thread the wheel cannot cancel at all; it sets a flag the fire checks.
- **Fire lateness.** One expire that files a backlog of 0.3 to 0.9 million entries takes 4 to 5 milliseconds. A burst of arms at about 290 million a second outruns the owner's filing at about 110 million, so the inbox fills and drains in one pass. The worst fire is 0.21, 3.48 and 4.08 milliseconds at 1, 4 and 14 producers, against stash's 1.02, which is just its tick. Paced to stash's own rate of an arm every 100 to 300 nanoseconds there is no backlog and the worst fire is 0.2 to 0.9 milliseconds. Above about 110 million arms a second, stash fires less late.
- **A few small timers.** With a thousand fire-and-forget keys and one or four producers, the wheel's whole job costs 2.3 and 1.8 times stash's, because the loop wakes about once per key where stash drains with one walk. At fourteen producers stash's insert contention flips it, and the wheel costs 0.53 times as much.
- **Empty.** The wheel allocates 65,552 bytes at construction, and stash 9,248. A process with a handful of timers pays the difference.

These are medians, and I have not measured the tail of a striped push, which was The Sparse Wheel's headline for stash.

## Why scheduler goes too

Scheduler is stash's front door: a threaded scheduler, a debouncer and scheduled tasks, running stash-timed callbacks on threads. With an owned wheel, a debounce is one entry re-armed in place, which is the operation the wheel is cheapest at, and a callback runs on the loop that owns the wheel. Where something must fire while every loop is busy, a small thread owns a wheel of its own. Keeping scheduler beside that would mean two ways to do one thing.

## Before anything is archived

The [logger](/blog/logger/) is the first user to move. Its LOG thread now files deferred lines in a wheel it owns, where a worker's cancel stays the flag the line already carried.

Retirement has three conditions, and as of this update neither repository is archived.

1. The replacement is its own library, which wheel is. My task library and Xapiand will depend on it rather than carry a copy.
2. It is measured better on every current use: Xapiand's fsync and manager debouncers, each with its own before-and-after.
3. Nothing uses stash or scheduler. A search across every one of my repositories comes back empty, and only then are the two archived.

This one stings a little. I wrote stash by hand, over a long time, and it was a good answer to the question it was built for: many threads schedule, one fires, and nobody may block. The wheel keeps both of its best ideas, nested levels of slots and producers that never wait on each other. What it drops is the shared structure everyone writes into, because the question changed: the owner re-arms constantly, and the owner should not have to pay for sharing.
