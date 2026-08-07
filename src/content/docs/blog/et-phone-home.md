---
title: "ET Phone Home"
subtitle: "A native control plane for Eternal Terminal"
description: "Eternal Terminal only ever spoke one language, the rendered screen, so a script or an agent had to stand outside and scrape it. This is how I taught et to speak machine instead: a control Console swapped in behind the client, a per-user socket, and a native CLI called etctl. A 15 millisecond per-call floor, a deadlock I had been walking around for years that an agent finally pinned down, and a change that is client-side only so it is easy to merge upstream."
excerpt: "A terminal is built end to end for eyes and fingers, which is exactly what locks out everything that has neither. Rather than keep scraping the screen from outside, I went looking for a seam inside Eternal Terminal and found one already cut. etctl is what came out: a native control plane, the numbers behind it, and a years-old deadlock that only held still once a machine was doing the typing."
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

Because the backgrounded `et` is just an Eternal Terminal client, it reconnects on its own across network drops, the same way a human's session does. That durability was something [`etch.py`](/blog/a-pair-of-missing-hands/#first-from-the-outside), the screen-scraping prototype from the last part, had to hand-roll for itself. Here it came for free, because this time it was not hand-rolled. It was the thing `et` already does.

All of it, the control mode, the socket, the cursored scrollback, the CLI, came together over a weekend. Not because the code was trivial, but because the seam was already cut. I was plugging into `et`, not prying it open.

The verbs are the ones the prototype had already settled, because that vocabulary was right: `run` for a command that finishes (clean output, a real exit code, and a multi-line body that runs as one unit), `write` and `writeln` and `expect` and `read` for a prompt that waits, `key` for the named keys and signals, `sniff` to tap the live exchange, `observe` and `attach` to take the wheel by hand. What changed is everything underneath. There is no prompt to neutralize, no ANSI to strip, no resync, no line-cap chunking, and no Python process per call. It reads `et`'s native byte stream over a local socket, locked to my user (`0700` directory, `0600` socket, and the daemon checks the peer's uid). The hacks did not get better. They became unnecessary.

```bash
H=you@devbox
etctl open main $H                      # background (or reuse) the 'main' session
etctl run  main 'cd ~/work && make'     # clean stdout + the real exit code
etctl run  main 'systemctl is-active nginx' && echo up
```

