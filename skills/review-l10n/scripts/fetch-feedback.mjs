#!/usr/bin/env node
// Pull every Weblate unit that carries a comment or a pending suggestion, so the
// review can see what humans said before it writes anything.
//
// Usage: fetch-feedback.mjs --out=<feedback.json> [--langs=ru,be] [--md-dir=<dir>] [--since=YYYY-MM-DD]
//   --langs   repo language codes (default: every language in the component)
//   --md-dir  also write one feedback-<lang>.md per language for the reviewers
//   --since   only keep threads with human activity on/after this date
//
// feedback.json:
// {
//   fetched_at, owner, langs,
//   active_translators: {lang: {authors:[...], last:"<iso>"}},   // translator activity in the last 90 days
//   units: [{lang, key, unit_id, web_url, state, source, target, last_updated,
//            comments:    [{author, role:"bot"|"maintainer"|"translator", ts, text}],
//            suggestions: [{author, ts, target, votes}],
//            human: bool,          // a translator comment or a pending suggestion exists
//            open:  bool}]         // the latest translator word has no bot/maintainer reply after it
// }
// `human` units are held: the gate never overwrites them and fill never touches them.
// `open` units are the ones the feedback reviewers must answer.
// Maintainer comments (the token owner's) are context, not a hold: before 2026-09-04
// the skill posted its overwrite notes unmarked under that account.
import {writeFileSync, mkdirSync} from 'node:fs';
import {join} from 'node:path';
import {loadToken, makeClient, isBotComment, usernameFromUrl, toRepoLang} from './weblate-client.mjs';

function arg(n, d) { const a = process.argv.find(x => x.startsWith(`--${n}=`)); return a ? a.slice(n.length + 3) : d; }

const outPath = arg('out');
if (!outPath) {
  console.error('usage: fetch-feedback.mjs --out=<feedback.json> [--langs=a,b] [--md-dir=<dir>] [--since=YYYY-MM-DD]');
  process.exit(2);
}
const langsArg = (arg('langs', '') || '').split(',').filter(Boolean);
const mdDir = arg('md-dir');
const since = arg('since');

const token = loadToken();
if (!token) { console.error('ERROR: no WLT_TOKEN found (env, repo .env, or ~/.config/weblate-token)'); process.exit(3); }
const wl = makeClient({token, throttleMs: 400});

const owner = await wl.whoAmI();
const langs = langsArg.length ? langsArg : await wl.listLanguages();
console.error(`owner=${owner || 'unknown'} langs=${langs.join(',')}`);

function role(author) {
  if (owner && author === owner) return 'maintainer';
  return 'translator';
}

const units = [];
for (const lang of langs) {
  let n = 0;
  try {
    for await (const u of wl.feedbackUnits(lang)) {
      const comments = u.has_comment ? await wl.unitComments(u.id) : [];
      const suggestions = u.has_suggestion ? await wl.unitSuggestions(u.id) : [];
      const cs = comments
        .map(c => ({author: usernameFromUrl(c.user), ts: c.timestamp,
                    role: isBotComment(c.comment) ? 'bot' : role(usernameFromUrl(c.user)),
                    text: c.comment}))
        .sort((a, b) => a.ts.localeCompare(b.ts));
      const ss = suggestions.map(s => ({author: usernameFromUrl(s.user), ts: s.timestamp, target: s.target?.[0] ?? '', votes: s.votes ?? 0}));
      const translatorEvents = [...cs.filter(c => c.role === 'translator').map(c => c.ts), ...ss.map(s => s.ts)];
      const lastHuman = translatorEvents.sort().at(-1) || null;
      const lastReply = cs.filter(c => c.role !== 'translator').map(c => c.ts).sort().at(-1) || null;
      const human = translatorEvents.length > 0;
      const open = human && (!lastReply || lastReply < lastHuman);
      if (since && (!lastHuman || lastHuman.slice(0, 10) < since)) continue;
      units.push({lang: toRepoLang(u.language_code || lang), key: u.context, unit_id: u.id, web_url: u.web_url,
                  state: u.state, source: u.source?.[0] ?? '', target: u.target?.[0] ?? '', last_updated: u.last_updated,
                  comments: cs, suggestions: ss, human, open, last_human: lastHuman});
      n++;
    }
  } catch (e) {
    if (e.status === 404) { console.error(`  ${lang}: not on Weblate (404), skipped`); continue; }
    throw e;
  }
  console.error(`  ${lang}: ${n} feedback unit(s)`);
}

