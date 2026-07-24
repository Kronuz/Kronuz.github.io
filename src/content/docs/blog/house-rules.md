---
title: "House Rules"
subtitle: "Self-hosted comments, built to be mine."
description: "The boss fight in 'Goodbye, Dr. Jekyll' was comments, and giscus won the truce. Then I went back down and built my own: a self-hosted comment system that lives on the edge, signs you in with GitHub, renders Markdown in the same colors as the rest of the site, and belongs entirely to me. What it is, how it works, and why building the one thing a static site 'can't have' was the most fun I've had all year."
excerpt: "Goodbye, Dr. Jekyll ended with giscus winning the comments boss fight. It turns out the boss got back up. This is the comment system I built to replace it: self-hosted, on the edge, mine down to the boards, and a blast to build."
date: 2026-07-17
authors: kronuz
series: "This Blog"
seriesOrder: 2
tags:
  - meta
  - cloudflare
  - blogging
---

In [Goodbye, Dr. Jekyll](/blog/goodbye-jekyll/) I called comments the boss fight of a static site, and handed the win to [giscus](https://giscus.app). That was a truce, not a kill. giscus works, but it keeps every word your readers write in a database that belongs to GitHub, not to me. So I went back down into the dungeon and built my own: a comment system that lives on the edge, signs you in with GitHub, renders your Markdown in the same colors as the rest of the site, and belongs entirely to me. The whole thing is about 360 KB, it renders a comment in roughly five milliseconds, and it was the most fun I have had building anything all year.

## The boss that got back up

Every dungeon has the boss you are sure you killed, the one that stands back up while you are sheathing your sword. Mine was comments. A static site has no backend, and a comment is the most backend-shaped thing there is, so for a while you make peace with a hosted service that keeps the conversation for you. giscus is a good one. It tucks each thread into GitHub Discussions and renders it inline, themed to match. On this blog it Just Works™️.

But the truce chafed, in two places. The first was the frame. giscus renders inside an [iframe](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/iframe), a boxed little window cut into the page, and matching its colors never quite hides the seams: a scrollbar that is not mine, a box that resizes with a lurch, a frame that always reads as bolted on rather than built in. For someone who rebuilt an entire syntax theme down to one specific olive green before writing a single post, that was never going to sit right.

The second was ownership. "Kept for you" is a polite way of saying "not yours." Every reply, every reaction, every correction a reader takes the time to write sits in someone else's database, under someone else's rules, one policy change away from a shape I did not choose. I did not want a room leased across the street. I wanted a front porch, bolted to my own house.

I had made this trade once already with [my shell](/blog/molting-zsh/): keep the part I cared about, replace the machinery around it, and accept that every quiet convenience became mine to understand. Comments were the same bargain, only this time I wanted to own the place where other people left their words.

## What it is

A comment box at the bottom of every post. You sign in with GitHub, and it learns exactly one thing: who you are, a name and an avatar, no repo access, nothing else. Then you can write in Markdown, reply, react with the usual emoji, and drop a GIF when words fail you. It looks like it grew there, because it did: real page, not a frame cut into one. It follows the light and dark toggle, and highlights code in a comment the same way the posts do. Behind the friendly box, every comment, reply, reaction, and quiet moderator action lives in my own database, on my own terms. House rules.

## How it works

The moving parts are small.

```d2
direction: down
reader: Your browser {
  widget: Comment widget
}
gh: GitHub (sign-in)
worker: Comment API\n(Cloudflare Worker) {
  style.bold: true
}
db: D1\n(SQLite at the edge)

reader.widget -> gh: sign in
reader.widget -> worker: comment / react / preview
worker -> db: read / write
```

A little script rides along on each post and mounts a comment box keyed to that page. It talks to a tiny API running as a [Cloudflare Worker](https://developers.cloudflare.com/workers/), close to whoever is reading. The Worker keeps everything in [D1](https://developers.cloudflare.com/d1/), a SQLite database that also lives at the edge, so the data sits next to the code instead of an ocean away.

Two details I am fond of. First, Markdown is rendered on the server with [Shiki](https://shiki.style), using the very same Kronuz theme the article code blocks use, so a fenced snippet in a comment comes out in the exact olive green I am constitutionally incapable of living without. Second, there is no session table: your sign-in rides in a small signed cookie, which means there is nothing on my side to leak and nothing to sweep. It is multi-tenant too, so one deployment could keep house for more than one blog, each thread walled off to its own.

## The fun parts

Here is where it stops being work and turns into a toy I cannot put down.

**It is tiny, and it flies.** The entire Worker is about 360 KB, and rendering a comment (Markdown, highlighting, all of it) takes roughly five milliseconds. The slow part was never the render, it was the trip across the network, so the preview quietly starts rendering the moment your cursor drifts toward the Preview tab. By the time you click it, it is already there.

**It runs on nothing.** Cloudflare's free tier, scaled to zero. When nobody is commenting there is no server sitting idle, no bill, no cron job, nothing to patch at 2am.

**It has a GIF picker,** because a comment section that cannot answer with a perfectly timed reaction GIF is a sad comment section.

**And it is mine.** If I ever change hosts, the whole conversation comes with me in a single file. No export dance, no "download your data," no waiting on a form.

None of those is the real reason, though. The real reason is that a static site is not supposed to be able to do this at all, and comments are the exact thing everyone tells you to farm out. Building the one part you are told you cannot have, and watching it come out small and fast and yours, is the whole of the fun.

## Say something

The house has a front porch now, and it is mine down to the boards. Which means, for the first time since 2015, this blog can talk back.

There is a comment box at the bottom of this very page. Pull up a chair and use it. Tell me where I am wrong, or just say hello.

Roll for initiative. 🎲
