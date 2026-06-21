# Discussions — a self-hosted comments widget (a giscus alternative)

A framework-free comment widget (`widget/`) plus a small FastAPI backend
(`backend/`) for blog comments backed by GitHub. Sign-in is GitHub OAuth; Markdown is
rendered with GitHub's own renderer (cmark-gfm) so bodies match GitHub.

> **Status on this blog: present but not enabled.** This blog currently uses
> [giscus](https://giscus.app). The widget + backend live here so the full solution is
> versioned and ready to switch on; nothing renders until a `Discussions` component is
> wired into the post layout (see "Enabling" below).

## Two store backends

The backend keeps the commenting system behind a swappable `Store` interface
(`backend/discussions/store/`), selected by `DISCUSSIONS_BACKEND`:

- **`sqlite`** — a self-hosted system of record (comments, replies, edits, hides,
  reactions in SQLite). OAuth is used only to learn who the reader is. Works anywhere,
  owns its data, needs no special GitHub permissions.
- **`github`** — real **GitHub Discussions** via GraphQL. The reader's own OAuth token
  writes, so comments and reactions are authentically authored by them (their
  avatar/name, editable on GitHub, native reactions) — like giscus, but with this
  widget's UI. Reads use a server token for signed-out visitors. Use this for a repo
  you own; an organization that restricts OAuth Apps blocks reader-token writes, where
  `sqlite` is the fallback.

## Enabling (when you want to switch off giscus)

1. Register a GitHub **OAuth App** (or GitHub App) for this site and set
   `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET`. For the `github` backend the sign-in
   scope is `repo` (the config default) so the reader's token can write Discussions.
2. For the `github` backend, also set `GITHUB_READ_TOKEN` (a fine-grained PAT with
   Discussions:read) for signed-out reads, plus `REPO` and `DISCUSSION_CATEGORY`.
3. Deploy the backend (`backend/run.sh`, or any ASGI host). The `github` backend is
   **stateless** (no database), so a free serverless tier works; `sqlite` needs a
   persistent disk.
4. Add a `Discussions.astro` component that renders `widget/` pointed at the deployed
   backend URL, and include it in the post layout (in place of `Giscus`). See
   `widget/README.md` for the widget's data-attributes.

## Layout

```
widget/     framework-free widget (JS/CSS) — the UI; auto-mounts every .gc[data-term]
backend/    FastAPI backend: OAuth, the Store interface, SQLite + GitHub backends
  discussions/store/  base.py (interface) · sqlite.py · github.py
  .env.example        every setting, documented
```

See `widget/README.md` for embedding the widget and `backend/.env.example` for the
full backend configuration.
