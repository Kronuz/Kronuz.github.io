---
title: "The Syscalls That Lie"
subtitle: "The EINTR retry, the fsync that isn't, and the one call you must never retry."
description: "io is an EINTR-safe POSIX file and socket layer extracted verbatim from Xapiand. Every function in the io:: namespace mirrors a syscall of the same name but adds the retry and short-count handling a real storage or network engine needs: read, write, send, recv, fsync and friends retry through EINTR, write and pread loop until the whole buffer moves, open refuses to hand back a descriptor below stderr and sets O_CLOEXEC, and durability is made portable (fdatasync on Linux, F_FULLFSYNC on macOS for real on-platter sync, fallocate with fallbacks). The one deliberate exception is close(), which never retries on EINTR, because retrying close can double-close a file descriptor another thread has already reused."
excerpt: "The POSIX calls at the bottom of every server are not as honest as they look. A read can be cut short by a signal and return having done nothing wrong. An fsync on macOS returns success without actually putting your data on the platter. And retrying a close() that was interrupted can silently destroy a file descriptor another thread just reused. The eighteenth familiar is the thin layer that knows all of this and does the boring, correct thing so the rest of the engine never has to."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 18
chapter: "Forbidden Layer"
tags:
  - familiars
  - cpp
  - posix
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is the floor nobody thanks: [io](https://github.com/Kronuz/io).*

The system calls at the bottom of every server look like the simplest thing in the stack, and they are the most quietly treacherous. Not because they are hard, but because they are *honest in ways you did not ask for*: they report exactly what the kernel did, and what the kernel did is often "nothing, because a signal arrived," or "I wrote some of it," or "I flushed to the disk's cache and called that durable." Handle each of those correctly at every call site and your code is right and unreadable. Handle them by copy-pasting a retry loop and you will get one of them wrong. [io](https://github.com/Kronuz/io) is the thin layer that handles them **once**: every function in the `io::` namespace mirrors a syscall of the same name, and adds the retry and short-count handling underneath, so no call site ever open-codes an `EINTR` loop again.

Three of the lies it covers are worth telling.

## The read that did nothing

A blocking `read`, `write`, `accept`, `fsync`, almost any slow syscall, can be interrupted by a signal before it does its work and return `-1` with `errno == EINTR`. Nothing is wrong; you are just expected to call it again. Miss that, and a stray signal, a timer, a `SIGCHLD`, turns a perfectly good read into a spurious error at random. io routes those calls through a retry that loops while `errno == EINTR`, so the interruption is invisible above it. And it goes further where the kernel is allowed to be lazy: `write` and `pwrite` loop until the *whole* buffer is transferred, because a "successful" write is allowed to move fewer bytes than you asked, and treating a short write as done is a classic way to silently truncate data.

## The fsync that isn't

Then there is durability, which is where the platform stops merely being lazy and starts actively misleading you. On macOS, `fsync` returns success after flushing your data to the drive's own write cache, not to the platter. If the power fails a moment later, the data you were told was safe is gone. The real guarantee needs `fcntl(F_FULLFSYNC)`, which is slower and which Apple made opt-in precisely because it is slow. io's `full_fsync` uses `F_FULLFSYNC` on macOS and `fdatasync` on Linux, so "make this durable" means the same thing everywhere, instead of meaning "durable" on one OS and "probably" on another. The same portability seam covers preallocation: `fallocate` on Linux, `F_PREALLOCATE` on macOS, and a ftruncate-and-touch emulation where neither exists.

## The one call you must never retry

And then the sharpest edge of all, the reason this cannot just be a blanket "retry everything" macro: **`close()` is the one call you must not retry on `EINTR`.** It is counterintuitive, because retrying is the fix for every *other* interrupted call. But on Linux, when `close()` returns `EINTR`, the file descriptor may already have been closed. Retry it, and you are now calling `close()` on a descriptor number that another thread, in the microseconds since, may have been handed by `open()` for a completely unrelated file. You do not re-close your socket; you slam shut someone else's database handle, and the resulting corruption is untraceable because the two operations have nothing to do with each other. So io retries almost everything and deliberately, pointedly, does **not** retry `close`. It is the kind of exception you only add to a library after it, or something like it, has cost someone a very bad afternoon.

For good measure, `open()` also refuses to return any descriptor below `stderr + 1`, so a data file can never accidentally land on `fd` 0, 1, or 2 and get written to by a stray `printf`, and it sets `O_CLOEXEC` so descriptors do not leak across an `exec`.

## Where it fits

Reach for it whenever you do real file or socket IO in a long-running C++ process and want EINTR, short counts, safe descriptors, and honest durability handled for you, portably, with zero dependencies. Skip it only if you are already inside a runtime (an async framework, a database) that owns the syscalls for you. This is not a glamorous familiar. It is the one that makes the glamorous ones correct.

The next familiar stays down here in the machine, on the same portability problem from the other side: reading how much memory and CPU the process and the host actually have, on operating systems that each keep the answer somewhere different.
