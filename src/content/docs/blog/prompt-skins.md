---
title: "Impressions"
subtitle: "One prompt, wearing every other prompt's face."
description: "KronuZSH's whole layout is deferred, so a few lines in ~/.zshrc.local reshape it into anything: pure, robbyrussell, an agnoster ribbon, a DOS box. How the layout comes loose, the palette that keeps it safe, and the one invariant a skin can't break."
excerpt: "The serious case for a home-made prompt was speed and size. The fun one is this: because the whole layout is yours, the prompt can do impressions. Here it is as pure, as robbyrussell, as an agnoster ribbon, as a DOS box, the same engine under every face."
series: "KronuZSH"
seriesOrder: 5
date: 2026-07-24
authors: kronuz
draft: true
tags:
  - tooling
  - shell
  - zsh
  - terminal
  - prompt
---

[Part 4](/blog/prompt-worth-it/) made the serious case: a home-made prompt can paint as fast as the giants and carry a fiftieth of their code. This is the unserious case, and it is the one I enjoy most.

Because the whole layout is a handful of lines I own, the prompt is not condemned to look like mine. It can do impressions. Here it is wearing [pure](https://github.com/sindresorhus/pure)'s two-line face:

```ansi
[34m~/project[39m [38;2;135;135;135mmain*[0m[38;2;135;135;135m[24m[38;2;135;135;135m[27m[38;2;135;135;135m[39m[49m[K
[35m❯[39m 
```

...[oh-my-zsh](https://ohmyz.sh/)'s robbyrussell:

```ansi
[32m➜[39m  [36mproject[39m [34mgit:([31mmain[34m)[0m[34m[24m[34m[27m[34m[39m[49m [33m✗[0m[33m[24m[33m[27m[33m[39m[49m 
```

...an [agnoster](https://github.com/agnoster/agnoster-zsh-theme) ribbon:

```ansi
[48;2;135;135;135m[38;2;255;255;255m you@laptop [90m[44m[38;2;255;255;255m ~/project [42m[34m[38;2;135;135;135m  main [49m[32m[39m 
```

...and, because nothing was stopping me, a DOS box from 1994:

```ansi
[1m[32mC:\project\>[39m[0m 
```

Same engine under every one. The same ~7 ms paint, the same gitstatusd, the same shell-integration marks. Only the costume changes. Here is how the costume comes off.

## The layout came loose

For most of this project the layout was welded shut. `PROMPT` was assembled once, at startup, with the segments in the order I liked: an error dot, user at host, git, then a second line with the time, the path, the caret. To change the shape you opened the engine and edited it.

That is fine while the shape is mine. It is useless if I want anyone else to reshape it without touching the file. So I lifted the layout out of the engine and into three variables you set from `~/.zshrc.local`:

- `PROMPT_KRONUZ_PROMPT`, the live prompt (one line, or two).
- `PROMPT_KRONUZ_RPROMPT`, the right prompt.
- `PROMPT_KRONUZ_TRANSIENT_PROMPT`, the collapsed line [the scrollback trick](/blog/prompt-scrollback/) leaves behind.

Set any of them and the prompt takes the new shape at the very next draw. No rebuild, no reload, no restart.

Getting there took one trick that is not obvious. `PROMPT` is a template zsh re-expands on every draw, with `PROMPT_SUBST` on. A segment like `$kz[git]` works because it sits *literally* in that template, so each redraw re-parses it and resolves it. A layout handed in through a variable is a different animal: when zsh expands `$PROMPT_KRONUZ_PROMPT`, what comes back is *data*, a finished string, not fresh syntax to parse again. A single `${(e)...}` evaluates it once and stops, and the `$kz[git]` inside falls out as ten literal characters, unresolved.

The fix is to evaluate twice, in the one pass:

```zsh
# one PROMPT_SUBST pass, two levels: the layout, then the segments it named
PROMPT='${(e)${(e)PROMPT_KRONUZ_PROMPT-$DEFAULT_PROMPT_KRONUZ_PROMPT}}'
```

The inner `${(e)}` resolves the layout string; the outer one resolves the `$kz[...]` segments that string just produced. Both ride the single expansion zsh already does per draw, so a skin costs nothing at render time. It reads like a stutter. It is load-bearing.

## A palette, and the trap in it

A skin composes from two sets. The segment palette, `$kz[git]`, `$kz[pwd]`, `$kz[time]` and the rest, each a ready-made piece. And the colour palette, `$kz[FG.blue]` for a foreground, `$kz[BG.blue]` for a background. So *minimal*, the entire skin, is one line:

```zsh
PROMPT_KRONUZ_PROMPT='$kz[pwd]$kz[git] ${kz[FG.magenta]}${kz[GLYPH.caret]}${kz[RESET]} '
```

```ansi
[38;2;255;255;255m~/project[0m[38;2;255;255;255m[24m[38;2;255;255;255m[27m[38;2;255;255;255m[39m[49m [90m[0m[90m[24m[90m[27m[90m[39m[49m [1m[38;2;255;255;255mmain[0m[38;2;255;255;255m[24m[38;2;255;255;255m[27m[38;2;255;255;255m[39m[49m [90m[0m[90m[24m[90m[27m[90m[39m[49m [38;2;255;255;255morigin/main[0m[38;2;255;255;255m[24m[38;2;255;255;255m[27m[38;2;255;255;255m[39m[49m[90m ([0m[90m[24m[90m[27m[90m[39m[49m[38;2;175;175;255m 1[0m[38;2;175;175;255m[24m[38;2;175;175;255m[27m[38;2;175;175;255m[39m[49m [38;2;135;95;0m✗[0m[38;2;135;95;0m[24m[38;2;135;95;0m[27m[38;2;135;95;0m[39m[49m [38;2;135;255;0m⇡1[0m[38;2;135;255;0m[24m[38;2;135;255;0m[27m[38;2;135;255;0m[39m[49m [38;2;215;95;0m 2[0m[38;2;215;95;0m[24m[38;2;215;95;0m[27m[38;2;215;95;0m[39m[49m [31m 1[0m[31m[24m[31m[27m[31m[39m[49m [90m⊖1[0m[90m[24m[90m[27m[90m[39m[49m[90m)[0m[90m[24m[90m[27m[90m[39m[49m [35m❯[0m[35m[24m[35m[27m[35m[39m[49m 
```

You might ask why I reach for `${kz[FG.magenta]}` when zsh's own `%F{magenta}` is shorter and paints the same colour. I used to. It cost me an evening.

The moment a colour goes *inside* a conditional, `%F{}` turns on you. Say the branch should appear only when there is one:

```zsh
# looks right, renders as a truncated mess
'${kz[git.branch]:+ %F{blue}(${kz[git.branch]})%f}'
```

zsh reads `${name:+word}` by scanning for the brace that closes `word`. `%F{blue}` brought a brace of its own, and the `}` after `blue` is the first one zsh meets, so it decides the conditional ends *there*. Half the segment falls on the floor. `${kz[FG.blue]}` is a balanced `${...}`; zsh counts it right, and the segment stays whole. The palette earns its keep twice: once for theming a colour, and once for being a colour you can drop inside a conditional without it biting.

That is the whole reason the robbyrussell impression up top is only two lines, `git:(branch)` and all:

```zsh
PROMPT_KRONUZ_GIT='${kz[git.branch]:+ ${kz[FG.blue]}git:(${kz[FG.red]}${kz[git.branch]}${kz[FG.blue]})${kz[RESET]}${kz[git.dirty]:+ ${kz[FG.yellow]}✗${kz[RESET]}}}'
PROMPT_KRONUZ_PROMPT='%(?.${kz[FG.green]}.${kz[FG.red]})➜%f  ${kz[FG.cyan]}%c%f$kz[git] '
```

Two lines to wear oh-my-zsh's flagship theme, reading git from the same daemon, inside the same paint budget.

## The wild end

Once the layout is loose, taste is the only limit, and I have little. The DOS box up top is one line, the path as a drive letter, bold green on the memory of a CRT:

```zsh
PROMPT_KRONUZ_PROMPT='%B${kz[FG.green]}C:\\${PWD:t}\\>%f%b '
```

Or an all-emoji line: a folder, a plant for the branch, a small fire when the tree is dirty, a spark for the caret:

```ansi
📁 [36m~/project[39m 🌿 [32mmain[0m[32m[24m[32m[27m[32m[39m[49m 🔥 ⚡ 
```

The agnoster ribbon up top wanted one thing the rest did not: backgrounds. The palette is just colour codes now, layer-neutral, so the engine wraps each hue both ways: `${kz[FG.green]}` paints it as a foreground, `${kz[BG.green]}` the same code as a background. A powerline skin fills its blocks with the `BG.` side. Nerd Font separators, solid colour, the whole agnoster silhouette, out of the engine that a line ago was a DOS box.

## The one thing a skin can't break

There is exactly one rule, and you will not trip it by accident. Every prompt this shell draws is wrapped in the OSC 133 marks that tell the terminal where a command begins and ends, and the OSC 1337 marks iTerm reads for the same purpose. Those live in the engine, wrapped *around* whatever a skin renders, so [the quiet scrollback](/blog/prompt-scrollback/), the command boundaries, iTerm's jump-to-previous-command, all of it survives any costume you hang on the prompt.

I did not want to take that on faith. So there is a small harness that renders a skin in a throwaway shell, no terminal attached, and asserts the marks are still there:

```
dev/preview-skin.py skins/robbyrussell.zsh
```

It prints the prompt and fails loudly the instant a skin drops a mark. Every impression above went through it before it earned a file.

## Yours now

They all live in [`skins/`](https://github.com/Kronuz/KronuZSH/tree/main/skins), a few lines each. Copy one into your `~/.zshrc.local`, or delete an `%F` and write your own in the time it takes your coffee to cool. That was the arc of these five posts. Not that my prompt is the one to use, but that the file got small enough, and now loose enough, that the one to use is the one you shape.

Go wild.
