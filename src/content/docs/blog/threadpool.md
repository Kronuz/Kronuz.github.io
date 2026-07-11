---
title: "The Pool and Its Parts"
subtitle: "A fixed-size worker pool, and the thread primitives it hands you so you can build your own."
description: "threadpool is a small, dependency-free C++20 fixed-size worker pool: construct it with a name format and a thread count, then hand it work three ways, fire-and-forget enqueue, bulk enqueue_bulk, or call-and-await-result async that returns a std::future. Each worker is a long-lived thread pulling tasks off a shared blocking queue. It is the pool Xapiand uses for its servers, indexers, and background work, and it ships the layers underneath it: a Thread CRTP base that turns any class with name() and operator() into a runnable joinable thread, a one-shot TaskQueue of packaged_tasks, and the mutex-backed concurrent queues the pool sits on, so you can build your own concurrency on the same parts."
excerpt: "A thread pool is the least surprising thing in a concurrent codebase, which is exactly why it is worth getting plainly right rather than cleverly wrong. The twenty-fifth familiar is a straightforward fixed-size pool with three ways to submit work, and the quietly useful part is that it comes unbundled: the CRTP thread base, the task queue, and the blocking queues underneath are all exposed, so you can assemble your own."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 25
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is the plainest of the concurrency crew, and useful for it: [threadpool](https://github.com/Kronuz/threadpool).*

Every server needs the same thing eventually: a set of worker threads that stay alive and chew through tasks handed to them, so that a slow or blocking piece of work does not tie up the thread that produced it. A thread pool is the least exotic component in a concurrent system, and that is precisely why it should be plain and correct rather than clever. [threadpool](https://github.com/Kronuz/threadpool) is exactly that plain thing: a fixed-size pool of long-lived workers, each pulling tasks off a shared blocking queue and running them until the pool is told to finish. It is the pool Xapiand runs its HTTP and binary servers on, its document indexers and preparers, and its background chores.

You construct it with a worker-name format and a thread count, and hand it work three ways, which cover essentially everything you want from a pool:

- **`enqueue`**, fire-and-forget: run this, I do not care when or what it returns.
- **`enqueue_bulk`**, the same for a batch of tasks at once.
- **`async`**, call-and-await: run this and hand me back a `std::future` for its result, so I can go do other work and collect the answer later.

That is the whole surface, and it is deliberately unremarkable. The value of a pool is that it is boring and does not surprise you at three in the morning.

## Unbundled on purpose

The part worth pointing at is that threadpool does not just hand you the pool as a sealed box; it ships the **layers it is built from**, each usable on its own. That is a small decision with an outsized payoff, because "I need *almost* a thread pool, but with one different behavior" is a situation you hit constantly, and a sealed pool leaves you rewriting it from scratch. Here the parts are on the table:

- **`Thread<Impl, policy>`** is a tiny CRTP base that turns any class with a `name()` and an `operator()` into a runnable, joinable thread. Want one long-lived named thread that is not part of a pool? Use this directly.
- **`TaskQueue`** is a one-shot queue of `std::packaged_task`s you drain by calling them with arguments, the primitive behind "callbacks waiting on a condition."
- **`ConcurrentQueue`** and **`BlockingConcurrentQueue`** are the mutex-backed queues the pool sits on, cousins of the [blocking queue](/blog/queue/) from last post.

So the pool is an *assembly* of named threads over a blocking queue, and because the assembly is exposed, you can build a different one: a single worker, a priority variant, a pool with custom lifecycle, all from the same tested pieces instead of a fresh hand-rolled thread and a fresh hand-rolled queue with fresh hand-rolled shutdown bugs. Shipping the primitives, not just the product, is what turns a library from a thing you use into a thing you build with.

## Where it fits

Reach for it when you want a straightforward worker pool with fire-and-forget, bulk, and future-returning submission, or when you want the thread-and-queue primitives to compose your own. Skip it if your runtime already owns task scheduling (an async framework, a coroutine executor), or if a single `std::async` or `std::jthread` covers your whole need.

That closes the lock-free chapter, and nearly closes the campaign. The last familiars are a different kind of magic: the ones that do their work before the program ever runs, at compile time.
