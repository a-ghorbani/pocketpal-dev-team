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
//   --wired=fa,he,...   languages exposed in-app, from wired-langs.mjs (derived
//                       from src/locales/index.ts — never hand-written here).
//                       Omitted or empty => every changed locale is gated, because
//                       a gate that silently narrows its own scope is worse than
//                       one that over-reports.
//   --feedback=<f.json> fetch-feedback.mjs output. Units with translator input are
//                       HELD: a WRONG finding there becomes a flag comment, never an
//                       overwrite, and AWKWARD suggestions are dropped (the feedback
//                       reviewer answers that thread instead). If the file is missing
//                       every overwrite is downgraded to a comment — never write blind.
//   --max-suggestions=N per-language cap on AWKWARD suggestions posted per run (default 10);
//                       the overflow is recorded, not posted — a volunteer must never be flooded.
//   --out=<dir>         where to write decision.json + plan.json (default: cwd)
//
// findings.json schema (produced by the per-language review subagents):
//   [{lang, key, severity:"WRONG"|"AWKWARD", kind, en, current, new?, proposal?, note?, source?}]
//   kind    → meaning | grammar | orthography | style | brand | placeholder
//   source  → URL actually consulted (CLDR, a dictionary, a style guide). REQUIRED for
//             grammar and orthography findings: a norm the model merely believes is
//             dropped, not posted. Model-internal knowledge is not a source.
//   WRONG   → adjudicable. With `new` it becomes a Weblate overwrite candidate.
//   AWKWARD → deferrable. With `proposal` it becomes a Weblate suggestion, unless the
//             language has an active translator (feedback.active_translators), in
//             which case only WRONG findings are acted on.
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
const feedbackPath = arg('feedback');
const maxSuggestions = Number(arg('max-suggestions', '10'));
const outDir = arg('out', '.');
const wiredArg = (arg('wired', '') || '').split(',').filter(Boolean);
const wiredKnown = wiredArg.length > 0;
const wired = new Set(wiredArg);
const wiredSource = wiredKnown ? 'derived' : 'unknown-gate-all';

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
// With no derived wired list we cannot tell shipping locales from dormant ones,
// so everything changed is gated. Over-blocking is recoverable; under-blocking
// ships a broken placeholder.
const gateLangs = wiredKnown ? changedLangs.filter(l => wired.has(l)) : [...changedLangs];
const skippedLangs = changedLangs.filter(l => !gateLangs.includes(l));

