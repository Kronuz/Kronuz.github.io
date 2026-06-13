# AGENTS.md: Kronuz.github.io

Agent handoff for this repo. The human-facing overview is in `README.md`; this file
captures the conventions and the non-obvious gotchas an agent needs to not break things.

## What this is

German's personal blog (`https://kronuz.github.io`). Astro + Starlight + starlight-blog,
a custom *Kronuz* code theme, build-time D2 diagrams, giscus comments. Self-deploying:
push to the default branch and GitHub Actions builds and publishes to Pages
(`.github/workflows/deploy.yml`).

- Working branch: `gmendezb/astro-rebuild` (unpushed; publishing is Phase-5 gated).
- Posts live in `src/content/docs/blog/<slug>.md`. Schema: `src/content.config.ts`.

## Frontmatter conventions

```yaml
---
title: "Short title"                 # keep titles short; long ones were trimmed
subtitle: "One line under the title"
description: "SEO/meta description, a real sentence."
excerpt: "Shown in the blog list; lead with the hook."
date: 2026-06-08
draft: true                          # drafts are EXCLUDED from the build (see below)
series: "Opening Boxes"              # optional: groups posts into a series
seriesOrder: 3                       # optional: position within the series
tags:
  - opening-boxes
---
```

Series posts are **frontmatter-driven**: every part sets the same `series:` name and a
`seriesOrder:`, and the series UI (a right-sidebar stepper, a mobile "Part N of M" chip,
and prev/next series pagers) is rendered automatically. There is no hub page and no manual
"part of the series" line in the body.

- **Ordering:** `seriesOrder` ascending, then `date`, then `title`. Omit `seriesOrder`
  when the dates already run in order; set it when they collide or don't match the
  narrative. It defaults to 0.
- **"Part N of M" counts published + upcoming parts.** Drafts are otherwise hidden.
- **Tease a draft with `upcoming: true`.** On a *draft* part, `upcoming: true` shows it
  greyed and un-linked in the stepper (a "disabled" item) instead of hiding it. A plain
  draft stays hidden; a published part ignores `upcoming`. No "soon" label, just the
  greyed item.
- **One visible part is not a series** (no box, no pager) until a second is published or
  teased.

The resolver and UI are shared byte-for-byte with the internal blog (`lib/series.mjs`,
`TableOfContents.astro`, the series bits of `MarkdownContent.astro`); only the series name
differs (here "Opening Boxes", internal "Build It Yourself"). Preview the reader's view
with `npm run dev:prod` (drafts hidden, upcoming greyed); `npm run dev` shows every draft.

## Voice (load-bearing)

