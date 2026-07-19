#!/usr/bin/env python3
"""etch — drive a persistent EternalTerminal session programmatically.

Wraps `et` in a PTY (via a small built-in engine), neutralizes the prompt to get a
clean byte stream, and runs commands framed by unique sentinels so output and
exit codes extract reliably regardless of the remote prompt's rendering.

Library: EtSession (one-shot) / open_session(key=...) (warm daemon).
CLI: `etch <run|open|attach|send|sendline|expect|read|peep|ls|close|gc> KEY ...` (see --help).
"""

from __future__ import annotations

import base64
import codecs
import fcntl
import getpass
import glob
import json
import os
import pty
import re
import select
import shlex
import signal
import socket
import struct
import subprocess
import sys
import termios
import time
import tty
import uuid
from typing import Any, Callable, Union, cast

# The remote PTY runs in canonical mode, which truncates a single input line at
# the kernel's cap (~1KB). A framed run() line longer than this is silently cut,
# the end sentinel never matches, and the leftover poisons the session. run()
# reroutes anything longer than this through run_script()'s chunked path.
_LINE_CAP = 900


# ─────────────────────────────────────────────────────────────────────────────
# PTY/expect engine
# -----------------
# A small, self-contained pseudo-terminal driver: spawn a command under a PTY and
# drive it with an expect-style read buffer. This is all etch needs to make `et`
# believe a human is on the other end, with no third-party dependencies.
#
#   spawn(cmd, encoding=, timeout=, dimensions=, codec_errors=)  -> child
#   child.expect(pattern | list, timeout=)   child.expect_exact(s, timeout=)
#   child.read_nonblocking(size=, timeout=)  child.send(s)  child.sendline(s)
#   child.before  child.after  child.match   child.close(force=)
#   TIMEOUT / EOF   (raised, and usable as expect() patterns to match instead of raise)
# ─────────────────────────────────────────────────────────────────────────────


class TIMEOUT(Exception):
    """No match or data arrived before the deadline. Usable as an expect() pattern
    to match-on-timeout instead of raising."""


class EOF(Exception):
    """The child's PTY hit end-of-file / the process exited. Usable as an expect()
    pattern to match-on-EOF instead of raising."""


_Pattern = Union[str, "re.Pattern[str]", type[TIMEOUT], type[EOF]]
_ExpectArg = Union[_Pattern, list[_Pattern]]


class _PtyProcess:
    """Spawn a command under a pseudo-terminal and drive it with an expect-style
    read buffer. A minimal driver: only the behavior etch needs."""

    # A brief pause before each write avoids losing input to a remote PTY that is
    # not yet ready to read. Tunable if latency ever matters.
    delaybeforesend: float = 0.05

    def __init__(
        self,
        command: str,
        encoding: str = "utf-8",
        timeout: float = 30,
        dimensions: tuple[int, int] = (24, 80),
        codec_errors: str = "strict",
    ) -> None:
        self.timeout = timeout
        self.before: str = ""
        self.after: str | type[TIMEOUT] | type[EOF] = ""
        self.match: re.Match[str] | None = None
        self._buf: str = ""
        self._decoder = codecs.getincrementaldecoder(encoding)(codec_errors)
        argv = shlex.split(command)
        pid, fd = pty.fork()
        if pid == 0:  # child: replace ourselves with the command on the PTY slave
            try:
                os.execvp(argv[0], argv)
            except Exception:
                os._exit(127)
        self.pid: int = pid
        self.fd: int = fd
        rows, cols = dimensions
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    # ── low-level I/O ─────────────────────────────────────────────────────────
    def _read_fd(self, timeout: float) -> str | None:
        """Wait up to `timeout` for output; decode and return a chunk (possibly ''
        on a partial multibyte char). Return None on timeout; raise EOF when gone."""
        try:
            empty: list[int] = []
            ready, _, _ = select.select([self.fd], empty, empty, max(0.0, timeout))
        except (OSError, ValueError):
            raise EOF()
        if not ready:
            return None
        try:
            data = os.read(self.fd, 4096)
        except OSError:  # Linux reports the PTY master EOF as EIO
            raise EOF()
        if not data:  # macOS reports EOF as an empty read
            raise EOF()
        return self._decoder.decode(data)

    def send(self, s: str) -> int:
        if self.delaybeforesend:
            time.sleep(self.delaybeforesend)
        return os.write(self.fd, s.encode("utf-8", "replace"))

    def sendline(self, s: str = "") -> int:
        return self.send(s + "\n")

    def read_nonblocking(self, size: int = 1, timeout: float | None = None) -> str:
        """Up to `size` chars: drain the expect buffer first, else read the fd.
        Raise TIMEOUT if nothing arrives in time, EOF at end of file."""
        if self._buf:
            out, self._buf = self._buf[:size], self._buf[size:]
            return out
        chunk = self._read_fd(self.timeout if timeout is None else timeout)
        if chunk is None:
            raise TIMEOUT()
        if size and len(chunk) > size:
            self._buf = chunk[size:] + self._buf
            chunk = chunk[:size]
        return chunk

    # ── expect machinery ──────────────────────────────────────────────────────
    @staticmethod
    def _compile(pattern: _ExpectArg) -> list[object]:
        items = pattern if isinstance(pattern, list) else [pattern]
        out: list[object] = []
        for p in items:
            out.append(re.compile(p) if isinstance(p, str) else p)
        return out

    def _set(
        self,
        before: str,
        after: str | type[TIMEOUT] | type[EOF],
        match: re.Match[str] | None,
        rest: str,
    ) -> None:
        self.before, self.after, self.match, self._buf = before, after, match, rest

    def expect(self, pattern: _ExpectArg, timeout: float | None = None) -> int:
        """Read until one of `pattern` (a regex, or a list mixing regexes with the
        EOF/TIMEOUT classes) matches; return its index and set before/after/match.
        EOF/TIMEOUT in the list match instead of raising."""
        compiled = self._compile(pattern)
        eof_idx: int | None = None
        tmo_idx: int | None = None
        regexes: list[tuple[int, re.Pattern[str]]] = []
        for i, p in enumerate(compiled):
            if p is EOF:
                eof_idx = i
            elif p is TIMEOUT:
                tmo_idx = i
            elif isinstance(p, re.Pattern):
                regexes.append((i, cast("re.Pattern[str]", p)))
        deadline = time.time() + (self.timeout if timeout is None else timeout)
        while True:
            best: tuple[int, int, re.Match[str]] | None = None
            for i, rx in regexes:
                m = rx.search(self._buf)
                if m is not None and (best is None or m.start() < best[0]):
                    best = (m.start(), i, m)
            if best is not None:
                _, i, m = best
                self._set(self._buf[: m.start()], m.group(0), m, self._buf[m.end() :])
                return i
            remaining = deadline - time.time()
            if remaining <= 0:
                if tmo_idx is not None:
                    self._set(self._buf, TIMEOUT, None, "")
                    return tmo_idx
                raise TIMEOUT()
            try:
                chunk = self._read_fd(remaining)
            except EOF:
                if eof_idx is not None:
                    self._set(self._buf, EOF, None, "")
                    return eof_idx
                raise
            if chunk:
                self._buf += chunk

    def expect_exact(self, s: str, timeout: float | None = None) -> int:
        """Like expect() but matches a literal substring (no regex)."""
        deadline = time.time() + (self.timeout if timeout is None else timeout)
        while True:
            idx = self._buf.find(s)
            if idx >= 0:
                self._set(self._buf[:idx], s, None, self._buf[idx + len(s) :])
                return 0
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TIMEOUT()
            chunk = self._read_fd(remaining)  # raises EOF when the child is gone
            if chunk:
                self._buf += chunk

    def close(self, force: bool = True) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGKILL if force else signal.SIGHUP)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(self.pid, 0)
            except OSError:
                pass
            self.pid = 0


