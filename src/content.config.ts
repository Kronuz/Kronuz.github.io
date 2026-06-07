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
					}),
				),
		}),
	}),
};
