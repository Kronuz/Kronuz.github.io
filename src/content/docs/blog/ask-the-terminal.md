---
title: "Ask the Terminal"
subtitle: "What your terminal actually means by green"
description: I wanted old commands to keep their syntax colors, only dimmer. That led through zsh highlighting internals, terminal palette queries, and one recursive hook that screamed.
excerpt: Making an old command fade looked like a ten-minute prompt tweak. Then I learned that "green" has no RGB value until the terminal tells you what it chose.
series: "Opening Boxes"
seriesOrder: 9
date: 2026-06-18
draft: true
tags:
  - opening-boxes
  - zsh
  - terminal
---

I had already [pulled my prompt out of Prezto and built a small zsh setup around it](/blog/molting/). That story was about leaving a framework: what I kept, what broke, and which quiet conveniences I had to rebuild. This one starts afterward, with a ten-minute improvement that took three evenings.

I wanted a **transient prompt**. When you press Enter, the full two-line prompt for the command you just ran collapses to a single faded caret, so your scrollback is a clean column instead of a wall of repeated prompts:

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

```ansi
[2m# ask: "what is your color 2 (green), really?"[0m
[36msend →[0m  [1;33m\e]4;2;?\e\\[0m
[35mrecv ←[0m  [1;32m\e]4;2;rgb:8a8a/e2e2/3434\e\\[0m     [2m# 0x8a 0xe2 0x34  →  #8ae234[0m
```

The `\e` is the printable spelling of the ESC byte. The terminal receives the byte, not those two characters.

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

## The marks stayed behind

The prompt looked right to me, but iTerm2 disagreed.

