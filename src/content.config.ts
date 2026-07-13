import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { blogSchema } from 'starlight-blog/schema';

export const collections = {
	docs: defineCollection({
		loader: docsLoader(),
		schema: docsSchema({
			extend: (context) =>
				blogSchema(context).merge(
					z.object({
						// Optional smaller deck shown under the title.
						subtitle: z.string().optional(),
						// GitHub Discussion number backing this post's comments
						// (link-out). Stamped when the post is published.
						discussion: z.number().optional(),
						// Name of the article series this post belongs to (e.g.
						// "Opening Boxes"), and its position within that series.
						series: z.string().optional(),
						seriesOrder: z.number().optional(),
						// Chapter grouping within a long series: a display title (e.g.
						// "Lock-Free"). Parts sharing a chapter collapse into one section in
						// the sidebar stepper, in first-appearance order; the linear
						// seriesOrder path is unchanged. All parts must be tagged for grouping
						// to kick in, else the stepper stays a flat list.
						chapter: z.string().optional(),
						// On a *draft* part of a series, `upcoming: true` shows it greyed and
						// un-linked in the series stepper (a "disabled" item teasing a part
						// that's on the way), instead of hiding it. Ignored once the post is
						// published. No effect outside a series.
						upcoming: z.boolean().optional(),
						// Post type, shown as a small emoji badge before the title
						// (announcement / tutorial / note). Omit it for a plain
						// article, the default, which gets no badge.
						category: z.enum(['announcement', 'tutorial', 'note']).optional(),
					}),
				),
		}),
	}),
	// Projects are their own space (not Starlight docs, not blog posts): each is a page
	// under src/content/projects/, rendered by src/pages/projects/[slug].astro and listed
	// by src/pages/projects/index.astro. Kept out of the blog RSS, the blog index and /all/
	// for free, since none of those look at this collection.
	projects: defineCollection({
		loader: glob({ base: './src/content/projects', pattern: '**/*.{md,mdx}' }),
		schema: z.object({
				title: z.string(),
				// One-line deck shown under the title and on the index card.
				tagline: z.string().optional(),
				// Longer blurb for the index card and meta description.
				description: z.string().optional(),
				// Optional project logo (path under /public, e.g. /img/projects/mech.png).
				// Shown on the index card and floated beside the project page header.
				logo: z.string().optional(),
				// Tech tags (first one shown as the card's pill).
				tech: z.array(z.string()).default([]),
				// Canonical links.
				repo: z.string().optional(),
				website: z.string().optional(),
				docs: z.string().optional(),
				// Lifecycle, kept separate from `draft` (draft = visibility). Optional for now.
				status: z
					.enum(['proposed', 'active', 'blocked', 'paused', 'shipped', 'completed', 'dead'])
					.optional(),
				// Index ordering (ascending), then title. Featured projects sort first.
				order: z.number().optional(),
				featured: z.boolean().optional(),
				draft: z.boolean().optional(),
				// Project-internal grouping (multi-page projects), mirroring the blog series:
				// same `series` name + `seriesOrder` link the parts with a stepper/pager.
				series: z.string().optional(),
				seriesOrder: z.number().optional(),
				// Cross-space links to blog posts (by slug), e.g. the write-up behind a project.
				related: z.array(z.string()).default([]),
		}),
	}),
};
