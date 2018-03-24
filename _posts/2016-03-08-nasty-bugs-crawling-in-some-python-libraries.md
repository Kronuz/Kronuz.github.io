---
title:      Nasty Bugs Crawling In Some Python Libraries
date:       2016-03-08 23:00:00 -0600
modified:   2016-03-09 10:00:00 -0600
categories: Python
author:     Kronuz
tags:       python, bug, exception, monkeypatch
identifier: nasty-bugs-crawling-in-some-python-libraries
redirect_from: /nasty-bugs-crawling-in-some-python-libraries.html
---

Nasty bugs crawling down in some of my installed Python libraries.

The Problem
-----------

For many weeks I had a problem in one of our codebases using the
`requests` Python library where doing a `requests.get()` would end up
catching a weird exception nobody could figure out. See
<https://github.com/kennethreitz/requests/issues/2935>

**JUST TO BE CLEAR HERE, NO ACTUAL BUG WAS THERE IN THE FANTASTIC
requests LIBRARY!**

This is an example of exception we had been seeing:

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
  File "/usr/local/lib/python2.7/site-packages/requests/packages/urllib3/poolmanager.py", line 99, in clear
    self.pools.clear()
  File "/usr/local/lib/python2.7/site-packages/requests/packages/urllib3/_collections.py", line 93, in clear
    self.dispose_func(value)
  File "/usr/local/lib/python2.7/site-packages/requests/packages/urllib3/poolmanager.py", line 65, in <lambda>
    dispose_func=lambda p: p.close())
  File "/usr/local/lib/python2.7/site-packages/requests/packages/urllib3/connectionpool.py", line 410, in close
    conn = old_pool.get(block=False)
  File "/usr/local/lib/python2.7/Queue.py", line 176, in get
    raise Empty
KeyError: (1, True)
```

A `Empty` exception was being thrown, but a `KeyError` was being
received.

The Diagnosis
-------------

I struggled hard trying to find the code that was, as many theorized,
monkeypatching the `Queue` module. No luck there. The most commonly
suggested suspect was `gevent`; however, I didn't even have `gevent`
installed, so I kept looking for things that could be monkeyparching
stuff. e.g. do a regex search of `\.(Empty|LifoQueue|get)\s*=` and
`setattr\([^)]+["'] (Empty|LifoQueue|get)["']\)`. Nothing.

Obviously something was \"patching\" the `Queue.Empty` variable, but
there was no way of telling what, who, when or why\...

The Solution
------------

I had almost lost any hope, when I decided to go hunting again and then
I remembered about IRC channels\... It was an aliviating moment when
someone at Freenode's \#python (*Yhg1s*) suggested I could try
protecting a Python module by directly modifying `sys.modules` and
exchanging the module in question a tweaked object instead of a module,
so when the bad guy was trying to modify `Empty` it would get exposed by
throwing an exception. This is how I did it:

First, I protected the Queue module. To do this, I renamed the original
`Queue.py` to `_Queue.py`:

```
mv /usr/local/lib/python2.7/Queue.py /usr/local/lib/python2.7/_Queue.py
```

And then in its place, I created another `Queue.py` which would mimic
the real `Queue` module, only with a protected object to which no
attribute assignments would be allowed, so the whole new
`/usr/local/lib/python2.7/Queue.py` ended up like this:

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

As you see, I modified `sys.modules['Queue']`, so further imports of
`Queue` would return the `Protected` object with all attributes from
`_Queue` (the original `Queue`, only sort of immutable).

Finally, after doing that, I starting using the system, and I quickly
saw a new exception:

```
Traceback (most recent call last):
  File "/usr/local/lib/python2.7/site-packages/rest_framework/views.py", line 463, in dispatch
    response = handler(request, *args, **kwargs)
  File "project/apis/base.py", line 1184, in create
    self.perform_create(serializer)
  File "project/apis/base.py", line 1243, in perform_create
    return self._stamp_invoice(request, serializer)
  File "project/apis/base.py", line 1272, in _stamp_invoice
    serializer.save(**extra_kwargs)
  File "/usr/local/lib/python2.7/site-packages/rest_framework/serializers.py", line 191, in save
    self.instance = self.create(validated_data)
  File "project/apis/base.py", line 520, in create
    return self._issue_invoice(xml_etree)
  File "project/apis/base.py", line 982, in _issue_invoice
    with Balancer('dummy', owner, is_live) as ws:
  File "project/backends/balancer.py", line 72, in __enter__
    self.ws = self.get_pooler().get_stamper(self.owner, self.live)
  File "project/backends/balancer.py", line 34, in get_stamper
    except KeyError, Queue.Empty:
  File "/usr/local/lib/python2.7/Queue.py", line 9, in __setattr__
    raise AttributeError("can't set attribute")
AttributeError: can't set attribute
```

See the problem here:

```python
try:
    ...
except KeyError, Queue.Empty:
    ...
```

Someone decided to catch both `KeyError` and `Queue.Empty`
exceptions\... only this isn't the right way of catching two exceptions
in Python 2. What this someone did in this library was actually
assigning any `KeyError` exception object onto `Queue.Empty`, so if for
instance a `KeyError: (1, True)` was caught, it'd get assigned and
would replace old `Queue.Empty` (effectively monkeypatching it without
even knowing)

I fixed this, obviously, by simply changing the code to:

```python
try:
    ...
except (KeyError, Queue.Empty):
    ...
```

The Verdict
-----------

After checking around all the code we use, we found there are quite a
few libraries doing things like that one above\... producing bugs which
end up overriding exception types, and these can hit you when you least
expect it. Beware!

What I Learned
--------------

But most of all, this whole mess was a useful exercise to learn a good
technique about how to \"protect\" a whole module from monkeypatching
*and* being able to detect problems if you know something *must* be
patching a module but you don't know what.
