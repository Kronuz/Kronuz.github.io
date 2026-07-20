#!/usr/bin/env node
// Publish a draft blog post in one step (public site).
//
//   npm run publish -- <slug> [--dry-run] [--no-push]
//
// Drops `draft: true`, stamps `date:` to today, commits, and pushes. GitHub
// Actions (.github/workflows/deploy.yml) then builds and deploys automatically.
// There is no manual deploy or per-post comments setup.

import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

const args = process.argv.slice(2);
const flags = new Set(args.filter((a) => a.startsWith("--")));
const slugArg = args.find((a) => !a.startsWith("--"));
const DRY = flags.has("--dry-run");
const NO_PUSH = flags.has("--no-push");

if (!slugArg) {
	console.error("Usage: npm run publish -- <slug> [--dry-run] [--no-push]");
	process.exit(1);
}

const slug = slugArg.replace(/\.mdx?$/, "").replace(/^.*\/blog\//, "").replace(/\/$/, "");
const candidates = ["md", "mdx"].map((ext) => resolve(ROOT, "src/content/docs/blog", `${slug}.${ext}`));
const file = candidates.find(existsSync);
if (!file) {
	console.error(`✗ No post at src/content/docs/blog/${slug}.{md,mdx}`);
	process.exit(1);
}

const raw = readFileSync(file, "utf8");
const m = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
if (!m) {
	console.error("✗ Could not parse frontmatter.");
	process.exit(1);
}
let [, fm, body] = m;
const title = (fm.match(/^title:\s*(.*)$/m) || [])[1]?.trim().replace(/^["']|["']$/g, "") || slug;

const today = (() => {
	const d = new Date();
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
})();

const nextFm = fm
	.split("\n")
	.filter((line) => !/^draft:\s*true\s*$/.test(line))
	.map((line) => (/^date:\s*/.test(line) ? `date: ${today}` : line))
	.join("\n");

if (DRY) {
	console.log(`• ${slug} ("${title}")`);
	console.log("\n--- frontmatter (dry-run) ---\n" + nextFm + "\n--- end ---\n");
	console.log("Dry run: nothing written.");
	process.exit(0);
}

writeFileSync(file, `---\n${nextFm}\n---\n${body}`);
console.log(`✓ ${slug}: draft removed, date: ${today}`);

execSync(`git add ${JSON.stringify(file)}`, { cwd: ROOT, stdio: "inherit" });
execSync(`git commit -q -m ${JSON.stringify(`Publish: ${title}`)}`, { cwd: ROOT, stdio: "inherit" });
if (NO_PUSH) {
	console.log("• --no-push: committed only. Push when ready (Actions deploys on push).");
	process.exit(0);
}
execSync(`git push`, { cwd: ROOT, stdio: "inherit" });
console.log(`✓ Pushed. GitHub Actions will build + deploy "${title}".`);
