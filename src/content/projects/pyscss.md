---
title: pyScss
tagline: A Sass compiler for Python
description: A pure-Python compiler for the Sass language, a superset of CSS that adds variables, nesting, mixins, and functions.
tech: [Python]
logo: /img/projects/pyscss.png
repo: https://github.com/Kronuz/pyScss
docs: http://pyscss.readthedocs.io
status: shipped
order: 3
---

pyScss is a pure-Python implementation of the Sass language, the CSS superset that adds
variables, nesting, mixins, and functions. I started it in 2011, back when "compile your
CSS" meant shelling out to a Ruby toolchain and Node wasn't really on the table for a Python
shop. pyScss let a Python web stack compile Sass in-process, and for a stretch it was the
de-facto Sass compiler in that ecosystem.

It covered most of what people actually used: roughly 95% of Sass 3.2 and a good chunk of
Compass, MIT-licensed, running on Python 2 and 3 and PyPy. It's around 586 stars now and
mostly dormant. The world has moved on to libsass and Dart Sass, which is exactly what you
want to happen to a piece of infrastructure: it did its job for the years it was needed.
