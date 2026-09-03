#!/usr/bin/env node
// Derive the wired (shipped in-app) language list from src/locales/index.ts.
//
// `languageRegistry` in that file is the single source of truth for which
// locales reach users. Any second copy of the list rots the moment a language
// is wired, and a rotted copy fails silently — a skipped language looks exactly
// like a clean one in the gate output. So callers derive it, never hardcode it.
//
// Usage:
//   wired-langs.mjs --ref=<sha|branch> [--repo=a-ghorbani/pocketpal-ai]
//   wired-langs.mjs --file=<path-to-index.ts>
//
// Prints the comma-separated list (en excluded) on stdout.
// Exit 3 when the registry cannot be read or parsed, so callers can fail safe
// rather than proceed on a guess.
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';

function arg(name) {
  const a = process.argv.find(x => x.startsWith(`--${name}=`));
  return a ? a.slice(name.length + 3) : undefined;
}

const ref = arg('ref');
const file = arg('file');
const repo = arg('repo') || 'a-ghorbani/pocketpal-ai';
const path = arg('path') || 'src/locales/index.ts';

if (!ref && !file) {
  console.error('usage: wired-langs.mjs --ref=<sha|branch> [--repo=owner/name] | --file=<path>');
  process.exit(2);
}

let source;
try {
  source = file
    ? readFileSync(file, 'utf-8')
    : execFileSync(
        'gh',
        ['api', `repos/${repo}/contents/${path}?ref=${ref}`, '-H', 'Accept: application/vnd.github.raw'],
        {encoding: 'utf-8', maxBuffer: 8 * 1024 * 1024},
      );
} catch (e) {
  console.error(`wired-langs: cannot read ${file || `${repo}@${ref}:${path}`}: ${e.message}`);
  process.exit(3);
}

const block = source.match(/languageRegistry\s*=\s*\{([\s\S]*?)\}\s*as const/);
if (!block) {
  console.error('wired-langs: could not locate `languageRegistry = { ... } as const` in the registry source');
  process.exit(3);
}

const langs = [...block[1].matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{/gm)]
  .map(m => m[1])
  .filter(l => l !== 'en');

if (!langs.length) {
  console.error('wired-langs: parsed an empty registry — refusing to report zero wired languages');
  process.exit(3);
}

console.log(langs.join(','));
