---
title: "A Guest on the Loop"
subtitle: "Coroutines that pause, share a thread, and find their way home."
description: "task is a header-only C++20 coroutine library for code that runs on an event loop someone else owns, such as Asio or a reactor. A task starts only when awaited, resumes whoever awaited it without growing the stack, returns to the awaiter's own loop when it finishes on another, yields the loop when its time slice is spent, and can be cancelled mid-wait. Creating, awaiting and destroying one costs 9.2 nanoseconds on an Apple M4 Pro, and 20 million of them allocate nothing."
excerpt: "An event loop is one thread serving thousands of conversations, and it only works if nobody hogs it. The thirty-fifth familiar is the kind of function that knows how to step aside: it pauses, lets the loop serve someone else, and comes back to exactly where it left off, on exactly the thread it started on."
date: 2026-11-13
authors: kronuz
series: "Familiars"
seriesOrder: 35
chapter: "Lock-Free"
tags:
  - familiars
  - cpp
  - coroutines
---

*Part of [**Familiars**](https://kronuz.github.io/cpp-libraries/), my collection of standalone C++ building blocks. This one is how code takes turns on a shared thread: [task](https://github.com/Kronuz/task).*

Picture one waiter serving a whole restaurant. They take an order, hand it to the kitchen, and instead of standing there until the food is ready, they go take the next table's order. When a dish comes up, they carry it out and pick up where they left off.

That waiter is an **event loop**: one thread that serves thousands of network connections by never sitting idle on any one of them. It only works if the code it runs can say "I am waiting now, serve someone else, and come back to me here." A plain function cannot. Once called, it runs to the end, and if it waits for a socket, the whole thread waits with it.

A **coroutine** is a function that can. In C++20, writing `co_await` inside a function means "pause here." Its local variables are saved in a small block of memory called its *frame*, the thread goes off to do other work, and later something *resumes* the frame and the function continues from the next line. A waiter with a notepad.

[task](https://github.com/Kronuz/task) is my coroutine type for that, with one narrow job: run on a loop that belongs to somebody else, and be a good guest there.

## Why not just use what is there

C++20 gives you the language feature and no standard coroutine *type*, so every library brings its own. A naive one has three problems.

The first is the stack. When task A awaits task B and B finishes at once, B has to resume A, and the obvious way is to call A from inside B. Do that a million times in a loop and you get a million nested calls and a stack overflow.

The second is the thread. A program often runs one loop per core. If A runs on loop 1 and awaits B, which finishes on loop 2, a naive coroutine resumes A on loop 2, a thread it does not own, touching state loop 1 thinks is its alone.

The third is manners. A coroutine that computes for 50 milliseconds without pausing is a waiter reading a novel at one table while every other table waits.

[Asio](https://think-async.com/Asio/)'s own `asio::awaitable` handles some of this, but it is bound to Asio, and I wanted one type that scoring, storage and network code could all share.

## Handing over the baton

The fix for the stack is called **symmetric transfer**. Instead of B *calling* A, B's last act is to *return* A's handle, and the compiler turns that into a jump: B's frame is done, so A takes over its spot on the stack. A relay runner hands over the baton; they do not carry the next runner on their back. The tests run a million immediate awaits and a chain 100,000 tasks deep, and the stack never grows.

The gnarly part is that compilers disagree. Clang makes that jump at every optimization level; GCC only in optimized builds without sanitizers, and elsewhere it quietly makes a real call that recurses until the stack runs out. So on GCC, task uses a **trampoline** by default: a small per-thread queue where a finishing task drops the next handle, and a loop at the bottom of the stack that pops and resumes them one after another. Nothing nests, because every resume starts from the same floor. The [transfers note](https://github.com/Kronuz/task/blob/main/docs/mechanisms/transfers.md) has the details.

## Going home, taking turns

For the thread problem, task remembers which loop A was on when it awaited B. If B finishes on that loop, it hands the baton directly; if somewhere else, it posts A back to A's own loop. That is **executor affinity**: a task always comes home.

The loop itself is the host's. To task, a *scheduler* is anything with a `post` that queues a resumption and a `now` that tells the time; the library owns no queue and no threads. `task_asio.hh` provides one on a standalone Asio executor, and an inline one drives the tests.

For manners, there is the **budget**. A long loop takes a `task::budget` with a time slice, say 200 microseconds, and calls `co_await slice.checkpoint()` every few thousand iterations. While the slice lasts, a checkpoint costs one read of the CPU's cycle counter and never pauses. Once the slice is spent, it pauses and joins a queue of demoted work that the loop serves one entry at a time between everything else. The long job still finishes; it just stops cutting in line.

## Stopping early

The last piece is **cancellation**: a client disconnects or a deadline passes, and the work on its behalf should stop. A `cancel_token` carries that request and a reason, and a `deadline` is a token a timer triggers. Deadlines live on one [timer wheel](/blog/retiring-the-sparse-wheel/) per loop, so setting one allocates nothing.

The point is that a token interrupts a wait already in progress. Before it did, a cancelled socket read ended **489 to 491 milliseconds** later, at a fallback close; wired into Asio's own cancellation, it ends in **0.0 to 0.1 milliseconds**, as Asio's own coroutine does. The runs are in the [cancellation status](https://github.com/Kronuz/task/blob/main/docs/status/cancellation.md).

## The numbers

The table shows the cost of creating, awaiting and destroying the smallest task, next to `asio::awaitable`, and the median delay from yielding the loop to running again, at `-O3` (from the [README](https://github.com/Kronuz/task#-performance)). task wins on Clang and loses the first column on GCC:

| Machine, compiler | task | `asio::awaitable` | Yield and resume: task | `asio::post` |
| --- | ---: | ---: | ---: | ---: |
| Apple M4 Pro, Apple clang 17 | **9.2 ns** | 10.2 ns | 42 ns | 42 ns |
| Intel Core i9-9980HK, Apple clang 17 | **18.1 ns** | 30.4 ns | 115 ns | 148 ns |
| Intel Core i9-9980HK, g++ 16 | 56.4 ns | **23.9 ns** | 90 ns | 122 ns |

On the Intel with Clang, task is 40 percent cheaper than Asio's coroutine. On GCC the trampoline costs 56 nanoseconds against Asio's 24, and forcing the tail call brings it to 34, still behind. Across 20 million tasks it allocates nothing, because frames come from per-thread pools of recycled blocks.

## How it is proven

Besides the deep chains, the tests cover affinity across threads, budget demotion, cancellation mid-wait, deadlines on a manual clock, and a stress run of a million tasks with random yields and cancellations. CI runs them with GCC and Clang on Linux (x86-64 and arm64), macOS and FreeBSD, plus address, undefined-behavior and thread sanitizer builds.

## Where it fits

task has two neighbors. [workpool](/blog/workpool/) owns *workers*, threads for blocking work like disk writes, shared fairly. [reactor](/blog/reactor/) owns *loops*, one per core, with accepting and clean shutdown. task owns neither: it is the coroutine that runs on a loop the host owns. Its docs tie it to the pool only at shutdown: the owner first stops every loop and pool a suspended task may be waiting on, which in Xapiand means draining its `WorkGroup`s, before any task frame is destroyed.

[http](/blog/http/) is built on it now: a request handler is a `task::task<void>`, and each connection a task on its reactor's loop. Reach for task when coroutines share a loop someone else runs, must give it back on a time budget, and must come home to the thread they started on.

Skip it for the fastest coroutines under GCC, where `asio::awaitable` wins, or when memory must stay on its thread: a frame freed elsewhere joins that thread's pool. And an exception escaping fire-and-forget work (a `spawn`) ends the program.
