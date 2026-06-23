import { defineRouteMiddleware } from '@astrojs/starlight/route-data';
import { tocHasHeadings } from './lib/toc.mjs';
import { resolveSeries } from './lib/series.mjs';

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
export const onRequest = defineRouteMiddleware(async (context) => {
	const route = context.locals.starlightRoute;
	const toc = route?.toc;
	if (!toc || tocHasHeadings(toc)) return;

	const locals = /** @type {{ projectSeries?: { inSeries?: boolean } }} */ (context.locals);
	let hasStepper = Boolean(locals.projectSeries?.inSeries);
	if (!hasStepper && route.entry?.data?.date) {
		const term = (route.entry.id ?? '').replace(/\.mdx?$/, '');
		const series = await resolveSeries(term);
		hasStepper = Boolean(series?.inSeries);
	}

	if (!hasStepper) route.toc = undefined;
});
