---
title: "Before You Ask"
subtitle: "Reading a git repository's whole state from the prompt, one glyph at a time."
description: "The KronuZSH git segment answers most of what you would run git status for, in a handful of colored glyphs. Here is every one of them: branch, remote host, ahead and behind, the dirty counts, conflicts, the overflow mark, and the direct-git fallback."
excerpt: "Once the prompt was mine, I taught its git segment to say everything a git status would, in a line you read without stopping. This is the whole vocabulary, glyph by glyph."
series: "Home Made"
seriesOrder: 5
date: 2026-07-23
authors: kronuz
draft: true
tags:
  - tooling
  - shell
  - zsh
  - git
  - terminal
---

I [pulled my prompt out of Prezto](/blog/molting/) and then [taught it to collapse into quiet scrollback](/blog/prompt-history/). Somewhere in between, the part I actually stare at all day got good enough that I stopped running `git status`. The prompt already knew.

The git segment of [KronuZSH](https://github.com/Kronuz/KronuZSH) sits at the end of the line, right after the working directory, and only when you are inside a repository. At rest it looks like this:
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
```
Read it left to right. A branch glyph and `main`, so you know the branch. Then a small [GitHub](https://github.com) mark, because that is where this repo's remote lives, and the upstream it tracks, `origin/main`. Then, inside the parentheses, a green check: the working tree is clean. Nothing staged, nothing changed, nothing untracked.

The little leading glyphs are grey and the names carry the color, so the branch reads first and the decoration second. Everything past this point is the prompt reacting to the repository as it changes.

## Where you are

The head of the segment answers "where am I". On a branch you get the branch glyph and its name. On a tag, a tag glyph. On a detached HEAD, a commit glyph and the short hash.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
[0m [0;90m[0m [0;1;38;2;255;255;255mv1.4.0[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
[0m [0;90m[0m [0;38;2;255;255;255ma1b2c3d[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
```
Same shape each time, so the three read alike at a glance.

## Whose remote

The remote is tagged by where it lives. KronuZSH reads the remote URL, which the status daemon already hands it, and picks the logo: GitHub, [GitLab](https://gitlab.com), [Bitbucket](https://bitbucket.org), or a generic compare-mark for a self-hosted or unknown host.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
```
Four identical repos, four homes. It costs nothing extra, since the URL is already in the payload.

## How far off you are

Once you start committing, two arrows measure your distance from upstream. `⇡` ahead, `⇣` behind, each with a count. Green for ahead, pink for behind.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0m [0;38;2;135;255;0m⇡2[0m [0;38;2;215;0;95m⇣1[0;90m)[0m
```
If you push somewhere other than you pull from, the fork-and-upstream dance, a second pair shows up: `⇧` and `⇩` for the push remote. Here you track `upstream/main`, sit two commits behind it, and have four commits your own fork has not seen yet.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255mupstream/main[0;90m ([0;38;2;95;255;95m✔[0m [0;38;2;215;0;95m⇣2[0m [0;38;2;135;255;0m⇧4[0;90m)[0m
```
That second pair only appears when the push remote is genuinely a different remote, so an ordinary single-remote repo never grows a redundant one. And if you have parked work in a stash, a count rides at the front so you do not forget it is there.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;175;175;255m 3[0m [0;38;2;95;255;95m✔[0;90m)[0m
```
## What is dirty

This is the part I read all day. The moment the tree is dirty the green check becomes a cross, and the counts fan out behind it.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;135;95;0m✗[0m [0;38;2;215;95;0m 5[0m [0;31m 3[0m [0;90m⊖4)[0m
```
Orange for staged, red for modified-but-not-staged, grey for untracked, each with how many paths. Three colors, three questions answered without a keystroke: what is ready to commit, what still needs adding, and what git is not tracking yet.

Sometimes you want to know not just how many, but what kind. Set `PROMPT_KRONUZ_GIT_SPLIT=1` and each group breaks apart into added `+`, changed `~`, and deleted `-`, still colored by staged-versus-unstaged so you can tell the two apart.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;135;95;0m✗[0m [0;38;2;215;95;0m 2[0m [0;38;2;215;95;0m 2[0m [0;38;2;215;95;0m 1[0m [0;31m 2[0m [0;31m 1[0m [0;90m⊖4)[0m
```
The daemon already reports the new and deleted breakdown, so this too is free. It is off by default; the compact count is what I keep.

## Mid-operation

When a merge or rebase is underway, the operation shows with its own glyph and name, and any conflicts get their own red count.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0m [0;90m[0m [0;38;2;215;95;0mmerge[0;90m ([0;38;2;135;95;0m✗[0m [0;38;2;215;95;0m 1[0m [0;31m 2[0;90m)[0m
```
A merge in progress, one path staged, two conflicted. The prompt is telling you the repo is not in a normal state before you wonder why a command misbehaves.

## It never blocks

Talking to [gitstatusd](https://github.com/romkatv/gitstatus), the daemon that makes all of this cheap, is asynchronous. The prompt never waits on git. If an answer misses its short latency budget, the last-known status paints immediately with a small refresh mark, and the line repaints in place the instant the daemon catches up.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m [0;90m [0m
```
You see it only on a cold cache or a very large repo, and only for a blink. A slow prompt reads as refreshing, never as frozen.

Very large repositories have one more tell. gitstatusd caps how much of the index it will scan so a giant tree cannot stall the prompt. Over that cap it skips the dirty scan, and rather than guess "clean", the prompt shows an infinity mark.
```ansi
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;135;95;0m✗[0m [0;38;2;215;95;0m 3[0m [0;90m∞)[0m
```
Staged is always counted exactly, so `+3` is real. The rest is genuinely unknown, and `∞` says so honestly.

## Make it yours

The indicators are joined by a separator you can set. A space by default, or a middle dot, a colon, or nothing at all if you like them packed tight.
```ansi title="PROMPT_KRONUZ_GIT_SEP"
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0;90m ([0;38;2;135;95;0m✗[0m [0;38;2;215;95;0m 5[0m [0;31m 3[0m [0;90m⊖4)[0m
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0;90m ([0;38;2;135;95;0m✗[0m·[0;38;2;215;95;0m 5[0m·[0;31m 3[0m·[0;90m⊖4)[0m
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0;90m ([0;38;2;135;95;0m✗[0m:[0;38;2;215;95;0m 5[0m:[0;31m 3[0m:[0;90m⊖4)[0m
[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0;90m ([0;38;2;135;95;0m✗[0;38;2;215;95;0m 5[0;31m 3[0;90m⊖4)[0m
```
And every glyph has a plain-Unicode twin, so the whole thing renders without a [Nerd Font](https://www.nerdfonts.com/). `PROMPT_KRONUZ_NERD_FONT=0`, or a `dumb` terminal, switches to it automatically. The host logo falls back to a plain compare-mark, and the split view keeps the same `+ ~ -`.
```ansi title="plain-Unicode set"
[0m [0;90m⎇[0m [0;1;38;2;255;255;255mmain[0m [0;90m⇅[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;95;255;95m✔[0;90m)[0m
[0m [0;90m⎇[0m [0;1;38;2;255;255;255mmain[0m [0;90m⇅[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;135;95;0m✗[0m [0;38;2;215;95;0m✛5[0m [0;31m✴3[0m [0;90m⊖4)[0m
[0m [0;90m⎇[0m [0;1;38;2;255;255;255mmain[0m [0;90m⇅[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;135;95;0m✗[0m [0;38;2;215;95;0m+2[0m [0;38;2;215;95;0m~2[0m [0;38;2;215;95;0m-1[0m [0;31m~2[0m [0;31m-1[0m [0;90m⊖4)[0m
```
## When the daemon is away

If gitstatusd is not running at all, not installed, or not yet warmed up, KronuZSH drops to a lean direct-`git` fallback, flagged with a warning glyph so you know you are not getting the full picture.
```ansi
[0m [0;38;2;215;175;0m[0m [0;90m[0m [0;1;38;2;255;255;255mmain[0m [0;90m[0m [0;38;2;255;255;255morigin/main[0;90m ([0;38;2;135;95;0m✗[0m [0;38;2;215;95;0m[0m [0;31m[0m [0;90m⊖)[0m
```
The fallback is deliberately spare. Branch, upstream, and which categories are dirty as presence, no counts, no host logo, no ahead-and-behind, no split. Each of those would cost its own `git` subprocess, and staying cheap when the daemon that makes them free is missing is the entire point of a fallback. It still tells you the one thing you need: where you are, and whether the tree is clean.

## The whole point

Most of the [Powerlevel10k](https://github.com/romkatv/powerlevel10k) ideas that inspired this were about exactly this: say more, in less space, without ever making the prompt wait. A branch, a host, a check or a cross, and a few colored counts that describe the shape of the working tree before you ask for it. Ninety-nine times out of a hundred you never think about any of it. That is the part I am proudest of.
