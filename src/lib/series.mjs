import { getCollection } from 'astro:content';

// Article-series helpers, driven by post frontmatter (`series` name + `seriesOrder`).
// Shared by the sidebar series box (TableOfContents override) and the in-content
// prev/next pagers + mobile one-liner (MarkdownContent override). Any post that sets
// `series:` joins that series; order within it is `seriesOrder` (then date, then title).
//
// Visibility within a series:
//   published  (draft !== true)            -> readable, linked, counts toward "Part N of M".
//   upcoming   (draft: true + upcoming)    -> shown greyed and un-linked (the disabled
//                                             stepper item), still counts, so a published
//                                             part can tease a draft that's on the way.
//   hidden     (draft: true, no upcoming)  -> not shown at all in production.
// `upcoming` only matters while a post is a draft; a published part ignores it.

const bareSlug = (id) => id.replace(/\.mdx?$/, '').split('/').pop();

// Resolve the series state for a post `term` (its slug, optionally "blog/<slug>").
// "Part N of M" counts published + upcoming parts; a series with a single such part isn't
// shown as a series at all. Plain drafts (no `upcoming`) are hidden in production but kept
// in dev so the full series previews; the post being viewed always counts itself.
export async function resolveSeries(term) {
	const slug = (term ?? '').split('/').pop();
	const docs = await getCollection('docs');
	const current = docs.find((e) => bareSlug(e.id) === slug);
	const name = current?.data?.series;
	if (!name) return { inSeries: false };

	const isProd = import.meta.env.MODE === 'production';
	const isPublished = (e) => e.data.draft !== true; // published ignores `upcoming`
	const isUpcoming = (e) => e.data.draft === true && e.data.upcoming === true;
	// A part appears in the series if it's published, an upcoming draft, the post being
	// viewed, or (in dev) any draft so the whole series previews while writing.
	const isVisible = (e) =>
		bareSlug(e.id) === slug || isPublished(e) || isUpcoming(e) || !isProd;

	const members = docs
		.filter((e) => e.data.series === name && isVisible(e))
		.sort(
			(a, b) =>
				(a.data.seriesOrder ?? 0) - (b.data.seriesOrder ?? 0) ||
				(a.data.date?.getTime() ?? 0) - (b.data.date?.getTime() ?? 0) ||
				a.data.title.localeCompare(b.data.title),
		);
	// A lone visible part is just a post, not a series — no series box, no series pager.
	if (members.length <= 1) return { inSeries: false };

	const index = members.findIndex((e) => bareSlug(e.id) === slug);
	const parts = members.map((e, i) => ({
		slug: bareSlug(e.id),
		title: e.data.title,
		index: i,
		current: i === index,
		// Linked only when a readable page exists (published). Upcoming drafts render greyed
		// and un-linked (the disabled stepper item), so nothing dead-links.
		available: isPublished(e),
	}));

	const prevP = index > 0 ? parts[index - 1] : null;
	const nextP = index < parts.length - 1 ? parts[index + 1] : null;
	return {
		inSeries: true,
		name,
		index,
		total: parts.length,
		parts,
		// The pagers only point at readable parts; an upcoming neighbor yields no pager link.
		prev: prevP && prevP.available ? { slug: prevP.slug, title: prevP.title } : null,
		next: nextP && nextP.available ? { slug: nextP.slug, title: nextP.title } : null,
	};
}

// Chronological prev/next across all blog posts (entries with a date), so we can render
// the blog pager ourselves right next to the series pager instead of where starlight-blog
// forces it (the post footer, below the comments). We use plain chronological order
// (Previous = older post, Next = newer post) so it points the same way as the series
// pager (whose Next is the next, later part) rather than mirroring it. Drafts are
// excluded only in production, matching starlight-blog.
export async function resolveChronological(term) {
	const slug = (term ?? '').split('/').pop();
	const docs = await getCollection('docs');
	const posts = docs
		.filter((e) => e.data.date && (import.meta.env.MODE !== 'production' || e.data.draft !== true))
		.sort((a, b) => b.data.date.getTime() - a.data.date.getTime() || a.data.title.localeCompare(b.data.title));
	const i = posts.findIndex((e) => bareSlug(e.id) === slug);
	if (i < 0) return { prev: null, next: null };
	const link = (e) => (e ? { slug: bareSlug(e.id), title: e.data.title } : null);
	// Array is newest-first: posts[i+1] is older (Previous), posts[i-1] is newer (Next).
	return { prev: link(posts[i + 1]), next: link(posts[i - 1]) };
}
