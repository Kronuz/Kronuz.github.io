---
title: "CSS That Computes"
subtitle: "Building a Sass compiler in Python."
description: "A code-verified look at pyScss, the Sass compiler I wrote in Python: how Sass is really a small typed expression language, how Number carries units and cancels them like dimensional analysis, how Color does channel math, and why the scanner had to be rewritten in C. With links to the real source."
excerpt: "Sass looks like CSS with variables, but it is really a small typed programming language: colors that add, numbers that carry units and cancel them. I rebuilt about 95% of it in Python. Here is how the compiler actually works, from the C scanner to the color math."
date: 2026-06-08
draft: true
series: "Opening Boxes"
seriesOrder: 4
tags:
  - opening-boxes
  - python
  - compilers
---

*Part of the **Opening Boxes** series, a set of technical deep-dives into the boxes from [The Boy Who Opened Boxes](/blog/the-boy-who-kept-opening-the-box/). This one opens [pyScss](https://github.com/Kronuz/pyScss). It is also the grown-up, legal version of [The Forbidden Layer](/blog/the-forbidden-layer/): take a tool someone built in another language, open it up, understand exactly how it works, and rebuild it in yours.*

[Sass](http://sass-lang.com/) was a Ruby tool. I wanted it in Python, so I wrote one, [pyScss](https://github.com/Kronuz/pyScss), which implements about **95% of Sass 3.2**. You install it with `pip install pyScss` and use it like this:

```python
from scss import Compiler
Compiler().compile_string("a { color: red + green; }")
```

Look closely at that input. `color: red + green`. You are *adding two colors*. That line is the whole reason this is interesting, and the reason building it was a real compiler problem and not a glorified find-and-replace.

## Sass is not a template language. It is a typed language.

The mistake is to think Sass is CSS with variables pasted in. It is not. Sass is a small, **typed expression language** that happens to emit CSS. `red + green` is not string concatenation; it is an operation on two values of type `Color`, and it produces a third `Color`. `10px * 2` is arithmetic on a value of type `Number` that carries a unit. To compile Sass you have to actually evaluate these expressions, which means you need real value types, with real arithmetic, and a real evaluator.

pyScss has exactly that. The value types live in [`scss/types.py`](https://github.com/Kronuz/pyScss/blob/master/scss/types.py): `Number`, `Color`, `String`, `Boolean`, `List`, `Map`, `Null`, and a few more, each a subclass of a common `Value`. Two of them are worth opening up.

### Numbers that know their units

In Sass, `10px`, `2em`, and `50%` are not strings with a suffix. They are numbers with **dimensions**, and they obey dimensional analysis. Multiply `10px` by a unitless `2` and you get `20px`. Divide `10px` by `2px` and the units cancel to a plain `5`. pyScss's `Number` implements this literally: it stores units as separate numerator and denominator tuples and cancels the ones that appear on both sides, exactly like reducing a fraction.

```python
# from scss/types.py: a Number carries its units as numer/denom tuples
def __init__(self, amount, unit=None, unit_numer=(), unit_denom=()):
    ...
    # Cancel out any convertable units on the top and bottom
    numerator_base_units = count_base_units(unit_numer)
    denominator_base_units = count_base_units(unit_denom)
    ...
    self.unit_numer = tuple(unit_numer)
    self.unit_denom = tuple(unit_denom)
    self.value = amount * (numer_factor / denom_factor)
```

There is a precision subtlety hiding in there that I am still a little proud of. Unit conversions are ratios (96px to an inch, and so on), and doing them in floating point accumulates error. So the amount is stored as a Python `Fraction`, not a float, to keep conversions exact. The source even keeps my honest note next to it: *"this slowed the test suite down by about 10%, ha."* Correctness cost ten percent, and I paid it.

### Colors that do math

`Color` (also in `types.py`) stores an RGBA tuple and knows how to be built from every form Sass accepts: [`from_rgb`](https://github.com/Kronuz/pyScss/blob/master/scss/types.py), `from_hsl` (which leans on Python's own `colorsys`), and `from_hex`. Once a literal like `red` is a `Color`, `red + green` is channel-wise addition on the underlying values. The arithmetic operators on the value types are what make CSS, suddenly, able to compute.

## The pipeline: scan, parse, evaluate, flatten

Putting it together, compiling a stylesheet runs through a real compiler pipeline.

```d2 alt="The pyScss pipeline: SCSS source goes through a C-accelerated scanner, then a yapps grammar that builds an AST, then a Calculator that evaluates expressions in a Namespace over typed Sass values, then selector flattening to plain CSS"
direction: down
src: "SCSS source"
scan: "Scanner, C-accelerated\n(scanner.c, _speedups.c)" {style.bold: true}
parse: "yapps grammar to AST\n(expression.g)"
calc: "Calculator evaluates expressions\nin a Namespace (vars, mixins, functions)" {style.bold: true}
types: "Typed Sass values:\nNumber (+units), Color, List, Map" {style.stroke-dash: 3}
css: "Nest, flatten selectors, emit CSS"
src -> scan -> parse -> calc
calc -> types: "operates on"
calc -> css
```

The grammar for the expression language is a real grammar, written for the `yapps2` parser generator in [`scss/grammar/expression.g`](https://github.com/Kronuz/pyScss/blob/master/scss/grammar) and compiled to a scanner and parser. The [`Calculator`](https://github.com/Kronuz/pyScss/blob/master/scss/calculator.py), whose docstring is simply *"Expression evaluator,"* walks the resulting AST and evaluates it against a `Namespace` that holds the variables, mixins, and functions in scope, caching parsed ASTs along the way. Selectors get parsed and the nesting flattened. Out the other end comes plain CSS.

## Why there is C in a Python project

If you look in the repository you will find [`scss/src/scanner.c`](https://github.com/Kronuz/pyScss/blob/master/scss/src/scanner.c), along with `_speedups.c`, `block_locator.c`, and a small `hashtable.c`. A Sass compiler written in pure Python spends an enormous fraction of its time in the **scanner**, character by character, and that is exactly the kind of tight loop CPython is slowest at. So the hot path got a hand-written C scanner, with a pure-Python scanner kept as a fallback so the library still installs and runs anywhere, PyPy included.

That instinct is the same one from every other box in this series: when a thing is slow, open it, find the loop that actually costs, and rewrite just that. In DOSBox it was the scaler. Here it was the tokenizer. The shape of the fix never changes.

## What it was

pyScss was, for a while, a widely used way to compile Sass without a Ruby dependency in the build, `pip install pyScss` and go. Implementing 95% of someone else's language teaches you that language more thoroughly than any amount of using it, because every corner you skipped as a user is a corner you now have to make behave. I came out the other side understanding Sass better than I understood most things I had merely used, which is the whole argument for opening the box instead of admiring it from outside.

---

*Code references: [`scss/types.py`](https://github.com/Kronuz/pyScss/blob/master/scss/types.py) (Number, Color and the other Sass value types), [`scss/calculator.py`](https://github.com/Kronuz/pyScss/blob/master/scss/calculator.py) (the expression evaluator), the [yapps grammar](https://github.com/Kronuz/pyScss/blob/master/scss/grammar), and the [C scanner](https://github.com/Kronuz/pyScss/blob/master/scss/src/scanner.c). The full source is at [github.com/Kronuz/pyScss](https://github.com/Kronuz/pyScss).*
