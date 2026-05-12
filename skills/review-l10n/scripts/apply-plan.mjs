#!/usr/bin/env node
// Apply a review-l10n plan against the Weblate REST API.
//
// Plan format:
// {
//   "target_id": "PR-683",
//   "weblate": {"project": "pocketpal-ai", "component": "translations",
//               "base_url": "https://hosted.weblate.org"},
//   "default_state": 10,            // 10=needs-editing, 20=translated, 30=approved
//   "overwrites":  [{lang, key, current, new,      comment?}],
//   "suggestions": [{lang, key, current, proposal, comment?}],
//   "comments":    [{lang, key, comment}]          // optional extra comments
// }
//
// Usage:
//   apply-plan.mjs <plan.json> [--dry-run] [--only=overwrites|suggestions|comments]
//
// Token sourcing:
//   1. process.env.WLT_TOKEN
//   2. .env at repo root (key WLT_TOKEN=...)
//   3. ~/.config/weblate-token (single line)
//
// Throttles to 1 req/sec, prints per-line result, fails fast on auth/lookup error.

import {readFileSync, existsSync} from 'node:fs';
import {join, dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {homedir} from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '../../..'); // skills/review-l10n/scripts → repo root

function loadEnvFile(p) {
  if (!existsSync(p)) return {};
  const out = {};
  for (const line of readFileSync(p, 'utf-8').split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith('#')) continue;
    const m = t.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!m) continue;
    let v = m[2];
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    out[m[1]] = v;
  }
  return out;
}

function loadToken() {
  if (process.env.WLT_TOKEN) return process.env.WLT_TOKEN;
  const envFile = join(repoRoot, '.env');
  const envVals = loadEnvFile(envFile);
  if (envVals.WLT_TOKEN) return envVals.WLT_TOKEN;
  const fallback = join(homedir(), '.config/weblate-token');
  if (existsSync(fallback)) return readFileSync(fallback, 'utf-8').trim();
  return null;
}

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

// hosted.weblate.org maps some PocketPal repo codes to different language codes.
// Keep this list in sync with src/locales/index.ts.
const LANG_REMAP = {zh: 'zh_Hans'};
function remapLang(lang) { return LANG_REMAP[lang] || lang; }

const {planPath, dryRun, only, suggestionsAsComments} = parseArgs(process.argv);
if (!planPath) {
  console.error('usage: apply-plan.mjs <plan.json> [--dry-run] [--only=overwrites|suggestions|comments]');
  process.exit(2);
}
const plan = JSON.parse(readFileSync(planPath, 'utf-8'));
const token = loadToken();
if (!token && !dryRun) {
  console.error('ERROR: no WLT_TOKEN found. Set it in .env (repo root), env var, or ~/.config/weblate-token.');
  console.error('Get one at https://hosted.weblate.org/accounts/profile/#api');
  process.exit(3);
}

const baseUrl = (plan.weblate?.base_url || 'https://hosted.weblate.org').replace(/\/$/, '');
const project = plan.weblate?.project || 'pocketpal-ai';
const component = plan.weblate?.component || 'translations';
const defaultState = plan.default_state ?? 10;

console.log(`plan          : ${planPath}`);
console.log(`weblate       : ${baseUrl}/${project}/${component}`);
console.log(`dry-run       : ${dryRun}`);
console.log(`default state : ${defaultState}  (10=needs-editing, 20=translated, 30=approved)`);
console.log(`overwrites    : ${plan.overwrites?.length || 0}`);
console.log(`suggestions   : ${plan.suggestions?.length || 0}`);
console.log(`comments      : ${plan.comments?.length || 0}`);
console.log('');

const headers = {
  Authorization: `Token ${token}`,
  'Content-Type': 'application/json',
  Accept: 'application/json',
  'User-Agent': 'pocketpal-review-l10n/1.0',
};

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function api(method, url, body) {
  if (dryRun) return {dryRun: true, method, url, body};
  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json;
  try { json = text ? JSON.parse(text) : null; } catch { json = {raw: text}; }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status} ${res.statusText}`);
    err.body = json;
    err.url = url;
    throw err;
  }
  await sleep(1000); // 1 req/sec
  return json;
}

async function findUnit(lang, key) {
  const wlLang = remapLang(lang);
  const url = `${baseUrl}/api/translations/${encodeURIComponent(project)}/${encodeURIComponent(component)}/${encodeURIComponent(wlLang)}/units/?q=${encodeURIComponent('context:' + key)}`;
  const data = await api('GET', url);
  if (dryRun) return {id: 'DRYRUN', web_url: url};
  const results = data?.results || [];
  const exact = results.find(u => u.context === key);
  if (!exact) throw new Error(`unit not found for ${lang}${wlLang!==lang?`→${wlLang}`:''}/${key} (matches=${results.length})`);
  return exact;
}

async function overwrite(item) {
  const u = await findUnit(item.lang, item.key);
  const id = u.id;
  const state = item.state ?? defaultState;
  await api('PATCH', `${baseUrl}/api/units/${id}/`, {target: [item.new], state});
  if (item.comment) {
    await api('POST', `${baseUrl}/api/units/${id}/comments/`, {comment: item.comment, scope: 'translation'});
  }
  return {id, url: u.web_url};
}

// hosted.weblate.org does NOT expose a public POST suggestions endpoint.
// Fall back to a comment with the proposal text + rationale, leaving target unchanged.
async function suggest(item) {
  if (!suggestionsAsComments) {
    throw new Error('hosted.weblate.org has no /api/units/<id>/suggestions/ endpoint; re-run without --no-suggestion-fallback');
  }
  const text = `Translation review suggestion:\n\nProposal: ${item.proposal}\n\nReason: ${item.comment ?? '(no rationale provided)'}\n\n— posted by review-l10n; the translation itself is left unchanged.`;
  return await comment({lang: item.lang, key: item.key, comment: text});
}

async function comment(item) {
  const u = await findUnit(item.lang, item.key);
  const id = u.id;
  await api('POST', `${baseUrl}/api/units/${id}/comments/`, {comment: item.comment, scope: 'translation'});
  return {id, url: u.web_url};
}

const tally = {ok: 0, fail: 0};
async function run(label, items, fn) {
  if (only && only !== label) return;
  if (!items || items.length === 0) return;
  console.log(`--- ${label} (${items.length}) ---`);
  for (const item of items) {
    const tag = `${item.lang}/${item.key}`;
    try {
      const r = await fn(item);
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

console.log('');
console.log(`done: ${tally.ok} ok, ${tally.fail} failed${dryRun ? ' (DRY RUN — no writes)' : ''}`);
process.exit(tally.fail > 0 ? 1 : 0);
