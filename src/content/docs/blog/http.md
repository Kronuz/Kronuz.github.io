---
title: "The Seam"
subtitle: "An HTTP/1.1 framework that streams requests in and buffers replies out."
description: "http is a generic HTTP/1.1 application framework on Asio coroutines that puts the application above the server behind a single seam: you implement an HttpHandler whose handle method gets the Request and a ResponseWriter, and the framework parses bytes with http-parser, builds the Request, calls you, and frames the response. A request body can stream, pushed to a sink as it is parsed or read by the handler while it arrives, with back-pressure to the client, so a multi-gigabyte RESTORE runs in bounded memory. Replies are buffered and leave with Content-Length, which is what lets an ETag, a byte range and compression work on the whole body. The search engine is one handler; a demo key-value store is another."
excerpt: "Most HTTP frameworks make you think about the server. This one gives you exactly one thing to implement, a handler that takes a request and writes a response, and hides the socket, the parser, and the event loop behind that seam. The fourteenth familiar streams where it has to, on the way in, so a multi-gigabyte restore never sits in memory, and buffers on the way out, which is a limit, and also what gives a reply its ETag, its byte ranges and its compression."
date: 2026-09-03
series: "Familiars"
seriesOrder: 14
chapter: "Network"
tags:
  - familiars
  - cpp
  - http
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one rides the [runtime from last time](/blog/reactor/): [http](https://github.com/Kronuz/http), the framework itself.*

A good framework is mostly about what it refuses to make you think about. [http](https://github.com/Kronuz/http) is a generic HTTP/1.1 application framework on [standalone Asio](https://think-async.com/Asio/) coroutines, and its entire design goal is to put your application *above* the server, so that the socket, the byte parsing, and the event loop are simply not your problem. It does that with a single seam. You implement one class, `HttpHandler`, and the method that matters on it, `handle`, receives the `Request` and a `ResponseWriter`. The framework does the rest: one coroutine per connection parses the incoming bytes with [http-parser](/blog/http-parser/), assembles the `Request`, hands it to your handler, and frames whatever you write back over the socket.

That is the whole contract. Xapiand's search engine is one `HttpHandler`. A demo REST key-value store is another, a `Router` of closures over [radix-router](/blog/radix-router/), one per method and path (`GET /kv/:key`, `PUT /kv/:key`). Neither of them ever names a socket or the parser.

The parser is the one piece that had to change before the seam held. The first prototype parsed with [llhttp](https://github.com/nodejs/llhttp), and it lasted under an hour. Xapiand speaks its own verbs (`COUNT`, `INFO`, `DUMP`, `RESTORE`), llhttp checks every method against its own list, and a `COUNT` died in the parser as a `400` before any handler could see it. The fork behind http-parser carries those verbs in its method table, so after the switch the same `COUNT` went through to the router like any `GET`. Only the connection ever talks to the parser, so the swap touched no handler code at all.

## The body that never lands

Where streaming matters is the request. A search engine takes bodies of every size: a three-line query, an NDJSON bulk load, a `RESTORE` of a whole database that runs to gigabytes. Buffering the first one is right. Buffering the last one is how a restore turns into an out-of-memory crash. So the body is a choice the handler makes per request, when the headers are complete and it can look at them, before a single body byte is read.

By default the body lands whole in `Request::body`, the easy path for small requests. Return a `BodySink` from `on_request_body` instead and each chunk goes to the sink as it is parsed, and nothing accumulates. The demo counts NDJSON lines that way:

```cpp
// examples/kv_store.cc: count lines as the body arrives; only a partial line is held
class LineCountingSink : public http::BodySink {
    std::shared_ptr<BulkCtx> ctx_;
    std::string partial_;
public:
    explicit LineCountingSink(std::shared_ptr<BulkCtx> ctx) : ctx_(std::move(ctx)) {}
    void write(std::string_view chunk) override {
        partial_.append(chunk);
        std::size_t nl;
        while ((nl = partial_.find('\n')) != std::string::npos) {
            ++ctx_->lines;
            partial_.erase(0, nl + 1);
        }
    }
    void end() override {
        if (!partial_.empty()) { ++ctx_->lines; }  // trailing line without a newline
    }
};

// in the handler: stream POST /bulk into the sink, buffer everything else
std::unique_ptr<http::BodySink> on_request_body(http::Request& request) override {
    if (request.method == "POST" && request.path == "/bulk") {
        auto ctx = std::make_shared<BulkCtx>();
        request.user_data = ctx;
        return std::make_unique<LineCountingSink>(ctx);
    }
    return nullptr;
}
```

A sink runs while the bytes are being parsed, so its work has to stay light: counting, hashing. Heavy work, like indexing every object of a `RESTORE`, takes the third path. Return true from `wants_body_stream` and the handler starts as soon as the headers are in, then reads the body chunk by chunk while it is still arriving. Between the socket and the handler sits a queue that holds eight chunks. When it fills, the connection stops reading, the kernel's receive buffer fills up behind it, and TCP tells the client to slow down. The back-pressure goes all the way to the sender, and a multi-gigabyte restore is indexed as it arrives, in the memory of a few chunks. Xapiand's whole-database `RESTORE` takes that path.

## The reply that waits

The response side is plainer, and I would rather say so than dress it up. The `ResponseWriter` interface was drawn with streaming in mind (status and headers can change only until the first body byte, and `end()` is a required completion signal), but the Asio transport's writer buffers what you write. Every `write()` appends to one buffer, and when the response ends, the writer frames it with `Content-Length` and sends it whole:

```cpp
resp.send(200, body);                      // status, Content-Type, the body and end(), in one call

resp.status(200);                          // or piece by piece:
for (auto& row : rows) resp.write(row);    // each write() appends to the buffer
resp.end();                                // framed with Content-Length, sent whole
```

That is a limit, and it has a cost: a reply the size of a database dump sits whole in memory before its first byte leaves. Streaming a response is a separate problem, and `write()` does not take it on.

The buffer buys something, though. With the whole body in hand, three transforms can run on a reply before it goes out, in this order, each a knob the application turns on for the service:

1. **Conditional.** A weak ETag hashed from the body (64-bit FNV-1a), and if the client's `If-None-Match` already holds it, the body is dropped and the answer is `304 Not Modified`. It runs first so the ETag names the resource, and the compressed bytes never enter into it.
2. **Range.** A single byte `Range` becomes `206 Partial Content` with its `Content-Range`, or `416` when it cannot be satisfied.
3. **Compression.** zstd or gzip, negotiated from `Accept-Encoding` and encoded with [compressors](/blog/compressors/), skipped for a bodyless status, a `206` slice, a body that is already encoded, and a result that did not shrink.

Every one of them needs the whole body before the first header goes out. You cannot hash what you have not seen yet, and you cannot know whether compression paid off until it is done.

The buffer has one more reader. Xapiand wraps its handler in an access log, [http-log](https://github.com/Kronuz/http-log), that prints each request and response, bodies included. Because the writer keeps the response anyway, the log reads the status, the headers and the body back by reference instead of holding a second copy.

## Where it fits

Reach for it when you want to serve HTTP/1.1 in C++ by writing only the handlers, and some of your requests carry bodies too big to hold. It rides the [reactor](/blog/reactor/) runtime, so the thread-per-core loops and the clean shutdown come from there, and a REST app is a table of routes and closures. Skip it if you need HTTP/2 or 3 (this is a 1.1 framework), or if you are already inside a batteries-included web stack that owns the request lifecycle.

The next familiar is where all those requests eventually land: the store on disk that keeps their data, and the one property, refusing to ever overwrite a record, that makes it survive a crash.
