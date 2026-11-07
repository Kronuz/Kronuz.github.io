---
title: "A Smaller Party"
subtitle: "Rebuilding my agent campaigns from their own logs"
description: "The agent campaigns behind One Fun Task ran on a method I had grown for three weeks: fifteen roles, fourteen agent types, 25,000 words of instructions, ledgers kept by hand, and agents waiting hours for the machine. Their own logs showed where the tokens went. Campaign 2.0 keeps the reviews and the hunts that paid, and turns the rest into a small tool: four roles, two agent types, less than half the words, and checks that run on the exact code that lands."
excerpt: "The campaign behind One Fun Task worked, and it was heavy: fifteen roles, 25,000 words of instructions, and agents that waited hours for a turn on the machine. Its logs said where the tokens went, so I had it rebuilt around what paid: a smaller party, a tool that enforces what the rules used to ask for, and nobody waiting on a benchmark."
date: 2026-11-05
authors: kronuz
tags:
  - ai
  - agents
---

Four days ago I wrote [One Fun Task](/blog/bignum-campaign/), about a day in which a campaign of AI coding agents rebuilt the insides of my old bignum. The campaign is a method I keep as a skill, a set of instructions every agent in it reads, and in about three weeks it had grown to **fifteen roles**, **fourteen agent types** and **25,142 words** of instructions, with ledgers kept by hand and a rule that two agents should always be busy while quota remained.

