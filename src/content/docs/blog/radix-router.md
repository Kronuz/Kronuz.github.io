---
title: "The Fork in the Path"
subtitle: "Matching a URL to one of a thousand routes in time that ignores how many there are."
description: "radix-router maps /-separated path patterns to values through a compressed prefix trie, so a lookup costs O(path length) instead of O(routes): flat no matter how many endpoints you register, 200x faster than a linear scan at a thousand routes, 440x on a miss. The catch is the params and catch-alls, which turn the tree into a maze with forks, and matching them needs backtracking that stays bounded instead of blowing up on the one path an attacker sends on purpose."
excerpt: "Every request that reaches a server is a URL, and something has to decide which of a thousand handlers owns it before any real work starts. The obvious router gets slower with every endpoint you add. A radix tree does not: it walks the path, not the table, and stays flat at a thousand routes. The fourth familiar, and the forks in its tree are where it gets interesting."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 4
tags:
  - familiars
  - cpp
  - data-structures
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). The [last one](/blog/the-sparse-wheel/) was the strangest thing in the engine; this one is the first thing every request meets: [radix-router](https://github.com/Kronuz/radix-router).*

A request arrives as a URL, and before anything real can happen, something has to decide which handler owns it. `/documents/count` goes here, `/documents/42` goes there, `/static/css/site.css` goes somewhere else entirely. That decision happens on every single request, so it sits squarely on the hot path, and the naive way to make it is the way that quietly kills you as the server grows.

## The router that gets slower as you succeed

The first router anyone writes is a list. Register each pattern, and on every request walk the list comparing until one matches. It is fine at ten routes. It is `O(routes)`: every endpoint you add makes every lookup a little slower, and a **miss**, a URL that matches nothing, is the worst case, because it has to check the entire table before it can say no. A mature service has hundreds of endpoints. You built more features and made the router slower, and the slowest path is the 404 an attacker can send you a million times.

[radix-router](https://github.com/Kronuz/radix-router) is the structure that breaks that coupling. It stores the routes in a **radix tree**, a prefix trie with the single-child chains compressed out, so a lookup walks the shared prefixes of the *path* rather than scanning the *table*. The cost is `O(path length)`, and path length does not grow when you add routes. Flat. On the same pattern language, against the linear scan, across growing tables:

| routes | linear ns/op | radix ns/op | speedup |
| --- | --- | --- | --- |
| 8 | 43.8 | 11.3 | 3.9x |
| 128 | 692.9 | 19.3 | 35.9x |
| 1024 | 5048.6 | 24.7 | **204x** |
| 1024 (miss) | 10587.9 | 24.0 | **440x** |

The radix line barely moves, 11 ns to 24 ns, and only because a deeper tree touches more cache lines. The linear line just tracks the route count. This is the structure `httprouter` popularized and that Gin, Echo, and Fiber are built on; radix-router is the same idea in header C++.

## The forks

A trie that only held static paths would be easy, and it would not be worth a post. The interesting part is that real routes are not all static. Two segment kinds turn the tree from a lookup into a search:

```cpp
r.insert("/documents/count", 1);
r.insert("/documents/:id",   2);   // ":id" matches one segment
r.insert("/static/*path",    3);   // "*path" matches the rest
```

A `:name` param matches any one segment; a `*name` catch-all swallows the remainder. Now `/documents/count` is ambiguous: it matches the static `count` *and* the param `:id`. The router has to prefer the more specific one, which means that when a promising branch dead-ends deeper down, it cannot just fail. It has to **back up** to the last fork where a param or catch-all was waiting and try that instead. A trie became a maze with forks, and matching is a walk that sometimes has to retrace its steps.

Backtracking is exactly where routers get dangerous, because naive backtracking is exponential. Stack enough overlapping `:param` and static segments and a single crafted path can make the matcher explore a combinatorial number of dead ends, the routing equivalent of catastrophic regex backtracking, a denial of service delivered as one innocent-looking URL. The whole trick of a serious router is to keep the backtracking **bounded**: explore the param and catch-all alternatives at each fork in a fixed order, never re-descend a subtree you have already ruled out, and let the worst case stay a function of the path's depth, not of how cleverly an attacker overlapped your routes. That is the property behind the flat `miss` column in the table above. A miss is fast *and* a miss is safe.

## Where it fits

Reach for it wherever you match one input against many patterns and the count of patterns is going to grow: an HTTP server, obviously, but also a command dispatcher, a permission matcher, any `/`-separated namespace. Captured `:id` and `*path` values come back through a `Params` object as string views, no copies, so the match does not allocate. It is header C++, one type, and it does the one thing a router must never get wrong: it stays flat, and it stays bounded, no matter what you throw at it.

The next familiar leaves the server's front door for something much older and much larger. It takes the whole surface of the Earth and turns it into search terms a plain text index can answer, by tiling the planet in triangles.
