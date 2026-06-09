---
title: "The Boy Who Kept Opening the Box"
subtitle: "A life measured in machines, from a borrowed Commodore 64 in Mexico City to the heart of Python itself."
description: "The full arc: a C64 in 1980s Mexico City, a digital ouija written in C, a modem worth months of waiting, the forbidden pleasures of assembly and SoftICE, a game engine Nintendo noticed, five servers named after a Forrest Gump memory, and an idea about laziness that rippled across Instagram and landed in the Python language."
excerpt: "I have spent my whole life opening boxes I was not supposed to open. This is the story of all of them, from a borrowed Commodore 64 to a feature in the Python language, and the same restless kid behind each one."
date: 2026-06-07
draft: true
authors: kronuz
tags:
  - life
  - story
  - retrocomputing
---

I have spent my whole life opening boxes I was not supposed to open.

That is the most honest summary I can give you. Not opening them in the careful, sanctioned way, with a manual and a warranty card, but the other way: prying at the seam until something inside gives, finding out how it works, and usually breaking it at least once on the way to understanding. The boxes got bigger over the years. A home computer. A modem. A game console's good name. A database. Eventually the Python language itself. But the boy doing the prying never really changed.

This is the story of the boxes.

## A borrowed machine

It starts, as these things often do, with a machine that was not mine.

My cousin **Victor** had a **Commodore 64**, and in the chaotic glow of late-1980s Mexico City, that beige wedge of plastic was the most interesting object I had ever been near. I was a kid. I would hunch over it, fingers awkward on the stiff keys, trying to convince a blinking cursor to do my bidding. The cursor did not care about me. That, somehow, made me care more.

Victor taught me C. Not all of it, nobody learns all of C, but enough to be dangerous, and together we built the first thing I was ever genuinely proud of: a **"digital ouija."** It was a small program, a little parlor trick written in C, that made answers appear on the screen as if from nowhere. We would sit our friends down in front of it and watch their faces do the thing faces do when reality wobbles. They were unsettled. We were delighted. I had made a machine do something that felt, for a moment, like magic, and I have been chasing that exact feeling ever since.

The first machine that was actually **mine** arrived a few years later, and I remember the exact shape of the moment. It was a **cold winter night** in Mexico City, the family waiting in the car while my dad went to collect something he had not explained. He came back carrying **two big boxes**. *"It's a computer,"* he said, as plainly as if he were saying *it's groceries*. I was **twelve**. I had seen computers in movies and on television, but I could not believe one of those strange, almost magical things was about to be in my house, mine to take apart. That fawn-colored box spoke in **small bright green letters**, a **Hercules** monitor, glowing phosphor on black, driven by an **8088**, the **XT**-class machine I still remember by name, which we later upgraded to an **8086**. Green on black was simply what a computer looked like, to me, for years. That box is, I think, the literal first box of this whole story. I have been opening it, in one form or another, ever since.

And it was not only computers. The years from about **1990 to 1994** were, for me, a fever of game consoles. I wanted all of them and got to know most of them: the woodgrain-and-toggle **Atari 2600**, the **NES**, the **Genesis**, the **Game Boy** I could finally carry in a pocket. But the one I truly loved, the one that felt like the future arriving early, was the **SNES**. Those sixteen-bit colors, that sound chip, the way a cartridge seated with a click like a small promise. I did not yet know I would spend years of my life trying to build worlds half as good as the ones I was playing on it. The wanting started there, controller in hand.

I should mention I was also drawing constantly in those years. Painting, sketching. I was not bad. I was also not great, and I knew it, but the hours I spent looking hard at things and trying to get them down on paper turned out to matter later, in a way I could not have predicted. The eye you train drawing a tree is the same eye you later use to place a sprite one pixel to the left because it just looks *wrong* there. The hand learns. It does not care what it is holding.

## The fellowship and the modem

In 1991 my family sent me to spend a year in **Gaeta**, a small Italian town wedged between Naples and Rome, living with my aunt, uncle, and two little cousins. It was a strange and wonderful year for a lot of reasons, and one of the smaller ones still makes me smile: it was the first time I ever sat in front of a computer with a **color monitor**. At home, mine still glowed in that single shade of Hercules green, so seeing a machine speak in actual colors felt like switching from black-and-white dreams into Technicolor. But here is the reason that truly changed me: I watched the 1978 animated **Lord of the Rings**, the strange, rotoscoped Bakshi version, all shadows and feverish color, and something in me opened like a door.