It worked, and it cost a lot. So I had it rebuilt from its own logs. Campaign 2.0 has four roles, two agent types and less than half the words, and a small tool enforces the rules that matter most. Both the skill and the tool are on GitHub as [agent-campaign](https://github.com/Kronuz/agent-campaign).

## Where the tokens went

The best record I had was the log of [strata](https://github.com/Kronuz/strata), a C++20 segment store that has been a long campaign of its own: **133 agent runs** between October 20 and November 4, about **30.6 million tokens**. This table shows the roles that mattered, with their runs and what a typical run cost.

| Role | Runs | Tokens | Median run |
|---|---|---|---|
| developer | 49 | 12.2M | 240k |
| code review | 16 | 3.3M | 210k |
| explorer | 27 | 2.9M | 93k |
| architect review | 7 | 2.1M | 236k |
| recheck | 9 | 1.1M | 134k |

The developers are the work. The others told on the method. All nine rechecks, agents sent to confirm that a reviewer's findings were fixed, came back "CLOSED": **1.1 million tokens** for what rerunning the reviewer's own probes would have shown in seconds. One durability design went through seven re-checks and grew to 3,554 lines, and plain approval was almost extinct: 2 of about 92 verdicts.

And agents waited. Tiny [Detent](https://github.com/Kronuz/Detent) probes sat for about **two and a half hours** behind other agents' benchmark holds, and builds on the [cpp-libraries](https://github.com/Kronuz/cpp-libraries) gate waited one to seven hours. A waiting agent either holds its turn open or polls, and every poll rereads its whole context. The lead, meanwhile, spent its days as a clerk, keeping indexes and ledgers that git could have told it.

Two things paid. The reviews of risky code found a use-after-free, lost wake-ups, a nested-wait deadlock and a durability protocol error. And the hunts: explorers, mostly Claude Sonnet at medium effort, landed **20 of 33** runs at a median of 93k tokens, the best yield of any role.

## A smaller party

I handed the redesign to one long session in [GitHub Copilot CLI](https://github.com/features/copilot/cli) running Claude Opus 5.5: audit 1.x, study what else exists ([Superpowers](https://github.com/obra/superpowers), [Beads](https://github.com/gastownhall/beads), [Gas Town](https://github.com/gastownhall/gastown), [Overstory](https://github.com/jayminwest/overstory)), then design, build and test 2.0. A reviewer from another model family, GPT-6.1, read the design before anything was built and came back with thirteen findings, most of which changed it.

The campaign was always named for the tabletop game, so 2.0 leans into it, lightly. I am the **patron**: I set the goals and make the calls that are mine. The **game master** is the lead session: it splits the goals into **quests** and lands them. **Adventurers** each take one quest in their own git worktree and keep a **journal** of where they are. **Paladins** are fresh reviewers, sent according to the quest's risk. **Scouts** are the cheap hunters.

```d2 alt="I give goals and calls to the game master, who sends adventurers on quests and scouts after targets; an adventurer's branch goes to a paladin for review."
direction: down
me: "Me: goals and the calls"
gm: "Game master: plan, quests, landing" { style.bold: true }
adv: "Adventurers: one quest each"
scouts: "Scouts: cheap hunts"
pal: "Paladins: fresh review, by risk"
me -> gm
gm -> adv
gm -> scouts
adv -> pal: branch
```

What used to be a separate role is now an adventurer's class (a Sage designs, an Artificer measures, a Bard writes docs in my voice, a Squire makes mechanical changes), and the class picks the method and the model. A low-risk quest lands on green checks with no paladin at all; a critical one gets a paladin from another model family.

## One quest

`campaign new` records a quest's risk, the files it may touch, its checks and its dependencies, and the game master writes its outcome and numbered criteria in the quest file. `campaign start` cuts its branch in a fresh worktree. The adventurer commits and submits its builds and tests as jobs; when only jobs remain, it writes their ids in its journal and ends its turn, and the game master's background wait resumes it when they finish.

```d2 alt="The game master runs new and start, hands the adventurer the quest, the adventurer commits and submits jobs to campaign, campaign tells the game master the jobs are done, and the game master resumes the adventurer."
shape: sequence_diagram
gm: "Game master"
adv: "Adventurer"
tool: "campaign"
gm -> tool: "new, start"
gm -> adv: "the quest"
adv -> tool: "commits, jobs"
tool -> gm: "jobs done"
gm -> adv: "resume"
```

A paladin reads the quest and the branch for itself, reuses the adventurer's results where the code is the same, runs its own probes as jobs, and files APPROVE, CHANGES or REJECT. After CHANGES, the game master reruns those probes against the fix; a second review happens only when the fix adds a mechanism of its own.

## Rules became a tool

The old skill said "never edit your own done criteria" and "one writer per file set", and an agent can forget a sentence. So `campaign`, about 4,000 lines of Python with no dependencies, turned those sentences into behavior. Landing refuses a branch that edits its quest file, the campaign's state has one writer, and `campaign land` moves `main` only when every check passed and every review the risk calls for was accepted, on the exact code being landed. A result is keyed by the machine, the toolchain, the command and the code, so a journal commit keeps the evidence and a code change reruns the check.

A live campaign found one more hole. Detent's biggest quest read **0%** in `campaign status`, because its journals argued their criteria in prose, and I asked whether it could land anyway. It could: landing never looked at the criteria. Now it reads the evidence tables of the journals in the commit it lands. Every criterion needs a row, every job a row cites must have passed on that code, and every task must be merged or dropped with a reason.

```d2 alt="On the quest branch, a worktree and journal lead to gate checks as jobs and then a paladin by risk; landing moves the tested code to main, where deferred checks run before the milestone is all green."
grid-columns: 2
grid-gap: 50
branch: "On the quest branch" {
  direction: down
  label.near: outside-top-left
  start: "Worktree, journal"
  gates: "Gate checks as jobs"
  review: "Paladin, by risk"
  start -> gates -> review
}
main: "On main" {
  direction: down
  label.near: outside-top-left
  land: "Land the tested code" { style.bold: true }
  later: "Deferred checks"
  milestone: "Milestone: all green"
  land -> later -> milestone
}
branch.review -> main.land
```

The rule I care most about now is **the direct path first**. Gate checks block landing: the build, the tests, and the evidence the risk needs, like ThreadSanitizer for concurrency. Deferred checks (other platforms, long soaks, extended fuzzing) run after landing at low priority, and they block the milestone, never the next quest.

## Nobody waits

Builds, tests and benchmarks are **jobs**, run by one worker per machine for every campaign, in priority order, each under a runner with a heartbeat. The game master waits on all of them with one background command, which costs no tokens until it returns.

```d2 alt="Agents submit jobs and end their turn; one queue for every campaign feeds the worker and runners, which run under quiet and report back to the game master's single background wait."
direction: down
agents: "Agents submit, end their turn"
queue: "One queue, every campaign"
runner: "Worker and runners"
quiet: "quiet: light, strict, exclusive" { style.bold: true }
gm: "Game master: one background wait"
agents -> queue -> runner -> quiet
runner -> gm: done
```

Underneath sits `quiet`, which shares one machine between every agent on it: builds and tests a few at a time at the lowest priority, measurements on their own cores or alone. A measurement is capped at 30 minutes, a build that has waited ten minutes goes ahead of new measurements, and a request still waiting shows why in the sidebar.

## Proving it

The test suite runs on Python 3.9 and 3.15 at once, on a machine other agents are using, and that load found bugs a quiet machine would not have. `quiet` reported **13 of 16** trivial jobs as past their deadline, a runner skipped its heartbeat while cleaning up and the reaper killed a live job, and starvation fairness held one time in three. Of 33 bugs planted on purpose, four got past the tests at first; each fails a test now, or its code is gone.

Fresh agents with only a prompt and the skill ran it too. One resumed a half-finished quest in **8 tool calls** without rerunning a job the reaper had already retried. Another took a toy library's quadratic `unique()` from 49.34 seconds to 5.72 milliseconds at 200,000 items, measured alone against a control run that agreed within 0.1%.

## The first real campaign

The real trial was a live Detent campaign in [Codex](https://github.com/openai/codex), on another machine. It moved a feature split across three branches into one quest, found a real bug (a task's `HEAD` resolved in the main checkout), and then, ten minutes after resuming, used up its five-hour window.

Nothing in the skill could see that coming, because 2.0 had dropped the record of what each agent cost along with the other clerical work. It came back without a clerk: `campaign usage` reads the logs the harness already writes and attributes every run to a quest, a role, a class, a model and an effort. Those ten minutes came to 10.3 million tokens, **51.5%** of it the lead rereading its own context and the rest three agents on Astra, Codex's strongest model, at high effort. The lead and most classes now start on Sol at medium effort.

## Several campaigns

I usually run more than one campaign on a machine, and they share libraries. Two of them could land into the same library at once, and one fallback could even reset `main` over the other's work, so landing into a shared repository now takes that repository's lock too. Campaigns register on the machine, and `campaign check` warns when another campaign's quest touches the same files or a contract yours consumes.

They talk to each other, too. An agent on an unrelated run found something for another campaign's quest and could only pass it on through me. Now `campaign message demo:fix "..."` leaves it for that quest, or for a campaign's game master, from anywhere on the machine. It wakes the game master and blocks the landing until a journal answers it by id or the game master closes it. A quest that starts on another campaign's files tells that game master on its own, and between machines each campaign pushes its messages to a git ref only it writes.

## What is left

The usage report doesn't read Claude Code's logs yet, a message sends no receipt back to its sender, and I have not run the same work under both versions: a fair head-to-head would cost millions of tokens for a sample too small to mean much. 1.x stays a branch switch away. And a test holds the instructions to a word budget, so the next sensible sentence has to replace one.

## The part I did

Again, I wrote none of the code. I asked questions, and nearly every one changed the design: whether the scouts survived, whether long benchmarks still held up the work, what an agent costs, whether a quest could land unproven, how one campaign could tell another what it found. What I keep coming back to is how much of the old method was trust written as prose, and how much better it holds as a check that runs on the code.

Thanks to the authors of Superpowers, Beads, Gas Town and Overstory, whose ideas are in here, and to the GPT-6.1 reviewer, whose thirteen findings arrived before any of this was built, the cheapest time to hear them.
