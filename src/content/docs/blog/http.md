---
title: "The Seam"
subtitle: "One interface between your application and the wire, and a writer that streams without remembering."
description: "http is a generic HTTP/1.1 application framework on Asio coroutines that puts the application above the server behind a single seam: you implement one HttpHandler::handle(Request, ResponseWriter) method, and the framework parses bytes with http-parser, builds the Request, calls you, and frames the response. The ResponseWriter serves two shapes through one interface: buffered send() that sets Content-Length, or a streamed status()/write()/end() that turns into chunked encoding, so a huge result set or a database dump goes out incrementally and never has to sit in memory all at once. The search engine is one handler; a demo key-value store is another."
excerpt: "Most HTTP frameworks make you think about the server. This one gives you exactly one thing to implement, a handler that takes a request and writes a response, and hides the socket, the parser, and the event loop entirely behind that seam. The fourteenth familiar, and the quiet cleverness is the writer: the same interface that sends a small buffered reply also streams a million-row result as chunks, never holding the whole thing in memory."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 14
tags:
  - familiars
  - cpp
  - http
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one rides the [runtime from last time](/blog/reactor/): [http](https://github.com/Kronuz/http), the framework itself.*

A good framework is mostly about what it refuses to make you think about. [http](https://github.com/Kronuz/http) is a generic HTTP/1.1 application framework on Asio coroutines, and its entire design goal is to put your application *above* the server, so that the socket, the byte parsing, and the event loop are simply not your problem. It does that with a single seam. You implement one interface:

```cpp
struct HttpHandler {
    virtual void handle(const Request&, ResponseWriter&) = 0;
};
```

and the framework does the rest: an Asio coroutine connection parses incoming bytes with [http-parser](/blog/http-parser/), assembles a `Request`, hands it to your handler, and frames whatever you write back over the socket. That is the whole contract. The search engine is one `HttpHandler`. A demo REST key-value store is another. Neither of them ever names a socket, the parser, or the loop.

## The writer that does not have to remember

The seam is tidy, but the piece I find genuinely clever is the `ResponseWriter`, because it hides a real problem behind a boring interface. HTTP/1.1 has two ways to send a body, and they are not interchangeable. If you know the size up front you send `Content-Length` and the bytes. If you do not, or the body is enormous, you send `Transfer-Encoding: chunked` and stream it in pieces. Most code picks one and bakes it into the call site. The `ResponseWriter` serves both through the same interface and picks for you:

```cpp
resp.send(200, body);                      // buffered: the writer sets Content-Length

resp.status(200);                          // streamed: each write() becomes a chunk
for (auto& row : rows) resp.write(row);    // a huge result set goes out incrementally
resp.end();                                // and never sits in memory all at once
```

The second form is the one that matters in a search engine. A `DUMP` of a database, or a result set with a million rows, cannot be built into one string in memory and then sent; that is how you turn a large query into an out-of-memory crash. Through the streamed writer it becomes a loop that writes rows as it finds them, the framework frames each `write()` as a chunk, and the peak memory is one row, not the whole answer. The handler code looks the same either way, a few calls on a writer, and the framing decision, `Content-Length` versus chunked, is made underneath it. That is the point of the seam: the hard part of HTTP/1.1, the framing, lives in the framework, and the application just writes.

## Where it fits

Reach for it when you want to serve HTTP/1.1 in C++ by writing handlers, not plumbing, and you want streaming responses to be as easy to write as buffered ones. It rides the [reactor](/blog/reactor/) runtime, so it inherits the thread-per-core loops and the clean shutdown for free, and it composes handlers into routers of closures, so a REST app is a table of routes and functions. Skip it if you need HTTP/2 or 3 (this is a 1.1 framework), or if you are already inside a batteries-included web stack that owns the request lifecycle.

The next familiar is where all those requests eventually land: the store on disk that keeps their data, and the one property, refusing to ever overwrite, that makes it survive a crash.