iTerm keeps an [invisible record of each command](https://iterm2.com/documentation-shell-integration.html). A terminal normally sees only a stream of bytes. It does not know that one line is a prompt, the next few characters are something I typed, and everything after Enter came from a program. Shell integration teaches it that grammar by slipping four non-printing `OSC 133` markers into the stream: `A`, `B`, `C`, and `D`.

Suppose I run a command that prints one line and fails. I captured this from the real prompt in an interactive pty, with iTerm detection enabled. Keeping the visible text and the four `OSC 133` boundaries, in their exact relative positions, it is:

```ansi
[31m▶[0m [1;35m\e]133;A\a[0m[38;5;31m~/code/KronuZSH ❯ [0m[1;36m\e]133;B\a[0m[33msh -c 'printf "nope\n"; exit 1'[0m[2m\n[0m
[1;33m\e]133;C;\r\a[0mnope[2m\n[0m
[1;31m\e]133;D;1\a[0m[31m⏎ 1[0m[2m\n[0m
[32m●[0m kronuz at Germans-MacBook-Pro.local[2m\n[0m
[16:14:29] [38;5;39m~/code/KronuZSH ❯❯❯[0m
```

The full prompt at the bottom is unmarked. If I type a second command there and press Enter, `reset-prompt` erases those live lines and replaces them with the next collapsed history line. This time the command succeeds. Keeping the first command above it, the cumulative history is:

```ansi
[31m▶[0m [1;35m\e]133;A\a[0m[38;5;31m~/code/KronuZSH ❯ [0m[1;36m\e]133;B\a[0m[33msh -c 'printf "nope\n"; exit 1'[0m[2m\n[0m
[1;33m\e]133;C;\r\a[0mnope[2m\n[0m
[1;31m\e]133;D;1\a[0m[2;31m⏎ 1[0m[2m\n[0m
[34m▶[0m [1;35m\e]133;A\a[0m[38;5;31m~/code/KronuZSH ❯ [0m[1;36m\e]133;B\a[0m[33mprintf "okay\n"[0m[2m\n[0m
[1;33m\e]133;C;\r\a[0mokay[2m\n[0m
[1;31m\e]133;D;0\a[0m[32m●[0m kronuz at Germans-MacBook-Pro.local[2m\n[0m
[16:14:31] [38;5;39m~/code/KronuZSH ❯❯❯[0m
```

The backslash forms are visible stand-ins for bytes that normally print nothing: `\e` is ESC, `\a` is BEL, `\r` is carriage return, and each dim `\n` marks an actual newline. Magenta is `A`, cyan is `B`, yellow is `C`, and red is `D`. The terminal receives the control bytes, not the backslash notation.

The triangles are different. They are not bytes in the stream; they stand for iTerm's mark indicator in the left margin. An `A` creates a blue mark beside that prompt. When the matching `D` reports a nonzero status, iTerm turns it red. That leaves the failed first command with a red triangle and the successful second command with a blue one. With **Show mark indicators** disabled, the same metadata is retained but the triangles are hidden.

The four sequences are boundaries:

- `\e]133;A\a` says, "the prompt starts here." iTerm puts its gutter mark on that row, and Command-Shift-Up or Command-Shift-Down can jump to it.
- `\e]133;B\a` says, "the prompt is finished; what follows is the editable command." That separates my two-line prompt from the text I typed.
- `\e]133;C;\r\a` says, "Enter was pressed; output starts now." It gives iTerm the output's starting coordinate, after the prompt and command.
- `\e]133;D;1\a` says, "the command is done, and its exit status was 1." iTerm can turn the mark red, calculate how long the command ran from `C` to `D`, and attach both facts to that command. A successful command ends with `\e]133;D;0\a`.

The protocol lifecycle is pleasantly linear: prompt from `A` to `B`, command from `B` to the newline before `C`, execution from `C` to `D`, then another `A` starts the next prompt. The captured transient path is different in one important way: the full prompt after `D` has no `A` or `B`. It is temporary. Its markers are emitted only when Enter collapses it into the next permanent history line.

In the non-transient prompt, `A` and `B` are part of `PROMPT` itself:

```zsh
_kronuz_osc_a=$'%{\e]133;A\a%}'
_kronuz_osc_b=$'%{\e]133;B\a%}'

PROMPT="\${_prompt_kronuz_status_live}\${_kronuz_osc_d}\${_kronuz_osc_a}$kronuz[err] $kronuz[info]$kronuz[context]$kronuz[etctl]$kronuz[git]$kronuz[venv]$kronuz[jobs]$kronuz[nl]$kronuz[time] $kronuz[pwd] $kronuz[prompt] \${_kronuz_osc_b}"
```

The `%{` and `%}` tell zsh that the bytes inside occupy zero columns. Without those guards, zsh counts the invisible sequences as visible text and gets cursor movement and line wrapping wrong. `C` cannot live in `PROMPT` because it happens only after I press Enter, so the `preexec` hook writes it directly. The matching `precmd` hook writes `D` after the command returns, while `$?` still holds the real exit status:

```zsh
# preexec: the command is about to run
print -n '\e]133;C;\r\a'

# precmd: it returned; $ret is the captured $?
print -n "\e]133;D;${ret}\a"
```

A transient prompt is not linear. In my first attempt, iTerm had already seen `A` and `B` around the full prompt by the time I pressed Enter. Then my widget called `reset-prompt`, erased that prompt, and redrew a shorter one in its place. The pixels moved. The markers did not. iTerm still thought the command belonged to the two-line prompt that no longer existed, so its gutter mark landed on the wrong row and its idea of the command's output drifted away from what was on screen.

My first fix was the obvious one: after the redraw, emit a fresh `A` and `B` around the collapsed prompt. That moved the mark to the right place, but left the first pair alive too. One command now had two beginnings. Jumping through history stopped on ghost prompts, and output selection acquired pieces of the prompt I had meant to erase.

The real fix was to stop marking the live prompt at all when transience is enabled. It is only a preview. On Enter, the widget resolves and dims the collapsed `path ❯`, builds a temporary prompt with fresh `A` and `B` boundaries, redraws it, and only then lets zsh accept the command:

```zsh
osc_a=$'%{\e]133;A\a%}'
osc_b=$'%{\e]133;B\a%}'
PROMPT="${status_prefix}${osc_a}${tp}${osc_b}"
zle .reset-prompt
zle .accept-line
```

`status_prefix` is the dimmed `⏎ 1` or running time from the command that just finished. It sits before `A`, so it survives in history without moving the next blue triangle away from the collapsed `path ❯`. An empty Enter takes the same A/B path, but runs no command, so no C/D pair follows. That gives the empty prompt its own triangle and its own Command-Shift-Up stop instead of folding it into the previous command.

There is one consequence I only found by trying **Select Output of Last Command**. iTerm does not end that selection at `D`. [Its source computes the range](https://github.com/gnachman/iTerm2/blob/9272e49d03728e4f56dc18c93a7d2f20bcb3aa73/sources/VT100Screen/VT100ScreenState.m#L1039-L1065) from the command's output coordinate to the start of the next prompt mark. The status is deliberately between those two points, so copied output includes `⏎ 1`. Moving `A` before the status would exclude it, but would also put the gutter triangle beside the status again. I kept the useful result metadata in copied output and kept the triangle on the command line. The alternative was another cursor-positioning trick in code I had just made less patchy.

`C` and the eventual `D;<status>` still attach to the line that actually survives in scrollback. With transience disabled, the normal prompt gets the markers instead. Same four letters, two different paths through them.

iTerm had one more small demand. The shared terminal protocol accepts `OSC 133;C`, but iTerm's own zsh integration emits `OSC 133;C;` followed by a carriage return. That trailing `;\r` matters to its screen-scraping command capture. So KronuZSH sends iTerm the exact form it expects and keeps the parameter-free form for other terminals. It also announces shell integration once with `OSC 1337`, then reports the current host and directory on each prompt. I did not source iTerm's integration script because it would wrap the prompt and emit a second set of the same marks I was already struggling to place.

There was still a second set of marks, just not from the integration script. I was also sending the standard current-directory sequence on every `precmd`:

```zsh
print -Pn '\e]7;file://%M%d\a'
```

I treated `OSC 7` as harmless metadata. In iTerm it is not. I cloned iTerm2 and followed the handler: `setWorkingDirectoryFromURLString` calls `setPathFromURL`, which updates the directory and then calls `setPromptStartLine`. That last call creates a prompt mark. The [source even warns about adjacent marks](https://github.com/gnachman/iTerm2/blob/9272e49d03728e4f56dc18c93a7d2f20bcb3aa73/sources/VT100Screen/VT100ScreenMutableState.m#L3316-L3321) when a shell sends `OSC 7` alongside shell integration.

That explained the triangles none of my `A`, `B`, `C`, and `D` rearrangements could remove. One blue triangle came from `OSC 133;A`. The other came from a directory update I had not known was also a mark. The fix was not another ordering trick. iTerm already receives the same directory through its mark-free `OSC 1337;CurrentDir`, so KronuZSH stopped sending `OSC 7` to iTerm and kept it for other terminals:

```zsh
if (( _kronuz_is_iterm )); then
  print -Pn "\e]1337;RemoteHost=${USER}@%M\a\e]1337;CurrentDir=%d\a"
else
  print -Pn '\e]7;file://%M%d\a'
fi
```

The test was no longer "does the caret fade?" It was: run `sh -c 'printf "nope\\n"; exit 1'`, confirm the collapsed command gets one red triangle, confirm `⏎ 1` persists without a triangle, press Enter on an empty prompt and get a separate blue navigation mark, then select the command's output and see `nope` plus its result metadata but neither prompt. The terminal integration was finally working when the invisible structure agreed with the visible one.

## Where it landed

The finished feature is small: old prompts collapse, exit status and slow-command duration stay in history, old commands keep their syntax colors at half brightness, and terminals that will not report a palette fall back to the xterm values. The prompt still drops all color under [`NO_COLOR`](https://no-color.org/) or on a dumb terminal. The implementation lives in [KronuZSH](https://github.com/Kronuz/KronuZSH), alongside the pty test that runs the real plugin stack and makes sure the recursion stays dead.

The framework migration taught me to own the machinery. This smaller box taught me something more useful: ownership does not mean guessing what the machinery does. Sometimes the machine knows the answer, and the shortest route is to ask it.
