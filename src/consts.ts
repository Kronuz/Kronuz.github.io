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

// Repository backing this blog. Used by footer and source links.
export const REPO_URL = 'https://github.com/Kronuz/Kronuz.github.io';

// Multi-tenant discussions Worker. PUBLIC_DISCUSSIONS_BACKEND overrides this for local
// development when testing against another Worker instance.
export const DISCUSSIONS_BACKEND = 'https://discussions.kronuz.workers.dev/kronuz';
// Login suffix dropped when displaying handles (cosmetic; e.g. "_sso"). Empty = as-is.
export const DISCUSSIONS_STRIP_SUFFIX = '';
// Public GIPHY key; when set, the composer shows a client-side GIF picker. Empty = no GIF button.
export const DISCUSSIONS_GIPHY_KEY = '';
