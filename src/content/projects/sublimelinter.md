---
title: SublimeLinter
tagline: A framework for linting code
description: The code-linting framework for Sublime Text, surfacing warnings and errors inline as you type.
tech: [Python, Sublime Text]
repo: https://github.com/SublimeLinter/SublimeLinter
website: http://www.sublimelinter.com
status: shipped
order: 5
---

SublimeLinter is a linting framework for Sublime Text. Rather than bundling one linter, it
provides the plumbing that dozens of language-specific linter plugins hang off of, surfacing
their warnings and errors inline as you type. Today the project sits at around 2,000 stars.

It didn't start as a framework, and it didn't start with that name. Ryan Hileman wrote a
single-file proof of concept called `sublimelint`. I forked it, refactored it into the
extensible multi-language framework it became, and in 2011 renamed it "SublimeLinter", the
CamelCase, Sublime-prefixed branding I'd reuse on
[SublimeCodeIntel](/projects/sublimecodeintel/). For the Sublime Text 2 era I was the
project's central maintainer, and my fork was the hub others merged through.

I stood up the GitHub organization the project still lives in, then handed the next
generation off: the Sublime Text 3/4 rewrite was led by other maintainers inside that org.
That's the arc I'm proudest of here, taking someone's sharp little idea and turning it into
something durable enough to outlive my involvement.
