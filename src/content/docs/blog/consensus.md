---
title: "Acknowledged Means Durable"
subtitle: "A log and a Raft core that never say yes too early."
description: "journal is a header-only C++20 write-ahead log whose append returns only after the data is truly on disk, and which refuses to start rather than forget anything it confirmed. consensus is a header-only deterministic Raft core on top of it: events in, actions out, and no vote or acknowledgement leaves a machine before journal says it is saved. A real flush costs about 62 milliseconds on an Intel Mac, so journal groups work: 16 saved operations a second become 4,074 when 256 share one flush."
excerpt: "When a database tells you your write is safe, it is repeating a promise a disk made to it. The thirty-sixth familiar is two libraries with one rule between them: nothing says yes until the bytes are really down, from the disk all the way up to a vote among servers."
date: 2026-11-14
authors: kronuz
series: "Familiars"
seriesOrder: 36
chapter: "Bytes"
tags:
  - familiars
  - cpp
  - durability
  - raft
---

*Part of [**Familiars**](https://kronuz.com/cpp-libraries/), my collection of standalone C++ building blocks. These two are a pair, and they replace the logging and replication Xapiand used to do on its own: [journal](https://github.com/Kronuz/journal) keeps the bytes, and [consensus](https://github.com/Kronuz/consensus) decides which bytes count.*

When an app says "saved," it is repeating what the operating system told it, which is repeating what the disk told it. You are betting your data that the drive meant it.

Usually it does not, quite. A drive is like a busy clerk with a notepad: it jots your data on the notepad (its cache) right away, says "got it," and files it properly later. If the power goes out before the filing, the notepad is wiped. Programs ask for the real filing with a call named `fsync`, and even that has a catch: on macOS, plain `fsync` stops at the notepad, and only a stronger call, `F_FULLFSYNC`, reaches the filing cabinet (the lie I wrote about in [The Syscalls That Lie](/blog/io/)).

These two libraries are built on one rule: **acknowledged means durable**. Nobody says yes until the bytes are really down, and when a layer cannot be sure, it stops.

## journal: saying yes honestly

journal is a log: you append a batch of records, and it gives back a receipt, a *frontier*, naming the last batch that is safe. It hands over that receipt only after a fixed chain of flushes: the data, then a small index file that points at it, then the folder that holds that index, because renaming a file is itself a change that a crash can undo. On macOS it uses the strong flush.

If a flush fails, journal does not retry and hope. After a failed flush you no longer know what reached the disk, so the journal *fences* itself: it refuses all work until it is reopened and has re-read what is actually there.

An earlier familiar, [storage](/blog/storage/), is crash safe too, but it recovers the opposite way. After a crash, storage finds the last good record and drops the half-written one after it. That record was never promised to anyone, but journal's records were. So if anything it already confirmed is damaged or missing, even the very last batch, journal refuses to open. Shrinking its history would break a promise, and the next section shows what that costs.

Here is `journal_bench` on an Intel Core i9-9980HK running macOS 15.8.1 with the strong flush, 64 rounds per row. The flush takes the same time whether it carries one record or 256:

| Records per flush | Records per second | Median time per flush (ms) |
| ---: | ---: | ---: |
| 1 | 16 | 62.2 |
| 32 | 509 | 62.9 |
| 256 | 4,074 | 62.9 |

The one-record run took four seconds and used about 70 milliseconds of processor time. The machine is waiting on the drive, not working, so the way to go fast is to share each flush among as much work as you can.

## consensus: a vote you can trust

Now put several servers together. [Raft](https://raft.github.io/) is a way for three or five servers to agree on one shared list of changes, even when some of them crash. They elect a *leader*. The leader sends each new change to the others, the *followers*, and each follower writes it down and replies "I have it." Once a majority has replied, the change is *committed*, and the client hears that its write is safe. Elections work the same way: each server votes at most once per round, and a majority of votes makes a leader.

Picture a follower that votes for server A, crashes before the vote reaches the disk, and wakes up with no memory of voting. Server B asks for its vote in the same round, and it says yes again. Now A and B both believe they won, and two leaders can each commit different changes. This is why journal refuses to forget, and why consensus never lets a reply out early.

consensus is a Raft core that does no input or output of its own. You hand it an *event* (a message arrived, time passed, a client proposed a change), and it hands back *actions* (save this batch, send this message, apply these changes). Saving is just another action, and the rule lives in the shape of the loop:

```text
event -> core -> "save this batch" -> journal flushes it -> "saved"
                                                            -> replies go out
```

Votes, acknowledgements and commit decisions wait inside the core until the matching "saved" comes back from journal. If saving fails, the core fences itself, like journal does. Since time, randomness and disk all come from outside, the same events always produce the same actions, so any run replays exactly.

## A test that passed for the wrong reason

That determinism makes cruel testing possible. consensus runs simulated groups of three or five servers whose messages are delayed, reordered, duplicated and lost, whose clocks run from half to twice real speed, and which crash keeping or losing their unsaved batch. After every step it checks that no round ever had two leaders and that every vote was saved before it was sent. Then fourteen known bugs, "send before saving" first among them, are planted one at a time, and the simulation must catch each. Its first long run, 2,000 random schedules of 10,000 steps, found no safety violation, and it did find a liveness hole: a server with stale data and a fast clock could keep a group leaderless as long as the skew lasted. Adding a *pre-vote*, a practice round before a real election, closed it.

Planted bugs earn their keep because a green test proves less than it looks. journal has a test that flips one byte in each saved file and requires the damage to be caught. Then I deleted one of the checksum checks it covered, and it still passed. The first batch in the file happened to be empty, so the flipped byte landed in the next batch's header, and a different check caught it. The check under test had never run. Now each check gets its own flipped byte, and removing any of them fails the test.

None of this proves your particular drive: the tests prove the protocol, assuming a disk that does what a successful flush says.

## Where it fits

Reach for journal when a log must survive power loss and you need to know the exact moment each record is safe. Reach for consensus to keep three or five servers agreeing on one history when you need to know exactly what is saved.

Skip journal for data you want to search (it only replays records in order) and for network filesystems that ignore flushes. Skip consensus if you want a finished replicated database: it is the agreement and its storage, and your application brings the rest. It also trusts its members, so it is no defense against a server that lies on purpose.
