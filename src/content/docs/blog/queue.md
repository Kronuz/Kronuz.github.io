---
title: "Sometimes a Mutex Is Right"
subtitle: "A blocking channel that is not trying to be fast, only correct, with timeouts and a shutdown that actually drains."
description: "queue is a thread-safe, bounded, blocking, double-ended MPMC queue built on a std::mutex, two condition variables, and a std::deque. It is deliberately not lock-free: it is the queue you reach for when you want a blocking channel with per-operation timeouts (negative blocks forever, zero is non-blocking, positive waits) and a clean two-stage shutdown, where end() stops new pushes but lets consumers drain what is left and finish() wakes every waiter and rejects everything. It pays a mutex on purpose, because the things it is good at, blocking with timeouts and an orderly teardown, are exactly the things lock-free queues make painful."
excerpt: "After a chapter of lock-free structures that avoid mutexes at all costs, here is the honest counterweight: a queue that reaches straight for one. The twenty-third familiar is not chasing throughput. It is chasing the two things fast queues are bad at, waiting with a timeout and shutting down without losing or hanging on the items still in flight, and for those, a mutex and two condition variables are simply the right tool."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 23
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one reaches for a mutex on purpose: [queue](https://github.com/Kronuz/queue).*

This series has spent a whole chapter on structures that go to real lengths to avoid a lock: a [timer wheel](/blog/the-sparse-wheel/) whose insert never stalls, an [atomic shared pointer](/blog/atomic-shared-ptr/), the shared-nothing loops of the [reactor](/blog/reactor/). So it is worth saying the honest thing out loud: **most of the time, a mutex is the right tool**, and pretending otherwise is how you ship a subtle bug in pursuit of a benchmark nobody was measuring. [queue](https://github.com/Kronuz/queue) is the familiar that reaches straight for one, without apology, because what it needs to be good at is not throughput.

It is a thread-safe, bounded, blocking, double-ended multi-producer/multi-consumer queue, built on a `std::mutex`, two `std::condition_variable`s, and a `std::deque`. Push and pop at either end; a push blocks when the queue is full; and it is the queue you reach for when you want a **blocking channel** between threads and you are happy to pay a lock for correctness.

## The parts a lock-free queue makes hard

The feature set is the whole point, and it is precisely the set of things lock-free queues are bad at.

**Waiting, with a timeout.** Every push and pop takes an optional timeout in seconds: negative means block forever, `0` means try once and give up immediately, a positive value waits up to that long and then returns empty-handed. This is trivial with a condition variable, a producer waits on "not full," a consumer waits on "not empty," and a timed wait is built in, and it is genuinely awkward to do well without one, because "sleep until there is room, but no longer than 200 ms" is exactly the kind of blocking a lock-free structure is designed to never do. The two separate condition variables are what let a full-queue waiter and an empty-queue waiter each sleep on their own condition and be woken only when it is their turn.

**Shutting down without losing or hanging.** It has a two-stage graceful shutdown, and the two stages matter. `end()` stops accepting new pushes but lets consumers keep draining what is already in the queue, so you can retire a producer and still process the backlog it left. `finish()` is the hard stop: it wakes every thread blocked in a wait and rejects all further operations, so nothing is left asleep forever. Getting shutdown right, no lost items, no thread parked on a condition that will never be signalled again, is one of the genuinely tricky parts of any concurrent queue, and doing it under a mutex with condition variables is clear and correct in a way the lock-free version simply is not.

## The lesson worth keeping

The right reading of this familiar next to its lock-free neighbors is not "one of these is better." It is that the tool follows the requirement. When the requirement is a flat tail under contention on a hot path, you pay for something like the [wheel](/blog/the-sparse-wheel/). When the requirement is a blocking channel with timeouts and a clean shutdown, you pay a mutex and get code you can actually reason about. Reaching for lock-free reflexively, where you did not need it, buys you nothing and costs you clarity. The engineering is in matching the two.

## Where it fits

Reach for it when you want a bounded blocking channel between threads with timeouts and an orderly shutdown: a work handoff, a bounded pipeline stage, a request queue with back-pressure. Skip it when you truly are on a contended hot path where the mutex's tail latency shows up (then measure, and consider a lock-free queue), or when you never block and never shut down and a lighter structure will do.

The next familiar is the thing that sits on top of a queue just like this one and turns it into useful work: a pool of worker threads, and the small, reusable primitives it is built from.
