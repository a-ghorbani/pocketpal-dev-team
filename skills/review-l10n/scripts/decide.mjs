#!/usr/bin/env node
// Merge-gate engine for review-l10n --auto.
//
// Splits the gate into two layers:
//   1. MECHANICAL hard blockers (non-overridable): out-of-scope files, malformed
//      JSON, placeholder mismatches in changed wired langs, GitHub conflicts.
//      Any of these => HOLD, and no judgment can override it.
//   2. SEMANTIC findings (WRONG / AWKWARD) from the per-language subagents. These
//      do NOT auto-decide. When there are no hard blockers, the verdict is
//      ADJUDICATE: the main session reads all findings and makes the MERGE/HOLD call.
//
// Inputs:
//   --head=<dir>        locale JSONs at PR head            (required)
//   --base=<dir>        locale JSONs at PR base            (required)
//   --pr=<pr.json>      `gh pr view` json: {number, files:[{path}], mergeable, mergeStateStatus}
//   --findings=<f.json> per-language semantic findings (array; see schema below)  (optional)
//   --wired=fa,he,...   languages exposed in-app; only these gate the merge
//   --out=<dir>         where to write decision.json + plan.json (default: cwd)
//
// findings.json schema (produced by the per-language review subagents):
//   [{lang, key, severity:"WRONG"|"AWKWARD", en, current, new?, proposal?, note?}]
//   WRONG   → adjudicable. With `new` it becomes a Weblate overwrite candidate.
//   AWKWARD → deferrable. With `proposal` it becomes a Weblate suggestion.
//
// Output decision.json carries:
//   mechanical_verdict : "HOLD" | "ADJUDICATE"
//   decision           : "HOLD" (when mechanical) | null (pending session adjudication)
// The session sets the final decision via apply-decision.sh --decision=MERGE|HOLD.
//
// Exit: 0 = ADJUDICATE (pending), 1 = mechanical HOLD, 2 = usage error.
import {readFileSync, readdirSync, writeFileSync, existsSync} from 'node:fs';
import {join} from 'node:path';

function arg(name, dflt) {
  const a = process.argv.find(x => x.startsWith(`--${name}=`));
  return a ? a.slice(name.length + 3) : dflt;
}

const headDir = arg('head');
const baseDir = arg('base');
if (!headDir || !baseDir) {
  console.error('usage: decide.mjs --head=<dir> --base=<dir> [--pr=pr.json] [--findings=f.json] [--wired=...] [--out=dir]');
  process.exit(2);
}
const prPath = arg('pr');
const findingsPath = arg('findings');
const outDir = arg('out', '.');
const wired = new Set(
  arg('wired', 'fa,he,id,ja,ko,ms,ru,uk,zh,zh_Hant').split(',').filter(Boolean),
);

const LOCALE_PATH = /^src\/locales\/[^/]+\.json$/;

function* leaves(obj, prefix = '') {
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) yield* leaves(v, p);
    else yield [p, v];
  }
}
function getAt(o, p) { return p.split('.').reduce((x, k) => (x ? x[k] : undefined), o); }
function placeholders(s) { return (String(s).match(/\{\{(\w+)\}\}/g) || []).sort(); }

const en = JSON.parse(readFileSync(join(headDir, 'en.json'), 'utf-8'));
const enLeaves = [...leaves(en)].filter(([, v]) => typeof v === 'string');

const pr = prPath ? JSON.parse(readFileSync(prPath, 'utf-8')) : {};
const changedPaths = (pr.files || []).map(f => f.path);

// ---- Layer 1: MECHANICAL hard blockers (non-overridable) ----
const hardBlockers = [];

// Scope: a Weblate PR must touch only src/locales/*.json. Anything else is a
// safety stop — never auto-merge a mis-scoped or tampered PR.
for (const p of changedPaths) {
  if (!LOCALE_PATH.test(p)) hardBlockers.push({kind: 'scope', detail: p});
}

