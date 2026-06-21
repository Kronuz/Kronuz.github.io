/**
 * remark-snippet — turn fenced ```snippet blocks into a source-code viewer.
 *
 *     ```snippet file="statusline.sh" title="statusline.sh" collapse
 *     ```
 *
 * `file=` reads from src/snippets/<file> (also served raw at /snippets/raw/<file>.txt,
 * and gets a full-page view at /snippets/view/<file>/).
 * Without `file=`, the fence body itself is highlighted inline. Options:
 *   file="..."   read this file from src/snippets/
 *   lang="..."   override the language (else inferred from the extension)
 *   title="..."  toolbar title (defaults to the filename)
 *   collapse     wrap the code in a <details> (good for long files)
 *
 * Rendering is shared with the full-page route via ../lib/renderSnippet.mjs.
 */
import { visit } from "unist-util-visit";
import { snippetFigure, langForFile, readSnippet, rawHref } from "../lib/renderSnippet.mjs";

function parseMeta(meta) {
  const out = {};
  if (!meta) return out;
  const re = /(\w+)(?:="([^"]*)")?/g;
  let m;
  while ((m = re.exec(meta))) out[m[1]] = m[2] === undefined ? true : m[2];
  return out;
}

export default function remarkSnippet() {
  return async (tree) => {
    const jobs = [];
    visit(tree, "code", (node, index, parent) => {
      if (!parent || node.lang !== "snippet") return;
      jobs.push({ node, index, parent, meta: parseMeta(node.meta) });
    });

    for (const job of jobs) {
      const { meta } = job;
      let opts;
      if (meta.file) {
        opts = {
          code: readSnippet(meta.file),
          lang: langForFile(meta.file, meta.lang),
          title: meta.title || meta.file,
          rawHref: rawHref(meta.file),
          viewHref: `/snippets/view/${meta.file}/`,
          copy: true,
          collapse: !!meta.collapse,
        };
      } else {
        opts = {
          code: job.node.value,
          lang: meta.lang || "text",
          title: meta.title || "",
          copy: true,
          collapse: !!meta.collapse,
        };
      }
      const html = await snippetFigure(opts);
      job.parent.children[job.index] = { type: "html", value: html };
    }
  };
}
