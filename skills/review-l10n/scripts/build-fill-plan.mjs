#!/usr/bin/env node
// Validate machine-fill translations and assemble a Weblate write plan (overwrites
// at state=10 "needs-editing"). Used by --fill mode after the per-language
// translation subagents have written their output files.
//
// Inputs:
//   --missing-dir=<dir>  holds missing-<lang>.json (from find-missing.mjs)   [required]
//   --out-dir=<dir>      holds the subagents' output files: any *.json whose
//                        items are {lang,key,en,new,note?}  (e.g. out-ja-1.json) [required]
//   --langs=ja,ms        languages to assemble                                 [required]
//   --plan=<path>        output plan path (default: <out-dir>/fill-plan.json)
//   --state=10           Weblate state for the writes (default 10 = needs-editing)
//   --feedback=<f.json>  fetch-feedback.mjs output; keys with a pending suggestion or
//                        translator comment are skipped (a human is already on them)
//
// Validation per item (rejected with a logged problem, not written):
//   - key must be in that lang's missing list  - no duplicates
//   - new must be a non-empty string           - placeholders byte-identical to en
//   (whitespace-only en values, e.g. icon labels, are skipped silently)
import {readFileSync, writeFileSync, readdirSync, existsSync} from 'node:fs';
import {join} from 'node:path';

function arg(n, d) { const a = process.argv.find(x => x.startsWith(`--${n}=`)); return a ? a.slice(n.length + 3) : d; }
function ph(s) { return (String(s).match(/\{\{(\w+)\}\}/g) || []).sort(); }

const missingDir = arg('missing-dir');
const outDir = arg('out-dir');
const langs = (arg('langs') || '').split(',').filter(Boolean);
if (!missingDir || !outDir || !langs.length) {
  console.error('usage: build-fill-plan.mjs --missing-dir=<dir> --out-dir=<dir> --langs=ja,ms [--plan=<path>] [--state=10]');
  process.exit(2);
}
const planPath = arg('plan', join(outDir, 'fill-plan.json'));
const state = Number(arg('state', '10'));
const feedbackPath = arg('feedback');
const held = new Set();
if (feedbackPath && existsSync(feedbackPath)) {
  for (const u of JSON.parse(readFileSync(feedbackPath, 'utf-8')).units || []) if (u.human) held.add(`${u.lang}/${u.key}`);
}

// Gather all output items once, grouped by lang.
const byLang = {};
for (const f of readdirSync(outDir)) {
  if (!f.endsWith('.json') || f.startsWith('missing-') || f === 'fill-plan.json') continue;
  let items;
  try { items = JSON.parse(readFileSync(join(outDir, f), 'utf-8')); } catch { continue; }
  if (!Array.isArray(items)) continue;
  for (const it of items) { if (it && it.lang) (byLang[it.lang] ||= []).push(it); }
}

const plan = {
  target_id: `fill-${langs.join('-')}`,
  weblate: {project: 'pocketpal-ai', component: 'translations', base_url: 'https://hosted.weblate.org'},
  default_state: state,
  overwrites: [], suggestions: [], comments: [],
};
const problems = [];
const heldSkipped = [];
for (const lang of langs) {
  const mp = join(missingDir, `missing-${lang}.json`);
  if (!existsSync(mp)) { problems.push(`${lang}: no missing-${lang}.json`); continue; }
  const want = new Map(JSON.parse(readFileSync(mp, 'utf-8')).map(m => [m.key, m.en]));
  const seen = new Set();
  for (const it of (byLang[lang] || [])) {
    if (!want.has(it.key)) { problems.push(`${lang}/${it.key}: not in missing list`); continue; }
    if (seen.has(it.key)) { problems.push(`${lang}/${it.key}: duplicate`); continue; }
    const en = want.get(it.key);
    if (typeof en === 'string' && en.trim().length === 0) { seen.add(it.key); continue; } // icon/space label
    if (held.has(`${lang}/${it.key}`)) { seen.add(it.key); heldSkipped.push(`${lang}/${it.key}`); continue; }
    if (typeof it.new !== 'string' || !it.new.trim()) { problems.push(`${lang}/${it.key}: empty translation`); continue; }
    if (JSON.stringify(ph(en)) !== JSON.stringify(ph(it.new))) {
      problems.push(`${lang}/${it.key}: placeholder mismatch en[${ph(en)}] new[${ph(it.new)}]`); continue;
    }
    seen.add(it.key);
    plan.overwrites.push({lang, key: it.key, new: it.new});
  }
  const miss = [...want.keys()].filter(k => !seen.has(k));
  if (miss.length) problems.push(`${lang}: ${miss.length} keys not covered: ${miss.slice(0, 5).join(', ')}${miss.length > 5 ? '…' : ''}`);
  console.log(`${lang}: ${seen.size}/${want.size} covered`);
}

writeFileSync(planPath, JSON.stringify(plan, null, 2));
console.log(`\nwrote ${planPath}: ${plan.overwrites.length} overwrites (state=${state})`);
if (heldSkipped.length) console.log(`held (translator input pending, not filled): ${heldSkipped.join(', ')}`);
if (problems.length) { console.log(`\nPROBLEMS (${problems.length}):`); for (const p of problems) console.log('  - ' + p); }
else console.log('\nvalidation: clean');
