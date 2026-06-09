---
title: "Catching a Monkeypatch"
subtitle: "For weeks, requests.get() kept catching an exception that made no sense. The library was innocent. The culprit was one comma in a Python 2 except clause."
description: "A months-long bug hunt: requests.get() kept catching a KeyError where an Empty should have been. The fix was to replace a module in sys.modules with a write-protected proxy that raised the moment something tried to patch it, exposing a Python 2 except-syntax trap."
excerpt: "For weeks, requests.get() kept catching an exception nobody could explain, and the library was innocent. This is the hunt: replacing a module in sys.modules with a proxy that screams when something patches it, and the one-comma Python 2 bug it caught."
date: 2016-03-08
draft: true
authors: kronuz
series: "Opening Boxes"
seriesOrder: 6
tags:
  - opening-boxes
  - python
  - monkeypatch
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This one opens a box I did not want to open: someone else's monkeypatch, hiding in a dependency.*

For many weeks, a codebase I worked on had a bug where a plain `requests.get()` would end up catching an exception nobody could explain. I want to be clear before I start, because the traceback points at it and the traceback is lying: there was never any bug in the excellent [`requests`](https://github.com/kennethreitz/requests/issues/2935) library. It was the messenger.

Here is the kind of exception we kept seeing:

```
Traceback (most recent call last):
  File "project/views.py", line 49, in get_url
    response = requests.get(url)
  File "/usr/local/lib/python2.7/site-packages/requests/api.py", line 69, in get
    return request('get', url, params=params, **kwargs)
  File "/usr/local/lib/python2.7/site-packages/requests/api.py", line 54, in request
    session.close()
  File "/usr/local/lib/python2.7/site-packages/requests/sessions.py", line 649, in close
    v.close()
  File "/usr/local/lib/python2.7/site-packages/requests/adapters.py", line 264, in close
    self.poolmanager.clear()
  File ".../urllib3/poolmanager.py", line 99, in clear
    self.pools.clear()
  File ".../urllib3/_collections.py", line 93, in clear
    self.dispose_func(value)
  File ".../urllib3/poolmanager.py", line 65, in <lambda>
    dispose_func=lambda p: p.close())
  File ".../urllib3/connectionpool.py", line 410, in close
    conn = old_pool.get(block=False)
  File "/usr/local/lib/python2.7/Queue.py", line 176, in get
    raise Empty
KeyError: (1, True)
```

Read the bottom two lines slowly. The code does `raise Empty`, and what comes out is a `KeyError: (1, True)`. A `raise` statement raised one exception type and the caller received a completely different one. That is not supposed to be possible.

## The diagnosis

The obvious theory was that something was monkeypatching the `Queue` module, swapping out its `Empty` for something else. The usual suspect for that kind of thing is `gevent`, which patches the standard library on purpose. Except I did not have `gevent` installed.

So I went hunting by hand. I grepped the entire codebase for anything assigning to those names, patterns like `\.(Empty|LifoQueue|get)\s*=` and `setattr\([^)]+["'](Empty|LifoQueue|get)["']\)`. Nothing. Something was clearly patching `Queue.Empty`, but there was no visible code doing it, and no way to tell what, who, when, or why.

## The trick: a module that screams when you touch it

I had nearly given up when I remembered IRC still exists. On Freenode's `#python`, *Yhg1s* suggested something I had never thought to do: protect a module by replacing it in `sys.modules` with an object that mimics the module but refuses to be modified, so that the moment the bad guy tries to assign to `Empty`, it raises and exposes itself in a traceback.

First, I moved the real `Queue` module aside, renaming `Queue.py` to `_Queue.py`:

```
mv /usr/local/lib/python2.7/Queue.py /usr/local/lib/python2.7/_Queue.py
```

Then, in its place, I wrote a new `Queue.py` that imports the original under its new name and exposes everything through a write-protected proxy. Any attribute read works; any attribute *write* raises immediately:

```python
class Protected(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, name))

    def __setattr__(self, name, value):
        raise AttributeError("can't set attribute")

import sys, _Queue
sys.modules['Queue'] = Protected(_Queue.__dict__)
```

Now any code that does `import Queue` gets the `Protected` object, carrying every attribute of the real module, but immutable. The first attempt to assign to any attribute on it raises an `AttributeError` right at the offending line.

```d2 alt="Swap the real Queue module for a write-protected proxy in sys.modules; when the Python 2 except trap tries to assign to Queue.Empty, the proxy raises and the traceback points at the culprit"
direction: down
swap: "Swap the real Queue for a Protected proxy\nin sys.modules" {style.bold: true}
bad: "except KeyError, Queue.Empty:  (a Python 2 trap)\nassigns the caught error to Queue.Empty" {style.stroke-dash: 3}
trap: "Protected.__setattr__ raises AttributeError\non the illegal assignment" {style.bold: true}
cul: "the traceback points straight at the culprit line"
swap -> bad: "now run the app"
bad -> trap
trap -> cul
```

I started the system, used it for a minute, and the trap sprang:

```
Traceback (most recent call last):
  ...
  File "project/backends/balancer.py", line 34, in get_stamper
    except KeyError, Queue.Empty:
  File "/usr/local/lib/python2.7/Queue.py", line 9, in __setattr__
    raise AttributeError("can't set attribute")
AttributeError: can't set attribute
```

There it was, finally with a name and a line number.

## The one-comma bug

Look at the culprit:

```python
try:
    ...
except KeyError, Queue.Empty:
    ...
```

Someone meant to catch *both* `KeyError` and `Queue.Empty`. But that is not how you catch two exception types in Python 2. The form `except SomeError, name:` means "catch `SomeError` and bind the caught instance to the variable `name`." So this code was not catching two exceptions at all. It was catching `KeyError` and **assigning the caught `KeyError` instance to `Queue.Empty`**.

Every time that handler ran, it monkeypatched `Queue.Empty`, silently, replacing the real `Empty` class with whatever `KeyError` had just been caught, for instance `KeyError: (1, True)`. After that, somewhere far away, `Queue.get()` would do `raise Empty`, only `Empty` was no longer the empty-queue sentinel, it was a stale `KeyError`. That is how a `raise Empty` surfaced as a `KeyError`, weeks of confusion from a missing pair of parentheses.

The fix is exactly those parentheses:

```python
try:
    ...
except (KeyError, Queue.Empty):
    ...
```

## What it left me with

Two things stuck. The first is a healthy paranoia: once I went looking, I found several installed libraries doing the same `except A, B:` thing, each one quietly capable of overriding an exception type at the worst possible moment. The second is the technique itself, which has earned its keep many times since. When you are certain *something* is patching a module but you cannot find what, do not keep grepping. Replace the module with a `Protected` proxy that refuses to be written to, run the program, and let the monkeypatch raise its own hand.
