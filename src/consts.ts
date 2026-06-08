// Place any global data in this file.
// You can import this data from anywhere in your site by using the `import` keyword.

export const SITE_TITLE = 'Kronuz.github.io';
export const SITE_DESCRIPTION =
	'Notes, experiments, and write-ups from Germán Méndez Bravo (Kronuz) — Python, C++, and systems at scale.';

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
