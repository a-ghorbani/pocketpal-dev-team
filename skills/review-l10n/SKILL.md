---
name: review-l10n
description: Review a Weblate auto-merge PR (or any locale PR) for PocketPal. Computes per-locale completion, identifies wirable candidates, runs per-language semantic review via subagents, validates placeholders, and optionally applies fixes back to Weblate (overwrites + suggestions + comments).
user-invocable: true
argument-hint: "<pr-number | branch-ref | locales-dir>"
---

# Review L10n

Review a PocketPal localization change as a translation-quality and wiring-readiness audit.

```text
/review-l10n 683                    # Weblate auto-merge PR
/review-l10n PR-683                 # same, by branch label
/review-l10n weblate-translations   # branch ref
/review-l10n --auto                 # unattended merge-gate (discovers the open Weblate PR)
/review-l10n --fill <lang[,lang]>   # backfill missing strings
```

## References (read X when Y)

| File in `references/` | Read when |
| --- | --- |
| `auto-mode.md` | running `--auto`: the 7-step flow, the two gate layers, adjudication, human merge |
| `translator-feedback.md` | before any Weblate write; briefing a feedback-resolution reviewer (what is read, output schema, prompt) |
| `fill-mode.md` | running `--fill` or `--auto --fill-missing` |
| `stages.md` | interactive run: Stage 1–3 and 5–8 commands, `plan.json` format, apply behaviour |
| `semantic-review.md` | Stage 4: reviewer prompt, grounded findings, per-language reference URLs, gotchas, chunking |
| `weblate-and-scripts.md` | the wired-list history, every script's role, hosted.weblate.org API quirks |

## Inputs and contract

- Target: PR number (preferred), branch ref, or a directory of locale JSONs. Repo `a-ghorbani/pocketpal-ai`. Weblate project/component `pocketpal-ai/translations` (confirm before any write). If target info can't be resolved from `gh`, stop and ask.
- Scratch dir `/tmp/review-l10n-<TARGET_ID>/`, never inside the submodule or a worktree. The submodule is read-only: pull locale JSONs via `gh api` from the PR head; never patch there.
- Interactive runs: every Weblate write needs explicit user approval; default to **dry-run** unless the user says "apply". Overwrites default to state `10` (needs editing) so a native speaker re-confirms.
- `WLT_TOKEN` is the only secret; `apply-plan.mjs` loads it itself. Never echo it, paste it, ask the user to paste it in chat (point them to `.env`), or commit `.env`.
- All writes go to Weblate, never the PR (it is regenerated). Never merge or close the auto-merge PR here.

## Interactive stages (`stages.md`, `semantic-review.md`)