Fantasy. Worlds with their own rules, their own maps, their own history sitting just off the edge of the frame. I did not know yet that I would spend years of my life building exactly that, a world with an editor and a scripting language and hand-placed tiles. I just knew I wanted *in*.

Back home, the obsession found its medium: the modem. If you are young enough that "modem" is an abstraction, let me set the scene. For a long stretch we did not even have a **telephone line** at home, which is its own particular torture when the entire world is discovering the internet at once. I watched friends reach in and pull down information I simply could not get to, and I have never in my life enjoyed being left behind. So I waited. I waited **months**, actual months, first for the line and then for a **14,400 bps modem**. That number, 14.4k, was a promise of the entire world arriving down a phone line one screeching handshake at a time. When it finally came, I dialed into the BBSes of the Mexican scene, places with names like **"Tierras Extrañas,"** **Coyoacán BBS**, and **Tornado BBS**. I traded files over Xmodem, Ymodem, Zmodem, watching the transfer counter tick upward like a slow ritual. There was **ANSI art**. There were online games. There were **zines**, electronic magazines passed hand to hand, full of things nobody was supposed to know. The wait for that modem taught me something I have never unlearned: desire can be measured in time, and the things worth wanting usually make you wait.

In 1994 we left Mexico City for **Morelia**, in Michoacán. New city, same kid, bigger boxes to open.

## The things meant never to be found

High school is where I found Assembly, and Assembly is where I found the forbidden.

I want to be careful how I say this, because it is the part of my story most easily misunderstood. I was a teenager who fell completely in love with the layer of the machine you are not supposed to touch. I learned to read **disassembly**. I learned **INT 21h** and the **Ralf Brown Interrupt List**, that legendary, encyclopedic catalog of every undocumented call the hardware would answer if you only knew how to ask. I learned **polymorphic code**, programs that rewrite themselves so they never look the same twice. I wrote **virii**, in the way that a certain kind of curious kid in the '90s wrote virii: not to hurt anyone, but because a self-replicating program is the most astonishing toy a teenager can imagine, a little machine that makes copies of its own cleverness.

And I spent glorious nights inside **SoftICE**, the kernel-mode debugger, single-stepping through live code while the whole operating system held its breath. There is no feeling quite like it. You freeze the world, and then you walk through it one instruction at a time, watching registers flip, seeing the secret actually happen. It was, and I mean this without any irony, *really fun*.

My credo from those years has not changed: **the most interesting things are the ones that were meant never to be found.**

The best illustration of what kind of teenager that made me involves, of course, Victor again, and a cable modem. Cable internet was new and astonishing, and somewhere in it was a configuration that capped your speed. So I uncapped it. I uncapped Victor's modem to its full, unthrottled speed, and we did something that was simply not possible on home internet in the mid-'90s: we downloaded multiple videos and watched them, in real time, as they arrived. It felt like cheating physics.

It also got us caught, in the most teenage way imaginable. The ISP noticed, suspended the service, and we, geniuses that we were, **called to complain that our internet was out**. A technician came to Victor's house. He did not yell. He just explained, with the tired patience of a man who has met our type before, that next time there would be legal action. A warning. Two kids who had pushed on the seam of something and felt it give. I am not proud of the trouble, exactly, but I am not sorry I knew how.

## Proof they did not believe

I studied **Systems Engineering** at the **Instituto Tecnológico de Morelia**, from 1997 to 2000, and I spent most of it quietly overshooting the assignment.

There was an **adventure game** I built that was apparently so far beyond the curriculum that the faculty did not believe a student had made it, and I spent the better part of a semester demonstrating it before they accepted it was mine. There was a working **sound card** I wired up through the **parallel port**, coaxing audio out of a connector that was never meant to carry it. There was a visualization of the **Dining Philosophers** problem, that classic of computer-science deadlock, except I rendered the philosophers in **3D Studio Max** because if you are going to explain concurrency you might as well make it beautiful. And there was an **emulator for the Motorola 6802** microprocessor I wrote in C, with a built-in assembler and step-by-step tracing, that the school liked enough to adopt as a teaching tool. For years afterward it taught computer architecture to more than a thousand students who had no idea the courseware had been written by one of their own.

The drawing hand and the debugging hand, finally working together.

## Time is of the essence

Around this time I fell in with the emulation people, the wonderful obsessives at **VOGONS** who keep old games playable forever, and I started contributing to **DOSBox**.

