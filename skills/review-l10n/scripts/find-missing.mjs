#!/usr/bin/env node
// List en.json string keys that are MISSING or EMPTY in a locale (the fill targets).
// Deliberately excludes keys present-but-identical-to-en (those may be intentional,
// e.g. brand names) — fill is only for genuinely absent strings.
// Usage: find-missing.mjs <dir-with-locale-jsons> <lang> [--json <out>]
import {readFileSync, writeFileSync} from 'node:fs';
import {join} from 'node:path';

const dir = process.argv[2];
const lang = process.argv[3];
if (!dir || !lang) {
  console.error('usage: find-missing.mjs <dir> <lang> [--json <out>]');
  process.exit(2);
}
const outArg = process.argv.indexOf('--json');
const outPath = outArg > -1 ? process.argv[outArg + 1] : null;

function* leaves(obj, prefix = '') {
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) yield* leaves(v, p);
    else yield [p, v];
  }
}
function getAt(o, p) { return p.split('.').reduce((x, k) => (x ? x[k] : undefined), o); }

const en = JSON.parse(readFileSync(join(dir, 'en.json'), 'utf-8'));
const loc = JSON.parse(readFileSync(join(dir, `${lang}.json`), 'utf-8'));

const missing = [];
for (const [key, enVal] of leaves(en)) {
  if (typeof enVal !== 'string' || enVal.length === 0) continue;
  const v = getAt(loc, key);
  if (typeof v !== 'string' || v.trim().length === 0) {
    missing.push({lang, key, en: enVal});
  }
}

if (outPath) {
  writeFileSync(outPath, JSON.stringify(missing, null, 2));
  console.error(`${lang}: ${missing.length} missing/empty → wrote ${outPath}`);
} else {
  console.log(JSON.stringify(missing, null, 2));
  console.error(`${lang}: ${missing.length} missing/empty`);
}
