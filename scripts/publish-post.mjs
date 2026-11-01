#!/usr/bin/env node
// Publish a draft blog post in one step (public site).
//
//   npm run publish -- <slug> [--date <date>] [--dry-run] [--no-push]
//
// Drops `draft: true` (and `upcoming: true`), sets `date:` to today or to --date, commits, and
// pushes. GitHub Actions (.github/workflows/deploy.yml) then builds and deploys automatically.
// --date takes YYYY-MM-DD or an ISO date-time (2026-08-06T09:30, with an optional Z or offset);
// use it to publish a draft under the date it was written (AGENTS.md, "Publishing a backlog").
// --no-push commits only, so several posts can go out in one push.

import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const USAGE = "Usage: npm run publish -- <slug> [--date YYYY-MM-DD[THH:MM[:SS][Z|±HH:MM]]] [--dry-run] [--no-push]";

const args = process.argv.slice(2);
const flags = new Set();
const positional = [];
let dateArg;
for (let i = 0; i < args.length; i++) {
	const a = args[i];
	if (a === "--date") {
		dateArg = args[++i];
		if (dateArg === undefined) {
			console.error(`✗ --date needs a value.\n${USAGE}`);
			process.exit(1);
		}
	} else if (a.startsWith("--date=")) {
		dateArg = a.slice("--date=".length);
	} else if (a.startsWith("--")) {
		flags.add(a);
	} else {
		positional.push(a);
	}
}
const unknown = [...flags].filter((f) => !["--dry-run", "--no-push"].includes(f));
if (unknown.length || positional.length !== 1) {
	console.error((unknown.length ? `✗ Unknown option ${unknown.join(", ")}.\n` : "") + USAGE);
	process.exit(1);
}
const slugArg = positional[0];
const DRY = flags.has("--dry-run");
const NO_PUSH = flags.has("--no-push");

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
if (!/^draft:\s*true\s*$/m.test(fm)) {
	console.error(`✗ ${slug} is not a draft (no \`draft: true\`); publishing it again would change its date.`);
	process.exit(1);
}
const title = (fm.match(/^title:\s*(.*)$/m) || [])[1]?.trim().replace(/^["']|["']$/g, "") || slug;

const today = (() => {
	const d = new Date();
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
})();

// A YAML timestamp the content schema reads as a date: a calendar day or an ISO date-time.
const DATE_RE = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})?)?$/;
let date = today;
if (dateArg !== undefined) {
	const [y, mo, d] = dateArg.slice(0, 10).split("-").map(Number);
	const day = new Date(Date.UTC(y, mo - 1, d));
	const realDay = day.getUTCFullYear() === y && day.getUTCMonth() === mo - 1 && day.getUTCDate() === d;
	if (!DATE_RE.test(dateArg) || !realDay || Number.isNaN(Date.parse(dateArg))) {
		console.error(`✗ --date ${dateArg} is not a date (YYYY-MM-DD or YYYY-MM-DDTHH:MM[:SS][Z|±HH:MM]).`);
		process.exit(1);
	}
	if (dateArg.slice(0, 10) > today) {
		console.error(`✗ --date ${dateArg} is after today (${today}); a future date would publish now under a later date.`);
		process.exit(1);
	}
	// YAML reads a date-time only with seconds; without them it stays a string the schema rejects.
	date = dateArg.replace(/T(\d{2}:\d{2})(?=Z|[+-]|$)/, "T$1:00");
}

const nextFm = fm
	.split("\n")
	.filter((line) => !/^(draft|upcoming):\s*true\s*$/.test(line))
	.map((line) => (/^date:\s*/.test(line) ? `date: ${date}` : line))
	.join("\n");

if (DRY) {
	console.log(`• ${slug} ("${title}")`);
	console.log("\n--- frontmatter (dry-run) ---\n" + nextFm + "\n--- end ---\n");
	console.log("Dry run: nothing written.");
	process.exit(0);
}

writeFileSync(file, `---\n${nextFm}\n---\n${body}`);
console.log(`✓ ${slug}: draft removed, date: ${date}`);

execSync(`git add ${JSON.stringify(file)}`, { cwd: ROOT, stdio: "inherit" });
execSync(`git commit -q -m ${JSON.stringify(`Publish: ${title}`)}`, { cwd: ROOT, stdio: "inherit" });
if (NO_PUSH) {
	console.log("• --no-push: committed only. Push when ready (Actions deploys on push).");
	process.exit(0);
}
execSync(`git push`, { cwd: ROOT, stdio: "inherit" });
console.log(`✓ Pushed. GitHub Actions will build + deploy "${title}".`);
