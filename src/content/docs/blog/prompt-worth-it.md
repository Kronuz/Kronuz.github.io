---
title: "Punching Up"
subtitle: "A home-made prompt, on a scale next to the giants."
description: "Is a ~1,800-line home-made zsh prompt any good next to Powerlevel10k, starship, pure, and the frameworks? I benchmarked cold start, per-prompt latency, and size on a 60,000-file repo. It lands in the fastest tier, at a fraction of the code."
excerpt: "Rolling your own prompt sounds indulgent until you measure it. On a 60,000-file repo mine paints in the same 7.4 ms as Powerlevel10k, while the shell-out crowd waits 160 to 450, and it does it in a fraction of the lines."
series: "KronuZSH"
seriesOrder: 4
date: 2026-07-23
authors: kronuz
draft: true
tags:
  - tooling
  - shell
  - zsh
  - benchmarks
  - terminal
---

Rolling your own prompt is easy to mock. A fast, free, genuinely gorgeous one is a `git clone` away in [Powerlevel10k](https://github.com/romkatv/powerlevel10k). [starship](https://starship.rs/) gives you much the same across every shell, in Rust. A dozen frameworks hand you a good-enough prompt in a single line. Writing your own in ~1,800 lines of zsh, to do a job three downloads already do, is exactly the kind of thing that looks like productivity and smells like procrastination.

So before I get too attached to it, the fair question. Is [KronuZSH](https://github.com/Kronuz/KronuZSH) actually good, or just mine? I put it on a scale next to the ones people actually use.

## The test

I made a repository with 60,000 files, the size where the way a prompt reads git stops being a rounding error, and measured every prompt I could install the same way, in that repo. Two numbers matter. **Cold start**: how long from launching zsh to a usable shell. **Per prompt**: the wall time of one prompt cycle, which is what you pay after every single command. Medians, zsh 5.9, an Apple Silicon Mac.

| prompt | cold start | per prompt | how it reads git |
| --- | ---: | ---: | --- |
| bare zsh (no prompt) | 19 ms | 6 ms | nothing |
| **KronuZSH** | **30 ms** | **7.4 ms** | async, gitstatusd |
| Powerlevel10k | 40 ms | 7.4 ms | async, gitstatusd |
| pure | 41 ms | 7.6 ms | async git worker |
| Prezto (sorin) | 58 ms | 24 ms | git-info |
| starship | 33 ms | 161 ms | shells out to git |
| oh-my-posh | 58 ms | 233 ms | shells out to git |
| oh-my-zsh (agnoster) | 136 ms | 447 ms | vcs_info |

Read the third column first, because it is the one you feel. Three prompts paint in about seven milliseconds. The rest take twenty to four hundred and fifty.

## The line is async, not clever

KronuZSH lands on the same ~7 ms per prompt as Powerlevel10k. Not near it. On it, a dead heat inside the run-to-run noise. That is not a coincidence and it is not me being clever, it is the same daemon and the same trick, because I took both from p10k. [gitstatusd](https://github.com/romkatv/gitstatus) is a small C process that keeps a warm, cached view of your repository and answers in microseconds. You ask it without blocking, paint the last-known answer right away, and repaint when it replies. [pure](https://github.com/sindresorhus/pure) does nearly as well at 7.6 ms with a different async design, a background worker instead of a daemon.

There is an easy way to flatter a home-made prompt, and I want to name it so you know I did not do it: time a blanked prompt, or skip the render and measure only the segment math. So I measured the whole paint, `PROMPT_SUBST` expanding the layout and every segment on each cycle, the way the shell actually draws it. Against p10k drawn the same way it is still a tie, a hair under if anything, and "a hair under" is me being generous to myself. Call it even.

Everything slow shares one habit: it runs `git` in the foreground, every prompt, and waits for it. [starship](https://starship.rs/), [oh-my-posh](https://ohmyposh.dev/), and [oh-my-zsh](https://ohmyz.sh/)'s agnoster all shell out synchronously, so on a big repository they hand you the bill in full: 161, 233, 447 milliseconds, every command. The [Kronuz prompt I ran inside Prezto](https://github.com/Kronuz/prezto) for years, the one this whole project grew out of, did the same through Prezto's `git-info`: about 80 ms a prompt on a repo this size. Trading that for gitstatusd is most of the gap.

There is a quieter point hiding in pure's 7.6 ms. Async hides the wait, but pure still re-runs `git` in its worker on every prompt, roughly 180 ms of work each time, just off the critical path. The daemon does less: it keeps an incremental cache and answers in about 87 ms of real work, warm, and reuses it. Same felt speed, less CPU and less battery. Borrowing the daemon was the right theft.

(One honest asterisk on cold start. KronuZSH's 30 ms is the prompt on its own; my full setup, with syntax highlighting and completion, is nearer 74 ms. And p10k has one trick I did not copy, an [instant prompt](https://github.com/romkatv/powerlevel10k#instant-prompt) that paints a cached line before zsh finishes loading, so its *perceived* start is nearer zero than any number here. On raw load the prompt is light; on the trick, p10k wins.)

## The other axis

Speed is a tie at the top, so the tiebreaker is what you carry to get it.

| prompt | the prompt itself | the framework it rides on |
| --- | ---: | --- |
| **KronuZSH** | **1,229 lines** | none, the whole setup is ~1,800 |
| pure | ~1,970 lines | none |
| Powerlevel10k | 13,700 lines | none, or oh-my-zsh |
| agnoster | 380 lines | oh-my-zsh: 31,500 lines |
| sorin | 190 lines | Prezto: 50,600 lines |
| starship | 9 MB binary | none |
| oh-my-posh | 18 MB binary | none |

This is the column I am proudest of. The entire KronuZSH is about 1,800 lines of zsh I can read on a slow afternoon. To get agnoster you carry 31,000 lines of oh-my-zsh around it; sorin rides on 50,000 lines of Prezto; starship and oh-my-posh are multi-megabyte binaries you cannot open. Even p10k's theme alone is bigger than all of KronuZSH, though in fairness it is generated and tuned for speed, not written to be read. Mine is written to be read. When the prompt does something I dislike, I open the file and change it. That is not a small thing. It is the thing.

## Where it actually loses

I would be lying if I stopped on the wins. This is where a home-made prompt gives ground, and it gives a lot of it.

Powerlevel10k is the better choice for most people, and it is not close on breadth. It has a segment for everything: your node, python, and rust versions, your AWS profile, your kubernetes context, your battery. Its instant prompt makes startup feel free. Its wizard produces something beautiful in a minute. starship gives you that same breadth across bash, fish, and PowerShell, from a clean TOML file. oh-my-posh ships a gallery of themes prettier than anything I would hand-draw.

KronuZSH has none of that. No language-version segments, no cloud, no kubernetes, no themes but the one I like, no wizard, no instant prompt. It shows the shell context I actually use and a git segment as detailed as any, and then it stops. It is narrow on purpose, and narrow is a real cost, not a humble-brag.

## So, worth it?

Here is the honest ledger. A home-made prompt will not out-feature p10k, out-theme oh-my-posh, or out-travel starship. It never will. What it does is land in the fastest tier there is, on the same daemon as the best of them, in a fiftieth of the code, doing exactly the things I use and nothing I do not, in a file I own from top to bottom.

If that trade sounds indulgent, run p10k. It is superb and I recommend it without a caveat. But if you have ever wanted a prompt small enough to hold in your head and fast enough to disappear, the surprising part is that you do not have to choose: you can have both, and it costs about 1,800 lines. Mine is one of them. Yours could be too.

That is the whole pitch. After putting it on a scale, I believe it.

And there is one more thing owning the file buys you, the least serious and the most fun of all: because the whole layout is yours, you can bend it into almost anything. That is where we go next.
