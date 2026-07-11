---
title: "Copy on Write"
subtitle: "A dynamic document value that serialises to MessagePack, patches like JSON, and copies for free."
description: "msgpack is Xapiand's batteries-included MessagePack value library: the MsgPack copy-on-write value type with JSON-like map and array access, serialise and unserialise to the compact MessagePack wire format, typed accessors, RapidJSON and string_view adaptors, and an RFC 6902 JSON-Patch helper over the DOM. Its two clever bits are copy-on-write storage, so passing a document by value is a pointer bump until someone mutates it, and a forked msgpack-c exception header that makes the vendored library's exceptions inherit the host's base exception type, so a decode error travels through your own error hierarchy instead of a foreign one."
excerpt: "A search engine passes documents around constantly: parse one, copy it into a request, hand it to a handler, serialise it to disk. If every copy of a document deep-copied the whole tree, that traffic would be pure waste. The sixteenth familiar is the document value that copies for free until you change it, speaks MessagePack on the wire, and patches like JSON in place."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 16
tags:
  - familiars
  - cpp
  - serialization
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is the document itself: [msgpack](https://github.com/Kronuz/msgpack).*

A document-oriented search engine is, underneath, a program that moves documents around all day. It parses one from a request, copies it into an internal object, hands it to a handler, mutates a field, serialises it to the store, sends it across the cluster. If a "document" were a plain tree of maps and arrays that deep-copied itself every time it crossed a function boundary, all of that movement would be copying, most of it needless, because the vast majority of those copies are read and then dropped without a single change.

[msgpack](https://github.com/Kronuz/msgpack) is the value type that carries documents without paying that tax. It is a batteries-included MessagePack library built around `MsgPack`, a dynamic value with JSON-like map and array access, typed accessors, serialise and unserialise to the compact MessagePack wire format, and an RFC 6902 JSON-Patch helper. You use it the way you would use a JSON value in a scripting language, except it is C++ and it is fast:

```cpp
MsgPack doc = { { "name", "Neo" }, { "tags", { "chosen" } } };
doc["tags"].push_back("operator");
std::string wire = doc.serialise();          // compact MessagePack bytes
MsgPack copy = MsgPack::unserialise(wire);
```

## Copy for free until you don't

The `MsgPack` storage is **copy-on-write**. Copying a document does not copy the tree; it bumps a reference to the same shared representation, and only when someone actually mutates a shared value does it quietly clone the part being changed. So passing a document by value, the natural, safe C++ style, costs a pointer operation, not a deep copy, and the deep copy only ever happens for the documents you truly modify, which are the minority. It is the same trick that made copying a string cheap in older standard libraries, applied to a whole document DOM, and in a system whose entire job is shuffling documents from parser to index to wire, it is the difference between "copy freely" being idiomatic and being a performance bug.

## The exception that travels with it

There is a smaller, sharper piece worth pointing at, because it is the kind of thing you only learn by vendoring a library into a bigger one. msgpack bundles the Xapiand fork of `msgpack-c` v1.3.0, and the fork is almost nothing: it makes the msgpack library's own exceptions inherit the host's `BaseException`. That sounds trivial until you have lived without it. A decode error thrown from deep inside a third-party parser normally arrives as *its* exception type, foreign to your codebase, sliding past every `catch` you wrote for your own error hierarchy, formatting its message its own way, carrying none of your context. Reparenting the vendored library's exception base onto yours means a malformed-MessagePack error travels through the same error machinery as everything else you throw, gets described and logged the same way, and is caught where you expect. It is a one-line change to a header that has to travel *with* the library forever, and it is the sort of seam that makes a vendored dependency feel native instead of bolted on.

## Where it fits

Reach for it when you want a dynamic, JSON-shaped value in C++ that serialises small (MessagePack is denser than JSON), copies cheaply, and supports in-place JSON-Patch. It ships the RapidJSON and `string_view` adaptors and pulls a handful of sibling familiars for its plumbing. Skip it if your data is statically typed and known at compile time (a struct and a codegen serializer will beat a dynamic DOM), or if you need a schema-validated format rather than a schemaless one.

The next familiar moves those documents in bulk. It floats a whole database downstream over a wire, compressed and integrity-checked, without ever holding the file in memory.
