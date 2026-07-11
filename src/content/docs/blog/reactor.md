---
title: "One Loop Per Core"
subtitle: "The part of every TCP server you keep rewriting, written once."
description: "reactor is a generic Asio server runtime: the shared-nothing, thread-per-core pool of event loops, the accept plumbing, and the graceful shutdown that every network protocol needs, with the protocol itself left entirely to you. You hand it a Session, a C++20 coroutine that serves one accepted connection, and it runs it across N reactors on N threads with no shared state. It picks the bind mode per platform (SO_REUSEPORT where the kernel load-balances, a shared acceptor where a second same-port bind is rejected) and gives each reactor an offload pool for blocking or CPU-heavy work. Kronuz/http, a Xapian remote server, and replication all ride the same runtime instead of each re-writing the accept loop."
excerpt: "Every TCP server re-implements the same three unglamorous things: a pool of event loops across the cores, the accept loop that fans connections out to them, and the shutdown dance that tears it down without hanging. None of that is your protocol, and all of it is where the concurrency bugs live. The thirteenth familiar owns exactly that and nothing else, so a new protocol is a coroutine, not a runtime."
date: 2026-07-10
draft: true
series: "Familiars"
seriesOrder: 13
tags:
  - familiars
  - cpp
  - concurrency
---

*Part of **Familiars**: the small, sharp libraries I carved out of [Xapiand](https://github.com/Kronuz/Xapiand). This one is the floor everything networked stands on: [reactor](https://github.com/Kronuz/reactor).*

Write a second network server in the same codebase and you notice you are writing the same thing you wrote for the first one. Not the protocol, the protocol is different, but everything *under* it: the pool of event loops spread across the cores, the accept loop that binds a port and fans new connections out to those loops, and the shutdown sequence that stops all of it without deadlocking on in-flight work. It is unglamorous plumbing, it is identical every time, and it is precisely where the nasty concurrency bugs live, the ones about cross-thread teardown and sockets closing under a coroutine's feet. Rewriting it per protocol is how you get to debug the same race three times.

[reactor](https://github.com/Kronuz/reactor) is that plumbing, factored out and owned in one place, and nothing else. It runs on [standalone Asio](https://think-async.com/Asio/) with C++20 coroutines, header-only. You give it a **Session**, a coroutine that serves one accepted connection, and it runs it:

```cpp
asio::awaitable<void> echo(asio::ip::tcp::socket socket, reactor::Reactor& r) {
    char tmp[1024];
    for (;;) {
        std::size_t n = co_await socket.async_read_some(asio::buffer(tmp), asio::use_awaitable);
        if (n == 0) co_return;                                   // peer closed
        co_await asio::async_write(socket, asio::buffer(tmp, n), asio::use_awaitable);
    }
}
reactor::TcpServer server(/*reactors*/ 4, /*offload*/ 2, /*queue*/ 256, echo);
server.start(8080);   // binds, runs 4 loops on 4 threads, returns
```

The runtime knows nothing about HTTP or any framing. It hands the Session a `socket` and a `Reactor` and gets out of the way. Your whole protocol is the body of that coroutine.

## Shared-nothing, thread-per-core

The design decision underneath is **thread-per-core**: N reactors on N threads, each its own event loop, with no state shared between them. No global lock, no cross-core bounce, no cache line ping-ponging between loops. A connection is served entirely on the reactor that accepted it, so the work stays on one core and one cache. This is the architecture high-throughput servers converge on, because the cheapest synchronization is the synchronization you never do, and shared-nothing loops never have to.

That choice forces a portability problem the library solves quietly. To have each of N loops accept on the *same* port, the clean way is Linux's `SO_REUSEPORT`, where every reactor binds its own acceptor and the kernel load-balances new connections across them. But macOS and the BSDs reject a second bind on a port already bound, so `SO_REUSEPORT` is not portable. reactor picks the mode automatically: per-reactor acceptors with `SO_REUSEPORT` where it exists, a single shared acceptor that hands connections to the loops everywhere else. Same shared-nothing model, two different bind strategies under it, chosen by the platform. And because a Session should never do something slow on its reactor thread (that would stall every other connection on that loop), each reactor carries an **offload pool** for the blocking or CPU-heavy work, so the loop stays free to do IO.

## The payoff: one runtime, many protocols

The point of pulling this out is what it lets ride on it. In Xapiand, [Kronuz/http](https://github.com/Kronuz/http) runs on this runtime, and so does the Xapian remote-backend server, and so does the replication server, and a future service would too, each of them just a Session, none of them re-writing the accept loop, the offload pool, or the shutdown. Get the teardown race right *once*, here, and every protocol built on top inherits a clean shutdown for free.

## Where it fits

Reach for it when you are writing a TCP server in C++ and want the loops, accepting, offloading, and shutdown handled so you can write only the protocol. Skip it if you need something other than TCP, or you are already deep in a framework (Boost.Beast, an actor system) that owns the runtime for you.

The next familiar is the protocol that rides this floor: the HTTP framework itself, the one that turns a socket and a Session into requests, responses, routes, and middleware.
