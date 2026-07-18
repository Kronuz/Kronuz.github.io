---
title: "Molting Zsh"
subtitle: "Down to the core"
description: I ran Prezto for years and tuned a 500-line prompt on top of it. This is how I replaced the framework with KronuZSH, the ~1,500-line setup I now maintain myself, and what broke when I pulled my prompt out.
excerpt: I used a sliver of Prezto's 22,000 lines, so I kept the part I cared about—my prompt—and wrote the few hundred lines of shell setup I wanted around it. Then I found out how many small conveniences the framework had been providing all along.
date: 2026-07-14
tags:
  - tooling
  - shell
---

I'd used the same shell setup for years without really looking at it.

It was [Prezto](https://github.com/sorin-ionescu/prezto), a framework for [zsh](https://www.zsh.org/). At some point long ago I'd forked it, tuned it, and stopped thinking about it. The prompt was the part I'd made my own: it had started from another theme, picked up ideas and pieces from a few others, and grown into a 528-line function I'd fussed over until it showed exactly what I wanted—the git state, the Python venv, an exit code when something broke, a tidy path. I rarely thought about everything underneath it.

That changed one evening when I went to update the fork and found it was seven years behind upstream. I had seven years of drift in code I mostly didn't run, all to keep a prompt that barely depended on it. So I opened the directory and counted what I'd been carrying.

## The weight

Prezto is 42 modules and about 22,000 lines of zsh. I loaded a handful of them. The module that mattered to me, the prompt, ships 17 themes; I used the Kronuz theme I'd been maintaining. The rest was an editor module, a completion module, a history module, a syntax-highlighting loader, an init system to wire them all together, and a long tail of integrations for tools I don't use and shells-within-shells I never start.

None of it was bad. It's careful, well-worn code. But it was a whole house built around the one room I lived in, and the house had drifted years out of date while I wasn't looking. Updating it meant reconciling all that drift for the privilege of keeping a 528-line prompt that, when I finally sat and read it, leaned on the framework for almost nothing I couldn't do myself.

So I asked the obvious question. What if I just kept the room?

## KronuZSH

The plan was simple: lift the prompt out of the framework, vendor the handful of plugins I actually load, write the options, history, and completion setup I'd want on any machine anyway, and source those files directly. No general module system and no fork to reconcile—just an explicit core load order and a tiny loader for optional tool integrations.

I called it [KronuZSH](https://github.com/Kronuz/KronuZSH).

```d2 alt="Prezto loaded 42 modules through a general init system to build the shell; KronuZSH sources its core files directly, uses a tiny loader for optional tool integrations, and the prompt stands on its own."
direction: down
old: "Prezto\n42 modules, ~22,000 lines\nan init system wiring them together" { shape: rectangle }
new: "KronuZSH\n11 core files, ~1,500 lines\ndirect load order + tiny integration loader" { shape: rectangle }
old -> new: "kept the one room"
```

The entry point is the whole idea on one screen:

```zsh
# runcoms/zshrc: the interactive entry point (env lives in zshenv)

source "$KRONUZSH/lib/options.zsh"
source "$KRONUZSH/lib/history.zsh"
source "$KRONUZSH/lib/colors.zsh"          # canonical $LS_COLORS, before completion
source "$KRONUZSH/lib/completion.zsh"
source "$KRONUZSH/lib/keybindings.zsh"
source "$KRONUZSH/lib/aliases.zsh"
source "$KRONUZSH/lib/functions.zsh"
source "$KRONUZSH/lib/terminal.zsh"
source "$KRONUZSH/lib/plugins.zsh"
source "$KRONUZSH/integrations/init.zsh"   # optional external tools, each guarded
source "$KRONUZSH/lib/prompt.zsh"

prompt_kronuz_setup
```

Eleven core files, in the order they load, each short enough to read in a sitting. There is no registration layer or async loader deciding what runs when. The one bit of discovery is deliberate: `integrations/init.zsh` finds each `integrations/<tool>/init.zsh` and sources it. Those small, guarded files wire in the modern CLI tools I lean on (fzf, bat, zoxide, ripgrep, and friends) when they're installed and stay silent when they aren't. If ordering ever matters, the loader is simple enough to replace with explicit `source` lines.

![bat rendering lib/aliases.zsh in the Kronuz syntax theme, the same palette shared across bat, delta, eza, and the editor colorschemes.](/img/blog/kronuz-theme-highlight.png)

## Porting the prompt

The prompt was the hard part, and I knew it would be.

Those 528 lines didn't stand alone. They reached into Prezto's plumbing: the editor module told the prompt which keymap was active, a git-info module fed it the repository state, and an async helper kept a slow `git` call from blocking the shell. Pulling out the prompt meant replacing each of those dependencies.

So I did, natively. Git status comes from [gitstatusd](https://github.com/romkatv/gitstatus) when it's there, which is fast, with a plain `git` fallback for when it isn't. The venv, the active keymap, the abbreviated path, all computed directly in the prompt instead of read out of a framework. It came out at 403 lines, leaner than the original, and leaning on nothing but zsh. (It's since grown to about 900, all of it functionality I added in a later overhaul, not weight the framework had been sparing me; the port itself was lean.)

![The KronuZSH prompt: the OS glyph, hostname, a clean git segment and a Python venv marker, then the time, working directory, and caret, over a color-coded directory listing.](/img/blog/kronuzsh-prompt.png)

The prompt now also collapses old prompts to a quiet `path ❯ command` line. A failure
or slow command shows its exit code or duration immediately above the next live prompt;
when I run the next command, that visual status disappears with the full prompt. In
iTerm2 the command mark keeps the historical exit status and running time, so the
information remains available without filling scrollback with another line per command.

The port was not clean. The best bug took an afternoon.

After the move, my prompt rendered as literal text: `${(e)...}` printed right there on the line, the segments never expanding. It worked in every quick test I tried. It only broke in a real terminal. The culprit was a single option, `PROMPT_SUBST`, that Prezto's prompt module had been quietly setting from a `$prompt_opts` variable I'd never heard of. The framework turned it on; my port didn't; zsh dutifully printed my prompt's expansion syntax verbatim. The reason my tests passed is the worse half: a sandboxed `${(e)PROMPT}` check expands the prompt itself, so it always looked right. The only thing that told the truth was a fresh shell on the actual machine.

There were smaller ones. gitstatusd needs job control, so it fails in a shell with no tty, and the direct-`git` fallback has to cover it. `ls` colors are a GNU-versus-BSD coin flip that has to be detected, not assumed. macOS sets `HISTFILE` in `/etc/zshrc` before my config even runs. Each was a small thing the framework had been smoothing over, and each was now mine to smooth.

## What I kept, by the numbers

When it settled, the trade looked like this:

| | Prezto | KronuZSH |
|---|---|---|
| zsh source | ~22,000 lines | ~1,000 lines |
| files / modules | 42 modules | 14 files |
| the prompt | 528 lines, in the framework | 403 lines, standalone |
| plugins | a module loader | 4 git submodules, sourced explicitly |

About twenty times less code, and the part I cared about came out standalone and free. I symlinked it onto my laptop and my dev VM, archived the old `.zprezto`, and for the first time in years my shell was something I'd read end to end.

The result worked, but for the first few days it didn't feel quite right.

## The things you don't notice

For a few days after the switch, small things were subtly wrong, and I couldn't always say what.

I'd hit Ctrl-W to rub out the last bit of a path, the way I have for a decade, and the whole path would vanish instead of stopping at the last slash. I'd reach for Option+Left to jump back a word and the cursor wouldn't budge. The terminal tab, which had always shown whatever command was running, just sat there with the directory.

I hadn't configured any of these things myself. I'd never written a line about Ctrl-W or tab titles. Prezto's editor module set `WORDCHARS` so that `/` counted as a word boundary, which is why Ctrl-W stopped at slashes. It bound several escape sequences for Option and Ctrl arrows, so word-jumping worked regardless of what the terminal sent. Its terminal module emitted the [escape sequences](https://en.wikipedia.org/wiki/ANSI_escape_code#OSC_(Operating_System_Command)) that name the tab. Prezto had handled all of it for years, and I'd mistaken that behavior for a terminal default.

Restoring each one was a few lines:

```zsh
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

That was the useful lesson in leaving a framework. Its visible features are only part of what you depend on; the rest are small defaults you stop noticing after years of use. Removing Prezto made those defaults visible again, one missing key binding at a time.

## Try it

KronuZSH lives at [github.com/Kronuz/KronuZSH](https://github.com/Kronuz/KronuZSH). Clone it, run the installer, open a fresh shell:

```sh
git clone --recursive https://github.com/Kronuz/KronuZSH.git ~/.config/KronuZSH
cd ~/.config/KronuZSH && ./install.sh
exec zsh
```

`install.sh` symlinks the runcoms (`~/.zshrc` and friends) into `$HOME`, backing up anything it replaces, and pulls in the plugin submodules. It's idempotent, and `./install.sh --uninstall` puts your old setup back. The prompt leans on a few [Nerd Font](https://www.nerdfonts.com/) glyphs (the OS logo, the git markers), so point your terminal at one. [JetBrains Mono](https://www.jetbrains.com/lp/mono/) is a safe all-rounder and MesloLGS is the old reliable for a prompt; I keep a longer, opinionated (and surely incomplete) list of coding fonts in the repo at [nerd_fonts.md](https://github.com/Kronuz/KronuZSH/blob/main/nerd_fonts.md). One iTerm2 gotcha worth knowing: pick the plain `… Nerd Font`, not the `… Nerd Font Mono` variant, or the icons shrink to dots. Without one the prompt still works; the logo just shows as a box. Machine-specific tweaks (host color, the logo, tool hooks) go in a git-ignored `~/.zshrc.local`, so the tracked files stay the same everywhere.

## Where it landed

My dotfiles are about 1,500 lines I can hold in my head. I know where the prompt and bindings live, the files load in an order I chose, and there's no fork drifting years behind upstream. When something's off now, I open the relevant file instead of grepping a framework to find out where the behavior came from.

I ended up rebuilding less than I'd expected. The tricky part wasn't writing it; it was noticing everything I needed to replace.
