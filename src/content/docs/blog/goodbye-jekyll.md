---
title: "Goodbye, Dr. Jekyll"
subtitle: "Three lives of a blog, the monsters between them, and one comfortable old villain."
description: "The full origin story of this blog: a Pelican site in 2015, a Jekyll site in 2018, eight years of silence, and a 2026 rebuild in Astro. The friction that killed the first two, the monsters in the third, and the respectable old static-site generator who kept whispering that I should just come back."
excerpt: "This blog has died twice. Pelican in 2015, Jekyll in 2018, then eight years of cobwebs. This is the story of its third life: the friction that killed the first two, the monsters in the rebuild, and the comfortable old villain who kept whispering I should come back to him."
date: 2026-06-07
authors: kronuz
tags:
  - meta
  - astro
  - blogging
---

This blog has died twice. Pelican in 2015, Jekyll in 2018, then eight years of cobwebs. What you are reading is the third life, rebuilt from the studs, and this time built so I cannot use friction as an excuse to abandon it again. Here is the whole adventure: the two blogs that died, the monsters in the rewrite, and the respectable old doctor who kept whispering that I should just come back to him.

## A quiet place

A static site is a quiet place. Mine got so quiet you could hear the cobwebs settle. The last post went up in March 2018, a cheerful little note titled "Welcome to Jekyll!", and then nothing. Eight years of nothing. The welcome mat was still out. Nobody was home.

It is worth being honest about why, because the reason is not interesting and that is exactly the point. The blog did not die for lack of things to say. It died of friction.

## Two funerals

The first life was [Pelican](https://blog.getpelican.com/), back in 2015. I was proud of it. I even wired up a tiny publishing pipeline, a `publish.sh` and a git `post-commit` hook, so that every commit shipped the site:

```sh
# .git/hooks/post-commit, circa 2015 — the original "frictionless" dream
pelican content -o published -s publishconf.py && \
  ghp-import -b master published && \
  git push origin master
```

"Now with every commit, the blog gets published!" I wrote, delighted. Reader, the blog was not published much.

The second life was Jekyll, in 2018. The migration post was four lines long and ended on a hopeful command:

```sh
~/Kronuz.github.io $ gem install jekyll bundler
~/Kronuz.github.io $ bundle exec jekyll serve
```

Here is the thing both of these had in common. The setup was a delight for exactly one afternoon. Write a post, run a command, push, watch it deploy. Magic. The trouble is always the *second* post. By then you have forgotten the command, the Ruby version has drifted, bundler wants a word, a gem refuses to build, and the gap between "I have a thought" and "it is published" has quietly grown wide enough to fall into. So the thoughts stayed in my head, which is the worst possible place for them.

## The respectable doctor

In 2026 I decided to fix the actual problem instead of writing one more apologetic "sorry for the silence" post. The goal was simple and a little ruthless: make publishing so cheap that laziness stops being a valid excuse.

This is where the doctor shows up.

Jekyll is *respectable*. GitHub builds it for free, with no pipeline to babysit, and I already knew it. Every time the rebuild got hard, a calm and reasonable voice suggested I just go back to him. He is a known quantity. He is safe.

The trouble is that the respectable Dr. Jekyll I remembered had a Mr. Hyde I had conveniently forgotten: the local Ruby toolchain, the gem versions, the `bundle exec` incantations, the whole quiet machinery of friction that had killed the blog twice already. The doctor and the monster were the same person. They always are.

What finally broke the spell was realizing that the one thing making Jekyll tempting, *GitHub builds it automatically*, was not unique to Jekyll at all. GitHub Actions will happily build anything, Astro included. The single reason to go back evaporated. I shut the door on the doctor and went looking for a better weapon.

## Into the dungeon

The better weapon turned out to be [Astro](https://astro.build) with [Starlight](https://starlight.astro.build). That decision was the easy part. The dungeon was everything after it, and the dungeon had monsters.

**The first monster was the theme.** I am constitutionally incapable of reading code in someone else's colors. So before writing a single post I rebuilt my old "Kronuz" editor theme as a syntax theme for the site, dark and light, down to the exact olive green I use for strings. Vanity? Absolutely. But a blog you do not enjoy looking at is a blog you do not write.

**The second monster lived deeper down: diagrams.** I did not want screenshots of diagrams, I wanted real ones, in the repo, in version control, themed to match. [D2](https://d2lang.com) does this beautifully. The catch is that it is a separate binary the build shells out to, which is a small dungeon of its own to get installed in continuous integration. Worth it. Now a fenced `d2` block becomes a crisp, theme-aware diagram at build time, and the source lives next to the prose.

**The boss fight was comments.** Comments on a static site are the classic boss: the site has no backend, and comments are the most backend-shaped thing there is. The modern answer is [giscus](https://giscus.app), which parks every thread in GitHub Discussions and renders them inline. On a normal public repository it Just Works™️. (On a locked-down corporate one it is a genuine nightmare, but that is a different dungeon, and a different blog.) Here, it just works, themed to match the rest of the site and reacting to the light/dark toggle.

There was also a flourish I could not resist. The home page greets you with a tiny Python REPL that calls `kronuz.whoami()` and types out a different answer each time. It does nothing useful. I love it.

## What I dragged back out

Here is what the whole adventure actually bought me, and it is the only feature that mattered from the start: the path from thought to published is now one command.

```sh
npm run publish -- my-post
```

That drops the draft flag, stamps the date, commits, and pushes. A GitHub Action does the rest, builds the site, renders the diagrams, and deploys it. No Ruby. No `bundle exec`. No remembering. The 2015 dream of "every commit publishes," finally delivered, eleven years and two dead blogs later.

## Why bother

So, why does this exist?

The same reason it existed in 2015. I figure things out, sometimes gnarly bugs, sometimes a profiling result, sometimes a packaging trick that shaved real money off a server bill, and I like to write them down somewhere they can be read, argued with, and occasionally corrected. A thought you cannot share is a thought you only half understand.

The doctor is gone. The Ruby is gone. The friction that buried this place twice is, I hope, gone with them. The welcome mat is back out, and this time someone is home.
