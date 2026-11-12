---
title: "Who Owns the Wheel"
subtitle: "Why stash and scheduler retire, and what replaces them."
description: "stash, the lock-free timer wheel from Xapiand, and scheduler, the library on top of it, are being retired. Measured on the timers my systems actually run, which are re-armed and cancelled far more often than they fire, a single-owner wheel with a striped inbox costs 3.6 to 30 times less per timer and 9 to 17 times less per arm from another thread. Where stash's time goes, how the new wheel library works inside, and what stash still does better."
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

I am retiring [stash](https://github.com/Kronuz/stash) and [scheduler](https://github.com/Kronuz/scheduler). Measured on the timers my systems run today, a timer wheel owned by one thread costs **3.6 to 30 times less** per timer than stash, and with a striped inbox for other threads it arms **9 to 17 times cheaper** than stash does from those threads, with no allocation at all. The replacement is a new library, [wheel](https://github.com/Kronuz/wheel). This post is how I got there, what is inside the new wheel, and what stash still does better.

## The table I wrote myself

In [The Sparse Wheel](/blog/the-sparse-wheel/) I called stash the strangest, best thing in Xapiand, the familiar I would keep if I could keep only one. I meant it. Its insert never waits on another insert, so fourteen threads can arm timers while one thread drains them, and the tail stays flat where a locked heap spikes.

That post also had a table of when to reach past stash. Two of its rows were timers owned by one event loop, and timers that are usually cancelled or moved, because stash cannot take a timer back out.

Then I started building [Detent](https://github.com/Kronuz/Detent), and its timers are almost all of that kind. A consensus heartbeat re-arms every follower's election timer, every time. A request deadline is armed and then cancelled when the request finishes first, which is nearly always. A debounced fsync is pushed back again and again before it fires once. Nothing was broken; the old shape simply never had to carry this load. Before choosing a wheel for the new system, I measured whether my favorite familiar still won on it.

## Why stash cannot take a timer back

To see where the time goes, it helps to remember how stash files a timer. Xapiand's wheel is four nested levels over a leaf, keyed on nanoseconds: 4,800 slots of 18 seconds, then 36 of 500 milliseconds, 10 of 50 milliseconds and 50 of one millisecond. Each level maps a key to slot `key / Div % Mod`, and a slot holds the next, finer level, allocated by whichever producer touches it first with a compare-and-swap (the loser frees its copy). At the bottom, the leaf is an append-only array: a producer claims the next index with one fetch-add on the leaf's cursor, then swaps its value into the claimed cell.

Append-only is what makes it lock-free, and it is also why nothing can come back out. Removing a value from the middle of a leaf means changing a cell that another producer may be claiming next to, and freeing it means knowing that the consumer is not reading it. stash avoids both questions by never removing anything. A cancel clears a flag on the task. A re-arm clears the flag and files the task again at its new deadline. The old filing stays where it was, a *stale filing*, until the walk reaches that slot, checks the flag and the deadline, and drops it. Its memory is freed only when the cleaner passes the slot.

For timers that mostly fire, that is cheap. For timers that are re-armed on every heartbeat, every re-arm is a new filing and a future visit.

## How it was measured

Six candidates went into one harness with one interface: arm, cancel, expire, and arm from another thread where the candidate allows it.

1. A single-owner prototype wheel: 4,096 slots of one millisecond, a 32-byte entry that lives inside the object that owns the timer, and only the owner thread touching it.
2. stash as it is, in Xapiand's four-level configuration, with raw entry pointers as values.
3. stash with a new leaf that stores the entry in its cell and keeps a back-pointer from the entry, so a cancel is one exchange and the walk never sees a cancelled entry. This was the fair test: a stash fixed for exactly this workload.
4. The prototype with one shared lock-free inbox for other threads.
5. The same inbox, threaded through the entry's own link so the entry stays 32 bytes.
6. That inbox split into 64 stripes, one cache line each.

The workload runs one entry's whole life on a manual clock, deadlines spread uniformly over two seconds: arm every entry, re-arm every entry, cancel every entry, then arm them all again and expire in one-millisecond steps until the last one fires. The decision rule was written and committed before the first measured run: one shape wins only if it is within 10% of the best on that single-loop path and within 10% of stash on stash's own cross-thread path.

Every number came from a job that had the machine to itself, with paired same-code runs to show the noise, on a 16-thread Intel laptop under macOS and again in a Linux VM. Every candidate first matched a reference model and passed the cross-thread tests under AddressSanitizer and ThreadSanitizer. The full record, with job ids, is Detent's [wheel evidence](https://github.com/Kronuz/Detent/blob/main/docs/design/wheel-evidence.md).

## Where stash's time goes

This table gives the median nanoseconds per entry for that whole life on macOS, at a thousand and at a million live entries, and the ratio to the best candidate.

| Candidate | 1,000 entries | ratio | 1,000,000 entries | ratio |
|---|---:|---:|---:|---:|
| owner-only prototype | 37.3 | 1.00 | 352.7 | 1.06 |
| stash as is | 1,106 | 29.7 | 1,201 | 3.60 |
| stash, fixed leaf | 857 | 23.0 | 594 | 1.78 |
| prototype, 64-stripe inbox | 44.4 | 1.19 | 333.3 | 1.00 |

Most of stash's cost sits in expire: **835 nanoseconds per entry** at a thousand entries and 863 at a million, because the walk visits every stale filing the re-arms and cancels left. Arming is the smaller part, 80 to 213 nanoseconds for stash against 5 to 7 for the prototype at a thousand entries. At a million, the prototype's arm rises to about 100 nanoseconds, and that is the memory system rather than the wheel: the entries are visited in random order, so each one is a cache miss.

The fixed leaf confirms the diagnosis and then shows a second cost. With nothing left behind, its expire drops to 157 nanoseconds at a million entries, close to the prototype's 106. At a thousand entries it still costs 664 nanoseconds per entry, because stash walks all four levels on every tick, and with only a thousand entries over two seconds most of those visits find nothing.

Then there is the heap. stash allocates as it files (a box per value, slots, leaves, level nodes) and frees only when the cleaner passes, so each re-arm costs **101 bytes** of heap at a thousand entries and 27 at a million until the old deadline goes by. The prototype allocates nothing, ever. Its fixed cost is 64 KiB of slot heads, which is 98 bytes per entry at a thousand entries and 32 at a million, against stash's 269 and 44.

## The surprise: stash was right about sharing

The cross-thread run is stash's home ground: 1, 4 or 14 producer threads each arm their share of two million entries, and one owner fires them. This table gives each producer's cost per arm in nanoseconds.

| Candidate | 1 producer | 4 producers | 14 producers |
|---|---:|---:|---:|
| stash as is | 157 | 196 | 292 |
| stash, fixed leaf | 126 | 158 | 216 |
| one shared inbox | 15 | 267 | 1,379 |
| 64-stripe inbox | 13.6 | 11.6 | 32.6 |

The shared inbox is the row that taught me something. With one producer it is ten times cheaper than stash. With fourteen it is **almost five times worse**, because its head is one cache line and every push is a compare-and-swap on it. Fourteen cores fighting over one line spend their time passing it around, and every failed swap costs another round trip. stash spreads its producers over many slots and many leaves, and that instinct was correct.

Splitting the inbox into 64 stripes gives each producer thread its own head on its own line, so the swap almost never fails and the line almost never moves. At fourteen producers that is 32.6 nanoseconds against stash's 292. The Linux VM agreed: at one, four and seven producers the striped wheel cost 8%, 4% and 5% of what stash did.

## Inside the new wheel

The winning shape became [wheel](https://github.com/Kronuz/wheel), one C++20 header with no dependencies. The diagram puts the two designs side by side.

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

### The entry

Every timer is this struct, embedded in whatever owns the timer, so the wheel never allocates.

```cpp
struct timer_entry {
	timer_entry* next = nullptr;    // the slot's list, or the inbox while a remote arm waits
	timer_entry** pprev = nullptr;  // the pointer that points here; null while unarmed
	std::uint64_t deadline = 0;     // nanoseconds on the wheel's clock
	void (*fire)(timer_entry&, bool expired) noexcept = nullptr;
};
```

The interesting field is `pprev`. It points at whatever points to the entry: a slot's head, the previous entry's `next`, or the head of the due list. Unlinking is then the same three stores wherever the entry is, with no search and no need to know which slot it is in, and "is it armed" is just `pprev != nullptr`. That is what makes cancel and re-arm cost a few nanoseconds instead of a filing and a future visit.

### The levels

Level 0 is 4,096 slots of one millisecond, the next 4.1 seconds from the cursor. Above it sit six levels of 64 slots, each slot 64 times wider than a slot of the level below: 4.1 seconds, 4.4 minutes, 4.7 hours, 12.4 days, 2.2 years and 142 years. Every 64-bit nanosecond deadline has a slot.

Filing is a few shifts. A deadline in the current round goes in level 0 at `tick & 4095`. A farther one goes in the lowest upper level whose 64 slots reach it, found with at most six comparisons, at slot `(tick >> shift) & 63`, where the shift grows by six bits per level. Every head, level 0's and the upper levels', lives in one array, with one occupancy bit per slot in a parallel array of 64-bit words. A slot's bit is set when something is linked into it and cleared when an unlink leaves it empty, which the unlink detects because `pprev` points inside the head array.

### Expire and cascade

`expire(now)` first files whatever other threads queued, then moves the cursor to `now`. If the cursor crossed into the span of an upper slot, that slot's entries are filed again relative to the new cursor, which puts each one at least a level lower. An entry moves at most once per level, six times in its life. stash walks its levels on every tick; the new wheel touches an upper level only at its span boundaries, so a million timers a day out cost a run of one-millisecond ticks nothing.

Then it walks the level 0 slots the cursor passed, skipping empty ones by their bit, and moves every due entry to a detached list in slot order before any fire runs. Detaching first is what lets a fire cancel or re-arm any entry, itself included: a re-armed due entry simply leaves the list. An entry fires at most one tick after its deadline and never before.

### Sleeping until the next timer

A reactor wants one number: when to wake up. `next()` answers it from the bitmaps. For level 0 it scans the 64 words starting at the cursor, and `std::countr_zero` finds the first occupied slot in a word in one instruction; the answer is the end of that slot. For each upper level it rotates the level's one word to start at the cursor's slot and counts trailing zeros again; the answer is the start of that span, where those entries move down. The wheel never reads a clock, so a reactor feeds it `steady_clock` time and a simulator feeds it a counter and runs a day of timers in no time.

### The striped inbox

This is how a thread that is not the owner arms a timer, abridged from `wheel.hh`.

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

The push threads the entry through its own `next`, which is unused while the entry is unarmed, so the inbox needs no node and the entry stays 32 bytes. Each thread takes a stripe from a counter the first time it arms, so up to 64 producers never share a head. Only the push that finds its stripe empty touches the shared word of stripe bits. The owner takes that whole word with one exchange, empties each marked stripe with one exchange of its head, and files the entries it finds. When the inbox is idle, all of this costs expire one relaxed load.

### The two rules

None of the wheel's own state is atomic, because only one thread ever touches it. That is a contract, and a Debug build asserts it on every call:

1. Only the owner thread arms, re-arms, cancels and expires.
2. Any other thread may arm an entry that is not armed, through the inbox; after that only the owner touches it.

When the owner re-arms or cancels an entry that is not armed yet while the inbox holds something, it drains the inbox first, so an entry another thread just armed is re-armed or cancelled exactly.

## What stash still does better

Rule 2 is the honest cost, and the [logger](/blog/logger/) shows it. The logger arms a "this is taking too long" line on every operation and cancels it from the worker thread when the operation finishes, which is almost always. On stash that cancel was one compare-and-swap from any thread. On the wheel a worker cannot cancel; it sets a flag that the fire checks, and the entry stays filed until its deadline.

The logger has in fact already left stash's wheel: since November it writes each thread's lines into a queue of that thread's own and keeps deferred lines in a heap on its LOG thread, and it takes only a cancellable task type and a thread wrapper from scheduler. A first attempt to put it on the wheel found that the wheel's slots are last in, first out, so it wrote lines out of their thread's order, which the logger promises to keep. Its own queues and heap against the wheel is a measurement running now.

It is not the only open item.

- **Fire lag under a burst.** In stash the producers file their own timers; in the wheel the owner files every remote arm, about 100 nanoseconds each at that scale. When a million arms landed within ten milliseconds, the striped wheel's last fire came 4.3 milliseconds after its deadline at fourteen producers, against stash's 1.0.
- **The tail.** The Sparse Wheel's headline was stash's flat 99th-percentile insert. These runs measured medians, not the tail of a striped push.
- **One bound missed.** On macOS the striped wheel is 1.19 times the owner-only prototype at a thousand entries, over the 10% rule, because its re-arm costs 9.7 nanoseconds against 5.9. The noise band at that size is 31%, so the gap is small, but it is real and it is the new library's first job.
- **Stash's own best case.** A separate run is measuring stash where it should shine, fire-and-forget timers from many threads over a 24-hour horizon, under a rule written before it ran. If stash wins a use there by 10% or more, it keeps that use.

## Why scheduler goes too

Scheduler is stash's front door: a threaded scheduler, a debouncer and scheduled tasks, running stash-timed callbacks on threads. With an owned wheel, a debounce is one entry re-armed in place, which is the operation the wheel is cheapest at, and a callback runs on the loop that owns the wheel. Where something must fire while every loop is busy, a small thread owns a wheel of its own. Keeping scheduler beside that would mean two ways to do one thing.

## Before anything is archived

Retirement has three conditions, and nothing is archived until all three hold.

1. The replacement is its own library, which wheel is. My task library and Xapiand will depend on it rather than carry a copy.
2. It is measured better on every current use: Xapiand's fsync and manager debouncers each with its own before-and-after, and for the logger, whichever of its own queues or the wheel measures better.
3. Nothing uses stash or scheduler. A search across every one of my repositories comes back empty, and only then are the two archived.

This one stings a little. I wrote stash by hand, over a long time, and it was a good answer to the question it was built for: many threads schedule, one fires, and nobody may block. The new wheel keeps both of its best ideas, nested levels of slots and producers that never wait on each other. What it drops is the shared structure everyone writes into, because the question changed: the owner re-arms constantly, and the owner should not have to pay for sharing.
