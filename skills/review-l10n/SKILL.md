---
name: review-l10n
description: Review a Weblate auto-merge PR (or any locale PR) for PocketPal. Computes per-locale completion, identifies wirable candidates, runs per-language semantic review via subagents, validates placeholders, and optionally applies fixes back to Weblate (overwrites + suggestions + comments).
user-invocable: true
argument-hint: "<pr-number | branch-ref | locales-dir>"
---

# Review L10n

Review a PocketPal localization change as a translation-quality and wiring-readiness audit.

Typical invocation:

```text
/review-l10n 683          # Weblate auto-merge PR
/review-l10n PR-683       # same, by branch label
/review-l10n weblate-translations   # branch ref
/review-l10n --auto       # unattended merge-gate (discovers the open Weblate PR)
```

## Auto mode (`--auto`) — unattended merge gate

`--auto` turns the review into a **merge decision** for the recurring Weblate
auto-merge PR. It is designed to run unattended (twice-weekly remote routine) and
replaces the "ask before every write" gate with a deterministic rubric.

Flow (orchestrated by `scripts/auto-review.sh` → semantic subagents → `scripts/decide.mjs` → `scripts/apply-decision.sh`):

1. **Discover** the open Weblate PR (`author:weblate`, head `weblate-translations`). No PR → exit cleanly.
2. **Pre-review** (`auto-review.sh`): fetch head/base locale JSONs, run coverage + placeholder checks, split the diff per language.
3. **Semantic review**: spawn one `general-purpose` subagent per *changed wired* language (parallel, blind to each other), each returning STRICT-JSON findings: `[{lang,key,severity:WRONG|AWKWARD,en,current,new?,proposal?,note}]`. Collate into `findings.json`.
4. **Mechanical gate** (`decide.mjs`): split into two layers and write `decision.json` + `plan.json`.
   - **Layer 1 — hard blockers (non-overridable, no judgment):** out-of-scope file (anything outside `src/locales/*.json`), malformed JSON, placeholder mismatch in a changed wired lang, or GitHub `CONFLICTING`. These can crash/break the app or are unsafe to auto-merge, so any one of them => `mechanical_verdict: HOLD` and the decision is final. The model cannot wave these through.
   - **Layer 2 — semantic findings (adjudicable):** `WRONG` (wired) and `AWKWARD` findings. These never auto-decide. With no hard blockers, `mechanical_verdict: ADJUDICATE`.
   - Unwired-language issues are recorded (`ignoredUnwired`) but never gate — they don't ship in-app.
5. **Adjudicate** (main session, only when `ADJUDICATE`): the session reads **all** `WRONG` + `AWKWARD` findings together (key, en, current, proposed fix, rationale, lang) and makes one reasoned `MERGE` or `HOLD` call — "are these wrongs terrible enough to keep off prod, or tolerable to fix next round?" This judgment lives with the main model, not a per-language subagent or a count threshold.
6. **Act** (`apply-decision.sh`, **dry-run by default; `--execute` to act**). Pass the session's call as `--decision=MERGE|HOLD --reason=...`; it is ignored if Layer 1 already forced HOLD.
   - **MERGE:** `gh pr merge` first (needs `--admin` to bypass branch protection — the routine *is* the review), then file all Weblate writes (corrections + suggestions, state=10) for the next cycle.
   - **HOLD:** do **not** merge; apply the Weblate writes so the source is fixed and the *next* regenerated PR is cleaner.
   - Either way: post a summary comment on the PR (and the caller fires a push notification).
