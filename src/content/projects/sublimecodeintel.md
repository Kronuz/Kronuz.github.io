---
title: SublimeCodeIntel
tagline: Sublime Code Intelligence
description: Full-featured code intelligence and smart autocomplete engine for Sublime Text.
tech: [Python, Sublime Text]
logo: /img/projects/sublimecodeintel.png
repo: https://github.com/SublimeCodeIntel/SublimeCodeIntel
website: https://sublimecodeintel.github.io/
docs: https://sublimecodeintel.github.io/docs/
status: shipped
order: 2
---

SublimeCodeIntel brought IDE-grade code intelligence to Sublime Text: jump-to-definition,
real-time import autocomplete, and function-call tooltips, across a whole project. I started
it in 2011, years before the Language Server Protocol made any of this routine, and for a
long stretch it was *the* way to get this kind of navigation in a famously minimal editor.

The trick was not writing a code-intelligence engine from scratch. I ported one. The whole
thing is built on ActiveState's Open Komodo engine (the CIX / CodeIntel2 system behind the
Komodo IDE), which meant it inherited Komodo's entire language roster on day one: Python,
PHP, JavaScript and ES6, Node.js, Ruby, Perl, Tcl, HTML/HTML5, CSS, SCSS and Less, the
Django, Twig, Smarty and Template Toolkit templating languages, XML/XSLT, Mason, and more.
It's distributed under the Mozilla Public License, same as Open Komodo. That lineage is why
it could be genuinely useful, for around twenty languages, almost immediately.

It got big, and it stayed big. It's around 5,000 stars and over 1.8 million installs on
Package Control, where, even now, it still ranks #7 by installs among *all* Sublime Text
packages. I eventually transferred it into a dedicated community organization on GitHub so it
could outlive my involvement, and I still keep a personal LSP-based fork going for my own
setup. Spinning a tool out into its own org and brand became a habit of mine: the same
pattern runs through [SublimeLinter](/projects/sublimelinter/) and [mech](/projects/mech/).
