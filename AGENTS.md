# AGENTS.md: Kronuz.github.io

Agent handoff for this repo. The human-facing overview is in `README.md`; this file
captures the conventions and the non-obvious gotchas an agent needs to not break things.

## What this is

German's personal blog (`https://kronuz.github.io`). Astro + Starlight + starlight-blog,
a custom *Kronuz* code theme, build-time D2 diagrams, and a multi-tenant comments Worker. Self-deploying:
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

Fenced ```d2 blocks are rendered at build time by the shared engine's
`plugins/remark-d2.mjs` and `lib/renderD2.mjs`, which shell out to the `d2` CLI. `\n` in a label = line break. The fence's
`alt="..."` is the diagram's description, read once by Reader view and screen readers (see "Reader
view and listening"): write it as a sentence.

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
import { renderD2 } from "@kronuz/starlight-core/lib/renderD2.mjs";
const code = `direction: down
a -> b -> c`;
const svg = decodeURIComponent(renderD2(code,"light").replace("data:image/svg+xml,",""));
const m = svg.match(/<svg[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"/);
console.log(`${Math.round(+m[1])}x${Math.round(+m[2])} ratio=${(+m[1]/+m[2]).toFixed(2)}`);
'
```

## Snippets & cross-links

- **Snippets** (full files from `src/snippets/`), plain Markdown, two forms: a fenced
  ```` ```snippet ```` with `file="name.ext"` (optional `title=`, `lang=`, `collapse`)
  for the framed viewer, or an inline link `[label](snippet:file)` for a click-to-open
  modal. Both render via `lib/renderSnippet.mjs` (`remark-snippet.mjs` /
  `remark-snippet-link.mjs`), driven by the global `<SnippetScript>`. Served raw at
  `/snippets/raw/<file>.txt`, full page at `/snippets/view/<file>/`.
- **Terminal output (colored):** a plain ```` ```ansi ```` fence — `remark-ansi.mjs`
  normalizes terminal-valid colon-form extended SGR colors before Expressive Code renders
  Shiki's `ansi` language, so raw captures come out colored and theme-aware. The same
  `normalizeAnsi.mjs` helper runs in `renderSnippet.mjs` for `.out`/`.ansi`/`.log` snippets.
  Use ```` ```ansi ```` for an inline capture (a prompt, a build log); a ```` ```snippet ````
  with a terminal-output file is only for *sharing the whole file*.
- **Soft cross-links:** a `/blog/<slug>/` link to a post that is a *draft* (so not in a
  production build) renders as plain text instead of 404ing, then becomes a real link once
  that post publishes (`remark-soft-blog-links.mjs`). Only known post slugs are softened, so
  links to published posts, tags, anchors and external URLs are untouched. Link siblings
  freely, even forward to a not-yet-published one.

## Gotchas

- **Drafts are excluded from `dist`.** `npm run build` does NOT render `draft: true` posts,
  so it does NOT exercise their D2 fences. Validate a draft's diagrams with the measure
  snippet above (or via the dev server), not the build.
- **Rendered markdown is cached.** The content layer (`node_modules/.astro/`) reuses the rendered HTML
  of unchanged posts, so editing a remark/rehype plugin or `figureHtml` does not re-render them: build
  with `npm run build -- --force` (or delete `node_modules/.astro`) to see the new markup.
