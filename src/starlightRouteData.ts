import type { APIContext } from 'astro';
import { defineRouteMiddleware } from '@astrojs/starlight/route-data';
import { tocHasHeadings } from './lib/toc.mjs';
import { resolveSeries } from './lib/series.mjs';

export const onRequest = defineRouteMiddleware(async (context, next) => {
	await fitTitleAndToc(context);
	// starlight-blog's middleware resolves each post's authors and runs after this one.
	await next();
	addArticleMeta(context);
});

// Unify the right "On this page" column across the blog and the projects space: it should
// appear only when there is something real to show. Starlight (and starlight-blog) leave a
// truthy `toc` on heading-less pages — the blog index, tag/author lists, a project landing
// (a status board) or a standalone project — so the layout reserves an empty right gutter.
//
// `toc` is finalized before any route middleware runs and starlight-blog never touches it,
// so we can safely drop it here. We keep the column when the page has real headings, or when
// a series stepper will render in it: project pages hand their series in via
// `Astro.locals.projectSeries` (set by src/pages/projects/[slug].astro before StarlightPage
// runs this middleware); blog posts resolve their series from the entry id.
async function fitTitleAndToc(context: APIContext) {
	const route = context.locals.starlightRoute;
	const toc = route?.toc;

	// Lead the "On this page" list with the page title instead of Starlight's generic
	// "Overview" (matches the Xapiand docs). Mutating route.toc here covers both the desktop
	// right-sidebar TOC and the mobile "On this page" dropdown, which both read route.toc.
	const topItem = toc?.items?.find((it) => it.slug === '_top');
	if (topItem && route.entry?.data?.title) topItem.text = route.entry.data.title;

	if (!toc || tocHasHeadings(toc)) return;

	const locals = /** @type {{ projectSeries?: { inSeries?: boolean } }} */ (context.locals);
	let hasStepper = Boolean(locals.projectSeries?.inSeries);
	if (!hasStepper && route.entry?.data?.date) {
		const term = (route.entry.id ?? '').replace(/\.mdx?$/, '');
		const series = await resolveSeries(term);
		hasStepper = Boolean(series?.inSeries);
	}

	if (!hasStepper) route.toc = undefined;
}

// Reader views and link previews read a post's byline and date from <meta> tags, under the
// conventional names `author`, `article:author` and `article:published_time` (the JSON-LD
// BlogPosting from starlight-blog carries the same facts for extractors that read it). The
// author comes from starlight-blog's resolved post, so the tags match the byline on the page.
function addArticleMeta(context: APIContext) {
	const route = context.locals.starlightRoute;
	const entry = route?.entry;
	const date = entry?.data?.date as Date | undefined;
	if (!date) return;

	type BlogData = { posts: { entry: { id: string }; authors: { name: string }[] }[] };
	const blogs = (context.locals as { starlightBlogs?: Map<string, BlogData> }).starlightBlogs;
	const post = [...(blogs?.values() ?? [])].flatMap((blog) => blog.posts).find((p) => p.entry.id === entry.id);
	const names = (post?.authors ?? []).map((author) => author.name);

	if (names.length > 0) route.head.push({ tag: 'meta', attrs: { name: 'author', content: names.join(', ') } });
	for (const name of names) route.head.push({ tag: 'meta', attrs: { property: 'article:author', content: name } });
	route.head.push({ tag: 'meta', attrs: { property: 'article:published_time', content: date.toISOString() } });
}
