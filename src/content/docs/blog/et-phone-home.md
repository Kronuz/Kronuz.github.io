---
title: "et phone home"
subtitle: "A native control plane for Eternal Terminal"
description: "I gave a machine a handle on a remote box by wrapping Eternal Terminal in a pseudo-terminal and scraping the screen. Every clever thing that wrapper did was a workaround for one fact: et only speaks 'human terminal.' So I stopped scraping and taught et to speak machine, a native control plane called etctl. It is ~1.9x faster to cold-start, ~6.9x faster per call, deletes whole categories of the old hacks, and is built to merge: client-side only, no server or protocol changes."
excerpt: "My first handle on a remote terminal worked by scraping a screen meant for human eyes. Every clever thing it did was a workaround for one fact: et only speaks 'human terminal.' So I built the control plane into et itself. etctl is faster on every axis I measured, deletes whole categories of the old hacks, and is built to be easy to merge upstream. The honest report, with numbers."
date: 2026-06-14
draft: true
featured: true
series: "Driving Eternal"
seriesOrder: 2
tags:
  - driving-eternal
  - tooling
  - automation
  - ai
  - cpp
---

*Part of the **Driving Eternal** series: giving a script or an AI agent a real handle on a remote terminal. The [first part](/blog/a-pair-of-missing-hands/) is the problem; this one is the fix, and an open invitation to merge it.*

In the last part, an agent sat in front of a terminal it could not drive, and I went looking for a handle a machine could hold. This part is the handle.

