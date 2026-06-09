---
title: "Twice to the Steering Council"
subtitle: "How lazy imports got rejected as PEP 690, came back as PEP 810, and ended up in the Python grammar without the part of the implementation I was proudest of."
description: "The standardization story behind lazy imports: PEP 690 proposed a global switch and was rejected by the Python Steering Council in 2022; PEP 810 proposed an explicit `lazy import` keyword and was accepted in 2025 for Python 3.15. Why the second attempt deliberately threw away the dict-internals trick."
excerpt: "I tried to give lazy imports to all of Python. The Steering Council said no, for a good reason. So we did it again, properly: explicit, opt-in, and pointedly not touching the dictionary internals I had been so proud of. The second time, they said yes."
date: 2026-06-08
draft: true
series: "Opening Boxes"
seriesOrder: 7
tags:
  - opening-boxes
  - python
  - cpython
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This one is the sequel to [The Large, Black Ball](/blog/the-large-black-ball/): what happened when I tried to give lazy imports to the whole language.*

The previous article ended on a single sentence: *I wrote it up as PEP 690 and proposed it to Python itself.* This is what happened next. The language said **no**, in December 2022. Then it said **yes**, in November 2025, to a different proposal that kept the idea and discarded the implementation detail I loved most. The feature is slated for **Python 3.15**.

It took knocking twice. Here is what changed between the knocks.

## The first knock: PEP 690

[PEP 690](https://peps.python.org/pep-0690/) proposed lazy imports as a **global switch**. You would flip it on for your whole application, with a `-L` interpreter flag or an `importlib.set_lazy_imports()` call, and from that point every top-level `import` in the program became lazy: deferred until the imported name was first used. Imports inside `try` / `except` / `with` blocks stayed eager (so import errors could be handled), star imports stayed eager (you cannot defer what you cannot enumerate), and anything inside a function or class was never "top level" to begin with.

The implementation was the dict-internals trick from the last article, written down formally. When a lazy import ran, the name went straight into the module namespace dictionary, but its value was an internal **lazy import object** holding the metadata to run the import later. A new flag on the dict's keys, `dk_lazy_imports` in `PyDictKeysObject`, marked dictionaries that might contain one. Every dictionary lookup checked whether the value it was about to return was a lazy object, and if so, resolved it on the spot: run the import, replace the placeholder with the real value, return the real value. The laziness lived *inside the dict*, so it was automatic and invisible everywhere a name was ever read.

That is an elegant trick. It is also exactly what got the proposal into trouble.

## The rejection

The Steering Council rejected PEP 690 in December 2022. I will not pretend it did not sting. But the reason was honest, and with a few years of distance, correct.

A global switch splits the world into **two Pythons**. In one, imports are eager and have side effects exactly when you wrote them. In the other, they are lazy and those side effects happen later, or never. Every library would now have to work, and be tested, under both. The Council's own words:

> A world in which Python only supported imports behaving in a lazy manner would likely be great. But we cannot rewrite history and make that happen.

The key thing I missed in the moment, and got later: they had not rejected the *idea*. They had rejected the *global switch*. Laziness imposed invisibly on the whole ecosystem was the problem. Laziness you asked for, explicitly, was never on trial.

## The second knock: PEP 810

So we did it again, properly this time. With Pablo Galindo Salgado leading and a group of people I deeply respect, I helped author [PEP 810](https://peps.python.org/pep-0810/). Instead of a mode that makes everything lazy, an explicit word you write yourself:

```python
lazy import json
lazy from json import dumps
```

You opt in, per import, in the open. A reader sees `lazy` and knows exactly what was deferred. There is still a global flag and a `__lazy_modules__` declaration for teams migrating a large codebase, and a `sys.set_lazy_imports_filter()` escape hatch for fine-grained control, but the heart of the proposal is the explicit keyword. It is the same idea the Council blessed in spirit, with the action-at-a-distance removed.

## The part I had to give up

Here is the twist I did not see coming, and the reason this is its own article rather than a footnote.

PEP 810 **deliberately does not touch the dictionary internals**. The thing I was proudest of in the original implementation, the lazy object living inside the dict and resolving on lookup, is explicitly listed in PEP 810's *Rejected Ideas*. The reasoning is sound, and it is a little humbling to read:

> The dictionary is the foundational data structure in Python. Adding any kind of hook or special behavior to dicts to support lazy imports would prevent critical interpreter optimizations including future JIT compilation, add complexity to a data structure that must remain simple and fast, affect every part of Python, not just import behavior, and violate separation of concerns: the hash table shouldn't know about the import system.

Instead, PEP 810 uses a `LazyImportType` **proxy object**. A lazy import binds the name to a proxy; the first time the name resolves, the proxy is replaced by the real value. No hook in the dict lookup path, so the JIT and every future dict optimization stay unobstructed. The PEP even works through why the proxy has to be a real replaceable object rather than something transformed in place: `lazy from foo import bar` can bind `bar` to *any* object, a function, a class, a constant, so there is no single memory layout to mutate into. A uniform proxy is the only thing that works for both `lazy import x` and `lazy from x import y`.

```d2 alt="PEP 690 put the lazy object inside the dict and was rejected as a global switch; PEP 810 uses an explicit lazy keyword and a LazyImportType proxy with no dict hooks, and was accepted"
direction: down
p690: "PEP 690 (2022): a global switch" {
  flag: "-L flag / set_lazy_imports()"
  dict: "lazy object lives in the dict (dk_lazy_imports)" {style.bold: true}
  resolve: "resolved on every dict lookup"
  verdict: "Rejected: two Pythons, eager and lazy" {style.stroke-dash: 3}
  flag -> dict -> resolve -> verdict
}
p810: "PEP 810 (2025): an explicit keyword" {
  kw: "lazy import json"
  proxy: "LazyImportType proxy, no dict hooks" {style.bold: true}
  swap: "proxy replaced on first use"
  ok: "Accepted: opt-in, dict stays clean"
  kw -> proxy -> swap -> ok
}
```

I think the proxy is the right call. The dict trick was clever, and clever in the wrong place is a liability when the wrong place is the hottest data structure in the language. The second attempt is better than the first precisely because it gave up my favorite part of the first.

## What it taught me

Shipping a feature inside one company and standardizing it for everyone are different crafts. Inside Instagram I optimized for "make it work, invisibly, for our codebase." For the language, the right objective was "make it explicit, optional, and impossible to impose on someone who did not ask." The Steering Council was protecting millions of people from a switch they would not have chosen, and they were right to.

On **November 3, 2025**, the Steering Council accepted PEP 810. The idea I had on a locked-down oncall night, annoyed at a server's startup time, the one the language turned down three years earlier, is going into the grammar of Python 3.15. Not because the first attempt was right. Because the second one was better, and because a roomful of people carried it the rest of the way.

It just took knocking twice.

---

*Sources: [PEP 690 (Lazy Imports)](https://peps.python.org/pep-0690/), [PEP 810 (Explicit Lazy Imports)](https://peps.python.org/pep-0810/), and the engineering story behind them in [The Large, Black Ball](/blog/the-large-black-ball/). PEP 810 was authored with Pablo Galindo Salgado and others; I am a co-author.*
