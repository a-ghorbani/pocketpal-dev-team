#!/usr/bin/env node
// For each language changed in the PR, list ADDED and CHANGED entries (head vs base).
// Usage: diff-entries.mjs <head-dir> <base-dir> [<out-path>]
import {readFileSync, readdirSync, writeFileSync, existsSync} from 'node:fs';
import {join} from 'node:path';

const headDir = process.argv[2];
const baseDir = process.argv[3];
const out = process.argv[4];
if (!headDir || !baseDir) {
  console.error('usage: diff-entries.mjs <head-dir> <base-dir> [<out-path>]');
  process.exit(2);
}

const en = JSON.parse(readFileSync(join(headDir, 'en.json'), 'utf-8'));
function* leaves(obj, prefix = '') {
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) yield* leaves(v, p);
    else yield [p, v];
  }
}
function getAt(o, p) { return p.split('.').reduce((x, k) => (x ? x[k] : undefined), o); }
const allKeys = [...leaves(en)].map(([p]) => p);

const langs = readdirSync(baseDir)
  .filter(f => f.endsWith('.json') && f !== 'en.json')
  .map(f => f.replace('.json', ''));

const lines = [];
for (const lang of langs) {
  const headPath = join(headDir, `${lang}.json`);
  const basePath = join(baseDir, `${lang}.json`);
  if (!existsSync(headPath)) continue;
  const head = JSON.parse(readFileSync(headPath, 'utf-8'));
  const base = JSON.parse(readFileSync(basePath, 'utf-8'));

  const added = [], changed = [];
  for (const p of allKeys) {
    const enVal = getAt(en, p);
    if (typeof enVal !== 'string') continue;
    const h = getAt(head, p), b = getAt(base, p);
    if (typeof h !== 'string') continue;
    if (typeof b !== 'string') { added.push({key: p, en: enVal, head: h}); continue; }
    if (h !== b) changed.push({key: p, en: enVal, base: b, head: h});
  }
  lines.push('');
  lines.push('========================================');
  lines.push(`## ${lang}: +${added.length} added, ~${changed.length} changed`);
  lines.push('========================================');
  if (added.length) {
    lines.push('');
    lines.push('--- ADDED ---');
    for (const a of added) {
      lines.push(`[${a.key}]`);
      lines.push(`  en  : ${JSON.stringify(a.en)}`);
      lines.push(`  ${lang}  : ${JSON.stringify(a.head)}`);
    }
  }
  if (changed.length) {
    lines.push('');
    lines.push('--- CHANGED ---');
    for (const c of changed) {
      lines.push(`[${c.key}]`);
      lines.push(`  en   : ${JSON.stringify(c.en)}`);
      lines.push(`  was  : ${JSON.stringify(c.base)}`);
      lines.push(`  now  : ${JSON.stringify(c.head)}`);
    }
  }
}

const text = lines.join('\n') + '\n';
if (out) { writeFileSync(out, text); console.log(`wrote ${out} (${lines.length} lines)`); }
else { process.stdout.write(text); }
