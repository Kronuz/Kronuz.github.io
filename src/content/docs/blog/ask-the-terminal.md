---
title: "Ask the Terminal"
subtitle: "Dropping the framework and rebuilding my zsh prompt, one escape code at a time."
description: I tore my zsh prompt off its framework and rebuilt it by hand. The hardest part was making old commands fade, which taught me that "green" is not a color your terminal agrees with until you ask it.
excerpt: I had been running someone else's prompt for years, forking a five-process pipeline on every Enter and writing to a debug file I had forgotten in /tmp. So I tore it off the framework and rebuilt it by hand. The fun part was learning that my terminal's green is not the green I thought.
series: "Opening Boxes"
seriesOrder: 9
date: 2026-06-18
draft: true
tags:
  - opening-boxes
  - zsh
  - terminal
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). The others are boxes from my past. This one I built last, [kronuzsh](https://github.com/Kronuz/kronuzsh), my own zsh setup, and it has a smaller box inside it: what your terminal actually means by "green."*

You press Enter a few hundred times a day. Each time, for years, my prompt was forking a five-process pipeline to find my own IP address, and appending a line to a debug file I had left in `/tmp` and forgotten. I never noticed. The prompt looked fine. That is the thing about a prompt: you read it constantly and you never actually look at it.

It was not really my prompt, either. It was a theme that shipped with [prezto](https://github.com/sorin-ionescu/prezto), the zsh framework I had run for years. I had tuned its colors until it felt like mine, but the machinery underneath belonged to the framework: an async worker, a module loader, a dozen files cooperating to draw two lines of text. When I finally opened it up, I found the IP lookup that ran on every render,

```sh
ifconfig | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}'
```

five processes spawned every time the prompt drew, just to print a number that changes maybe once a week. And below it, a stray `echo >> /tmp/prompt_kronuz` that some past version of me had used to debug something and never removed. It had been writing to that file on every prompt, on every machine, for years.

So over a few evenings I did the unreasonable thing and tore the whole prompt off the framework.

## Owning the two lines

The plan was simple and a little arrogant: keep only the part that was actually mine, the look, and replace every framework dependency under it with a small native piece. No `pmodload`, no `vcs_info`, no async worker. Just zsh, and code I could read in one sitting.

The framework had been doing five jobs for me. Here is what replaced each one.

| prezto module | replaced by |
| --- | --- |
| `git-info` + an async worker | [gitstatus](https://github.com/romkatv/gitstatus) (`gitstatusd`), with a direct-`git` fallback |
| `python-info` (the venv) | a six-line segment reading `$VIRTUAL_ENV` |
| `editor-info` (vi/emacs keymap) | a couple of `zle` hooks |
| `prompt-pwd` | `${(%):-%~}`, one parameter expansion |
| `spectrum` (the color palette) | a palette defined inline, in the file |

The async worker was the one I expected to miss. A git prompt has to run `git status` in a repo, and in a big repo that is slow enough to stutter every keystroke, which is the whole reason prezto spawns a background worker to do it. I did not rebuild the worker. I handed the job to [`gitstatusd`](https://github.com/romkatv/gitstatus), Roman Perepelitsa's daemon that keeps a warm cache and answers in microseconds, and wrote a lean direct-`git` fallback for when the daemon is not there (no tty, not installed, a locked-down box). The prompt always shows git, fast when the daemon is up, correct when it is not.

What came out the other side was one file, about 700 lines, that I own end to end. That sounds like more code than a framework module. It is. It is also the entire prompt, with nothing underneath it I have not read.

## The unglamorous half

Owning the whole thing means owning the parts nobody screenshots.

A prompt should not break when it lands somewhere strange. So the glyphs come in two full sets: the polished [Nerd Font](https://www.nerdfonts.com/) icons by default, and a plain-Unicode fallback that renders in any font, chosen with one switch. On a `dumb` terminal (Emacs `M-x shell`, some CI logs) it drops to plain glyphs automatically, because a Private-Use-Area icon there is just tofu. And the whole color layer collapses to nothing under [`NO_COLOR`](https://no-color.org/) or a dumb terminal: the full layout still renders, with zero escape codes. I check that every prompt, so flipping `NO_COLOR` takes effect on the next line, not the next shell.

The colors themselves got the modern treatment too. The 16 base ANSI slots stay as `%F{0..15}` so they follow your terminal theme, but the 240 others are now exact 24-bit hex, downsampled by `zsh/nearcolor` on terminals that cannot do truecolor. One palette, every tier, from a truecolor iTerm down to an eight-color tty.

None of that is exciting. All of it is the difference between a prompt that is mine and a prompt that is mine *only on my machine*.

## The part I thought would be easy

Now the fun began, which is to say the part where a one-line idea ate three evenings.

I added a **transient prompt**. When you press Enter, the full two-line prompt for the command you just ran collapses to a single faded caret, so your scrollback is a clean column instead of a wall of repeated prompts:

```ansi
[2m# before: every past command keeps its whole two-line prompt[0m
[32m●[0m [1;37mgmendezb[0m at [34mhost[0m [90m(10.0.0.5)[0m  [90m⎇[0m [1;37mmain[0m  [1;31m❯[0m[1;33m❯[0m[1;32m❯[0m cd src
[32m●[0m [1;37mgmendezb[0m at [34mhost[0m [90m(10.0.0.5)[0m  [90m⎇[0m [1;37msrc[0m   [1;31m❯[0m[1;33m❯[0m[1;32m❯[0m make
[32m●[0m [1;37mgmendezb[0m at [34mhost[0m [90m(10.0.0.5)[0m  [90m⎇[0m [1;37msrc[0m   [1;31m❯[0m[1;33m❯[0m[1;32m❯[0m ./run

[2m# after: past commands collapse to a faded caret; only the live prompt stays full[0m
[2m❯ cd src[0m
[2m❯ make[0m
[2m❯ ./run[0m
[32m●[0m [1;37mgmendezb[0m at [34mhost[0m [90m(10.0.0.5)[0m  [90m⎇[0m [1;37mmain[0m  [1;31m❯[0m[1;33m❯[0m[1;32m❯[0m
```

I liked it immediately. Then I wanted one more thing: the command you typed should fade too, the way old history feels old. Keep its syntax colors, just dimmer. A trivial ask. I budgeted ten minutes.

zsh paints the command line through an array called `region_highlight`, a list of "from here to here, in this style" spans. So I would just add a `faint` attribute to each span and be done.

zsh does not have a `faint` attribute. `region_highlight` understands `bold`, `underline`, and `standout`, and silently ignores everything else. There is no dim. You cannot tell zsh "the same, but darker."

If the terminal will not dim a color for me, I will dim it myself. Take each color the syntax highlighter chose, pull it apart into red, green, blue, scale all three toward black, and hand back the darker version. Real arithmetic instead of an attribute. I wired it up, set the factor to a gentle 0.7, pressed Enter, and the faded command came back the wrong color.

## What color is green?

Not a little wrong. The greens went olive, the blues went muddy. I lowered the factor to almost nothing, 0.99, barely a fade at all, and the hue *still* shifted. The math was not the problem. The math was halving numbers. The problem was which numbers.

The syntax highlighter does not color a command with hex codes. It uses names: a command is `fg=green`, a string is `fg=yellow`, a path is `fg=magenta`. To darken green I first had to turn the word "green" into red, green, blue, and that is where the ground opened up. There is no such thing as the RGB of "green." There is only what *your terminal* has decided green looks like.

| Where "green" gets defined | RGB |
| --- | --- |
| VGA / old Windows console | `#008000` |
| xterm default | `#00cd00` |
| my iTerm2 theme | `#8ae234` |

My green, the actual one glowing on my screen, is `#8ae234`, a bright lime. My darkening code had been assuming xterm's `#00cd00`, a deeper, bluer green. I was not dimming the green on my screen. I was dimming a *different green that happened to share its name*, and of course the result looked wrong, because it started wrong. The fade was honest; the color it faded was a guess.

I had no framework to ask. There was no `python-info` to hand me the truth. There was just me and the terminal. So I asked the terminal.

It turns out you can. There is an escape sequence, `OSC 4`, that means "tell me what color number N really is." You write the question to the terminal and it writes the answer back:

```text
# ask: "what is your color 2 (green), really?"
send →  \e]4;2;?\e\\
recv ←  \e]4;2;rgb:8a8a/e2e2/3434\e\\     # 0x8a 0xe2 0x34  →  #8ae234
```

There it was. `#8ae234`, straight from iTerm, no guessing. So at startup the prompt now asks the terminal for all sixteen of its ANSI colors, once, and caches the answers. When it dims `fg=green`, it darkens *that* green. Halved, `#8ae234` becomes `#45711a`: same hue, genuinely darker, the faded-history look I wanted three evenings earlier. If a terminal does not answer, it falls back to the xterm table and life goes on.

The lesson was the whole post in miniature. With the framework gone, there was no abstraction left between me and the machine, and the answer to "what is true" was not in a config file or a module. It was in the terminal, and I could just ask.

## The loop that screamed

I shipped the dimming, felt good about it, and a day later saw this sitting on top of a window I was not even typing in:

```text
azhw:zle-line-finish:3: maximum nested function level reached; increase FUNCNEST?
```

`FUNCNEST` is zsh's circuit breaker for infinite recursion. Something I wrote was calling itself forever.

To re-dim the command after the syntax highlighter painted it, I had hooked the moment the line finishes, `zle-line-finish`. Reasonable. The trouble is that [fast-syntax-highlighting](https://github.com/zdharma-continuum/fast-syntax-highlighting), which does the painting, *also* wraps that same widget, and it re-wraps it fresh on every prompt. My hook and its wrapper got tangled: the dispatcher zsh builds to hold multiple hooks ended up, after fsh rebuilt itself, calling back through the very wrapper it was supposed to sit beside.

```d2 alt="The recursion cycle: a restyle hook on zle-line-finish, fast-syntax-highlighting re-wrapping that same widget every prompt, and the saved original calling back through the wrapper, looping until zsh aborts with a nesting error"
direction: down
hook: "restyle hook on zle-line-finish"
fsh: "fsh re-wraps the widget"
orig: "saved original calls back in"
hook -> fsh
fsh -> orig
orig -> hook: "loops until zsh aborts"
```

The fix was to stop fighting over the widget. Instead of hooking `zle-line-finish`, I wrap the highlighter's own function once, and let it run normally, then re-apply my dimming on top only while a one-line flag is set. No widget rebinding, so there is nothing for fsh to re-wrap, and nothing to loop. As a bonus it covers a case the hook missed: the highlighter rebuilds its colors unconditionally when the line finishes, so a pasted command, which it would otherwise skip, now dims too.

I tested it the only way that is honest for a prompt, which is in a real terminal pressing real Enters: a pty running the full plugin stack, eight commands, each forced to fail so the exit-code path ran too. Zero recursion errors, empty stderr. The screaming stopped.

## Where it landed

What I have now is two lines of text with nothing under them I did not write.

- **One file, ~700 lines.** Down from a theme plus a framework plus an async worker plus a module loader.
- **Five prezto pieces** replaced by native zsh and one daemon.
- **A five-process fork per render, gone** (cached, with a 10-second TTL), and that `/tmp` debug line gone with the framework it rode in on.
- **One palette** that renders truecolor on iTerm, 256-color on an older terminal, and zero-escape plaintext on a dumb one or under `NO_COLOR`.
- **30 commits over three evenings**, and a [manual](https://github.com/Kronuz/kronuzsh) so future-me remembers which knob does what.

It is public, if you want to take it apart: [`kronuzsh`](https://github.com/Kronuz/kronuzsh). I lean on real giants for the hard parts, `gitstatusd` for the git and the Nerd Fonts project for the glyphs, and I am glad I do. Owning the prompt never meant writing everything. It meant knowing what every line does, and having somewhere to stand when one of them lies to me.

## The company it keeps

A prompt does not live alone on the line. A few zsh plugins do the interactive work around it, and they are the other half of why the shell feels good. fast-syntax-highlighting colors a command as you type it, so a misspelled command name turns red before you press Enter. [zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions) ghosts the rest of a line in grey from your history, so yesterday's command is one right-arrow away. [zsh-history-substring-search](https://github.com/zsh-users/zsh-history-substring-search) lets you type a fragment, press Up, and walk only the history that matches. None of them are mine. All of them are load-bearing.

Under that sits a quieter layer worth stealing: the integrations. Each wires a modern command-line tool into the shell, but only when you actually have it. A check for the binary guards every one, so the same config runs on my laptop, a fresh VM, or a locked-down box with none of them, and lights up the moment one shows up. Install a few and the day gets nicer: [eza](https://github.com/eza-community/eza) for `ls` (icons, colors, a git column), [bat](https://github.com/sharkdp/bat) for `cat` (syntax and a diff gutter), [fd](https://github.com/sharkdp/fd) for `find`, [ripgrep](https://github.com/BurntSushi/ripgrep) for `grep`, [delta](https://github.com/dandavison/delta) for git diffs, [zoxide](https://github.com/ajeetdsouza/zoxide) for a `cd` that learns where you go, and [fzf](https://github.com/junegunn/fzf) for a fuzzy `Ctrl-R` through your history. The full list is in the repo; install whichever you like and the shell finds them.

This was the same instinct as [the rest of this series](/blog/css-that-computes/): take a thing someone else built, open it up until you understand every line, and rebuild it as your own. A prompt is a small box. But I look at it a few hundred times a day, and now when it fades a command to grey-green, it is fading the right green, because I stopped guessing and asked.
