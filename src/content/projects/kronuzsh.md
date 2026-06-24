---
title: KronuZSH
tagline: A thin, prezto-free zsh setup
description: "My zsh setup: a ported prompt, three plugins, and gitstatus, with no framework underneath."
tech: [Zsh, Shell]
repo: https://github.com/Kronuz/KronuZSH
status: active
order: 8
---

KronuZSH is my zsh setup, stripped down to the parts I actually use. It replaces a prezto
fork that had drifted seven years behind upstream with something I own end to end: my
prompt, three plugins, and a small amount of config, with no framework magic underneath.

It's deliberately small. The prompt is one file, ported off prezto, with git status coming
from [gitstatus](https://github.com/romkatv/gitstatus) and tiny native replacements for the
prezto bits I kept (venv indicator, vi/emacs keymap, pwd). Past prompts collapse to a
compact `path ❯` line, and a slow or failed command leaves a one-line marker behind in
scrollback. The config lives in one named file per concern (`options.zsh`, `history.zsh`,
`completion.zsh`, and so on), so when you want to change something, the file it lives in is
obvious. The guiding rule is to keep only the genuinely useful parts, lean and easy to find,
and prefer zsh-native over a vendored module.

It also wires in a set of modern CLI tools when they're installed and silently skips them
when they aren't (fzf, fd, zoxide, bat, ripgrep, git-delta, eza, yazi), so the same config
works on my laptop, a fresh box, or a locked-down server with none of them. The colored
tools share one Kronuz look, generated from the same source of truth as my
[VS Code](https://github.com/Kronuz/kronuz-theme-vscode) and Sublime themes, so my terminal,
my editor, and my diffs all match.