German's writing voice: data-first, honest, practitioner. **No em dashes** (use commas,
periods, parentheses, ellipses). No corporate buzzwords, no decorative emoji in prose.
Double quotes in Python. Numbers carry the weight; cite the source/link behind each one.
Articles tell an honest arc (problem → struggle → payoff → what's left + credits).

## D2 diagrams: the recipe

Fenced ```d2 blocks are rendered at build time by `src/plugins/remark-d2.mjs` →
`src/lib/renderD2.mjs`, which shells out to the `d2` CLI. `\n` in a label = line break.

**Keep diagrams visually balanced: width/height ratio ~0.6–1.2 (target ~1.0).** Avoid
both extremes (wide chains and tall single-column chains read badly).

What actually works, learned the hard way:

1. **Use `direction: down`, not `direction: right`.** Right-chains render very wide
   (ratios 2.4–4.2). Down layouts land in range.
2. **A long single-column `direction: down` chain goes too tall** (e.g. a 6-node chain
   hit 0.34). Fix it by *widening the nodes*: use **single-line labels** instead of
   multi-line `\n` labels. Wider boxes raise the ratio toward 1.0 without changing the
   graph. (DOSBox new-path diagram went 0.55 → 0.86 this way, same nodes.)
3. **For before/after or eager-vs-lazy, use two side-by-side containers** with
   `direction: down` overall; that balances to ~1.0.
4. Light styling is fine: `{ style.bold: true }` on the load-bearing node,
   `{ style.stroke-dash: 3 }` for a cache/aux node.

**Measure through the REAL pipeline, not plain `d2`.** The site renders with
`--sketch --pad 24` plus prepended theme/ramp vars, so plain `d2 --theme 0 -` gives
slightly different sizes. Measure like this:

```bash
# from repo root, with d2 on PATH
node --input-type=module -e '
import { renderD2 } from "./src/lib/renderD2.mjs";
const code = `direction: down
a -> b -> c`;
const svg = decodeURIComponent(renderD2(code,"light").replace("data:image/svg+xml,",""));
const m = svg.match(/<svg[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"/);
console.log(`${Math.round(+m[1])}x${Math.round(+m[2])} ratio=${(+m[1]/+m[2]).toFixed(2)}`);
'
```

## Gotchas

- **Drafts are excluded from `dist`.** `npm run build` does NOT render `draft: true` posts,
  so it does NOT exercise their D2 fences. Validate a draft's diagrams with the measure
  snippet above (or via the dev server), not the build.
- **The dev server caches D2 output.** After editing a `.md`, a running `npm run dev` may
  keep serving a stale diagram render. If a change "didn't take," restart the dev server
  (the markdown HMR doesn't always re-run the D2 render). Hard-refresh the browser too.
- **Org has no vision API** (German's LinkedIn env): never rely on seeing image pixels.
  Verify diagrams via the SVG bytes/dimensions, never by "looking" at them.
- D2 install in CI is a `curl | sh` step in `deploy.yml`; `renderD2.mjs` also falls back to
  `/opt/homebrew/bin/d2` and `/usr/local/bin/d2`, so local builds work without PATH fuss.

## Commands

```bash
npm run dev       # dev server (renders drafts), http://localhost:4321
npm run build     # build to dist/ (drafts excluded)
npm run preview   # serve built dist/
```

Do not add the `Co-authored-by: Copilot` trailer to commits.

## Navigation, chrome & snippets

The page chrome is shared byte-for-byte with the internal mirror (see "Two-blog sync"); the
durable rules:

- **One authoritative menu** in `src/lib/sidebar.mjs` (About · Projects · Blog), re-set on every
  page by `Sidebar.astro`. Menu entries take a leading icon via `data-icon="<name>"`, masked in
  `custom.css` from Starlight's own icon set.
- **Top nav is icon-only** (`ThemeSelect.astro`): About · Blog · RSS, labels kept as
  `aria-label`/`title`.
- **RSS lives in the nav only.** starlight-blog auto-injects an `rss` social icon; a trailing
  Starlight plugin in `astro.config.mjs` filters it out (the feed + `rel="alternate"` head tag stay).
- **Snippets match Expressive Code's terminal frame** (theme-adaptive bar, faint dots, drop shadow,
  `0.45rem` radius) — mirror EC's tokens, don't hard-code.
- **About page:** no `## About me` heading, `tableOfContents: false`, role/intro line is a muted
  italic `.about-lede` (the name stays upright/full-color via `.about-lede strong`).
- **Header search is pinned** (`.header { grid-template-columns: auto 1fr auto }`) so it doesn't
  jump from splash to doc pages.
- **Hero icon-first:** `attrs.class: kz-icon-first` on a hero action renders its icon before the
  text (the Projects and About actions use it).

## Two-blog sync

This repo and the **internal** mirror (`~/Development/LinkedIn/gmendezb-pages`, branch `main`,
served at go/Kronuz) share their *code* byte-for-byte: `custom.css`, the shared components,
`renderSnippet.mjs`, the snippet pages, `PageTitle.astro`, `Sidebar.astro`, `ThemeSelect.astro`,
etc. After editing a shared file, copy it to the other repo and rebuild both. **Legitimately
different:** content (posts, `about.md`, `index.mdx`, `projects.md`), `sidebar.mjs` (this side adds
Projects), `content.config.ts`, `astro.config.mjs`, `consts.ts`, `SiteTitle.astro`, `Footer.astro`,
`ReplHero.astro`, and the comment system — this (public) side uses `Giscus.astro`; the internal side
uses a Discussion link-out (`PostCta.astro` + `MarkdownContent.astro`).

## Deferred ideas

- **Projects with a status lifecycle** (deferred 2026-06-10). A Projects section grouped by progress
  state. Sketch: a `status` enum (`proposed | active | blocked | shipped`, maybe `paused`/`archived`)
  kept *separate* from `draft` (draft = visibility, status = progress); projects as their own
  `/projects/` pages (not blog posts, kept out of the writing RSS) with a status badge reusing the
  `PageTitle` pattern; a `/projects/` index grouped by status. `projects.md` here is currently a flat
  list. Open forks: page-per-project vs. a single grouped index; final status vocabulary. Deferred
  because status earns its keep for in-flight work, less for a shipped-OSS portfolio.
