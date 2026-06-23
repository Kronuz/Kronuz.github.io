// Starlight always seeds a route's table of contents with one synthetic top entry
// (slug "_top", labelled "Overview") and appends the page's real headings after it.
// So a page with no headings still has a truthy `toc` of exactly that one item, which
// is what makes Starlight reserve the right "On this page" column (an empty gutter).
//
// `tocHasHeadings` tells those two apart: true only when there is a real heading
// beyond the synthetic top item. Shared by the route middleware (which drops the
// empty column) and the TableOfContents override (which then hides the bare
// "Overview" list, leaving only the series stepper when there is one).
const TOP_SLUG = '_top';

export function tocHasHeadings(toc) {
	if (!toc?.items?.length) return false;
	const stack = [...toc.items];
	while (stack.length > 0) {
		const item = stack.pop();
		if (item.slug !== TOP_SLUG) return true;
		if (item.children?.length) stack.push(...item.children);
	}
	return false;
}
