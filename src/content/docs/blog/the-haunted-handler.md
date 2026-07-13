---
title: "The Haunted Handler"
subtitle: "Walking every thread's stack, portably, from inside a signal handler."
description: "traceback, a whole-process crash dumper extracted from Xapiand, freezes every registered thread with SIGUSR2 and has each one photograph its own stack from inside the signal handler. Two unrelated hard parts meet there: walking a stack portably (the frame pointer is one idea spelled nine ways across Linux, macOS, and FreeBSD on x86-64 and AArch64, plus stack-growth direction and whether backtrace() even exists), and doing it where almost nothing is safe to call. Plus the bug where backtrace() itself lazily dlopens libgcc_s (a malloc) on its first call, inside the handler, which killed the TSAN build at startup until we warmed it one call early."
excerpt: "Sometimes the only useful question about a stuck server is 'what is every thread doing, right now?' traceback answers it by signalling every thread at once and having each photograph its own stack. The hard part is that the stack walk is one idea spelled nine different ways across Linux, macOS, and FreeBSD, run inside a signal handler where the wrong call deadlocks the process. The second familiar out of Xapiand, written half by reasoning and half by waiting for a red build on a machine I'll never log into."
date: 2026-07-09
draft: true
series: "Familiars"
seriesOrder: 2
chapter: "Forbidden Layer"
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). [Rolling for a Name](/blog/rolling-for-a-name/) pulled out a jester. This one pulls out something that has to do its work in a haunted room: [traceback](https://github.com/Kronuz/traceback).*

There is a question you eventually need to ask a server that has stopped answering: **what is every thread doing, right now?** Not "what crashed," which a core dump tells you, but the live picture of a process that is up, accepting connections, and quietly wedged. One thread is blocked on a lock, another is spinning, a third is asleep waiting for the first, and the shape of the deadlock is written across all of their stacks at once. You want a single photograph of the whole process, every call stack frozen in the same instant.

[traceback](https://github.com/Kronuz/traceback) takes that photograph. It is the crash-and-diagnostics toolkit I pulled out of Xapiand, and its party trick is exactly this whole-process snapshot: signal every thread, have each one walk its own stack where it stands, and render all of them together. The trick works. The reason it is worth a post is *where* each thread has to do its walking, and the very small, very sharp bug I found living there.

## The easy half: reading one stack

The bottom layer is ordinary. Give traceback nothing and it captures the current stack and symbolizes it: `backtrace()` for the return addresses, then `dladdr` plus `abi::__cxa_demangle` to turn each address into a demangled `symbol + offset`, with an optional `atos` pass for `file:line` on macOS.

```cpp
std::string tb = traceback::format(std::source_location::current());

// == Traceback (most recent call first): search.cc:214 at do_search():
//       2 0x000000010429... Xapiand::MSet::merge() + 56
//       1 0x000000010429... main + 36
//       0 0x0000000188... start + 6992
```

Fine. Every crash reporter does some version of this. The interesting layer sits on top, behind a build flag, and it is the one that has to survive somewhere hostile.

## The hard half: reading *every* stack at once

You cannot walk another thread's stack from the outside while it runs. Its stack pointer, its frames, its registers are all moving. The only safe moment to read a thread's stack is when that thread is standing still, and the portable way to make a running thread stand still and run a little code for you is a **signal**.

So the whole-process dump is a piece of choreography. Every thread that wants to appear in the photograph first **registers** itself, dropping its `pthread_t` and a name into a shared table. Then, when one thread calls `dump_callstacks()`, it does this:

```d2 alt="One collector thread calls pthread_kill(SIGUSR2) on every registered thread. Each signalled thread, inside its SIGUSR2 handler, walks its own stack and stores the frames into its own slot in the shared registry. The collector then waits for the acknowledgements and renders every thread's stack together."
direction: down
c: "collector · dump_callstacks()"
k: "pthread_kill(SIGUSR2) → every registered thread"
h: "each thread, in its handler:\nwalk own stack → own slot  (× N)"
r: "collector: gather slots, render every stack"
c -> k -> h -> r
```

Every thread is interrupted wherever it happened to be, and *in the signal handler*, each one walks its own stack and writes the frames into its own slot. The interrupted thread is the one holding still and doing the reading, which is the only arrangement that is actually safe. Then the collector gathers the slots and prints the whole process.

That middle step, "walk your own stack," sounds like one line of code. It is the hardest thing in the library, for two reasons that have nothing to do with each other. The first is that there is no portable way to walk a stack, so the one line is really nine. The second is *where* the walking happens.

## The same register, nine ways

Before signals enter the picture at all, there is this: to follow a chain of return addresses up the stack you need a foothold, the interrupted thread's frame pointer, and the kernel does hand it to you, buried in the `ucontext_t` it passes into the handler. But a `ucontext_t` is a saved copy of the CPU register file, and the register file is the least portable object in computing. Every operating system wraps it in a differently-shaped struct, and every architecture keeps the frame pointer in a differently-named register. "Read the frame pointer" is not a line. It is a ladder:

```cpp
#if   defined(__x86_64__)
  #if   defined(__FreeBSD__)   frame = uc->uc_mcontext.mc_rbp;
  #elif defined(__linux__)     frame = uc->uc_mcontext.gregs[REG_RBP];
  #elif defined(__APPLE__)     frame = uc->uc_mcontext->__ss.__rbp;
  #endif
#elif defined(__aarch64__)
  #if   defined(__FreeBSD__)   frame = uc->uc_mcontext.mc_gpregs.gp_x[29];
  #elif defined(__linux__)     frame = uc->uc_mcontext.regs[29];
  #elif defined(__APPLE__)     frame = uc->uc_mcontext->__ss.__fp;
  #endif
#else
  #error Unsupported architecture.
#endif
```

That is condensed. The real ladder carries i386 too, and it `#error`s on anything it does not recognize rather than guess. Read it top to bottom and it is the same sentence nine times: *the frame pointer is register X, and on this OS the kernel filed it there.* On x86-64 the register is `rbp`, and FreeBSD calls the field `mc_rbp`, Linux indexes it as `gregs[REG_RBP]`, macOS reaches through a pointer to `__ss.__rbp`. On AArch64 the register is `x29`, and the three OSes disagree all over again about where it lives. The idea never changes inside a single cell of that table. Only the spelling does, and every cell is a fresh chance to read the wrong eight bytes and send the walker chasing a garbage pointer into noise. In a signal handler. Where you get no second warning.

Two smaller potholes sit on the same road. A frame pointer is only safe to dereference if you know which way the stack grew, because the handler sanity-checks that the frame lies on the correct side of the current stack pointer first, and that comparison flips sign on the rare architecture whose stack grows *up*. And `backtrace()` itself, the higher-level walker traceback prefers, is not a language feature but a libc one that lives in `execinfo.h`. glibc, macOS, and FreeBSD have it; musl does not, and even where a compatible `libexecinfo` exists it is a separate library the build has to go hunting for, so the dumper has to degrade cleanly to "no frames" wherever it is absent.

Symbolizing the addresses you collected has its own per-OS map. `dladdr` plus `abi::__cxa_demangle` turn an address into a demangled `symbol + offset` almost everywhere. But `file:line`, the part you actually want at three in the morning, has no portable source, so traceback earns it on macOS only, by shelling out to `atos` through a `forkpty`, and simply does without it elsewhere.

The cruel part is that you cannot test most of this where you write it. I work on an arm64 Mac. The FreeBSD-on-AArch64 cell of that ladder is code I wrote **blind**, reasoning from a header I read in a browser tab, and the only thing that ever confirmed `mc_gpregs.gp_x[29]` was the right incantation was a CI runner on a machine I will never log into. Portable systems code like this is written half by reasoning and half by pushing a commit and waiting for a red build somewhere you have never been.

## The forbidden room

The portability is a grind you can at least see coming. The second hard part is a trap you cannot, because it is not about what you write, it is about *where it runs*. A signal can arrive at any instruction. It can interrupt your thread in the exact middle of `malloc`, while `malloc` holds its internal lock and its data structures are half-updated. If your handler then calls `malloc`, it tries to take a lock the interrupted thread already holds and will not release until the handler returns. That is a self-deadlock, in one thread, from one line. The same trap is set under every lock in libc, which is why the list of functions you are *allowed* to call from a handler, the **async-signal-safe** list, is tiny: `write`, `_exit`, a handful of syscalls. No `malloc`, no `printf`, no locks, almost nothing that allocates.

traceback's handler is built to live under that rule. The thread registry is a **fixed, preallocated, lock-free array**, not a growable container, precisely so the handler never allocates and never locks. It takes the foothold from the ladder above, walks, and stores the frames it finds with plain relaxed atomic writes into its own slot:

```cpp
// inside the SIGUSR2 handler: no malloc, no lock, only atomic stores
for (std::size_t n = 0; n < frames; ++n) {
    thread_info.callstack[n].store(callstack[n], std::memory_order_relaxed);
}
thread_info.callstack_frames.store(frames, std::memory_order_release);
```

No allocation, no lock, nothing that isn't async-signal-safe. I was careful about all of it. And it still mallocked in the handler, because the unsafe call was hiding inside a function I thought was innocent.

## The torch you light too late

The handler calls `::backtrace()` to walk the stack. `backtrace()` looks like a leaf: hand it a buffer, get back return addresses. But on glibc the unwinder it needs lives in a separate shared object, `libgcc_s`, and glibc does not load that object until the **first** time `backtrace()` is called anywhere in the process. That first call quietly `dlopen`s `libgcc_s`, and `dlopen` allocates.

So `backtrace()` is async-signal-safe... on every call but its first. The very first `backtrace()` in the life of the process mallocs, once, to load the unwinder, and after that it never does again.

Now line up the timing. At node startup Xapiand takes an early whole-process snapshot, before anything else has had a reason to walk a stack. That means the first `backtrace()` in the entire process happens **inside the SIGUSR2 handler**. It `dlopen`s `libgcc_s`. It mallocs. In signal context. On a normal build you would most likely never notice, because nothing was mid-`malloc` in that instant and the deadlock is a race you usually win. But **ThreadSanitizer** does not care whether you won the race. It sees a call that is not on the async-signal-safe list happening inside a signal handler, reports "signal-unsafe call inside of a signal," and under `halt_on_error` it aborts the process. The TSAN build died on startup, every time, and the stack it died on was the very code whose whole job is to survive there.

The fix is almost funny, because it is the same lazy initialization that caused the wound, moved one step earlier and pointed the other way. A thread must register before it can be signalled. So force the one-time load in `register_thread()`, in normal context, the first time anyone registers:

```cpp
// register_thread(), normal context: pay the one-time libgcc_s load HERE,
// so every later in-handler backtrace() is malloc-free.
#if defined(TRACEBACK_HAVE_EXECINFO)
    [[maybe_unused]] static const bool warmed_backtrace = [] {
        void* tmp[1];
        (void)::backtrace(tmp, 1);
        return true;
    }();
#endif
```

One `backtrace()`, guarded by a thread-safe function-local static, so it fires exactly once for the whole process and costs nothing after. Because registration always precedes any signal, the torch is lit in the safe room before anyone carries it into the haunted one. TSAN went quiet, and the startup snapshot stopped mallocking where it must not.

## The lesson the handler taught me

I went into that handler watching for the obvious forbidden things, the `malloc` I might write, the lock I might take, and I kept all of them out. The call that broke the rule was one I did not write at all. It was a **lazy initialization** buried three layers down in a function that is safe on every call except the one that matters, the first.

That is the part worth carrying out of the room. Async-signal-safety is not only about the allocations *you* make in the handler. It is about every lazy path anything you call might take on its first use: the `dlopen` behind `backtrace`, a `std::call_once`, a static local's guarded construction, a locale table filled on demand. Any of them is a single hidden `malloc` waiting for its first invocation, and if that first invocation lands in a handler, you have an unsafe call you never wrote. The defense is boring and reliable: **warm every lazy path once, in normal context, before you can ever be signalled.** Touch the code in daylight so it is never touched for the first time in the dark.

traceback is that discipline made into a small library: a portable whole-process stack photographer you can point at a wedged server to see every thread at once, with the async-signal-safety worked out and the one nasty lazy path warmed for you. One header of API, a formatting box you can use on its own, and the crash dumper behind a flag when you want the whole picture.

Next familiar is the one I would keep if I could keep only one. Somewhere in the running server a single thread sleeps, and every other thread keeps dropping timed work onto its schedule: log flushes, fsyncs, commits, replication triggers, a hundred thousand hand-offs a second. Not one of them is allowed to take a lock, and, harder than that, not one is allowed to *stall*. The strange little lock-free structure that makes both true at once is the best thing in the whole codebase.
