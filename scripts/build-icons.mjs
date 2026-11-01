#!/usr/bin/env node
// Renders every site icon from the vector logo, src/assets/logo.svg (`npm run icons`).
// Each PNG is rasterized once, at its exact pixel size, so nothing is resampled.
//
//   npm run icons                                         light-gray tracks, dark tile (live set)
//   npm run icons -- --variant green-gray --out DIR       green-gray tracks, light tile
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import sharp from 'sharp';

// Tracks color and the opaque tile behind it. iOS and Android flatten a transparent icon
// onto white, so the tile is a theme's page color chosen for contrast with the tracks.
const VARIANTS = {
	gray: { tracks: '#a7a7a7', tile: '#1a1a1a' }, // brand grey on the dark theme's page
	'green-gray': { tracks: '#465c56', tile: '#fdfdfc' }, // first favicon's tracks on the light page
};
// Stem darkening for tab sizes: thin strokes only partly cover their pixels there, and a
// gamma on alpha firms them up (0.5 starts closing the gaps between the green layers).
const GAMMA = { 16: 0.7, 32: 0.7, 48: 0.85 };

const { values: opt } = parseArgs({ options: { variant: { type: 'string', default: 'gray' }, out: { type: 'string' } } });
const variant = VARIANTS[opt.variant];
if (!variant) throw new Error(`unknown --variant ${opt.variant}; one of: ${Object.keys(VARIANTS).join(', ')}`);
const outDir = opt.out ? new URL(`file://${opt.out.replace(/\/?$/, '/')}`) : new URL('../public/', import.meta.url);
mkdirSync(outDir, { recursive: true });

const master = readFileSync(new URL('../src/assets/logo.svg', import.meta.url), 'utf8');
const [, viewBox, body] = master.match(/viewBox="([^"]+)"[^>]*>([\s\S]*)<\/svg>/);
const [x, y, w, h] = viewBox.trim().split(/\s+/).map(Number);
const art = body.replaceAll(VARIANTS.gray.tracks, variant.tracks);
const cx = x + w / 2;
const cy = y + h / 2;
const square = (side) => `${cx - side / 2} ${cy - side / 2} ${side} ${side}`;

const icon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${square(Math.max(w, h))}">${art}</svg>\n`;
// The logo fills 74% of the tile's height, inside the maskable safe circle (radius 40%).
const t = Math.round(h / 0.74);
const tile = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${square(t)}"><rect x="${cx - t / 2}" y="${cy - t / 2}" width="${t}" height="${t}" fill="${variant.tile}"/>${art}</svg>`;

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

const out = (name, data) => {
	writeFileSync(new URL(name, outDir), data);
	console.log(`${name.padEnd(26)} ${String(data.length).padStart(6)} bytes`);
};

out('favicon.svg', icon);
const frames = [];
for (const size of [16, 32, 48, 64, 128, 256]) frames.push({ size, data: await png(icon, size) });
out('favicon.ico', ico(frames));
out('apple-touch-icon.png', await png(tile, 180, { opaque: true }));
out('apple-touch-icon-167.png', await png(tile, 167, { opaque: true }));
out('apple-touch-icon-152.png', await png(tile, 152, { opaque: true }));
out('icon-192.png', await png(tile, 192, { opaque: true }));
out('icon-512.png', await png(tile, 512, { opaque: true }));
