/**
 * Generate the blog's Expressive Code (Shiki) themes (dark + light).
 *
 *   node scripts/build-kronuz-themes.mjs
 *
 * The DARK palette is the classic Kronuz palette (the exact colors from the
 * original 0.0.6 editor theme, github.com/Kronuz/kronuz-theme-vscode), so code
 * looks identical in the editor and on the blog. The LIGHT theme is derived
 * from it with the same mathematical transform the editor uses: invert
 * lightness (hue kept), brighten neutral surfaces toward white, and keep
 * chromatic colors deep + saturated so they don't wash out on the light page.
 *
 * Writes src/styles/kronuz-dark.json and src/styles/kronuz-light.json.
 */
import { writeFileSync } from "node:fs";

const parseHex = (hex) => {
  let m = hex.slice(1), a = "";
  if (m.length === 8) { a = m.slice(6); m = m.slice(0, 6); }
  else if (m.length === 4) { a = m[3] + m[3]; m = m.slice(0, 3); }
  if (m.length === 3) m = [...m].map((c) => c + c).join("");
  return [parseInt(m.slice(0, 2), 16) / 255, parseInt(m.slice(2, 4), 16) / 255, parseInt(m.slice(4, 6), 16) / 255, a];
};
const rgb2hsl = (r, g, b) => {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn, l = (mx + mn) / 2;
  let s = 0, h = 0;
  if (d) {
    s = d / (1 - Math.abs(2 * l - 1));
    switch (mx) { case r: h = ((g - b) / d) % 6; break; case g: h = (b - r) / d + 2; break; default: h = (r - g) / d + 4; }
    h = (h * 60 + 360) % 360;
  }
  return [h, s * 100, l * 100];
};
const hsl = (h, s, l) => {
  s /= 100; l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
  const to = (x) => Math.round(255 * x).toString(16).padStart(2, "0");
  return `#${to(f(0))}${to(f(8))}${to(f(4))}`;
};
const toLight = (hex) => {
  if (typeof hex !== "string" || hex[0] !== "#") return hex;
  const [r, g, b, a] = parseHex(hex);
  const [h, s, l] = rgb2hsl(r, g, b);
  if (s < 12) return hsl(h, s, l < 28 ? 92 + l * 0.28 : Math.max(16, 100 - l)) + a;
  const luminous = h >= 55 && h <= 175;
  const L = Math.max(28, Math.min(100 - l, luminous ? 32 : 40));
  const S = Math.min(92, s * 1.2 + 12);
  return hsl(h, S, L) + a;
};

// The classic Kronuz dark palette (exact 0.0.6 colors).
const DARK = {
  bg: "#383838", fg: "#c8c6c5", dim: "#7a7775", soft: "#9a9794", sel: "#3366ff55",
  comment: "#95815e", string: "#a5c261", number: "#a5c260", regexp: "#c7d87b", escape: "#d08442",
  keyword: "#cc7833", func: "#e8bf6a", type: "#da4939", cls: "#ffd68d", tag: "#caa473",
  vari: "#e8e6e5", param: "#fde9bbdd", lang: "#d0d0ff", constLang: "#6e9cbe", raw: "#d687bf", link: "#6089b4",
  heading: "#fd971f", mdBold: "#437cb9", mdItalic: "#7ea4cc", list: "#9aa83a",
  ins: "#219186", del: "#dc322f", chg: "#cb4b16", invalid: "#ff0b00",
};

function theme(variant) {
  const dark = variant === "dark";
  const c = dark ? DARK : Object.fromEntries(Object.entries(DARK).map(([k, v]) => [k, toLight(v)]));
  const sel = dark ? "#3366ff55" : "#3366ff22";

  const t = (scope, foreground, fontStyle) => ({
    scope,
    settings: { ...(foreground ? { foreground } : {}), ...(fontStyle ? { fontStyle } : {}) },
  });
  const tokenColors = [
    t("comment, punctuation.definition.comment", c.comment, "italic"),
    t("string, string.quoted, string.template, meta.string", c.string),
    t("constant.character.escape, constant.other.placeholder", c.escape),
    t("string.regexp, keyword.operator.regexp", c.regexp),
    t("constant.numeric, constant.numeric.integer, constant.numeric.float, keyword.other.unit", c.number),
    t("constant.language, constant.language.boolean, constant.language.null, constant.language.undefined", c.constLang),
    t("constant.other, support.constant", c.keyword),
    t("keyword, keyword.control, keyword.other, keyword.declaration", c.keyword),
    t("keyword.operator, keyword.operator.new, punctuation.accessor", c.keyword),
    t("storage, storage.type, storage.modifier", c.keyword),
    t("entity.name.function, support.function, meta.function-call entity.name.function, variable.function", c.func),
    t("entity.name.type, entity.name.namespace, support.type", c.type),
    t("entity.name.class", c.cls),
    t("support.class", c.func),
    t("entity.other.inherited-class", c.tag),
    t("entity.name.tag, punctuation.definition.tag", c.tag),
    t("entity.other.attribute-name", c.vari),
    t("support.type.property-name, meta.object-literal.key, support.type.property-name.json, support.type.property-name.css, entity.name.tag.yaml", c.vari),
    t("variable, variable.other, variable.other.readwrite, meta.definition.variable", c.vari),
    t("variable.other.constant, variable.other.enummember", c.keyword),
    t("variable.parameter, meta.function.parameters", c.param, "italic"),
    t("variable.language, variable.language.this, variable.language.self, variable.language.super", c.lang, "italic"),
    t("entity.name.function.decorator, meta.decorator, punctuation.decorator, meta.annotation, storage.type.annotation", c.func),
    t("punctuation, meta.brace, punctuation.separator, punctuation.terminator", c.fg),
    t("entity.name.label, support.other.namespace", c.func),
    t("markup.heading, markup.heading entity.name, entity.name.section", c.heading, "bold"),
    t("markup.bold", c.mdBold, "bold"),
    t("markup.italic", c.mdItalic, "italic"),
    t("markup.underline.link, markup.link, string.other.link", c.link, "underline"),
    t("markup.inline.raw, markup.raw, markup.fenced_code", c.raw),
    t("markup.quote", c.tag, "italic"),
    t("markup.list punctuation.definition.list.begin", c.list),
    t("markup.inserted, markup.inserted.diff", c.ins),
    t("markup.deleted, markup.deleted.diff", c.del),
    t("markup.changed, markup.changed.diff", c.chg),
    t("meta.diff.range, punctuation.definition.range.diff", c.lang),
    t("invalid, invalid.illegal", c.invalid),
    t("invalid.deprecated", c.keyword),
  ];

  return {
    name: dark ? "kronuz-dark" : "kronuz-light",
    type: variant,
    colors: {
      "editor.background": c.bg,
      "editor.foreground": c.fg,
      "editor.selectionBackground": sel,
    },
    tokenColors,
  };
}

for (const v of ["dark", "light"]) {
  const th = theme(v);
  writeFileSync(new URL(`../src/styles/${th.name}.json`, import.meta.url), JSON.stringify(th, null, 2) + "\n");
  console.log(`wrote src/styles/${th.name}.json (bg ${th.colors["editor.background"]})`);
}