// JSON validity + placeholder integrity. These run on EVERY changed locale —
// the checks are free and a malformed placeholder is a latent bug whether or not
// the locale ships today. Only whether they *block* depends on wiring.
const structuralWarnings = [];
for (const lang of changedLangs) {
  const sink = gateLangs.includes(lang) ? hardBlockers : structuralWarnings;
  const f = join(headDir, `${lang}.json`);
  if (!existsSync(f)) continue;
  let data;
  try { data = JSON.parse(readFileSync(f, 'utf-8')); }
  catch (e) { sink.push({kind: 'malformed-json', lang, detail: e.message}); continue; }
  for (const [p, enVal] of enLeaves) {
    const v = getAt(data, p);
    if (typeof v !== 'string') continue;
    if (JSON.stringify(placeholders(enVal)) !== JSON.stringify(placeholders(v))) {
      sink.push({
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
const unsourced = []; // grammar/orthography claims with no reference — never posted
const NORM_KINDS = new Set(['grammar', 'orthography']);
const hasSource = fi => typeof fi.source === 'string' && /^https?:\/\//.test(fi.source.trim());
const isGated = lang => (wiredKnown ? wired.has(lang) : true);
for (const fi of findings) {
  if (NORM_KINDS.has(fi.kind) && !hasSource(fi)) { unsourced.push(fi); continue; }
  if (fi.severity === 'WRONG') {
    (isGated(fi.lang) ? wrong : ignoredUnwired).push(fi);
  } else if (fi.severity === 'AWKWARD') {
    awkward.push(fi);
  }
}

const mechanicalHold = hardBlockers.length > 0;
const mechanical_verdict = mechanicalHold ? 'HOLD' : 'ADJUDICATE';
const decision = mechanicalHold ? 'HOLD' : null; // null = pending session adjudication

// ---- Translator-held units: never overwrite where a human has spoken ----
const feedbackKnown = Boolean(feedbackPath && existsSync(feedbackPath));
const heldUnits = new Set();
const activeLangs = new Set();
if (feedbackKnown) {
  const fb = JSON.parse(readFileSync(feedbackPath, 'utf-8'));
  for (const u of fb.units || []) if (u.human) heldUnits.add(`${u.lang}/${u.key}`);
  for (const l of Object.keys(fb.active_translators || {})) activeLangs.add(l);
}
const isHeld = (lang, key) => !feedbackKnown || heldUnits.has(`${lang}/${key}`);

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
// Same defect in a non-shipping locale: still worth a comment so it is fixed
// before that locale is ever wired, but it does not hold the merge.
for (const w of structuralWarnings) {
  if (w.kind === 'placeholder') {
    plan.comments.push({lang: w.lang, key: w.key, comment: `[review-l10n] placeholder mismatch (unwired locale, non-blocking): ${w.detail}`});
  }
}
// WRONG findings → overwrite if a concrete fix is given, else a flag comment.
// On a held unit the fix is only proposed: the translator's thread decides.
const heldWrong = [];
const heldAwkward = [];
for (const w of wrong) {
  if (w.new && !isHeld(w.lang, w.key)) {
    plan.overwrites.push({lang: w.lang, key: w.key, current: w.current, new: w.new, comment: w.note});
  } else if (w.new) {
    heldWrong.push(w);
    const why = feedbackKnown ? 'a translator has commented on this unit, so it is not applied' : 'feedback.json missing, so nothing is applied blind';
    plan.comments.push({lang: w.lang, key: w.key, comment: `[review-l10n] flagged WRONG (${why}): ${w.note || ''} Proposed: ${w.new}`});
  } else {
    plan.comments.push({lang: w.lang, key: w.key, comment: `[review-l10n] flagged WRONG: ${w.note || ''}`});
  }
}
// AWKWARD → suggestions, except on held units where the thread already exists,
// in a language a translator is actively maintaining (their style, their call),
// or beyond the per-language cap.
const deferredActive = [];
const capped = [];
const perLang = {};
for (const a of awkward) {
  if (!a.proposal) continue;
  if (feedbackKnown && heldUnits.has(`${a.lang}/${a.key}`)) { heldAwkward.push(a); continue; }
  if (activeLangs.has(a.lang)) { deferredActive.push(a); continue; }
  perLang[a.lang] = (perLang[a.lang] || 0) + 1;
  if (perLang[a.lang] > maxSuggestions) { capped.push(a); continue; }
  const rationale = a.source ? `${a.note || ''} (ref: ${a.source})` : a.note;
  plan.suggestions.push({lang: a.lang, key: a.key, current: a.current, proposal: a.proposal, comment: rationale});
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
  wiredSource, wired: [...wired],
  feedbackSource: feedbackKnown ? feedbackPath : 'missing-no-overwrites',
  heldUnits: [...heldUnits],
  activeTranslatorLangs: [...activeLangs],
  maxSuggestionsPerLang: maxSuggestions,
  changedLangs, gateLangs, skippedLangs,
  counts: {
    hardBlockers: hardBlockers.length,
    structuralWarnings: structuralWarnings.length,
    wrong: wrong.length,
    awkward: awkward.length,
    heldWrong: heldWrong.length,
    heldAwkward: heldAwkward.length,
    unsourced: unsourced.length,
    deferredActive: deferredActive.length,
    capped: capped.length,
    overwrites: plan.overwrites.length,
    suggestions: plan.suggestions.length,
    comments: plan.comments.length,
  },
  hardBlockers, hardReasons, structuralWarnings,
  wrong, awkward, ignoredUnwired, heldWrong, heldAwkward, unsourced, deferredActive, capped,
};

writeFileSync(join(outDir, 'decision.json'), JSON.stringify(decisionObj, null, 2));
writeFileSync(join(outDir, 'plan.json'), JSON.stringify(plan, null, 2));

console.log(`mechanical verdict: ${mechanical_verdict}  (pr=${decisionObj.pr ?? '?'})`);
console.log(`wired list: ${wiredSource}${wiredKnown ? ` (${wired.size} langs)` : ' — every changed locale gated'}`);
console.log(`changed locales (${changedLangs.length}): ${changedLangs.join(', ') || 'none'}`);
console.log(`  gated  (${gateLangs.length}): ${gateLangs.join(', ') || 'none'}`);
console.log(`  SKIPPED(${skippedLangs.length}): ${skippedLangs.join(', ') || 'none'}`);
if (skippedLangs.length) {
  console.log(`  ^ these were NOT gated. Confirm they are genuinely unwired before reading this run as full coverage.`);
}
console.log(`hard blockers=${hardBlockers.length} | structural warnings (unwired)=${structuralWarnings.length} | semantic: wrong=${wrong.length} awkward=${awkward.length}`);
console.log(`translator feedback: ${feedbackKnown ? `${heldUnits.size} held unit(s)` : 'MISSING — every overwrite downgraded to a comment'}`);
if (heldWrong.length || heldAwkward.length) {
  console.log(`  held back: ${heldWrong.length} WRONG fix(es) posted as comments, ${heldAwkward.length} AWKWARD suggestion(s) dropped — the feedback reviewer owns those threads`);
}
if (unsourced.length) {
  console.log(`unsourced norm claims dropped (${unsourced.length}) — grammar/orthography findings need a consulted URL:`);
  for (const u of unsourced) console.log(`  - ${u.lang}/${u.key} [${u.kind}]: ${u.note || ''}`);
}
if (activeLangs.size) {
  console.log(`active translators: ${[...activeLangs].join(', ')} — meaning-level only; ${deferredActive.length} AWKWARD suggestion(s) not posted there`);
}
if (capped.length) {
  console.log(`suggestion cap ${maxSuggestions}/lang: ${capped.length} suggestion(s) held over — ${[...new Set(capped.map(c => c.lang))].join(', ')}`);
}
console.log(`plan: overwrites=${plan.overwrites.length} suggestions=${plan.suggestions.length} comments=${plan.comments.length}`);
if (hardReasons.length) {
  console.log('\nHard HOLD (non-overridable):');
  for (const r of hardReasons) console.log(`  - ${r}`);
}
if (structuralWarnings.length) {
  console.log('\nStructural issues in unwired locales (non-blocking, fix before wiring):');
  for (const w of structuralWarnings) {
    console.log(`  - ${w.lang}${w.key ? `/${w.key}` : ''}: ${w.kind} — ${w.detail}`);
  }
}
if (mechanical_verdict === 'ADJUDICATE') {
  console.log(`\n${wrong.length} WRONG finding(s) need session adjudication → MERGE or HOLD.`);
  for (const w of wrong) console.log(`  - ${w.lang}/${w.key}: ${w.note || ''}`);
}
console.log(`\nwrote ${join(outDir, 'decision.json')} and ${join(outDir, 'plan.json')}`);
process.exit(mechanicalHold ? 1 : 0);
