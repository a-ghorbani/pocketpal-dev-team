#!/usr/bin/env node
// Apply a review-l10n plan against the Weblate REST API.
//
// Plan format:
// {
//   "target_id": "PR-683",
//   "weblate": {"project": "pocketpal-ai", "component": "translations",
//               "base_url": "https://hosted.weblate.org"},
//   "default_state": 10,            // 10=needs-editing, 20=translated, 30=approved
//   "overwrites":  [{lang, key, current, new, state?, comment?, adopt?}],
//   "suggestions": [{lang, key, current, proposal, comment?}],
//   "comments":    [{lang, key, comment}],
//   "replies":     [{lang, key, comment}]   // answers to translator threads (feedback plan)
// }
//
// Usage:
//   apply-plan.mjs <plan.json> [--dry-run] [--only=overwrites|suggestions|comments|replies]
//
// An overwrite only lands on machine text that still reads as reviewed: the live unit
// must be below state 20 (our drafts are written at 10) and its target must equal
// `current`. Anything else is a human's translation, or changed since the review,
// so the fix goes out as a flag comment instead. `adopt` (the translator's own
// wording, from build-feedback-plan) skips only the state check.
//
// Every comment goes out with the [review-l10n] marker so the next run can tell
// its own comments from a translator's. Throttled to 1 req/sec; fails fast on
// auth/lookup errors. Dry-run still looks units up when a token is present, so
// the preview also validates that every unit exists.
import {readFileSync} from 'node:fs';
import {loadToken, makeClient, markComment, toWeblateLang} from './weblate-client.mjs';

function parseArgs(argv) {
  const args = {planPath: null, dryRun: false, only: null, suggestionsAsComments: true};
  for (const a of argv.slice(2)) {
    if (a === '--dry-run') args.dryRun = true;
    else if (a.startsWith('--only=')) args.only = a.slice('--only='.length);
    else if (a === '--no-suggestion-fallback') args.suggestionsAsComments = false;
    else if (!args.planPath) args.planPath = a;
  }
  return args;
}

const {planPath, dryRun, only, suggestionsAsComments} = parseArgs(process.argv);
if (!planPath) {
  console.error('usage: apply-plan.mjs <plan.json> [--dry-run] [--only=overwrites|suggestions|comments|replies]');
  process.exit(2);
}
const plan = JSON.parse(readFileSync(planPath, 'utf-8'));
const token = loadToken();
if (!token && !dryRun) {
  console.error('ERROR: no WLT_TOKEN found. Set it in .env (repo root), env var, or ~/.config/weblate-token.');
  console.error('Get one at https://hosted.weblate.org/accounts/profile/#api');
  process.exit(3);
}

const wl = makeClient({
  token, dryRun,
  baseUrl: plan.weblate?.base_url,
  project: plan.weblate?.project,
  component: plan.weblate?.component,
});
const defaultState = plan.default_state ?? 10;
const lookups = Boolean(token);

console.log(`plan          : ${planPath}`);
console.log(`weblate       : ${wl.baseUrl}/${wl.project}/${wl.component}`);
console.log(`dry-run       : ${dryRun}${dryRun && !lookups ? ' (no token: unit lookups skipped)' : ''}`);
console.log(`default state : ${defaultState}  (10=needs-editing, 20=translated, 30=approved)`);
for (const s of ['overwrites', 'suggestions', 'comments', 'replies']) {
  console.log(`${s.padEnd(14)}: ${plan[s]?.length || 0}`);
}
console.log('');

async function findUnit(lang, key) {
  if (!lookups) return {id: 'DRYRUN', state: 0, target: [''], web_url: `${wl.baseUrl}/translate/${wl.project}/${wl.component}/${toWeblateLang(lang)}/?q=context:${key}`};
  return wl.findUnit(lang, key);
}

function overwriteRefusal(item, u) {
  if (!lookups) return null;
  const live = u.target?.[0] ?? '';
  if ((item.current ?? '') !== live) return 'the live text differs from the reviewed text';
  if (!item.adopt && u.state >= 20) return `a person translated or approved this (state ${u.state})`;
  return null;
}

async function overwrite(item) {
  const u = await findUnit(item.lang, item.key);
  const refusal = overwriteRefusal(item, u);
  if (refusal) {
    await wl.postComment(u.id, `flagged (not applied: ${refusal}): ${item.comment || ''} Proposed: ${item.new}`);
    return {id: u.id, url: u.web_url, held: refusal};
  }
  await wl.patchTarget(u.id, item.new, item.state ?? defaultState);
  if (item.comment) await wl.postComment(u.id, item.comment);
  return {id: u.id, url: u.web_url};
}

// hosted.weblate.org has no public POST suggestions endpoint, so a suggestion is
// a comment carrying the proposal; the target is left unchanged.
async function suggest(item) {
  if (!suggestionsAsComments) {
    throw new Error('hosted.weblate.org has no /api/units/<id>/suggestions/ endpoint; re-run without --no-suggestion-fallback');
  }
  const text = `Suggestion: ${item.proposal}\n\nReason: ${item.comment ?? '(no rationale provided)'}\n\nThe translation itself is left unchanged.`;
  return comment({lang: item.lang, key: item.key, comment: text});
}

async function comment(item) {
  const u = await findUnit(item.lang, item.key);
  await wl.postComment(u.id, markComment(item.comment));
  return {id: u.id, url: u.web_url};
}

const tally = {ok: 0, fail: 0, held: 0};
async function run(label, items, fn) {
  if (only && only !== label) return;
  if (!items || items.length === 0) return;
  console.log(`--- ${label} (${items.length}) ---`);
  for (const item of items) {
    const tag = `${item.lang}/${item.key}`;
    try {
      const r = await fn(item);
      if (r.held) {
        tally.held++;
        console.log(`  HELD ${tag.padEnd(60)} unit=${r.id} → comment only: ${r.held}`);
        continue;
      }
      tally.ok++;
      console.log(`  ok   ${tag.padEnd(60)} unit=${r.id} ${r.url || ''}`);
    } catch (e) {
      tally.fail++;
      console.log(`  FAIL ${tag.padEnd(60)} ${e.message}`);
      if (e.body) console.log(`       ${JSON.stringify(e.body).slice(0, 200)}`);
    }
  }
}

await run('overwrites',  plan.overwrites,  overwrite);
await run('suggestions', plan.suggestions, suggest);
await run('comments',    plan.comments,    comment);
await run('replies',     plan.replies,     comment);

console.log('');
console.log(`done: ${tally.ok} ok, ${tally.held} overwrite(s) held as comments, ${tally.fail} failed${dryRun ? ' (DRY RUN — no writes)' : ''}`);
process.exit(tally.fail > 0 ? 1 : 0);
