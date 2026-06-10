/**
 * The one authoritative site menu.
 *
 * Starlight shows the configured sidebar on docs-style pages, but starlight-blog
 * replaces it with its own (recent posts / tag counts) on every /blog/ page, so
 * the menu changed shape as you moved between sections. This module is the single
 * source of truth for the authoritative part of the menu, used two ways:
 *   - `sidebarConfig()` feeds Starlight's `sidebar` config (so route-derived bits
 *     like prev/next pagination still make sense), and
 *   - `buildSidebar()` is rendered by the Sidebar component override on *every*
 *     page; on /blog/ pages the override then appends the blog's own post nav.
 *
 * `match: "section"` marks a link current for its whole section (any path under
 * it), not just the exact page — so "Blog" stays lit on posts and tag pages too.
 */

const MENU = [
  { label: "About", href: "/about/", icon: "information" },
  { label: "Projects", href: "/projects/", match: "section", icon: "rocket" },
  { label: "Blog", href: "/blog/", match: "section", icon: "open-book" },
];

// Compare paths ignoring a trailing slash (Starlight serves with one); leave
// file-like hrefs (e.g. /blog/rss.xml) untouched.
const norm = (p) => (p.includes(".") || p.endsWith("/") ? p : `${p}/`);

function toLink(item, pathname) {
  const here = norm(pathname);
  const target = norm(item.href);
  const isCurrent = item.match === "section" ? here.startsWith(target) : here === target;
  return {
    type: "link",
    label: item.label,
    href: item.href,
    isCurrent,
    badge: undefined,
    attrs: { ...(item.icon ? { "data-icon": item.icon } : {}), ...(item.attrs ?? {}) },
  };
}

/** The menu as Starlight `SidebarEntry[]`, with the current page marked. */
export function buildSidebar(pathname) {
  return MENU.map((item) =>
    item.items
      ? {
          type: "group",
          label: item.label,
          collapsed: false,
          badge: undefined,
          entries: item.items.map((sub) => toLink(sub, pathname)),
        }
      : toLink(item, pathname),
  );
}

/** The same menu in Starlight's user-config `sidebar` shape. */
export function sidebarConfig() {
  return MENU.map((item) =>
    item.items
      ? { label: item.label, items: item.items.map((s) => ({ label: s.label, link: s.href })) }
      : { label: item.label, link: item.href, ...(item.attrs ? { attrs: item.attrs } : {}) },
  );
}