7. **Fill phase (opt-in: `--auto --fill-missing`).** After the merge decision, top up missing strings for wired languages, **uncapped**, per **Fill mode** above: find-missing → model sanity-judge each language's delta (fill new strings; flag-and-skip anything that looks like an `en.json` restructure) → translate contextually in a less-formal register → model quality pass → write at state=10. Fills never change the *current* PR's decision (missing keys aren't in its diff) — they ride the next regenerated PR. Report what was filled and anything skipped.

Why this shape: structural breakage (placeholders/JSON) is a fact, not an opinion — it stays mechanical. Everything that needs taste — the merge call, "does this backfill make sense," and translation quality — goes to the model, which sees the whole picture at once rather than a single subagent's local call or a numeric threshold.

Secrets for unattended runs: `WLT_TOKEN` (Weblate) and a `gh` token with merge
scope must be present in the run environment — a remote routine needs them
provisioned; a local cron inherits `.env` + the gh keyring.

## Fill mode (`--fill`)

`--fill <lang[,lang...]>` backfills **genuinely-missing** strings (keys present in
`en.json` but absent/empty in the locale) for wired languages, written to Weblate
at **state=10 ("needs-editing")**.

Runs on demand, or as an opt-in phase of the twice-weekly `--auto` run
(`--auto --fill-missing`, see Auto mode). **Uncapped** — each run fills whatever is
missing, so wired languages stay at ~0 untranslated continuously; in steady state
the per-run delta is just the handful of `en` keys added since the last run. Fill
closes the *coverage* gap (strings present), not the *approval* gap — drafts sit at
needs-editing until a human approves them in Weblate.

**Know before running:** a value in the locale JSON **ships** — Weblate `state` is a
review flag, not a publish gate. So filled strings reach users on the next
regenerated Weblate PR, *replacing the English fallback*. This is the agreed policy
(MT baseline, community refines), but it means fills are a deliberate
ship-machine-translation action, not just a suggestion.

Flow:
1. `find-missing.mjs <head-dir> <lang> --json <out>` → the missing keys (excludes present-but-identical-to-en, which may be intentional, e.g. brand names).
2. **Sanity-judge the delta — model judgment, NOT a numeric cap.** Look at what is missing per language and decide whether filling makes sense. A normal delta is a few newly-added `en` keys → fill. A *large or structural* delta is a signal, not a workload: it usually means an `en.json` rename/restructure, where a "missing" key still has a good **human** translation under the old key name — machine-filling it would replace human work with a draft. If the delta looks like a restructure (e.g. a whole key prefix newly missing while the locale holds orphaned old keys), **don't auto-fill that language — flag and report it** so a human migrates the old translations instead. Reasoning about "does this fill make sense" is the model's job; that is the whole reason we use a model rather than a threshold.
3. Split each language's missing list into batches; spawn one translation subagent per batch (parallel). Each gets its batch + the existing `<lang>.json` as a style/terminology anchor. Requirements: **preserve `{{placeholders}}` byte-identical**; keep brand/engine/model names in English; **translate contextually** — use the key path, the screen/feature it belongs to, and neighbouring strings to get terminology and meaning right; and use a **natural, less-formal register** — a friendly consumer-app tone, not stiff or over-formal. Write `[{lang,key,en,new,note?}]` to an output file.
4. **Quality pass — model judgment.** Before writing, review the drafts for real problems (wrong sense, leaked English, over-formal/awkward phrasing, inconsistent terminology) and fix or re-generate. Only placeholder/JSON correctness is mechanical (next step); quality is judged by the model, same principle as the merge gate.
5. `build-fill-plan.mjs --missing-dir=<d> --out-dir=<d> --langs=...` → validates (placeholders byte-identical, coverage, dupes; skips whitespace-only `en` icon labels) and assembles `fill-plan.json` (overwrites only, state=10).
6. `apply-plan.mjs fill-plan.json [--dry-run]` → applies. ~2 req/unit at 1 req/sec, so large backfills take minutes — run in the background. No per-unit comments (avoids flooding Weblate with hundreds).

Scope: the initial backfill brought all wired languages to ~0 untranslated; ongoing,
the `--fill-missing` phase keeps them there by filling only the per-run delta.

## What this skill does

1. **Fetch** the locale JSON files at the PR head and the PR base.
2. **Coverage table** — count en.json leaf strings vs each locale (% present, % translated, identical-to-en, placeholder mismatches). Separates wired vs unwired.
3. **Wirable candidates** — flags unwired locales ≥ 95% coverage AND zero placeholder bugs.
4. **Placeholder validation** — runs `scripts/validate-l10n.js` in PocketPal style (registry-aware AND registry-bypassed) so unwired locales are also checked.
5. **Semantic review** — for each wired language touched by the PR, spawns a per-language subagent that classifies each new/changed entry as CORRECT / AWKWARD / WRONG, with rationale grounded in surrounding `id.json`-style context already used by the locale.
6. **Plan generation** — emits `plan.json` listing OVERWRITES (wrong, breaking) and SUGGESTIONS (awkward, stylistic), each with proposed target + one-line comment.
7. **Apply** — on explicit user approval, calls the Weblate API to PATCH overwrites (default state=10, "needs editing"), POST suggestions, and POST a comment on each touched unit. Token loaded from `.env`.

## Operating contract

- The submodule `repos/pocketpal-ai/` is read-only. Pull locale JSONs via `gh api` from the PR head; never patch files there.
- Per-language subagents must NOT see each other's reports — independent native review.
- All Weblate writes require explicit user approval. Default to **dry-run** unless the user says "apply".
- Default state for overwrites is `10` (needs editing) so a native speaker re-confirms before the next auto-merge.

## Inputs to resolve

- Target: PR number (preferred), or branch ref, or a path to a directory of locale JSONs.
- Repository: `a-ghorbani/pocketpal-ai`.
- Weblate project/component: `pocketpal-ai/translations` (defined in [memory](../../) — confirm before any write).
- Working scratch dir: `/tmp/review-l10n-<TARGET_ID>/` (NOT inside the submodule or any worktree).

If essential target info is missing and cannot be resolved from `gh`, stop and ask.

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
node skills/review-l10n/scripts/coverage.mjs "${SCRATCH}/head" > "${SCRATCH}/coverage.txt"
node skills/review-l10n/scripts/find-placeholder-issues.mjs "${SCRATCH}/head" > "${SCRATCH}/placeholders.txt"

# Optional: run repo's own validator
node repos/pocketpal-ai/scripts/validate-l10n.js  # registry-aware (wired langs only)

# Bypass the registry filter to also catch issues in unwired files
( cd "${SCRATCH}/head"
  cp -r . ../runner-src && mkdir -p ../runner/scripts && cp ../../../repos/pocketpal-ai/scripts/validate-l10n.js ../runner/scripts/
  cd .. && mv runner-src runner/src/locales 2>/dev/null || true
  # (or just run coverage.mjs which surfaces the same info)
)
```

The skill should always run `coverage.mjs` and `find-placeholder-issues.mjs`; running the repo validator is optional and informational.

## Stage 3 — Wirable candidates

From `coverage.txt`, list unwired locales with:
- `%present ≥ 95`
- `%translated ≥ 95`
- `placeholder mismatches = 0`

If none qualify, say so explicitly. Do not "round up" 90% to "almost wirable" — call out exactly what's missing.

## Stage 4 — Per-language semantic review

```bash
node skills/review-l10n/scripts/diff-entries.mjs "${SCRATCH}/head" "${SCRATCH}/base" "${SCRATCH}/diff-report.txt"

# Split per language for parallel agents
awk -v scratch="${SCRATCH}" '/^## [A-Za-z_]+:/ {f=scratch "/diff-" $2 ".txt"; sub(":","",f)} f {print > f}' "${SCRATCH}/diff-report.txt"
```

For each changed wired language, spawn a `general-purpose` agent **in parallel**. Each agent gets:
- The path to its diff file only (never another language's file).
- A language-specific prompt that:
  - States the app context (mobile, RN, local LLMs, Settings/Models/Chat).
  - Lists language-specific gotchas: orthography (e.g. Russian ё, missing measure word 个 in Chinese, Korean register mismatch), brand-name policy (keep `OpenAI`, `Groq`, `Hugging Face`, model names, engine names like `Kitten/Kokoro/Supertonic` in English).
  - Reminds: placeholders `{{name}}` must stay byte-identical.
  - Asks for output limited to AWKWARD/WRONG entries with key, en, lang, one-line note.

Language-specific gotchas worth encoding (extend over time):
- **Russian / Ukrainian** — naive `{{count}} step(s)` patterns; missing ё; Russianisms in Ukrainian.
- **Chinese (zh)** — missing measure word `个` after `{{count}}`; 远端 vs 远程 consistency.
- **Chinese (zh_Hant)** — simplified chars leaking in (e.g. 设 vs 設); 語音 vs 聲音 distinction.
- **Korean** — register mix (합쇼체 vs 해요체); particle errors; brand names.
- **Indonesian** — title-case headers; "Mengunduh" vs "Mendownload"; reduplicated plurals.
- **Hebrew** — RTL ok; verbatim brand names; imperative form for buttons.

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
- For overwrites: `PATCH /api/units/<id>/ {target, state: default_state}`.
- For suggestions: `POST /api/units/<id>/suggestions/ {target}`.
- For comments: `POST /api/units/<id>/comments/ {comment}`.
- Throttles to ≤ 1 req/sec to be polite to hosted.weblate.org.
- Reports per-line success/fail with the Weblate unit URL.

## Stage 8 — Report back

End with a short summary:
- How many entries patched / suggested / commented.
- Any failures (with reason).
- Reminder: a follow-up Weblate auto-merge PR will pick up the changes; PR #<n> itself does NOT need to be reopened.

## Anti-patterns to avoid

- Don't run native subagent reviews in series — always parallel; they're independent.
- Don't show one language's findings to another's reviewer.
- Don't patch directly on PR; all writes go to Weblate. The PR will be regenerated.
- Don't commit `.env` or echo `$WLT_TOKEN` to stdout. Never paste tokens into the conversation.
- Don't ask the user to paste the token in chat. Direct them to `.env` instead.
- Don't merge or close the original auto-merge PR as part of this skill — that's a separate decision.

## See also

- `scripts/coverage.mjs` — coverage logic.
- `scripts/find-placeholder-issues.mjs` — placeholder mismatch scanner.
- `scripts/diff-entries.mjs` — per-language diff producer.
- `scripts/apply-plan.mjs` — Weblate API executor.
- `scripts/find-missing.mjs` — `--fill`: list en keys missing/empty in a locale.
- `scripts/build-fill-plan.mjs` — `--fill`: validate subagent translations → fill plan (overwrites, state=10).
- `scripts/auto-review.sh` — `--auto` pre-review: discover PR, fetch, machine checks, per-lang diff split.
- `scripts/decide.mjs` — `--auto` merge-gate decision engine → `decision.json` + `plan.json`.
- `scripts/apply-decision.sh` — `--auto` act path: merge-or-not + Weblate writes + PR comment (dry-run by default).
- `repos/pocketpal-ai/scripts/validate-l10n.js` — the repo's own (registry-aware) validator.
- Memory: locale registry lives in `repos/pocketpal-ai/src/locales/index.ts`.

## hosted.weblate.org gotchas (verified 2026-05-12)

- **Language code remap.** PocketPal repo uses `zh` for the Simplified Chinese file, but hosted.weblate.org's translation slug is `zh_Hans`. `apply-plan.mjs` remaps automatically via `LANG_REMAP`; if you add a new language and the unit lookup 404s, check what hosted.weblate.org calls it (e.g. `GET /api/translations/pocketpal-ai/translations/<code>/`) and update the map. Other PocketPal codes (`fa`, `he`, `id`, `ja`, `ko`, `ms`, `ru`, `uk`, `zh_Hant`) match Weblate 1:1.
- **No public suggestion API.** Neither `POST /api/units/<id>/suggestions/` nor `POST /api/suggestions/` exist on hosted.weblate.org (both return 404). Suggestions in the Weblate sense — proposed target visible alongside the current translation — are only creatable through the web UI. `apply-plan.mjs` falls back to posting the proposal + rationale as a comment, leaving the target untouched. Pass `--no-suggestion-fallback` if you'd rather fail loudly.
- **Comments endpoint.** `POST /api/units/<id>/comments/` with `{comment, scope}` works. Use `scope: "translation"` so the comment is scoped to the language, not the source string.
- **Unit lookup.** `GET /api/translations/<project>/<component>/<lang>/units/?q=context:<key>` returns results matched by Weblate's substring search; always re-filter client-side on exact `context` equality (the skill does this).