# Alias so call sites read `spawn(...)`.
spawn = _PtyProcess

_ANSI = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[=>]"
)


def _clean(s: str) -> str:
    return _ANSI.sub("", s).replace("\r", "")


_TRANSPORTS = {"et": "et {host}", "ssh": "ssh -tt {host}"}


def _transport_cmd(via: str, host: str) -> str:
    """The command that opens an interactive PTY shell on HOST. `via` is a known
    transport name (et/ssh) or a literal 'CMD {host}' template (host is appended if
    it has no {host}). The default, et, gives the resilient eternal session."""
    tmpl = _TRANSPORTS.get(via, via)
    return tmpl.format(host=host) if "{host}" in tmpl else "%s %s" % (tmpl, host)


class EtSession:
    def __init__(
        self,
        host: str,
        via: str = "et",
        connect_timeout: float = 60,
        dims: tuple[int, int] = (50, 200),
        remote_histfile: str | None = "/dev/null",
        cmdlog: str | None = None,
    ) -> None:
        self.host = host
        self.timeout = connect_timeout
        # remote_histfile: where the remote shell writes history.
        #   '/dev/null' (default) = discard; or a path = dedicated audit file;
        #   set None to leave the shell's default untouched.
        self.remote_histfile = remote_histfile
        # cmdlog: optional LOCAL file; the wrapper appends every command it runs.
        self.cmdlog = cmdlog
        self.prompt = ""  # verbatim remote prompt line from the last expect()
        # before/after/match are populated dynamically; keep the child typed Any and
        # lean on the sentinel framing. The engine itself is fully typed above.
        self.child: Any = spawn(
            _transport_cmd(via, host),
            encoding="utf-8",
            timeout=connect_timeout,
            dimensions=dims,
            codec_errors="replace",
        )

    def connect(self) -> EtSession:
        c = self.child
        c.expect("❯", timeout=self.timeout)
        self._drain(0.6)  # flush the full p10k prompt render
        hf = self.remote_histfile
        # zsh side: stop it saving the exec line / anything to the real history
        if hf is not None:
            c.sendline("HISTFILE=%s; fc -p /dev/null 2>/dev/null" % hf)
            self._drain(0.3)
        # replace noisy interactive zsh+p10k with a bare, quiet bash
        c.sendline("exec bash --norc --noprofile")
        self._drain(0.6)
        # clean-room env: empty prompts, dumb term, no \r, no pagers/interactive prompts
        setup = (
            "export PS1='' PS2='' PROMPT_COMMAND='' TERM=dumb "
            "PAGER=cat GIT_PAGER=cat GIT_TERMINAL_PROMPT=0 "
            "DEBIAN_FRONTEND=noninteractive; stty -echo -onlcr 2>/dev/null"
        )
        if hf is None:
            pass
        elif hf == "/dev/null":
            setup = "set +o history; " + setup  # don't record at all
        else:
            setup += "; export HISTFILE=%s" % hf  # dedicated audit file
        c.sendline(setup)
        self._drain(0.6)
        nonce = "RDY_" + uuid.uuid4().hex[:8]
        for _ in range(8):
            c.sendline("echo %s" % nonce)
            try:
                c.expect_exact(nonce, timeout=4)  # stty -echo => appears once (output)
            except TIMEOUT:
                continue
            except EOF:
                raise RuntimeError("et session closed during connect")
            else:
                self._drain(0.4)
                return self
        raise RuntimeError("sync failed; tail=%r" % (c.before[-300:],))

    def _drain(self, idle: float = 0.3) -> None:
        """Discard whatever output is buffered right now (settle the stream)."""
        self.read_available(idle)

    def _resync(self, attempts: int = 3) -> bool:
        """Recover a desynced session after a framing failure (a command that
        hung reading stdin, or a truncated over-long line). Interrupt whatever is
        running with Ctrl-C, drain, and confirm a clean prompt with a nonce.
        Returns True if the session is usable again. This keeps one bad command
        from poisoning the whole warm key."""
        c = self.child
        try:
            for _ in range(attempts):
                c.send("\x03")  # Ctrl-C: kill a hung/partial command
                self._drain(0.4)
                nonce = "RSY_" + uuid.uuid4().hex[:8]
                c.sendline("echo %s" % nonce)
                try:
                    c.expect_exact(nonce, timeout=4)
                    self._drain(0.3)
                    return True
                except TIMEOUT:
                    continue
                except EOF:
                    return False
        except Exception:
            return False
        return False

    def run(self, cmd: str, timeout: float = 60) -> tuple[str, int]:
        c = self.child
        if self.cmdlog:
            with open(self.cmdlog, "a") as fh:
                fh.write(cmd + chr(10))
        s = "S_" + uuid.uuid4().hex[:8]
        e = "E_" + uuid.uuid4().hex[:8]
        framed = "printf '%%s\\n' '%s'; %s; printf '%s%%d\\n' \"$?\"" % (s, cmd, e)
        # Over-long lines would be truncated by the PTY's canonical cap and wedge
        # the session; route them through the chunk-safe run_script path instead.
        if len(framed) > _LINE_CAP:
            return self.run_script(cmd, timeout=timeout)
        c.sendline(framed)
        try:
            c.expect(re.escape(e) + r"(\d+)", timeout=timeout)
        except TIMEOUT:
            ok = self._resync()
            raise RuntimeError(
                "run() timed out waiting for the end sentinel (the command may "
                "read stdin or hang; run() does not forward stdin, and is for "
                "short commands, use run_script/`script` for input or long "
                "payloads). session %s. cmd=%r"
                % ("resynced" if ok else "may be wedged", cmd[:120])
            )
        code = int(c.match.group(1))
        raw = _clean(c.before)
        if s in raw:
            raw = raw.split(s, 1)[1]
        return raw.strip("\n"), code

    def run_script(
        self, script: str, timeout: float = 180, chunk: int = 400
    ) -> tuple[str, int]:
        """Inject an arbitrarily long/multi-line script safely. PTY canonical mode
        caps a single input line (~1KB), so we base64-encode and append in small
        chunks to a remote file, then decode and run it (preserving its exit code)."""
        blob = base64.b64encode(script.encode()).decode()
        remote = "/tmp/etch_%s.b64" % uuid.uuid4().hex[:8]
        _, code = self.run(": > %s" % remote)
        if code != 0:
            raise RuntimeError("could not create remote temp file")
        for i in range(0, len(blob), chunk):
            _, code = self.run(
                "printf '%%s' '%s' >> %s" % (blob[i : i + chunk], remote)
            )
            if code != 0:
                raise RuntimeError("chunk append failed at offset %d" % i)
        return self.run(
            "base64 -d %s | bash; rc=$?; rm -f %s; (exit $rc)" % (remote, remote),
            timeout=timeout,
        )

    # ── Interactive driving (write_bash-style) ────────────────────────────────
    # run()/run_script() are for commands that finish and return to the prompt.
    # For programs that PROMPT mid-run (sudo, [y/n], REPLs, mysql>), use these
    # raw primitives: send input, expect a prompt pattern, read the live stream.
    # Output here is raw (the program's own prompts/echo) — you match prompts
    # yourself. Don't interleave run() while an interactive program is mid-flight;
    # expect it back to the shell first. (Never hardcode a password — for an auth
    # prompt, route the secret through secure input, not the script.)
    def send(self, data: str) -> None:
        """Write raw bytes/text to the remote stdin (no trailing newline)."""
        self.child.send(data)

    def sendline(self, data: str = "") -> None:
        """Write a line (adds newline) to the remote stdin."""
        self.child.sendline(data)

    def _prompt_line(self) -> str:
        """Reconstruct the verbatim prompt the program is waiting at: the last
        non-empty line of what preceded the match, plus the matched text itself
        (e.g. '[sudo] password for gmendezb:'). Show this to a human who has to
        answer it, so they know exactly what's being asked."""
        before = _clean(self.child.before or "")
        after = self.child.after if isinstance(self.child.after, str) else ""
        last = ""
        for ln in before.splitlines():
            if ln.strip():
                last = ln
        return (last + _clean(after)).strip()

    def expect(self, pattern: str | list[str], timeout: float = 30) -> tuple[str, int]:
        """Wait for a regex pattern (or list); returns (cleaned_text_before, index).
        Also sets self.prompt to the verbatim prompt line that matched."""
        idx = self.child.expect(pattern, timeout=timeout)
        self.prompt = self._prompt_line()
        return _clean(self.child.before), idx

    def expect_exact(self, s: str, timeout: float = 30) -> str:
        """Like expect() but matches a literal string (no regex). Returns text before."""
        self.child.expect_exact(s, timeout=timeout)
        self.prompt = self._prompt_line()
        return _clean(self.child.before)

    def read_available(self, idle: float = 0.3) -> str:
        """Drain and return whatever output is currently buffered."""
        buf = ""
        while True:
            try:
                buf += self.child.read_nonblocking(4096, timeout=idle)
            except (TIMEOUT, EOF):
                break
        return _clean(buf)

    def read(self, timeout: float = 10, quiet: float = 0.4) -> str:
        """Show whatever the other end is saying when you DON'T have a prompt to
        expect: wait up to `timeout` for output to start, then drain until `quiet`
        seconds of silence. Returns cleaned text. Pattern-free 'peek at the screen'.
        Line/stream output works; full-screen TUIs (vim/top) that redraw via cursor
        escapes won't linearize cleanly — those need a terminal emulator (out of scope)."""
        deadline = time.time() + timeout
        buf = ""
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                buf += self.child.read_nonblocking(4096, timeout=min(quiet, remaining))
            except TIMEOUT:
                if buf:
                    break  # had output, now silent => done
            except EOF:
                break
        return _clean(buf)

    def close(self) -> None:
        try:
            self.child.sendline("exit")
            self.child.expect(EOF, timeout=5)
        except Exception:
            pass
        finally:
            self.child.close(force=True)