const ACTIVE_DAYS = 90;
const cutoff = new Date(Date.now() - ACTIVE_DAYS * 86400e3).toISOString();
const activeTranslators = {};
for (const u of units) {
  const events = [...u.comments.filter(c => c.role === 'translator').map(c => ({author: c.author, ts: c.ts})),
                  ...u.suggestions.filter(s => s.author !== 'anonymous').map(s => ({author: s.author, ts: s.ts}))];
  for (const e of events) {
    if (e.ts < cutoff) continue;
    const a = (activeTranslators[u.lang] ||= {authors: [], last: ''});
    if (!a.authors.includes(e.author)) a.authors.push(e.author);
    if (e.ts > a.last) a.last = e.ts;
  }
}

const feedback = {fetched_at: new Date().toISOString(), owner, langs, active_days: ACTIVE_DAYS, active_translators: activeTranslators, units};
writeFileSync(outPath, JSON.stringify(feedback, null, 2));

const held = units.filter(u => u.human);
const open = units.filter(u => u.open);
console.log(`feedback: ${units.length} unit(s) with comments/suggestions, ${held.length} held by translator input, ${open.length} open thread(s) awaiting a reply`);
const activeList = Object.entries(activeTranslators).map(([l, a]) => `${l} (${a.authors.join(', ')}, last ${a.last.slice(0, 10)})`);
console.log(`active translators (last ${ACTIVE_DAYS} days): ${activeList.join('; ') || 'none'} — those languages get meaning-level review only`);
const byLang = {};
for (const u of open) (byLang[u.lang] ||= []).push(u);
for (const [lang, us] of Object.entries(byLang)) console.log(`  open ${lang}: ${us.length} — ${us.map(u => u.key).join(', ')}`);

if (mdDir) {
  mkdirSync(mdDir, {recursive: true});
  const perLang = {};
  for (const u of held) (perLang[u.lang] ||= []).push(u);
  for (const [lang, us] of Object.entries(perLang)) {
    const lines = [`# Human feedback on Weblate — ${lang}`, '',
      `${us.length} unit(s) carry a translator comment or a pending suggestion. ` +
      `Units marked OPEN have translator input newer than any reply. Comments by "${owner}" ` +
      `are the maintainer's; before 2026-09-04 they were this skill's own unmarked overwrite notes.`, ''];
    for (const u of us) {
      lines.push(`## ${u.key}${u.open ? '  [OPEN]' : ''}`);
      lines.push(`- unit: ${u.unit_id} · state: ${u.state} · ${u.web_url}`);
      lines.push(`- en: ${JSON.stringify(u.source)}`);
      lines.push(`- current: ${JSON.stringify(u.target)}`);
      for (const s of u.suggestions) lines.push(`- PENDING SUGGESTION by ${s.author} (${s.ts.slice(0, 10)}, votes ${s.votes}): ${JSON.stringify(s.target)}`);
      for (const c of u.comments) {
        const who = c.role === 'bot' ? 'this skill' : `${c.author} (${c.role})`;
        lines.push(`- ${c.ts.slice(0, 10)} ${who}: ${c.text.replace(/\s+/g, ' ').trim()}`);
      }
      lines.push('');
    }
    writeFileSync(join(mdDir, `feedback-${lang}.md`), lines.join('\n'));
  }
  console.log(`wrote per-language feedback files to ${mdDir}: ${Object.keys(perLang).join(', ') || 'none'}`);
}
