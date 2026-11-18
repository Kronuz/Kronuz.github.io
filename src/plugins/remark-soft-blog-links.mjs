/**
 * remark-soft-blog-links — turn an internal link to a page that is NOT in the
 * current build (a draft, in a production build) into plain text: a blog post
 * (`/blog/<slug>/`), a project page (`/projects/<id>/...`) or any other docs page
 * (`/ref/...`). This lets a page reference one that publishes later without a
 * 404: the reference reads as plain text until the target goes live, then
 * becomes a real link again on the next build.
 *
 * Only *known* pages are ever softened, so links to published pages stay links,
 * and tag pages, pagination, snippets, external URLs and typos are left
 * completely alone. A page is treated as "in this build" the same way Starlight
 * and starlight-blog decide it: present, and not `draft: true` in production.
 *
 * Runs in the remark stage on markdown `[text](/blog/x/#anchor)` link nodes, so
 * it covers both `.md` and `.mdx` bodies.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { SKIP, visit } from "unist-util-visit";

const CONTENT = join(dirname(fileURLToPath(import.meta.url)), "..", "content");
const IS_PROD = process.env.NODE_ENV === "production";
// A site-relative page path, without its anchor or query.
const PAGE_LINK = /^(\/[^#?]*?)\/?(?:[#?].*)?$/;

// The URL path a content file builds: its path under the collection's base, each segment
// slugged the way Astro ids are (github-slugger), with a trailing `/index` dropped.
const slug = (s) =>
  s.toLowerCase().replace(/[^\p{L}\p{M}\p{N}\p{Pc} -]/gu, "").replace(/ /g, "-");
function urlOf(base, root, file) {
  const parts = relative(root, file).replace(/\.mdx?$/, "").split(sep).map(slug);
  if (parts.at(-1) === "index") parts.pop();
  return `${base}/${parts.join("/")}`.replace(/\/+$/, "") || "/";
}

function walk(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(dir, e.name)) : /\.mdx?$/.test(e.name) ? [join(dir, e.name)] : [],
  );
}

// Computed once per build: every content page's URL path, and the subset this build emits.
let cache = null;
function pageSets() {
  if (cache) return cache;
  const known = new Set();
  const published = new Set();
  const collections = [
    ["", join(CONTENT, "docs")],
    ["/projects", join(CONTENT, "projects")],
  ];
  for (const [base, root] of collections) {
    for (const file of walk(root)) {
      const url = urlOf(base, root, file);
      known.add(url);
      let draft = false;
      try {
        const frontmatter = /^---\n([\s\S]*?)\n---/.exec(readFileSync(file, "utf8"));
        if (frontmatter && /^draft:\s*true\s*$/m.test(frontmatter[1])) draft = true;
      } catch {
        // Unreadable file: treat as published so we never hide a real link.
      }
      if (!IS_PROD || !draft) published.add(url);
    }
  }
  cache = { known, published };
  return cache;
}

export default function remarkSoftBlogLinks() {
  return (tree) => {
    const { known, published } = pageSets();
    visit(tree, "link", (node, index, parent) => {
      if (index == null || !parent) return;
      const match = PAGE_LINK.exec(node.url || "");
      if (!match) return;
      const url = match[1];
      // Leave published pages, and anything that is not a known page (tags,
      // pagination, typos), exactly as written.
      if (published.has(url) || !known.has(url)) return;
      // Soften: replace the link with its inline children (the visible text).
      parent.children.splice(index, 1, ...node.children);
      return [SKIP, index];
    });
  };
}
