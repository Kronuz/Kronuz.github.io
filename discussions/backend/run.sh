#!/usr/bin/env bash
# Run the comments backend. Loads ./.env (if present), then starts uvicorn. Usage:
#   ./run.sh                # 127.0.0.1:8099 (local)
#   HOST=0.0.0.0 PORT=8443 ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

# Prefer a modern Python; many systems ship one here.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x /export/apps/python/3.12/bin/python3 ]; then PY=/export/apps/python/3.12/bin/python3
  else PY=python3; fi
fi

if [ ! -d .venv ]; then
  echo "Creating venv with $PY ($($PY --version 2>&1))"
  "$PY" -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

# shellcheck disable=SC1091
set -a; [ -f .env ] && . ./.env; set +a

# TLS: if a cert + key are configured, serve HTTPS. A browser on an HTTPS page
# (GitHub Pages) can only fetch an HTTPS backend, so production needs these set
# (see install.sh / README). Local 127.0.0.1 testing can leave them unset.
SSL_ARGS=()
if [ -n "${SSL_CERTFILE:-}" ] && [ -n "${SSL_KEYFILE:-}" ]; then
  SSL_ARGS=(--ssl-certfile "$SSL_CERTFILE" --ssl-keyfile "$SSL_KEYFILE")
fi

# The app is fully async, so run it on uvloop + httptools (both ship with
# uvicorn[standard]) for the fast event loop and HTTP parser.
#
# uvicorn's own stdout/stderr carries startup errors that happen BEFORE the app
# configures logging (bad TLS path, port in use, import error). Under systemd those
# would only reach the journal, which isn't readable on the host, so redirect the
# whole server (uvicorn + the app, which logs to stdout) to one file. An interactive
# run still prints to the console.
LOG_FILE="${LOG_FILE:-$PWD/discussions.log}"
if [ -t 1 ]; then
  exec ./.venv/bin/uvicorn discussions.app:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8099}" \
    --loop uvloop --http httptools "${SSL_ARGS[@]}"
fi
echo "=== $(date -Is) starting uvicorn host=${HOST:-127.0.0.1} port=${PORT:-8099} ssl=${SSL_CERTFILE:+on} ===" >> "$LOG_FILE"
exec ./.venv/bin/uvicorn discussions.app:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8099}" \
  --loop uvloop --http httptools "${SSL_ARGS[@]}" >> "$LOG_FILE" 2>&1
