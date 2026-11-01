---
title: "Who Owns the Tree"
subtitle: "A JSON-shaped MessagePack value whose copies share nothing."
description: "msgpack is Xapiand's MessagePack document value: MsgPack, a JSON-like value with map and array access and typed accessors, kept as msgpack-c objects in an arena of its own, with RapidJSON and string_view adaptors and an RFC 6902 JSON-Patch helper. A reference is a node inside the document, a move hands the arena over, and a copy builds a new arena and copies every node, so a copy shares nothing with its source. Sharing is a separate step: lock() freezes a document so many threads can read it through one shared_ptr, which is how Xapiand shares its schemas and copies one only when a request writes to it."
excerpt: "A search engine moves documents around all day, and in C++ the way you hand one over decides what it costs. The sixteenth familiar is the document value itself, and every document lives in an arena of its own: a reference reaches into it, a move hands it over, and a copy builds a whole new one. When Xapiand needed many threads to share one document, it froze it and shared a pointer instead."
date: 2026-09-09
series: "Familiars"
seriesOrder: 16
chapter: "Bytes"
tags:
  - familiars
  - cpp
  - serialization
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is the document itself: [msgpack](https://github.com/Kronuz/msgpack).*

A document-oriented search engine is, underneath, a program that moves documents around all day. It parses one from a request, hands it to a handler, changes a field, serializes it to the store, and sends it across the cluster. In C++ every one of those hand-offs is a choice between a copy, a reference, and a move, and for a tree of maps and arrays that choice is most of what the hand-off costs.

[msgpack](https://github.com/Kronuz/msgpack) is the document value Xapiand hands around: `MsgPack`, a dynamic value you build from initializer lists and index like a map or an array. It is kept as [MessagePack](https://msgpack.org/) objects from a bundled [msgpack-c](https://github.com/msgpack/msgpack-c) 1.3.0, with [RapidJSON](https://rapidjson.org/) on the JSON side and an [RFC 6902](https://www.rfc-editor.org/rfc/rfc6902) JSON Patch helper on top. Each of the three hand-offs does exactly what its C++ spelling says:

```cpp
MsgPack doc = { { "name", "Neo" }, { "tags", { "chosen" } } };

MsgPack& tags = doc["tags"];           // a reference: the node inside doc
tags.push_back("operator");            // doc changes

MsgPack copy = doc;                    // a copy: a new arena, every node copied
copy["name"] = "Trinity";              // doc does not change

MsgPack moved = std::move(copy);       // a move: the arena changes hands
std::string wire = moved.serialise();  // compact MessagePack bytes
```

## One arena per document

Under the friendly API sits msgpack-c's `msgpack::object`, a small tagged union whose strings, arrays, and maps live in a `msgpack::zone`: an arena that hands out memory by bumping a pointer, and frees all of it at once when it dies. That tree *is* the document. `serialise()` packs it as it stands, with no conversion step in between.

The map-and-array API is an index over that tree, built lazily. The first time you read or change a map, `MsgPack` builds a hash map for it, keyed by `string_view`s into the arena, with a `Body` for each key and each value, and every change writes straight back into the tree. Nested maps you never touch stay raw, so reading a document off the wire and writing it back out never builds the index at all. Every `Body` holds a `shared_ptr` to the document's arena, so the arena lives as long as any of them does. The document owns its tree outright, in one arena.

## A copy is a copy

Open `msgpack.h` and the first data member of the class is a `std::shared_ptr<Body>`, which smells like sharing: copy-on-write, a reference count bumped per copy. It isn't. That pointer is how a move hands a document over in one step. A copy builds a fresh arena and copies every node of the tree into it, strings included, so the copy and its source share nothing and a change to one never shows in the other.

Assignment follows from the references. `doc["name"]` is the node inside `doc`, so `doc["name"] = other` has to write into `doc`'s tree, in `doc`'s arena: it copies `other` in, even when you `std::move` it there (`other` comes out untouched). Only building a new value from a moved one hands the arena over.

None of this is free. msgpack-c starts every arena with an 8 KB chunk, so even a lone `MsgPack(5)` owns one, and a copy of anything pays for a chunk before it copies a single node. The index costs a `Body` allocation for every key and every value of a map, the first time you touch it. A reference costs a lookup, moving into a new value costs a pointer, and a copy costs the whole document.

## The arena only grows

The arena keeps the same discipline as the [storage](/blog/storage/) volumes of the last familiar: it only appends. Nothing in it is freed until the whole document goes. Overwrite a 1 KB field a thousand times and the document still holds every old value, over a megabyte of them. As in any append-only store, getting the space back takes a compaction pass, and here the compaction pass is a copy: copy the document into a new value, which takes only what is live, and drop the old one. `std::swap` trades the two by pointer; `doc = fresh` would copy `fresh` back into the old arena and keep the megabyte.

## Sharing takes a lock

So where does copy-on-write live? One level up, in a pointer you hold yourself.

There is a catch first. Because the index is built on first touch, even a read changes a value's insides, and two threads reading the same unlocked document can race to build the same index. `lock()` settles that: it builds the index of the whole tree, then refuses every write. A locked document can sit behind a `std::shared_ptr<const MsgPack>` and be read by any number of threads.

That is how [Xapiand keeps its schemas](https://github.com/Kronuz/Xapiand/blob/master/src/database/schema.h). Each index's schema is a locked document in a cache that hands the same pointer to every reader. A request that has to change it copies it on its first write, changes the copy, then locks the copy and offers it back to the cache in place of the old one:

```cpp
// Xapiand's Schema, reduced: read the shared document, copy it on the first write.
std::shared_ptr<const MsgPack> schema;  // locked, shared by every reader
std::unique_ptr<MsgPack> mut_schema;    // this request's own copy, once it writes

MsgPack& get_mutable_properties() {
	if (!mut_schema) {
		mut_schema = std::make_unique<MsgPack>(*schema);  // the one deep copy
	}
	return *mut_schema;
}

std::shared_ptr<const MsgPack> get_modified_schema() {
	auto m_schema = std::shared_ptr<const MsgPack>(mut_schema.release());
	m_schema->lock();  // frozen, ready to share
	return m_schema;
}
```

That is copy-on-write, written by hand: the request that writes pays for one copy, and the readers never pay for any.

## The exception that travels with it

There is a smaller seam worth pointing at, the kind you only learn about by vendoring one library into a bigger one. The part of Xapiand's msgpack-c fork that matters here is `msgpack/exception.hpp`. It redefines each msgpack-c exception (`type_error`, `unpack_error`, `parse_error`, the size overflows) to inherit the host's `BaseException` as well as the standard type it had. The header includes `"exception.h"` by name, so whichever one comes first on the include path wins: [located-exception](https://github.com/Kronuz/located-exception)'s when msgpack stands alone, Xapiand's own inside Xapiand.

Without it, a decode error thrown from deep inside a third-party parser arrives as *its* exception type, foreign to your codebase, sliding past every `catch` you wrote for your own errors. With it, a malformed document throws a `msgpack::parse_error` that your `catch (const BaseException&)` catches like everything else you throw, and a plain `catch (const std::runtime_error&)` still catches it too.

## Where it fits

Reach for it when you want schemaless, JSON-shaped documents in C++ that move between JSON and MessagePack. It applies JSON Patch with Xapiand's `incr` and `decr` on top, and it merges with `update()`, where an undefined value (an extension type MessagePack can carry and JSON cannot) erases the key.

Skip it if your data has a fixed shape (a struct and a generated serializer will beat any dynamic value) or if your map keys are not strings. And if all you need is to serialize, current msgpack-c will serve new code better: this one bundles msgpack-c 1.3.0 because Xapiand does.

The next familiar stops handing documents around one at a time and moves a whole database instead: it floats it downstream over a wire, compressed and checked, without ever holding the file in memory.
