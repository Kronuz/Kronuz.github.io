---
title: "The Session Smith"
subtitle: "One workbench for Claude, Codex, and Copilot"
description: "AgentSmith is a local command-line workbench for finding, inspecting, resuming, exporting, moving, and cleaning sessions from Claude Code, Codex, and GitHub Copilot CLI."
excerpt: "Coding agents remember plenty, each in a different place and shape. AgentSmith works those native stores into one directory-centered command line without flattening away where the work came from."
date: 2026-07-24
draft: true
authors: kronuz
tags:
  - ai
  - agents
  - cli
  - developer-tools
---

[AgentSmith](https://github.com/Kronuz/AgentSmith) is a local command-line workbench for the sessions that [Claude Code](https://code.claude.com/docs/en/sessions), [Codex](https://github.com/openai/codex), and [GitHub Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/chronicle) leave on your machine. It finds them, reads them, searches them, measures them, resumes them, exports them, and cleans them up. The working directory is the common thread.

That last part is the one I care about.

I do not wake up thinking, "I should resume session `019c7390-55cc-7e83-9537-e7534558d473`." I think, "I was working on AgentSmith." The repository is what I remember. The session ID is bookkeeping.

```sh
cd ~/code/AgentSmith
asmith ls --here
asmith resume codex
```

AgentSmith makes the directory the handle and lets the native agent remain the engine.

## Three metals on the bench

The three agents all preserve useful history. They simply disagree on its shape.

Claude Code keeps project-scoped JSONL conversations, including adjacent subagent material. Codex combines rollout files with a SQLite thread index. Copilot CLI has session-state files, an index, usage data, and its own rules for which records can still be resumed. Their token accounting does not line up either. Cache reads, cache writes, reasoning tokens, child agents, and Copilot's AIU belong to different ledgers.

None of this is bad design. Each store serves its own agent. It becomes awkward when one repository has been touched by all three.

```console
$ asmith ls --here
* codex    019c7390   18m    42 turns  ~/code/project  Tighten the parser
* claude   bbe91a64    2h    19 turns  ~/code/project  Trace config loading
* copilot  7a3fc324    1d     8 turns  ~/code/project  Add import validation
```

The source label stays visible because normalization should not become laundering. A Codex turn remains a Codex turn. A Copilot AIU does not quietly turn into a Claude token. AgentSmith works each native store through a backend, then exposes the pieces that can be compared honestly: identity, directory, timestamps, messages, touched files, resumability, and usage.

```d2 alt="AgentSmith normalizes three native session stores around a working directory"
direction: down

directory: "working directory" { style.bold: true }
stores: "native session stores\nClaude · Codex · Copilot"
agentsmith: "AgentSmith\nnormalized view"
actions: "list · inspect · search · usage\nresume · export · merge"

directory -> agentsmith
stores -> agentsmith
agentsmith -> actions
```

Think of it as a smith. The three stores never get poured into one anonymous vat. Their internals are heated just enough to become workable, while provenance and native artifacts survive the hammer.

## The everyday workbench

The command is `asmith`. Most days, five commands cover the ground:

```console
$ asmith ls -n 15       # recent sessions across all three agents
$ asmith ls --here      # sessions attached to this directory
$ asmith tree           # group the whole history by directory
$ asmith show 019c7390  # metadata, files, usage, and resume details
$ asmith dump 019c7390  # render the conversation
```

Every listing says which agent produced each row. Full IDs work, but a unique prefix is enough. Paths work where they make sense, so `asmith show .`, `asmith files .`, and `asmith usage .` follow the newest matching session for the current directory.

There is one search across all three stores:

```sh
asmith search "palette cache"
asmith grep 'OSC 133.*precmd' .
```

`search` finds a literal phrase across sessions. `grep` runs a regular expression over rendered transcripts. `dump` can include tool arguments, results, reasoning, or nested subagents, and it can render Markdown when the terminal is no longer the right place to read a long conversation.

Usage gets the same treatment. AgentSmith keeps each model's fresh input, output, cache, and reasoning counts separate, then offers an explicitly estimated weighted-token count for ranking sessions across agents. The estimate is for comparison. Each native count remains beside it.

## Resume the project

Each native CLI already knows how to resume its own sessions. Claude Code, for example, scopes session lookup to the current project and its worktrees. Copilot records enough local state to resume and also offers its broader Chronicle history. AgentSmith does not replace those mechanisms.

It chooses the newest resumable native session for a directory and calls the right one:

```sh
asmith resume claude
asmith resume codex ~/code/KronuZSH
asmith resume copilot ~/code/AgentSmith
```

The optional shell integration goes one step further. Calling `claude`, `codex`, or `copilot` with no arguments resumes the current directory when possible, and starts normally when there is nothing to resume. Arguments pass straight through to the real CLI.

Directories become lightweight session names without creating another session database.

## Carry the work with you

A rendered transcript is useful, but it is not always the whole job. Sessions can have native sidecars, child-agent conversations, memory, project instructions, settings, hooks, and skills. AgentSmith exports the material it can attribute by default and records it in a checksummed directory bundle:

```text
project-export/
├── manifest.json
├── sessions/
│   ├── claude/<id>/
│   ├── codex/<id>/
│   └── copilot/<id>/
├── project-memory/
└── environment/
```

Export the current project, copy the directory to another machine, and verify it there:

```sh
asmith export . -o ~/exports/agentsmith
asmith verify ~/exports/agentsmith
```

Multiple session IDs or project directories can go into one bundle. Path selection is exact unless `--recursive` is explicit, which keeps a careless parent-directory export from swallowing every nested project.

Import is conservative. AgentSmith does not forge a Claude conversation into Codex's private database and hope the schema remains stable. It prepares a readable, agent-neutral handoff from one or more bundles or old dumps. The destination agent reads that handoff and creates a real session of its own:

```sh
handoff=$(asmith import ~/exports/agentsmith -o ~/imports/agentsmith)
asmith launch codex "$handoff"
```

`merge` starts from live sessions instead of exported material:

```sh
handoff=$(asmith merge . -o ~/imports/combined-history)
asmith launch claude "$handoff"
```

The prepared directory remains inspectable before launch. Project context stays with the project. Global instructions, hooks, skills, and configuration have their own `--global` export, so a user-wide rule is not copied into every project bundle.

This is continuation with provenance. The source remains available, omissions are named, and the new agent owns the new session.

## The neighboring anvils

There is good prior art around this problem.

[Agent Sessions](https://github.com/jazzyalex/agent-sessions) is a polished, local-first macOS application for browsing, searching, analyzing, and resuming history from a wide range of agents. It covers more harnesses than AgentSmith and gives the work a proper visual cockpit.

[Agent Capsule](https://github.com/z2z23n0/agent-capsule) focuses on sharing a complete Codex or Claude conversation and continuing it as a native local session. [codex-claude-transfer](https://github.com/ahmojo/codex-claude-transfer) goes directly after translation, portable bundles, sync, and native import between those two agents. [agent-session-resume](https://github.com/hacktivist123/agent-session-resume) approaches continuation as a reusable skill that reconstructs context for the next agent.

AgentSmith sits a little lower and wider in the toolbox. It is a scriptable CLI for three local stores, organized around directories, with inspection, cross-agent search, usage accounting, export/import, global and project context, cleanup, and shell-level resume in one place. Its transfer path deliberately favors a visible handoff over writing translated history into another vendor's private store.

Different jobs want different tradeoffs. If you want a macOS session browser, use the good macOS session browser. If you want direct native translation between Claude and Codex, use a tool built for that. I wanted something I could pipe, audit, and teach to my shell.

## Put it on the anvil

AgentSmith is Python standard library only. You need `python3`, the agent CLIs you use, and `~/.local/bin` on `PATH`.

```sh
git clone https://github.com/Kronuz/AgentSmith.git ~/code/AgentSmith
~/code/AgentSmith/install.sh
```

The installer links the executable into `~/.local/bin`. Add the optional shell integration to `~/.profile`, `~/.zshrc`, or `~/.bashrc` for auto-resume wrappers, `ascd`, and tab completion:

```sh
[ -r "$HOME/code/AgentSmith/agentsmith.sh" ] &&
  . "$HOME/code/AgentSmith/agentsmith.sh"
```

Open a new shell, then start somewhere harmless:

```sh
asmith stats
asmith dirs
asmith tree
asmith ls --here
```

These commands only read the local stores. When you are ready, try `asmith dump <id>` and `asmith resume codex`.

AgentSmith also has sharp tools. `rm` shreds selected local session state, `purge` removes empty sessions, and `redact` scrubs a leaked value across mutable agent stores. They support previews and confirmations for a reason. Start with `--dry-run`.

```sh
asmith rm . --dry-run
asmith purge --dry-run
asmith redact 'example-leaked-value' --dry-run
```

The [repository](https://github.com/Kronuz/AgentSmith) has the complete command reference and a copy-paste tutorial. Try it against the directory you are already working in. If one of the three agents has changed its private store again, bring a sample, an issue, or a hammer.