My first real patch is still there, posted in November 2005, and I am a little proud of it. The scalers, the routines that blow up a tiny old game to fit a modern screen, were redrawing the entire picture every frame. I changed them to redraw only the parts that had actually changed. The benchmarks were almost comical. The simplest scaler got **90% faster**. The fanciest one, **Hq2x**, got faster by something like **9,500%**. I signed my posts on that forum with a line I had adopted as a kind of motto: *"Time is of the essence."* I had no idea, at the age I wrote that, how much my whole career would turn out to be about exactly that, about not wasting work, about not doing a thing until the moment you truly have to.

I also, finally, built the fantasy world. **Open Zelda** was an open-source 2D game engine, a tool for making top-down action-RPGs, with a real world editor and a scripting language so you could give your creatures behavior from a plain text file. I poured the drawing kid and the assembly kid and the Bakshi-struck kid all into it at once.

And then I got a letter. **Nintendo**, it turns out, has opinions about the word "Zelda." A cease-and-desist arrived, polite and immovable, and I learned my hobby project had grown big enough to appear on the radar of one of the most protective brands on earth. I was annoyed. I was also, secretly, a little thrilled. I renamed it **Open Legends** and kept going. The work was never about the name.

## Five servers named Jenny

The 2000s were my entrepreneurial decade, and they were gloriously, instructively naive.

My first company wanted to **compete with Amazon**. Read that again and enjoy it as much as I now do. We were going to take on Amazon. We were children with a database.

Then came **Deipi**, which I built with my partner **Omar**, and Deipi is where I learned what running real infrastructure feels like in your stomach. We bought **five servers** and colocated them in a facility in **San Diego**. We named them **Jenny 1 through 5**, after a dumb, fond memory of Jenny from *Forrest Gump*, and I ran them on **FreeBSD**, because I have always had a stubborn, unfashionable distaste for Linux and FreeBSD felt like the operating system of people who actually wanted to understand their machine. Five servers with a silly name, humming in a room in another country, that I was personally responsible for keeping alive. That will teach you things a textbook cannot.

In and around the companies, I was shipping open source constantly, and some of it quietly went further than I ever expected:

- I wrote **BestLyrics**, a **Winamp plugin** that watched whatever mp3 you were playing and went and found its lyrics for you, automatically. It scraped them from a dozen different lyrics sites, it was scriptable so you could teach it new ones, it stripped out the ads and the formatting junk, and it cached what it found so it never had to do the same work twice. It was one of the first things of its kind. It had its own name and its own website. I was a teenager building a real, branded little product before I had any idea that was what I was doing, which, looking back, was the whole pattern of my life showing up early.
- I wrote **pyScss**, a Sass compiler in pure Python, because the web needed one and I wanted it to exist. It found hundreds of stars and a real user base.
- I created **SublimeCodeIntel**, code intelligence and autocomplete for the Sublime Text editor, in 2011. I eventually handed it to a community organization to look after, and it now sits at over **five thousand** stars. People I will never meet have used it every day for years.
- I did the same thing a second time, almost as a reflex. There was a rough little linting script that Ryan Hileman had started; I forked it, refactored it into a proper extensible, multi-language framework, and gave it the name it still carries today: **SublimeLinter**. I named it, I shaped it, and for the whole Sublime Text 2 era my fork was the one everyone else built on top of. It is still installed by an enormous number of developers, most of whom have no idea a kid from Morelia chose those letters.
- I wrote a PostgreSQL extension called **isn**, for international standard numbers, ISBNs and ISSNs and the barcodes on the back of every book and magazine. It was merged into PostgreSQL itself in 2006. If you open the official PostgreSQL documentation today, in any version from 2006 to now, the `isn` page still says, at the bottom: **"Germán Méndez Bravo (Kronuz), 2004–2006."** My name, sitting quietly inside one of the most important databases in the world, for going on twenty years.
- I found and fixed a bug deep in **Django**'s deletion machinery, the part that figures out what else to delete when you delete one thing, which had been quietly corrupting data for anyone using polymorphic models.

Then there was **Dubalu**, where I served as **CTO**. Dubalu was supposed to be a social network organized around **"circles,"** the idea that you do not share everything with everyone, that your life has groups and you want to post to one without the others. We built this. And then **Google+** launched circles to the entire world and made it look like their idea. There is a particular ache to being early, to holding a thing in your hands a year before it has a name everyone knows. But Dubalu gave me **Xapiand**, a distributed search and storage engine I wrote in modern C++, async to the core, and that engine taught me more about systems at scale than anything before it.