const changedLangs = changedPaths
  .filter(p => LOCALE_PATH.test(p))
  .map(p => p.replace(/^src\/locales\//, '').replace(/\.json$/, ''));
const gateLangs = changedLangs.filter(l => wired.has(l));

// JSON validity + placeholder integrity for each gated (wired, changed) lang.
for (const lang of gateLangs) {
  const f = join(headDir, `${lang}.json`);
  if (!existsSync(f)) continue;
  let data;
  try { data = JSON.parse(readFileSync(f, 'utf-8')); }
  catch (e) { hardBlockers.push({kind: 'malformed-json', lang, detail: e.message}); continue; }
  for (const [p, enVal] of enLeaves) {
    const v = getAt(data, p);
    if (typeof v !== 'string') continue;
    if (JSON.stringify(placeholders(enVal)) !== JSON.stringify(placeholders(v))) {
      hardBlockers.push({
        kind: 'placeholder', lang, key: p,
        detail: `expected [${placeholders(enVal).join(', ')}] found [${placeholders(v).join(', ')}]`,
        en: enVal, current: v,
      });
    }
  }
}

// GitHub mergeability. CONFLICTING can't be merged regardless of content.
const mergeable = pr.mergeable ?? 'UNKNOWN';
const conflicting = mergeable === 'CONFLICTING';
if (conflicting) hardBlockers.push({kind: 'conflict', detail: 'PR has merge conflicts on GitHub'});

// ---- Layer 2: SEMANTIC findings (adjudicable, never auto-decide) ----
const findings = findingsPath && existsSync(findingsPath)
  ? JSON.parse(readFileSync(findingsPath, 'utf-8'))
  : [];
const wrong = [];     // WRONG in a wired lang — the session adjudicates these
const awkward = [];   // AWKWARD — deferrable suggestions
const ignoredUnwired = [];
for (const fi of findings) {
  if (fi.severity === 'WRONG') {
    (wired.has(fi.lang) ? wrong : ignoredUnwired).push(fi);
  } else if (fi.severity === 'AWKWARD') {
    awkward.push(fi);
  }
}

const mechanicalHold = hardBlockers.length > 0;
const mechanical_verdict = mechanicalHold ? 'HOLD' : 'ADJUDICATE';
const decision = mechanicalHold ? 'HOLD' : null; // null = pending session adjudication

// ---- Weblate write plan (used regardless of final call) ----
const plan = {
  target_id: pr.number ? `PR-${pr.number}` : 'unknown',
  weblate: {project: 'pocketpal-ai', component: 'translations', base_url: 'https://hosted.weblate.org'},
  default_state: 10,
  overwrites: [],
  suggestions: [],
  comments: [],
};
// Hard placeholder blockers without a proposed fix → flag comment so a human sees it.
for (const b of hardBlockers) {
  if (b.kind === 'placeholder') {
    plan.comments.push({lang: b.lang, key: b.key, comment: `[review-l10n] blocker (placeholder): ${b.detail}`});
  }
}
// WRONG findings → overwrite if a concrete fix is given, else a flag comment.
for (const w of wrong) {
  if (w.new) plan.overwrites.push({lang: w.lang, key: w.key, current: w.current, new: w.new, comment: w.note});
  else plan.comments.push({lang: w.lang, key: w.key, comment: `[review-l10n] flagged WRONG: ${w.note || ''}`});
}
// AWKWARD → suggestions.
for (const a of awkward) {
  if (a.proposal) plan.suggestions.push({lang: a.lang, key: a.key, current: a.current, proposal: a.proposal, comment: a.note});
}

const hardReasons = hardBlockers.map(b =>
  b.kind === 'scope' ? `out-of-scope file: ${b.detail}`
  : b.kind === 'malformed-json' ? `${b.lang}: malformed JSON`
  : b.kind === 'placeholder' ? `${b.lang}/${b.key}: placeholder mismatch`
  : b.kind === 'conflict' ? 'PR has merge conflicts on GitHub'
  : JSON.stringify(b),
);

const decisionObj = {
  decision,                 // null until the session adjudicates (unless mechanical HOLD)
  mechanical_verdict,
  adjudication: null,       // session fills {decision, reasoning} when verdict=ADJUDICATE
  pr: pr.number ?? null,
  mergeable, mergeStateStatus: pr.mergeStateStatus ?? null,
  gateLangs,
  counts: {
    hardBlockers: hardBlockers.length,
    wrong: wrong.length,
    awkward: awkward.length,
    overwrites: plan.overwrites.length,
    suggestions: plan.suggestions.length,
    comments: plan.comments.length,
  },
  hardBlockers, hardReasons,
  wrong, awkward, ignoredUnwired,
};

writeFileSync(join(outDir, 'decision.json'), JSON.stringify(decisionObj, null, 2));
writeFileSync(join(outDir, 'plan.json'), JSON.stringify(plan, null, 2));

console.log(`mechanical verdict: ${mechanical_verdict}  (pr=${decisionObj.pr ?? '?'}, gated langs: ${gateLangs.join(', ') || 'none'})`);
console.log(`hard blockers=${hardBlockers.length} | semantic: wrong=${wrong.length} awkward=${awkward.length}`);
console.log(`plan: overwrites=${plan.overwrites.length} suggestions=${plan.suggestions.length} comments=${plan.comments.length}`);
if (hardReasons.length) {
  console.log('\nHard HOLD (non-overridable):');
  for (const r of hardReasons) console.log(`  - ${r}`);
}
if (mechanical_verdict === 'ADJUDICATE') {
  console.log(`\n${wrong.length} WRONG finding(s) need session adjudication → MERGE or HOLD.`);
  for (const w of wrong) console.log(`  - ${w.lang}/${w.key}: ${w.note || ''}`);
}
console.log(`\nwrote ${join(outDir, 'decision.json')} and ${join(outDir, 'plan.json')}`);
process.exit(mechanicalHold ? 1 : 0);
