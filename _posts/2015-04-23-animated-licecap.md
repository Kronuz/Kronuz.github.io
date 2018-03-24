---
title:      Animated LICEcap GIFs, the Hard Way
date:       2015-04-23 14:00:00 -0600
modified:   2015-04-23 14:00:00 -0600
categories: Interesting
author:     Kronuz
tags:       screencast, licecap, animated gifs
identifier: animated-licecap-gifs-the-hard-way
redirect_from:
	- /animated-licecap-gifs-the-hard-way
	- /animated-licecap-gifs-the-hard-way.html
---

LICEcap can record the screen to LCF which can then be converted to animated
GIFs, the hard way.

It was some time ago when I first saw how Jon Skinner had created some
really nice looking and sleek simple screencast on the Sublime Text page
as introduction to the magnificent editor, I loved it. I contacted Jon,
whom kindly shared with me the Python and Javascript code he had used to
create it. He told me not to write anything until he had published about
it, and I promised not to. It was months before he decided to write a
blog post about it, which he called [Animated GIFs the Hard Way]

Animated GIFs are limited in the sense they can only be 256 colors, but
with Jon\'s method all that was missing was a simpler way for recording
the screen. He provided the `capture.py` script, but it captured the
whole screen and at constant intervals of time, still it was very handy.

Recently I found out about [LICEcap](http://www.cockos.com/licecap/), a
pretty neat and useful tool to capture an area of the screen and save it
directly to .GIF, but *also* to its own native lossless proprietary file
format: `.LCF`. The proprietary format keeps the recorded screencast
compressed in full color, I just needed a way to extract those and use
Jon\'s `anim_encoder` to package those to a single PNG file and its
corresponding Javascript so I started a fork of Jon\'s
[anim\_encoder](https://github.com/sublimehq/anim_encoder) and went
about adding LCF file format support to it.

My GitHub [fork](https://github.com/Kronuz/anim_encoder) contains the
`.LCF` reader and processor and accepts LICEcap LCF files to produce the
packaged files. The following is an example produced by running
`./anim_encoder.py example.lcf`:

<div id="anim_fallback" class="anim_target"><canvas id="anim_target" class="anim_target"></canvas></div>
<script src="/assets/anim.js"></script>
<script src="/assets/example_anim.js"></script>
<script>
  set_animation("/assets/example_packed.png", example_timeline, 'anim_target',
  'anim_fallback');
</script>

[Animated GIFs the Hard Way]: http://www.sublimetext.com/~jps/animated_gifs_the_hard_way.html