## A new country, and then the world closed

In **late 2019**, Facebook called.

In **February 2020**, I moved my family, my wife and our **five-month-old daughter**, to **Menlo Park, California**. New country, new job, new baby, all at once. It was terrifying and it was wonderful.

About two months later, the world closed. **COVID** locked us down in a place we barely knew, a long way from everyone we loved, with an infant and a lot of fear. I do not want to be glib about that time. It was hard in ways that had nothing to do with code.

But code is where I went. I landed in **Instagram Server DevInfra**, and I spent a lot of long, strange, locked-down nights on oncall, staring at one number that bothered me more than it should have: the server took about **twenty-five seconds** to start, sometimes a minute and a half, and almost all of that time was spent doing nothing but **importing modules**. Twenty-eight thousand of them. Creating function objects and class objects for code that, on any given run, mostly would not even be called.

It offended me. All that work, done eagerly, up front, in case. And the old credo came back, the one from the DOSBox scalers, the one about not doing a thing until the moment you truly must.

## Lazy is the new fast

What I wanted was for Python to be **lazy**. To not import a thing until you actually reached for it.

I rolled up my sleeves and dove into **CPython**, into **Cinder**, Meta's performance fork, and I started building it. My first attempt leaked the lazy objects out into places they should never have been, and after some very good conversations with Carl Meyer and Dino Viehland I made the brave, slightly insane decision to move the whole mechanism down into the most sacred and dangerous part of the language: the **dictionary internals**, the data structure Python uses for almost everything. Touch that wrong and you slow down the entire world. I touched it very, very carefully.

It worked. By loading roughly **twelve times fewer modules**, we cut server reload time by about **70%** at the median. Memory dropped by **twenty to forty percent**. A specific, maddening class of bug, circular import errors, went from about **eighty a day to zero**. Later, on Meta's machine-learning workloads, the same idea cut the time to the first batch of training by **up to 40%**. Seconds and minutes, given back, multiplied across one of the largest fleets of computers on the planet. My performance review that year had a name I will not pretend I did not enjoy: **"Redefined Expectations."**

I wanted to give the idea to everyone, so I wrote it up as **PEP 690** and proposed it to the Python language itself.

The Python Steering Council said **no**.

I will not pretend that did not sting. They had a real reason, an honest one: my proposal made laziness a global switch, and they worried it would split the world into two Pythons, one eager and one lazy, where every library had to be tested in both. *"A world in which Python only supported imports behaving in a lazy manner would likely be great,"* they wrote. *"But we cannot rewrite history and make that happen."* Rejected, December 2022.

That is usually where a story like this ends. It is not where this one ends.

## The second try

We moved to **Folsom**. I left Meta and joined **LinkedIn**, where I am a **Staff Software Engineer** working on Python infrastructure, still pointed at the same restless question: how do you make these enormous systems pay for less than they ask for.

And the lazy imports idea would not die. The Steering Council had not rejected the *idea*, they had rejected the *global switch*. So with a group of brilliant people, led by core developer Pablo Galindo Salgado, we did it again, properly this time. Instead of a switch that makes everything lazy, an explicit word you write yourself:

```python
lazy import json
lazy from json import dumps
```

You opt in, one import at a time, in the open, where everyone can see it. No two Pythons. No fragmentation. Just a clear request to defer this particular work until you actually need it.

It became **PEP 810**, and on **November 3, 2025**, the Python Steering Council **accepted** it. It is slated for **Python 3.15**. The idea I had on a locked-down night staring at a server's startup time, the one the language turned down, is now going to be part of the language. It just took knocking twice.

## The same boy

So here I am. From a borrowed Commodore 64 in Mexico City to a keyword in the Python grammar, and if you laid out everything in between it would look like a dozen different careers: a virus-writing teenager, an emulation hobbyist, a failed Amazon-killer, a database contributor, a search-engine author, a CTO, an infrastructure engineer.

But it has only ever been one thing. It has been a kid who could not look at a closed box without wanting to know how it worked, and who was willing to break it to find out, and who got very lucky in that the world turned out to be full of boxes, each one bigger than the last.

The cursor still does not care about me. I still care more because of it.

There are other stories. The ones I left out of this could fill a small book, and maybe one day they will. But this is the shape of it, the throughline, the honest version. A life measured in machines, and the same restless boy at the seam of every one of them, prying, listening for the moment it gives.
