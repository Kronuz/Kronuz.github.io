---
title: "Down the Flume"
subtitle: "Streaming a whole database over a wire, compressed and checked, without holding it in memory."
description: "flume carries a file, or any fd-backed byte source, downstream over a byte channel: compressed, framed, integrity-checked, in bounded memory. It is the transport-layer counterpart to the compressors buffer codecs: compressors squeezes an in-memory buffer, flume owns the fd reading, the on-wire framing, and the end-to-end integrity check, and delegates the per-block squeeze to a codec policy. It defaults to Zstandard level 6, the ratio knee for bulk transfer (about 48% fewer bytes than LZ4 at 379 MB/s on one core), and treats the level as a knob rather than a wire-format decision, since a self-describing zstd frame decodes at any level regardless of what the other end used."
excerpt: "Replicating a database means moving a file bigger than memory across a link, and doing it so that it arrives smaller, intact, and without ever loading the whole thing into RAM at either end. The seventeenth familiar is named after the wooden channel that floats logs downstream: you feed a file in one end and it comes out the other, compressed and checked, in bounded memory, at a ratio that turns bandwidth into headroom."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 17
chapter: "Bytes"
tags:
  - familiars
  - cpp
  - compression
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one moves whole files, not buffers: [flume](https://github.com/Kronuz/flume).*

A flume is the wooden channel that floats logs downstream, and the name is the design. When a node has to send another node a whole database, a replication snapshot, a bulk import, you cannot compress it the way you compress a small buffer, because the file is bigger than the memory you are willing to spend on it. You need to feed it in one end of a channel and have it come out the other, smaller and intact, while only ever holding a block of it at a time. That is [flume](https://github.com/Kronuz/flume): carry a file, or any fd-backed byte source, downstream over a channel, compressed, framed, integrity-checked, in **bounded memory**.

It is the transport-layer counterpart to the [compressors](/blog/compressors/) buffer codecs from a few posts back. compressors squeezes an in-memory buffer; flume owns the parts a buffer codec does not: reading the file descriptor, framing the stream into blocks on the wire, and checking end-to-end that what arrived is what left. The per-block squeeze it delegates to a codec policy, so the two libraries split the job cleanly, one does the compression math, the other does the plumbing of moving a large thing safely.

## The ratio is the bandwidth

For a whole-database transfer, the compression ratio is not a nicety, it *is* the bandwidth: every byte you do not send is a byte the link does not carry. So flume's default is tuned for exactly that case. Measured on a 32 MB replication-like corpus in 256 KB blocks:

| codec | ratio | compress | decompress |
| --- | --- | --- | --- |
| lz4 (classic) | 7.90x | 1671 MB/s | 3346 MB/s |
| zstd L3 (zstd's default) | 12.63x | 1467 MB/s | 3231 MB/s |
| **zstd L6 (flume default)** | **15.14x** | **379 MB/s** | **3796 MB/s** |
| zstd L9 | 15.79x | 209 MB/s | 3928 MB/s |

flume defaults to Zstandard at **level 6**, above zstd's own default of 3, because L6 is the knee of the curve for bulk data: about **48% fewer bytes than LZ4** (2.22 MB versus 4.25 MB for the 32 MB corpus) while still compressing at 379 MB/s, which saturates any normal link on a single core. Push higher and the ratio barely improves while compression speed collapses; the classic LZ4 default was leaving nearly half the bandwidth on the table. And notice decompression gets *faster* at higher levels, not slower, because there is simply less encoded data to read back.

## The level is a knob, the codec is the wire

The subtle, correct design decision is which choices are on the wire and which are not. A zstd frame is **self-describing**: it carries everything a decoder needs, so a block compressed at level 1 and a block compressed at level 19 both decode with the same decoder, and the two ends of the flume do not have to agree on the level at all. That makes the level a free, per-call-site **knob**: reach for `ZstdCodec<1>` when you are CPU-starved and the link is fat, `ZstdCodec<19>` when the link is thin and you have cycles to spare, and the receiver neither knows nor cares. The *codec* choice, zstd versus LZ4, is the actual wire-format decision, because those are incompatible formats; the *level* never is. Getting that distinction right is what lets you tune a transfer to its link without a protocol negotiation.

## Where it fits

Reach for it when you move large fd-backed things between processes or hosts and want them compressed, framed, and checked without buffering the whole payload: replication, backups, bulk load. Skip it if your payload fits comfortably in memory (just use the [buffer codec](/blog/compressors/) directly) or if you are already inside a transfer protocol that frames and checksums for you.

The next familiar is the floor all of this stands on, the one nobody thanks: the POSIX layer that survives a signal mid-syscall, and knows which of the calls beneath it are quietly lying to you.
