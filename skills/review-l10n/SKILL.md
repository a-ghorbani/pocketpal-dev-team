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

## Auto mode (`--auto`) — unattended reviewer + Weblate fixer

`--auto` reviews the recurring Weblate PR, **applies fixes to Weblate**, and emits a
**MERGE/HOLD recommendation** — a human does the actual merge. It is designed to run
unattended (twice-weekly remote routine) and replaces the "ask before every write"
gate with a deterministic rubric.

**It never touches GitHub** — no PR merge, no PR comment. The `main` ruleset requires
an approving review, and merges to a prod branch stay a human decision. The routine's
only writes are to Weblate; the recommendation is recorded for a maintainer to act on.

Flow (orchestrated by `scripts/auto-review.sh` → semantic subagents → feedback subagents → `scripts/decide.mjs` → `scripts/apply-decision.sh`):

1. **Discover** the open Weblate PR (`author:weblate`, head `weblate-translations`). No PR → exit cleanly.
2. **Pre-review** (`auto-review.sh`): fetch head/base locale JSONs, **derive the wired-language list** (`wired-langs.mjs` against the PR's base commit), run coverage + placeholder checks, split the diff per language, write `review-manifest.json` with the per-language entry counts and chunk plan, and **pull translator feedback** (`fetch-feedback.mjs` → `feedback.json` + `feedback/feedback-<lang>.md`, every language, see **Translator feedback** below). Its summary lists the *open* threads — translator comments or pending suggestions nobody has answered.
3. **Semantic review**: spawn `general-purpose` subagents over the *changed gated* languages (parallel, blind to each other), each returning STRICT-JSON findings: `[{lang,key,severity:WRONG|AWKWARD,kind,en,current,new?,proposal?,note,source?}]` (see **Grounded findings** in Stage 4: a grammar or orthography claim without a consulted URL is dropped by the gate; a language with an active translator gets WRONG-only review; at most 10 suggestions per language are posted). **Honour the manifest's `chunks`** — a language over 50 entries is split across that many reviewers, each given a slice, never one agent for the whole diff (see Stage 4). Each reviewer also gets its language's `feedback-<lang>.md` when one exists, so it does not re-raise what a translator has already settled. Collate into `findings.json`.
3b. **Feedback resolution**: for every language with open threads (any language, wired or not — a translator is a translator), spawn one `general-purpose` subagent with that language's `feedback-<lang>.md`, the rules from **Translator feedback**, and the output path `feedback/replies-<lang>.json`. Then `build-feedback-plan.mjs --feedback=... --in-dir=feedback --tag="PR #<n>"` → `feedback-plan.json` (replies + adopted translator wording). It lists any open thread left unanswered; a run that leaves threads unanswered must say so in its report.
4. **Mechanical gate** (`decide.mjs --feedback=<feedback.json> ...`): split into two layers and write `decision.json` + `plan.json`. It drops unsourced grammar/orthography findings, posts no AWKWARD suggestions in a language with an active translator, and caps suggestions at 10 per language (`--max-suggestions`); each of these is printed and recorded in `decision.json` so the report can say what was withheld. Units with translator input are **held**: a WRONG fix there is posted as a comment, never applied, and AWKWARD suggestions on them are dropped because the thread already exists. If `feedback.json` is missing (fetch failed) *every* overwrite is downgraded to a comment — the gate never writes blind.
   - **Layer 1 — hard blockers (non-overridable, no judgment):** out-of-scope file (anything outside `src/locales/*.json`), malformed JSON, placeholder mismatch in a gated lang, or GitHub `CONFLICTING`. These can crash/break the app or are unsafe to auto-merge, so any one of them => `mechanical_verdict: HOLD` and the decision is final. The model cannot wave these through. Structural checks run on **every** changed locale; in a genuinely unwired one they are recorded as non-blocking `structuralWarnings` (plus a Weblate comment) so they get fixed before that locale is ever wired.
   - **Layer 2 — semantic findings (adjudicable):** `WRONG` (wired) and `AWKWARD` findings. These never auto-decide. With no hard blockers, `mechanical_verdict: ADJUDICATE`.
   - Unwired-language issues are recorded (`ignoredUnwired`) but never gate — they don't ship in-app.
5. **Adjudicate** (main session, only when `ADJUDICATE`): the session reads **all** `WRONG` + `AWKWARD` findings together (key, en, current, proposed fix, rationale, lang) and makes one reasoned `MERGE` or `HOLD` call — "are these wrongs terrible enough to keep off prod, or tolerable to fix next round?" This judgment lives with the main model, not a per-language subagent or a count threshold.
6. **Act** (`apply-decision.sh`, **dry-run by default; `--execute` to write**). Applies **Weblate writes only** (overwrites + suggestions + comments, state=10, plus `feedback-plan.json` when present: replies to translators and adopted wording at state=20) in all cases, and **records a MERGE/HOLD recommendation** — it does **not** merge or comment on GitHub. Pass `--decision=MERGE|HOLD --reason=...` (ignored if Layer 1 forced HOLD). A maintainer reads the recommendation, and merges PR manually once it looks clean (the `main` ruleset needs one approving review).
7. **Fill phase (opt-in: `--auto --fill-missing`).** After the merge decision, top up missing strings for wired languages, **uncapped**, per **Fill mode** above: find-missing → model sanity-judge each language's delta (fill new strings; flag-and-skip anything that looks like an `en.json` restructure) → translate contextually in a less-formal register → model quality pass → write at state=10 (`build-fill-plan.mjs --feedback=<feedback.json>` skips any key a translator is already on). Fills never change the *current* PR's decision (missing keys aren't in its diff) — they ride the next regenerated PR. Report what was filled and anything skipped.

Report the feedback pass too: how many open threads were found, answered (per action), adopted, and left open.

Why this shape: structural breakage (placeholders/JSON) is a fact, not an opinion — it stays mechanical. Everything that needs taste — the merge recommendation, "does this backfill make sense," and translation quality — goes to the model, which sees the whole picture at once rather than a single subagent's local call or a numeric threshold.

### Translator feedback — humans outrank the machine

Weblate has people on the other end. A translator who comments on a unit or leaves a
suggestion has done exactly what the project asks of them, and a run that then
overwrites that unit, or re-posts the same suggestion, or never answers, teaches them
to stop. So every run reads the human side before it writes anything.

**What is read.** `fetch-feedback.mjs` pulls every unit with a comment or a pending
suggestion (`GET /api/units/<id>/comments/` and `/suggestions/` both work on
hosted.weblate.org; only *creating* suggestions is missing). Each comment is classed
as `bot` (starts with `[review-l10n]`, or the older "Translation review suggestion:" /
"posted by review-l10n" forms), `maintainer` (the token owner, unmarked), or
`translator` (anyone else). A unit is **held** when a translator has commented or a
suggestion is pending; it is **open** when the latest translator word has no bot or
maintainer reply after it. Maintainer comments are context, not a hold: before
2026-09-04 the skill posted its overwrite notes unmarked under the maintainer's account.

**Rules.**
- A held unit is never overwritten by the gate or the fill. A WRONG fix on it becomes a
  flag comment; an AWKWARD suggestion on it is dropped.
- The translator's judgment wins by default. The feedback reviewer disagrees only for
  an app-context reason (the string is a chip and must stay short; a term is used
  consistently under another key) and even then it *proposes* and leaves the decision
  with them.
- Asked for a source you cannot cite? Withdraw. Never invent a norm.
- Every reply is short, specific, in English, addressed `@username`, and marked
  `[review-l10n <tag>]` — `build-feedback-plan.mjs` adds the mention and the marker.
- When the translator's wording should replace the current target, `adopt` writes it
  at **state=20** (they authored it; needs-editing would ask them to approve their
  own words) and says so in the reply.

**Reviewer output** (`feedback/replies-<lang>.json`, strict JSON):
`[{lang, key, action: adopt|withdraw|stand|ask|reply|none, reply, new?}]`. One item per
open unit; `none` with an empty reply for threads that need no answer (an anonymous
whitespace suggestion, say).

**Reviewer prompt must carry:** the app context (mobile, RN, local LLMs; Chat / Models /
Pals / Settings / Benchmark / Voice & Speech / HTML preview / onboarding), the path to
`feedback-<lang>.md`, read-only access to `en.json` and `<lang>.json` for terminology
(absolute paths, never `cd` into the submodule), permission to WebFetch a real
reference (CLDR, a dictionary), the rules above, and the output path. Language
reviewers stay blind to each other, as in Stage 4.

**Marker discipline.** `apply-plan.mjs` prefixes every comment it posts with
`[review-l10n]`; that is how the next run tells its own voice from a translator's.
Do not post Weblate comments through any other path.

### The wired list is derived, never written down

Which languages ship is decided by `languageRegistry` in `repos/pocketpal-ai/src/locales/index.ts`, and `wired-langs.mjs` reads it from the PR's **base commit** (not the local submodule checkout, which lags `main`). Nothing else may carry a copy.

This is a scar, not a style preference. The list used to be hardcoded in `coverage.mjs` and `decide.mjs`; PR #826 wired `pl`/`pt` and nobody updated the copies, so for weeks three shipping languages were excluded from **both** gate layers — including the "non-overridable" placeholder check. The failure was invisible because a skipped language and a clean language produce identical output.

Two consequences hold that shut:

- If the list cannot be derived, `decide.mjs` gates **every** changed locale rather than fall back to a default. Over-blocking is a nuisance; under-blocking ships a broken placeholder.
- `decide.mjs` always prints the `gated` / `SKIPPED` split. Coverage is stated, never implied — "we reviewed 10 of 13" must be visible in the run, not inferred from its silence.

**Human merge (manual step).** When a maintainer acts on a MERGE recommendation, merge the Weblate PR with a **merge commit**, never squash:
`gh pr merge <n> --repo a-ghorbani/pocketpal-ai --merge --admin`. Squash rewrites
history so Weblate's commits stop being ancestors of `main`, and Weblate's next
update fails with a rebase conflict (`CONFLICT in src/locales/*.json`). If that
happens, recover with a Weblate **repository reset** (`POST .../repository/
{"operation":"reset"}`) — `main` already has the content; reset drops only
un-pushed pending edits, which the next routine run regenerates.

Secrets for unattended runs: only `WLT_TOKEN` (Weblate) is needed — the routine no
longer merges or comments on GitHub, so no GitHub write token is required. Reading
the PR uses the ambient read-only token.

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
5. `build-fill-plan.mjs --missing-dir=<d> --out-dir=<d> --langs=... --feedback=<feedback.json>` → validates (placeholders byte-identical, coverage, dupes; skips whitespace-only `en` icon labels; skips keys a translator has commented on or suggested for) and assembles `fill-plan.json` (overwrites only, state=10).
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
# Derive the wired list first — every downstream stage depends on it.
WIRED=$(node skills/review-l10n/scripts/wired-langs.mjs --ref="${BASE_OID}")

node skills/review-l10n/scripts/coverage.mjs "${SCRATCH}/head" --wired="${WIRED}" > "${SCRATCH}/coverage.txt"
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
node skills/review-l10n/scripts/diff-entries.mjs "${SCRATCH}/head" "${SCRATCH}/base" \
  "${SCRATCH}/diff-report.txt" --manifest="${SCRATCH}/review-manifest.json"

# Split per language for parallel agents
awk -v scratch="${SCRATCH}" '/^## [A-Za-z_]+:/ {f=scratch "/diff-" $2 ".txt"; sub(":","",f)} f {print > f}' "${SCRATCH}/diff-report.txt"
```

For each changed wired language, spawn a `general-purpose` agent **in parallel**. Each agent gets:
- The path to its diff file only (never another language's file), plus its `feedback-<lang>.md` when one exists.
- A language-specific prompt that:
  - States the app context (mobile, RN, local LLMs, Settings/Models/Chat).
  - Lists language-specific gotchas: orthography (e.g. Russian ё, missing measure word 个 in Chinese, Korean register mismatch), brand-name policy (keep `OpenAI`, `Groq`, `Hugging Face`, model names, engine names like `Kitten/Kokoro/Supertonic` in English).
  - Reminds: placeholders `{{name}}` must stay byte-identical.
  - Names the reference(s) for that language (table below) and grants WebFetch to consult them.
  - States the scope: **WRONG only** when `feedback.json` lists an active translator for the language; WRONG + AWKWARD otherwise.
  - Asks for output limited to AWKWARD/WRONG entries with key, en, lang, `kind`, one-line note, and `source` where required.

### Grounded findings — a norm needs a reference, not a belief

The failure this guards against is real: on PR #884 the Belarusian reviewer asserted
"the standard abbreviation is X" and "the genitive is Y" for a low-resource language,
with no source, and a native translator refuted every one with CLDR. A model's
confidence in a grammar rule is not evidence of the rule.

- Every finding carries `kind`: `meaning` (sense changed, English leaked, wrong term),
  `grammar`, `orthography`, `style`, `brand`, `placeholder`.
- `grammar` and `orthography` findings **must** carry `source`: the URL the reviewer
  actually fetched (CLDR data, a dictionary entry, a published style guide). The gate
  drops any without one. The reviewer's prompt must say this outright, and say that
  its own knowledge does not count. Language-model consensus is exactly what was wrong
  on PR #884.
- `meaning` findings need no external source — the English string and the app context
  are the evidence — but the note must say what the current text means and why that
  differs from the source.
- **Active translator → meaning only.** If `feedback.json` shows translator activity in
  the last 90 days for a language, the reviewer is told to report WRONG only. Style is
  that person's job, and thirty style notes on a volunteer's work is how a locale loses
  its translator. The gate enforces this even if the reviewer ignores it.
- **Cap.** At most 10 AWKWARD suggestions per language per run are posted; the rest are
  recorded in `decision.json` and mentioned in the report. Reviewers should put the
  most consequential first.

References to hand each reviewer (verify the URL works before relying on it; extend as
languages are added):

| lang | reference |
| --- | --- |
| any | CLDR data: `https://raw.githubusercontent.com/unicode-org/cldr/main/common/main/<code>.xml` (dates, units, relative-time abbreviations, plurals); survey tool `https://st.unicode.org/cldr-apps/v#/<code>/` |
| be | skarnik.by (ТСБМ + Belarusian–Russian dictionaries) `https://www.skarnik.by/` |
| ru | Грамота.ру `https://gramota.ru/` |
| uk | Словник.ua `https://slovnyk.ua/` · СУМ `https://sum.in.ua/` |
| pl | Słownik PWN `https://sjp.pwn.pl/` |
| pt / pt_BR | Priberam `https://dicionario.priberam.org/` |
| id | KBBI `https://kbbi.kemdikbud.go.id/` |
| ms | PRPM (DBP) `https://prpm.dbp.gov.my/` |
| fa | Vajehyab `https://www.vajehyab.com/` |
| he | Academy of the Hebrew Language `https://hebrew-academy.org.il/` |
| ko | 표준국어대사전 `https://stdict.korean.go.kr/` |
| zh_Hant | 教育部重編國語辭典 `https://dict.revised.moe.edu.tw/` |
| ja / zh | CLDR plus in-app consistency; treat grammar claims as `style` unless a source is found |

**Chunk anything large — one agent per 50 entries.** `review-manifest.json` gives each language a `chunks` count; honour it. A reviewer handed 300 entries and asked "flag what's wrong" degrades badly: it reads the head of the diff carefully and skims the tail, and the whole point of the pass is the one bad string among the 299 fine ones. Give each agent a slice and a line range, and tell it the slice is a slice. A 300-entry `zh` polish pass is 7 reviewers, not one.

Mass-rewrite passes deserve extra suspicion, not less. When a language shows hundreds of changed (not added) entries it is usually a human style sweep — spacing, punctuation, terminology — and the risk is not that the sweep is bad but that one entry quietly acquired a *new claim* while everything around it was cosmetic. Prompt the reviewer to hunt for meaning drift specifically, and to ignore the cosmetic churn it is swimming in.

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
- For overwrites: `PATCH /api/units/<id>/ {target, state: item.state ?? default_state}`.
- For suggestions: a `[review-l10n]` comment carrying the proposal (hosted.weblate.org has no suggestion-create API); the target is untouched.
- For comments and replies: `POST /api/units/<id>/comments/ {comment, scope: "translation"}`, always prefixed `[review-l10n]`.
- Throttles to ≤ 1 req/sec to be polite to hosted.weblate.org.
- Reports per-line success/fail with the Weblate unit URL.

## Stage 8 — Report back

End with a short summary:
- How many entries patched / suggested / commented.
- Any failures (with reason).
- Reminder: a follow-up Weblate auto-merge PR will pick up the changes; PR #<n> itself does NOT need to be reopened.

## Anti-patterns to avoid

- Don't hardcode the wired-language list anywhere. Derive it with `wired-langs.mjs`. A stale copy silently shrinks the gate and looks exactly like a clean run.
- Don't hand one subagent a diff of hundreds of entries — chunk per `review-manifest.json`.
- Don't run native subagent reviews in series — always parallel; they're independent.
- Don't show one language's findings to another's reviewer.
- Don't patch directly on PR; all writes go to Weblate. The PR will be regenerated.
- Don't commit `.env` or echo `$WLT_TOKEN` to stdout. Never paste tokens into the conversation.
- Don't ask the user to paste the token in chat. Direct them to `.env` instead.
- Don't merge or close the original auto-merge PR as part of this skill — that's a separate decision.
- Don't overwrite, re-suggest on, or machine-fill a unit a translator has commented on or suggested for. Answer the thread instead (`build-feedback-plan.mjs`).
- Don't post a Weblate comment without the `[review-l10n]` marker — the next run would read it as a human's.
- Don't assert a grammar or spelling norm from model memory. Fetch the reference, cite the URL in `source`, or downgrade the finding to `style`.
- Don't send style suggestions to a language with an active translator. WRONG only there.

## See also

- `scripts/wired-langs.mjs` — derives the wired list from `src/locales/index.ts`. Exits 3 rather than guess.
- `scripts/coverage.mjs` — coverage logic.
- `scripts/find-placeholder-issues.mjs` — placeholder mismatch scanner.
- `scripts/diff-entries.mjs` — per-language diff producer.
- `scripts/weblate-client.mjs` — shared Weblate client: token, throttle/429 retry, lang remap, the `[review-l10n]` marker, unit lookup, comment/suggestion reads.
- `scripts/apply-plan.mjs` — Weblate API executor (overwrites, suggestions-as-comments, comments, replies).
- `scripts/fetch-feedback.mjs` — pull translator comments + pending suggestions → `feedback.json` and per-language `feedback-<lang>.md`.
- `scripts/build-feedback-plan.mjs` — validate the feedback reviewers' resolutions → `feedback-plan.json` (replies + adopted wording).
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
- **Reads that work (verified 2026-09-04).** `GET /api/units/<id>/comments/` → `{results:[{comment, timestamp, user}]}`; `GET /api/units/<id>/suggestions/` → `{results:[{target, user, timestamp, votes}]}`; unit search `?q=has:comment OR has:suggestion`; `GET /api/users/?page_size=1` returns the token's own account (used to tell maintainer comments from translators'). `GET /api/units/<id>/changes/` is 404.
- **Comments post under the token owner's name.** There is no bot identity; the `[review-l10n]` marker is the only thing that distinguishes the skill's comments from the maintainer's own.
- **Unit lookup.** `GET /api/translations/<project>/<component>/<lang>/units/?q=context:<key>` returns results matched by Weblate's substring search; always re-filter client-side on exact `context` equality (the skill does this).
