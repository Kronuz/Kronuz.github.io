import { getCollection } from 'astro:content';

// Project-space helpers (public blog only): list the projects collection, and resolve the
// two kinds of links a project page can show. Mirrors lib/series.mjs (the blog series
// engine) but over the `projects` collection, kept separate so the shared series.mjs stays
// blog-only (the internal mirror has no projects collection).

const isProd = import.meta.env.MODE === 'production';
const isPublished = (p) => p.data.draft !== true;

// All projects for the index: featured first, then `order`, then title. Drafts are hidden
// in production (kept in dev so the whole catalog previews), matching the blog. A series
// collapses to a single card here: only its first part (lowest seriesOrder) is listed; the
// rest are reachable from that project's page. Each returned item carries `parts` (1 for a
// standalone project, N for a series head) so a card can show an "N parts" hint.
export async function listProjects() {
	const items = (await getCollection('projects')).filter((p) => !isProd || isPublished(p));

	const seriesParts = new Map(); // series name -> visible parts
	for (const p of items) {
		const s = p.data.series;
		if (!s) continue;
		if (!seriesParts.has(s)) seriesParts.set(s, []);
		seriesParts.get(s).push(p);
	}
	const headId = (name) =>
		[...seriesParts.get(name)].sort(
			(a, b) => (a.data.seriesOrder ?? 0) - (b.data.seriesOrder ?? 0),
		)[0].id;
	const isHead = (p) => !p.data.series || headId(p.data.series) === p.id;

	return items
		.filter(isHead)
		.map((p) => ({
			id: p.id,
			data: p.data,
			parts: p.data.series ? seriesParts.get(p.data.series).length : 1,
		}))
		.sort(
			(a, b) =>
				Number(b.data.featured ?? false) - Number(a.data.featured ?? false) ||
				(a.data.order ?? 0) - (b.data.order ?? 0) ||
				a.data.title.localeCompare(b.data.title),
		);
}

// Project-internal series: parts sharing a `series` name, linked with a stepper/pager just
// like the blog series. prev/next point only at reachable parts (published always; a draft
// only in `npm run dev`), carrying `pending` so a dev-only draft link can be greyed.
export async function resolveProjectSeries(id) {
	const items = await getCollection('projects');
	const current = items.find((p) => p.id === id);
	const name = current?.data?.series;
	if (!name) return { inSeries: false };

	const isVisible = (p) => p.id === id || isPublished(p) || !isProd;
	const members = items
		.filter((p) => p.data.series === name && isVisible(p))
		.sort(
			(a, b) =>
				(a.data.seriesOrder ?? 0) - (b.data.seriesOrder ?? 0) ||
				a.data.title.localeCompare(b.data.title),
		);
	if (members.length <= 1) return { inSeries: false };

	const index = members.findIndex((p) => p.id === id);
	const parts = members.map((p, i) => ({
		slug: p.id,
		title: p.data.title,
		index: i,
		current: i === index,
		reachable: isPublished(p) || !isProd,
		pending: !isPublished(p),
	}));
	const prevP = index > 0 ? parts[index - 1] : null;
	const nextP = index < parts.length - 1 ? parts[index + 1] : null;
	const link = (p) => (p && p.reachable ? { slug: p.slug, title: p.title, pending: p.pending } : null);
	return { inSeries: true, base: '/projects', name, index, total: parts.length, parts, prev: link(prevP), next: link(nextP) };
}

// Cross-space links: a project's `related` blog-post slugs, resolved against the docs
// collection. Linked when the post is reachable (published always; a draft only in dev,
// greyed). In production an unpublished related post drops out, so nothing dead-links.
export async function resolveRelatedPosts(slugs) {
	if (!slugs || slugs.length === 0) return [];
	const docs = await getCollection('docs');
	const bareSlug = (id) => id.replace(/\.mdx?$/, '').split('/').pop();
	const bySlug = new Map(
		docs.filter((e) => e.id.startsWith('blog/')).map((e) => [bareSlug(e.id), e]),
	);
	return slugs
		.map((s) => {
			const e = bySlug.get(s);
			if (!e) return null;
			const reachable = e.data.draft !== true || !isProd;
			if (!reachable) return null;
			return { slug: s, title: e.data.title, pending: e.data.draft === true };
		})
		.filter(Boolean);
}