1. **Fetch** head and base locale JSONs (`scripts/fetch-pr.sh <PR> <SCRATCH>`).
2. **Coverage + validation.** Derive the wired list first (`wired-langs.mjs --ref=<BASE_OID>`), then always run `coverage.mjs --wired=` and `find-placeholder-issues.mjs`; the repo's `validate-l10n.js` (copied into scratch) is optional, informational.
3. **Wirable candidates**: unwired locales with `%present ≥ 95`, `%translated ≥ 95`, 0 placeholder mismatches. If none qualify, say so; never round 90% up to "almost wirable": state what's missing.
4. **Semantic review**: `diff-entries.mjs --manifest=`, split per language, one `general-purpose` reviewer per changed wired language (and per chunk), in parallel.
5. **Plan** `plan.json`: OVERWRITES (clear functional bug: placeholder mismatch, leaked English, meaning-changing term, missing measure word making it ungrammatical) and SUGGESTIONS (stylistic: register, capitalization, punctuation, brand handling, idiom). Brand-name un-translations (uk `Кошеня` for `Kitten`) are overwrites by default; downgrade if the user prefers.
6. **Present** the summary table and ask: "Apply now, dry-run, or save plan only?" No write without affirmative approval.
7. **Apply**: `apply-plan.mjs plan.json [--dry-run]`.
8. **Report**: patched / suggested / commented counts, failures with reason, and that the next Weblate PR picks the changes up (PR #<n> needs no reopen).

## Semantic review rules (Stage 4, `--auto` step 3)

- Reviewers run in parallel, each seeing only its own diff slice (plus its `feedback-<lang>.md` and `history-<lang>.md`), never another language's findings.
- Honour `review-manifest.json` `chunks`: one reviewer per 50 entries, each told its slice is a slice. On mass rewrites, hunt meaning drift and ignore cosmetic churn.
- Prompt carries: app context, language gotchas, brand-name policy (keep `OpenAI`, `Groq`, `Hugging Face`, model and engine names like `Kitten/Kokoro/Supertonic` in English), `{{placeholders}}` byte-identical, the language's reference URLs with WebFetch, the scope, and the output shape (AWKWARD/WRONG only, with key, en, lang, `kind`, note, `source`).
- Every finding has `kind`: `meaning`, `grammar`, `orthography`, `style`, `brand`, `placeholder`. `grammar`/`orthography` need `source`, a URL actually fetched; model knowledge doesn't count and the gate drops unsourced ones (or downgrade to `style`). `meaning` needs no URL but says what the text means and why it differs. Verify a reference URL works before relying on it.
- Translator activity in the last 90 days → WRONG only for that language (gate-enforced).
- At most 10 AWKWARD suggestions per language per run, most consequential first; the rest go to `decision.json` and the report.

## Translator feedback rules (`translator-feedback.md`)

Every run reads the human side (`fetch-feedback.mjs`: comments, pending suggestions, 180-day edit history) before it writes.

- **The machine overwrites only machine text.** `apply-plan.mjs` refuses an overwrite when the live unit is at state ≥ 20 or its live target differs from `current`; the fix goes out as a flag comment. Only an `adopt` skips the state check. Applies to `--auto`, interactive fixes, and fills; never route a write around it. Report HELD lines as held, never applied.
- A held unit (translator comment or pending suggestion) is never overwritten or machine-filled: a WRONG fix becomes a flag comment, an AWKWARD suggestion is dropped; answer the thread instead (`build-feedback-plan.mjs`).
- **One note per unit until someone edits it**: a unit already flagged with no edit since gets nothing new (`alreadyFlagged`); report stale flags, never re-post. Exception: our own unedited draft (state < 20) may be corrected.
- **A comment needs a reader**: an AWKWARD fix on a unit only this skill has written rewrites the draft at state 10 instead of commenting (`draftRewrites`).
- A finding that would undo a translator's edit in `history-<lang>.md` is a question, not a revert.
- The translator's judgment wins by default; disagree only for an app-context reason, and then propose, leaving the decision with them. Asked for a source you cannot cite: withdraw. Never invent a norm.
- Replies: short, specific, English, `@username`, marked `[review-l10n <tag>]` (added by `build-feedback-plan.mjs`). `adopt` writes the translator's wording at state 20 and says so.
- Every Weblate comment carries the `[review-l10n]` marker and goes through `apply-plan.mjs` only.
- Report the feedback pass: open threads found, answered (per action), adopted, left open. Unanswered threads must be named.

## Wired-list rules

- The wired list is derived by `wired-langs.mjs` from `languageRegistry` in `src/locales/index.ts` at the PR's **base commit**; never hardcode or copy it anywhere.
- If it can't be derived, `decide.mjs` gates **every** changed locale. It always prints the `gated` / `SKIPPED` split.

## `--auto` rules (`auto-mode.md`)

- Never touches GitHub (no merge, no PR comment): writes go to Weblate only, plus a recorded MERGE/HOLD recommendation for a human. No open Weblate PR → exit cleanly.
- **Layer 1** hard blockers (file outside `src/locales/*.json`, malformed JSON, placeholder mismatch in a gated language, GitHub `CONFLICTING`) force a final, non-overridable HOLD. Structural checks run on every changed locale; in an unwired one they are non-blocking `structuralWarnings` plus a Weblate comment.
- **Layer 2** (WRONG, AWKWARD) never auto-decides: with no blockers the main session reads all findings together and makes one MERGE/HOLD call, never a subagent or a count threshold. Unwired-language issues are recorded (`ignoredUnwired`) and never gate.
- Missing `feedback.json` downgrades every overwrite to a comment.
- `apply-decision.sh` is dry-run by default; `--execute` writes; `--decision=MERGE|HOLD --reason=...` (ignored under a Layer 1 HOLD).
- A human merges a MERGE with a **merge commit**, never squash: `gh pr merge <n> --repo a-ghorbani/pocketpal-ai --merge --admin`. Rebase conflict after a squash → Weblate repository reset (`auto-mode.md`).
- The fill phase never changes the current PR's decision; report what was filled and skipped.

## Fill rules (`fill-mode.md`)

- Fill only genuinely missing keys (absent/empty; identical-to-en is excluded) in wired languages, at state 10, uncapped. A filled value **ships** on the next Weblate PR, replacing the English fallback: a deliberate ship-MT action.
- The model sanity-judges each language's delta, never a numeric cap: a delta that looks like an `en.json` restructure is not filled but flagged and reported.
- Translators keep `{{placeholders}}` byte-identical and brand/engine/model names in English, translate contextually (key path, screen, neighbours), in a natural, less-formal register; a model quality pass precedes the write.
- `build-fill-plan.mjs --feedback=` skips keys a translator is on; `apply-plan.mjs` runs in the background, with no per-unit comments.

## Weblate quirks (`weblate-and-scripts.md`)

Repo `zh` is Weblate `zh_Hans` (`LANG_REMAP`; check new codes on a 404). No suggestion-create API: proposals post as `[review-l10n]` comments (`--no-suggestion-fallback` to fail instead). Comments use `scope: "translation"` and post under the token owner's name. Unit lookup re-filters on exact `context`. Calls are throttled to ≤ 1 req/sec.
