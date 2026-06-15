/**
 * remark-snippet-link — markdown-native inline snippet links, no JSX needed.
 *
 *     [etch.py](snippet:etch.py)
 *
 * Rewrites an inline link whose URL is `snippet:<file>` into the same
 * click-to-open modal markup that <SnippetLink file="<file>">label</SnippetLink>
 * produced, so a post can link a snippet inline and still be a plain `.md` file.
 * The link text becomes the label. The shared builder lives in
 * ../lib/renderSnippet.mjs; the modal is driven by the global <SnippetScript>
 * delegated listener (loaded once in the blog frame).
 */
import { visit } from "unist-util-visit";
import { snippetLinkHtml } from "../lib/renderSnippet.mjs";

function textOf(node) {
  if (node.value) return node.value;
  if (node.children) return node.children.map(textOf).join("");
  return "";
}

export default function remarkSnippetLink() {
  return async (tree) => {
    const jobs = [];
    visit(tree, "link", (node, index, parent) => {
      if (!parent || index == null) return;
      const m = /^snippet:(.+)$/.exec(node.url || "");
      if (!m) return;
      jobs.push({ index, parent, file: m[1], label: textOf(node) });
    });
    for (const job of jobs) {
      const html = await snippetLinkHtml(job.file, job.label);
      job.parent.children[job.index] = { type: "html", value: html };
    }
  };
}
