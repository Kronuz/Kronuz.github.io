# Discussions backend

A small FastAPI app serving blog comments. See `../README.md` for the overview and
`.env.example` for every setting.

## Run

```sh
pip install -r requirements.txt   # the selfhosted (sqlite) form; installs .[sqlite]
cp .env.example .env              # then fill in OAUTH_CLIENT_ID/SECRET, REPO, ...
./run.sh                          # 127.0.0.1:8099 (set HOST/PORT, or SSL_* for HTTPS)
```

For the `github` store, install the lean core instead (no database/Markdown deps):

```sh
pip install .[github]             # fastapi + uvicorn + httpx only
STORE=github ./run.sh
```

## Stores (`STORE`)

- `selfhosted` (default) — self-hosted system of record in a Database (`DATABASE=sqlite`,
  in `discussions.db`); OAuth only identifies the reader and Markdown is rendered locally.
  Needs a persistent disk; install the `[sqlite]` extra.
- `github` — real GitHub Discussions via GraphQL; the reader's own token writes
  (authentic authorship), a `GITHUB_READ_TOKEN` reads for signed-out visitors, and
  Markdown previews via GitHub's API. Stateless (no database) and lean (core deps only),
  so it runs fine on a serverless tier. Needs the `repo` OAuth scope.

The `Store` interface (`discussions/store/base.py`) keeps the two swappable; the routes
are thin wrappers over the active store. The backend is split into four such seams —
`Store`, `Database` (`db/`), `SessionStore` (`sessions.py`), `TenantRegistry`
(`tenants.py`) — wired by `runtime.py`, so adding a database (e.g. MySQL) or another
store is one new file. `DISCUSSIONS_BACKEND=sqlite|github` is kept as a back-compat
alias for `STORE`.
