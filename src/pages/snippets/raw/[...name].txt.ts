import type { APIRoute, GetStaticPaths } from "astro";
import { listSnippets, readSnippet } from "../../../lib/renderSnippet.mjs";

/**
 * Raw snippet text at /snippets/raw/<file>.txt (file may be nested, e.g.
 * demo/app.py -> /snippets/raw/demo/app.py.txt).
 *
 * The `.txt` extension is the lever: GitHub Pages (which offers no header/
 * Content-Type configuration) serves `.txt` as `text/plain; charset=utf-8`, so
 * the UTF-8 source renders correctly instead of as Latin-1 mojibake. The dev
 * server honors the explicit header below.
 */
export const getStaticPaths: GetStaticPaths = () =>
  listSnippets().map((file) => ({ params: { name: file } }));

export const GET: APIRoute = ({ params }) => {
  const body = readSnippet(params.name as string);
  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
