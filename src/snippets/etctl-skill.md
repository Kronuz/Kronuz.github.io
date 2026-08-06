---
name: remote-machine
description: Drive a remote machine over Eternal Terminal with etctl. Use for a persistent remote shell, running commands, answering interactive prompts, or moving files to and from a remote host.
---

# Driving a remote machine with etctl

`etctl` opens a named Eternal Terminal session in the background and lets you send
it input and read its output over a local Unix socket. No tty needed. Output comes
back verbatim, with the command's real exit code.

Before connecting, know the target's user, host, and how it authenticates.

## Open one session and keep it

```bash
NM=work-$(openssl rand -hex 3)          # generate once, reuse this exact name
H=user@host
etctl open "$NM" "$H" -c 'export PAGER=cat GIT_PAGER=cat SYSTEMD_PAGER=cat'
echo "etctl session: $NM"               # tell the user, so they can observe/attach
```

- **Reuse the session for the whole task.** The connection costs about 13 seconds
  once, then the working directory, environment, and warm caches persist. `open` is
  idempotent.
- **Reuse the literal name, not a shell variable.** If each command runs in a fresh
  shell, `$NM` will not survive between them.
- **One driver per session.** Two actors sharing a name interleave bytes and corrupt
  each other's input. Give every actor its own name.
- **Leave it open.** `etctl gc` clears dead sockets; `etctl key NAME eof` ends a
  session deliberately.

## The verbs

`etctl` lists them; `etctl <verb> --help` explains one. Flags go after the verb
(`etctl run --timeout 5 NAME '...'`).

| Verb | For |
| --- | --- |
| `run NAME 'cmd'` | A command that finishes. Verbatim output, real exit code. |
| `read` / `expect` / `wait` | Read output, wait for a pattern, wait for quiet. |
| `write` / `writeln` | Inject bytes or a line. `writeln --secret` for a password. |
| `key` | Named keys and signals (`interrupt` is Ctrl-C, `eof` is Ctrl-D). |
| `sniff` | Tap the raw byte exchange, sent and received. |
| `observe` / `attach` | Put a human at the wheel. |
| `sessions` / `info` / `gc` | Status and cleanup. |

`run` takes one quoted argument and **multi-line bodies are fine**: it groups the
block, so a `cd` or `export` inside it persists. Output is eight-bit clean, so the
PTY's carriage returns come through; strip them when capturing a value:

```bash
v=$(etctl run "$NM" 'hostname' | tr -d '\r')
```

## Interactive prompts

A bare `expect` scans from the current head, so in a tight write-then-wait loop the
text you are waiting for can land in the gap. Capture the cursor first:

```bash
C=$(etctl info "$NM" | sed -n 's/^headCursor=//p')
etctl writeln "$NM" "printf 'Q? '; read a; echo GOT=\$a"
etctl expect  "$NM" 'Q\? $' --cursor "$C" --timeout 10
```

For a password prompt raised mid-command, never send another `run` while the first
is parked, because it becomes the answer. Pre-authenticate (`sudo -v`) when you can,
or park the command and let a human answer with `etctl writeln NAME --secret`, which
keeps the value out of the transcript.

## Moving a file

There is no transfer verb, and for anything large the right tool is an Eternal
Terminal port-forward tunnel (`etctl open NAME HOST -t LOCAL:REMOTE`), not the
terminal. For an ordinary file, wrap the byte stream in matching `stty raw -echo`
modes so the roughly 4 KiB line cap, CR/NL translation, and flow-control bytes are
out of the way, then restore the saved mode. This is byte-exact, no base64, and the
practical ceiling is about 2 MiB of scrollback each way.

**Push.** Wait for `READY` so the first bytes cannot hit a cooked shell:

```bash
LOCAL=./app.bin; REMOTE='~/app.bin'
N=$(wc -c < "$LOCAL" | tr -d ' ')
C=$(etctl info "$NM" | sed -n 's/^headCursor=//p')
etctl writeln "$NM" "O=\$(stty -g); stty raw -echo; echo READY; head -c $N > $REMOTE; stty \"\$O\""
etctl expect  "$NM" 'READY\r?\n' --cursor "$C"
etctl write   "$NM" < "$LOCAL"
etctl wait    "$NM" --idle 1.0 --timeout 120
etctl run     "$NM" "sha256sum $REMOTE | cut -d' ' -f1"; shasum -a 256 "$LOCAL"
```

**Pull.** `run` is verbatim, so redirect it:

```bash
etctl run "$NM" "O=\$(stty -g); stty raw -echo; cat '$REMOTE'; stty \"\$O\"" > "$LOCAL"
```

`head -c N` reads exactly the length announced, so nothing inside the file can pose
as a terminator. **Always verify with a hash.** The exit code you get back is
`stty`'s, not `cat`'s, and comparing file sizes proves nothing, because a CR/NL
translation substitutes bytes rather than adding them.

## Watch out for

- **Pagers wedge the session.** `git`, `systemctl`, and `less` all open one and hang.
  The `-c` on `open` above neutralizes them.
- **Do not background inside `run`** (`cmd &`). It confuses the framing. Use a real
  service manager for a detached job and poll its log.
- **Do not put `exit` in a `run`.** It ends the remote shell. Test exit codes with
  `sh -c 'exit 7'`.
- **`read -p` is a bash idiom.** Under zsh it errors out and your `expect` waits the
  full timeout. Use `printf 'Q? '; read a`.
- **Restarting the remote `et` server ends the session.** Reconnect under a new name.

When something looks wrong, `etctl sniff NAME` shows what actually crossed the wire
(`»` sent, `«` received), which is almost always faster than guessing. `etctl info
NAME` shows whether the session is alive and connected.
