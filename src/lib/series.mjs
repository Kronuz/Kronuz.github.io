import { getCollection } from 'astro:content';

// Article-series helpers, driven by post frontmatter (`series` name + `seriesOrder`).
// Shared by the sidebar series box (TableOfContents override) and the in-content
// prev/next pagers + mobile one-liner (MarkdownContent override). Any post that sets
// `series:` joins that series; order within it is `seriesOrder` (then date, then title).

const bareSlug = (id) => id.replace(/\.mdx?$/, '').split('/').pop();

// Resolve the series state for a post `term` (its slug, optionally "blog/<slug>").
// Sibling links resolve only for already-published parts (drafts are marked
// unavailable) so nothing dead-links, in any publish order.
export async function resolveSeries(term) {
	const slug = (term ?? '').split('/').pop();
	const docs = await getCollection('docs');
	const current = docs.find((e) => bareSlug(e.id) === slug);
	const name = current?.data?.series;
	if (!name) return { inSeries: false };

	// The series reflects only *published* parts: "Part N of M" counts published parts
	// (M is their count, i.e. the last published part), the stepper lists exactly them,
	// and a series with a single published part isn't shown as a series at all. Drafts
	// count only in dev (so the full series previews while writing), and the post being
	// viewed always counts itself (so a draft previews its own series).
	const isPublished = (e) =>
		import.meta.env.MODE !== 'production' || e.data.draft !== true || bareSlug(e.id) === slug;
	const members = docs
		.filter((e) => e.data.series === name && isPublished(e))
		.sort(
			(a, b) =>
				(a.data.seriesOrder ?? 0) - (b.data.seriesOrder ?? 0) ||
				(a.data.date?.getTime() ?? 0) - (b.data.date?.getTime() ?? 0) ||
				a.data.title.localeCompare(b.data.title),
		);
	// A lone published part is just a post, not a series — no series box, no series pager.
	if (members.length <= 1) return { inSeries: false };

	const index = members.findIndex((e) => bareSlug(e.id) === slug);
	const parts = members.map((e, i) => ({
		slug: bareSlug(e.id),
		title: e.data.title,
		index: i,
		current: i === index,
		available: true,
	}));

	const prevP = index > 0 ? parts[index - 1] : null;
	const nextP = index < parts.length - 1 ? parts[index + 1] : null;
	return {
		inSeries: true,
		name,
		index,
		total: parts.length,
		parts,
		prev: prevP ? { slug: prevP.slug, title: prevP.title } : null,
		next: nextP ? { slug: nextP.slug, title: nextP.title } : null,
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
