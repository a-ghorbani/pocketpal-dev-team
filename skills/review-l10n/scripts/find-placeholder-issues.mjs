#!/usr/bin/env node
// Find {{placeholder}} mismatches in any locale relative to en.json.
// Always scans every JSON in the dir (no registry filter), so unwired locales are surfaced too.
// Usage: find-placeholder-issues.mjs <dir-with-locale-jsons>
import {readFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';

const dir = process.argv[2];
if (!dir) { console.error('usage: find-placeholder-issues.mjs <dir>'); process.exit(2); }

const en = JSON.parse(readFileSync(join(dir, 'en.json'), 'utf-8'));
function* leaves(obj, prefix = '') {
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) yield* leaves(v, p);
    else yield [p, v];
  }
}
function getAt(o, p) { return p.split('.').reduce((x, k) => (x ? x[k] : undefined), o); }

let total = 0;
for (const file of readdirSync(dir).filter(f => f.endsWith('.json') && f !== 'en.json')) {
  const lang = file.replace('.json', '');
  const data = JSON.parse(readFileSync(join(dir, file), 'utf-8'));
  const issues = [];
  for (const [p, enVal] of leaves(en)) {
    if (typeof enVal !== 'string') continue;
    const v = getAt(data, p);
    if (typeof v !== 'string') continue;
    const enP = (enVal.match(/\{\{(\w+)\}\}/g) || []).sort();
    const lP = (v.match(/\{\{(\w+)\}\}/g) || []).sort();
    if (JSON.stringify(enP) !== JSON.stringify(lP)) issues.push({key: p, en: enVal, v, enP, lP});
  }
  if (issues.length) {
    console.log(`\n## ${lang} — ${issues.length} placeholder mismatch(es)`);
    for (const i of issues) {
      console.log(`  key:  ${i.key}`);
      console.log(`  en:   ${JSON.stringify(i.en)}`);
      console.log(`  ${lang}:   ${JSON.stringify(i.v)}`);
      console.log(`  expected [${i.enP.join(', ')}]  found [${i.lP.join(', ')}]`);
    }
    total += issues.length;
  }
}
console.log(`\ntotal placeholder mismatches: ${total}`);
process.exit(total > 0 ? 1 : 0);
