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
import { createHighlighter } from "shiki";
import lightTheme from "../styles/kronuz-light.json";
import darkTheme from "../styles/kronuz-dark.json";

const LANGS = [
  "bash", "python", "javascript", "typescript", "json", "c", "cpp", "rust",
  "markdown", "yaml", "toml", "css", "html", "diff", "ini", "go", "sql", "astro",
];

// File extension -> Shiki language id. Anything unknown falls back to plain text.
const EXT_LANG = {
  sh: "bash", bash: "bash", zsh: "bash",
  py: "python", js: "javascript", mjs: "javascript", cjs: "javascript",
  ts: "typescript", tsx: "typescript", jsx: "javascript",
  json: "json", c: "c", h: "c", cpp: "cpp", cc: "cpp", hpp: "cpp",
  rs: "rust", md: "markdown", markdown: "markdown",
  yml: "yaml", yaml: "yaml", toml: "toml", css: "css", html: "html",
  diff: "diff", patch: "diff", ini: "ini", cfg: "ini", conf: "ini",
  go: "go", sql: "sql", astro: "astro", txt: "text", text: "text",
};

let _hl;
async function highlighter() {
  if (!_hl) _hl = createHighlighter({ themes: [lightTheme, darkTheme], langs: LANGS });
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

/** List snippet filenames (skipping dotfiles). */
export function listSnippets() {
  try {
    return readdirSync(SNIPPETS_DIR).filter((f) => !f.startsWith("."));
  } catch {
    return [];
  }
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

/**
 * Build the inline snippet figure: a titled toolbar (Open / Raw) over the
 * highlighted code, optionally collapsed inside a <details>.
 */
export async function snippetFigure({ code, lang, title, rawHref, viewHref, collapse }) {
  const pre = await highlight(code, lang);
  const lineCount = code.split("\n").length;
  const actions = [
    viewHref ? `<a class="snippet-btn" href="${esc(viewHref)}">Open</a>` : "",
    rawHref ? `<a class="snippet-btn" href="${esc(rawHref)}" target="_blank" rel="noopener">Raw</a>` : "",
  ].join("");
  const bar =
    `<figcaption class="snippet-bar">` +
    `<span class="snippet-title">${esc(title || lang)}</span>` +
    `<span class="snippet-actions">${actions}</span>` +
    `</figcaption>`;
  const body = collapse
    ? `<details class="snippet-details"><summary>Show ${lineCount} lines</summary>` +
      `<div class="snippet-code">${pre}</div></details>`
    : `<div class="snippet-code">${pre}</div>`;
  return `<figure class="snippet" data-lang="${esc(lang)}">${bar}${body}</figure>`;
}