The first version was a Python wrapper I called etch. It ran [Eternal Terminal](https://eternalterminal.dev/) inside a pseudo-terminal, kept a warm session, and scraped the rendered screen to hand a script back clean output and a real exit code where before there was a wall of color codes and tea leaves. I was proud of it.

Then I lived with it, and I kept seeing it for what it was. Every clever thing etch did was a workaround for a single fact: `et` only speaks one language, the rendered screen, the one meant for human eyes. etch stood outside that screen with its nose against the glass, reading.

This is the part where I stopped reading the glass and taught the terminal to speak machine.

## Everything etch had to fake

Look at what it took to fake a clean channel out of a screen. etch ran `et` inside a pseudo-terminal and then spent its whole life undoing what a terminal is for. It neutralized the shell prompt so the fancy [Powerlevel10k](https://github.com/romkatv/powerlevel10k) banner would stop bleeding into the output. It stripped ANSI escape codes by hand. It wrapped every command in `printf` sentinels to carve the real output and exit code out of the stream. It chunked long lines so the kernel's input cap would not silently truncate them. When a command wedged, it resynced the session with a fresh nonce. And it paid for a Python interpreter to start on every single call.

None of that is `et`. All of it is etch reaching around `et` to reconstruct, from a picture of a screen, the structured thing that `et` already had on the inside and never offered to anyone.

Two bugs in real use were the same shape, twice. A piped stdin that hung. A kilobyte-long line that the PTY's canonical mode chopped, leaving truncated junk that poisoned the warm channel until a full stop-and-sweep. Both were a scraper guessing at a stream built for eyes, and guessing wrong at an edge I would never have hit by hand. I fixed them. But the fixes were better guesses, not a different idea.

The different idea was to stop guessing. `et` has the clean byte stream inside it. I just could not reach it from outside.

## So I went inside

`et` is open source, and it was already running on my machine, so the right fix was not a smarter wrapper. It was a seam that turned out to be already there.

Eternal Terminal abstracts the local terminal behind a small interface it calls a `Console`. The entire interactive client only ever does three things through it: read your keystrokes, write the server's output to the screen, and ask how big the window is. Normal `et` plugs a real tty into those three methods. So I wrote a different one. `et --ctl` plugs in a `Console` that, instead of a tty, takes its input from a pipe I can inject bytes into and keeps the server's output in a scrollback buffer I can read back. The client driving the session never noticed. Not one line of the server, the wire protocol, or the session loop changed.

On top of that swap, `et --ctl --name main user@host` backgrounds the client with no terminal attached and has it listen on a per-user unix socket at `~/.et/ctl/main.sock`. A small native CLI, `etctl`, talks to that socket. That is the whole shape.

```d2 alt="etch wrapped et from outside in a pseudo-terminal and scraped the rendered screen. etctl instead talks to a backgrounded 'et --ctl' client over a local unix socket, reading et's native byte stream; that client maintains the normal encrypted Eternal Terminal session to etserver and the remote shell."
direction: right
agent: "agent / script"
etch: "etch.py\nPTY wrapper\n(scrapes the screen)" { style.stroke-dash: 3 }
etctl: "etctl\n(native CLI)"
sock: "~/.et/ctl/main.sock\n0600, getpeereid" { shape: cylinder }
daemon: "et --ctl\nbackgrounded client\n(auto-reconnecting)"
remote: "etserver → etterminal → shell" { shape: document }
agent -> etctl
etctl -> sock -> daemon
daemon -> remote: "normal encrypted ET"
agent -> etch -> remote: "the old way (scrape)" { style.stroke-dash: 3 }
```

Because the backgrounded `et` is just an Eternal Terminal client, it reconnects on its own across network drops, the same way a human's session does. The durability I had hand-rolled in etch came for free, because this time it was not hand-rolled. It was the thing `et` already does.

All of it, the control mode, the socket, the cursored scrollback, the CLI, came together over a weekend. Not because the code was trivial, but because the seam was already cut. I was plugging into `et`, not prying it open.

The verbs an agent uses are the same ones etch had, because that vocabulary was right: `run` for a command that finishes (clean output, real exit code), `script` for a multi-line block, `write` and `expect` and `read` for a prompt that waits, `peep` to tap the live exchange, `observe` and `attach` to take the wheel by hand. What changed is everything underneath. There is no prompt to neutralize, no ANSI to strip, no resync, no line-cap chunking, and no Python process per call. It reads `et`'s native byte stream over a local socket, locked to my user (`0700` directory, `0600` socket, and the daemon checks the peer's uid). The hacks did not get better. They became unnecessary.

```bash
H=you@devbox
etctl open main $H                      # background (or reuse) the 'main' session
etctl run  main 'cd ~/work && make'     # clean stdout + the real exit code
etctl run  main 'systemctl is-active nginx' && echo up
```

One thing did survive the move, honestly: `run` still wraps a command in `printf` sentinels to capture clean output, and the remote shell still echoes that framing into the transcript. `run`'s own stdout is clean, but a `peep` of the session is noisier than what a human would type. That is a property of the remote shell's line editor, not of the scrape, so going native did not buy it back. I would rather say so than pretend it is gone.

## The bug that wasn't

I benchmarked the new thing against the old one on identical tasks, both driving the same remote host across a real network, real round-trips and a real shell. The first interactive run came back damning: `etctl` looked about **nineteen times slower** than etch on the prompt cycle, ten full seconds an iteration. I started writing the autopsy. I had a theory, too, something principled about a stateless `expect` racing the output.

My theory was wrong, and so was the benchmark. The test prompt was `read -p 'Q? ' a`. `read -p` is a [bash](https://www.gnu.org/software/bash/) idiom, and the box's login shell is [zsh](https://www.zsh.org/), where `-p` means "read from a coprocess" and the line just errors out. The token I was waiting for never printed, so `expect` did the correct thing and waited the full ten-second timeout. etch had only looked like it passed because its looser matching latched onto the echoed command line instead of the answer. Swap in a portable prompt, `printf 'Q? '; read a`, and both tools work, and `etctl` is the faster one.

There was a real finding hiding behind the fake one. A stateless `expect` does start scanning at the session's current head, and in a tight write-then-wait loop the awaited bytes can land in the gap between the write returning and the `expect` sampling. Over a network round-trip it almost never bites, because the output takes longer to come back than the gap lasts. On a fast or pre-buffered session it can. The fix is to capture the cursor before you write and tell `expect` to scan from there, which costs one extra round-trip, about thirty milliseconds, and is now the documented default for loops. The lesson was the one the live testing keeps teaching: measure against the real host and the real shell. A piped local bash would never have found the zsh failure.

## The numbers

Median wall-clock, lower is better, both tools driving the same `etserver` over the same network. `etctl/etch` below 1.0 means `etctl` is faster.

| Task | etch | etctl | etctl / etch |
| --- | ---: | ---: | ---: |
| Cold start (spawn + first command) | 7139.9 ms | 3755.1 ms | **0.53x** |
| Warm `run echo hello` (x15) | 219.7 ms | 195.5 ms | 0.89x |
| Warm `run hostname; id -un` (x10) | 275.5 ms | 200.2 ms | **0.73x** |
| Output-heavy `run seq 1 3000` (x5) | 224.2 ms | 222.7 ms | 0.99x |
| Interactive prompt cycle (x7) | 542.5 ms | 318.5 ms | **0.59x** |
| Local CLI startup (`--help`, x20) | 106.3 ms | 15.5 ms | **0.15x** |

The steady-state command runs are network-bound, so the wins there are modest and honest: both tools are mostly waiting on the same round-trip to the host, and `etctl` shaves a consistent slice off the top by not starting a Python interpreter and not scraping a screen. Streaming three thousand lines is a tie, which is the right answer, the cursored scrollback adds no measurable tax on bulk reads.

The number I care about most is the last row. A `etctl` invocation starts in about **15 milliseconds** against etch's **106**, because one is a native binary already part of the `et` build and the other is a Python import. That is roughly **90 milliseconds saved on every single call**, and an agent driving a host issues a great many small calls. It is the kind of fixed cost that rounds to nothing in a demo and adds up to real time across a day of automated work.

## Where etch is still ahead

This is an honest report, so the column where etch wins matters as much as the table.

**Maturity.** etch has months of real agent sessions behind it. `etctl` is a working prototype: the [Catch2](https://github.com/catchorg/Catch2) suite passes 433 assertions across 26 cases and every flow has run against a real `etserver`, but it has almost no mileage. Speed is not robustness, and the interactive race above is exactly the class of bug that only daily use flushes out. etch earned my trust the hard way; `etctl` has not yet.

**Persistence.** Neither tool survives a reboot today. Both daemons die with the host process. The design for reattaching across a restart is sketched and parked, and until it exists, this is the one capability where `etctl` is not yet strictly better than etch, only faster.

**Deployment.** etch is a single portable script with no dependencies. `etctl` is a binary that has to be built per platform, because it ships inside `et`. That is a real cost the script does not have.

So I am not retiring etch. I am running both side by side, with `etctl` as the fast path and etch as the fallback that has never let me down, and I will let the prototype earn its mileage the same way the script did, by getting used hard.

## Built to merge

I built this to be easy to say yes to. It is client-side only: the change lives entirely in the `et` client, swapping one `Console` implementation and adding a control socket. Not a line of `etserver`, `etterminal`, or the wire protocol changed, so it cannot regress an existing session, and `et` without `--ctl` behaves exactly as it always has. The whole thing is a handful of new files and three small touches to the launch path.

It lives on a branch today, with a green test suite and real mileage still ahead of it. If you maintain or lean on [Eternal Terminal](https://github.com/MisterTea/EternalTerminal), I would love to see something like this land upstream, so the next person who needs to drive a session from a script finds it already there, speaking their machine's language, instead of scraping the glass like I did.

## Cut in, not scratched on

I named etch for two things at once: `et` plus the channel it held, and the verb, to etch, to cut something in so it stays. The script cut the channel from the outside, scratched onto the surface of a screen with a careful tool and a steady hand.

`etctl` cuts it into the tool itself. The [pair of hands](/blog/a-pair-of-missing-hands/) an agent was missing, the clean channel the Python wrapper scraped together, all of it is now a few hundred lines living inside Eternal Terminal, speaking machine in its own voice instead of miming it through glass. The handle did not just get faster. It stopped being a thing bolted on and became part of the thing it drives.

That is the move I keep coming back to. When a tool only talks to people, you can stand outside and scrape, and that gets you surprisingly far. But the real answer, when you can reach it, is to teach the tool to talk to machines too. Then nobody has to read the glass.
