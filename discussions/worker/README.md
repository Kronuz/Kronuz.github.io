# discussions

Self-hosted blog comments as a Cloudflare Worker (Hono + D1). A giscus-style widget talks
to it: readers sign in with GitHub for identity, and comments, replies, reactions, edits,
and moderation live in D1. Markdown is rendered and syntax-highlighted server-side.

It is multi-tenant (one deployment can host several blogs, keyed by request origin), and
currently serves a single blog, Kronuz.github.io.

## Features

- **GitHub sign-in** for identity only (scope `read:user`; no repo access).
- **Threaded comments** (one level of replies), edits, and deletes.
- **Reactions** — GitHub's eight emoji, one per verified user per comment.
- **Moderation** — a tenant's moderators can hide (with a reason) or delete any comment.
- **GitHub Flavored Markdown**, sanitized with `rehype-sanitize` (GitHub's own allow-list),
  so raw HTML is dropped and dangerous URL schemes are neutralized.
- **Syntax highlighting** with Shiki using the site's own themes (`src/themes/kronuz-*.json`);
  light/dark is handled with CSS variables, so it follows the page theme.
- **Multi-tenant** — comments/reactions/threads are scoped per blog, resolved from the
  request `Origin`; per-tenant moderators and widget config.
- **Stateless sessions** — an HMAC-signed cookie carries the reader's identity, so there is
  no session table and no server-side session state (good for the edge).
- **Per-origin CORS + origin enforcement** and sliding-window rate limits.

## Layout

```
src/
  index.ts      Hono app: middleware (CORS, origin enforcement, size limit) + all routes
  config.ts     env bindings + effective config
  db.ts         D1 driver (comments, reactions, discussions, tenants)
  store.ts      comment logic + authorization; the API comment shape
  md.ts         Markdown -> sanitized, Shiki-highlighted HTML
  sessions.ts   stateless signed-cookie sessions (WebCrypto HMAC)
  tenants.ts    tenant registry: origin -> tenant, moderators, widget config (from D1)
  gh.ts         GitHub OAuth token exchange + identity lookup
  ratelimit.ts  per-isolate sliding-window limiter
  themes/       Shiki themes used to highlight comment code
migrations/     D1 schema
wrangler.toml   bindings + non-secret vars
deploy.sh       guided, re-runnable production deploy
```

D1 tables: `tenants`, `tenant_admins`, `discussions`, `comments`, `reactions`. (Sessions are
cookies, so there is no session table.)

## Install (local development)

```bash
npm install
cp .dev.vars.example .dev.vars     # then edit if you want sign-in locally
npm run migrate:local              # apply the schema to a local (miniflare) D1
npm run seed:local                 # optional: seed the default tenant deterministically
npm run dev                        # http://localhost:8787
```

`.dev.vars` (gitignored) holds local secrets/overrides; `.dev.vars.example` documents them.

## Configure

**Non-secret settings** live in `wrangler.toml` under `[vars]`:

| var | meaning |
| --- | --- |
| `REPO`, `SITE_URL`, `REPO_URL` | the blog this deployment serves (seed the default tenant) |
| `ALLOWED_ORIGINS` | comma-separated site origins allowed to call the API |
| `ADMIN_LOGINS` | comma-separated GitHub logins that moderate the default tenant |
| `PUBLIC_BASE_URL` | this Worker's public URL (the OAuth redirect base) — set at deploy |
| `OAUTH_SCOPE` | `read:user` (identity only) |
| `COOKIE_CROSS_SITE` | `1` in prod (blog and Worker are different sites → `SameSite=None; Secure`); `0` for same-site localhost dev |
| `MAX_BODY`, `REQUEST_MAX_BYTES`, `SESSION_TTL` | limits |

**Secrets** (production) are set with `wrangler secret put NAME`, done for you by `deploy.sh`:
`SESSION_SECRET` (signs the session cookie), `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`. For
local dev these go in `.dev.vars` instead.

### GitHub OAuth App

Create one at <https://github.com/settings/developers> → **New OAuth App**:

- **Homepage URL:** `https://kronuz.github.io`
- **Authorization callback URL:** `<PUBLIC_BASE_URL>/auth/callback`
  (for local dev: `http://localhost:8787/auth/callback`)

The scope is `read:user` — sign-in learns who the reader is, nothing more. Put the Client ID
and a generated client secret into the secrets above (`deploy.sh` prompts for them) or into
`.dev.vars` for local testing.

### GIF picker (optional)

The comment composer shows a GIPHY GIF picker when the tenant has a `giphy_key`. It's a
public key (served to browsers via `/api/config`, and the browser calls GIPHY directly with
rating forced to `g`), so use one you're comfortable exposing on a public site. `deploy.sh`
prompts for it; to set or change it later:

```bash
wrangler d1 execute discussions --remote \
  --command "UPDATE tenants SET giphy_key='YOUR_GIPHY_KEY' WHERE id='default'"
```

Leave it empty to hide the picker.

### New-comment notifications (optional)

By default a new comment just lands in D1 and nothing tells you. Two opt-in ways to know:

- **Webhook ping** — set `NOTIFY_KIND` in `wrangler.toml` to `slack`, `discord`, or `telegram`,
  and store the destination as the `NOTIFY_WEBHOOK` secret (`wrangler secret put NOTIFY_WEBHOOK`).
  On each new comment the Worker POSTs a short *"New comment by X on <post>"* message to it,
  fire-and-forget (via `waitUntil`, so it never delays the commenter). For Telegram, use the bot
  `https://api.telegram.org/bot<token>/sendMessage` URL and also set `NOTIFY_TELEGRAM_CHAT` in
  `[vars]`. Unset `NOTIFY_WEBHOOK` = disabled.
- **Private Atom feed** — set the `NOTIFY_FEED_TOKEN` secret, then subscribe your RSS reader to
  `<Worker URL>/api/comments/feed?token=<token>`. It lists the tenant's most recent (non-hidden)
  comments, newest first, each linking to its post. Without a valid token the endpoint 404s (so
  it doesn't exist for anyone else). RSS readers send no `Origin`, so origin enforcement doesn't
  block them.

`deploy.sh` prompts for both secrets.

## Deploy

```bash
npx wrangler login     # once
./deploy.sh
```

`deploy.sh` is idempotent and walks the whole path: create the D1 database, apply
migrations, generate `SESSION_SECRET`, deploy, print the Worker URL and the exact OAuth
callback to register, set the OAuth secrets, set `PUBLIC_BASE_URL`, and redeploy. The
default tenant is seeded automatically from `SITE_URL` / `REPO` / `ADMIN_LOGINS` on the
first request, so there's nothing to seed by hand.

Manual equivalent:

```bash
wrangler d1 create discussions                      # paste database_id into wrangler.toml
wrangler d1 migrations apply discussions --remote
wrangler secret put SESSION_SECRET
wrangler secret put OAUTH_CLIENT_ID
wrangler secret put OAUTH_CLIENT_SECRET
# set PUBLIC_BASE_URL in wrangler.toml to the Worker's URL
wrangler deploy
```

## Use it (wire the widget)

The blog embeds the comments widget and points it at this Worker with a `data-backend`
attribute (in this repo, set `DISCUSSIONS_BACKEND` in `src/consts.ts` to the Worker URL).
Each page passes a `term` (its slug); the Worker stores that page's thread under it. The
widget calls the API with `credentials: include`, so the session cookie rides along.

## Dev test

```bash
curl localhost:8787/api/health
curl -H 'Origin: http://localhost:4321' localhost:8787/api/config
```

Authenticated endpoints need a session: sign in through the widget (set the OAuth creds in
`.dev.vars`), or mint a dev cookie (`sessions.ts`'s HMAC format) for scripted tests.

## API

| method + path | body / query | notes |
| --- | --- | --- |
| `GET /api/health` | — | liveness |
| `GET /api/me` | — | current identity + admin flag |
| `GET /api/config` | — | per-tenant widget config (resolved from Origin) |
| `GET /api/discussions` | `?term=&after=&first=` | a page's thread |
| `GET /api/comments/feed` | `?token=` | owner's private Atom feed of recent comments (`NOTIFY_FEED_TOKEN`) |
| `POST /api/comments` | `{body, term, title?, subtitle?, url?, reply_to_id?}` | add a comment/reply |
| `POST /api/comments/edit` | `{comment_id, body}` | author or moderator |
| `POST /api/comments/delete` | `{comment_id}` | author or moderator |
| `POST /api/comments/hide` | `{comment_id, hide, reason?}` | moderators |
| `POST /api/preview` | `{text}` | rendered HTML (signed-in) |
| `POST /api/react` | `{comment_id, content, on}` | toggle a reaction |
| `GET /auth/login`, `GET /auth/callback`, `POST /auth/logout` | — | OAuth + session cookie |

## Adding another blog later

Everything is scoped by tenant and resolved from the request `Origin`, so hosting a second
blog is one more tenant row (its origin → repo + moderators) — no structural change.

## Notes

- Rate limiting is per-isolate best-effort; for a hard global limit, use Cloudflare's Rate
  Limiting binding or a Durable Object.
- The deployed bundle is ~362 KiB gzipped (Cloudflare's free-tier limit is 1 MB).
