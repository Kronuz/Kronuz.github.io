---
title: "Keys Stay Home"
subtitle: "Small checks around an offline authority."
description: "pki is an offline C++20 toolkit for generating and checking keys, fingerprints, identities and certificate expiry. It refuses unsafe authority directories and private files; certificate issuance comes later."
excerpt: "An offline certificate authority only stays offline if its private key never drifts onto a cluster node. pki begins with the smaller jobs that make that boundary practical: guarded key files, fingerprints, canonical identities, and expiry checks."
date: 2026-11-22
authors: kronuz
series: "Familiars"
seriesOrder: 40
chapter: "Trust"
tags: [familiars, cpp, security, tls]
---

*Part of [**Familiars**](https://kronuz.github.io/cpp-libraries/), my collection of standalone C++ building blocks. This one is [pki](https://github.com/Kronuz/pki).*

An offline certificate authority has a simple rule: its signing key stays on the operator's host. The nodes generate requests and receive certificates, but they never receive that key. The rule is easy to write on a diagram and easy to erode in practice. A directory is copied into a data root. A key is created with a permissive mode. A passphrase ends up in a command line or an environment variable. An expiring certificate is discovered only when a connection fails.

`pki` begins with the checks around that boundary. It is a C++20 library over [OpenSSL 3](https://www.openssl.org/) with one command entry point, `pki::run`, which a consumer can expose inside its own binary. It currently generates keys, checks authority directories and private files, prints fingerprints, validates identities, and reports certificate expiry. **It does not issue certificates yet.** Signing, an issuance index, rotation, and recovery are [later steps](https://github.com/Kronuz/pki/blob/main/docs/ROADMAP.md). I would rather make the existing boundary honest than put a CA label on an unfinished signer.

## One directory, one authority

The authority directory is opened once. On a POSIX filesystem with local ownership and modes, `pki` checks that the caller owns it and that its mode is `0700`. It reaches children through `openat` on that directory descriptor, with no symlink following. It checks a private file after opening it: regular file, one link, correct owner, and the required mode. The CA key is `0600`; a node key may be `0640` for the caller's effective group. Creation uses exclusive open, sets the mode, syncs the file, and flushes the directory. [The architecture](https://github.com/Kronuz/pki/blob/main/ARCHITECTURE.md) names the checks and the filesystem contract.

Those details are not decoration. A path checked before opening can be swapped before use. A symlink can point outside the guarded directory. A second hard link can make a private file reachable through another name. The descriptor and post-open checks close those particular gaps, and a refusal names the reason instead of pretending the file is safe.

The toolkit also avoids common secret leaks: passphrases come from a terminal or a checked file, not from arguments or the environment; secret buffers are locked and wiped; core dumps are disabled. Generated CA keys use encrypted PKCS#8, with scrypt and AES-256-CBC. The format is readable with OpenSSL's own `pkcs8` command, so recovery does not require the `pki` binary.

## Which key is this?

Two SHA-256 fingerprints answer different questions. A certificate's **SPKI fingerprint** hashes the public-key information, so it stays the same when that key receives a renewed certificate. Its **DER fingerprint** hashes the entire certificate, so a renewal changes it. The distinction prevents a pin meant to follow a key from accidentally pinning one issuance. `pki` prints both, as 64 lowercase hex digits.

Identities use [SPIFFE](https://spiffe.io/) URI form: `spiffe://<cluster>/<consumer>/<node|client>/<name>`. The library canonicalizes the allowed fields so the same identity has one byte representation. For a cluster protocol, that is more useful than accepting several spellings and hoping every peer normalizes them the same way.

Expiry is also a command check rather than a calendar reminder. A certificate is flagged once it has passed five sixths of its lifetime, or when it is within an explicit span such as `--within 30d`. The exit status separates an ordinary check (`0`), a finding (`1`), and a refusal to operate (`2`). That makes a cron job able to alert on approaching expiry without interpreting prose.

## The remaining work

The intended consumers include Xapiand's HTTPS API and [Detent](https://github.com/Kronuz/Detent)'s mutual-TLS peers. Neither integration is complete merely because the library can inspect a key or a certificate. The [roadmap](https://github.com/Kronuz/pki/blob/main/docs/ROADMAP.md) still has the issuance index and signing, rotation and backup, then the consumer commands and adoption.

Today I would use `pki` to generate and guard keys, inspect fingerprints, and check expiry. I would not use it as a certificate issuer. That clear edge is part of keeping the authority where it belongs.
