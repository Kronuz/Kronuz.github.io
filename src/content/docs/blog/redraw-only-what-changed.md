---
title: "Redraw Only What Changed"
subtitle: "Making DOSBox's scalers up to 9,500% faster."
description: "A deep look at my 2005 DOSBox scaler patch: a previous-frame source cache, chunked dirty-region detection, and scalers that only re-run on the pixels that moved. With the real code, the numbers, and what happened to it."
excerpt: "DOSBox's scalers redrew the entire screen every single frame, even when almost nothing had changed. So I taught them to notice. This is how the patch actually worked, a source-line cache and a chunked dirty map, and the up-to-9,500% it bought."
date: 2026-06-08
draft: true
series: "Opening Boxes"
seriesOrder: 3
tags:
  - opening-boxes
  - retrocomputing
  - performance
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This one opens the [DOSBox](https://www.dosbox.com) box.*

In late 2005 I was twenty-seven, in love with old games, and annoyed at a number.

The number was how long [DOSBox](https://www.dosbox.com) took to draw a frame when you turned on one of the nice scalers. DOSBox is an emulator that runs old DOS games, and its **scalers** are the filters that blow up a tiny 320x240 game to fill a modern screen without it looking like a blanket. The best of them, **Hq2x**, is gorgeous. It is also expensive: for every output pixel it looks at a 3x3 neighborhood of source pixels and picks, from a big lookup table, how to blend them. Do that for a whole screen, sixty times a second, and you feel it.

I measured it. On a Pentium 4 at 3 GHz, Hq2x was spending about **10,676** of my arbitrary units per ~5,000 frames. The plain `Normal` scaler took 126. Hq2x cost roughly eighty times more than just copying the picture.

Here is the thing that bothered me, the thing this whole post is about: **almost none of the screen changes from one frame to the next.** A character walks. A health bar ticks. The other 95% of the pixels are identical to the frame before. And DOSBox was lovingly re-running that expensive Hq2x kernel over every single one of them, every frame, to produce an output that was, for almost the entire screen, byte-for-byte what it had just produced.

So I taught the scalers to notice.

## The old path

DOSBox's render pipeline was simple and wasteful. Every frame, the whole emulated framebuffer went through the scaler kernel and the whole result was handed to SDL (or OpenGL) to put on screen.

```d2 alt="The original DOSBox render path: the whole frame is rescaled and uploaded every frame"
direction: down
emu: "Emulated VGA framebuffer"
scaler: "Scaler kernel (whole frame, every frame)"
out: "SDL / OpenGL (upload whole frame)"
emu -> scaler: "every pixel"
scaler -> out: "every pixel"
```

It does not matter that nothing moved. The cost is paid in full, every frame.

## The idea: a cache and a dirty map

What I wanted was for the scaler to remember the previous frame's *input*, compare the new input against it, and only do work where the two differ. Two pieces make that happen.

The first is a **source-line cache**: a copy of the previous frame's source pixels, kept per line. The second is, for each line, a small list of the spans that actually changed, which I called the **BlockMap**. From the BlockMap I also kept a bounding box of the whole changed area, a `Rect`, to hand to the display layer so it would only upload the part of the screen that moved.

```d2 alt="The patched render path: a previous-frame cache feeds a chunked diff that produces a BlockMap of changed spans and a changed Rect; the scaler runs only on changed spans, and only the Rect is uploaded"
direction: down
emu: "Emulated VGA frame"
cache: "Previous-frame source cache" { style.stroke-dash: 3 }
keeper: "CacheKeeper (chunked diff)" { style.bold: true }
bm: "BlockMap (changed spans)"
rect: "Changed Rect (bounding box)"
scaler: "Scaler kernel: changed spans only" { style.bold: true }
out: "SDL / OpenGL: upload Rect only"
emu -> keeper
cache -> keeper: "compare"
keeper -> bm
keeper -> rect
bm -> scaler: "run kernel here"
scaler -> out
rect -> out: "upload here"
```

The expensive kernel and the expensive upload both shrink from "the whole screen" to "the parts that moved." On a typical game frame that is the difference between 100% of the work and maybe 5%.

## What the patch actually changed

The patch (`dosbox-optscalers-20051213.diff`, version 11b, the [last release candidate](https://www.vogons.org/download/file.php?id=2413)) touches ten files, but the heart of it is in three: `include/dosbox.h`, `src/gui/render.cpp`, and `src/gui/render_templates.h` (the file the scaler kernels are generated from).

In `dosbox.h` I added the changed-region box:

```c
typedef struct Rect {
    Bit32u left;
    Bit32u top;
    Bit32u right;
    Bit32u bottom;
} Rect;
```

The real work is a function I wrote in the scaler template header and, in the patch, marked with a comment I still smile at: `// Cache management stuff. Added by Kronuz:`. It is called `CacheKeeper`, and it runs once per source scanline. Lightly trimmed, here is the core of it:

```c
// Maintains and updates the Cache and the modifications BlockMap
// for the current frame being drawn:
static INLINE SRCTYPE* CacheKeeper(const SRCTYPE *src, SRCTYPE *cache) {
    if (Scaler_RebuildCache) {
        BlockMap[0] = 0;             // number of changed spans, reset
        Bitu *bm = BlockMap + 1;
        Bitu base = 0, chunk = CACHE_CHUNKS;   // CACHE_CHUNKS == 20

        for (Bitu xx = 0; xx < Scaler_SrcWidth; ) {
            // compare four source bytes at a time against the cached line
            if (GCC_UNLIKELY(*((Bit32u*)&cache[xx]) != *((Bit32u*)&src[xx]))) {
                if (GCC_UNLIKELY(!base)) {       // entering a changed span
                    base = !base;
                    bm[0] = xx;                  // remember where it started
                    ++BlockMap[0];
                }
                xx += chunk;                     // skip ahead...
                chunk <<= 1;                     // ...faster each step
            } else {
                if (GCC_UNLIKELY(base)) {        // leaving a changed span
                    base = !base;
                    bm[1] = xx;                  // remember where it ended
                    memcpy(&cache[bm[0]], &src[bm[0]], (bm[1]-bm[0])*SRCSIZE);
                    bm += 2;
                    chunk = CACHE_CHUNKS;
                }
                xx += sizeof(Bit32u);
            }
        }
    }
    /* ... */
}
```

A few details that matter, because the speedup lives in them:

- **Four bytes at a time.** It compares the cached line and the new line as `Bit32u` words, not byte by byte. The common case (no change) is a fast pointer-chasing scan.
- **Adaptive skipping.** When it finds a change, it does not crawl. It jumps ahead by `chunk` and *doubles* `chunk` each step (`chunk <<= 1`). Once you know you are inside something that moved, you can afford to find its far edge coarsely and back-fill; a span of changed pixels is found in a handful of jumps instead of one comparison per pixel. When the span ends, `chunk` resets to 20.
- **The cache is only updated on the spans that changed.** That `memcpy` copies the new pixels into the cache exactly for the span we just closed, and nowhere else.
- **The BlockMap is a run-length list.** `BlockMap[0]` is the count of changed spans on the line; the rest are `[start, end]` pairs. The scaler walks that list and runs its kernel over those spans only.

There is a second, palette-aware version of the loop for 8-bit games, and it is the detail I am most quietly proud of. In a palette game the *indices* in the framebuffer can be identical between two frames while the **palette** underneath them changes, a fade, a flash, a cycling waterfall. Comparing indices alone would miss that, and you would get a frozen, wrong screen. So when the palette changed, the loop also marks a chunk dirty if any of its pixels' palette entries moved:

```c
if (*((Bit32u*)&cache[xx]) != *((Bit32u*)&src[xx]) ||
    Scaler_PaletteDiffs[cache[xx]]   || Scaler_PaletteDiffs[cache[xx+1]] ||
    Scaler_PaletteDiffs[cache[xx+2]] || Scaler_PaletteDiffs[cache[xx+3]]) {
    /* changed: open / extend a span */
}
```

The neighborhood scalers needed one more thing. Hq2x looks at a 3x3 grid, so to scale line *N* correctly the kernel needs lines *N-1*, *N*, and *N+1*. I keep three cached lines (`Cache_p1`, `Cache_p2`, `Cache_p3`) and the kernel reads its nine neighbors (`CA` through `CI`) from them, so a chunk is only re-scaled when its 3x3 neighborhood actually moved, not just its own row.

## What it bought, and how to read the numbers

The optimization is not really about scalers. It is about touching less of the screen: the copy, the scaling, and the upload to the GPU. The scalers are just where it shows up most violently, because their per-pixel kernel is the most expensive thing in the pipeline. The same change helps even the cheapest path: the plain `Normal` scaler, which is essentially a `memcpy`, **nearly doubled.**

Here are the version-4 numbers on platform games (units are ms per ~5,000 frames, lower is better), with the speedup written as a plain ratio so there is no ambiguity:

| Scaler     | Before | After | Speedup | "Percent faster" |
| ---------- | -----: | ----: | ------: | ---------------: |
| Normal     |  127.3 |    67 |  1.9×   |  +90%   |
| Normal2x   |    356 |    69 |  5.2×   |  +416%  |
| TV2x       |  413.5 |    71 |  5.8×   |  +482%  |
| AdvMame2x  |  825.5 |    72 | 11.5×   | +1,047% |
| AdvMame3x  |   1665 |    77 | 21.6×   | +2,062% |
| **Hq2x**   | **10,480** | **109** | **96×** | **+9,515%** |

A word on that math, because it is genuinely easy to trip on (I did, at the time). The "percent faster" column is `(before − after) / after`, which is just `speedup − 1` written as a percentage: 1.9× is "+90% faster." That is correct, but do not read "+90%" as "90% less time." The time *reduction* is `(before − after) / before`, which for `Normal` is 47%. Same fact, two framings: the new `Normal` is **1.9× as fast**, equivalently it runs the frame in **~53% of the time**. The ratio (×) is the least confusing, so that is what I lead with now.

And there is the real insight, sitting in that very first row. The changed-region scan costs a roughly **fixed** amount per frame, no matter which scaler runs. So the payoff is proportional to how expensive the per-pixel work you get to *skip* is. For `Normal` (a copy) the scan overhead eats into the gain and you net about 2×. For `Hq2x` (a lookup over a 3x3 neighborhood, the priciest kernel) skipping the unchanged ~95% of the screen is the gap between 10,480 and 109, about **96×**. Cheapen the per-pixel work and this optimization matters less; make it more expensive and it matters enormously. The flashy 9,515% is real, but the quiet `+90%` on a plain copy is the one that tells you what is actually going on.

## Getting it right took eleven tries

That clean "version 4" hides a grind. The [thread](https://www.vogons.org/viewtopic.php?t=10594) is a running changelog of me arguing with the problem:

- **v2** "greatly improves the speed" (the cache lands).
- **v3** fixes artifacts and improves speed.
- **v4** fixes a Warcraft 2 corruption bug (a class of games that updated in ways my span detector mishandled).
- **v6 (RC2)** added modified-chunks *"prediction"*, anticipating which blocks were about to change.
- **v7 (RC3)** folded in gulikoza's "force full redraw" suggestion.
- **v8 (RC4)** "updated region detection speed improvements", which took Hq2x from 109 down to **89**.
- **v9–v11b** chased aspect correction, the fullscreen toggle, double buffering, an OpenGL partial-upload path, and TV scanline modes.

That last category, the OpenGL path, is where the `Rect` earned its keep: instead of re-uploading the whole texture, only the changed bounding box gets pushed to the GPU each frame.

By v11b I wrote, with the particular optimism of someone who has been staring at one file for three weeks: *"This is now truly hopefully the last release candidate."*

## What happened to it

This is the part of the story I have learned not to round off.

The DOSBox regulars were generous. A core admin wrote into the project's official FAQ that, on the subject of speed, *"unless miracles happen (like Kronuz video patch), don't expect much."* People put my custom build, which I served from a machine in my house at `ftp://kronuz.no-ip.com` "only when I'm online," next to the official one.

And then the core team did the most flattering and most deflating thing at once. They liked the idea enough to put it into the next release, **DOSBox 0.65**, but they did not take my patch. They reimplemented the design in their own code. When the changelog came out, the scalers I had added were credited, *"Add more scalers (hq2x/hq3x/sai). (Kronuz),"* but the optimization this whole post is about, the redraw-only-what-changed engine, was in that same list reworded as *"EGA/VGA memory changes detection for faster rendering,"* with no name beside it. I am not in the project's thank-you file either.

I want to be fair: a clean reimplementation by the maintainers is often the right call for a project's long-term health, and the maintainer who did it, Harekiet, built something solid. But I will be honest that, at twenty-seven, watching the part I was proudest of get quietly absorbed and unsigned, it stung. It is a real part of why I drifted away from DOSBox.

It also taught me something I have never let go of since: I care, maybe more than is reasonable, about names staying attached to work. A credit at the bottom of a PostgreSQL manual page. A project I got to *name*. An author line on a Python proposal. If you have read [the longer story](/blog/the-boy-who-kept-opening-the-box/), you know where all of those go. I think they start here, with a scaler that learned to notice what changed, and a teenager who learned the same thing the hard way.

---

*Sources and artifacts: the original thread is [VOGONS t=10594](https://www.vogons.org/viewtopic.php?t=10594) (my [first post](https://www.vogons.org/viewtopic.php?p=71665#p71665), 2005-11-23); the actual patch I dissected here is [`dosbox-optscalers-20051213.diff`](https://www.vogons.org/download/file.php?id=2413). The reimplementation lives in DOSBox 0.65's changelog.*
