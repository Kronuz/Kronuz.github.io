---
title: "One More Benchmark"
subtitle: "A field guide to working with me, for humans and machines alike."
description: "Why I ask for the number instead of the adjective, why I follow a task past the sign that says stop, and why the real wins live in the tenth 'wait, actually'. A field guide for whoever builds with me next, human or machine."
excerpt: "You just made it work. Then the huddle comes: 'wait, actually...'. If you have ever built anything with me, you know that message. This is the field guide: why I don't believe 'faster', why I follow the thread past the trapdoor, and why the win is never in the first draft."
date: 2026-07-18
authors: kronuz
draft: true
tags:
  - meta
  - engineering
---

You just made it work. The tests are all green, the thing does the thing, you lean back. Then the huddle comes:

*Wait, actually...*

If you have ever built something with me, you know those words. It is the tenth one today. It lands right after "great, that works", and it always opens a door you thought was closed: sometimes a better name, sometimes a whole second approach, sometimes just "did we measure that, or did we only decide it?"

I am that person. Let me explain, mostly so you can forgive me, and a little so you can survive me.

## I don't believe "faster"

Tell me the new version is faster and I will not argue. I will ask for the number. Not because I doubt you, but because "faster" is a feeling and a nanosecond is a fact, and only one of them survives contact with a graph. A word-at-a-time hash I adopted this season was supposed to be an obvious win. It was. But I did not know *by how much*, or on which machine, or whether it moved anything end to end, until it sat in a table next to the thing it replaced. It came out 18 to 51% faster at the hash, and a rounding error in production. Both are true, and I needed both.

So the "wait, actually" is often just: *show me*. Adjectives are where bugs and wishful thinking hide. A benchmark on the real key set, on the real box, is where they go to die.

## I follow the thread past the sign that says stop

Give me a task with a clean edge and I will find the frayed bit and pull. A blog post becomes a library. The library turns out to be mostly sugar, so we retire it. Retiring it means touching a shared macro, which means widening a type, which means a full build, which means a green checkmark, which turns red on a compiler I do not even own, which means it is suddenly midnight and I am reading a compiler's constexpr evaluator like it owes me money.

I know how that looks from the outside. It looks like I cannot leave a thing alone. That is because I cannot leave a thing alone. The eleven-year-old who wanted to know what was behind the screen never fully left, and he is *delighted* every time a task turns out to be a trapdoor.

## The receipts

In case you think this is a personality I am performing:

- I built a small library this season, liked it, and **deleted it two days later** because the benchmark said it was doing nothing the engine underneath could not already do. Clean beats clever, and gone is cleaner than both.
- A test showed a value coming back "wrong". It would have been so easy to blame the change in front of me. It was a **red herring**, a different feature entirely, and proving that took longer than the fix would have. Worth it. Blaming the wrong thing is how you fix the wrong thing.
- The bug that ate the most hours was **not in my code**. It was a latent incompatibility three compilers happily ignored and a fourth refused. It had been broken and green at the same time for a while. Now it is just green.

None of those were in the ticket. All of them were the actual work.

## The bill

Here is the honest part. It is tiring to be on the other end of me. The "wait, actually" arrives right when you were done, and there is always one more. I ask for proof you did not think you needed and a benchmark you did not think to run. I will send you down a trapdoor at 11pm with a cheerful note attached. Measured against a reasonable person, I am *annoying*, and I have made my peace with the p99.

But the win is never in the first draft. It lives in the tenth "wait, actually", in the number that turned out to be a rounding error, in the red herring we refused to blame, in the bug three of us walked past. Push a thing a little further than it is supposed to go, and pay for less than you import. That is the whole religion. Everything else is one more benchmark.

## To whoever builds with me next

Human or machine, here is the field guide. Keep up: I move fast and change my mind faster, and none of it is churn. Bring me a number, not an adjective. When you hit a wall, say so plainly and hand me two doors. Tell me when I am wrong; I would much rather that than be flattered into shipping something soft.

And when I say "wait, actually" for the tenth time today, know that it is not me being difficult. It is me being delighted.

Roll for initiative. 🎲
