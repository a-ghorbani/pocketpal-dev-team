# Auto mode (`--auto`)

Read from `skills/review-l10n/SKILL.md` when running `--auto`.

## Flow

`--auto` reviews the recurring Weblate PR, **applies fixes to Weblate**, and emits a
**MERGE/HOLD recommendation** — a human does the actual merge. It is designed to run
unattended (twice-weekly remote routine) and replaces the "ask before every write"
gate with a deterministic rubric.

**It never touches GitHub** — no PR merge, no PR comment. The `main` ruleset requires
an approving review, and merges to a prod branch stay a human decision. The routine's
only writes are to Weblate; the recommendation is recorded for a maintainer to act on.

Flow (orchestrated by `scripts/auto-review.sh` → semantic subagents → feedback subagents → `scripts/decide.mjs` → `scripts/apply-decision.sh`):

1. **Discover** the open Weblate PR (`author:weblate`, head `weblate-translations`). No PR → exit cleanly.
2. **Pre-review** (`auto-review.sh`): fetch head/base locale JSONs, **derive the wired-language list** (`wired-langs.mjs` against the PR's base commit), run coverage + placeholder checks, split the diff per language, write `review-manifest.json` with the per-language entry counts and chunk plan, and **pull translator feedback** (`fetch-feedback.mjs` → `feedback.json` + `feedback/feedback-<lang>.md` + `feedback/history-<lang>.md`, every language, see `translator-feedback.md`). Its summary lists the *open* threads — translator comments or pending suggestions nobody has answered.
3. **Semantic review**: spawn `general-purpose` subagents over the *changed gated* languages (parallel, blind to each other), each returning STRICT-JSON findings: `[{lang,key,severity:WRONG|AWKWARD,kind,en,current,new?,proposal?,note,source?}]` (see Grounded findings in `semantic-review.md`: a grammar or orthography claim without a consulted URL is dropped by the gate; a language with an active translator gets WRONG-only review; at most 10 suggestions per language are posted). **Honour the manifest's `chunks`** — a language over 50 entries is split across that many reviewers, each given a slice, never one agent for the whole diff (`semantic-review.md`). Each reviewer also gets its language's `feedback-<lang>.md` and `history-<lang>.md` when they exist, so it does not re-raise what a translator has already settled, and sees when a finding would undo a translator's deliberate edit. Collate into `findings.json`.
3b. **Feedback resolution**: for every language with open threads (any language, wired or not — a translator is a translator), spawn one `general-purpose` subagent with that language's `feedback-<lang>.md`, the rules from `translator-feedback.md`, and the output path `feedback/replies-<lang>.json`. Then `build-feedback-plan.mjs --feedback=... --in-dir=feedback --tag="PR #<n>"` → `feedback-plan.json` (replies + adopted translator wording). It lists any open thread left unanswered; a run that leaves threads unanswered must say so in its report.
4. **Mechanical gate** (`decide.mjs --feedback=<feedback.json> ...`): split into two layers and write `decision.json` + `plan.json`. It drops unsourced grammar/orthography findings, posts no AWKWARD suggestions in a language with an active translator, and caps suggestions at 10 per language (`--max-suggestions`); each of these is printed and recorded in `decision.json` so the report can say what was withheld. Units with translator input are **held**: a WRONG fix there is posted as a comment, never applied, and AWKWARD suggestions on them are dropped because the thread already exists. If `feedback.json` is missing (fetch failed) *every* overwrite is downgraded to a comment — the gate never writes blind. A unit we already flagged with no edit since is **not re-posted** (`alreadyFlagged`, see `translator-feedback.md`), and an AWKWARD fix on this skill's own untouched draft rewrites the draft instead of commenting on it (`draftRewrites`).
   - **Layer 1 — hard blockers (non-overridable, no judgment):** out-of-scope file (anything outside `src/locales/*.json`), malformed JSON, placeholder mismatch in a gated lang, or GitHub `CONFLICTING`. These can crash/break the app or are unsafe to auto-merge, so any one of them => `mechanical_verdict: HOLD` and the decision is final. The model cannot wave these through. Structural checks run on **every** changed locale; in a genuinely unwired one they are recorded as non-blocking `structuralWarnings` (plus a Weblate comment) so they get fixed before that locale is ever wired.
   - **Layer 2 — semantic findings (adjudicable):** `WRONG` (wired) and `AWKWARD` findings. These never auto-decide. With no hard blockers, `mechanical_verdict: ADJUDICATE`.
   - Unwired-language issues are recorded (`ignoredUnwired`) but never gate — they don't ship in-app.
5. **Adjudicate** (main session, only when `ADJUDICATE`): the session reads **all** `WRONG` + `AWKWARD` findings together (key, en, current, proposed fix, rationale, lang) and makes one reasoned `MERGE` or `HOLD` call — "are these wrongs terrible enough to keep off prod, or tolerable to fix next round?" This judgment lives with the main model, not a per-language subagent or a count threshold.
6. **Act** (`apply-decision.sh`, **dry-run by default; `--execute` to write**). Applies **Weblate writes only** (overwrites + suggestions + comments, state=10, plus `feedback-plan.json` when present: replies to translators and adopted wording at state=20) in all cases, and **records a MERGE/HOLD recommendation** — it does **not** merge or comment on GitHub. Pass `--decision=MERGE|HOLD --reason=...` (ignored if Layer 1 forced HOLD). A maintainer reads the recommendation, and merges PR manually once it looks clean (the `main` ruleset needs one approving review).
7. **Fill phase (opt-in: `--auto --fill-missing`).** After the merge decision, top up missing strings for wired languages, **uncapped**, per `fill-mode.md`: find-missing → model sanity-judge each language's delta (fill new strings; flag-and-skip anything that looks like an `en.json` restructure) → translate contextually in a less-formal register → model quality pass → write at state=10 (`build-fill-plan.mjs --feedback=<feedback.json>` skips any key a translator is already on). Fills never change the *current* PR's decision (missing keys aren't in its diff) — they ride the next regenerated PR. Report what was filled and anything skipped.

Report the feedback pass too: how many open threads were found, answered (per action), adopted, and left open.

Why this shape: structural breakage (placeholders/JSON) is a fact, not an opinion — it stays mechanical. Everything that needs taste — the merge recommendation, "does this backfill make sense," and translation quality — goes to the model, which sees the whole picture at once rather than a single subagent's local call or a numeric threshold.


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
