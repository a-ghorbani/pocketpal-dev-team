# Interactive stages 1–3 and 5–8

Read from `skills/review-l10n/SKILL.md` when running an interactive review (commands, plan format, apply behaviour).

## Overview

1. **Fetch** the locale JSON files at the PR head and the PR base.
2. **Coverage table** — count en.json leaf strings vs each locale (% present, % translated, identical-to-en, placeholder mismatches). Separates wired vs unwired.
3. **Wirable candidates** — flags unwired locales ≥ 95% coverage AND zero placeholder bugs.
4. **Placeholder validation** — runs `scripts/validate-l10n.js` in PocketPal style (registry-aware AND registry-bypassed) so unwired locales are also checked.
5. **Semantic review** — for each wired language touched by the PR, spawns a per-language subagent that classifies each new/changed entry as CORRECT / AWKWARD / WRONG, with rationale grounded in surrounding `id.json`-style context already used by the locale.
6. **Plan generation** — emits `plan.json` listing OVERWRITES (wrong, breaking) and SUGGESTIONS (awkward, stylistic), each with proposed target + one-line comment.
7. **Apply** — on explicit user approval, calls the Weblate API to PATCH overwrites (default state=10, "needs editing"), POST suggestions, and POST a comment on each touched unit. Token loaded from `.env`.

## Stage 1 — Fetch

```bash
TARGET_ID="PR-683"               # or branch label
PR_NUMBER=683                    # if PR
SCRATCH="/tmp/review-l10n-${TARGET_ID}"
mkdir -p "${SCRATCH}/head" "${SCRATCH}/base"

# Resolve refs
HEAD_OID=$(gh pr view ${PR_NUMBER} --repo a-ghorbani/pocketpal-ai --json headRefOid --jq .headRefOid)
BASE_OID=$(gh pr view ${PR_NUMBER} --repo a-ghorbani/pocketpal-ai --json baseRefOid --jq .baseRefOid)

# Discover locale files in the PR
gh pr view ${PR_NUMBER} --repo a-ghorbani/pocketpal-ai --json files \
  --jq '.files[].path' \
  | grep '^src/locales/.*\.json$' \
  > "${SCRATCH}/changed.txt"

# Always pull en.json + every locale that exists at HEAD (for coverage), plus base copies of changed ones (for diff).
bash skills/review-l10n/scripts/fetch-pr.sh "${PR_NUMBER}" "${SCRATCH}"
```

`scripts/fetch-pr.sh` handles the loop and base64-decodes the contents.

## Stage 2 — Coverage + Validation

```bash
# Derive the wired list first — every downstream stage depends on it.
WIRED=$(node skills/review-l10n/scripts/wired-langs.mjs --ref="${BASE_OID}")

node skills/review-l10n/scripts/coverage.mjs "${SCRATCH}/head" --wired="${WIRED}" > "${SCRATCH}/coverage.txt"
node skills/review-l10n/scripts/find-placeholder-issues.mjs "${SCRATCH}/head" > "${SCRATCH}/placeholders.txt"

# Optional: run the repo's validator against the PR head locales (no index.ts there,
# so it auto-discovers every locale, wired or not). ROOT = dev-team repo root.
ROOT="$PWD"
mkdir -p "${SCRATCH}/runner/scripts" "${SCRATCH}/runner/src/locales"
cp -r "$ROOT/repos/pocketpal-ai/scripts/validate-l10n.js" "$ROOT/repos/pocketpal-ai/scripts/lib" "${SCRATCH}/runner/scripts/"
cp "${SCRATCH}/head/"*.json "${SCRATCH}/runner/src/locales/"
node "${SCRATCH}/runner/scripts/validate-l10n.js"
```

The skill should always run `coverage.mjs` and `find-placeholder-issues.mjs`; running the repo validator is optional and informational.

## Stage 3 — Wirable candidates

From `coverage.txt`, list unwired locales with:
- `%present ≥ 95`
- `%translated ≥ 95`
- `placeholder mismatches = 0`

If none qualify, say so explicitly. Do not "round up" 90% to "almost wirable" — call out exactly what's missing.

## Stage 5 — Plan generation

After the agents return, build `${SCRATCH}/plan.json`:

```json
{
  "target_id": "PR-683",
  "weblate": {"project": "pocketpal-ai", "component": "translations"},
  "default_state": 10,
  "overwrites": [
    {
      "lang": "ko",
      "key": "voiceAndSpeech.insufficientStorage",
      "current": "...({{freeMb}} MB available).",
      "new":     "...({{freeMb}} MB 사용 가능).",
      "comment": "English `available` leaked into KO; replaced with 사용 가능."
    }
  ],
  "suggestions": [
    {
      "lang": "id",
      "key": "settings.serverDetails",
      "current":  "Keterangan Server",
      "proposal": "Detail Server",
      "comment":  "`Keterangan` reads as `description/note`; `Detail Server` matches the source."
    }
  ]
}
```

Severity policy:
- **Overwrite** = clear functional bug. Placeholder mismatch, leaked English, wrong-sense terminology that changes meaning, missing measure word that makes the string ungrammatical.
- **Suggestion** = stylistic. Register inconsistency, capitalization, punctuation, brand-name handling, more idiomatic wording.

Brand-name un-translations (e.g. uk `Кошеня` for engine `Kitten`) — by default treat as overwrites (functional, since the brand is searched by name), but downgrade to suggestion if the user prefers.

## Stage 6 — Present plan, ask to apply

Show the user a concise summary table:

```text
target  PR-683
wired langs changed: he, id, ko, ru, uk, zh, zh_Hant
overwrites: 13 (state=10 "needs editing")
suggestions: 57
comments will be posted on each touched unit
weblate token source: .env (WLT_TOKEN)
```

Ask explicitly: "Apply now, dry-run, or save plan only?"

Do not write to Weblate without affirmative approval.

## Stage 7 — Apply (with explicit approval)

```bash
node skills/review-l10n/scripts/apply-plan.mjs "${SCRATCH}/plan.json" [--dry-run]
```

The script:
- Loads `WLT_TOKEN` from `<repo-root>/.env` (falls back to env var if already set). Fails fast with a clear message if absent.
- Resolves each `{lang, key}` to a Weblate unit via the units API (`?q=context:<key>`).
- For overwrites: `PATCH /api/units/<id>/ {target, state: item.state ?? default_state}`, but only when the live unit is below state 20 and its target equals `current`; otherwise a flag comment carries the proposal (`HELD` in the output).
- For suggestions: a `[review-l10n]` comment carrying the proposal (hosted.weblate.org has no suggestion-create API); the target is untouched.
- For comments and replies: `POST /api/units/<id>/comments/ {comment, scope: "translation"}`, always prefixed `[review-l10n]`.
- Throttles to ≤ 1 req/sec to be polite to hosted.weblate.org.
- Reports per-line success/fail with the Weblate unit URL.

## Stage 8 — Report back

End with a short summary:
- How many entries patched / suggested / commented.
- Any failures (with reason).
- Reminder: a follow-up Weblate auto-merge PR will pick up the changes; PR #<n> itself does NOT need to be reopened.
