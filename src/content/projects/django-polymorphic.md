---
title: Django Polymorphic
tagline: Polymorphic Django model inheritance
description: Improved Django model inheritance with automatic downcasting, and the deletion fix that made it safe.
tech: [Python, Django]
repo: https://github.com/django-commons/django-polymorphic
status: shipped
order: 6
---

django-polymorphic improves model inheritance for Django: querying a base model returns
instances of the right subclass automatically, instead of the plain base rows Django gives
you by default. It's a widely-used community library (around 1,800 stars), and the use case
that pulled me into it was a bug in how Django deleted polymorphic objects.

Django's delete `Collector` assumed every model in a delete batch matched the first one, so
deleting across a polymorphic hierarchy could generate the wrong `DELETE` statements and
raise integrity errors. My patch on ticket #16128 became the basis for the fix in #23076,
which the Django maintainers applied "directly based on a patch submitted by Kronuz." It's a
small, sharp kind of contribution I like: a subtle correctness bug in code that thousands of
projects rely on, fixed once, upstream.
