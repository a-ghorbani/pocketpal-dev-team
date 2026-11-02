# Fill mode (`--fill`)

Read from `skills/review-l10n/SKILL.md` when running `--fill` or `--auto --fill-missing`.

`--fill <lang[,lang...]>` backfills **genuinely-missing** strings (keys present in
`en.json` but absent/empty in the locale) for wired languages, written to Weblate
at **state=10 ("needs-editing")**.

Runs on demand, or as an opt-in phase of the twice-weekly `--auto` run
(`--auto --fill-missing`, see `auto-mode.md`). **Uncapped** — each run fills whatever is
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
