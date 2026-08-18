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
	const parts = members.map((e, i) => {
		const published = isPublished(e);
		return {
			slug: bareSlug(e.id),
			title: e.data.title,
			index: i,
			current: i === index,
			// Chapter grouping title (frontmatter `chapter`), used only by the sidebar
			// stepper; null when this series isn't chapter-tagged.
			chapter: e.data.chapter ?? null,
			// Reachable = there's a page to link to. Published parts always have one; a draft
			// has a built page only in `npm run dev`, so it's reachable there but not in
			// production (where an unpublished part stays un-linked, so nothing dead-links).
			reachable: published || !isProd,
			// A not-yet-published part shown for preview (an `upcoming` tease, or any draft in
			// dev). Rendered greyed ("is-pending") wherever it appears.
			pending: !published,
		};
	});

	// Group parts into chapters (frontmatter `chapter`), for the sidebar stepper only.
	// Chapters are visual grouping: the linear path — parts[], prev/next, "Part N of M" —
	// is untouched. Parts that carry a `chapter` are grouped, in first-appearance order; a
	// part with NO chapter is "loose" and sits above the groups (an intro / index landing).
	// Grouping kicks in when there's at least one chaptered part and either more than one
	// chapter or a loose part to lift out; otherwise the stepper falls back to the flat list.
	let chapters = null;
	let looseParts = null;
	const chaptered = parts.filter((p) => p.chapter);
	const loose = parts.filter((p) => !p.chapter);
	if (chaptered.length > 0 && (new Set(chaptered.map((p) => p.chapter)).size > 1 || loose.length > 0)) {
		looseParts = loose;
		const byTitle = new Map();
		chapters = [];
		for (const p of chaptered) {
			let ch = byTitle.get(p.chapter);
			if (!ch) {
				ch = {
					title: p.chapter,
					id: p.chapter.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, ''),
					parts: [],
					hasCurrent: false,
				};
				byTitle.set(p.chapter, ch);
				chapters.push(ch);
			}
			ch.parts.push(p);
			if (p.current) ch.hasCurrent = true;
		}
	}

	const prevP = index > 0 ? parts[index - 1] : null;
	const nextP = index < parts.length - 1 ? parts[index + 1] : null;
	return {
		inSeries: true,
		base: '/blog',
		name,
		index,
		total: parts.length,
		parts,
		// Chapter grouping for the sidebar stepper (null when not chapter-tagged).
		chapters,
		// Parts with no `chapter`, lifted above the chapter groups (an intro / index). Null
		// unless chapters are in play; the flat view still lists them in seriesOrder.
		looseParts,
		// The pagers point at any reachable neighbor (published always; a draft only in
		// `npm run dev`), carrying `pending` so the pager can grey a dev-only draft link the
		// same way the stepper greys an is-pending item.
		prev: prevP && prevP.reachable ? { slug: prevP.slug, title: prevP.title, pending: prevP.pending } : null,
		next: nextP && nextP.reachable ? { slug: nextP.slug, title: nextP.title, pending: nextP.pending } : null,
	};
}

// Chronological prev/next across all blog posts (entries with a date), so we can render
// the blog pager ourselves right next to the series pager instead of where starlight-blog
// forces it (the post footer, below the comments). Reverse-chronological, matching the
// /blog/ index list pager: `prev` (the left button) is the NEWER post, `next` (the right
// button) is the OLDER post — so "Newer/Older" points the same way on a post and on the
// index. (The series pager is separate and keeps its own part-order Previous/Next.) Drafts
// are excluded only in production, matching starlight-blog.
export async function resolveChronological(term) {
	const slug = (term ?? '').split('/').pop();
	const docs = await getCollection('docs');
	const posts = docs
		.filter((e) => e.data.date && (import.meta.env.MODE !== 'production' || e.data.draft !== true))
		.sort((a, b) => b.data.date.getTime() - a.data.date.getTime() || a.data.title.localeCompare(b.data.title));
	const i = posts.findIndex((e) => bareSlug(e.id) === slug);
	if (i < 0) return { prev: null, next: null };
	const link = (e) => (e ? { slug: bareSlug(e.id), title: e.data.title } : null);
	// Array is newest-first: posts[i-1] is newer (prev/left), posts[i+1] is older (next/right).
	return { prev: link(posts[i - 1]), next: link(posts[i + 1]) };
}

// Total number of visible blog posts (entries with a date), matching the set the /blog/
// index paginates and the sidebar draws "Recent posts" from. Drafts count only in dev, like
// starlight-blog. Used by the sidebar to decide whether a "View more" link is warranted.
export async function countBlogPosts() {
	const docs = await getCollection('docs');
	return docs.filter(
		(e) => e.data.date && (import.meta.env.MODE !== 'production' || e.data.draft !== true),
	).length;
}

// Every article series, for the "Series" sidebar group and the /blog/series/ index.
// A series is any set of blog posts sharing a `series:` name; its landing is the
// lowest-`seriesOrder` part (which carries the series description). Visibility follows
// the same rules as resolveSeries: published parts always count; a plain draft counts
// only in dev (so the whole thing previews while writing); an `upcoming` draft always
// counts (the greyed tease). A series with fewer than two visible parts isn't a series
// yet, so it's omitted. Series are ordered by their most recent part's date (newest
// activity first), matching the blog's reverse-chronological feel; `currentSlug` (a bare
// post slug) marks the active series and its current part so the sidebar can light them.
export async function listAllSeries(currentSlug = null) {
	const isProd = import.meta.env.MODE === 'production';
	const isPublished = (e) => e.data.draft !== true;
	const isUpcoming = (e) => e.data.draft === true && e.data.upcoming === true;
	const visible = (e) => isPublished(e) || isUpcoming(e) || !isProd;

	const docs = await getCollection('docs');
	const byName = new Map();
	for (const e of docs) {
		if (!e.data.date || !e.data.series || !visible(e)) continue;
		const list = byName.get(e.data.series) ?? [];
		list.push(e);
		byName.set(e.data.series, list);
	}

	const series = [];
	for (const [name, list] of byName) {
		if (list.length < 2) continue; // a lone visible part isn't a series
		const parts = list.sort(
			(a, b) =>
				(a.data.seriesOrder ?? 0) - (b.data.seriesOrder ?? 0) ||
				(a.data.date?.getTime() ?? 0) - (b.data.date?.getTime() ?? 0) ||
				a.data.title.localeCompare(b.data.title),
		);
		const landing = parts[0];
		const latest = Math.max(...parts.map((e) => e.data.date?.getTime() ?? 0));
		series.push({
			name,
			landingSlug: bareSlug(landing.id),
			description: landing.data.subtitle ?? landing.data.excerpt ?? landing.data.description ?? '',
			total: parts.length,
			latest,
			isCurrent: parts.some((e) => bareSlug(e.id) === currentSlug),
			parts: parts.map((e) => ({
				slug: bareSlug(e.id),
				title: e.data.title,
				current: bareSlug(e.id) === currentSlug,
				// Reachable = has a built page to link to (published always; a draft only in dev).
				reachable: isPublished(e) || !isProd,
				pending: !isPublished(e),
			})),
		});
	}
	// Newest activity first.
	return series.sort((a, b) => b.latest - a.latest || a.name.localeCompare(b.name));
}
