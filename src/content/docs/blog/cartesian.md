---
title: "The Earth Is Not a Ball"
subtitle: "Turning latitude and longitude into vectors you can do geometry on, on an Earth that is lumpier than a sphere."
description: "cartesian converts geodetic coordinates (latitude, longitude, ellipsoid height on some SRID) to and from geocentric Cartesian x/y/z vectors on the WGS84 ellipsoid, and adds the vector algebra (dot, cross, norm, normalize, angular distance) you need on those points. It converts between datums along the way with a 7-parameter Helmert transform, ships seventeen SRIDs with their ellipsoid parameters, and is the sibling library the HTM mesh runs on. The point is that doing geometry on the Earth means first turning surface coordinates into vectors, and doing it honestly means accounting for an Earth that is an ellipsoid, not a sphere, and for the different reference datums the world's maps were drawn on."
excerpt: "Latitude and longitude are angles on a curved surface, and you cannot take the dot product of two angles. To do real geometry on the Earth, measure an angle between two cities, feed a region to a spatial index, you first turn each point into a vector in space. The twentieth familiar does that conversion, honestly, across an Earth that is neither round nor drawn on a single map."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 20
tags:
  - familiars
  - cpp
  - geospatial
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is the ground the [mesh](/blog/htm/) stands on: [cartesian](https://github.com/Kronuz/cartesian).*

Latitude and longitude feel like coordinates, but they are angles on a curved surface, and you cannot do vector math on angles. You cannot dot two latitudes, or take a meaningful cross product of two longitudes, or measure the angle between two cities by subtracting their coordinates. Every real piece of geographic geometry, the angular distance between two points, the plane through three of them, feeding a circular region to a [spatial index](/blog/htm/), starts by leaving lat/long behind and turning each point into a genuine 3-D **vector**: its position in space, measured in meters from the center of the Earth. [cartesian](https://github.com/Kronuz/cartesian) is the library that does that crossing, in both directions, and the little algebra you need once you are on the other side.

## Vectors on a planet

The type is `Cartesian`, and it wears two hats. As a **converter**, you hand it a latitude, longitude, and height and it returns the geocentric `(x, y, z)` for that point; `toGeodetic` takes a vector back to lat/long/height, and `toDegMinSec` pretty-prints it. As a **3-vector**, it is exactly what you would want: dot product, cross product, addition and subtraction, `norm`, `normalize`, `inverse`, and an angular `distance` between two surface points. Once your cities are unit vectors, "how far apart are they" is the angle between two vectors, an `acos` of a dot product, and "the boundary of this region" is geometry you can actually compute. This is precisely the vector type the [HTM mesh](/blog/htm/) runs on: the mesh tiles the *unit sphere*, and cartesian is what puts your points onto it.

## The part that makes it honest

The naive version of this conversion pretends the Earth is a sphere, and for rough work that is fine. cartesian does not pretend. It converts on the **WGS84 ellipsoid**, because the Earth is flattened at the poles by about a third of a percent, and treating it as a ball puts you tens of kilometers off in the worst places. That is one source of lumpiness. The other is human: the world's maps were not all drawn against the same reference. A coordinate reference system (an SRID) pins down which ellipsoid and which **datum**, which origin and orientation, the numbers are measured against, and there are many: WGS84, NAD83 and the older NAD27, Britain's OSGB36, Europe's ED50, Tokyo, seventeen of them shipping with their parameters. A latitude in one datum is a *different place* from the same latitude in another, sometimes by hundreds of meters.

So converting a point is not just trigonometry on an ellipsoid; it is also moving between datums, which cartesian does with a **7-parameter Helmert transform**, three translations, three rotations, and a scale, that shifts a coordinate from its source datum into WGS84, the canonical frame everything converts into. It is the unglamorous, essential geodesy that separates a geospatial system that is roughly right from one that is actually right, and it is the reason "put a pin on the map" is a harder sentence than it sounds.

## Where it fits

Reach for it when you need real geometry on Earth coordinates: angular distances, spatial indexing, moving between coordinate reference systems, anything where "close enough for a sphere" is not close enough. Skip it if a flat-Earth approximation over a small area is all you need (planar math on a local projection is simpler and faster), or if a full GIS library already owns your coordinate handling.

The next familiar leaves space for sound. It matches words not by how they are spelled but by how they are said, so that `Smith` and `Schmidt` finally land in the same place.
