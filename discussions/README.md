# Discussions

A framework-free comment widget (`widget/`) plus a small Cloudflare Worker backend
(`worker/`, Hono + Cloudflare D1) for public blog comments. Each tenant configures its own
OAuth provider for identity; Markdown is rendered and syntax-highlighted server-side with Shiki
using the blog's own themes, so comment code matches the article code blocks.

## Layout

```
widget/     framework-free widget (JS/CSS) — the UI; auto-mounts every .gc[data-term]
worker/     Cloudflare Worker backend (Hono + D1): OAuth, comments, replies,
            reactions, moderation, Markdown rendering; multi-tenant, keyed by URL path
```

The widget is backend-agnostic: it reads and writes through whatever `data-backend` URL it
is given (set `DISCUSSIONS_BACKEND` in `src/consts.ts`, or `PUBLIC_DISCUSSIONS_BACKEND` for
local dev). The reader's identity rides as an `Authorization: Bearer` token, stashed in
localStorage after the OAuth redirect so sign-in works on mobile Safari (where cross-site
cookies are blocked), with the session cookie as a fallback.

See `worker/README.md` for the backend (features, D1 schema, configuration, deploy) and
`widget/README.md` for embedding the widget and its data-attributes.

The backend URL includes the tenant, for example
`https://discussions.kronuz.workers.dev/kronuz`. See `worker/README.md` for the
complete configuration and deployment contract.

Tenants with an empty `accessKey` are public. A non-empty key is a static capability sent
by the widget in `X-Discussions-Key`; see the Worker tutorial for generation and rollout.
