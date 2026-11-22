---
title: Familiars
tagline: Standalone C++ building blocks
description: A collection of small C++ libraries, each with one job, its own tests and a CMake target you can link on its own.
tech: [C++]
logo: /img/projects/familiars.svg
repo: https://github.com/Kronuz/cpp-libraries
website: https://kronuz.github.io/cpp-libraries/
status: active
featured: true
order: 3
related:
  - session-zero
---

Familiars is my collection of C++ building blocks: a timer wheel, a crash tracer, an
HTTP server, a compact text index, and dozens of smaller things. The first parts came
out of [Xapiand](/projects/xapiand/); later ones were written for other systems or
started as independent projects.

Each library has one job, a README, tests and a CMake target. Most are header-only. There
is no common runtime to adopt. Link the part you need and let its declared dependencies
follow. [Detent](/projects/detent/) uses several of them, and Xapiand uses many more.

The [Familiars page](https://kronuz.github.io/cpp-libraries/) is a short map by task. The
[full catalog](https://github.com/Kronuz/cpp-libraries) lists every library, and the
[Familiars series](/blog/session-zero/) opens them one by one: the constraint behind each
design, the mechanism inside it, and where I reach for it.
