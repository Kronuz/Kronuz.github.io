---
title: "The Directory Remembers"
subtitle: "Portable sessions for coding agents"
description: "AgentSmith treats a working directory as the durable identity behind Claude Code, Codex, and Copilot CLI sessions, then makes those sessions inspectable, exportable, and movable without writing into an agent's private store."
excerpt: "I wanted one command that could enter a project and resume whatever its coding agent had been doing. That small convenience turned into AgentSmith, a translation and migration layer for three incompatible ideas of a session."
date: 2026-07-24
draft: true
authors: kronuz
tags:
  - ai
  - agents
  - cli
  - developer-tools
---

I wanted one command that could enter a project and resume whatever its coding agent had been doing. That small convenience turned into **AgentSmith**, a translation and migration layer for three incompatible ideas of a session. It can find the work attached to a directory, inspect it, account for its usage, export it with its context, and hand it to another agent without pretending their private storage formats are interchangeable.

The command that started it was almost embarrassingly small:

```sh
asmith resume codex ~/code/project
```

Change `codex` to `claude` or `copilot`, and AgentSmith finds the newest resumable session associated with that directory. The directory is the durable key. The agent is a choice you can change.

That last sentence took considerably more work than the command suggests.

## Three agents walk into a directory

[Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started), [Codex](https://developers.openai.com/codex/), and [GitHub Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli) all understand sessions. They do not agree on what a session is.

One stores conversations as JSONL with adjacent subagent and tool-result directories. Another combines a SQLite index with rollout files. The third has its own event stream, usage records, and continuation rules. Even their accounting differs: cache reads, cache writes, reasoning tokens, and child agents do not line up cleanly.

The files are an implementation detail until you want to answer a very ordinary question:

> What work happened in this repository, regardless of which agent did it?

AgentSmith reads each native store through a backend and normalizes only the parts that can honestly be compared: session identity, working directory, timestamps, messages, touched files, and usage. It keeps the source label visible. A row from Claude should never quietly masquerade as one from Codex.

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

This gives me a single `asmith ls`, a single full-text search, and a usage view that says where every number came from. It also gives `resume` a stable meaning: find the newest compatible native session for this directory, then invoke that agent's own continuation mechanism. AgentSmith does not manufacture a fake common session underneath.

## The box was not the session

The first migration feature was called `dump --raw`. It copied native transcript data. That sounded faithful because nothing had been transformed.

It was faithful to the file and unfaithful to the session.

A transcript may have child-agent sidecars. Project memory can live elsewhere. Instructions may sit in the repository, the agent's home, or both. Hooks, skills, configuration, and touched-file records can all affect what happened without appearing as conversational turns. A raw dump can also represent only one of several sessions attached to the same directory.

So the portable unit became an **export bundle**, a directory with a manifest and checksummed inventory:

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

Each session carries a readable conversation, metadata, usage, file records, and its untouched native artifacts. Project memory and project-scoped instructions remain attached to their project. Global configuration is a separate export because copying the same global hook into twenty project bundles would be both wasteful and misleading.

Exports include everything they can attribute by default. The smaller form is opt-out:

```sh
asmith export . -o ~/exports/project
asmith export --global -o ~/exports/globals
asmith verify ~/exports/project
```

That default matters. A person making a backup is unlikely to know which obscure sidecar will become important six months later.

## Moving without forgery

Exporting is the easy half. Importing one agent's private session records into another agent's database would require reverse-engineering undocumented internals and lying convincingly enough for the destination to accept the result.

I chose a less magical design.

`asmith import` prepares a new directory containing the verified source, a generated `HANDOFF.md`, and the material needed to continue. `asmith launch` starts the destination agent and asks it to ingest that handoff. The resulting conversation is a real native session created by the destination itself.

```sh
handoff=$(asmith import ~/exports/project --cwd ~/code/project)
asmith launch codex "$handoff"
```

The handoff requires the agent to inspect every preserved conversation, memory file, instruction, and native artifact. It builds a coverage ledger, names anything unreadable or omitted, and extracts concrete objectives, decisions, open work, and referenced files. It must not fabricate alternating historical turns. Provenance is better than counterfeit history.

`asmith merge` uses the same machinery, but starts by discovering every live session attached to one or more projects:

```sh
asmith merge ~/code/project -o ~/imports/merged-history
```

The original sessions remain untouched. The merged handoff becomes a new continuation, not a destructive rewrite of history.

## The 74,702-byte mistake

Global migration exposed a nastier problem.

I had several sets of instructions, commands, hooks, and skills from two agents. My first converter helpfully concatenated the shared instructions into a Codex `AGENTS.md`. It produced **74,702 bytes** and marked the file as ready for `~/.codex/AGENTS.md`.

Codex's default instruction-ingestion budget was **32,768 bytes**.

The adapter was more than twice the budget, mixed global preferences with environment-specific workflows, and included skills whose commands did not exist on the destination machine. Some source hooks deliberately restricted networking or remote access. Installing the whole thing would have been a successful copy and a bad migration.

That changed the import model. A global import now has two trees:

```text
prepared-import/
├── HANDOFF.md
├── candidate/     # edit or delete here
├── source/        # untouched provenance
└── manifest.json
```

`candidate/` is the user's decision. Deleting a candidate means *exclude this*. The importing agent may consult `source/` to understand provenance or repair a reference, but it may not resurrect a deleted candidate behind the user's back.

Before writing live configuration, the agent must present a compact destination blueprint. Each proposed output gets a path, purpose, approximate size, source inputs, dependencies, and a keep/adapt/omit decision. Restrictive policies, missing commands, unavailable services, and environment-only skills go into a separate exception table. Ambiguous omissions require a question.

Most importantly, the destination uses its native shapes. Concise global instructions stay concise. Project guidance remains in the project. Reusable workflows become skills. Hooks remain hooks, and configuration remains configuration. Concatenation is not architecture.

## A receipt before the first cut

An agent migrating its own global configuration is performing surgery on the instructions that govern its behavior. "I made a backup somewhere" felt too loose.

AgentSmith therefore makes the approved path set explicit:

```sh
receipt=$(asmith snapshot \
  ~/.codex/AGENTS.md \
  ~/.agents/skills/imported \
  -o ~/.local/state/agentsmith/receipts/global-migration)

# The destination agent performs the approved writes.

asmith audit "$receipt" --seal
asmith rollback "$receipt" --dry-run
```

The snapshot records the exact baseline before the first write. Sealing records what the migration produced. A later audit detects drift, and rollback restores modified or deleted paths while removing paths that the migration created.

It is deliberately narrower than snapshotting a home directory. The path list is also the approval boundary. If the plan grows another destination, the agent stops and asks before touching it.

## Trying it on the ugly backup

The design stopped being theoretical when I fed it a real backup assembled by several methods on another machine.

The source contained standalone dumps, raw Claude project stores, two generations of memory, project instructions, and two generations of global Copilot configuration. Some transcripts were byte-identical duplicates. One duplicate in the raw project store had the sidecar directory that the standalone copy lacked. The newer global tree had to win path conflicts without erasing unique older files.

The final reconstruction produced:

- **16 unique sessions** from 18 transcript files
- **12 Claude sidecar files**
- **83 project instruction files**
- **49 global configuration files**
- **34 independently verifiable bundles**
- **zero synthesized destination adapters**

Every bundle passed checksum verification. I also imported representative project and global bundles, then checked that the prepared handoffs retained the expected candidates, provenance, working directories, and review protocol.

The mistakes were useful. Hard-coded path guesses turned `/private/tmp` into a made-up project directory. Picking the most frequent Claude cwd placed one session inside a nested build dependency instead of its project root. Deduplicating in the wrong order kept a transcript and threw away its richer twin's sidecars.

Each looked reasonable in isolation. Together they made the earlier export valid, checksummed, and wrong.

## What portability means here

AgentSmith cannot pour one model's working memory into another model. It cannot recover context absent from the source, and it cannot make a finite context window infinite. A dump made without memory or child sessions stays incomplete.

What it can do is preserve the evidence, account for it, and start a native continuation with far less left on the floor. The directory remains the anchor. Agents can change. Machines can change. The work has somewhere durable to live between them.

That is enough magic for one shell command.
