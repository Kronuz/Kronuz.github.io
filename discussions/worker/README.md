# discussions Worker (Hono + Cloudflare D1)

A port of the self-hosted comments backend (`../backend`, FastAPI + SQLite) to a
Cloudflare Worker on **Hono** with **D1** as the system of record. Self-hosted store only
(the `github` store is not ported); sessions are stateless signed cookies. The store is
multi-tenant, but for now it serves a single blog (Kronuz.github.io) — the `default`
tenant, self-seeded from env; adding another blog later is one more tenant row.

## What maps to what

| Python (`../backend/discussions`) | here (`src/`) |
| --- | --- |
| `db/base.py` + `db/sqlite.py` (aiosqlite) | `db.ts` (D1 prepared statements) |
| `store/selfhosted.py` + `store/base.py` | `store.ts` |
| `md.py` (cmark-gfm + Pygments) | `md.ts` (unified: remark-gfm + rehype-sanitize + Shiki) |
| `sessions.py` (CookieSessionStore) | `sessions.ts` (HMAC via WebCrypto, identity only) |
| `tenants.py` (DbTenants) | `tenants.ts` (loaded per request from D1) |
| `auth.py` + `gh.py` | `index.ts` (routes) + `gh.ts` |
| `app.py` + `comments.py` + `reactions.py` + `ratelimit.py` | `index.ts` + `ratelimit.ts` |
| `config.py` | `config.ts` + `wrangler.toml` |
| runtime schema/PRAGMA migrations | `migrations/0001_init.sql` (fresh, final DDL) |

## Deliberate changes for the edge

- **No lifespan/startup.** `runtime.py` built singletons at boot; here each request builds
  the D1 `Database`, loads the tenant registry, and constructs the session/store from
  `c.env`. Cheap wrappers.
- **No background tasks.** No session sweeper (stateless cookies) and no tenant-cache
  refresher (the registry is read per request).
- **Markdown renderer swapped.** cmark-gfm (C) and Pygments (Python) don't run on Workers.
  `md.ts` uses the unified remark/rehype pipeline, GFM-spec compatible, with
  `rehype-sanitize` (its default schema is GitHub's own allow-list) for XSS safety.
  Highlighting is **Shiki**, reusing the blog's own Kronuz themes (kronuz-light/dark) via
  the fine-grained core + pure-JS regex engine (no WASM) and a curated language set, so
  comment code is pixel-identical to the article code blocks. Dual-theme output uses
  `--shiki-dark` CSS variables, so `highlight.css` only flips light/dark (no token table).
  Shiki runs after sanitize (it styles already-safe code); the result is cached in D1, so
  it renders once per add/edit. Whole bundle: **362 KiB gzipped** (free-tier limit 1 MB).
- **Rate limiting is per-isolate best-effort** (see `ratelimit.ts`). For a hard global
  limit use the Cloudflare Rate Limiting binding or a Durable Object.

## Run it locally

```bash
npm install
npm run migrate:local        # apply migrations to local (miniflare) D1
npm run seed:local           # optional: seed the default (Kronuz.github.io) tenant
npm run dev                  # wrangler dev on http://localhost:8787
```

Secrets for local dev live in `.dev.vars` (not committed): `SESSION_SECRET`,
`OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`.

## Deploy

```bash
wrangler d1 create discussions          # paste database_id into wrangler.toml
npm run migrate:remote
wrangler secret put SESSION_SECRET
wrangler secret put OAUTH_CLIENT_ID
wrangler secret put OAUTH_CLIENT_SECRET
npm run deploy
```

Point the widget at the deployed URL via its `data-backend` attribute.

## Status

Spike. The full API surface is ported and verified against local D1: health, `/api/me`,
`/api/config`, per-origin tenant resolution, origin enforcement, comment CRUD, threaded
replies, reactions, preview, admin-only hide, sanitized Markdown, Shiki-highlighted code
(matching the site's themes), and cookie sign/verify/expiry. Not yet done: real OAuth
round-trip against a registered GitHub app, and an admin path for tenant onboarding (the
Python `admin.py` CLI).
