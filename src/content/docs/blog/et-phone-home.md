---
title: "ET Phone Home"
subtitle: "A native control plane for Eternal Terminal"
description: "Eternal Terminal only ever spoke one language, the rendered screen, so a script or an agent had to stand outside and scrape it. This is how I taught et to speak machine instead: a control Console swapped in behind the client, a per-user socket, and a native CLI called etctl. A 3.7 second cold start, a 15 millisecond per-call floor, honest limits, and client-side only so it is easy to merge upstream."
excerpt: "A terminal is built end to end for eyes and fingers, which is exactly what locks out everything that has neither. Rather than keep scraping the screen from outside, I went looking for a seam inside Eternal Terminal and found one already cut. etctl is what came out: a native control plane, the numbers behind it, the file transfer that fought back, and the parts that are still only a prototype."
date: 2026-08-02
featured: true
series: "Driving Eternal"
seriesOrder: 3
tags:
  - driving-eternal
  - eternal-terminal
  - tooling
  - automation
  - ai
  - cpp
---

In the last part, an agent sat in front of a terminal it could not drive, I wrote a Python wrapper that scraped the screen from outside, and I ended up convinced the wrapper was the wrong idea. This part is the right one.

`et` speaks one language: the rendered screen, the one meant for human eyes. Everything else follows from that. A script cannot ask it for the exit code of the command it just ran, because there is no channel that carries one. The information exists, clean and structured, inside the client. It just never comes out anywhere a machine can reach.

This is the part where I stopped reading the glass and taught the terminal to speak machine.

## So I went inside

`et` is open source, and it was already running on my machine, so the right fix was not a smarter wrapper. It was a seam that turned out to be already there.

Eternal Terminal abstracts the local terminal behind a small interface it calls a `Console`. The entire interactive client only ever does three things through it: read your keystrokes, write the server's output to the screen, and ask how big the window is. Normal `et` plugs a real tty into those three methods. So I wrote a different one. `et --ctl` plugs in a `Console` that, instead of a tty, takes its input from a pipe I can inject bytes into and keeps the server's output in a scrollback buffer I can read back. The client driving the session never noticed. Not one line of the server, the wire protocol, or the session loop changed.

On top of that swap, `et --ctl --name main user@host` backgrounds the client with no terminal attached and has it listen on a per-user unix socket at `~/.et/ctl/main.sock`. A small native CLI, `etctl`, talks to that socket. That is the whole shape.

```d2 alt="etctl sends input to and reads output from a backgrounded 'et --ctl' client over a local unix socket; that client maintains the normal encrypted Eternal Terminal session down to etserver, etterminal, and the remote shell."
direction: down
agent: "agent or script (no tty)"
etctl: "etctl, the native CLI"
daemon: "et --ctl, backgrounded and auto-reconnecting" { style.bold: true }
remote: "etserver, etterminal, shell" { shape: document }

agent -> etctl
etctl -> daemon: "~/.et/ctl/main.sock\n0600, uid-checked"
daemon -> remote: "encrypted ET"
```

Because the backgrounded `et` is just an Eternal Terminal client, it reconnects on its own across network drops, the same way a human's session does. The durability I had hand-rolled in etch came for free, because this time it was not hand-rolled. It was the thing `et` already does.

All of it, the control mode, the socket, the cursored scrollback, the CLI, came together over a weekend. Not because the code was trivial, but because the seam was already cut. I was plugging into `et`, not prying it open.

The verbs are the ones the prototype had already settled, because that vocabulary was right: `run` for a command that finishes (clean output, a real exit code, and a multi-line body that runs as one unit), `write` and `writeln` and `expect` and `read` for a prompt that waits, `key` for the named keys and signals, `sniff` to tap the live exchange, `observe` and `attach` to take the wheel by hand. What changed is everything underneath. There is no prompt to neutralize, no ANSI to strip, no resync, no line-cap chunking, and no Python process per call. It reads `et`'s native byte stream over a local socket, locked to my user (`0700` directory, `0600` socket, and the daemon checks the peer's uid). The hacks did not get better. They became unnecessary.

```bash
H=you@devbox
etctl open main $H                      # background (or reuse) the 'main' session
etctl run  main 'cd ~/work && make'     # clean stdout + the real exit code
etctl run  main 'systemctl is-active nginx' && echo up
```

