---
title: "Interchangeable Parts"
subtitle: "Three compression formats behind one interface, swapped by changing a single word."
description: "compressors wraps three genuinely different compression backends, deflate (zlib), lz4, and zstd, behind one uniform C++20 shape: a CRTP block-streaming base, a matching Data/CompressData/DecompressData class family per backend, and free-function helpers that take a string_view and return a string. Because the shape is identical, you swap deflate for lz4 for zstd by changing the function name and nothing else, and pick the tradeoff you want: broad interop, raw speed, or best ratio. deflate and lz4 also stream to and from file descriptors with the library's own EINTR-safe IO; the round-trip is byte-for-byte for every backend, including empty and incompressible input."
excerpt: "Compression is a set of tradeoffs, interop versus speed versus ratio, and the honest answer is 'it depends,' which is useless if switching backends means rewriting your call sites. The twelfth familiar puts three incompatible formats behind one identical shape, so choosing between deflate, lz4, and zstd is a matter of changing a single word in your code, and nothing else."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 12
tags:
  - familiars
  - cpp
  - compression
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is three engines behind one handle: [compressors](https://github.com/Kronuz/compressors).*

There is no best compression algorithm, only tradeoffs. **deflate** (zlib) is everywhere and speaks gzip, so it wins on interop. **lz4** barely thinks before it compresses, so it wins on speed and on cheap CPU. **zstd** gets the best ratio for the least regret and is the sensible modern default. Which one you want depends on the data, the CPU budget, and who has to read the bytes on the other end, and the honest answer for a system that compresses many kinds of thing is "different ones in different places."

That answer is only affordable if switching is cheap. If picking lz4 over zstd means a different API, different types, and rewritten call sites, then the choice calcifies: you pick once, early, and never revisit it even when the data changes under you. [compressors](https://github.com/Kronuz/compressors) is built so the choice stays live, by making the three backends **interchangeable parts**.

## One shape, three engines

Every backend has the same shape. There is a CRTP block-streaming base, `*BlockStreaming<Derived>`, a matching `*Data` / `*CompressData` / `*DecompressData` class family, and a pair of free functions that take a `std::string_view` and return a `std::string`. Because the shape is identical across all three, the only thing that changes between them is a name:

```cpp
std::string packed   = compress_zstd(payload);   // or compress_deflate, or compress_lz4
std::string restored = decompress_zstd(packed);  // restored == payload, byte for byte
```

Swap `zstd` for `lz4` in those two lines and you have changed your entire compression strategy, with no other edit. The uniformity is the feature. It means the decision of *which* backend is a local, reversible one, made where the data is, not an architectural commitment made once at the top. `decompress(compress(x)) == x` holds byte-for-byte for every backend, and the tests deliberately cover the awkward inputs, empty buffers and incompressible data, where naive compressors quietly grow the payload or mishandle the zero-length case.

## Genuinely different underneath

The uniform surface hides three formats that share nothing. Each backend only decodes its own output, and the test cross-checks that the three encodings of one input are three distinct byte streams. zstd emits a standard zstd frame that records the content size. deflate emits raw deflate, or gzip when you ask. lz4 uses its own framing, a sequence of `[uint16 length][LZ4 block]` records, ring-buffer streamed, because the raw lz4 block format does not carry its own length and something has to. deflate and lz4 additionally ship file-streaming variants that read and write file descriptors directly, using the library's own **EINTR-safe** IO helpers rather than any external layer, so a compressed copy from one fd to another is a first-class operation and not something you bolt on with a buffer in the middle; zstd is buffer-only.

The interchangeability is exactly why the design matters in Xapiand. The data store used deflate and lz4 for years, and when zstd earned its place as the default, adding it was a matter of writing one more backend of the same shape and changing a name at the call sites, not reworking the storage layer around a new API.

## Where it fits

Reach for it when you want to compress in-memory buffers (or stream files, for deflate and lz4) and you want the freedom to choose or change the backend per use without touching your code. Skip it if you only ever need one format and already link its library directly; the value here is the uniform shape, and if you never swap, you never spend it.

The next familiar is the floor the whole network stack stands on: the part of every TCP server you keep rewriting, the pool of event loops and the accept loop and the shutdown, written exactly once so no protocol ever has to write it again.
