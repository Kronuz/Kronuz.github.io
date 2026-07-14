// Place any global data in this file.
// You can import this data from anywhere in your site by using the `import` keyword.

export const SITE_TITLE = 'Kronuz.github.io';
export const SITE_DESCRIPTION =
	'Notes, experiments, and write-ups from Germán Méndez Bravo (Kronuz) — Python, C++, and systems at scale.';

// Blog list pagination + the sidebar "Recent posts" size. Keep RECENT_POST_COUNT a multiple
// of BLOG_POST_COUNT so the sidebar's "View more" link lands on the /blog/ page that
// continues right after the recent list, with no overlap: page floor(RECENT / POST) + 1.
export const BLOG_POST_COUNT = 5; // posts per /blog/ index page (starlight-blog `postCount`)
export const RECENT_POST_COUNT = 20; // posts in the sidebar "Recent posts" group

// Repository backing this blog. Used by the giscus comments + footer links.
export const REPO_URL = 'https://github.com/Kronuz/Kronuz.github.io';

// giscus comments (works because this is a PUBLIC repo). Fill these from
// https://giscus.app after: (1) the repo is public, (2) Discussions is enabled,
// (3) the giscus app is installed, (4) you pick a category. The comments widget
// only renders once `categoryId` is set, so local builds stay clean until then.
export const GISCUS = {
	repo: 'Kronuz/Kronuz.github.io',
	repoId: 'MDEwOlJlcG9zaXRvcnkzMzY3MjcyMQ==',
	category: 'Announcements',
	categoryId: 'DIC_kwDOAgHOEc4C-uYu',
};

// Discussions engine (self-hosted, a giscus alternative; see discussions/). Staged so
// the public blog's engine matches the internal blog and the Xapiand docs. For now the
// public blog USES giscus (above); MarkdownContent renders <Discussions> only when a
// backend is configured and otherwise falls back to giscus, so setting DISCUSSIONS_BACKEND
// to the deployed backend URL is the whole swap. The PUBLIC_DISCUSSIONS_BACKEND build env
// var overrides this for local dev. Empty = giscus stays active.
export const DISCUSSIONS_BACKEND = 'https://discussions.kronuz.workers.dev';
// Login suffix dropped when displaying handles (cosmetic; e.g. "_sso"). Empty = as-is.
export const DISCUSSIONS_STRIP_SUFFIX = '';
// Public GIPHY key; when set, the composer shows a client-side GIF picker. Empty = no GIF button.
export const DISCUSSIONS_GIPHY_KEY = '';
