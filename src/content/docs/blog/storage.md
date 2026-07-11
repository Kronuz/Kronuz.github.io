---
title: "Append Only"
subtitle: "A blob store that never overwrites, so a crash can only ever cost you the last write."
description: "storage is Xapiand's compressed, append-only, multi-volume blob store: it writes opaque binary records into fixed-size blocks in volume files, returns a stable offset for each, reads any record back by that offset, and transparently compresses large records with Zstandard. Its power is the append-only discipline. Because it never overwrites live data, only ever appends and advances, a crash mid-write can corrupt at most the tail it was writing, never a record already committed, which is what makes crash safety a property of the format rather than a prayer. The engine is one header-only template with the record framing and IO as injection seams."
excerpt: "The scariest moment for a datastore is the one where the power goes out mid-write. If your store overwrites data in place, that moment can shred a record that was already safe. The fifteenth familiar refuses to overwrite anything, ever: it only appends. A crash can lose the write in flight, and nothing else, and that single discipline turns crash safety from a hope into a guarantee of the format."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 15
tags:
  - familiars
  - cpp
  - storage
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is where the data lives: [storage](https://github.com/Kronuz/storage).*

Every datastore has one moment it is most afraid of, and it is the same moment: the power fails, or the process is killed, in the middle of a write. What happens to your data in that instant is decided long before it, by the shape of the format. A store that **overwrites in place**, that seeks to an existing record and writes new bytes over it, is exposed at that moment in the worst way, because a half-finished overwrite has destroyed the old record without finishing the new one. The data that was safe a millisecond ago is now torn.

[storage](https://github.com/Kronuz/storage) is built so that moment cannot cost you anything but the write that was in flight. It is a compressed, append-only, multi-volume blob store: opaque binary records, written into fixed-size blocks inside volume files, each write returning a stable **offset** you use to read it back later. Large records are transparently compressed, Zstandard by default. And it never overwrites. New data only ever gets **appended** past the end of what is already there.

## Why append-only is crash safety

The append-only discipline is the whole game. Because a record, once written and committed, is never touched again, a crash can only ever damage the region currently being appended: the tail. Everything before it is immutable and therefore intact by construction. Recovery is not a delicate repair of overwritten structures; it is finding where the last good record ended and treating everything after it as the write that did not make it. That is why crash safety here is a property of the *format* and not of luck. You do not overwrite live data, so a torn write cannot reach into the past.

Xapiand's data store had lived on this shape for years, and part of pulling it out was hardening it further into a crash-safe **v2 volume format**: it writes the new layout while still reading old v1 volumes, so existing data comes across unchanged, which the README guarantees byte-for-byte. Each record carries a header and an optional footer checksum, so a torn tail record is not just detectable by position but by a checksum that will not match, and recovery can draw the line exactly.

## An engine you frame yourself

The store is one header-only template, and the interesting design choice is what it does *not* decide:

```cpp
template <typename Header, typename BinHeader, typename Footer,
          typename IO = storage::DefaultIO>
class Storage;
```

`Header`, `BinHeader`, and `Footer` are the on-disk record framing, and you supply them: init and validate hooks let you stamp your own magic numbers, UUIDs, and checksums into the format. `IO` is the file-operation policy. Both are **injection seams**, so the engine itself carries nothing application-specific, and two different systems can use the same append-and-offset core with entirely different on-disk framing and durability policies. The append-only spine is fixed; the bytes around each record are yours.

## Where it fits

Reach for it when you need to persist a lot of opaque blobs, get a stable handle back for each, and care about surviving a crash without an external write-ahead log doing the safety for you. It pairs naturally with an index that stores those offsets. Skip it if you need in-place mutation of records (append-only means updates are new records, and reclaiming space is a compaction pass, not a free lunch), or if a real embedded database already gives you transactions.

The next familiar is what fills those records: the dynamic document value the whole engine passes around, the one that serialises to a compact wire format, patches like JSON, and copies for free.
