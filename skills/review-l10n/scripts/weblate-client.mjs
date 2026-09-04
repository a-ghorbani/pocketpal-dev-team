// Shared hosted.weblate.org client for the review-l10n scripts.
//
// Token sourcing (first hit wins):
//   1. process.env.WLT_TOKEN
//   2. .env at repo root (key WLT_TOKEN=...)
//   3. ~/.config/weblate-token (single line)
import {readFileSync, existsSync} from 'node:fs';
import {join, dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {homedir} from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));
export const repoRoot = resolve(__dirname, '../../..');

export const DEFAULTS = {
  baseUrl: 'https://hosted.weblate.org',
  project: 'pocketpal-ai',
  component: 'translations',
};

// Every comment the skill posts starts with this, so a later run can tell its
// own comments from a translator's. Comments without it are treated as human.
export const BOT_MARKER = '[review-l10n]';
const LEGACY_BOT_PATTERNS = [/posted by review-l10n/i, /^Translation review suggestion:/];

export function isBotComment(text) {
  const t = String(text || '').trim();
  return t.startsWith(BOT_MARKER) || LEGACY_BOT_PATTERNS.some(p => p.test(t));
}

export function markComment(text) {
  const t = String(text || '').trim();
  return t.startsWith(BOT_MARKER) ? t : `${BOT_MARKER} ${t}`;
}

// PocketPal repo codes vs hosted.weblate.org slugs. Keep in sync with src/locales/index.ts.
export const LANG_REMAP = {zh: 'zh_Hans'};
const LANG_UNMAP = Object.fromEntries(Object.entries(LANG_REMAP).map(([a, b]) => [b, a]));
export function toWeblateLang(lang) { return LANG_REMAP[lang] || lang; }
export function toRepoLang(wlLang) { return LANG_UNMAP[wlLang] || wlLang; }

function loadEnvFile(p) {
  if (!existsSync(p)) return {};
  const out = {};
  for (const line of readFileSync(p, 'utf-8').split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith('#')) continue;
    const m = t.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!m) continue;
    let v = m[2];
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    out[m[1]] = v;
  }
  return out;
}

export function loadToken() {
  if (process.env.WLT_TOKEN) return process.env.WLT_TOKEN;
  const envVals = loadEnvFile(join(repoRoot, '.env'));
  if (envVals.WLT_TOKEN) return envVals.WLT_TOKEN;
  const fallback = join(homedir(), '.config/weblate-token');
  if (existsSync(fallback)) return readFileSync(fallback, 'utf-8').trim();
  return null;
}

export function usernameFromUrl(url) {
  return String(url || '').split('/').filter(Boolean).pop() || 'unknown';
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// api(method, url, body): JSON in/out, throttled, retries on 429 and 5xx (hosted.weblate.org throws transient 502s).
// In dryRun mode writes are echoed instead of sent; reads still go out.
export function makeClient({token, dryRun = false, throttleMs = 1000, baseUrl = DEFAULTS.baseUrl,
                            project = DEFAULTS.project, component = DEFAULTS.component} = {}) {
  baseUrl = baseUrl.replace(/\/$/, '');
  const headers = {
    Authorization: `Token ${token}`,
    'Content-Type': 'application/json',
    Accept: 'application/json',
    'User-Agent': 'pocketpal-review-l10n/1.1',
  };
  const isWrite = m => m !== 'GET';

  async function api(method, url, body) {
    if (dryRun && isWrite(method)) return {dryRun: true, method, url, body};
    if (!url.startsWith('http')) url = baseUrl + url;
    for (let attempt = 0; attempt < 5; attempt++) {
      const res = await fetch(url, {method, headers, body: body ? JSON.stringify(body) : undefined});
      if (res.status === 429 || (res.status >= 500 && res.status < 600)) {
        const wait = res.status === 429 ? Number(res.headers.get('retry-after') || 5) : 5 * (attempt + 1);
        await res.text().catch(() => {});
        await sleep(wait * 1000);
        continue;
      }
      const text = await res.text();
      let json;
      try { json = text ? JSON.parse(text) : null; } catch { json = {raw: text}; }
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status} ${res.statusText}`);
        err.status = res.status; err.body = json; err.url = url;
        throw err;
      }
      await sleep(throttleMs);
      return json;
    }
    throw new Error(`gave up after 5 attempts (429/5xx): ${url}`);
  }

  async function* paginate(url) {
    while (url) {
      const page = await api('GET', url);
      for (const r of page?.results || []) yield r;
      url = page?.next || null;
    }
  }

  const translationBase = lang =>
    `${baseUrl}/api/translations/${encodeURIComponent(project)}/${encodeURIComponent(component)}/${encodeURIComponent(toWeblateLang(lang))}`;

  async function findUnit(lang, key) {
    const url = `${translationBase(lang)}/units/?q=${encodeURIComponent('context:' + key)}`;
    const data = await api('GET', url);
    const results = data?.results || [];
    const exact = results.find(u => u.context === key);
    if (!exact) {
      const wl = toWeblateLang(lang);
      throw new Error(`unit not found for ${lang}${wl !== lang ? `→${wl}` : ''}/${key} (matches=${results.length})`);
    }
    return exact;
  }

  async function listLanguages() {
    const out = [];
    for await (const t of paginate(`${baseUrl}/api/components/${encodeURIComponent(project)}/${encodeURIComponent(component)}/translations/?page_size=100`)) {
      out.push(toRepoLang(t.language_code));
    }
    return out;
  }

  // Units in a language carrying a comment or a pending suggestion.
  async function* feedbackUnits(lang) {
    const q = encodeURIComponent('has:comment OR has:suggestion');
    yield* paginate(`${translationBase(lang)}/units/?q=${q}&page_size=100`);
  }

  const unitComments = id => api('GET', `${baseUrl}/api/units/${id}/comments/`).then(r => r?.results || []);
  const unitSuggestions = id => api('GET', `${baseUrl}/api/units/${id}/suggestions/`).then(r => r?.results || []);

  const postComment = (id, text) =>
    api('POST', `${baseUrl}/api/units/${id}/comments/`, {comment: markComment(text), scope: 'translation'});
  const patchTarget = (id, target, state) =>
    api('PATCH', `${baseUrl}/api/units/${id}/`, {target: [target], state});

  // The account the token belongs to; its unmarked comments are the maintainer's,
  // every other account's comments are a translator's.
  async function whoAmI() {
    try {
      const me = await api('GET', `${baseUrl}/api/users/?page_size=1`);
      return me?.results?.[0]?.username || null;
    } catch { return null; }
  }

  return {api, paginate, findUnit, listLanguages, feedbackUnits, unitComments, unitSuggestions,
          postComment, patchTarget, whoAmI, baseUrl, project, component, dryRun};
}
