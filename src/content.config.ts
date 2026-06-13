import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';
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
						// "Coming soon" teaser within a series: keep the post `draft: true`
						// (so no readable page is built) and set `upcoming: true` to show it
						// as a greyed, un-linked "Soon" item in the series stepper, to tease
						// parts you're still writing. Plain drafts stay hidden.
						upcoming: z.boolean().optional(),
						// Post type, shown as a small emoji badge before the title
						// (announcement / tutorial / note). Omit it for a plain
						// article, the default, which gets no badge.
						category: z.enum(['announcement', 'tutorial', 'note']).optional(),
					}),
				),
		}),
	}),
};
