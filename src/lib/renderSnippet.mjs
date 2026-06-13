/**
 * Build-time source-snippet rendering, shared by the remark plugin
 * (```snippet fences) and the full-page viewer route (src/pages/snippets/view).
 *
 * Highlighting uses Shiki with the same Kronuz themes as the site's code blocks,
 * in dual-theme mode (CSS variables --shiki-light / --shiki-dark), so a snippet
 * matches the rest of the site and follows the light/dark toggle. See custom.css
 * for the `.snippet .shiki` rules that pick the right variable per `data-theme`.
 */
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { getSingletonHighlighter } from "shiki";
import lightTheme from "../styles/kronuz-light.json";
import darkTheme from "../styles/kronuz-dark.json";

const LANGS = [
  "bash", "python", "javascript", "typescript", "json", "c", "cpp", "rust",
  "markdown", "yaml", "toml", "css", "html", "diff", "ini", "go", "sql", "astro",
  "ansi",
];

// File extension -> Shiki language id. Anything unknown falls back to plain text.
// Terminal captures (.out/.ansi/.log) use Shiki's `ansi` grammar, which turns
// SGR escape codes into colored spans (palette comes from terminal.ansi* in the
// Kronuz themes, so it follows light/dark like the rest of the site).
const EXT_LANG = {
  sh: "bash", bash: "bash", zsh: "bash",
  py: "python", js: "javascript", mjs: "javascript", cjs: "javascript",
  ts: "typescript", tsx: "typescript", jsx: "javascript",
  json: "json", c: "c", h: "c", cpp: "cpp", cc: "cpp", hpp: "cpp",
  rs: "rust", md: "markdown", markdown: "markdown",
  yml: "yaml", yaml: "yaml", toml: "toml", css: "css", html: "html",
  diff: "diff", patch: "diff", ini: "ini", cfg: "ini", conf: "ini",
  go: "go", sql: "sql", astro: "astro", txt: "text", text: "text",
  out: "ansi", ansi: "ansi", log: "ansi",
};

let _hl;
async function highlighter() {
  // Shiki's singleton helper caches by themes+langs in its own (stable) module
  // scope, so the remark plugin, the components, and the route loader all share
  // ONE highlighter instead of each creating their own. Shiki warns once 10
  // instances exist; this keeps us at one.
  if (!_hl) _hl = getSingletonHighlighter({ themes: [lightTheme, darkTheme], langs: LANGS });
  return _hl;
}

/** Resolve a Shiki language id from a filename (or an explicit override). */
export function langForFile(file, explicit) {
  if (explicit) return EXT_LANG[explicit] || explicit;
  const ext = path.extname(file || "").slice(1).toLowerCase();
  return EXT_LANG[ext] || "text";
}

// Snippet source files live here (NOT in public/), so the only public raw URL is
// the charset-correct /snippets/raw/<file>.txt endpoint below.
const SNIPPETS_DIR = path.resolve("src/snippets");

/** List snippet files recursively, as posix relative paths (skipping dotfiles).
 *  A file in a subfolder (e.g. "demo/app.py") belongs to that "project". */
export function listSnippets() {
  const out = [];
  const walk = (dir, prefix) => {
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (e.name.startsWith(".")) continue;
      const rel = prefix ? `${prefix}/${e.name}` : e.name;
      if (e.isDirectory()) walk(path.join(dir, e.name), rel);
      else out.push(rel);
    }
  };
  walk(SNIPPETS_DIR, "");
  return out.sort();
}

/**
 * Files sharing a snippet's immediate folder (its "project"), as posix relative
 * paths including the file itself, sorted. A file in the snippets root has no
 * project, so this returns just [file] (length 1 -> no project menu is shown).
 */
export function projectFiles(file) {
  const slash = file.lastIndexOf("/");
  if (slash < 0) return [file];
  const dir = file.slice(0, slash);
  return listSnippets().filter((f) => {
    const s = f.lastIndexOf("/");
    return s >= 0 && f.slice(0, s) === dir;
  });
}

