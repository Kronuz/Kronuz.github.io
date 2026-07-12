---
title: "The Large, Black Ball"
subtitle: "Making Python lazy, in the most dangerous part of the language."
description: "The deep version of the Cinder Lazy Imports story: why Instagram Server's import graph was a solid black ball, how deferred objects defer module loading until first use, and why the mechanism had to live inside the dictionary internals. With the real numbers."
excerpt: "Instagram Server loaded 28,000 modules just to start, and its dependency graph rendered as a solid black ball. The fix was to make Python lazy: import a thing only when you reach for it. Doing that safely meant going into the most dangerous part of the language."
date: 2026-06-08
draft: true
featured: true
series: "Opening Boxes"
seriesOrder: 7
tags:
  - opening-boxes
  - python
  - performance
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This one opens the box I am still proudest of: making Python lazy. The original, shorter telling is the [Cinder blog post](https://developers.facebook.com/blog/post/2022/06/15/python-lazy-imports-with-cinder/); this is the longer, more technical one.*

In late 2021 a server reload at Instagram took around fifty seconds on a good day, and up to a minute and a half on a bad one. Not the production server. The *development* server, the one an engineer restarts dozens of times a day to see whether the line they just changed did what they hoped. Fifty seconds, times every save, times every engineer. That is not latency. That is a tax on thinking.

By early 2022 the same reload was about **70% faster at p50**, the codebase loaded roughly **12x fewer modules** at startup, and a class of error that engineers hit about **80 times a day** had dropped to **zero**. This is how, and more importantly *why* the how was so awkward.

## A graph that came back black

The obvious question is: why is starting a Python server slow at all? Python does not compile. The answer is *imports*. Just starting Instagram Server triggered loading about **28,000 modules**, and most of the startup time was spent literally importing them, building function and class objects, running module-level code.

You cannot fix what you cannot see, so a colleague, Joshua Lear, set out to draw the dependency graph. He ran a modified visualization script and waited. After **three hours** it finished, and what came back was a *"large, black ball"*: a circle so dense with edges that it rendered as a solid disc. His first thought was that the analyzer had a bug. It did not. The Instagram codebase really was that entangled, a **big, ugly mesh** where almost everything reached almost everything else.

That mesh has a nasty property I started calling the **Import Domino Effect**. Touch one module and you do not pull in one module, you pull in its imports, and their imports, and so on across the whole ball. Importing *anything* tended to import *everything*.

## Why the obvious fix does not work

So just find the heavy dependencies and cut them out of the startup path, right? Not quite. The moment you try to refactor an entangled graph, you hit **circular imports**. Module A imports B, B imports A, and the only thing holding the peace is the exact order things happened to load in. Change that order, even slightly, and a cycle that was dormant for years suddenly throws at import time, for you or for someone downstream a week later. Import cycles had caused real outages. Engineers were seeing about **80 import-cycle errors a day**.

For years the team fought this by hand. Make an expensive subsystem lazy: Django URLs, notifications, observers, even regular expressions, each wrapped in an inner import or an `import_module()` call so it loaded on demand. It worked, locally and temporarily, and then the ball grew back. Hand-tuned laziness is fragile and does not scale.

What was needed was not another hand-placed lazy import. It was a robust way of *lazifying all things*, automatically, for every import in the program.

## The idea: defer the import until you touch the name

Here is the whole idea in one sentence: an `import` statement should not load a module, it should only *promise* one.

Normally `import json` runs immediately. It finds the module, executes all of its top-level code (and everything *it* imports), and binds the result to the name `json` in your namespace. With lazy imports, that same line binds the name to a **deferred object** instead, and runs none of the module code. The module is loaded only when something actually *uses* the name, which might be the very next line, or a deep call stack hours later, or never.

```d2 alt="Eager import triggers a domino that pulls in 28,000 modules; lazy import binds a deferred name in the dict and resolves it only on first use"
direction: down
eager: "Eager import: the domino effect" {
  ea: "import app"
  eb: "pulls models"
  ec: "pulls views"
  ed: "pulls 28,000 modules"
  ea -> eb -> ec -> ed
}
lazy: "Lazy import" {
  la: "import app"
  lb: "deferred name in the dict" {style.bold: true}
  lc: "resolve only on first use" {style.bold: true}
  la -> lb -> lc
}
```

At Instagram this was a global switch: turn it on and *every* import in the program, including the standard library and third-party packages, becomes lazy automatically. No keyword, no per-line annotation. You import the world, and the world stays folded up until you reach into it.

```python
# With Lazy Imports enabled, this line loads and executes nothing:
import json              # binds the name "json" to a deferred object

# json's module code runs only when the name is first touched:
payload = json.dumps(x)  # this lookup resolves the deferred object, json loads now
```

If `json` is never touched on this code path, you never pay for it. Multiply that across 28,000 modules where the average request touches a small fraction, and the startup bill collapses.

## The hard part: it had to live in the dictionary

I had a working prototype in a few weeks. It was promising, and I badly underestimated everything between "promising" and "rock solid."

The first design kept the deferred objects as ordinary Python objects. That worked until the deferred objects started *leaking out of the C world into Python*: places deep in the interpreter and in libraries expected a real module or a real value and instead got my placeholder, in contexts where it had no business appearing. You cannot ship a feature that occasionally hands the rest of the language a ghost.

After some very good conversations with Carl Meyer and Dino Viehland, I made a decision that still sounds slightly insane when I say it out loud: move the whole mechanism *down*, into the **dictionary internals**.

Dictionaries are the substrate of Python. A module's namespace is a dict. A class body is a dict. Instance attributes, globals, keyword arguments, almost everything is a dict underneath. The reason to put laziness there is that *every* name access already goes through a dict lookup, so if the dict itself knows how to resolve a deferred value on the way out, resolution becomes automatic and invisible everywhere, with no placeholder ever escaping. Roughly:

```python
# What the module namespace holds right after `import json`:
#   eager:  {"json": <module 'json'>}     # already fully loaded
#   lazy:   {"json": <deferred 'json'>}   # a value that resolves on first lookup
```

The reason it is also *dangerous* to put laziness there is the same reason: the dict is the hottest, most heavily optimized data structure in CPython. Add a branch to the lookup path and you do not slow down imports, you slow down *the entire language*, every attribute access in every program. So the work was not "make it lazy," it was "make it lazy and prove the dict is exactly as fast as before when nothing is deferred." That second half is where most of the time went. There were many smaller obstacles too, including a genuine CPython bug in `TypedDict` ([bpo-41249](https://bugs.python.org/issue41249)) that I tripped over along the way.

Eventually I had a build that was reliable, and that ran the open-source [`pyperformance`](https://pyperformance.readthedocs.io/) suite, three times over, performance-neutral when the patch was present but the feature was off. A perf-neutral patch is the price of admission for touching dict internals, and it took a while to earn.

## What it bought

I enabled lazy imports across tens of thousands of Instagram Server modules and rolled it out, in early 2022, to thousands of development and production hosts. The graphs moved the day it went live.

| Metric | Result |
| --- | --- |
| Modules loaded at startup | **~12x fewer** |
| Dev-server reload, p50 | **~70% reduction** |
| Dev-server reload, p90 | **~60% reduction** |
| Other servers and tools | **50–70% faster** |
| Memory usage | **20–40% lower** |
| Import-cycle errors at Instagram | **~80/day to 0** |

That last row is the one I love most. Lazy imports does not forbid circular imports, it *defuses* them. A cycle that only mattered because both sides ran eagerly at import time mostly stops mattering when neither side runs until first use. We went from ~80 import-cycle errors a day to none, and refactoring the ball became possible for the first time in years.

## What it is not

Honesty requires the other column. Making the whole world lazy changes Python's semantics, and some code leans on the old behavior:

- **Import side effects.** Modules that *do something* simply by being imported (register a handler, mutate global state, expect a submodule to be set as an attribute on its parent) can stop happening, because the import no longer runs.
- **`sys.path` games.** Code that temporarily adds a path, imports, then removes the path assumes the import happened *right there*. Deferred, it does not.
- **Errors move in time.** Every failure, including `ModuleNotFoundError`, is deferred from import time to first-use time. The traceback now points at the line that *used* the name, not the line that imported it, which can make debugging less obvious.
- **Type annotations can quietly defeat it.** A bare annotation referencing an imported name forces that name to resolve. The fixes are `from __future__ import annotations`, string annotations for `typing.TypeVar()` and `typing.NewType()`, and wrapping type-only aliases in a `TYPE_CHECKING` block.

None of these are fatal, and most are one-time cleanups, but a deep-dive that hid them would be lying. It *Just Works™️*, most of the time, and the rest of the time it teaches you something true about your codebase.

## What lies ahead

The most exciting thing about lazy imports was never the seconds it saved. It was that it made a class of problem, the entangled import graph, stop being load-bearing. Refactors that were impossible became routine. Things you could not do because "it would create a cycle" became fine.

Which raised the obvious next question: if this is good for one company, why not give it to all of Python? I wrote it up as **PEP 690** and proposed it to the language itself. That is a different box, with a more painful and more interesting story, and it gets its own article in this series.

None of this opened alone. Joshua Lear is the reason we ever *saw* the ball; Benjamin Woodruff drew the graph that made it legible; Carl Meyer and Dino Viehland climbed down into the dictionary internals with me and talked me out of the design that leaked. Many more carried the rollout and the long tail of compatibility fixes. The [full list of names is in the original post](https://developers.facebook.com/blog/post/2022/06/15/python-lazy-imports-with-cinder/#thanks), and it is long for a reason.

---

*Sources and code: the [Cinder Lazy Imports post](https://developers.facebook.com/blog/post/2022/06/15/python-lazy-imports-with-cinder/) (the numbers above are from there), the [Cinder runtime](https://github.com/facebookincubator/cinder) and its [lazy-imports docs](https://github.com/facebookincubator/cinder/blob/cinder/3.8/CinderDoc/lazy_imports.rst), [PEP 690](https://peps.python.org/pep-0690/), and [bpo-41249](https://bugs.python.org/issue41249).*
