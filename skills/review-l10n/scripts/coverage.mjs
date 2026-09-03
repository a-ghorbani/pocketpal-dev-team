#!/usr/bin/env node
// Compute per-locale coverage vs en.json.
// Usage: coverage.mjs <dir-with-locale-jsons> [--wired=<from wired-langs.mjs>]
//
// Without --wired the wired column reports `?`. It deliberately does not guess:
// a hardcoded list printed a confident `NO` next to three languages that were
// in fact shipping, which is worse than admitting it doesn't know.
import {readFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';

const dir = process.argv[2];
if (!dir) {
  console.error('usage: coverage.mjs <dir> [--wired=...]');
  process.exit(2);
}
const wiredArg = process.argv.find(a => a.startsWith('--wired='));
const wiredList = wiredArg ? wiredArg.slice('--wired='.length).split(',').filter(Boolean) : null;
const wired = wiredList ? new Set(wiredList) : null;

const en = JSON.parse(readFileSync(join(dir, 'en.json'), 'utf-8'));

function* leaves(obj, prefix = '') {
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) yield* leaves(v, p);
    else yield [p, v];
  }
}
function getAt(o, p) { return p.split('.').reduce((x, k) => (x ? x[k] : undefined), o); }
function strip(s) { return String(s).replace(/\s+/g, ' ').trim().toLowerCase(); }

const enLeaves = [...leaves(en)];
const enLeafCount = enLeaves.length;

const files = readdirSync(dir).filter(f => f.endsWith('.json') && f !== 'en.json');
const results = [];
for (const file of files) {
  const lang = file.replace('.json', '');
  let data;
  try { data = JSON.parse(readFileSync(join(dir, file), 'utf-8')); }
  catch (e) { results.push({lang, error: e.message}); continue; }

  let present = 0, translated = 0, identical = 0, placeholderMismatch = 0;
  for (const [p, enVal] of enLeaves) {
    if (typeof enVal !== 'string') continue;
    const v = getAt(data, p);
    if (typeof v !== 'string' || v.length === 0) continue;
    present++;
    if (strip(v) !== strip(enVal)) translated++; else identical++;
    const enP = (enVal.match(/\{\{(\w+)\}\}/g) || []).sort();
    const lP = (v.match(/\{\{(\w+)\}\}/g) || []).sort();
    if (JSON.stringify(enP) !== JSON.stringify(lP)) placeholderMismatch++;
  }
  results.push({
    lang,
    wired: wired ? wired.has(lang) : null,
    present, translated, identical, placeholderMismatch,
    presentPct: ((present / enLeafCount) * 100),
    translatedPct: ((translated / enLeafCount) * 100),
  });
}

console.log(`en.json leaf strings: ${enLeafCount}`);
console.log(
  wiredList
    ? `wired (${wiredList.length}): ${wiredList.join(', ')}\n`
    : 'wired: UNKNOWN (no --wired passed; run wired-langs.mjs)\n',
);
console.log('lang     wired  present  %present  translated  %translated  ==en  ph-mismatch');
console.log('-------  -----  -------  --------  ----------  -----------  ----  -----------');
for (const r of results.sort((a,b) => (b.translatedPct||0) - (a.translatedPct||0))) {
  if (r.error) { console.log(`${r.lang}: ERROR ${r.error}`); continue; }
  console.log(
    `${r.lang.padEnd(7)}  ${(r.wired === null ? '?' : r.wired ? 'yes' : 'NO ').padEnd(5)}  ` +
    `${String(r.present).padStart(5)}    ${r.presentPct.toFixed(1).padStart(6)}%  ` +
    `${String(r.translated).padStart(8)}    ${r.translatedPct.toFixed(1).padStart(7)}%  ` +
    `${String(r.identical).padStart(4)}  ${String(r.placeholderMismatch).padStart(5)}`,
  );
}

// Machine-readable artifact for downstream stages
const json = {enLeafCount, wired: wiredList, results};
const out = process.env.COVERAGE_JSON;
if (out) {
  const {writeFileSync} = await import('node:fs');
  writeFileSync(out, JSON.stringify(json, null, 2));
  console.log(`\nwrote ${out}`);
}