# ─────────────────────────────────────────────────────────────────────────────
# Daemon mode — keep ONE warm EtSession alive across separate processes/one-shot
# calls, so any later invocation reuses it (no ~13s reconnect) and shell state
# persists for the whole experiment/session.
#
# CONCURRENCY MODEL (important): a single EtSession is ONE serial conversation —
# interleaving run()s would tangle their sentinels. So the daemon is keyed: each
# `key` is its own daemon → its own `et` client → its own remote shell.
#   * Same key  = same warm shell, requests SERIALIZED (safe, but not parallel).
#   * Diff key  = isolated shell, runs in PARALLEL.
# => give each agent/subagent its own key (e.g. ETCH_KEY). Never share one key
#    across actors that run concurrently.
# ─────────────────────────────────────────────────────────────────────────────


# ── Daemon: paths, process liveness & filesystem introspection ──
def _safe(key: str) -> str:
    """Filesystem-safe form of a daemon key."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def _user_prefix() -> str:
    """Shared /tmp path prefix for this user's daemon files."""
    return "/tmp/etch-%s-" % getpass.getuser()


def _sock_path(key: str) -> str:
    return _user_prefix() + _safe(key) + ".sock"


def _pid_path(key: str) -> str:
    return _sock_path(key)[:-5] + ".pid"  # /tmp/etch-<user>-<key>.pid


def _trace_path(key: str) -> str:
    return _sock_path(key)[:-5] + ".trace"  # /tmp/etch-<user>-<key>.trace (peep)


