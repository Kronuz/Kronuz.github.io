---
title: "Work, Not Threads"
subtitle: "Why a thread pool stops being enough, and what a work pool does instead."
description: "workpool is a small, dependency-free C++20 work pool built for a server with thousands of open indexes. A thread pool hands tasks to threads in the order they arrive; a work pool knows whose work each item is, and shares the threads fairly between owners. WorkPool is one set of named threads; each owner holds a WorkGroup on it and gets fair turns, its own waits and cancellation, and a fast lane for queries. Work items belong to the caller, so handing one over allocates nothing, and idle workers truly sleep: an idle pool uses 0.0008% of a core, and a query waits 12 to 40 microseconds behind 1,000 busy indexes instead of 70 milliseconds."
excerpt: "A thread pool is the least surprising thing in a concurrent program, until thousands of owners share it. The twenty-fifth familiar started life as a thread pool and grew into a work pool: the same threads, but shared by owners instead of handed out by arrival, so a query never waits behind somebody else's housekeeping, and an idle pool costs nothing."
date: 2026-10-02
lastUpdated: 2026-11-15
series: "Familiars"
seriesOrder: 25
chapter: "Lock-Free"
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is the workers everything else runs on: [workpool](https://github.com/Kronuz/workpool).*

A server does a lot of work that should not happen on the thread that asked for it. Writing an index to disk, compressing a block, answering a query: if each of those ran where it was requested, one slow job would freeze everything behind it. The usual answer is a **thread pool**: a fixed set of worker threads that stay alive and take jobs from a queue, one after another.

This library started as exactly that, under the name threadpool: a handful of workers and one shared queue. It served Xapiand for years. Then the question changed, the library changed with it, and the old name stopped fitting. It is called workpool now, and the difference between the two names is the whole story.

## A thousand customers, one line

A search server does not hold one index. It keeps thousands open, and they all want the workers at once. Some of the work is housekeeping that can wait a little: flushing new documents to disk, merging old files into bigger ones. Some of it is a query, and a person is waiting for that.

Picture a single checkout line at a busy store. Everyone waits in arrival order, so the customer with one item stands behind the one with three full carts. That is what one shared queue does. Measured with 1,000 busy indexes, a piece of a query waited **70.5 milliseconds** before a worker even looked at it, and an index that dumped a burst of jobs took 13 to 16 times its fair share of the workers. Nothing was wrong, exactly. The pool had just stopped being fair, and fairness had become the job.

## Thread pool or work pool

Both have the same thing inside: a fixed set of threads that run small pieces of work. What differs is what the pool knows about that work, and so what it can promise.

A **thread pool** sees tasks. A task arrives, it waits in the queue, a free thread runs it. The pool has no idea who the task is for, so the only fair thing it can do is first come, first served, and whoever submits the most work gets the most threads.

A **work pool** sees *owners*. Every piece of work belongs to someone (an index, an upload, a restore), and the pool shares the threads between those owners, not between tasks. That one extra fact unlocks everything a busy server needs:

| | Thread pool | Work pool |
| --- | --- | --- |
| The pool schedules | tasks, in arrival order | owners, in fair turns |
| A burst of work from one owner | takes the threads from everyone | takes only its own share |
| Urgent work, like a query | waits in the same line | has its own express lane |
| Waiting for "my" work to finish | waits for the whole pool, or tracks every task | waits for one owner's work |
| Cancelling | task by task, if at all | everything one owner queued |

The threads are the same. The work is what gets organized.

## Each owner gets a lane

`WorkPool` is the one set of workers for the whole program. Every owner of work (an index, a restore, an upload) gets its own `WorkGroup` and puts its jobs there:

```cpp
WorkPool pool;          // one worker per hardware thread
WorkGroup index(pool);  // one group per owner

index.enqueue([] { flush_to_disk(); });
index.wait();           // waits for this group's jobs, nobody else's
```

Everything an owner controls is about its own group. `wait()` returns when *its* jobs are done, not when the whole pool is quiet. `cancel()` drops its jobs that have not started yet. Closing one index never has to wait for the others.

Inside, the workers take turns among the groups, like a cashier who serves each line for a moment and then moves to the next. A worker serves one group for a short turn (100 microseconds of work), then sends that group to the back if it still has jobs. A group that ran long gets a shorter turn next time, so over time everyone gets the same share. The name for this is *deficit round robin*, and it is old networking wisdom: routers use it to share a link fairly between connections.

The same rule handles both extremes. A group alone on a quiet server spreads across every worker: one index finishes a flush of 64 one-millisecond jobs in about 4.3 to 5.1 ms on 16 workers, close to the ideal 4.0. A thousand busy groups each take their turn and end up with equal shares, and a group that dumps a burst gets about its fair share instead of 13 times it.

## An express lane for queries

Fair is not enough when someone is waiting. So jobs come in classes: queries, flushes and merges. Workers always look at the query line first, and one worker is kept for queries only, the way a store keeps one express register open. A query never waits for somebody's long merge to finish. With that, a query piece behind 1,000 busy indexes waits **12 to 40 microseconds**, down from 70.5 milliseconds, well over a thousand times sooner.

Merges get a promise in the other direction. A merge that has waited more than 100 ms moves ahead of the flushes, so a flood of flushes cannot starve it forever.

## The tricky part: waiting inside the pool

Here is the trap every pool falls into eventually. A job running on a worker splits itself into pieces and waits for them. That blocks a worker. If enough jobs do it at once, every worker is asleep waiting for pieces, and no worker is left to run the pieces. The program stops, forever.

workpool's answer is that a worker that waits does not sleep. It rolls up its sleeves and runs the pieces it is waiting for itself, and only those, so it can never get lost in somebody else's work. A wait that could never finish (waiting on a group that is already waiting on it) stops the program loudly instead of hanging quietly. The tests check this hard: 20,000 jobs that each wait on their own pieces still never need more than the existing threads, and a chain of 500 groups waiting on each other finishes on a single worker.

## An idle pool sleeps

The old workers checked for work ten times a second even when there was none, about 0.4% of a core and 300 wake-ups a second, per pool, doing nothing. Now each idle worker sleeps until someone actually hands it work, and a new job wakes exactly one sleeper, only when nobody is already looking. Idle cost dropped to **0.0008%** of a core, and handing a tiny job to the pool went from 7 microseconds to under 140 nanoseconds. On a fleet of mostly idle servers, that is real CPU and power handed back.

## Where it fits

Reach for it when one program does work for many owners who must share the CPU fairly: indexes, tenants, sessions, with requests that must not wait behind bulk work. It is also simply a good pool of named workers when you have only one owner.

Skip it for fine-grained parallel algorithms that want *work stealing* (idle workers raiding busy workers' queues), for coroutines (that is [task](https://github.com/Kronuz/task)'s job), or when you need a full queue to push back on producers: here, adding a job never blocks. The whole design, every alternative it beat, and the measurements behind each number are in the repo's [scheduler research note](https://github.com/Kronuz/workpool/blob/main/docs/research/scheduler.md).

That closes the lock-free chapter. The next familiars are a different kind of magic: the ones that do their work before the program ever runs, at compile time.
