---
title: "The Shunting Yard"
subtitle: "Turning a boolean query into something a machine can walk, in one pass over two stacks."
description: "boolean-parser turns a human-written boolean query like 'a OR (b AND NOT c)' into two consumable forms: an RPN token queue produced by Dijkstra's shunting-yard algorithm, and, on demand, an AST of typed nodes. It handles AND/OR/NOT/XOR/MAYBE with precedence, parentheses, quoted phrases, and bracketed lists, joins adjacent terms with a default OR, and does all the lexing and parsing in the constructor. The shunting yard is the elegant heart: one linear pass, an output queue and an operator stack, no recursion, and the RPN it leaves is directly executable, which is why many callers never build the tree at all."
excerpt: "Infix is how people write boolean queries and the worst way to evaluate them, because precedence and parentheses mean you cannot just read left to right. Dijkstra's shunting-yard algorithm fixes that in a single pass with two stacks, reshuffling 'a OR (b AND NOT c)' into a form a machine walks without ever recursing. The eleventh familiar is that algorithm, and the query language it feeds never needs the parse tree at all."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 11
tags:
  - familiars
  - cpp
  - parsing
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is a little compiler in a single class: [boolean-parser](https://github.com/Kronuz/boolean-parser).*

People write boolean queries in *infix*: `a OR (b AND NOT c)`, operators between their operands, precedence in their heads, parentheses to override it. It is the natural way to write and the worst way to evaluate, because you cannot read it left to right and act as you go. When you reach `OR` you do not yet know its right operand; when you hit `(` you have to remember everything outside it and come back. Infix demands you look ahead and back up, which is exactly the sort of thing a stack was invented to avoid.

[boolean-parser](https://github.com/Kronuz/boolean-parser) turns that human-written query into something a machine can just walk. Its whole job fits in one class, `BooleanTree`, and its constructor does all the work: lex the string into tokens, then run **Dijkstra's shunting-yard algorithm** over them to produce a queue in Reverse Polish Notation.

## The algorithm that is worth the post

The shunting yard is one of those algorithms that feels like a magic trick the first time it clicks, and it is named after exactly what it looks like: a railway shunting yard where cars are shuffled onto a side track and pulled back in a different order. You make one linear pass over the tokens with two stacks in hand, an **output queue** and an **operator stack**, and follow a tiny set of rules. An operand goes straight to the output. An operator waits on the operator stack, but before it does, any operators already there with higher-or-equal precedence get popped off to the output first, which is how precedence gets baked in without any lookahead. A `(` pushes; a `)` pops operators back to output until it finds its matching `(`. At the end you drain the stack. What falls out is the same expression in RPN, `a b c NOT AND OR`, where the order of operations is now implicit in the sequence and there is nothing left to parenthesize.

RPN is not just tidy; it is **directly executable**. To evaluate it you walk it front to back with one stack: push operands, and when you hit an operator, pop its operands, apply, push the result. No tree, no recursion, no precedence logic at runtime, because all of that was resolved in the single pass that built the queue. That is why many consumers, Xapiand's query DSL included, only ever walk the RPN queue and never ask for anything more. The parser hands them a ready-to-run sequence.

## The tree, when you want it

For the times you do want structure, `Parse()` consumes that RPN queue and builds an **AST**: a tree of typed nodes, `AndNode`, `OrNode`, `NotNode`, `XorNode`, `MaybeNode`, `IdNode`, with the operators as internal nodes and the terms as leaves. It is built on demand, from the same queue, so you pay for the tree only if you use it. The grammar it understands is small and practical: the five operators as both keywords (`AND`, `OR`, `NOT`) and symbols (`&`, `|`, `!`), parentheses, single- and double-quoted phrases, and a `[a,b,c]` bracketed-list syntax, with precedence running `NOT` > `AND` > `MAYBE` > `XOR` > `OR`. There is one humane touch that shows it came from a real query box: two terms written next to each other with no operator between them, `a b`, are joined by a default `OR`, because that is what a person typing two words almost always means.

## Where it fits

Reach for it whenever you need to accept a boolean expression from a human and turn it into something evaluable: a search query language, a filter DSL, a rules string. You get the RPN queue for free and the AST when you ask. Skip it if your inputs are already structured (you have JSON, not a string), or if your expression language is richer than boolean connectives and needs a real grammar and parser generator.

The next familiar drops back down to raw bytes and the oldest trick for making them fewer. Three different ways to compress a buffer, three genuinely incompatible formats, hidden behind one interface so uniform you switch between them by changing a single word.