One thing did survive the move, honestly: `run` still wraps a command in `printf` sentinels to capture clean output, and the remote shell still echoes that framing into the transcript. `run`'s own stdout is clean, but a `sniff` of the session is noisier than what a human would type. That is a property of the remote shell's line editor, not of the scrape, so going native did not buy it back. I would rather say so than pretend it is gone.

## The bug that wasn't

I benchmarked the interactive prompt cycle against a real host, real round-trips and a real shell, and the first run came back damning: ten full seconds an iteration. I started writing the autopsy. I had a theory, too, something principled about a stateless `expect` racing the output.

My theory was wrong, and so was the benchmark. The test prompt was `read -p 'Q? ' a`. `read -p` is a [bash](https://www.gnu.org/software/bash/) idiom, and the box's login shell is [zsh](https://www.zsh.org/), where `-p` means "read from a coprocess" and the line just errors out. The token I was waiting for never printed, so `expect` did the correct thing and waited the full ten-second timeout. The old wrapper had only looked like it passed because its looser matching latched onto the echoed command line instead of the answer. Swap in a portable `printf 'Q? '; read a` and the ten seconds become three hundred milliseconds.

There was a real finding hiding behind the fake one. A stateless `expect` does start scanning at the session's current head, and in a tight write-then-wait loop the awaited bytes can land in the gap between the write returning and the `expect` sampling. Over a network round-trip it almost never bites, because the output takes longer to come back than the gap lasts. On a fast or pre-buffered session it can. The fix is to capture the cursor before you write and tell `expect` to scan from there, which costs one extra round-trip, about thirty milliseconds, and is now the documented default for loops. The lesson is the one live testing keeps teaching: measure against the real host and the real shell. A piped local bash would never have found the zsh failure.

## The numbers

Median wall-clock, driving a real host over a real network, lower is better.

| Task | `etctl` |
| --- | ---: |
| Warm `run echo hello` (x15) | 195.5 ms |
| Warm `run hostname; id -un` (x10) | 200.2 ms |
| Output-heavy `run seq 1 3000` (x5) | 222.7 ms |
| Interactive prompt cycle (x7) | 318.5 ms |
| Local CLI startup (`--help`, x20) | **15.5 ms** |

Two things stand out. Every steady-state run sits near **200 milliseconds**, which is the network round-trip and almost nothing else, and streaming three thousand lines costs no more than printing one, so the cursored scrollback adds no measurable tax on bulk reads.

The other is the last row. `etctl` starts in about **15 milliseconds**, because it is a native binary already inside the `et` build. A Python entry point costs roughly **100 milliseconds** just to reach `main`, so going native hands back about **85 milliseconds on every single call**, and an agent driving a host issues a great many small calls. It is the kind of fixed cost that rounds to nothing in a demo and adds up to real time across a day of automated work.

Cold start is the one number that refuses to sit still, because it is dominated by the connection handshake and therefore tracks the link you are on. I have measured the same path at **3.8 s** on a good day and **9.5 s** on a slower one. The steady-state rows above reproduced within a few percent across both, so those are the ones to trust.

## A file through the keyhole

A machine driving a box eventually needs to put a file *on* it. The handle it has is the session, so the clean move is to make that one channel carry the file too, instead of bolting on a separate transfer tool. The catch is that the channel is a terminal, and a terminal is the thing least built to move a file.

The obvious move is to [base64](https://en.wikipedia.org/wiki/Base64) the file and paste it through. It works beautifully on a tiny file and falls apart above a hundred kilobytes, and not for the reason you would guess. The bytes do not land in a clean pipe. They land in the interactive line editor, zsh with syntax highlighting, which re-colors the entire growing line on every newline. That is quadratic, and a real file buries it. A megabyte did not transfer slowly, it took the session down.

So stop feeding the line editor. Drive the remote terminal into raw, no-echo mode and stream the bytes straight at a waiting reader. Binary-clean, no base64, no echo, and for small files it was perfect. Then it hung on anything past a few kilobytes, for the reason a terminal is not a file transport: a tty's input buffer is only a few kilobytes, and in raw mode it has no flow control. Send a burst bigger than the buffer and the overflow is not backpressured, it is silently dropped, and the reader waits forever for bytes that will never arrive.

What finally holds is unglamorous, and it is not a new verb at all. It is a procedure built out of the verbs already there. Capture the session's cursor, put the remote side into `stty raw -echo` and have it announce `READY`, and wait for exactly that before sending a byte. Then stream the file at a `head -c N` that reads precisely the length you announced and not one byte more, restore the saved terminal mode, and compare SHA-256 on both ends. Because the read is length-bounded, nothing inside the file can pose as an end marker, and there is no base64 anywhere: the bytes that arrive are the bytes you sent.

The honest costs are worth naming. The ceiling is roughly **two megabytes**, the retained scrollback in each direction, and the exit code that comes back belongs to `stty` rather than `cat`, so you trust the hash and not `$?`. There is also a faster and sloppier path, streaming into a running `cat` with echo off, which moves about **27 KB/s** against roughly **2 KB/s** for a here-document typed through the prompt, about fifteen times quicker. That one leaves the tty canonical, and I watched it quietly translate line endings inside ordinary Python source, file size unchanged so nothing looked wrong. It is fine for a throwaway script and wrong for anything you intend to execute or diff.

So I deliberately did not wrap this in a `put` verb. A subcommand would have promised something the channel cannot keep, and I would rather the shape of it stayed visible to whoever is driving. Anything genuinely large belongs in one of `et`'s own port-forward tunnels, a clean binary side-channel that is already sitting right there, and that is the next thing to cut in.

## Handing it to the agent

The whole point is for something without hands to use this, and the test of an interface is how much you have to explain before it works. So here is the entire handoff, the [agent skill](snippet:etctl-skill.md) I actually run, cleaned up for a machine that is not mine.

Most of it is not about `etctl`. Open a named session, keep it, one driver per name, and here are the verbs: that part is short, and a careful reader could rebuild it from `--help` alone. Everything after it is about the remote *shell*, and it is all warnings. A pager wedges the session, backgrounding inside a command confuses the framing, and a stray `exit` kills the shell you are living in. My favorite is still `read -p`, the bash idiom that fails silently under zsh and cost me a benchmark and most of an afternoon.

That ratio is the result I did not expect and am happiest about. The channel stopped being the hard part, and what is left over is a shell that still assumes someone is sitting in front of it.

## What it is not yet

This is an honest report, so here is what `etctl` is not.

**It is a prototype.** The [Catch2](https://github.com/catchorg/Catch2) suite passes 439 assertions across 26 cases, and I have since put it through a stress run against a real `etserver`, hundreds of rapid commands, concurrent readers, parallel sessions, file transfers of every shape. That shook out a real teardown race, recreating a session the instant after ending it could catch the still-dying daemon and quietly no-op, now fixed with a `--wait` that blocks until the old one is truly gone. It is more hardened than it was, and still almost untested in anger. Speed is not robustness, and a race like that is exactly the class of bug only hard daily use flushes out.

**It does not survive a reboot.** The daemon dies with the host process, so a restart costs you every open session. The design for reattaching across one is sketched and parked.

**It has to be built per platform,** because it ships inside `et`. A single portable script with no dependencies is an easier thing to hand someone, and that cost is real.

None of that is fatal, and none of it is hidden. `etctl` earns its mileage the only way anything does, by getting used hard, and it has not had enough of that yet.

## Built to merge

I built this to be easy to say yes to. It is client-side only: the change lives entirely in the `et` client, swapping one `Console` implementation and adding a control socket. Not a line of `etserver`, `etterminal`, or the wire protocol changed, so it cannot regress an existing session, and `et` without `--ctl` behaves exactly as it always has. The whole thing is a handful of new files and three small touches to the launch path.

It lives on a branch today, with a green test suite and real mileage still ahead of it, and I have [opened the conversation upstream](https://github.com/MisterTea/EternalTerminal/issues/779). Until it lands anywhere, it ships in my own build, the same `brew install Kronuz/tap/et` from the [first part](/blog/across-the-tunnel/). If you maintain or lean on [Eternal Terminal](https://github.com/MisterTea/EternalTerminal), I would love to see something like this land upstream, so the next person who needs to drive a session from a script finds it already there, speaking their machine's language, instead of scraping the glass like I did.

## In its own voice

The [pair of hands](/blog/a-pair-of-missing-hands/) an agent was missing is now a few hundred lines living inside Eternal Terminal, speaking machine in its own voice instead of miming it through glass. The handle did not just get faster. It stopped being a thing bolted on and became part of the thing it drives, which is why the reconnect and the durability came free. They were never mine to implement.

That is the move I keep coming back to. When a tool only talks to people, you can stand outside and scrape, and that gets you surprisingly far. It got me a working prototype and a lot of real automation. But the answer, when you can reach it, is to teach the tool to talk to machines too. Then nobody has to read the glass.
