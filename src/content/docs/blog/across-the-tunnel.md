---
title: "The Room Across the Tunnel"
subtitle: "Surviving the trip home"
description: My real work happens on a dev VM, not my laptop, and a normal connection to it dies every time the lid closes. This is why I reach it over EternalTerminal, how I got the client and server running on a Mac and a CBL-Mariner box, and why a session that outlives the connection changes how it feels to work on a machine across a tunnel.
excerpt: The laptop is a window; the VM is the room. The trouble with a room across a tunnel is that the tunnel keeps dropping. EternalTerminal is the fix, a session that survives a closed lid, a changed network, and the ride home, and is exactly where you left it the next morning.
date: 2026-06-28
authors: kronuz
series: "Driving Eternal"
seriesOrder: 1
tags:
  - driving-eternal
  - eternal-terminal
  - infra
  - tooling
---

*Part of the **Driving Eternal** series: giving a script or an AI agent a real handle on a remote terminal. Installing [Eternal Terminal](https://eternalterminal.dev/).*

I do most of my real work on a dev VM, not on the laptop in front of me. The laptop is a window; the VM is the room. Everything heavy lives there: the checkouts, the build caches, the cores, the memory. My machine just looks in on it.

The trouble with a room across a tunnel is that the tunnel keeps dropping. A plain `ssh` session is only alive as long as nothing moves. The laptop sleeps and the session dies. I leave the office and the laptop jumps from wifi to a phone hotspot, and the session dies. The VPN reconnects with a new IP and the session dies. I close the lid to go home and, of course, the session dies, taking whatever I was in the middle of with it. You learn to work in fear of the connection, and that's a bad way to live in a room.

## The usual answers

This is an old problem with good, well-worn answers, and I tried the obvious ones first.

[`screen`](https://www.gnu.org/software/screen/) and [`tmux`](https://github.com/tmux/tmux/wiki) keep the session alive on the *server*: you start one, detach, lose the connection, `ssh` back in, and reattach right where you were. That solves persistence, and it's genuinely useful. But it solves *only* persistence. After a drop I still have to notice it, reconnect, and reattach by hand. And a multiplexer isn't a free layer; it's a whole environment, with a prefix key, a status bar, and a copy-mode that swallows the terminal's own scrollback, so scrolling with the mouse stops working the way it does everywhere else. I reach for tmux when I want what it's actually for, panes and windows and shared sessions. I don't want to wear it just to keep a connection.

[`Mosh`](https://mosh.org/) is the closest thing to what I wanted, and on a genuinely awful link it's still the right call: it roams across networks, survives drops, and its predictive local echo makes high latency feel alive. The catch is what it trades away to do that. Mosh repaints your screen instead of streaming the bytes, so it has no native scrollback at all, and scrolling, true-color, and a few keybindings get mangled along the way. It also runs over UDP, which is wonderful right up until you're on a network that quietly blocks it.

[`autossh`](https://www.harding.motd.ca/autossh/) is the honest hack: restart the `ssh` session automatically when it drops. It works, but every reconnect is a *new* session, so you land at a fresh shell and have to find your place again. It reconnects the pipe, not the conversation.

What I actually wanted was smaller than any of these, and weirdly hard to get: my normal terminal, unchanged, that simply doesn't die.

## The session that doesn't drop

[EternalTerminal](https://eternalterminal.dev/) (`et`) is that. The reason is right there in the name: an `et` session is eternal. It uses `ssh` to handshake, so it rides on the keys and config I already have, and then holds the session on the server over its own TCP connection. The client can vanish and come back, on a new network, a new IP, after a closed lid, and pick the same session right back up. The laptop sleeps, the wifi changes, I walk from a desk to a couch, and the session is still there when I look again.

Better still, because `et` streams the terminal instead of redrawing it, the terminal stays *itself*: native scrollback works, the mouse scrolls like it does everywhere, true-color and copy-paste just behave. It's light in the way that counts. It's a connection, not an environment. It doesn't try to replace tmux either; if I want multiplexing I run tmux on top, and `et` will even keep a `tmux -CC` session intact across a drop. Running over TCP instead of UDP means it gets through the networks that block Mosh. The one thing I give up is Mosh's predictive echo, which I'd want on a truly bad link, but on the connections I actually use, `et` wins by leaving everything else alone.

The part that still feels like a small magic trick is going home. I close the laptop in the office with a build running and a half-typed command sitting at the prompt. I open it the next morning at my desk at home, and there it is: the same shell, the same working directory, the same half-typed command, the build long since finished and waiting for me. Nothing reconnected, nothing re-ran. The session never noticed I left. For a machine you live on all day, that resilience is the whole game.

## Getting it running

`et` is a client and a server, and you need both. On the Mac the client is one Homebrew formula away. I run my own fork of it, the same durable terminal with a machine-driving piece I get to later in the series:

```sh
brew install Kronuz/tap/et      # et (and etctl), at /opt/homebrew/bin/et
```

I built the Eternal Terminal server from source on the VM because the [CBL-Mariner](https://github.com/microsoft/CBL-Mariner) image we use doesn't ship a prebuilt package. The build is unremarkable until the last step, where the firewall reminds you it exists:

```sh
sudo dnf install -y clang cmake ninja-build pkgconf-pkg-config

git clone --recurse-submodules \
  --branch etctl-2-richer-verbs \
  https://github.com/Kronuz/EternalTerminal.git

cmake -S EternalTerminal -B EternalTerminal/build -G Ninja \
  -DDISABLE_TELEMETRY=ON \
  -DBUILD_TESTING=OFF \
  -DCMAKE_C_COMPILER=clang \
  -DCMAKE_CXX_COMPILER=clang++

cmake --build EternalTerminal/build
sudo cmake --install EternalTerminal/build

sudo install -m 644 \
  EternalTerminal/systemctl/et.service \
  /etc/systemd/system/et.service

sudo install -m 644 \
  EternalTerminal/etc/et.cfg \
  /etc/et.cfg

sudo systemctl daemon-reload
sudo systemctl enable --now et.service
```

The one gotcha about the firewall is the VM's `iptables` INPUT chain is default-deny, so the server can be running happily on port 2022 and still be unreachable until you punch the hole and persist it past a reboot.

```sh
sudo iptables -A INPUT -p tcp --dport 2022 -j ACCEPT
sudo sh -c 'iptables-save > /etc/systemd/scripts/ip4save'
```

Both ends end up on `et` 6.2.11. From my terminal it Just Works™️: I type `et kronuz@...`, and a second or two later I'm home, in the room, exactly where I left it.

## The catch I didn't see coming

So the connection problem is solved, for me. The session is durable, the reconnect is invisible, and the machine I live on is always one command away.

The word doing the quiet work in that sentence is ***me***. Everything about this setup, the prompt, the colors, the way `et` hands you a living terminal, is built for a person: for eyes that read a screen and fingers that hit Enter. That's exactly what makes it feel like home. It's also a wall, and I didn't notice the wall until something that wasn't me needed to get into the room. A script. A scheduled job. An AI agent I was pairing with all day. None of them have eyes or fingers, and the eternal terminal I love has nothing else to offer them.

That's the next part of the story: the morning I watched one of those agents stand at that wall, the command in its hand, the host in its head, and no way to knock. What it couldn't do that day taught me something about every door we've ever built.
