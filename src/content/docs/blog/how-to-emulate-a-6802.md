---
title: "How to Emulate a 6802"
subtitle: "A CPU emulator I wrote as a student, reconstructed from memory."
description: "A reconstruction of Emu6802, a Motorola 6802 microprocessor emulator I wrote in C with Watcom and a DOS extender: a full 64K address space, memory-mapped ports redirected to LPT1, a built-in assembler, and single-step tracing. It became courseware at ITM for over a thousand students. The source is lost; this is the design, honestly reconstructed."
excerpt: "As a student I wrote an emulator for the Motorola 6802 in C, with a built-in assembler and single-step tracing. The school adopted it to teach computer architecture to more than a thousand students. The source code did not survive, so this is how it worked, reconstructed."
date: 2026-06-08
draft: true
series: "Opening Boxes"
seriesOrder: 2
tags:
  - opening-boxes
  - emulation
  - assembly
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This one opens an early box, and a sad one: the source code did not survive. I am reconstructing the design from what I remember and from the documentation that did make it.*

One honest caveat before anything else. The source for this project is **gone**. Emu6802 shipped as a binary and a source archive, and only the binary and the documentation were ever archived anywhere I can reach. So unlike the rest of this series, I cannot show you the real code. What I can do is show you how the thing worked, because the documentation that survived is specific, and because emulating an 8-bit CPU is a well-understood shape that I remember building.

## What it was

**Emu6802** was an emulator for the Motorola 6802, an 8-bit microprocessor introduced in 1974 and clocked at 1 MHz. I wrote it as a student in C, compiled with the Watcom C/C++ v11.0 compiler and the **PMODE/W** DOS extender so the host program could run in 32-bit protected mode under plain DOS. (It still compiles today with Open Watcom.) It gave the emulated chip a full **64K of RAM**, **two ports redirected to the PC's LPT1** parallel port, and a small text display, and it shipped with a **built-in assembler**, **single-step code tracing**, memory editing, and save/load of memory images.

It outlived me at the school. From 1999 it was adopted as a teaching tool at the Instituto Tecnológico de Morelia, and over the following seven semesters more than **a thousand students** across two degree programs used it in their Computer Architecture and Digital Systems courses. For years it taught people how a processor actually works, and most of them had no idea a classmate had written it.

## What is inside a 6802

The 6802 is small enough to hold in your head, which is exactly why it makes a good teaching machine. Its entire visible state is a handful of registers:

- two 8-bit accumulators, **A** and **B**, where arithmetic happens;
- a 16-bit index register **X**;
- a 16-bit **stack pointer** SP and a 16-bit **program counter** PC;
- an 8-bit **condition code register** CCR holding the flags (half-carry, interrupt mask, negative, zero, overflow, carry).

There is no separate I/O space. The 6802 talks to the outside world through **memory-mapped I/O**: certain addresses are not RAM, they are devices, and reading or writing those addresses is how you reach a peripheral. That single design choice is the whole reason the emulator could redirect the chip's ports to the PC's LPT1, which I will come back to.

## The core: fetch, decode, execute

An emulator for a CPU this size is, at its heart, one loop. You keep the machine's state in plain variables, you read the byte at the program counter, you switch on it, and you do whatever that opcode says. Then you do it again. The shape, reconstructed:

```c
/* The shape of the core, reconstructed from memory, not the original source. */
uint8_t  mem[65536];          /* the 6802's full 64K address space */
uint8_t  A, B, CCR;           /* accumulators and condition codes */
uint16_t X, SP, PC;           /* index, stack pointer, program counter */

void step(void) {
    uint8_t op = mem[PC++];                 /* fetch */
    switch (op) {                           /* decode */
        case 0x86: A = mem[PC++]; set_nz(A); break;        /* LDAA #imm */
        case 0x8B: A = add(A, mem[PC++]);    break;        /* ADDA #imm */
        case 0x20: PC += (int8_t)mem[PC] + 1; break;       /* BRA  rel  */
        /* ... one case per opcode, ~72 of them ... */
    }
}
```

Those opcodes are real: `0x86` is load accumulator A immediate, `0x8B` is add to A immediate, `0x20` is the unconditional branch. The whole instruction set is about seventy-odd instructions across a handful of addressing modes (immediate, direct, extended, indexed, inherent, and the PC-relative form the branches use). Decoding it is mechanical once you have the table; the education is in writing every case yourself and watching the flags come out right.

```d2 alt="The emulator core loop: the program counter feeds a fetch from 64K RAM, a decode that switches on the opcode, and an execute step that updates the registers and memory-mapped devices, then advances or branches"
direction: down
pc: "Program counter (PC)"
fetch: "Fetch opcode from 64K RAM" {style.bold: true}
decode: "Decode: a big switch on the opcode"
exec: "Execute: update A, B, X, SP, CCR;\nread/write RAM, ports (LPT1), display" {style.bold: true}
pc -> fetch -> decode -> exec
exec -> pc: "advance or branch"
```

## Where it got fun: real I/O

The part students remembered was that the emulated chip could touch real hardware. Because the 6802 uses memory-mapped I/O, the emulator did not need a separate I/O subsystem at all. It only had to notice when a write landed on a port address and forward it:

```c
/* Reconstructed: a write to a port address goes to the PC's LPT1 instead of RAM. */
void store(uint16_t addr, uint8_t val) {
    if (addr == PORT_A || addr == PORT_B)
        outportb(LPT1_BASE, val);   /* the 6802's port becomes the PC's parallel port */
    else
        mem[addr] = val;
}
```

So a program written for the emulated 6802, assembled with the built-in assembler, single-stepped one instruction at a time so you could watch each register change, could light up something physically wired to the parallel port of a real PC. That is the moment computer architecture stops being a diagram on a slide and becomes a machine you are driving by hand.

## What I would tell the student who wrote it

I am sad the source is gone. I would have loved to read my own decode table again, find the corners I got wrong, see how a teenager structured seventy opcodes before he knew the words for any of it. But the loss is also a small, useful lesson that runs through this whole series: ship the source, archive it somewhere that outlives the floppy, and the binary is never the artifact you actually care about. The emulator did its job anyway. It taught a thousand people how a processor thinks, which is more than most code I have written since can claim.

---

*Documented details (chip specs, toolchain, classroom use) are from the surviving Emu6802 project page; the source archive (`emu6802_src.zip`) was never preserved, so the code here is a faithful reconstruction of the design, not the original.*