/** Read a snippet file, trimming a single trailing newline. */
export function readSnippet(file) {
  return readFileSync(path.join(SNIPPETS_DIR, file), "utf8").replace(/\n$/, "");
}

/** Public URL for a snippet's raw text (served as text/plain; charset=utf-8). */
export function rawHref(file) {
  return `/snippets/raw/${file}.txt`;
}

/** Highlight code to dual-theme Shiki HTML (a <pre class="shiki ...">). */
export async function highlight(code, lang) {
  const hl = await highlighter();
  const use = LANGS.includes(lang) ? lang : "text";
  return hl.codeToHtml(code, {
    lang: use,
    themes: { light: "kronuz-light", dark: "kronuz-dark" },
    defaultColor: false,
  });
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Copy-to-clipboard button, shared by the inline figure and the full-page view.
// The click is handled by the delegated listener in <SnippetScript> (it reads the
// rendered <pre>'s textContent, which is the original source). Kept identical to
// the button in <SnippetLink>'s modal so all three surfaces look and behave alike.
export const COPY_BTN =
  `<button class="snippet-btn snippet-icon-btn snippet-copy" type="button" data-snippet-copy ` +
  `aria-label="Copy to clipboard" title="Copy to clipboard">` +
  `<svg class="snippet-i snippet-i-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" ` +
  `stroke-width="2" stroke-linecap="round" stroke-linejoin="round">` +
  `<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>` +
  `<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>`;

// Download icon (save-to-disk arrow), matching the Copy/Close icon buttons. Kept in sync
// with the inline copy in <Snippet>/<SnippetLink> so all surfaces look alike.
export const DOWNLOAD_ICON =
  `<svg class="snippet-i snippet-i-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" ` +
  `stroke-width="2" stroke-linecap="round" stroke-linejoin="round">` +
  `<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>` +
  `<path d="M7 10l5 5 5-5"></path><path d="M12 15V3"></path></svg>`;

/** A download icon button: the raw file, saved under its real name (drops the `.txt`). */
export function downloadBtn(rawHref) {
  if (!rawHref) return "";
  const name = rawHref.replace(/^.*\/snippets\/raw\//, "").replace(/\.txt$/, "");
  return (
    `<a class="snippet-btn snippet-icon-btn snippet-download" href="${esc(rawHref)}" ` +
    `download="${esc(name)}" aria-label="Download ${esc(name)}" title="Download ${esc(name)}">` +
    `${DOWNLOAD_ICON}</a>`
  );
}

/**
 * Build the inline snippet figure: a titled toolbar (Open / Raw / Copy) over the
 * highlighted code, optionally collapsed inside a <details>. The same builder
 * renders the full-page viewer (pass `copy` and omit `viewHref` there).
 */
export async function snippetFigure({ code, lang, title, rawHref, viewHref, copy, bare, collapse }) {
  const pre = await highlight(code, lang);
  const lineCount = code.split("\n").length;
  const actions = [
    viewHref ? `<a class="snippet-btn" href="${esc(viewHref)}">Open</a>` : "",
    rawHref ? `<a class="snippet-btn" href="${esc(rawHref)}" target="_blank" rel="noopener">Raw</a>` : "",
    downloadBtn(rawHref),
    copy ? COPY_BTN : "",
  ].join("");
  const bar =
    `<figcaption class="snippet-bar">` +
    `<span class="snippet-title">${bare ? "" : esc(title || lang)}</span>` +
    `<span class="snippet-actions">${actions}</span>` +
    `</figcaption>`;
  const body = collapse
    ? `<details class="snippet-details"><summary>Show ${lineCount} lines</summary>` +
      `<div class="snippet-code">${pre}</div></details>`
    : `<div class="snippet-code">${pre}</div>`;
  return `<figure class="snippet" data-lang="${esc(lang)}">${bar}${body}</figure>`;
}
