import { getCollection } from 'astro:content';

// Project-space helpers (shared by both blogs). The model:
//   - A *project* is a `series` (its name is the project name), or a single standalone entry.
//   - Its *parts* are the entries sharing that series, sorted by `seriesOrder` then title.
//   - The *landing* is the first part (lowest seriesOrder): it carries the project-level card
//     metadata (tagline, tech, links, featured, order) and its body is the overview.
//   - Each part has its own `status`. The project page shows the non-landing parts as a status
//     board; the index shows one card per project with a status roll-up.
// Kept separate from the blog's series.mjs so that one stays blog-only (the shared
// TableOfContents reads `Astro.locals.projectSeries`, which the project route sets).

const isProd = import.meta.env.MODE === 'production';
const isPublished = (p) => p.data.draft !== true;
const visible = (p, currentId) => p.id === currentId || isPublished(p) || !isProd;

// Status groups for the board + roll-up, in display order. shipped + completed collapse to
// one "Done" group; everything else is its own group. Drives column order and chip order.
export const STATUS_GROUPS = [
	{ key: 'active', label: 'Active', statuses: ['active'] },
	{ key: 'blocked', label: 'Blocked', statuses: ['blocked'] },
	{ key: 'proposed', label: 'Proposed', statuses: ['proposed'] },
	{ key: 'paused', label: 'Paused', statuses: ['paused'] },
	{ key: 'done', label: 'Done', statuses: ['shipped', 'completed'] },
	{ key: 'dead', label: 'Dead', statuses: ['dead'] },
];
const groupOf = (status) => STATUS_GROUPS.find((g) => g.statuses.includes(status))?.key;

// Group every project entry into projects, each with its sorted parts and landing.
async function getProjects(currentId) {
	const items = (await getCollection('projects')).filter((p) => visible(p, currentId));
	const byKey = new Map();
	for (const e of items) {
		const key = e.data.series ?? `solo:${e.id}`;
		if (!byKey.has(key)) byKey.set(key, { series: e.data.series ?? null, parts: [] });
		byKey.get(key).parts.push(e);
	}
	return [...byKey.values()].map(({ series, parts }) => {
		parts.sort(
			(a, b) =>
				(a.data.seriesOrder ?? 0) - (b.data.seriesOrder ?? 0) ||
				a.data.title.localeCompare(b.data.title),
		);
		return { name: series ?? parts[0].data.title, landing: parts[0], parts };
	});
}

// The parts that appear on the board / in the roll-up: a multi-part project's non-landing
// parts, or a standalone project's single part. Only parts that declare a `status`.
const boardParts = (parts) =>
	(parts.length > 1 ? parts.slice(1) : parts).filter((p) => p.data.status);

// Non-zero status-group counts, in display order, for a set of parts.
function rollup(parts) {
	const counts = new Map();
	for (const p of parts) {
		const g = groupOf(p.data.status);
		if (g) counts.set(g, (counts.get(g) ?? 0) + 1);
	}
	return STATUS_GROUPS.filter((g) => counts.has(g.key)).map((g) => ({
		key: g.key,
		label: g.label,
		count: counts.get(g.key),
	}));
}

// Index view-models: one card per project. Featured first, then `order`, then name. A
// standalone project carries its own `status` (single badge); a multi-part one carries a
// roll-up of its parts' statuses.
export async function listProjects() {
	const projects = await getProjects(null);
	return projects
		.map((proj) => ({
			name: proj.name,
			landingSlug: proj.landing.id,
			data: proj.landing.data,
			single: proj.parts.length === 1,
			status: proj.landing.data.status,
			rollup: rollup(boardParts(proj.parts)),
		}))
		.sort(
			(a, b) =>
				Number(b.data.featured ?? false) - Number(a.data.featured ?? false) ||
				(a.data.order ?? 0) - (b.data.order ?? 0) ||
				a.name.localeCompare(b.name),
		);
}

// Project-page data for a given entry id: the project name, whether this entry is the
// landing, the status board (landing only), and the series stepper + prev/next (reusing the
// blog series shape with base '/projects' so the shared TableOfContents stepper just works).
export async function resolveProject(id) {
	const projects = await getProjects(id);
	const proj = projects.find((p) => p.parts.some((e) => e.id === id));
	if (!proj) return null;

	const parts = proj.parts;
	const index = parts.findIndex((e) => e.id === id);
	const multi = parts.length > 1;

	const bparts = boardParts(parts);
	const board = STATUS_GROUPS.map((g) => ({
		key: g.key,
		label: g.label,
		parts: bparts
			.filter((p) => groupOf(p.data.status) === g.key)
			.map((p) => ({ slug: p.id, title: p.data.title, status: p.data.status })),
	})).filter((col) => col.parts.length > 0);

	const stepParts = parts.map((e, i) => ({
		slug: e.id,
		title: e.data.title,
		index: i,
		current: i === index,
		reachable: isPublished(e) || !isProd,
		pending: !isPublished(e),
	}));
	const link = (p) => (p && p.reachable ? { slug: p.slug, title: p.title, pending: p.pending } : null);
	const prevP = index > 0 ? stepParts[index - 1] : null;
	const nextP = index < stepParts.length - 1 ? stepParts[index + 1] : null;
	const series = multi
		? {
				inSeries: true,
				base: '/projects',
				name: proj.name,
				index,
				total: parts.length,
				parts: stepParts,
				prev: link(prevP),
				next: link(nextP),
			}
		: { inSeries: false };

	return { name: proj.name, isLanding: index === 0, multi, board, rollup: rollup(bparts), series };
}

// Sidebar nav list (shown under "Projects" on /projects/ pages): the projects worth quick
// access — featured ones, plus any with an in-flight part (active/blocked/proposed/paused).
// Featured first, then `order`, then name; the project containing `currentSlug` is marked.
export async function listSidebarProjects(currentSlug) {
	const inFlight = ['active', 'blocked', 'proposed', 'paused'];
	const projects = await getProjects(currentSlug ?? null);
	return projects
		.filter(
			(proj) =>
				proj.landing.data.featured || proj.parts.some((e) => inFlight.includes(e.data.status)),
		)
		.sort(
			(a, b) =>
				Number(b.landing.data.featured ?? false) - Number(a.landing.data.featured ?? false) ||
				(a.landing.data.order ?? 0) - (b.landing.data.order ?? 0) ||
				a.name.localeCompare(b.name),
		)
		.map((proj) => ({
			name: proj.name,
			landingSlug: proj.landing.id,
			isCurrent: currentSlug ? proj.parts.some((e) => e.id === currentSlug) : false,
		}));
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
