# Kronuz.github.io

My personal blog and project notes — Python, C++, and systems at scale.

**Live:** <https://kronuz.github.io>

Built with [Astro](https://astro.build) + [Starlight](https://starlight.astro.build) +
[starlight-blog](https://github.com/HiDeoo/starlight-blog), with a custom *Kronuz* code
theme, build-time [D2](https://d2lang.com) diagrams, and a multi-tenant comments Worker.
It deploys itself: push to the default branch and GitHub Actions builds and
publishes to GitHub Pages.

## Local development

```bash
npm install
npm run dev       # local dev server with hot reload
npm run build     # build to dist/
npm run preview   # serve the built dist/ locally
```

D2 diagrams render at build time by shelling out to the `d2` CLI, so install it locally if
you write `​```d2` fences: <https://d2lang.com/tour/install>. CI installs it automatically.

## Writing a post

1. Add `src/content/docs/blog/<slug>.md` with frontmatter:
   ```yaml
   ---
   title: "Post title"
   description: "One-line summary."
   date: 2026-06-07
   draft: true        # remove (or run npm run publish) when ready
   authors: kronuz
   tags: [python, systems]
   ---
   ```
2. Preview with `npm run dev` (drafts show with a yellow badge).
3. Publish: `npm run publish -- <slug>` — drops `draft`, stamps `date` to today, commits,
   and pushes. GitHub Actions builds and deploys automatically.

## Code blocks

Fenced blocks render through [Expressive Code](https://expressive-code.com/), which
frames each by language: a **terminal window** for the shell languages (`sh`, `bash`,
`zsh`, `ansi`, `console`, …) and an **editor** (a file tab when titled) for everything
else. Override per block with `frame="terminal"`, `frame="code"`, or `frame="none"`, and
set the title with `title="..."`. An `ansi` block renders raw terminal output in real colors.

## Comments

Comments use the shared Cloudflare Worker and D1 service in `discussions/`. The public
tenant base URL is configured as `DISCUSSIONS_BACKEND` in `src/consts.ts`. See
`discussions/worker/TUTORIAL.md` for deployment and tenant setup, and
`discussions/worker/OPERATIONS.md` for routine maintenance.

## Deploy

`.github/workflows/deploy.yml` builds on every push to the default branch (installs D2,
`npm ci`, `npm run build`) and deploys to Pages via `actions/deploy-pages`. No manual step.
