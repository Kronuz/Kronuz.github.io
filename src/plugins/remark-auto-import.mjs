/**
 * remark-auto-import — make a few project components usable in any `.mdx` with no
 * import line. For each registered component that a file actually uses as JSX
 * (`<SnippetLink ...>`), inject its import at the top of the file, UNLESS the file
 * already imports that name. So you can just write `<SnippetLink file="x.sh">x</SnippetLink>`
 * without the `import SnippetLink from '@/components/SnippetLink.astro'` boilerplate,
 * and any file that still has an explicit import keeps working (no duplicate).
 *
 * Runs in the remark stage, so it only sees JSX in `.mdx` (plain `.md` has none, so it
 * is a no-op there). Imports use the `@/` path alias (see tsconfig.json), so the
 * injected path is the same regardless of how deep the file is.
 */
import { visit } from "unist-util-visit";

// Component name -> import source. Add a component here to make it import-free.
const COMPONENTS = {
  SnippetLink: "@/components/SnippetLink.astro",
  Snippet: "@/components/Snippet.astro",
};

// A minimal ESTree `Program` for `import <name> from "<source>";`, which MDX turns
// into a real import. Hand-built so the plugin needs no parser dependency.
function importProgram(name, source) {
  return {
    type: "Program",
    sourceType: "module",
    body: [
      {
        type: "ImportDeclaration",
        specifiers: [
          { type: "ImportDefaultSpecifier", local: { type: "Identifier", name } },
        ],
        source: { type: "Literal", value: source, raw: JSON.stringify(source) },
        attributes: [],
      },
    ],
  };
}

export default function remarkAutoImport() {
  return (tree) => {
    // 1. Which registered components does this file use as JSX?
    const used = new Set();
    visit(tree, (node) => {
      if (
        (node.type === "mdxJsxFlowElement" || node.type === "mdxJsxTextElement") &&
        node.name &&
        COMPONENTS[node.name]
      ) {
        used.add(node.name);
      }
    });
    if (used.size === 0) return;

    // 2. Which of those are already imported? (don't double-import)
    const imported = new Set();
    visit(tree, "mdxjsEsm", (node) => {
      for (const name of used) {
        if (new RegExp(`\\bimport\\s+${name}\\b`).test(node.value || "")) {
          imported.add(name);
        }
      }
    });

    // 3. Inject an import for each used-but-not-imported component, at the top.
    const toAdd = [...used].filter((n) => !imported.has(n)).sort();
    for (const name of toAdd.reverse()) {
      const source = COMPONENTS[name];
      tree.children.unshift({
        type: "mdxjsEsm",
        value: `import ${name} from ${JSON.stringify(source)};`,
        data: { estree: importProgram(name, source) },
      });
    }
  };
}
