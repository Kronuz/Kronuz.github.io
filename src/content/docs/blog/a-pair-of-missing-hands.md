---
title: "A Pair of Missing Hands"
subtitle: "No eyes, no hands"
description: I had a durable terminal onto the box I live on, and it felt like home because every inch of it was built for a person. That is exactly what locked everyone else out, the deploy scripts, the scheduled jobs, the AI agents I pair with, none of which have eyes to read a prompt or fingers to hit Enter. This is the need a control plane exists to fill, and what it would mean to give a human-shaped world handles that something without hands can hold.
excerpt: An agent I was pairing with needed to restart a service on a remote box. It knew the command and the host, and it just sat there, because the only way in was a terminal built for eyes and fingers it doesn't have. The whole human-shaped world is like that. The work isn't a smarter agent. It's a pair of hands.
date: 2026-06-13
draft: true
series: "Driving Eternal"
seriesOrder: 1
tags:
  - driving-eternal
  - ai
  - tooling
  - automation
---

*Part of the **Driving Eternal** series: giving a script or an AI agent a real handle on a remote terminal, ending in a small native addition to [Eternal Terminal](https://eternalterminal.dev/).*

An agent I was pairing with needed to restart a service on a remote box. It knew the command. It knew the host. And it just sat there, because the only way onto that machine was a terminal built for my eyes and my hands, and an agent has neither. It cannot watch a prompt redraw. It cannot tell the echo of what it typed from the answer that came back. It has no fingers to hit Enter, and no way to know whether the thing it ran worked or failed.

I had a durable, eternal terminal onto the machine I live on, [Eternal Terminal](https://eternalterminal.dev/), and it felt like home precisely because every inch of it, the prompt, the colors, the living terminal `et` hands you, was made for a person. The thing that makes it feel like home is the same thing that locks everyone else out.

## Years before the agent

The agent was only the newest arrival at a wall people had been bruising themselves against for decades. Every team has someone who automates the toil so nobody else has to think about it. Picture her clearly enough and she gets a name. Maya.

It's two in the morning and an alert is going off. The fix is three commands on a box in another datacenter, the kind of thing Maya has typed by hand a hundred times. Tonight she wants it to run itself, so she does what any of us would: she writes a small script to log in and type the commands for her.

The box wants a password, and then a prompt, and then a `[y/N]` it expects a human to answer. A plain script can't answer a question it can't see, so Maya reaches for [`expect`](https://en.wikipedia.org/wiki/Expect), the thirty-year-old tool built for exactly this, and teaches her script the words to watch for. It works. She goes to bed.

Wednesday it breaks. The remote tool printed `Proceed?` where it used to print `Continue?`, and her script, waiting on a word that never comes, hangs until it times out. She fixes the pattern. Thursday a different prompt has moved. The trouble with teaching a script to read a screen built for a person is that the screen keeps changing underneath it, and nothing anywhere promised it wouldn't.

And even on a good run she can't fully trust it. What comes back is the prompt, and the color codes, and the echo of her own keystrokes, braided together with the one line she actually wanted. Worse, when a remote command fails, her script often can't tell, because the interactive shell hands back a screenful of text and no clean exit code that says *this worked* or *this didn't*. She once watched a deploy script report a tidy success over a deployment that had quietly failed. That one cost her a Saturday.

## It isn't just her

I went looking to find out whether this was just me and Maya and one bad Saturday, and found a whole genre of suffering, decades deep and very well attended.

The classic tool for answering prompts from a script is `expect`, and its Python cousin [`pexpect`](https://pexpect.readthedocs.io/en/stable/overview.html). Between them they carry more than **3,600 questions** on Stack Overflow ([2,809](https://stackoverflow.com/questions/tagged/expect) for `expect`, [817](https://stackoverflow.com/questions/tagged/pexpect) for `pexpect`), which is a lot of confusion for tools whose whole job is to make automation easy. And the reason they're hard isn't a bug, it's physics, which `pexpect`'s own docs admit out loud: because it reads a pseudo-terminal one character at a time, "the `$` pattern for end of line match is useless," and when the child prints a newline "you actually see `\r\n`." You aren't reading output. You're parsing a screen.

How hard is parsing a screen? The single most-viewed `pexpect` question on Stack Overflow is just someone asking how to read the output of a command they ran. It has [more than **147,000 views**](https://stackoverflow.com/questions/17632010/python-how-to-read-output-from-pexpect-child), and the catch is that the first thing you read back is the echo of your own command, not its result, which is precisely the braided mess Maya kept fishing in. One developer who tried to skip the libraries and do it with Python's raw `pty` module left a verdict I think about often: ["the pty library is not fit for human consumption. The docs, essentially, are the source code."](https://stackoverflow.com/questions/31926470/run-command-and-get-its-stdout-stderr-separately-in-near-real-time-like-in-a-te)

The exit code is its own quiet heartbreak. Run a command over [`ssh`](https://www.openssh.com/) the way a script wants to, with no terminal attached, and ssh greets you with `Pseudo-terminal will not be allocated because stdin is not a terminal`. That one sentence has its own Stack Overflow question with [over **780,000 views**](https://stackoverflow.com/questions/7114990/pseudo-terminal-will-not-be-allocated-because-stdin-is-not-a-terminal). Attach a fake terminal to make the warning go away and you're back to parsing a screen. Get the quoting subtly wrong and the failure goes silent: there's a well-worn question titled ["bash script executed over ssh returns incorrect exit code 0,"](https://unix.stackexchange.com/questions/489737/bash-script-executed-over-ssh-returns-incorrect-exit-code-0) where the remote command fails and ssh reports success anyway. Maya's lying deploy, filed as a bug report.

My favorite of the lot is the smallest. Someone's automated file copy kept breaking, and the culprit turned out to be a friendly `echo` in the remote `.bashrc`, a line of greeting meant for a person. The machine on the other end couldn't tell the greeting from the data. The [accepted answer](https://stackoverflow.com/questions/12440287/scp-doesnt-work-when-echo-in-bashrc) draws the only lesson there is, and it happens to be the whole thesis of this story: "make separate accounts for humans and for machines (scripts), or just stop tattling via `.bashrc`."

That's the wall, and it's been there thirty years. We even keep a shelf of tools that exist only because one corner of it, the dropped connection, hurt us enough to fix: [`mosh`](https://mosh.org), [`autossh`](https://linux.die.net/man/1/autossh), and Eternal Terminal itself, all built so a session can survive "network outages and IP roaming." We fixed the part that hurt the humans. The part that locks out everything *without* hands, we mostly just learned to live around.

## A pair of hands

I kept turning it over until it came clear. The problem in front of me wasn't a smarter agent. It was a pair of hands.

Everything I reach for on that box, the shell, the prompt, the pager, the colored output scrolling past, was made for a person: for eyes that read and fingers that type. An agent shows up with neither and finds a world shaped end to end around a body it doesn't have. And almost every tool any of us has ever made is exactly like this. We built all of it for us. The terminal, the dashboard, the wizard with the *Next* button, the confirmation dialog, the form that wants a click. A whole civilization of interfaces, every one assuming eyes and hands on the other side.

So the work turns out to be quieter than making the models bigger, and a good deal more fun. It's walking the human-shaped world one tool at a time and giving each thing a handle that something without a face can hold. A terminal becomes a socket. A prompt becomes an exit code. A thirteen-second wall becomes a tenth-of-a-second room. None of it makes the agent think any harder. It just lets the agent in.

## The shape of the handle

I didn't know yet how many sharp edges were waiting in a terminal that never once expected to be driven by something without hands. There turned out to be more than I thought. But the shape of the fix was already clear: take the eternal terminal I love, the one built end to end for a person, and give it a handle a machine can hold. Clean output instead of tea leaves. A real exit code instead of a guess. A session that stays warm instead of a thirteen-second wall every single time.

Building that handle meant teaching a terminal that had only ever answered to a human to answer to something that wasn't one, and the machine on the far end did not give that up without a fight. The first version was a Python wrapper that scraped the screen from outside. The version worth talking about, I built into the terminal itself. That's the next part.
