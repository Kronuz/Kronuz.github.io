# Discussions backend

A small FastAPI app serving blog comments. See `../README.md` for the overview and
`.env.example` for every setting.

## Run

```sh
pip install -r requirements.txt
cp .env.example .env        # then fill in OAUTH_CLIENT_ID/SECRET, REPO, ...
./run.sh                    # 127.0.0.1:8099 (set HOST/PORT, or SSL_* for HTTPS)
```

## Stores (`DISCUSSIONS_BACKEND`)

- `sqlite` (default) — self-hosted system of record in `discussions.db`; OAuth only
  identifies the reader. Needs a persistent disk.
- `github` — real GitHub Discussions via GraphQL; the reader's own token writes
  (authentic authorship), a `GITHUB_READ_TOKEN` reads for signed-out visitors.
  Stateless (no database), so it runs fine on a serverless tier. Needs the `repo`
  OAuth scope so the reader's token can write Discussions.

The `Store` interface (`discussions/store/base.py`) keeps the two swappable; the
routes are thin wrappers over the active store.
