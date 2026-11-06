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

Four days ago I wrote [One Fun Task](/blog/bignum-campaign/), about a day in which a campaign of AI coding agents rebuilt the insides of my old bignum. The campaign is a method I keep as a skill, a set of instructions every agent in it reads, and in about three weeks it had grown to **fifteen roles**, **fourteen agent types**, **25,142 words** of instructions, a status index and ledgers kept by hand, and a rule that two agents should always be busy while quota remained.

It worked. It also cost a lot, and the logs of my other campaigns said exactly where. So I had it rebuilt. Campaign 2.0 has four roles and two agent types, its instructions are less than half the length, and the rules that matter most are no longer sentences an agent has to remember. A small tool enforces them, and both the skill and the tool are on GitHub as [agent-campaign](https://github.com/Kronuz/agent-campaign). This is the story of making it lighter without losing what made it trustworthy.

## Where the tokens went

The best record I had was the exploration log of [strata](https://github.com/Kronuz/strata), a C++20 segment store that has been a long campaign of its own. Between October 20 and November 4 it logged **133 agent runs** with their token counts, about **30.6 million tokens** with cached context included. This table shows the roles that mattered, with how many runs each made and what a typical run cost.

| Role | Runs | Tokens | Median run |
|---|---|---|---|
| developer | 49 | 12.2M | 240k |
| code review | 16 | 3.3M | 210k |
| explorer | 27 | 2.9M | 93k |
| architect review | 7 | 2.1M | 236k |
| recheck | 9 | 1.1M | 134k |

The developers are the work, so that row is fine. The others told on the method.

Every recheck in the log, an agent sent to confirm that a reviewer's findings were fixed, came back "CLOSED". Nine runs and **1.1 million tokens** to confirm what rerunning the reviewer's own probes would have shown in a few seconds of machine time.

Designs spiraled. One durability design went through seven re-checks and grew to 3,554 lines; another design spent about 1.27 million tokens before a line of its code existed. Reviews made up **47%** of strata's documentation, 36,149 of its 77,646 lines, and plain approval was almost extinct: 2 of about 92 verdicts. Nearly every review bought a round of conditions.

And agents waited. A [Detent](https://github.com/Kronuz/Detent) re-check had tiny Python probes that sat for about **two and a half hours** behind other agents' exclusive benchmark holds. On the [cpp-libraries](https://github.com/Kronuz/cpp-libraries) gate, builds waited one to seven hours. A waiting agent either holds its turn open or polls, and every poll rereads its whole context. Meanwhile the quota helper aimed for 95% of every five-hour window and a floor of two busy agents, which made utilization the goal instead of outcomes. Earlier still, a tool that rented bare-metal machines for the long runs had left machines idle for hours, at a cost of hundreds of dollars.

The lead itself spent its days as a clerk: a status index, a log row per run, a document index, status lines on every document, a quartermaster agent for chores. Every one of those was derivable from git or scriptable.

## What paid

Not everything was waste, and the redesign had to keep the parts that were not.

The reviews of risky code paid. Fresh agents that had not written a branch built it, probed it and found a use-after-free and lost wake-ups in a thread pool, a nested-wait deadlock, and a durability protocol error. Those reviews are the reason I trust what the agents write, and 2.0 keeps them.

The hunts paid too. Across the records, explorers made **33 runs**, most of them on Claude Sonnet at medium effort, and **20** of them landed or merged, at a median of 93k tokens each. That was the best yield of any role, and so was the measurement discipline from [One More Benchmark](/blog/one-more-benchmark/): an A/A run first, then interleaved A/B runs on a quiet machine.

## Building it

I handed the redesign to one long agent session in [GitHub Copilot CLI](https://github.com/features/copilot/cli), running Claude Opus 5.5, with a brief: audit 1.x, research what else exists, design 2.0 on its own branch, build it, test it, and keep 1.x intact as the way back. It read the whole skill and its 68 commits, mined the records of strata, Detent, [Xapiand](https://github.com/Kronuz/Xapiand) and cpp-libraries, and studied [Superpowers](https://github.com/obra/superpowers), [Beads](https://github.com/gastownhall/beads), [Gas Town](https://github.com/gastownhall/gastown) and [Overstory](https://github.com/jayminwest/overstory). Before building anything, it sent the design to a reviewer from another model family, GPT-6.1 at high effort, which came back with thirteen findings. Most of them changed the design.

The ideas it adopted are plain ones. Completion is recorded by the script that ran the check, never by an agent's report. Shared state has one writer. What git shows beats what a file claims. Each writer owns a disjoint set of files.

## A smaller party

The campaign was always named for the tabletop game, so 2.0 leans into it, lightly. I am the **patron**: I set the goals and make the calls that are mine. The **game master** is the lead session: it plans, splits the goals into **quests**, and lands them. **Adventurers** each take one quest in their own git worktree and keep a **journal** of where they are. **Paladins** review: fresh agents that never wrote the code, sent according to the quest's risk. **Scouts** are the cheap hunters, sent out as a scouting party, one target each. The technical words stay plain: commits, checks, jobs, holds.

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

Fifteen roles became four, and fourteen agent types became two, the adventurer and the paladin. What used to be a separate role is now how the agent works. An adventurer can be a Sage (architecture and design), a Wizard (rarely, when the mechanism itself is the limit), an Artificer (performance), a Scout, a Bard (documentation in my voice) or a Squire (mechanical changes), and the class picks its method and its model. A paladin carries a lens: correctness, security, durability, design or the whole system. A low-risk quest lands on green checks with no paladin at all; a critical one gets a paladin from another model family.

I worried the theme would make the instructions vaguer. A test agent that ran a whole campaign on the themed skill found the role names clear and one real collision: "class" also named a column in the review table. The column is called Kind now.

## One quest, start to finish

I write the goals in the campaign's plan. The game master turns each one into a quest: `campaign new` records its risk, the files it may touch, the checks that must pass, and what it depends on, and the game master writes its outcome and numbered criteria in the quest file. `campaign start` cuts a branch for it in its own worktree, with a fresh journal. Then the game master launches an adventurer with a short prompt that points at the quest and the worktree and names the class and the model.

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

The adventurer works in its worktree, commits, and submits its builds and tests as jobs. It waits for them once, for at most ten minutes; if they are still running, it writes their ids in its journal and ends its turn. When the jobs finish, the game master's background wait returns, and it resumes the adventurer: by message while its context is small, or as a fresh adventurer that starts from the journal. This loop repeats until every criterion has evidence and the journal says the quest is ready for review.

A low-risk quest skips the next part: the game master reads the diff and lands it. Anything riskier goes to the paladins its risk calls for, one per lens.

```d2 alt="The game master asks a paladin for a review, the paladin runs its probes as jobs on campaign and returns a verdict, the game master accepts it and asks campaign to land, and campaign reports the quest landed."
shape: sequence_diagram
gm: "Game master"
pal: "Paladin"
tool: "campaign"
gm -> pal: "review"
pal -> tool: "probes as jobs"
pal -> gm: "verdict"
gm -> tool: "accept, land"
tool -> gm: "landed"
```

The paladin reads the quest file and the branch for itself. It reuses the adventurer's test results where the code is the same, writes its own probes, runs them as jobs, and files a verdict: APPROVE, CHANGES or REJECT. After CHANGES, the adventurer fixes what blocks, and the game master reruns the paladin's probes against the fix as jobs; a second review happens only when the fix adds a mechanism of its own. `campaign accept` pins the verdict to the exact content it reviewed, `campaign land` checks everything once more against the exact code and moves `main`, and the quest's deferred checks join the queue behind it. Then the game master tells me it landed, or brings me the one decision that was mine to make.

## Rules became a tool

The old skill said "never edit your own done criteria", "rebase before landing" and "one writer per file set". An agent can forget a sentence. So 2.0 has a tool, `campaign`, about 3,000 lines of Python with no dependencies, and those sentences became its behavior.

The quest file holds the criteria, and landing refuses a branch that edits it. The campaign's state lives in one JSON file that only the tool writes, from one checkout, under a lock. And `campaign land` refuses to move `main` unless every check passed on the exact code being landed and every review the risk calls for was accepted for that exact content.

"Exact code" took a few tries to get right. A check result is keyed by a hash of the machine, the toolchain, the command and the commit's code with the campaign's own notes left out. When an adventurer commits its journal, the code has not changed, so the evidence stands. When a paladin wants the adventurer's test results, it gets them without rebuilding. When anything in the code changes, the old result no longer matches and the check runs again.

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

That diagram also shows the rule I care most about now: **the direct path first**. A quest's checks are either gates or deferred. Gates block landing: the build, the tests, and the evidence its risk needs, like ThreadSanitizer for concurrency or fuzzing for a decoder. Deferred checks are the completeness work: other platforms, long soaks, full test matrices, extended fuzzing. They run after landing, at low priority, on the landed code, and they block the milestone instead of the next quest. A red one is an error the game master has to fix forward or revert. Deferred work gets at most half of the slots for builds and tests, so it never becomes a new queue in front of the work that decides what happens next.

## Nobody waits

Builds, tests and benchmarks are **jobs** now, and a single worker per machine runs the queue for every campaign, in priority order; each attempt gets a runner that leads its own process session, writes a heartbeat every 15 seconds, and kills anything the command left behind. If a runner dies, the worker notices the stale heartbeat and retries or marks the job interrupted. The game master waits on all of it with one background command, which costs no tokens until it returns.

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

Underneath sits `quiet`, the small tool that shares one machine between every agent on it. Light holds are builds and tests, a few at a time, at the lowest priority. A strict hold is a measurement on its own cores, and an exclusive hold runs alone. 2.0 caps a measurement at 30 minutes and stops it at its deadline, because a benchmark that overran its isolation is not a result. A build that has waited ten minutes now goes ahead of new measurements, so a stream of benchmarks can no longer starve the builds behind them.

## Proving it

The tool comes with a full test suite, run on Python 3.9 and 3.15 at the same time on a machine other agents were using. Then the mechanisms were broken on purpose, one at a time, to see whether a test noticed: the reaper, attempt fencing, evidence keyed by code, landing recovery, starvation fairness, the deferred checks, and more. Of 33 planted bugs, four got past the tests at first. Two exposed weak tests, and one of those was hiding a real bug, below. One was a guard no real prompt could reach, so the guard went. The last was a path no test exercised, so it got a test.

Testing under real load found bugs a quiet machine would not have. Under CPU load, `quiet` reported **13 of 16** trivial jobs as past their deadline: a timer, terminated just after it started, could still mark the hold expired. It is decided by the clock now. A runner skipped its heartbeat while cleaning up, and the reaper killed a live job. A starving build announced itself only after winning a lock that the busy measurement held most of the time, so fairness depended on timing; the real code passed the test one time in three. The last turned up the day I published this: a job meant to run after one job could be handed an identical one queued after another, and inherit its skip when that one failed.

Then fresh agents, given nothing but a prompt and the skill, ran it on throwaway repositories. One got a half-finished quest, an uncommitted test and a job whose runner had been killed, and was asked to resume. It worked out where things stood in **8 tool calls**, kept the half-written test, did not rerun the killed job (the reaper had already retried it), and left the decision that was mine for me. Another ran a campaign from scratch: three quests landed in a little under 12 minutes, with one review. A third ran the themed skill on a toy library with a quadratic `unique()`: 49.34 seconds became 5.72 milliseconds at 200,000 items, measured on an exclusive hold against a control run of the same code that agreed within 0.1%, after a paladin compared 5,029 cases with the old code.

## The first real campaign

The real trial was a live campaign on Detent, running in [Codex](https://github.com/openai/codex) on another machine. The lead there parked its agents, installed 2.0 on its own branch, ran the test suite, which passed, and moved a feature that was split across three branches into one quest with three tasks. It found a real bug and a real gap. A job submitted from a task's worktree with `--commit HEAD` resolved `HEAD` in the main checkout instead, and no command could correct a task's file set after migration. It also checked the Codex details the skill had marked unverified, and wrote what it found into the harness notes.

Then, about ten minutes after it resumed the campaign, it used up its five-hour window.

Nothing in the skill could see that coming. The quota helper read Claude Code and Copilot but not Codex, and the campaign had no record of what each agent cost. 1.x had that record, the exploration log I built the whole audit from, and 2.0 had dropped it with the other clerical work. So it came back, without a clerk: `campaign usage` reads the logs the harness already writes and attributes every agent run to a quest, a role, a class, a model and an effort, from the first line of the prompt that launched it. On the themed test, it showed the Artificer at 2.0 million tokens, the paladin at 2.1 million, and two fresh resumes at 1.9 million together, which cost more than the build itself in Copilot's own units.

Once it read Codex's logs too, the ten minutes before that window ran out came to 10.3 million tokens: **51.5%** in the lead, nearly all of it rereading its own context, and the rest in three agents on Astra, Codex's strongest model, at high effort. Nothing showed Astra doing the ordinary work better, and the logs can't say what a token costs against the quota, so the lead and most classes now start on Sol at medium effort, and Astra is kept for a mechanism nobody has cracked.

Codex had one more surprise. A finished agent's result waits in a mailbox and wakes nobody, so one night the campaign simply stopped, with the results sitting there. The lead now blocks on Codex's own agent wait whenever agents are out.

## Several campaigns, one machine

I usually run more than one campaign on a machine, and they share libraries. The machine side already held: one job queue, one `quiet`, one quota for everyone. The repository side did not. Landing took only the campaign's own lock, so two campaigns could land into the same library at once, and one fallback could even reset `main` to a commit read before the other campaign landed, quietly undoing its work. No campaign had hit it yet; 2.0 was a day old. Landing into a shared repository now takes that repository's lock too. Campaigns register themselves on the machine, `campaign check` warns when another campaign's quest touches the same files or a contract yours consumes, and a quest can wait for another campaign's quest to land.

## Keeping it small

The old skill grew one sensible sentence at a time, and that is how it got to 25,000 words. So 2.0 has a rule for its own changes: a change replaces text, or it brings evidence, from `campaign usage`, a live test, or an incident. A test holds the instructions to a word budget. The budget went up once already, by a hundred words, on the day it was set, and the commit says why: the shared-repository race.

## What is left

The usage report reads Copilot's and Codex's logs; Claude Code's are not read yet. The quota helper cannot see extra credits bought for Claude Code, only its five-hour and weekly windows, so it informs a decision and never makes one. And I have not run the same work under both versions. A fair head-to-head would cost millions of tokens for a sample too small to mean much, so the only token savings I have are estimates from the 1.x medians, and I am not quoting them as results. 1.x stays a branch switch away.

## The part I did

Again, I wrote none of the code. I handed over the brief, and then I asked questions, and nearly every question changed the design: whether the scouting parties survived, whether the sidebar still showed what was running, whether the theme fit without dumbing anything down, whether we had lost the experts, whether long benchmarks still held up the work, what Codex needed, what an agent costs, and whether two campaigns could share a machine. The answers are all in the skill now. What I keep coming back to is how much of the old method was trust written as prose, and how much better it holds as a check that runs on the code.

Thanks to the authors of Superpowers, Beads, Gas Town and Overstory, whose ideas are in here, and to the GPT-6.1 reviewer, whose thirteen findings arrived before any of this was built, which is the cheapest time to hear them.
