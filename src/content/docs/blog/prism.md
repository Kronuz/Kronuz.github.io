---
title: "Everything but the Views"
subtitle: "An HTTP server assembled from the familiars, with the defaults already chosen."
description: "prism is an HTTP and HTTPS application server for C++20, built from the Kronuz libraries: it takes a plain table of routes and wraps it with one event loop per CPU core, transparent zstd or gzip compression, cache validation and byte ranges, colored logs of every request, and a stack trace when a handler fails. On an Apple M4 Pro it served about 51,000 requests per second while using about 2 of its 14 cores."
excerpt: "A table of routes is not a server. Before anyone can use it, something has to open a port, spread the work over the cores, shrink the replies, write down what came in and what went out, and explain a crash instead of hiding it. The thirty-third familiar is that something, assembled from the familiars before it, with every one of those decisions already made."
date: 2026-11-06
authors: kronuz
series: "Familiars"
seriesOrder: 33
chapter: "Network"
tags:
  - familiars
  - cpp
  - http
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is where the network familiars meet in one program: [prism](https://github.com/Kronuz/prism).*

Think of a web service as a restaurant. The *views* are the recipes: ask for `/hello` and you get a greeting, ask for `/json` and you get some JSON back. A *router* is the recipe book, the thing that looks at the address a request asked for and finds the right recipe. [radix-router](/blog/radix-router/) and [the http framework](/blog/http/) give you a very good recipe book.

But a recipe book is not a restaurant. Someone has to open the door, keep a log of every order, and, when a dish burns, tell the customer politely and the chef exactly what went wrong. None of that is the food, and every restaurant needs it.

[prism](https://github.com/Kronuz/prism) is that whole restaurant around the recipes. It is an HTTP application server for C++20 that takes a plain table of routes and wraps it with everything a real service needs, built entirely from earlier familiars. It is one program, one source file of about 350 lines, and the only part you are meant to replace is the recipes.

## Why not just write it?

The tempting first version is a small loop: wait for a connection, read, call the router, answer, repeat. It works in a demo, until one slow request makes everyone behind it wait. The other temptation is copying the shell of a service you already have. Xapiand had a good one, but it was tangled up with search and storage. prism is that shell pulled out clean.

## The layers

prism is built like an onion, and each layer is a library you can also use alone:

```d2 alt="The program is nested layers: main holds the HTTP service, the service holds the access log and the reply transforms, and the access log holds the application router at the center."
direction: down
main: "main(): flags, logger, signals, banner" {
  service: "HttpAsioService: one reactor per core" {
    log: "AccessLog: every exchange logged, a traceback on a 5xx" {
      app: "DemoApp: a plain http::Router of views" { style.bold: true }
    }
    transforms: "the reply: ETag, then Range, then zstd or gzip"
    log -> transforms
  }
}
```

At the center are the views. Around them, an *access log* ([http-log](https://github.com/Kronuz/http-log)) writes down each request and its reply. Around that, the HTTP service reads the raw bytes off the network with [http-parser](/blog/http-parser/), runs on [reactor](/blog/reactor/), and polishes each reply before it leaves. The outermost layer is the program itself: it reads the command-line flags, sets up the [logger](/blog/logger/), and stops cleanly on Ctrl-C.

Here is a real view from prism's `src/main.cc`. It answers the same greeting as JSON, as HTML or as plain text, depending on what the client said it wants in its `Accept` header:

```cpp
router_.route("GET", "/hello", [](http::Request& req, http::ResponseWriter& resp, const http::Params&) -> asio::awaitable<void> {
    auto accept = req.header("Accept");
    if (accept.find("application/json") != std::string_view::npos)
        resp.send(200, "{\"hello\":\"world\",\"from\":\"prism\"}\n", "application/json");
    else if (accept.find("text/html") != std::string_view::npos)
        resp.send(200, "<h1>hello from <em>prism</em></h1>\n", "text/html; charset=utf-8");
    else
        resp.send(200, "hello from prism\n");
    co_return;
});
```

The view never compresses, logs, or touches the network. It picks an answer, and the layers around it do the rest.

## What prism decides for you

The value of an assembly is the decisions already made. These are prism's, read from its `src/main.cc`:

1. **One event loop per CPU core.** An *event loop* is a worker that juggles many connections at once, switching to whichever one has data ready. prism starts one per core, and each takes at most 256 requests at a time; one more gets a polite "busy, retry in a second" (`503`) instead of a queue that grows until the server runs out of memory.
2. **Smaller replies.** If the client says it understands compression, replies of 256 bytes or more are squeezed with zstd or gzip through [compressors](/blog/compressors/), and only sent that way when the result really is smaller.
3. **"You already have this."** Each reply gets a fingerprint, an *ETag*. A browser that sends back a matching fingerprint gets a tiny "not modified" (`304`) instead of the whole body again. A client can also ask for just a slice of a reply, a *byte range*.
4. **Every request in the log by default**, in color on a terminal and plain when piped to a file. JSON bodies are indented so a person can read them.
5. **A stack trace on a crash.** When a view throws an error, the client gets a `500`, and the log gets a *traceback*: the list of functions that were running when it failed, from [traceback](/blog/the-haunted-handler/).
6. **HTTPS** from just a certificate and its key, when the build finds OpenSSL 3.

None of these is clever. Each is a decision you would otherwise make at two in the morning, after the incident that needed it.

## The copy nobody read

Logging a reply means the log needs to see it. The first version of the access log made its own copy of every reply as it was written. It worked, but it copied every reply even when logging was turned off, building a copy and throwing it away unread.

The fix came from noticing that the copy already existed. The server holds the whole reply in memory anyway, because it must announce the reply's size before sending the first byte. So the log now reads that same buffer, after the view finishes, instead of keeping a second one. On a 63 KB JSON reply with logging off, that took the cost per request from **66.2 to 63.3 microseconds**. A small win, measured, and Xapiand's search service got it for free because it uses the same log.

## The numbers

The repo's [benchmarks](https://github.com/Kronuz/prism/blob/main/BENCHMARKS.md) were run on 2026-07-08 on an Apple M4 Pro with 14 cores, with the load generator on the same machine and a 17-byte reply. That was before prism's coroutine views and HTTPS arrived, so treat these as a snapshot. The table shows the most telling results:

| Test | Requests per second | Cores busy |
| --- | ---: | ---: |
| One request at a time per connection, no logging | 50,622 | about 2.1 |
| Same, logging every request | 48,047 | about 2.9 |
| 32 requests sent together per connection | 94,129 | about 4 |

The slowest 1% of requests took under 6 milliseconds, and none failed. The surprise is how idle the machine was: about 2 of 14 cores busy, while a one-core Node server on the same setup topped out near 59,000. The limit was the test itself, the round trip on one machine, and batching requests nearly doubled the number. A real production figure needs Linux, a client on another machine, and views that do real work.

prism has no tests of its own; the libraries it assembles carry theirs, and CI builds prism on Linux, macOS and FreeBSD, plus sanitizer builds that catch memory errors and data races as the program runs.

## Where it fits

Reach for prism as the starting point of a small C++ web service: copy it, replace the routes with yours, and the logs, compression, stack traces and clean shutdown come along. It is also the clearest map I have of how the network familiars fit together, in one file you can read top to bottom.

Skip it if you want a production server out of the box: it has no config file, only flags. It speaks HTTP/1.1 and HTTPS, not HTTP/2, and it is a program to copy, not a library to link.