def _alive(pid: int) -> bool:
    # zombie-aware: a process that exists only as a defunct/zombie (state 'Z')
    # is treated as NOT alive, so reap() isn't fooled by a just-killed daemon.
    try:
        st = subprocess.run(
            ["ps", "-p", str(pid), "-o", "state="],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        # ps unavailable: fall back to signal-0 probe
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    return bool(st) and not st.startswith("Z")


def reap() -> None:
    """Sweep leftovers from crashed daemons: if a daemon PID is dead, kill its
    orphaned `et` child (by recorded PID, verified) and remove its socket+pidfile.
    Cheap; call opportunistically (open_session does)."""
    for pf in glob.glob(_user_prefix() + "*.pid"):
        try:
            parts = open(pf).read().split()
            dpid, epid = int(parts[0]), int(parts[1])  # pidfile: "<dpid> <epid> [host]"
        except Exception:
            try:
                os.unlink(pf)
            except OSError:
                pass
            continue
        if _alive(dpid):
            continue  # daemon still running; leave it
        if _alive(epid):
            # verify the PID is really an `et` client before killing (PID reuse guard)
            try:
                cmd = subprocess.run(
                    ["ps", "-p", str(epid), "-o", "command="],
                    capture_output=True,
                    text=True,
                    timeout=5,
                ).stdout
            except Exception:
                cmd = ""
            if "/et " in cmd or cmd.strip().startswith("et ") or " et " in cmd:
                try:
                    os.kill(epid, signal.SIGTERM)
                except OSError:
                    pass
        for p in (pf, pf[:-4] + ".sock", pf[:-4] + ".trace"):
            try:
                os.unlink(p)
            except OSError:
                pass

    # Also sweep orphaned sockets with no pidfile (a daemon that crashed after
    # binding but before writing its pidfile, e.g. connect() failed). The pidfile
    # loop above can't see those. A socket with a live listener is a daemon still
    # starting up, so probe it and only remove the ones nothing answers on.
    for sk in glob.glob(_user_prefix() + "*.sock"):
        if os.path.exists(sk[:-5] + ".pid"):
            continue  # has a pidfile (handled above, or a running daemon)
        try:
            probe = socket.socket(socket.AF_UNIX)
            probe.settimeout(1)
            probe.connect(sk)
            probe.close()
            continue  # someone is listening (a daemon starting up): leave it
        except OSError:
            for p in (sk, sk[:-5] + ".trace"):
                try:
                    os.unlink(p)
                except OSError:
                    pass


def _live_keys() -> list[str]:
    """Keys of currently-bound daemons (from their socket files)."""
    prefix = _user_prefix()
    return [s[len(prefix) : -5] for s in sorted(glob.glob(prefix + "*.sock"))]


def _pidfile_fields(key: str) -> tuple[str, str, str | None]:
    """(daemon_pid_str, et_pid_str, host) from a daemon's pidfile, or ('?','?',None)."""
    try:
        parts = open(_pid_path(key)).read().split()
        return parts[0], parts[1], (parts[2] if len(parts) > 2 else None)
    except Exception:
        return "?", "?", None


def _daemon_host(key: str) -> str | None:
    """The host a live daemon for KEY serves (from its pidfile), or None."""
    return _pidfile_fields(key)[2]


# ── Daemon: length-prefixed JSON wire protocol (4-byte big-endian length + body) ──
def _recvn(conn: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _send_msg(conn: socket.socket, obj: Any) -> None:
    data = json.dumps(obj).encode()
    conn.sendall(struct.pack(">I", len(data)) + data)


def _recv_msg(conn: socket.socket) -> dict[str, Any] | None:
    hdr = _recvn(conn, 4)
    if not hdr:
        return None
    (n,) = struct.unpack(">I", hdr)
    body = _recvn(conn, n)
    return None if body is None else json.loads(body.decode())


def _xlate_pat(pat: str | list[str]) -> Any:
    # the wire can't carry TIMEOUT/EOF objects, so callers pass the
    # sentinels "<<TIMEOUT>>"/"<<EOF>>" and we translate them back here.
    def one(p: str) -> Any:
        if p == "<<TIMEOUT>>":
            return TIMEOUT
        if p == "<<EOF>>":
            return EOF
        return p

    return [one(p) for p in pat] if isinstance(pat, list) else one(pat)


# ── Daemon: client (warm session reuse across processes) ──
class DaemonClient:
    """Thin client to a per-key etch daemon. Auto-starts the daemon on first
    use. Same .run()/.run_script() API as EtSession, but warm across processes."""

    def __init__(
        self,
        key: str,
        host: str | None = None,
        via: str = "et",
        idle: int = 900,
        autostart: bool = True,
        connect_timeout: float = 90,
    ) -> None:
        self.key, self.host, self.via, self.idle = key, host, via, idle
        self.path = _sock_path(key)
        self.conn: socket.socket | None = None  # set once connected
        self.prompt = ""  # verbatim remote prompt line from the last expect()
        self.started = (
            False  # True if this client spawned the daemon (vs reused a warm one)
        )
        if not self._connect():
            if not autostart:
                raise RuntimeError("no daemon for key %r" % key)
            self._start(connect_timeout)
            self.started = True

    def _connect(self, timeout: float = 10) -> bool:
        try:
            c = socket.socket(socket.AF_UNIX)
            c.settimeout(timeout)
            c.connect(self.path)
            self.conn = c
            return True
        except OSError:
            return False

    def _start(self, connect_timeout: float) -> None:
        if not self.host:
            raise RuntimeError("no host to start a daemon for key %r" % self.key)
        try:
            os.unlink(self.path)  # clear a stale socket
        except OSError:
            pass
        log = open("/tmp/etch-%s.log" % _safe(self.key), "a")
        subprocess.Popen(
            [
                sys.executable,
                os.path.realpath(__file__),
                "--daemon",
                self.key,
                self.host,
                self.via,
                str(self.idle),
            ],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )
        # The daemon binds the socket quickly but only accepts after its ~13s
        # EtSession.connect(). So: wait for the socket to appear, then send one
        # ping with a long timeout — the daemon answers once the shell is ready.
        deadline = time.time() + connect_timeout
        while time.time() < deadline:
            if self._connect(timeout=connect_timeout):
                break
            time.sleep(0.3)
        else:
            raise RuntimeError("daemon socket for key %r never appeared" % self.key)
        try:
            _send_msg(cast(socket.socket, self.conn), {"op": "ping"})
            r = _recv_msg(cast(socket.socket, self.conn))
        except OSError as e:
            raise RuntimeError("daemon ping failed for key %r: %r" % (self.key, e))
        if not (r and r.get("ok")):
            raise RuntimeError("daemon for key %r not ready" % self.key)

    def _rpc(self, msg: dict[str, Any], timeout: float = 60) -> dict[str, Any]:
        assert self.conn is not None, "not connected"
        self.conn.settimeout(
            timeout + 15
        )  # generous margin over the command's own timeout
        _send_msg(self.conn, msg)
        r = _recv_msg(self.conn)
        if r is None:
            raise RuntimeError("daemon closed the connection")
        if "error" in r:
            raise RuntimeError(r["error"])
        return r

    def run(self, cmd: str, timeout: float = 60) -> tuple[str, int]:
        r = self._rpc({"op": "run", "cmd": cmd, "timeout": timeout}, timeout=timeout)
        return r["out"], r["code"]

    def run_script(self, script: str, timeout: float = 180) -> tuple[str, int]:
        r = self._rpc(
            {"op": "run_script", "script": script, "timeout": timeout}, timeout=timeout
        )
        return r["out"], r["code"]

    # ── Interactive driving over the daemon (mirrors EtSession's primitives) ──
    def send(self, data: str, secret: bool = False) -> None:
        self._rpc({"op": "send", "data": data, "secret": secret}, timeout=10)

    def sendline(self, data: str = "", secret: bool = False) -> None:
        self._rpc({"op": "sendline", "data": data, "secret": secret}, timeout=10)

    def expect(self, pattern: str | list[str], timeout: float = 30) -> tuple[str, int]:
        # pass TIMEOUT/EOF as the sentinels "<<TIMEOUT>>"/"<<EOF>>"
        r = self._rpc(
            {"op": "expect", "pattern": pattern, "timeout": timeout}, timeout=timeout
        )
        self.prompt = r.get("prompt", "")
        return r["out"], r["idx"]

    def expect_exact(self, s: str, timeout: float = 30) -> str:
        r = self._rpc(
            {"op": "expect_exact", "s": s, "timeout": timeout}, timeout=timeout
        )
        self.prompt = r.get("prompt", "")
        return r["out"]

    def read(self, timeout: float = 10, quiet: float = 0.4) -> str:
        r = self._rpc(
            {"op": "read", "timeout": timeout, "quiet": quiet}, timeout=timeout
        )
        return r["out"]

    def read_available(self, idle: float = 0.3) -> str:
        r = self._rpc({"op": "read_available", "idle": idle}, timeout=max(5, idle * 3))
        return r["out"]

    def peep_start(self) -> str:
        """Enable the daemon's live trace; returns the trace file path to tail."""
        return cast(str, self._rpc({"op": "peep_start"}, timeout=10).get("path"))

    def peep_stop(self) -> None:
        try:
            self._rpc({"op": "peep_stop"}, timeout=10)
        except Exception:
            pass

    def shutdown(self) -> None:
        """Stop the daemon (closes its et session + remote shell)."""
        try:
            _send_msg(cast(socket.socket, self.conn), {"op": "shutdown"})
            _recv_msg(cast(socket.socket, self.conn))
        except OSError:
            pass
        self.close()

    def close(self) -> None:
        """Disconnect the client; the daemon stays warm for the next caller."""
        if self.conn:
            try:
                self.conn.close()
            except OSError:
                pass
            self.conn = None


def _random_key() -> str:
    """A short, opaque session handle (used when `open` gets no --key)."""
    return uuid.uuid4().hex[:8]


def open_session(
    host: str, key: str | None = None, via: str = "et", idle: int = 900
) -> DaemonClient:
    """Open (spawn-or-reuse) a warm per-key daemon to HOST and return a client.

    KEY is a logical handle for the session (random if omitted). The host lives
    with the daemon, not the key. `via` is the transport (et/ssh or a 'CMD {host}'
    template). Operate on the result with .run()/.send()/etc.; a later caller
    reattaches with DaemonClient(key, autostart=False).

    CONCURRENCY: a daemon is ONE serial conversation. One logical actor per key;
    give concurrent actors (e.g. subagents) distinct keys, or use EtSession()
    directly for an isolated one-shot shell.
    """
    reap()  # sweep any crashed-daemon orphans first
    return DaemonClient(key=key or _random_key(), host=host, via=via, idle=idle)


# ── Daemon: server (the long-lived worker that owns one warm EtSession) ──
def _daemon_main(key: str, host: str, via: str, idle: int) -> None:
    idle = int(idle)
    path = _sock_path(key)
    pidpath = _pid_path(key)
    srv = socket.socket(socket.AF_UNIX)
    try:
        srv.bind(path)  # fails if another daemon already won
    except OSError:
        return
    os.chmod(path, 0o600)
    srv.listen(8)
    try:
        sess = EtSession(
            host=host,
            via=via,
            cmdlog="/tmp/etch-%s.cmdlog" % _safe(key),
        ).connect()
    except Exception:
        # connect() failed (e.g. VM unreachable): don't leave the bound socket
        # behind with no pidfile, that would show in `ls` as a dead orphan.
        try:
            srv.close()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        os._exit(1)
    # record daemon PID + et-client PID (for reap) + the host this daemon serves
    try:
        open(pidpath, "w").write("%d %d %s" % (os.getpid(), sess.child.pid, host))
    except OSError:
        pass

    tracepath = _trace_path(key)
    trace: dict[str, Any] = {"fh": None, "n": 0}  # peep: refcounted op-level live trace

    def _trace(arrow: str, text: str) -> None:
        if not trace["fh"]:
            return  # zero cost when nobody is peeping
        t = text.replace("\n", "\\n")
        if len(t) > 4000:
            t = t[:4000] + "...(+%d)" % (len(t) - 4000)
        try:
            trace["fh"].write("%s %s %s\n" % (time.strftime("%H:%M:%S"), arrow, t))
            trace["fh"].flush()
        except Exception:
            pass

    def _graceful(*_: Any) -> None:
        # Unlink the fs entries FIRST so a stopped daemon vanishes from ls/peers
        # immediately, before the (slow) session teardown waits on et to exit.
        for p in (path, pidpath, tracepath):
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            srv.close()
        except Exception:
            pass
        try:
            if trace["fh"]:
                trace["fh"].close()
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass
        os._exit(0)

    # Session ops: each turns a request into a response dict; the loop wraps any
    # exception into {"error": ...}. (Control ops ping/peep/shutdown are inline.)
    def _op_run(msg: dict[str, Any]) -> dict[str, Any]:
        _trace("»", "run: " + msg["cmd"])
        out, code = sess.run(msg["cmd"], timeout=msg.get("timeout", 60))
        _trace("«", "(rc=%d) %s" % (code, out))
        return {"out": out, "code": code}

    def _op_run_script(msg: dict[str, Any]) -> dict[str, Any]:
        _trace("»", "run_script: <%d bytes>" % len(msg.get("script", "")))
        out, code = sess.run_script(msg["script"], timeout=msg.get("timeout", 180))
        _trace("«", "(rc=%d) %s" % (code, out))
        return {"out": out, "code": code}

    def _op_send(msg: dict[str, Any]) -> dict[str, Any]:
        sess.send(msg.get("data", ""))
        _trace("»", "<secret>" if msg.get("secret") else repr(msg.get("data", "")))
        return {"ok": True}

    def _op_sendline(msg: dict[str, Any]) -> dict[str, Any]:
        sess.sendline(msg.get("data", ""))
        _trace("»", "<secret>" if msg.get("secret") else msg.get("data", ""))
        return {"ok": True}

    def _op_expect(msg: dict[str, Any]) -> dict[str, Any]:
        out, idx = sess.expect(
            _xlate_pat(msg["pattern"]), timeout=msg.get("timeout", 30)
        )
        _trace("«", "[matched %d] %s" % (idx, sess.prompt or out[-160:]))
        return {"out": out, "idx": idx, "prompt": sess.prompt}

    def _op_expect_exact(msg: dict[str, Any]) -> dict[str, Any]:
        out = sess.expect_exact(msg["s"], timeout=msg.get("timeout", 30))
        _trace("«", sess.prompt or out[-160:])
        return {"out": out, "prompt": sess.prompt}

    def _op_read(msg: dict[str, Any]) -> dict[str, Any]:
        out = sess.read(timeout=msg.get("timeout", 10), quiet=msg.get("quiet", 0.4))
        _trace("«", out)
        return {"out": out}

    def _op_read_available(msg: dict[str, Any]) -> dict[str, Any]:
        out = sess.read_available(idle=msg.get("idle", 0.3))
        _trace("«", out)
        return {"out": out}

    session_ops: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "run": _op_run,
        "run_script": _op_run_script,
        "send": _op_send,
        "sendline": _op_sendline,
        "expect": _op_expect,
        "expect_exact": _op_expect_exact,
        "read": _op_read,
        "read_available": _op_read_available,
    }

    def _op_peep_start() -> dict[str, Any]:
        if trace["n"] == 0:
            try:
                trace["fh"] = open(tracepath, "a")
            except Exception:
                trace["fh"] = None
        trace["n"] += 1
        return {"ok": True, "path": tracepath}

    def _op_peep_stop() -> dict[str, Any]:
        if trace["n"] > 0:
            trace["n"] -= 1
            if trace["n"] == 0 and trace["fh"]:
                try:
                    trace["fh"].close()
                except Exception:
                    pass
                trace["fh"] = None
                try:
                    os.unlink(tracepath)
                except OSError:
                    pass
        return {"ok": True}

    # SIGALRM fires the idle timeout in ANY blocking state (accept OR recv), so a
    # client that holds a connection open-but-idle can't pin the daemon forever.
    # SIGTERM (e.g. from reap() on a sibling, or a manual stop) cleans up too.
    signal.signal(signal.SIGALRM, _graceful)
    signal.signal(signal.SIGTERM, _graceful)
    try:
        while True:
            signal.alarm(idle)  # idle countdown while waiting to accept
            conn, _ = srv.accept()
            signal.alarm(0)
            with conn:
                try:
                    while True:
                        signal.alarm(idle)  # idle countdown while waiting for a request
                        msg = _recv_msg(conn)
                        signal.alarm(0)  # request in hand; never interrupt a command
                        if msg is None:
                            break
                        op = msg.get("op")
                        if op in session_ops:
                            try:
                                _send_msg(conn, session_ops[op](msg))
                            except Exception as e:
                                _send_msg(conn, {"error": repr(e)})
                        elif op == "ping":
                            _send_msg(conn, {"ok": True})
                        elif op == "peep_start":
                            _send_msg(conn, _op_peep_start())
                        elif op == "peep_stop":
                            _send_msg(conn, _op_peep_stop())
                        elif op == "shutdown":
                            _send_msg(conn, {"ok": True})
                            _graceful()
                        else:
                            _send_msg(conn, {"error": "unknown op %r" % op})
                except OSError:
                    pass  # client vanished mid-request; back to accept()
    finally:
        _graceful()


# ═════════════════════════════════════════════════════════════════════════════
# Command-line interface
#   helpers (host guard, open/attach, payload) -> command funcs -> argparse
# ═════════════════════════════════════════════════════════════════════════════
def _use(key: str, host: str | None = None, via: str = "et") -> DaemonClient:
    """Open KEY's session for an operation: reuse the warm daemon if it exists,
    else autospawn it on HOST (the optional --host) via the chosen transport. With
    no warm daemon and no host, exit with a hint. Shared by every session verb."""
    try:
        s = DaemonClient(key=key, host=host, via=via, autostart=host is not None)
    except RuntimeError:
        sys.exit(
            "etch: no session %r; pass --host <user@host> to start it, "
            "or run `etch open <user@host>` first" % key
        )
    if host and not s.started:
        # reused a warm daemon; refuse a --host that contradicts its real host
        live = _daemon_host(key)
        if live and live != host:
            s.close()
            sys.exit(
                "etch: session %r is live on %s, not %s; close it (`etch close %s`) "
                "or use a different key" % (key, live, host, key)
            )
    if s.started:
        sys.stderr.write(
            "(started a warm daemon for %r on %s; `close %s` to end it)\n"
            % (key, s.host, key)
        )
    return s


def _payload(key: str, secret: bool, message: str | None) -> str:
    """Source the bytes to send: -m literal, --secret (silent getpass), a stdin
    pipe, or an interactive prompt."""
    if message is not None:
        return message
    if secret:
        return getpass.getpass("secret for %s: " % key)
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return input("send to %s: " % key)


# ── CLI: command implementations (one per subcommand) ──
def _do_send(
    key: str,
    newline: bool,
    secret: bool = False,
    message: str | None = None,
    host: str | None = None,
    via: str = "et",
) -> None:
    """`send`/`sendline`: feed input into a running daemon's warm session from
    YOUR own shell. The value goes terminal -> daemon -> remote stdin and is
    never seen by the agent (not in its transcript, checkpoints, logs, cmdlog,
    or the remote shell history). With --secret it's also redacted from peep."""
    payload = _payload(key, secret, message)
    if newline and payload.endswith("\n"):
        payload = payload[:-1]  # sendline re-adds exactly one newline
    cli = _use(key, host, via)
    (cli.sendline if newline else cli.send)(payload, secret=secret)
    cli.close()
    sys.stderr.write(
        "sent %d chars to %r%s%s\n"
        % (
            len(payload),
            key,
            " + newline" if newline else "",
            " (silent, redacted in peep)" if secret else "",
        )
    )


def _cmd_expect(
    key: str,
    pattern: str,
    timeout: float = 30,
    exact: bool = False,
    host: str | None = None,
    via: str = "et",
) -> None:
    """Wait for PATTERN (a regex, or a literal with --exact). Prints the matched
    prompt line and exits 0 on a match, or exits 1 on timeout."""
    cli = _use(key, host, via)
    pat = re.escape(pattern) if exact else pattern
    out, idx = cli.expect([pat, "<<TIMEOUT>>"], timeout=timeout)
    prompt = cli.prompt
    cli.close()
    if idx == 0:
        if prompt:
            print(prompt)
        sys.exit(0)
    sys.stderr.write("(timeout after %gs waiting for %r)\n" % (timeout, pattern))
    sys.exit(1)


def _cmd_open(host: str, key: str | None = None, via: str = "et") -> None:
    key = key or _random_key()
    existing = _daemon_host(key)
    if existing and existing != host:
        sys.exit(
            "etch: key %r is already open on %s; close it or pick a different --key"
            % (key, existing)
        )
    open_session(host, key=key, via=via).close()  # spawn-or-reuse, then leave warm
    print(key)  # the handle to reuse; a printed key means the session is open


def _cmd_run(
    key: str, cmd: str, timeout: float, host: str | None = None, via: str = "et"
) -> None:
    s = _use(key, host, via)
    try:
        out, code = s.run(cmd, timeout=timeout)
    finally:
        s.close()
    if out:
        print(out)
    sys.exit(code)


def _cmd_script(
    key: str,
    path: str | None,
    timeout: float,
    host: str | None = None,
    via: str = "et",
) -> None:
    """Run a multi-line script on the warm session via run_script (line-cap-safe,
    chunked base64). Reads from FILE, or stdin if FILE is omitted or '-'."""
    text = sys.stdin.read() if path in (None, "-") else open(path).read()
    s = _use(key, host, via)
    try:
        out, code = s.run_script(text, timeout=timeout)
    finally:
        s.close()
    if out:
        print(out)
    sys.exit(code)


def _cmd_attach(key: str, host: str | None = None, via: str = "et") -> None:
    """Raw interactive terminal bridged into the warm session: drive prompts,
    REPLs, sudo, etc. live. Ctrl-] detaches (the daemon stays warm). Exclusive:
    holds the serial daemon for the whole session, so other callers (e.g. an agent
    run) block until you detach. Don't drive one session from two places at once."""
    if not sys.stdin.isatty():
        sys.exit("attach: needs an interactive terminal (stdin is not a tty)")
    s = _use(key, host, via)
    # turn the clean-room shell into a normal interactive terminal for the attach
    s.sendline(
        "stty sane 2>/dev/null; export TERM=xterm-256color PS1='[et:%s] \\w\\$ ' PS2='> '"
        % key
    )
    s.read(timeout=1.0)
    sys.stderr.write(
        "== attached to %r on %s — press Ctrl-] to detach ==\r\n" % (key, s.host or "?")
    )
    sys.stderr.flush()
    s.send("\n")  # draw a fresh prompt
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    _no_fds: list[int] = []
    try:
        tty.setraw(fd)
        while True:
            r, _, _ = select.select([fd], _no_fds, _no_fds, 0.03)
            if r:
                data = os.read(fd, 4096)
                if not data or b"\x1d" in data:  # EOF or Ctrl-] detaches
                    head = data.split(b"\x1d", 1)[0] if data else b""
                    if head:
                        s.send(head.decode("utf-8", "replace"))
                    break
                s.send(data.decode("utf-8", "replace"))
            out = s.read_available(idle=0.02)
            if out:
                sys.stdout.write(out.replace("\n", "\r\n"))  # raw tty needs CRLF
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        try:  # restore clean-room so scripted run()s keep working
            s.sendline("stty -echo -onlcr 2>/dev/null; export PS1='' PS2='' TERM=dumb")
            s.read(timeout=1.0)
        except Exception:
            pass
        s.close()
        sys.stderr.write("\r\n== detached from %r (still warm) ==\r\n" % key)
        sys.stderr.flush()


def _cmd_peep(
    key: str,
    duration: float | None = None,
    host: str | None = None,
    via: str = "et",
) -> None:
    cli = _use(key, host, via)
    path = cli.peep_start()
    cli.close()  # release the daemon: it stays serial, we just tail the file
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    suffix = (" for %gs" % duration) if duration else ""
    print(
        "== peep %r%s (» sent  « received) — Ctrl-C to stop ==" % (key, suffix),
        file=sys.stderr,
    )
    for _ in range(20):
        if path and os.path.exists(path):
            break
        time.sleep(0.1)
    deadline = (time.time() + duration) if duration else None
    try:
        with open(path) as fh:
            fh.seek(0, 2)  # only traffic from now on
            while deadline is None or time.time() < deadline:
                line = fh.readline()
                if line:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                else:
                    time.sleep(0.2)
    except (KeyboardInterrupt, FileNotFoundError):
        pass
    finally:
        try:
            DaemonClient(key=key, autostart=False).peep_stop()
        except Exception:
            pass
        print("\n== peep stopped ==", file=sys.stderr)


def _cmd_read(
    key: str,
    timeout: float | None = None,
    host: str | None = None,
    via: str = "et",
) -> None:
    """Show what the session has emitted, without attaching: a pattern-free peek.
    Default grabs whatever is buffered right now; --timeout waits for output to
    start then drains until quiet. Pairs with `send`/`sendline` for step-by-step
    interactive driving from the shell."""
    cli = _use(key, host, via)
    out = cli.read(timeout=timeout) if timeout else cli.read_available()
    cli.close()
    sys.stdout.write(out if (not out or out.endswith("\n")) else out + "\n")


def _cmd_ls() -> None:
    prefix = _user_prefix()
    socks = sorted(glob.glob(prefix + "*.sock"))
    if not socks:
        print("no etch daemons running")
        return
    now = time.time()
    print(
        "%-22s %-10s %-7s %-6s %-34s %s"
        % ("KEY", "DAEMON", "ET", "AGE", "HOST", "SOCKET")
    )
    for sk in socks:
        key = sk[len(prefix) : -5]
        dpid, epid, host = _pidfile_fields(key)
        alive = dpid.isdigit() and _alive(int(dpid))
        try:
            age = "%ds" % int(now - os.path.getmtime(sk))
        except OSError:
            age = "?"
        print(
            "%-22s %-10s %-7s %-6s %-34s %s"
            % (key, dpid + ("" if alive else "!dead"), epid, age, host or "?", sk)
        )


def _cmd_stop(key: str | None, all_: bool) -> None:
    if all_:
        keys = _live_keys()
    elif key:
        keys = [key]
    else:
        sys.exit("close: pass a KEY or --all")
    if not keys:
        print("no sessions to close")
        return
    for k in keys:
        try:
            DaemonClient(key=k, autostart=False).shutdown()
            print("closed %r" % k)
        except Exception as e:
            print("could not close %r: %s" % (k, e))


def _cmd_selftest(host: str, via: str = "et") -> None:
    t0 = time.time()
    sess = EtSession(host, via=via).connect()
    print(f"== connected in {time.time() - t0:.1f}s ==", flush=True)
    for cmd in [
        "hostname",
        "whoami",
        "pwd",
        "echo $((6*7))",
        "uname -sm",
        "echo multi; echo line; echo test",
        "false",
        "ls /nonexistent 2>&1",
    ]:
        out, code = sess.run(cmd)
        print(f"  rc={code:<3} {cmd!r:38} -> {out!r}", flush=True)
    sess.close()
    print("== done ==")


# ── CLI: argument parsing & dispatch ──
def _main_cli(argv: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(
        prog="etch",
        description="Drive a persistent EternalTerminal session to the VM: warm daemon, "
        "clean output + exit codes, interactive send/read, live peep.",
        epilog=(
            "command groups:\n"
            "  run a command:    run, script                          clean output + exit codes\n"
            "  drive a session:  attach, send, sendline, expect, read  interactive (live or step-by-step)\n"
            "  observe:          peep                                  live tap of what's sent/received\n"
            "  daemons:          open, close/stop, ls/status, gc       open / list / close warm shells\n"
            "\nexamples:\n"
            "  etch open user@vm                          prints a key; or: etch open user@vm --key main\n"
            "  etch run main uname -a                     reuse the open session\n"
            "  etch run --host user@vm main uname -a      autospawn 'main' on first use, reuse after\n"
            "  etch run main -- some-tool --timeout 5     -- makes the rest a literal command\n"
            "  etch sendline main --secret                feed a password into a parked prompt\n"
            "\nKEY is a logical handle for a session; the host lives with the daemon, not\n"
            "the key. Set it once at `open`, or pass --host on any verb to autospawn a\n"
            "session that isn't open yet (optional once it is). `ls` shows each host.\n"
            "\nlibrary: from Python, `from etch import open_session, EtSession`.\n"
            "  open_session(host, key=...) opens/reuses a warm daemon; EtSession(host) is\n"
            "  a one-shot with no daemon.\n"
            "\nadvanced: `--daemon KEY HOST IDLE` is the internal daemon worker,\n"
            "spawned automatically by open_session(); do not run it by hand.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", metavar="<command>")

    def via_arg(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--via",
            default="et",
            metavar="TRANSPORT",
            help="transport to open with: et (default), ssh, or a 'CMD {host}' template (only when starting)",
        )

    def host_arg(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--host",
            metavar="USER@HOST",
            help="autospawn the session here if it isn't open yet (optional once open)",
        )
        via_arg(sp)

    def key_arg(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("key", help="session key (a handle from `etch open`)")

    # ── run a command (clean output + exit codes) ──
    pr = sub.add_parser(
        "run",
        help="run one command on the session (open it first, or --host to autospawn); exit code = remote rc",
    )
    pr.add_argument("--timeout", type=float, default=60)
    host_arg(pr)
    key_arg(pr)
    pr.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="the command (rest of the line, flags and all); etch's own options go "
        "before the key, or put `--` first for a fully literal command",
    )

    psc = sub.add_parser(
        "script",
        help="run a multi-line script (from FILE or stdin) on the warm session; exit code = remote rc",
    )
    psc.add_argument("--timeout", type=float, default=180)
    host_arg(psc)
    key_arg(psc)
    psc.add_argument("file", nargs="?", help="script file (default: stdin)")

    # ── drive a session interactively (live, or step-by-step send/expect/read) ──
    pat = sub.add_parser(
        "attach",
        help="interactive terminal bridged into the warm session: prompts/REPLs/sudo, Ctrl-] detaches (exclusive until you detach)",
    )
    host_arg(pat)
    key_arg(pat)

    for name, nl in (("send", False), ("sendline", True)):
        sp = sub.add_parser(
            name,
            help=(
                "%s to the session (%s); -m TEXT, --secret (silent), or stdin"
                % (name, "appends a newline" if nl else "raw, no newline")
            ),
        )
        sp.add_argument("key", help="session key to send to")
        host_arg(sp)
        sp.add_argument(
            "-s",
            "--secret",
            action="store_true",
            help="read the payload via a silent no-echo prompt",
        )
        sp.add_argument(
            "-m",
            "--message",
            help="payload on the command line (visible; not for secrets)",
        )

    pex = sub.add_parser(
        "expect",
        help="wait for a regex (or literal with --exact) to appear; exit 0 on match, 1 on timeout",
    )
    pex.add_argument("key", help="daemon key to watch")
    pex.add_argument("pattern", help="regex to wait for (literal if --exact)")
    pex.add_argument(
        "--timeout",
        type=float,
        default=30,
        metavar="SECS",
        help="give up after SECS (default 30)",
    )
    pex.add_argument(
        "--exact", action="store_true", help="match PATTERN literally, not as a regex"
    )
    host_arg(pex)

    prd = sub.add_parser(
        "read",
        help="drain session output without attaching: bare = peek what's buffered now (read_available), --timeout = wait for output then drain (read)",
    )
    prd.add_argument("key", help="daemon key to read from")
    prd.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECS",
        help="wait up to SECS for output to start, then drain until quiet "
        "(default: just grab what's buffered now)",
    )
    host_arg(prd)

    # ── observe ──
    ppe = sub.add_parser(
        "peep", help="live tap: show what's sent/received on the session"
    )
    ppe.add_argument("key", help="daemon key to tap")
    ppe.add_argument(
        "--for",
        dest="duration",
        type=float,
        default=None,
        metavar="SECS",
        help="auto-stop after SECS (for non-interactive/scripted taps)",
    )
    host_arg(ppe)

    # ── sessions: open / close ──
    po = sub.add_parser(
        "open",
        help="open a session on HOST (pre-warm); prints the key to reuse with run/send/...",
    )
    po.add_argument("host", metavar="USER@HOST", help="user@host to connect")
    po.add_argument("--key", help="name for the session (default: a random handle)")
    via_arg(po)

    for nm, h in (
        ("close", "close a session (shut down its daemon)"),
        ("stop", "alias for close"),
    ):
        psx = sub.add_parser(nm, help=h)
        psx.add_argument("key", nargs="?", help="session key to close (or use --all)")
        psx.add_argument(
            "--all", action="store_true", help="close every running session"
        )

    # ── inspect / maintain ──
    sub.add_parser("ls", help="list running sessions")
    sub.add_parser("status", help="alias for ls")
    sub.add_parser("gc", help="reap dead daemons / orphaned et processes")
    pse = sub.add_parser(
        "selftest", help="connect to HOST and run a few sample commands"
    )
    pse.add_argument("host", metavar="USER@HOST", help="user@host to connect")
    via_arg(pse)

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return
    if args.cmd == "run":
        cmd = " ".join(args.command).strip()
        if not cmd:
            sys.exit("run: no command given")
        if "--" not in argv:
            _flags = ("--timeout", "--host", "--via")
            stray = [
                t
                for t in args.command
                if t in _flags or any(t.startswith(f + "=") for f in _flags)
            ]
            if stray:
                sys.stderr.write(
                    "etch: note: %s is inside the command, not applied as an option. "
                    "etch's flags go before the key (e.g. `run --timeout 5 KEY ...`); "
                    "use `--` for a command that legitimately contains them.\n"
                    % ", ".join(stray)
                )
        _cmd_run(args.key, cmd, args.timeout, args.host, args.via)
    elif args.cmd == "script":
        _cmd_script(args.key, args.file, args.timeout, args.host, args.via)
    elif args.cmd == "open":
        _cmd_open(args.host, args.key, args.via)
    elif args.cmd == "attach":
        _cmd_attach(args.key, args.host, args.via)
    elif args.cmd in ("send", "sendline"):
        _do_send(
            args.key,
            args.cmd == "sendline",
            args.secret,
            args.message,
            args.host,
            args.via,
        )
    elif args.cmd == "expect":
        _cmd_expect(
            args.key, args.pattern, args.timeout, args.exact, args.host, args.via
        )
    elif args.cmd == "peep":
        _cmd_peep(args.key, args.duration, args.host, args.via)
    elif args.cmd == "read":
        _cmd_read(args.key, args.timeout, args.host, args.via)
    elif args.cmd in ("ls", "status"):
        _cmd_ls()
    elif args.cmd in ("close", "stop"):
        _cmd_stop(args.key, args.all)
    elif args.cmd == "gc":
        reap()
        print("reaped stale etch daemons/orphans")
    elif args.cmd == "selftest":
        _cmd_selftest(args.host, args.via)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--daemon":  # internal worker, spawned by DaemonClient._start
        _daemon_main(a[1], a[2], a[3], int(a[4]))
        sys.exit(0)
    _main_cli(a)
