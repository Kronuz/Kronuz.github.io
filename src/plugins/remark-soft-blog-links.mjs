/**
 * remark-soft-blog-links — turn an internal `/blog/<slug>/` link into plain text
 * when `<slug>` is a real post that is NOT in the current build (a draft, in a
 * production build). This lets a post reference a sibling that publishes later
 * without a 404: the reference reads as plain text until the target goes live,
 * then becomes a real link again on the next build.
 *
 * Only *known* post slugs are ever softened, so links to published posts stay
 * links, and tag pages, pagination, snippets, refs, anchors and external URLs
 * are left completely alone. A post is treated as "in this build" the same way
 * starlight-blog decides it: present, and not `draft: true` in production.
 *
 * Runs in the remark stage on markdown `[text](/blog/x/)` link nodes, so it
 * covers both `.md` and `.mdx` bodies.
 */
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { SKIP, visit } from "unist-util-visit";

const BLOG_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "content", "docs", "blog");
const IS_PROD = process.env.NODE_ENV === "production";
const BLOG_LINK = /^\/blog\/([a-z0-9-]+)\/?$/;

// Computed once per build: every post slug, and the subset that this build emits.
let cache = null;
function slugSets() {
  if (cache) return cache;
  const known = new Set();
  const published = new Set();
  for (const name of readdirSync(BLOG_DIR)) {
    const match = /^(.+)\.mdx?$/.exec(name);
    if (!match) continue;
    const slug = match[1];
    known.add(slug);
    let draft = false;
    try {
      const frontmatter = /^---\n([\s\S]*?)\n---/.exec(readFileSync(join(BLOG_DIR, name), "utf8"));
      if (frontmatter && /^draft:\s*true\s*$/m.test(frontmatter[1])) draft = true;
    } catch {
      // Unreadable file: treat as published so we never hide a real link.
    }
    if (!IS_PROD || !draft) published.add(slug);
  }
  cache = { known, published };
  return cache;
}

export default function remarkSoftBlogLinks() {
  return (tree) => {
    const { known, published } = slugSets();
    visit(tree, "link", (node, index, parent) => {
      if (index == null || !parent) return;
      const match = BLOG_LINK.exec(node.url || "");
      if (!match) return;
      const slug = match[1];
      // Leave published posts, and anything that is not a known post slug
      // (tags, pagination, typos), exactly as written.
      if (published.has(slug) || !known.has(slug)) return;
      // Soften: replace the link with its inline children (the visible text).
      parent.children.splice(index, 1, ...node.children);
      return [SKIP, index];
    });
  };
}
