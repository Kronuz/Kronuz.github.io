---
title: "The Planet as a Prefix"
subtitle: "Turning the whole Earth into search terms a plain text index can answer."
description: "htm implements the Hierarchical Triangular Mesh: it tiles the sphere with nested triangles, gives every point a name and a 64-bit id, and makes nearby points share a name prefix so the name doubles as a spatial key. That is what lets a text search engine answer 'within 5 km of here' with no spatial database bolted on: you range a query region into a set of trixels or id intervals and hand them to the index as terms. Triangles instead of a lat/long grid because a grid melts at the poles, and the hard part is the ranging."
excerpt: "'Find documents within 5 km of here' is not a text query, and you cannot scan your way to it. The trick Xapiand uses is to turn the surface of the Earth into a hierarchy of triangles, give every point a name whose prefix is its neighborhood, and let the text index do the rest. The fifth familiar tiles a planet so a search engine that only knows words can answer questions about space."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 5
chapter: "Space"
tags:
  - familiars
  - cpp
  - geospatial
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is the largest single idea in the pile: [htm](https://github.com/Kronuz/htm), the mesh that let a text search engine answer questions about space.*

"Find me documents within five kilometers of here" is not a text query. A search index is superb at one thing, *which documents contain this term*, and a distance is not a term. You could bolt a separate spatial database onto the side, run two systems, and join them. Or you could find a way to turn *where* into *what*, a place into a word the index already knows how to match. That second path is the [Hierarchical Triangular Mesh](https://github.com/Kronuz/htm), and it is the most quietly clever thing in the whole engine.

## A name whose prefix is a neighborhood

Start with the sphere and tile it, not with a latitude/longitude grid, but with triangles. Project an octahedron onto the sphere to get eight spherical triangles, then recursively split each one into four smaller triangles, again and again, as deep as you want resolution. Each of these **trixels** gets a name: a root, `N` or `S`, followed by one digit `0`, `1`, `2`, `3` for each level of subdivision you descended. `N01230...` is a specific triangle a few levels down, and the triangle one level shallower is just `N0123`, its name with the last digit trimmed.

That naming is the entire trick, because it makes the name a **spatial key**. Two points that are close on the sphere fall into the same triangle for many levels before they split apart, so they share a long name prefix. Trim digits off a name and you zoom out to the trixel that contains it. And because the mesh is nested, a trixel's 64-bit id covers a contiguous *range* of ids: its whole subtree, every point inside it, is one `[start, end]` interval. A neighborhood is a prefix. A region is a set of ranges.

Now the search engine's own machinery does the geometry for free. Index each point under its trixel id. To answer "within five kilometers of here," you turn that circle into the set of trixels that cover it and hand their id ranges to the index as ordinary term ranges, the same range query it would run on a date or a price. No spatial join, no second database. The text index answers a question about space because you taught space to spell.

## Why triangles, and not a grid

The obvious tiling is a lat/long grid, and it is a trap. Lines of longitude converge at the poles, so grid cells shrink to slivers up north and balloon at the equator: the cells are wildly unequal in area, and the math degenerates exactly where the Earth is least forgiving. A recursively subdivided triangular mesh has none of that. Every trixel splits into four roughly-equal children the same way everywhere on the sphere, poles included, so resolution is even and the geometry never hits a singularity. The shape of the tiling is doing real work; a triangle is the piece that tiles a ball without lying about the poles.

## The hard part is the ranging

Naming a point is easy. The work is going the other way: given a query region, produce the *minimal* set of trixels that cover it. htm builds that on a `Constraint`, a spherical cap, a circular area cut off the sphere by a plane, and ranges a region by a recursive descent of the mesh. At each trixel it asks one of three questions: is this triangle **entirely inside** the region (emit its whole id range and stop, you have covered a huge area with one interval), **entirely outside** (drop it, and its whole subtree with it), or **partial** (recurse into its four children and decide again). Fully-inside and fully-outside are what keep the answer small; you only pay resolution along the *boundary* of the region, not its area. The set algebra on top, `trixel_union`, `trixel_intersection`, and their range equivalents, lets you build a polygon or an EWKT geometry out of caps and combine them into one term set.

That is the piece that let a *text* engine answer real geo queries, circles, polygons, arbitrary geometries, without a spatial index sitting beside it. It ships as two compiled units and leans on one sibling familiar, [cartesian](https://github.com/Kronuz/cartesian), for turning latitude and longitude into the unit-sphere vectors the mesh runs on.

The next familiar goes the opposite direction from a whole planet. It is a single number with no ceiling at all, and the one operation on it that nearly everyone gets wrong.