- **The dev server caches D2 output.** After editing a `.md`, a running `npm run dev` may
  keep serving a stale diagram render. If a change "didn't take," restart the dev server
  (the markdown HMR doesn't always re-run the D2 render). Hard-refresh the browser too.
- **Org has no vision API** (German's LinkedIn env): never rely on seeing image pixels.
  Verify diagrams via the SVG bytes/dimensions, never by "looking" at them.
- D2 install in CI is a `curl | sh` step in `deploy.yml`; `renderD2.mjs` also falls back to
  `/opt/homebrew/bin/d2` and `/usr/local/bin/d2`, so local builds work without PATH fuss.

## Reader view and listening

Readers open posts in Reader view (Safari **aA**, Show Reader; Firefox Reader View), and some
listen: Safari's Listen to Page reads the Reader extraction aloud, VoiceOver reads the page. The
templates give them the article and nothing else (fix regressions in the templates, not in posts):

- **The article.** On a post, `MarkdownContent.astro` wraps the body in
  `<article class="kz-post" aria-labelledby="_top">`, named by the page `<h1>`. The series chip
  (`details.series-mobile`), both pagers, the comments and the post footer are siblings outside it.
  Starlight puts the title panel (`PageTitle.astro`: `<h1>`, subtitle) and the content
  panel in separate siblings, so the title and subtitle sit above the article, and the date
  and byline sit between them and the chip. Reader view starts at the first paragraph and takes the
  title, byline and date from metadata.
- **Metadata.** Posts carry `og:type` `article`, a schema.org `BlogPosting` in JSON-LD (author,
  `datePublished`), and `<meta name="author">`, `article:author` and `article:published_time`.
  `starlightRouteData.ts` adds the meta tags after `next()`, once starlight-blog's middleware has
  resolved the post, so they match the rendered byline. Mozilla Readability, the extractor behind
  Firefox's Reader View, reads byline and date from them when the JSON-LD is absent.
- **D2 diagrams.** `figureHtml` (shared `lib/renderD2.mjs`) emits both theme images as decorative (`alt=""`),
  the dark one with `hidden` (Readability drops it, so Firefox's Reader shows the light diagram only;
  `styles/blog.css` shows it again under `[data-theme='dark']`), and the fence's `alt="..."` as one
  `figcaption.diagram-description.sr-only`. The description is text, so Reader and Listen to Page read
  it once in either theme, and Chrome's accessibility tree exposes it once and no image. Hand-written
  `<figure class="diagram">` HTML needs the same markup.
- No speech markup works: browsers implement neither CSS `speak`/`speak-as` nor SSML, and
  schema.org `speakable` is read only by Google Assistant for news. `aria-hidden="true"` removes an
  element from VoiceOver and from Readability, and so does `hidden`: use them for duplicates and
  decoration, never content.
- What a post's prose does for listeners (no bare hashes, a sentence before each table and code
  block, alt text as a sentence) is in the german-writing skill, `references/articles.md`,
  "Written to be read aloud".
- **Checking a change.** Build, serve `dist`, save pages, and run Mozilla Readability over them
  (jsdom plus `@mozilla/readability`): the text starts with the first paragraph, has no "Edit source"
  or series list, shows each diagram description once, and has `byline` and `publishedTime`. Compare
  element rects in headless Chrome before and after to show the layout did not move.

## Publishing a backlog

`npm run publish -- <slug>` drops `draft: true` (and `upcoming: true`), sets `date:`, commits
`Publish: <title>` and pushes; Actions deploys. `--date YYYY-MM-DD` (or an ISO date-time,
`2026-08-06T09:30`) publishes a draft under the date it was written instead of today, and
`--no-push` commits only, so a batch goes out in one `git push` after `npm run build`. The script
refuses a post that is not a draft, a date that does not exist and a date after today.

- A date is no earlier than the facts the post states (a library's behavior, a number, a release),
  the work it describes (the file's git history and the events in the text), its series intro and
  the parts before it, and every post it links to.
- Posts imported from the old blog keep their original dates; a post written for this blog dates
  from 2026-06-08 on (the relaunch, "Goodbye, Dr. Jekyll", is 2026-06-07).
- One post per day, interleaved around the published ones; series parts in `seriesOrder`, a few
  days apart.
- A draft that waited is re-checked against the current state of what it describes before it
  publishes (the draft-blog-post skill, "If the draft waited").

## Commands

```bash
npm run dev       # dev server (renders drafts), http://localhost:4321
npm run build     # build to dist/ (drafts excluded)
npm run preview   # serve built dist/
npm run icons     # regenerate every icon from src/assets/logo.svg (see "Site icons")
```

Do not add the `Co-authored-by: Copilot` trailer to commits.

## Navigation, chrome & snippets

The shared engine owns the chrome controls and footer; the durable rules:

- **One authoritative menu** in `src/lib/sidebar.mjs` (About · Projects · Blog), re-set on every
  page by `Sidebar.astro`. Menu entries take a leading icon via `data-icon="<name>"`, masked in
  `styles/blog.css` from Starlight's own icon set.
- **Top nav is icon-only** (shared `BlogThemeSelect.astro`): About · Blog · RSS, labels kept as
  `aria-label`/`title`, then the text-size toggle and the theme selector.
- **RSS lives in the nav only.** starlight-blog auto-injects an `rss` social icon; a trailing
  Starlight plugin in `astro.config.mjs` filters it out (the feed + `rel="alternate"` head tag stay).
- **Snippets match Expressive Code's terminal frame** (theme-adaptive bar, faint dots, drop shadow,
  `0.45rem` radius) — mirror EC's tokens, don't hard-code.
- **Copy on touch screens** stays hidden until a tap on the code reveals it; a second tap
  hides it. The shared `CopyReveal.astro` handles Expressive Code frames and source snippets,
  while the `(hover: none)` rules in `styles/blog.css` preserve desktop hover and keyboard focus.
- **About page:** no `## About me` heading, `tableOfContents: false`, role/intro line is a muted
  italic `.about-lede` (the name stays upright/full-color via `.about-lede strong`).
- **Header search is pinned** (`.header { grid-template-columns: auto 1fr auto }`) so it doesn't
  jump from splash to doc pages.
- **Hero icon-first:** `attrs.class: kz-icon-first` on a hero action renders its icon before the
  text (the Projects and About actions use it).
- **One filled highlight.** Only the sidebar link whose `href` is this page keeps Starlight's filled
  highlight (`aria-current="page"`). `Sidebar.astro` turns every other current link (the Blog or
  Projects root, a project hub while reading one of its parts, the series a post belongs to) into
  an ancestor (`data-ancestor`), tinted in `styles/blog.css`. A page the menu does not list shows only
  its tinted ancestors.
- **Reading text size.** The "Aa" toggle (`TextSizeToggle.astro`) sits just before the theme
  selector on desktop (`ThemeSelect.astro`) and in the header after the search button on a phone
  (the `Search.astro` override), one visible at a time; splash pages hide it. It sets
  `html[data-text-size="large"]`, remembered in `localStorage` (`kz-text-size`) and re-applied from
  `<head>` before paint by `starlightRouteData.ts`. `styles/blog.css` ("Reading text size") scales every
  Starlight type token inside `<main>` by 1.125 and opens `--sl-content-width` by 1.25 (900px,
  about 97 characters a line) at the root, where the TOC column and the header read it; the TOC
  keeps its 300px minimum, so the panel grows less below about 1500px wide. The header and
  sidebars keep their size, and pages without a sidebar are untouched. The toggle keeps the line
  at the top of the screen in place while the page reflows.
- **Edit links are for the author.** `EditLink.astro` renders "Edit source" (and, for a post under
  `npm run dev`, a local-editor icon) in the footer's meta row. They always show under `npm run dev`;
  in production only in a browser that opted in by visiting any page with `?editor=on`
  (`?editor=off` opts out), a `localStorage` flag that `starlightRouteData.ts` turns into
  `html[data-editor]` before paint. Project pages only ever get the dev-only link.
- **Image zoom.** `ImageZoom.astro`, mounted by `MarkdownContent.astro`, opens a content image or
  D2 diagram in a modal fitted to the window, on a desktop pointer only (hover and a fine pointer;
  touch screens keep pinch-to-zoom). An image is zoomable, and gets the zoom-in cursor, only when
  the modal shows it at least 1.15x larger; linked images, snippets and code are left alone.

## Site icons

The page logo and every icon derive from the vector master `src/assets/logo.svg`.
`npm run icons` regenerates them, rasterizing each PNG once at its exact size so nothing is
resampled:

- The header renders the master directly; the splash hero, whose image is frontmatter HTML,
  uses its copy at `public/img/logo.svg`.
- `favicon.svg` serves tabs at any DPR; `favicon.ico` (16 to 256 px frames) is the fallback.
- `apple-touch-icon.png` (180 px), `-167` and `-152` serve iOS; `icon-192.png` and `icon-512.png`
  serve Android through `src/pages/manifest.webmanifest.ts`.
- Touch and manifest icons are opaque tiles, because iOS (home screen, Listen to Page, share
  sheets) and Android flatten a transparent icon onto white.
- Two variants sit side by side in `brand/variants/<name>/`, each with its icons and a recolored
  `logo.svg`. `light-gray` (live) puts the master's tracks on the dark page color `#1a1a1a`;
  `green-gray` puts the first favicon's `#465c56` tracks on the light page color. The live set is
  also copied to `public/`; `npm run icons -- --live green-gray` swaps which one is live.
- The 16, 32 and 48 px frames get stem darkening (a gamma on alpha) to keep thin strokes firm.
- `logo.svg` is a potrace trace of the original 1920×2180 brand PNG (the internal repo's
  `brand/README.md` has the recipe). Rendered back at full size it matches the PNG at IoU 0.993.
- iOS caches touch icons; clear the site's Safari website data to see a new one.
## Projects

A project is a page, `src/content/projects/<id>.md` (`/projects/<id>/`), or a directory,
`src/content/projects/<id>/`, whose `index.md` is the hub and every other `.md` a part
(`/projects/<id>/<part>/`, ordered by `seriesOrder`, with an optional short `label` for the
project's own stepper). `src/lib/projects.mjs` groups entries by the first segment of the id. A
page's `title` names its subject on its own. A post joins a project with `project: <id>`: it
shows a "Project:" link above its title, and the hub lists the project's posts.

The public Projects index and sidebar use `order` as an editorial rank by German's own
recent work, not the upstream repository's latest commit. Update the ranks when work on
a project changes their order. `featured` currently marks the three most active projects;
the renderer puts those first, then sorts by `order`.

## Shared site engine

This repo, the internal blog (`~/code/KronuzBlog/gmendezb-pages`), Xapiand docs,
and Detent docs pin the public `Kronuz/starlight-core` package. It owns the
reading controls, code copy, image zoom, themes, Markdown plugins, snippet
renderer, series resolver, unified footer, and the blog and docs style presets.
The footer follows this blog's centered copyright and social layout, with
"Proudly hosted by GitHub" on all four sites. Change that package once, build
all four consumers, then update their pinned revision.

The site repositories own content, navigation, logos, project data, footer identity,
Astro configuration, and deployment. The blogs retain their surrounding post
layout and comments tenant configuration. The public blog also owns its icon
pipeline and project pages.

[Kronuz Discussions](https://github.com/Kronuz/discussions) owns the Astro
component, browser widget, and Worker. Both blogs pin its Git revision and
configure their own tenant URLs. Xapiand does not mount comments.

The internal tenant sets `oauth.identitySource: app-token` (public stays on the default
`userinfo`): it resolves the signed-in user via the OAuth App's token-introspection endpoint
instead of `GET /user`, because an enterprise IP allow list on the internal tenant's identity
provider blocks the Worker's Cloudflare IP on the authenticated userinfo call. See the
Worker's [operations guide](https://github.com/Kronuz/discussions/blob/main/worker/OPERATIONS.md)
and [tutorial](https://github.com/Kronuz/discussions/blob/main/worker/TUTORIAL.md).

## Deferred ideas

- **Projects with a status lifecycle** (deferred 2026-06-10). A Projects section grouped by progress
  state. Sketch: a `status` enum (`proposed | active | blocked | shipped`, maybe `paused`/`archived`)
  kept *separate* from `draft` (draft = visibility, status = progress); projects as their own
  `/projects/` pages (not blog posts, kept out of the writing RSS) with a status badge reusing the
  `PageTitle` pattern; a `/projects/` index grouped by status. `projects.md` here is currently a flat
  list. Open forks: page-per-project vs. a single grouped index; final status vocabulary. Deferred
  because status earns its keep for in-flight work, less for a shipped-OSS portfolio.
