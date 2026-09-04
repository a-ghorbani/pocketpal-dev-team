#!/usr/bin/env node
// Turn the feedback reviewers' resolutions into a Weblate write plan.
//
// Usage: build-feedback-plan.mjs --feedback=<feedback.json> --in-dir=<dir> [--plan=<path>] [--tag=<text>]
//   --in-dir   holds the reviewers' output: any replies-*.json whose items are
//              [{lang, key, action, reply, new?}]
//   --tag      short context appended to the marker, e.g. "PR #884"
//
// Actions:
//   adopt     the translator's wording wins → overwrite with `new` (defaults to the
//             pending suggestion's target) at state=20, plus a reply saying so
//   withdraw  our earlier suggestion was wrong → reply only, target untouched
//   stand     we still think the change is right → reply with the reason, target
//             untouched; the translator decides
//   ask       we need context from the translator → reply only
//   reply     anything else worth answering → reply only
//   none      thread needs no answer (e.g. a whitespace-only anonymous suggestion)
//
// Every item must point at a unit in feedback.json that carries translator input.
// A reply is addressed to the translator who spoke last (@username prepended when
// missing). Adopt requires placeholders byte-identical to the source.
import {readFileSync, writeFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';
import {DEFAULTS} from './weblate-client.mjs';

function arg(n, d) { const a = process.argv.find(x => x.startsWith(`--${n}=`)); return a ? a.slice(n.length + 3) : d; }
function ph(s) { return (String(s).match(/\{\{(\w+)\}\}/g) || []).sort(); }

const feedbackPath = arg('feedback');
const inDir = arg('in-dir');
if (!feedbackPath || !inDir) {
  console.error('usage: build-feedback-plan.mjs --feedback=<feedback.json> --in-dir=<dir> [--plan=<path>] [--tag=<text>]');
  process.exit(2);
}
const planPath = arg('plan', join(inDir, 'feedback-plan.json'));
const tag = arg('tag', '');

const feedback = JSON.parse(readFileSync(feedbackPath, 'utf-8'));
const units = new Map(feedback.units.filter(u => u.human).map(u => [`${u.lang}/${u.key}`, u]));

const items = [];
for (const f of readdirSync(inDir)) {
  if (!/^replies-.*\.json$/.test(f)) continue;
  let arr;
  try { arr = JSON.parse(readFileSync(join(inDir, f), 'utf-8')); } catch (e) { console.error(`skip ${f}: ${e.message}`); continue; }
  if (Array.isArray(arr)) items.push(...arr.map(it => ({...it, _file: f})));
}

const ACTIONS = new Set(['adopt', 'withdraw', 'stand', 'ask', 'reply', 'none']);
const plan = {
  target_id: `feedback${tag ? '-' + tag.replace(/\W+/g, '-') : ''}`,
  weblate: {...DEFAULTS, base_url: DEFAULTS.baseUrl},
  default_state: 10,
  overwrites: [], suggestions: [], comments: [], replies: [],
};
delete plan.weblate.baseUrl;
const problems = [];
const seen = new Set();
const counts = {};

for (const it of items) {
  const id = `${it.lang}/${it.key}`;
  const u = units.get(id);
  if (!u) { problems.push(`${id}: not a unit with translator input (${it._file})`); continue; }
  if (seen.has(id)) { problems.push(`${id}: duplicate resolution`); continue; }
  if (!ACTIONS.has(it.action)) { problems.push(`${id}: unknown action ${JSON.stringify(it.action)}`); continue; }
  seen.add(id);
  counts[it.action] = (counts[it.action] || 0) + 1;
  if (it.action === 'none') continue;

  const lastTranslator = [...u.comments].reverse().find(c => c.role === 'translator')?.author
    || u.suggestions.at(-1)?.author || null;
  let reply = String(it.reply || '').trim();
  if (!reply) { problems.push(`${id}: empty reply for action ${it.action}`); continue; }
  if (lastTranslator && lastTranslator !== 'anonymous' && !reply.includes(`@${lastTranslator}`)) reply = `@${lastTranslator} ${reply}`;
  const marked = `[review-l10n${tag ? ' ' + tag : ''}] ${reply}`;

  if (it.action === 'adopt') {
    const next = String(it.new ?? u.suggestions.at(-1)?.target ?? '').trim();
    if (!next) { problems.push(`${id}: adopt without a new target`); continue; }
    if (next === u.target) { problems.push(`${id}: adopt target equals current`); continue; }
    if (JSON.stringify(ph(u.source)) !== JSON.stringify(ph(next))) {
      problems.push(`${id}: adopt placeholder mismatch en[${ph(u.source)}] new[${ph(next)}]`); continue;
    }
    plan.overwrites.push({lang: it.lang, key: it.key, current: u.target, new: next, state: 20, comment: marked});
  } else {
    plan.replies.push({lang: it.lang, key: it.key, comment: marked, action: it.action});
  }
}

const unanswered = [...units.values()].filter(u => u.open && !seen.has(`${u.lang}/${u.key}`));

writeFileSync(planPath, JSON.stringify(plan, null, 2));
console.log(`resolutions: ${items.length} → ${JSON.stringify(counts)}`);
console.log(`wrote ${planPath}: ${plan.overwrites.length} adopt (state=20), ${plan.replies.length} replies`);
if (unanswered.length) {
  console.log(`\nOPEN threads with no resolution (${unanswered.length}):`);
  for (const u of unanswered) console.log(`  - ${u.lang}/${u.key}`);
}
if (problems.length) { console.log(`\nPROBLEMS (${problems.length}):`); for (const p of problems) console.log('  - ' + p); process.exitCode = 1; }
else console.log('\nvalidation: clean');
