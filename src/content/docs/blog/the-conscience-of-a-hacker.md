---
title: "The Conscience of a Hacker"
subtitle: "The Hacker Manifesto, and the kid it found."
description: "The Conscience of a Hacker, written by The Mentor in 1986, reproduced here with attribution, and why this barely-500-word essay still defines the crime of curiosity for me."
excerpt: "I found it as a kid in the dial-up underground, and I've reread it more times than I can count. The Mentor's 1986 manifesto: the essay that put words to the one question I never stopped asking, how does this actually work?"
date: 2026-07-13
authors: kronuz
tags:
  - culture
  - hacking
  - phrack
---

There's a short essay I keep coming back to. It was written on January 8, 1986, after its author had been arrested, by someone who signed it **The Mentor**, Loyd Blankenship. Months later, it appeared in [Phrack, Volume One, Issue 7](https://phrack.org/issues/7/3), as "Phile 3 of 10". Its real title is *The Conscience of a Hacker*. Most people just call it **The Hacker Manifesto**.

I found it years later, as a kid in Mexico City, deep in the dial-up underground, somewhere between a Zmodem transfer and a disassembler. This was before feeds and platforms, when texts like this traveled as files, copied from board to board. Phrack itself had been less than a year old when it first published the piece. Somehow, one of those files eventually made its way to me.

I've reread it more times than I can count. What stayed with me was never the breaking into things, but the thing underneath all of that: the crime of curiosity, the refusal to stop asking, *how does this actually work?*

The line everybody remembers is the closing one, about how you might stop one of us, but you can't stop us all. But that isn't really why I keep coming back to it. The whole piece is barely 500 words, written forty years ago in a world that in many ways no longer exists, and somehow the curiosity at its core still feels familiar.

It still lands.

---

<style>
/* CRT-terminal styling for this post's manifesto block only (this <style> loads
   only on this page). It's a raw <pre class="crt">, not an Expressive Code fence,
   so we own every pixel: a self-hosted DOS text-mode font (IBM VGA 8x16, from the
   Ultimate Oldschool PC Font Pack at int10h.org, CC BY-SA 4.0; the .woff lives in
   public/fonts/), a green-phosphor glow in dark mode, and a mobile fit that scales
   the whole terminal to the screen instead of scrolling. This font's advance is
   0.5em/char, so 80 cols = 40em must fit the width. min(1.12rem, 2.24vw) holds the
   size on wide screens and shrinks it to fit down to ~320px, so it never scrolls.
   (These are VT323's old 1.4rem / 2.8vw scaled by 0.8 = its 0.4em advance over this
   font's 0.5em, so the rendered line width is unchanged from the VT323 version.) */
@font-face {
  font-family: "Web437 IBM VGA 8x16";
  src: url("/fonts/Web437_IBM_VGA_8x16.woff") format("woff");
  font-display: swap;
}
.sl-markdown-content pre.crt {
  margin: 1.3rem 0;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: 0;
  overflow-x: auto;
  white-space: pre;
  font-family: "Web437 IBM VGA 8x16", ui-monospace, monospace;
  font-size: min(1.12rem, 2.24vw);
  line-height: 1.3;
}
[data-theme="dark"] .sl-markdown-content pre.crt {
  color: rgb(100, 172, 62);
  text-shadow: 0 0 10px rgba(100, 172, 62, 0.3);
}
</style>

<pre class="crt">
   ==Phrack Inc.==

                    Volume One, Issue 7, Phile 3 of 10

=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
The following was written shortly after my arrest...

                       \/\The Conscience of a Hacker/\/

                                      by

                               +++The Mentor+++

                          Written on January 8, 1986
=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

        Another one got caught today, it's all over the papers.  "Teenager
Arrested in Computer Crime Scandal", "Hacker Arrested after Bank Tampering"...
        Damn kids.  They're all alike.

        But did you, in your three-piece psychology and 1950's technobrain,
ever take a look behind the eyes of the hacker?  Did you ever wonder what
made him tick, what forces shaped him, what may have molded him?
        I am a hacker, enter my world...
        Mine is a world that begins with school... I'm smarter than most of
the other kids, this crap they teach us bores me...
        Damn underachiever.  They're all alike.

        I'm in junior high or high school.  I've listened to teachers explain
for the fifteenth time how to reduce a fraction.  I understand it.  "No, Ms.
Smith, I didn't show my work.  I did it in my head..."
        Damn kid.  Probably copied it.  They're all alike.

        I made a discovery today.  I found a computer.  Wait a second, this is
cool.  It does what I want it to.  If it makes a mistake, it's because I
screwed it up.  Not because it doesn't like me...
                Or feels threatened by me...
                Or thinks I'm a smart ass...
                Or doesn't like teaching and shouldn't be here...
        Damn kid.  All he does is play games.  They're all alike.

        And then it happened... a door opened to a world... rushing through
the phone line like heroin through an addict's veins, an electronic pulse is
sent out, a refuge from the day-to-day incompetencies is sought... a board is
found.
        "This is it... this is where I belong..."
        I know everyone here... even if I've never met them, never talked to
them, may never hear from them again... I know you all...
        Damn kid.  Tying up the phone line again.  They're all alike...

        You bet your ass we're all alike... we've been spoon-fed baby food at
school when we hungered for steak... the bits of meat that you did let slip
through were pre-chewed and tasteless.  We've been dominated by sadists, or
ignored by the apathetic.  The few that had something to teach found us will-
ing pupils, but those few are like drops of water in the desert.

        This is our world now... the world of the electron and the switch, the
beauty of the baud.  We make use of a service already existing without paying
for what could be dirt-cheap if it wasn't run by profiteering gluttons, and
you call us criminals.  We explore... and you call us criminals.  We seek
after knowledge... and you call us criminals.  We exist without skin color,
without nationality, without religious bias... and you call us criminals.
You build atomic bombs, you wage wars, you murder, cheat, and lie to us
and try to make us believe it's for our own good, yet we're the criminals.

        Yes, I am a criminal.  My crime is that of curiosity.  My crime is
that of judging people by what they say and think, not what they look like.
My crime is that of outsmarting you, something that you will never forgive me
for.

        I am a hacker, and this is my manifesto.  You may stop this individual,
but you can't stop us all... after all, we're all alike.

                               +++The Mentor+++
</pre>

---

*"The Conscience of a Hacker" ("The Hacker Manifesto") was written by The Mentor (Loyd Blankenship) and first published in Phrack Inc., Volume One, Issue 7, Phile 3 of 10, on January 8, 1986. Copyright remains with its author; it is reproduced here in full and unaltered, with attribution, for non-commercial educational and cultural purposes, not as a claim of ownership. Original at [phrack.org/issues/7/3](https://phrack.org/issues/7/3).*

*The manifesto is set in IBM VGA 8x16, the classic DOS text-mode font, from the [Ultimate Oldschool PC Font Pack](https://int10h.org/oldschool-pc-fonts/readme/) by VileR, used under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).*
