---
title: "The Forbidden Layer"
subtitle: "Learning to read the machine you're told not to touch."
description: "An honest, deliberately non-specific account of learning reverse engineering as a teenager in 1990s Mexico City: the zines, the BBS scene, the assembly I wrote, the viruses I never released, SoftICE and the disassemblers, and the run-disassemble-hypothesize-patch loop that is the root of everything I have built since. No targets, no how-to-do-harm."
excerpt: "As a teenager I fell in love with the layer of the machine you are not supposed to touch: disassembly, SoftICE, the assembly I wrote and the viruses I never released. This is the honest version, the thrill of finding the parts that were not meant to be found, with the specific targets left where they belong, in the past."
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

This is the part of my story most easily misunderstood, so let me set the terms before I tell it. As a teenager in 1990s Mexico City I fell completely in love with the layer of the machine you are not supposed to touch. Not the language you write in. The machine code underneath it, the actual bytes the processor runs, and the system calls beneath *those*. I am going to tell you what that taught me and why it mattered, and I am deliberately **not** going to name specific targets or walk through anything whose only use is to do harm. The specifics stay in the past where they belong. The method, and the fascination, are the parts worth keeping.

## The scene

None of this happened in a vacuum. It happened over a modem, at night, on the **BBS** boards of Mexico City: *Tierras Extrañas*, *Coyoacán BBS*, *HAL-9000*, and pretty much every other board in the city at one point or another. You dialed in, you traded files and arguments with people you only knew by handle, and later, when the internet arrived, the same crowd moved onto IRC, onto FreeNode and a dozen channels. It was the most generous education I ever got, and almost none of the teachers used their real names.

The reading material came from the same places. **Phrack**, the canonical hacker journal. **40Hex**, where the virus-writing groups published their craft. **29A**, the legendary group whose zine had a strong Spanish-speaking core, which mattered to a kid like me. **Raregazz**, closer to home in the Latin American scene. **2600** when I could get it. And underneath all of them, the two references I actually lived in: **Ralf Brown's Interrupt List** and the **Intel assembly manuals**. Between a zine that explained *why* something worked and a manual that told you *exactly* how the instruction behaved, you could teach yourself anything.

## Reading it, then writing it

Most people meet a program as a thing that runs. I met programs as things that could be **opened**. If you can read the machine code, a compiled binary stops being a sealed box and becomes a text, one you can read even when nobody wanted you to.

So I learned to read **disassembly**, the processor's instructions laid out one at a time, the way the CPU actually sees them. I learned **INT 21h**, the doorway through which a DOS program asked the operating system for anything real, and I learned to find every other doorway in Ralf Brown's List, including the undocumented ones nobody else wrote down.

But reading was only ever half of it. I also **wrote** assembly, by hand, in TASM and MASM, stepping through it in Turbo Debugger, dropping into C with Borland and Watcom when I wanted the comfort. And I wrote **viruses**, in the way a certain kind of curious kid in the '90s did. I started with the simple case, **COM** files, where the whole program is one flat segment, then moved to **EXE**, with its real relocations and headers. I wrote **polymorphic** code, programs that rewrite their own instructions so two copies never look the same, and I learned to slip past the antivirus scanners of the day, which was its own puzzle: understand exactly what the scanner looks for, then become the thing it cannot recognize.

I want to be precise about the ethic, because it is the whole point. I **never released any of it**. Not one. The thrill was never in setting something loose. It was in the act of creation itself, the strange vertigo of building something genuinely dangerous, a little self-replicating machine that could very easily get away from you, and choosing not to let it. That feeling, *I have made something that could escape, and it will not, because I say so*, taught me more about responsibility than any lecture ever did.

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

The tools made it physical. **SoftICE** was the holy grail, a debugger that lived *below* the operating system, so you could freeze the entire machine mid-instruction and read its mind. Alongside it, **W32Dasm** and **IDA** to lay a binary out as readable code, and **HIEW** and **BIEW** to edit the bytes of an executable directly. With those you could set a breakpoint exactly where a program made a decision, single-step until you found the precise instruction that checked something, and then **change one byte** to make it decide differently.

That last step is the whole craft. A conditional jump is one byte; flip it and "if the check fails" becomes "if the check passes." Once, with SoftICE, I traced a game down to the instruction that enforced a hard limit on how many units you could select at a time and patched the cap away. Harmless, and a perfect miniature of the entire discipline: find the rule, find where it physically lives, change it. The reward was always the same small electric jolt, the thing this article is named for: **finding the parts that were not meant to be found.**

## The line, and why I keep it

I am not going to pretend the gray was not gray. The same skill that reads a game's unit cap reads anything, and the curiosity did not stop at software. It ran into hardware, into the little **smartcards** that guard things in the physical world, into the boundaries of *access* itself, the locks that are not made of code. Some of what a curious kid does at that layer touches things a kid should not touch, and I touched some of them. I am not proud of all of it, I am long past it, and I am deliberately not going to detail it here, partly because the specifics would teach nothing useful and partly because the only responsible version of this story is the one that hands you the *instinct* without handing you a target or a method.

What I will defend, completely, is the instinct itself. The compulsion to open the box, to refuse to accept a system as a sealed surface, to assume there is a readable truth underneath whatever interface you were handed, is the single most valuable thing I have. Pointed at someone else's lock, it is a problem. Pointed at a server that takes fifty seconds to start, or a dictionary implementation that could be a little faster, or a bug that surfaces as the wrong exception type entirely, it is a career. The skill never changed. Only what I aimed it at did.

That is why this is the first box in the series. Everything after it, the [emulator](/blog/how-to-emulate-a-6802/), the [scaler patch](/blog/redraw-only-what-changed/), the [Sass compiler](/blog/css-that-computes/), the [search engine](/blog/a-search-engine-from-scratch/), the [lazy imports](/blog/the-large-black-ball/) that ended up in the Python grammar, is the same teenager reading the forbidden layer, finally invited in through the front door.

## The zines, if you want to read them

If any of this made you curious about the actual texts, here is where they live. I read all of these:

- **Phrack** is still online at [phrack.org](http://phrack.org/), issue by issue.
- **2600: The Hacker Quarterly** is at [2600.com](https://www.2600.com/).
- **Ralf Brown's Interrupt List**, the reference I lived in, is mirrored at [Ralf Brown's pages](https://www.cs.cmu.edu/~ralf/files.html).
- The virus-writing zines, **40Hex** and **29A**, are historical artifacts now, archived for study (text, not the live payloads) at places like [textfiles.com](http://textfiles.com/magazines/) and the [vx-underground](https://vx-underground.org/) archives.
- **Raregazz** and the rest of the Latin American scene survive in scattered e-zine archives.

*(I'd like to mirror the freely-redistributable text ones, Phrack and Raregazz, directly on this site behind a readable viewer. That viewer is the next thing I'm building, so for now these are links.)*
