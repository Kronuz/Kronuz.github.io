#!/usr/bin/env node
// Renders the site logo and every icon from the vector master, src/assets/logo.svg
// (`npm run icons`). Each PNG is rasterized once, at its exact pixel size.
//
// The live variant goes to public/; every other variant goes to brand/variants/<name>/,
// so the alternatives are regenerated with it. `npm run icons -- --live green-gray` swaps.
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import sharp from 'sharp';

// Tracks color and the opaque tile behind it. iOS and Android flatten a transparent icon
// onto white, so the tile is a theme's page color chosen for contrast with the tracks.
const VARIANTS = {
	gray: { tracks: '#a7a7a7', tile: '#1a1a1a' }, // brand gray on the dark theme's page
	'green-gray': { tracks: '#465c56', tile: '#fdfdfc' }, // first favicon's tracks on the light page
};
// Stem darkening for tab sizes: thin strokes only partly cover their pixels there, and a
// gamma on alpha firms them up (0.5 starts closing the gaps between the green layers).
const GAMMA = { 16: 0.7, 32: 0.7, 48: 0.85 };

const { values: opt } = parseArgs({ options: { live: { type: 'string', default: 'gray' } } });
if (!VARIANTS[opt.live]) throw new Error(`unknown --live ${opt.live}; one of: ${Object.keys(VARIANTS).join(', ')}`);

const root = fileURLToPath(new URL('../', import.meta.url));
const master = readFileSync(`${root}src/assets/logo.svg`, 'utf8');
const [, viewBox, body] = master.match(/viewBox="([^"]+)"[^>]*>([\s\S]*)<\/svg>/);
const [x, y, w, h] = viewBox.trim().split(/\s+/).map(Number);
const cx = x + w / 2;
const cy = y + h / 2;
const square = (side) => `${cx - side / 2} ${cy - side / 2} ${side} ${side}`;
const t = Math.round(h / 0.74); // the logo fills 74% of a tile, inside the maskable safe circle (r = 40%)

async function png(markup, size, { opaque = false } = {}) {
	const sized = markup.replace('<svg ', `<svg width="${size}" height="${size}" `);
	const { data, info } = await sharp(Buffer.from(sized), { density: 72 })
		.ensureAlpha()
		.raw()
		.toBuffer({ resolveWithObject: true });
	if (info.width !== size || info.height !== size) throw new Error(`rendered ${info.width}x${info.height}, wanted ${size}`);
	const g = GAMMA[size];
	if (g) for (let i = 3; i < data.length; i += 4) data[i] = Math.round(255 * (data[i] / 255) ** g);
	const img = sharp(data, { raw: info });
	return (opaque ? img.removeAlpha() : img).png({ compressionLevel: 9 }).toBuffer();
}

// ICO with PNG frames: a 6-byte header, a 16-byte entry per frame, then the PNGs.
function ico(frames) {
	const head = Buffer.alloc(6 + 16 * frames.length);
	head.writeUInt16LE(1, 2);
	head.writeUInt16LE(frames.length, 4);
	let offset = head.length;
	frames.forEach(({ size, data }, i) => {
		const e = 6 + 16 * i;
		head.writeUInt8(size % 256, e);
		head.writeUInt8(size % 256, e + 1);
		head.writeUInt16LE(1, e + 4);
		head.writeUInt16LE(32, e + 6);
		head.writeUInt32LE(data.length, e + 8);
		head.writeUInt32LE(offset, e + 12);
		offset += data.length;
	});
	return Buffer.concat([head, ...frames.map((f) => f.data)]);
}

function out(path, data) {
	mkdirSync(dirname(root + path), { recursive: true });
	writeFileSync(root + path, data);
	console.log(`${path.padEnd(52)} ${String(data.length).padStart(6)} bytes`);
}

async function renderSet(dir, { tracks, tile }) {
	const art = body.replaceAll(VARIANTS.gray.tracks, tracks);
	const icon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${square(Math.max(w, h))}">${art}</svg>\n`;
	const opaque = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${square(t)}"><rect x="${cx - t / 2}" y="${cy - t / 2}" width="${t}" height="${t}" fill="${tile}"/>${art}</svg>`;
	out(`${dir}favicon.svg`, icon);
	const frames = [];
	for (const size of [16, 32, 48, 64, 128, 256]) frames.push({ size, data: await png(icon, size) });
	out(`${dir}favicon.ico`, ico(frames));
	for (const [name, size] of [['apple-touch-icon', 180], ['apple-touch-icon-167', 167], ['apple-touch-icon-152', 152], ['icon-192', 192], ['icon-512', 512]])
		out(`${dir}${name}.png`, await png(opaque, size, { opaque: true }));
	return art;
}

// The page logo (header and splash hero) is the master itself, whatever icons are live.
out('public/img/logo.svg', master);
for (const [name, variant] of Object.entries(VARIANTS)) {
	if (name === opt.live) {
		rmSync(`${root}brand/variants/${name}`, { recursive: true, force: true });
		await renderSet('public/', variant);
	} else {
		const art = await renderSet(`brand/variants/${name}/`, variant);
		out(`brand/variants/${name}/logo.svg`, `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}">${art}</svg>\n`);
	}
}
