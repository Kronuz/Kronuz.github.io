---
title: "Built to Disappear"
subtitle: "An atomic shared_ptr that becomes a one-line alias the moment the standard library grows its own."
description: "atomic-shared-ptr provides atomic_shared_ptr<T>, thread-safe atomic operations over a std::shared_ptr<T> with the same member API as std::atomic: load, store, exchange, compare_exchange_weak and _strong, is_lock_free. It is the primitive lock-free data structures need to publish a new version of shared state atomically. Its defining trait is that it retires itself: where the standard library implements the C++20 std::atomic<std::shared_ptr<T>> specialization, the header becomes a plain alias and adds nothing; where it is not yet implemented, notably Apple clang's libc++, it provides the implementation. A polyfill written to vanish as the platform catches up."
excerpt: "You want to atomically swap a shared_ptr, publish a new version of some shared state without a lock, and read it safely from other threads. C++20 finally standardized that, but not every compiler shipped it. The twenty-third familiar fills the gap where it is missing and, more interestingly, is written to delete itself the moment the standard library grows the feature, so the dependency has a built-in expiry date."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 23
chapter: "Lock-Free"
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is designed to become unnecessary: [atomic-shared-ptr](https://github.com/Kronuz/atomic-shared-ptr).*

A `shared_ptr` is thread-safe in exactly one respect: the reference count. Two threads can copy and destroy the same `shared_ptr` object concurrently and the count stays correct. What is *not* safe is two threads racing on the pointer itself, one reading it while another reassigns it, which is exactly what you need to do to publish a new version of some shared state without a lock: build the new thing, then atomically swap the pointer so readers either see the whole old value or the whole new one, never a torn half. That atomic swap is the primitive under a lot of lock-free design, the read-copy-update pattern, a config you hot-reload, the head of a lock-free list, and a plain `shared_ptr` cannot do it.

[atomic-shared-ptr](https://github.com/Kronuz/atomic-shared-ptr) provides it: `atomic_shared_ptr<T>`, with the same member API as `std::atomic`, `load`, `store`, `exchange`, `compare_exchange_weak` and `_strong`, `is_lock_free`, so a lock-free algorithm reads and CAS-swaps a shared pointer the same way it would an integer.

```cpp
atomic_shared_ptr<Node> head{std::make_shared<Node>()};
auto cur  = head.load();
auto next = std::make_shared<Node>();
while (!head.compare_exchange_weak(cur, next)) { /* rebuild from cur, retry */ }
```

## The library with an expiry date

The genuinely nice thing about this one is not what it does, it is how it plans to stop existing. C++20 (proposal P0718) added a standard `std::atomic<std::shared_ptr<T>>` specialization that does precisely this. Not every standard library shipped it on time, though; Apple clang's libc++ lacked the specialization well past clang 17, even as it kept the older pre-C++20 free-function `atomic_*` overloads on `shared_ptr`. So there is a gap, some compilers have the clean standard thing, some do not, and code that wants to be portable *today* has to bridge it.

atomic-shared-ptr bridges it by **retiring itself gracefully**. It checks the feature-test macro `__cpp_lib_atomic_shared_ptr`, and:

- where the standard library implements the specialization, `atomic_shared_ptr<T>` is a **plain alias** for `std::atomic<std::shared_ptr<T>>`, and the header adds nothing at all;
- where it is missing, the header provides the implementation itself, built on the older free-function overloads.

So the library is a polyfill with a built-in exit. On a modern toolchain it compiles down to the standard type and evaporates; on an older one it quietly does the work; and your code says `atomic_shared_ptr<T>` either way and never has to know which branch it got. That is the right way to write a shim for a feature the standard is in the middle of absorbing: do not entrench yourself, make yourself deletable. The day the last compiler you care about grows the specialization, this dependency becomes a one-line `using` and then nothing, and no call site has to change.

## Where it fits

Reach for it when you need atomic operations on a `shared_ptr`, lock-free publication of shared state, a CAS'd list head, hot-swapped configuration, on a codebase that must build across compilers not all of which have the C++20 specialization yet. Skip it if you target only toolchains that ship `std::atomic<std::shared_ptr<T>>` (then just use that), or if a mutex around your pointer is simple enough and not on a hot path.

The next familiar is the honest counterweight to this whole lock-free chapter: a queue that does not try to be clever, pays a mutex without apology, and spends its cleverness instead on the two things lock-free queues make hardest, timeouts and a clean shutdown.
