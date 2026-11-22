---
title: "Sixteen Bytes Too Far"
subtitle: "A streaming HTTP parser that never copies, and the one place it read past the buffer."
description: "http-parser is a C++20 fork of the Joyent/Node.js HTTP/1.x parser: a callback-driven, zero-copy state machine you feed raw bytes in any framing, that calls back as it recognizes the request line, headers, body, and boundaries, handing you slices of your own input buffer and never allocating. It resumes mid-header across calls so the parse is identical however the bytes were framed. The gnarly bit is a hand-rolled SSE2 scan for the CRLF that read a 16-byte vector past the end of the buffer, an overread only ASAN caught. It was replaced with a bounded memchr, and later the vector scan came back, this time reading only whole blocks inside the buffer."
excerpt: "Bytes arrive off a socket in whatever sizes the network felt like: a whole request in one read, or one byte at a time, or a header split down the middle. A streaming parser has to produce the same result regardless, without copying and without ever reading a byte it was not handed. The eighth familiar does exactly that, except for the one line where it reached sixteen bytes past the end of the buffer, and only the sanitizer noticed."
date: 2026-08-19
lastUpdated: 2026-11-15
series: "Familiars"
seriesOrder: 8
chapter: "Network"
tags:
  - familiars
  - cpp
  - parsing
---

*Part of [**Familiars**](https://kronuz.github.io/cpp-libraries/), my collection of standalone C++ building blocks. This one lives at the wire: [http-parser](https://github.com/Kronuz/http-parser).*

TCP does not hand you messages. It hands you bytes, in whatever sizes it pleased, and the boundaries mean nothing: a whole HTTP request might arrive in one `read`, or dribble in one byte at a time, or split a header name straight down the middle across two packets. A parser that only works when the whole request shows up at once is not a parser, it is a demo. The real job is to consume bytes as they come and produce the exact same parse no matter how the wire chopped them up.

[http-parser](https://github.com/Kronuz/http-parser) is that: my C++20 fork of the venerable Joyent/Node.js `http_parser`, a callback-driven, **zero-copy** state machine for HTTP/1.0 and 1.1. You feed it raw bytes with `http_parser_execute()`, as many or as few as you have, and it calls back into your code as it recognizes the request line, each header field and value, the body, and the message boundaries. It keeps its state across calls, so a request split across a hundred `execute()`s parses identically to one delivered whole. And it never buffers the message or allocates on your behalf: the data callbacks hand you **slices of your own input buffer**, pointers into the bytes you passed in, so parsing a gigabyte of upload costs no parser memory at all.

Being a state machine is what makes the streaming work. There is no "read until you have the whole header" loop that could block or over-read; there is a current state, and each incoming byte advances it. Run out of bytes mid-header and the machine simply pauses, remembers it was halfway through a header value, and picks up there when the next chunk arrives. Xapiand's copy adds a few things on top of upstream: the method, status, and errno enums are built through the sibling [enum-reflection](https://github.com/Kronuz/enum-reflection) library so they are reflective, and the method table is extended with Xapiand's own verbs, `COMMIT`, `COUNT`, `UPDATE`, alongside the standard set.

## The one line that read too far

A zero-copy streaming parser has exactly one cardinal rule: **never read a byte you were not handed.** The callbacks point into the caller's buffer, the state machine advances one byte at a time within it, and the whole design is safe precisely because it never looks past the slice it was given. Except, for a while, in one place, it did.

Scanning for the `\r\n` that ends a line is the parser's hottest inner loop, so at some point it grew a hand-rolled **SSE2** fast path: on x86, load sixteen bytes at once into a vector register and compare them all against `\r` in a single instruction, which is much faster than a byte-at-a-time scan. The trouble is what "load sixteen bytes at once" does near the end of the buffer. When only three bytes remained before the end of the caller's input, the SSE2 load still read a full sixteen, thirteen of them past the end of the buffer, into memory that was not ours. On almost every run it read whatever happened to be there and moved on, harmless by luck. It was a **heap buffer overread**, the kind of bug that does nothing visible for years and then reads into an unmapped page and crashes, or worse, quietly influences a branch.

Nothing in a normal build flagged it. What flagged it was **AddressSanitizer**, running the doc-driven test suite in CI, which pointed straight at the vector load and said: this read is out of bounds. The fix was to delete the clever thing. glibc's `memchr` is already SIMD-optimized and, crucially, **bounded**: it scans exactly the length you give it and not one byte more. Replacing the SSE2 hand-roll with a plain `memchr` over the remaining length gave back the one guarantee the whole parser is built on: it never reads past the bytes it was handed. The lesson is old and keeps being true. A hand-vectorized loop that ignores its bound is faster right up until it reads someone else's memory, and only a sanitizer, run in CI on the architecture where the fast path lit up, will ever tell you.

The vector scan did come back, later, and this time it keeps the rule. Finding the end of a header value with `memchr` took two calls per value, about **3.4 nanoseconds** together, which was 10% to 16% of a header-heavy request. So the parser grew `find_crlf` again: sixteen bytes at a time, with NEON on ARM and SSE2 on x86, but it reads only whole sixteen-byte blocks that sit *inside* the span it was handed, and a plain byte loop takes the last few bytes. Near the end of the buffer, where the old version reached past it, the new one simply stops using vectors. The same treatment speeds up the URL (a 125-byte URL went from 415 ns to 63 ns), the build that turns the vector code off (`HTTP_PARSER_NO_SIMD`) runs in CI, and AddressSanitizer still watches every one of those scans.

## Where it fits

Reach for it any time you terminate HTTP/1.x yourself and want to do it without buffering or allocating: a server, a proxy, a client, a load test harness. It handles `Content-Length` and `chunked` bodies, keep-alive, upgrades, and reports a typed error when the input is malformed. It is one compiled source file, with one direct dependency, [enum-reflection](https://github.com/Kronuz/enum-reflection), which brings a handful of small header libraries of its own, and it does the thing a wire parser must never get wrong, which is stay inside its own buffer.

The next familiar is smaller and stranger: a unique identifier that is normally sixteen fixed bytes, and the trick of making it fewer by noticing how much of a UUID is not actually random.
