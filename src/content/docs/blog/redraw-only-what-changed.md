---
title: "Redraw Only What Changed"
subtitle: "A DOSBox scaler experiment that went much further than expected."
description: "In 2005 I proposed teaching DOSBox's scalers to skip unchanged pixels. I remember being told it probably would not matter. The patch reached 96x in one benchmark and helped shape the change-detecting renderer that replaced it."
excerpt: "DOSBox redrew the whole screen every frame, even when almost nothing moved. I remember being told that detecting changes at the scaler layer probably would not matter. So I measured it."
date: 2026-06-08
authors: kronuz
draft: true
featured: true
series: "Opening Boxes"
seriesOrder: 3
tags:
  - opening-boxes
  - retrocomputing
  - performance
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This one opens the [DOSBox](https://www.dosbox.com) box.*

Sometime in 2005, I brought an idea to the DOSBox developers.

Most of the screen in an old game does not change from one frame to the next. A character moves. A door opens. A health bar ticks. The rest of the image just sits there.

DOSBox had several scalers that could enlarge those tiny old game screens. Some were cheap. Others, especially Hq2x, did considerably more work to produce a cleaner image.

My question was simple: why run the scaler again over pixels whose input had not changed?

I remember discussing the idea on `#dosbox` IRC before I wrote the patch. The logs appear to be lost, and this was more than twenty years ago, so I cannot quote the conversation or reliably tell you which developer I was talking to.

What I remember is the sentiment: DOSBox's rendering plumbing was already very efficient, and adding change detection at the scaler layer was unlikely to make a meaningful difference.

The answer felt a little cocky, which was probably part of why it stuck with me. Maybe they were right. There was only one useful way to find out, so I measured it.

## Remember the last frame

Hq2x looked good for the same reason it was expensive. Instead of simply turning one source pixel into a larger square, it examined a 3x3 neighborhood and used the pattern around the pixel to decide how to blend the enlarged output.

On my Pentium 4 at 3 GHz, Hq2x took about **10,480** of my timing units over roughly 5,000 frames. DOSBox's simple `Normal` scaler took **127.3**.

Hq2x was doing around eighty times the work of the simple path.

The waste became obvious once I stopped looking at scalers and started looking at frames. DOSBox processed the whole image every time, even when most of it was identical to the previous frame.

My idea was to keep a copy of the previous source image, compare each new frame against it, and give the scaler a map of what had actually changed.

```d2 alt="The patched rendering path compares against the previous frame, finds changed spans, scales those spans, and updates the changed area"
direction: down

emu: "New VGA frame"
cache: "Previous-frame\nsource cache" {
  style.stroke-dash: 3
}
keeper: "CacheKeeper\nfind changes" {
  style.bold: true
}
bm: "BlockMap\nchanged spans"
rect: "Rect\nchanged area"
scaler: "Scaler kernel\nchanged spans only" {
  style.bold: true
}
out: "SDL / OpenGL\npartial update"

emu -> keeper
cache -> keeper: "compare"
keeper -> bm
keeper -> rect
bm -> scaler
scaler -> out
rect -> out
```

The source cache remembered the last frame. `BlockMap` stored changed spans as `[start, end]` pairs for each source line, while a `Rect` wrapped the changed area for the display backend. The expensive work could now shrink with the amount of movement on screen.

## `CacheKeeper`

On November 23, 2005, I submitted the first patch to the [official DOSBox tracker as patch #142, "Scalers performance boost"](https://sourceforge.net/p/dosbox/patches/142/).

My description was blunt:

> "What I did is basically modify the scalers so they update only the parts of the screen that really changed since the last time they were processed."

I also posted it to [VOGONS](https://www.vogons.org/viewtopic.php?p=71665#p71665), then started changing it almost immediately.

The heart of the patch was a function called `CacheKeeper`. I had marked the section with a comment I still smile at:

```c
// Cache management stuff. Added by Kronuz:
```

The central loop, lightly trimmed, looked like this:

```c
static INLINE SRCTYPE* CacheKeeper(const SRCTYPE *src, SRCTYPE *cache) {
    if (Scaler_RebuildCache) {
        BlockMap[0] = 0;

        Bitu *bm = BlockMap + 1;
        Bitu base = 0, chunk = CACHE_CHUNKS;

        for (Bitu xx = 0; xx < Scaler_SrcWidth; ) {
            if (GCC_UNLIKELY(
                *((Bit32u*)&cache[xx]) != *((Bit32u*)&src[xx])
            )) {
                if (GCC_UNLIKELY(!base)) {
                    base = !base;
                    bm[0] = xx;
                    ++BlockMap[0];
                }

                xx += chunk;
                chunk <<= 1;
            } else {
                if (GCC_UNLIKELY(base)) {
                    base = !base;
                    bm[1] = xx;

                    memcpy(
                        &cache[bm[0]],
                        &src[bm[0]],
                        (bm[1] - bm[0]) * SRCSIZE
                    );

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

The common case was that nothing changed, so the loop compared source and cached data four bytes at a time. Once it found movement, it used increasingly large jumps to cross the changed region, recorded the span in `BlockMap`, and copied only that span into the cache. The scaler ran its kernel only over those ranges.

The trick was not to make Hq2x cheaper. It was to stop calling it for pixels whose answer we already knew.

## Pixels lie

The first version of "unchanged" was wrong.

Warcraft II helped prove it.

Many old games use an 8-bit framebuffer. A pixel is not a final RGB color, but an index into a palette. The framebuffer can remain byte-for-byte identical while a palette change produces a fade, a flash, or a cycling water effect.

My cache could look at two frames and confidently declare them identical while the entire screen had changed color.

Version 4 fixed that. The palette-aware path checked both the source bytes and the palette entries referenced by them:

```c
if (*((Bit32u*)&cache[xx]) != *((Bit32u*)&src[xx]) ||
    Scaler_PaletteDiffs[cache[xx]]   ||
    Scaler_PaletteDiffs[cache[xx+1]] ||
    Scaler_PaletteDiffs[cache[xx+2]] ||
    Scaler_PaletteDiffs[cache[xx+3]]) {
    /* changed */
}
```

Same index, different color meant the pixel was dirty.

Hq2x found another hole. Its answer depends on a 3x3 neighborhood, so an unchanged pixel may still need recalculation when a neighbor moves. The question was no longer whether a pixel changed, but whether anything that could affect its output had changed.

Palette changes, neighborhood dependencies, fullscreen transitions, double buffering, different output backends: each made "redraw only what changed" less simple than the sentence.

## 96x

The version 4 numbers looked like this. These were low-action platform games, timed over roughly 5,000 frames. Lower is better.

| Scaler | Before | After | Speedup | Time reduction |
| --- | ---: | ---: | ---: | ---: |
| Normal | 127.3 | 67 | **1.90x** | **47.4%** |
| Normal2x | 356 | 69 | **5.16x** | **80.6%** |
| TV2x | 413.5 | 71 | **5.82x** | **82.8%** |
| AdvMame2x | 825.5 | 72 | **11.47x** | **91.3%** |
| AdvMame3x | 1,665 | 77 | **21.62x** | **95.4%** |
| **Hq2x** | **10,480** | **109** | **96.15x** | **98.96%** |

The Hq2x result was a **96.15x speedup**, or a **98.96% reduction in scaler execution time**. The optimized path took just 1.04% of the time used by the original one.

In 2005 I reported that as **9,515% faster** and helpfully added that "a 100% improvement is equivalent to twice the speed." The arithmetic was consistent with the formula I was using, but it was an unorthodox way to present a performance result. I would report the speedup ratio and execution-time reduction today.

Also, 96x is quite enough.

The speedup column tells only half the story. Before the patch, the timings ranged from 127.3 for `Normal` to 10,480 for Hq2x, an 82x spread. After the patch, they ranged from 67 to 109.

On these mostly static frames, I had almost flattened the cost of the scaler.

Hq2x was still vastly more expensive when it actually ran. It simply spent most of its time not running.

That is why `Normal` is the result I find more interesting now. It was already cheap, close to a copy, and the patch still made it **1.90x faster**. The change scan had a roughly fixed cost, so with `Normal` it consumed much of the gain. With Hq2x, every skipped pixel avoided a lookup-heavy neighborhood analysis.

The same detector sat in front of both. As the scaler became more expensive, not calling it became more valuable, until the scaler's own complexity was almost irrelevant on a mostly static frame.

The numbers had answered the IRC conversation better than I ever could.

## Eleven versions

The clean explanation above is what you get after the bugs have names.

The [VOGONS thread](https://www.vogons.org/viewtopic.php?t=10594) grew past two hundred posts. Version 4 fixed Warcraft II and palette changes. Version 7 included work with **gulikoza** to skip entire unchanged frames. Version 8 pushed Hq2x from 109 to **89** in one test. Later revisions chased fullscreen, double buffering, TV modes, and partial OpenGL uploads.

People broke the patch on games and hardware I did not own, measured it, and folded it into CVS builds. A DOSBox FAQ answer about future speed improvements eventually said:

> "unless miracles happen (like Kronuz video patch), don't expect much."

Duke Nukem 3D was measured at nearly twice the performance. By then the scaler layer had made its case.

## January 30

For years, my memory of the ending was fuzzy.

My patch did not go into DOSBox CVS. DOSBox later gained similar functionality through a different implementation, and my patch stopped being necessary.

In 2026 I went back through the forum, the SourceForge ticket, and an [unofficial Git mirror of the DOSBox history](https://github.com/jwilk-mirrors/dosbox).

On January 30, 2006, at 09:54 UTC, Sjoerd van den Berg, **Harekiet**, committed SVN revision 2442.

The title was:

> **Scaler rewrite for detecting changes**

The commit message included:

> **Only updaterect the changed parts in sdl**

Four minutes later, revision 2444 landed with the same title. That was the large renderer implementation, with **1,415 additions and 810 deletions** across the scaler and rendering code.

The mirror preserves the revisions as [`b24a1fb`](https://github.com/jwilk-mirrors/dosbox/commit/b24a1fb72f8fb51a6390f2392eab0887d2cf6df5) and [`7623888`](https://github.com/jwilk-mirrors/dosbox/commit/762388813c5c5cb2b7d5502bb84d6f7ad8c75b19).

The new renderer had `scalerSourceCache`, `scalerChangeCache`, and `Scaler_ChangedLines`. It cached source data, detected changed blocks, avoided recalculating unchanged output, handled neighborhood effects, and passed changed-line information to SDL.

This was not my patch. My code stored changed spans in a `BlockMap`; Harekiet used several caches and block-oriented change propagation as part of a much larger rendering rewrite. He wrote the code that shipped.

Still, the central move was familiar: remember the previous source, find what changed before expensive scaler work, recalculate affected regions, and update only changed output.

## What the record says

The VOGONS thread records the reaction when the rewrite landed.

One user tried to apply my patch and got **29 failed hunks**. He asked me to update what he called a "great" and "vital" patch.

Then somebody relayed a message Qbix had posted in a beta-tester-only forum:

> "the partial screenupdates is comparable to kronutz work. Although it should be even faster..."

Yes, `kronutz`.

Users tested the new CVS code. One reported:

> "performance is very comparable to the Kronuz patch now."

Another called it:

> "the biggest improvement in CVS in a long time."

My patch had become obsolete because DOSBox now did the job itself.

There was one more piece of the record I had forgotten.

On February 12, Qbix returned to [patch #142](https://sourceforge.net/p/dosbox/patches/142/) and wrote:

> "Something like this is in the cvs."

Then:

> "Thanks for helping creating it."

I had not read those words in twenty years, and they settled something for me.

I no longer had to infer the connection from two pieces of code. The patch was in the official tracker, Qbix compared the new partial updates to my work, and then thanked me for helping create what was in CVS.

The implementation was Harekiet's. My work had helped create what replaced it.

## The unsigned line

There is a small wrinkle in my own memory here.

I remembered Hq2x as one of "my" DOSBox scalers. The DOSBox changelog does, in fact, credit me with:

> "Add more scalers (hq2x/hq3x/sai). (Kronuz)."

But that work came later. In May 2006, months after the performance patch and the January renderer rewrite, I posted another scaler patch adding Hq2x, Hq3x, and the SAI family to the then-current DOSBox code. There had also been an earlier Hq2x patch by another contributor, Moe, in 2004.

So Hq2x was not my invention, and bringing those scalers into the release was not what led me to the 2005 optimization. Memory had compressed two pieces of my DOSBox work into one.

The changelog still makes the contrast interesting.

My scaler work has my nickname beside it:

> "Add more scalers (hq2x/hq3x/sai). (Kronuz)."

The change-detection work appears elsewhere:

> "EGA/VGA memory changes detection for faster rendering."

No name beside it.

I cannot say Harekiet copied my code. I have looked at his implementation, and it is his. I also cannot say anyone deliberately removed my name. The old IRC logs are gone, and I do not know what conversations happened inside the project.

I did not write the DOSBox renderer that shipped, and that is not the credit I am looking for.

What I wish the visible release history had preserved is that the changed-region work followed an experiment I had proposed, built, measured, and developed in public. Two months later DOSBox rewrote its scaler architecture around detecting changes, and Qbix later thanked me for helping create what was in CVS.

The project record preserved the connection, just in the basement: a closed SourceForge ticket, a 228-post forum thread, and a beta-tester quote copied into a public reply.

The release changelog kept the result and lost the path to it.

At twenty-seven, I did not have this tidy reconstruction. I only knew that I had spent weeks on something I was proud of, watched people use it, and then watched my patch become unnecessary almost overnight.

That was exactly what I had wanted for DOSBox, and somehow it still hurt. Not long after, I drifted away.

## Names on things

I think something from that experience stayed with me.

Years later, I cared about the credit at the bottom of a PostgreSQL manual page. I cared about getting to name a project. I cared about the author line on a Python proposal.

If you have read [the longer story](/blog/the-boy-who-kept-opening-the-box/), you know where those go.

For a long time I thought that instinct was vanity. Some of it probably is.

But code has a peculiar way of eating its own history. A patch gets rewritten. A branch disappears. The clean implementation survives because that is the point of good engineering, while the failed attempts, the measurements, and the odd experiment that made someone say *maybe we should do this properly* scatter into old forums and dead IRC logs.

Twenty years later, I am glad patch #142 was still there.

The scaler learned to notice what changed.

I am still learning to notice what gets lost.

---

*Sources and artifacts: [DOSBox patch #142, "Scalers performance boost"](https://sourceforge.net/p/dosbox/patches/142/) was created on November 23, 2005 and preserves the patch revisions and Qbix's February 12, 2006 closing comment. The public engineering discussion is the VOGONS thread ["Graphics performance boost"](https://www.vogons.org/viewtopic.php?t=10594), beginning with [my first post](https://www.vogons.org/viewtopic.php?p=71665#p71665). The patch dissected here is [`dosbox-optscalers-20051213.diff`](https://www.vogons.org/download/file.php?id=2413), version 11b. The January 30 upstream work is preserved in the historical Git mirror as [`b24a1fb`](https://github.com/jwilk-mirrors/dosbox/commit/b24a1fb72f8fb51a6390f2392eab0887d2cf6df5), SVN r2442, and [`7623888`](https://github.com/jwilk-mirrors/dosbox/commit/762388813c5c5cb2b7d5502bb84d6f7ad8c75b19), SVN r2444. The DOSBox changelog credits my later scaler work, and the earlier [Hq2x patch #54](https://sourceforge.net/p/dosbox/patches/54/) is preserved in SourceForge.*
