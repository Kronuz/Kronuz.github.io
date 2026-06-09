---
title: "The Forbidden Layer"
subtitle: "Before I ever wrote code I was paid for, I learned to read the layer of the machine you are not supposed to touch. Here is what it taught me, and what I am leaving out."
description: "An honest, deliberately non-specific account of learning reverse engineering as a teenager in the 1990s: reading disassembly, the Ralf Brown Interrupt List, self-modifying and polymorphic code, and the run-disassemble-hypothesize-test loop that is the root of every technical thing I have done since. No targets, no how-to-do-harm."
excerpt: "As a teenager I fell in love with the layer of the machine you are not supposed to touch: disassembly, interrupt lists, self-modifying code. This is the honest version, the method and the fascination, with the specific projects left where they belong, in the past."
date: 2026-06-08
draft: true
series: "Opening Boxes"
seriesOrder: 1
tags:
  - opening-boxes
  - assembly
  - reverse-engineering
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This is the first box, the one underneath all the others. I am going to be careful here, and a little vague on purpose, for reasons I will explain.*

This is the part of my story most easily misunderstood, so let me set the terms before I tell it. As a teenager in the 1990s I fell completely in love with the layer of the machine you are not supposed to touch. Not the language you write in. The machine code underneath it, the actual bytes the processor runs, and the system calls beneath *those*. I am going to tell you what that taught me and why it mattered, and I am deliberately **not** going to name specific targets or walk through anything whose only use is to do harm. The specifics stay in the past where they belong. The method, and the fascination, are the parts worth keeping.

## Falling for the layer underneath

Most people meet a program as a thing that runs. I met programs as things that could be **opened**. If you can read the machine code, a compiled binary stops being a sealed box and becomes a text, one you can read even when nobody wanted you to.

So I learned to read **disassembly**, the processor's instructions laid out one at a time, the way the CPU actually sees them. I learned **INT 21h**, the doorway through which a DOS program asked the operating system for anything real, and I lived inside the **Ralf Brown Interrupt List**, that legendary, encyclopedic catalog of every call the hardware would answer if you only knew how to ask. Half of reverse engineering is just knowing the doorways, and the Interrupt List was the map of every door in the building, including the ones that were not documented anywhere else.

And I fell hardest for **self-modifying and polymorphic code**: programs that rewrite their own instructions as they run, so they never look the same twice. I wrote **virii**, in the way a certain kind of curious kid in the '90s wrote them. Not to hurt anyone. Because a program that makes copies of its own cleverness is the most astonishing toy a teenager can imagine, and because writing one forces you to understand the machine at a depth nothing else does. That is the honest reason, and I am not going to dress it up as anything nobler or pretend it away.

## The method, which is the part that lasts

Strip away the targets and what is left is a single loop, and it is the same loop I still run today against a stack trace or an unfamiliar codebase:

```d2 alt="The reverse-engineering loop: run it and watch, disassemble the machine code, decode the system calls via the Ralf Brown list, change a byte and run again to confirm, looping until it makes sense"
direction: down
run: "Run it and watch what it does" {style.bold: true}
dis: "Disassemble: read the machine code"
map: "Decode INT 21h calls via the Ralf Brown list"
test: "Change a byte, run again, confirm" {style.bold: true}
run -> dis -> map -> test
test -> run: "loop until it makes sense"
```

Run it and watch. Disassemble and read what it really does, not what its author says it does. Map the system calls to the catalog so the intent comes into focus. Form a hypothesis. Then **change one byte and run it again** to see if you were right. That last step is the whole thing. You are not reading the machine, you are *interrogating* it, and a single flipped byte that confirms your guess teaches you more than a hundred pages of documentation written by someone who wanted you to believe a particular story.

This is also, exactly, the discipline of debugging anything. The reason I am comfortable in the parts of a system most people route around, the C internals, the dictionary lookup path, the place where a deferred object leaks out of the C world into Python, is that I spent my teenage years convinced that *every* box opens if you are patient enough to read what is actually there.

## The line, and why I keep it

I am not going to pretend the gray was not gray. Some of what a curious kid does at that layer touches things a kid should not touch, and I touched some of them. I am not proud of all of it and I am not going to relitigate it here, partly because the specifics would teach nothing useful and partly because the only responsible version of this story is the one that hands you the *instinct* without handing you a target.

What I will defend, completely, is the instinct itself. The compulsion to open the box, to refuse to accept a system as a sealed surface, to assume there is a readable truth underneath whatever interface you were handed, is the single most valuable thing I have. Pointed at someone else's lock, it is a problem. Pointed at a server that takes fifty seconds to start, or a dictionary implementation that could be a little faster, or a bug that surfaces as the wrong exception type entirely, it is a career. The skill never changed. Only what I aimed it at did.

That is why this is the first box in the series. Everything after it, the [emulator](/blog/how-to-emulate-a-6802/), the [scaler patch](/blog/redraw-only-what-changed/), the [search engine](/blog/a-search-engine-from-scratch/), the [lazy imports](/blog/the-large-black-ball/) that ended up in the Python grammar, is the same teenager reading the forbidden layer, finally invited in through the front door.