One thing did survive the move, honestly, though less of it than I expected. `etctl` sniffs the far shell once per session to see what it can speak. When the prompt supports [OSC 133](https://gitlab.freedesktop.org/Per_Bothner/specifications/blob/master/proposals/prefix-and-status.md) shell integration and bracketed paste, `run` sends the bare command inside a paste and lets the shell's own markers say where output begins and ends, so there is no framing in the transcript at all. Only when the far end can speak neither does it fall back to wrapping the command in `printf` sentinels, and then the remote shell does echo that framing into the session. `run`'s stdout is clean either way; it is a `sniff` of a fallback session that looks noisier than what a human would type. That last case is a property of the shell on the other end, not of `etctl`, which is why the answer was to detect it rather than to paper over it.

## The hidden bug

Something had been happening to me for years, every now and then, always the same way. I would paste something big into a session, a heredoc or a chunk of config, and the whole thing would wedge. Not slow, not garbled: dead. Reconnect and it was fine. I never caught it in the act, because a person pastes a big block rarely enough that you shrug and move on.

An agent does it constantly, so within a day of driving sessions with `etctl`, the wedge stopped being folklore and became a reproducible bug: paste past roughly one pty buffer, about 1 KB on macOS and 8 to 10 KB on Linux, and the session dies **every single time**.

With a reproduction, the cause was plain, and it was a deadlock four steps deep. The per-session terminal pump on the server, `UserTerminalHandler::runUserTerminal`, is a single-threaded `select` loop, and it wrote client input to the pty master with a **blocking** write.

1. The input echoes back and fills the pty's output buffer.
2. With its output buffer full, the shell stalls and stops reading input.
3. The blocking write to the master never drains, so it never returns.
4. Stuck in that write, the loop stops draining output, which is the one thing that would unstick the shell.

Each step is waiting on the step that follows it. The read path had tolerated `EAGAIN` all along, written as though the master were non-blocking, but nothing ever set `O_NONBLOCK` on it. The fix sets it where the fd is created, reworks the pump to buffer pending input and drain it through the `select` write set while still reading output every iteration, and adds backpressure so a full input buffer propagates back to the client. It is [merged upstream](https://github.com/MisterTea/EternalTerminal/pull/765), server-side only, with a regression test that pushes 8 KB through a real pty and times out against the old code. A 56 KB paste that used to kill a session now round-trips byte-exact.

The existing tests had never caught it because they all drove a socket pair instead of a real pty, and a socket pair has no buffer to fill. Neither did I, in years of daily use, because I am a slow and forgiving client. The agent was neither, and that is the part worth keeping: giving the machine a handle did not just let it in, it made the machine an instrument. It does the boring thing ten thousand times without getting bored, and the flaw you have been walking around for years finally holds still long enough to be seen.

## The numbers

Median wall-clock, driving a real host over a real network, lower is better.

| Task | Median |
| --- | ---: |
| Reaching a usable shell on a cold connection | ~10 s |
| Warm `run echo hello` (x15) | 195.5 ms |
| Warm `run hostname; id -un` (x10) | 200.2 ms |
| Output-heavy `run seq 1 3000` (x5) | 222.7 ms |
| Interactive prompt cycle (x7) | 318.5 ms |
| Local CLI startup (`--help`, x20) | **15.5 ms** |

The first row is not something `etctl` charges you. It is what reaching a remote shell costs anybody. Type `ssh host 'some command'` and you pay it. Use `et -c 'some command'` and you pay it. Put either in a loop and you pay it on every iteration, which is how a script doing twenty small things spends **over three minutes** to accomplish about four seconds of work.

`etctl` pays it once. Every command after the first lands in about **200 milliseconds**, so keeping one session open is worth roughly **fifty times** the connect-per-command path. That is the difference between an agent that feels like it is thinking and one that feels like it is dialing up, and it is why the first rule in the skill file is to open a session and keep it for the whole task.

Cold start is also the one number that refuses to sit still, because it is dominated by the connection handshake and therefore tracks the link you are on. I have measured the same path at **3.8 s** on a good day and **9.5 s** on a slower one. Everything below it reproduced within a few percent across both.

The rest of the table is network-bound and pleasantly boring. Every steady-state run sits near **200 milliseconds**, which is the round-trip and almost nothing else, and streaming three thousand lines costs no more than printing one, so the cursored scrollback adds no measurable tax on bulk reads.

The last row is the one I care about. `etctl` starts in about **15 milliseconds**, because it is a native binary already inside the `et` build. A Python entry point costs roughly **100 milliseconds** just to reach `main`, so going native hands back about **85 milliseconds on every single call**, and an agent driving a host issues a great many small calls. It is the kind of fixed cost that rounds to nothing in a demo and adds up to real time across a day of automated work.

## Handing it to the agent

The whole point is for something without hands to use this, and the test of an interface is how much you have to explain before it works. So here is the entire handoff, the [agent skill](snippet:etctl-skill.md) I actually run, cleaned up for a machine that is not mine.

Most of it is not about `etctl`. Open a named session, keep it, one driver per name, and here are the verbs: that part is short, and a careful reader could rebuild it from `--help` alone. Everything after it is about the remote *shell*, and it is all warnings. A pager wedges the session, backgrounding inside a command confuses the framing, and a stray `exit` kills the shell you are living in. My favorite is still `read -p`, the bash idiom that fails silently under zsh and cost me a benchmark and most of an afternoon.

That ratio is the result I did not expect and am happiest about. The channel stopped being the hard part, and what is left over is a shell that still assumes someone is sitting in front of it.

## On a branch, for now

It is a prototype, and an honest report says so. It comes with tests, 439 assertions across 26 cases written in [Catch2](https://github.com/catchorg/Catch2), the C++ test framework Eternal Terminal already builds with, so they run as part of the normal `et` suite rather than off to one side. A stress run against a real `etserver` shook out a teardown race where recreating a session the instant after ending it could catch the still-dying daemon and quietly no-op, now fixed with a `--wait`. It is more hardened than it was and still almost untested in anger. It does not survive a reboot, because the daemon dies with the host process, and the design for reattaching across one is sketched and parked. And it has to be built per platform, because it ships inside `et`.

That last part is also the good news: it is built to be easy to say yes to. The change is client-side only, swapping one `Console` implementation and adding a control socket. Not a line of `etserver`, `etterminal`, or the wire protocol changed, so it cannot regress an existing session, and `et` without `--ctl` behaves exactly as it always has. The [conversation is open upstream](https://github.com/MisterTea/EternalTerminal/issues/779). Until it lands there, all of it, plus the deadlock fix, is already in the build from the [first part](/blog/across-the-tunnel/): `brew install Kronuz/tap/et`, and you have `etctl` too.

If you maintain or lean on [Eternal Terminal](https://github.com/MisterTea/EternalTerminal), I would like to see something like this land upstream, so the next person who needs to drive a session from a script finds it already there instead of scraping the glass like I did.

## Nobody reads the glass

The [pair of hands](/blog/a-pair-of-missing-hands/) an agent was missing is now a few hundred lines living inside Eternal Terminal, speaking machine in its own voice instead of miming it through glass. The handle did not just get faster. It stopped being a thing bolted on and became part of the thing it drives, which is why the reconnect and the durability came free. They were never mine to implement.

That is the move I keep coming back to. When a tool only talks to people, you can stand outside and scrape, and that gets you surprisingly far. It got me a working prototype and a lot of real automation. But the answer, when you can reach it, is to teach the tool to talk to machines too. Then nobody has to read the glass.
