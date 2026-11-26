---
title: Detent
tagline: Runtime knobs for every process
description: A C++ runtime-configuration system for feature flags, kill switches and live settings, with process-local reads and durable distribution.
tech: [C++]
logo: /img/projects/detent.svg
repo: https://github.com/Kronuz/Detent
website: https://kronuz.com/Detent/
docs: https://kronuz.com/Detent/welcome/
status: active
featured: true
order: 2
---

A detent is the click-stop that holds a knob at its setting. My Detent gives an
application those knobs at runtime: named integer settings that can also act as feature
flags, kill switches, group overrides and gradual rollouts. A C++ read uses a local
snapshot. It does not wait for a network call, disk access or mutex.

The small version needs only baked defaults or a local file. The managed version adds a
durable authority with three Raft voters, an optional relay, and an agent on each host.
Publish a change as a transaction; the agents deliver a complete, validated generation to
their applications. If delivery stops, readers keep the last good snapshot.

The C++ client, Python and Rust bindings, and shell reader all use the same knob model.
Underneath, Detent pulls in several of my [Familiars](/projects/familiars/), including
`atomic-shared-ptr` for snapshot publication and `consensus` for the authority's Raft core.
The [quick-start](https://kronuz.com/Detent/quickstart/) walks through the first
knob and rollout.
