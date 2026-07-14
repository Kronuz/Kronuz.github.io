---
title: "Molting"
subtitle: "Down to the core"
description: I ran prezto for years and tuned a 500-line prompt on top of it. This is how I left the framework for KronuZSH, a ~700-line zsh setup I own, what porting the prompt broke, and the small things a framework quietly does for you that you only notice once they stop.
excerpt: I'd worn prezto for years, a 22,000-line framework I used a sliver of. So I lifted out the one part I loved, my prompt, wrote the few hundred lines around it I'd have wanted anyway, and left the rest. Then I spent days discovering what the framework had quietly been doing for me all along.
date: 2026-06-16
draft: true
tags:
  - tooling
  - shell
---

I'd worn the same shell setup for years without really looking at it.

It was [prezto](https://github.com/sorin-ionescu/prezto), a framework for [zsh](https://www.zsh.org/), and at some point long ago I'd forked it, tuned it, and stopped thinking about it. The prompt was mine: a 528-line function I'd fussed over until it showed exactly what I wanted, the git state, the Python venv, an exit code when something broke, a tidy path. Everything else was just there, the way the floor is there. You don't inspect the floor.

The forced look came one evening when I went to update the fork and found it was seven years behind upstream. Seven years of drift, in code I mostly didn't run, to keep a prompt that didn't depend on any of it. So I opened the directory and actually counted what I'd been carrying.

## The weight

prezto is 42 modules and about 22,000 lines of zsh. I loaded a handful of them. The module that mattered to me, the prompt, ships 17 themes; I used one, mine. The rest was an editor module, a completion module, a history module, a syntax-highlighting loader, an init system to wire them all together, and a long tail of integrations for tools I don't use and shells-within-shells I never start.

None of it was bad. It's careful, well-worn code. But it was a whole house built around the one room I lived in, and the house had drifted years out of date while I wasn't looking. Updating it meant reconciling all that drift for the privilege of keeping a 528-line prompt that, when I finally sat and read it, leaned on the framework for almost nothing I couldn't do myself.

So I asked the obvious question. What if I just kept the room?

## KronuZSH

The plan was small and a little reckless: lift the prompt out of the framework, vendor the two or three plugins I actually load, write the twenty-odd lines of options and history and completion I'd want on any machine anyway, and source them directly. No init system. No modules. No fork to reconcile. Just files I read.

I called it [KronuZSH](https://github.com/Kronuz/KronuZSH), because naming a thing is half of finishing it.

```d2 alt="prezto loaded 42 modules through an init system to build the shell; KronuZSH sources eight short files directly and the prompt stands on its own."
direction: down
old: "prezto\n42 modules, ~22,000 lines\nan init system wiring them together" { shape: rectangle }
new: "KronuZSH\n8 sourced files, ~700 lines\nthe prompt standing on its own" { shape: rectangle }
old -> new: "kept the one room"
```

The entry point is the whole idea on one screen:

```bash
# runcoms/zshrc: the interactive entry point
source "$KRONUZSH/options.zsh"
source "$KRONUZSH/history.zsh"
source "$KRONUZSH/completion.zsh"
source "$KRONUZSH/keybindings.zsh"
source "$KRONUZSH/aliases.zsh"
source "$KRONUZSH/terminal.zsh"
source "$KRONUZSH/plugins.zsh"
source "$KRONUZSH/prompt.zsh"
prompt_kronuz_setup
```

Eight files, in the order they load, each short enough to read in a sitting. No discovery, no registration, no async loader deciding what runs when. If something is wrong, it's in one of eight files, and I can open it.

## Porting the prompt

The prompt was the hard part, and I knew it would be.

Those 528 lines didn't stand alone. They reached into prezto's plumbing: the editor module told the prompt which keymap was active, a git-info module fed it the repository state, an async helper kept the whole thing from blocking the shell on a slow `git` call. To lift the prompt out, I had to rebuild that floor underneath it.

So I did, natively. Git status comes from [gitstatusd](https://github.com/romkatv/gitstatus) when it's there, which is fast, with a plain `git` fallback for when it isn't. The venv, the active keymap, the abbreviated path, all computed directly in the prompt instead of read out of a framework. It came out at 403 lines, leaner than the original, and now it leans on nothing but zsh.

The port was not clean. The best bug took an afternoon.

After the move, my prompt rendered as literal text: `${(e)...}` printed right there on the line, the segments never expanding. It worked in every quick test I tried. It only broke in a real terminal. The culprit was a single option, `PROMPT_SUBST`, that prezto's prompt module had been quietly setting from a `$prompt_opts` variable I'd never heard of. The framework turned it on; my port didn't; zsh dutifully printed my prompt's expansion syntax verbatim. The reason my tests passed is the worse half: a sandboxed `${(e)PROMPT}` check expands the prompt itself, so it always looked right. The only thing that told the truth was a fresh shell on the actual machine.

There were smaller ones. gitstatusd needs job control, so it fails in a shell with no tty, and the direct-`git` fallback has to cover it. `ls` colors are a GNU-versus-BSD coin flip that has to be detected, not assumed. macOS sets `HISTFILE` in `/etc/zshrc` before my config even runs. Each was a small thing the framework had been smoothing over, and each was now mine to smooth.

## What I kept, by the numbers

When it settled, the trade looked like this:

| | prezto | KronuZSH |
|---|---|---|
| zsh source | ~22,000 lines | ~700 lines |
| files / modules | 42 modules | 14 files |
| the prompt | 528 lines, in the framework | 403 lines, standalone |
| plugins | a module loader | 4 git submodules |

About thirty times less code, and the part I cared about came out smaller and free. I symlinked it onto my laptop and my dev VM, archived the old `.zprezto`, and for the first time in years my shell was something I'd read end to end.

It Just Works. Mostly. Which brings me to the part I didn't see coming.

## The things you don't notice

For a few days after the switch, small things were subtly wrong, and I couldn't always say what.

I'd hit Ctrl-W to rub out the last bit of a path, the way I have for a decade, and the whole path would vanish instead of stopping at the last slash. I'd reach for Option+Left to jump back a word and the cursor wouldn't budge. The terminal tab, which had always shown whatever command was running, just sat there with the directory.

None of these were things I had configured. I'd never written a line about Ctrl-W or tab titles in my life. They came in the box. prezto's editor module set `WORDCHARS` so that `/` counted as a word boundary, which is the entire reason Ctrl-W stopped at slashes. It bound a fat set of escape sequences for Option and Ctrl arrows so word-jumping worked whatever the terminal happened to send. Its terminal module emitted the [escape sequences](https://en.wikipedia.org/wiki/ANSI_escape_code#OSC_(Operating_System_Command)) that name the tab. The framework had been doing all of it, silently, for years, and I'd mistaken it for how terminals simply are.

Restoring each one was a few lines:

```bash
# Ctrl-W stops at slashes again: drop '/' (and '=') from the word set
WORDCHARS='*?_-.[]~&;!#$%^(){}<>'

# word-jumping back, whatever Option+Left actually sends
bindkey '^[[1;3D' backward-word    # CSI form
bindkey '^[b'     backward-word    # Esc-b form
# ...and the handful of other sequences it can be

# one more escape sequence, and the tab follows the command
function _title_precmd { print -Pn '\e]1;%~\a' }   # OSC 1 = tab title
```

Small fixes, all of them. But I only knew to make them because I'd lived with the result for years and felt the absence the instant it was gone.

That is what a framework actually costs you, and what leaving one teaches. The lines you read are the small part. The rest is a dozen quiet kindnesses below the waterline, the ones you never notice until you pull the framework out and reach for the floor and it isn't there.

## Try it

KronuZSH lives at [github.com/Kronuz/KronuZSH](https://github.com/Kronuz/KronuZSH). Clone it, run the installer, open a fresh shell:

```bash
git clone --recursive https://github.com/Kronuz/KronuZSH.git ~/.config/KronuZSH
cd ~/.config/KronuZSH && ./install.sh
exec zsh
```

`install.sh` symlinks the runcoms (`~/.zshrc` and friends) into `$HOME`, backing up anything it replaces, and pulls in the plugin submodules. It's idempotent, and `./install.sh --uninstall` puts your old setup back. The prompt leans on a few [Nerd Font](https://www.nerdfonts.com/) glyphs (the OS logo, the git markers), so point your terminal at one. [JetBrains Mono](https://www.jetbrains.com/lp/mono/) is a safe all-rounder and MesloLGS is the old reliable for a prompt; I keep a longer, opinionated (and surely incomplete) list of coding fonts in the repo at [NerdFonts.md](https://github.com/Kronuz/KronuZSH/blob/main/NerdFonts.md). One iTerm2 gotcha worth knowing: pick the plain `… Nerd Font`, not the `… Nerd Font Mono` variant, or the icons shrink to dots. Without one the prompt still works; the logo just shows as a box. Machine-specific tweaks (host color, the logo, tool hooks) go in a git-ignored `local.zsh`, so the tracked files stay the same everywhere.

## Where it landed

My dotfiles are 700 lines I can hold in my head. The prompt is mine, the bindings are mine, the eight files load in an order I chose, and there's no fork drifting years behind anything. When something's off now, I open a file and fix it, instead of grepping a framework to find out what it had decided on my behalf.

I rebuilt the floor I'd been standing on without looking. It turns out it wasn't much floor. But you have to pull it up to know that, and you have to miss a few boards before you learn what they were holding.
