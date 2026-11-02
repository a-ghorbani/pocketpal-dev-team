# Translator feedback — humans outrank the machine

Read from `skills/review-l10n/SKILL.md` before any Weblate write, and when briefing a feedback-resolution reviewer.

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

Most translator work is silent, though: edits, often uploaded as a file offline, with no
comment, and the uploader never sees our notes. So `fetch-feedback.mjs` also reads each
language's change log (`GET /api/translations/<p>/<c>/<lang>/changes/?timestamp_after=`)
and counts a person's edits as activity. Comments alone missed every active translator
except one (PR #944: 233 Russian edits read as "no active translator").

The same log is each unit's **edit history** (last 180 days): `feedback.json` `history`,
interleaved with the comments in `feedback-<lang>.md`, and per key in `history-<lang>.md`.
Without it the review could not see, on PR #944, that the Russian translator's own
earlier correct wording had been replaced by a later file upload, or that a zh_Hant
term change it kept "fixing" was the translator's deliberate choice.

**Rules.**
- **The machine overwrites only machine text.** `apply-plan.mjs` checks the live unit
  at write time and refuses an overwrite when the unit is at state ≥ 20 (a person
  translated or approved it; our drafts are written at 10), or when its live target
  differs from the plan's `current` (it changed since the review, or the finding
  quoted an excerpt). The fix then goes out as a flag comment. Only an `adopt` of the
  translator's own wording skips the state check. This guard covers every path:
  `--auto`, an interactive "fix the wrong ones", and fills. Report HELD lines as held,
  never as applied.
- A held unit is never overwritten by the gate or the fill. A WRONG fix on it becomes a
  flag comment; an AWKWARD suggestion on it is dropped.
- **One note per unit until someone edits it.** If this skill (or the maintainer) has
  commented on a unit and its target has not changed since, `decide.mjs` posts nothing
  new there — WRONG or AWKWARD — and lists it under `alreadyFlagged` with the note
  count and dates. On PR #944 the same eight units collected two or three identical
  flags across runs; a translator who did not act on a note will not act on its copy,
  and an offline uploader never sees either. Whether to press further (the maintainer
  fixes it, or asks elsewhere) is a human call: report the stale flags, never re-post.
  Exception: our own unedited draft (state < 20) may still be corrected.
- **A comment needs a reader.** An AWKWARD fix on a unit only this skill has ever
  written (every edit in the history is the token owner's) rewrites the draft at
  state 10 instead of commenting to nobody; `apply-plan.mjs` still re-checks state
  and text live.
- A finding that would undo a translator's edit visible in `history-<lang>.md` (they
  replaced our draft, or their own earlier wording) is a question, not a revert: say
  what changed and ask whether it was intended.
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
reviewers stay blind to each other, as in Stage 4 (`semantic-review.md`).

**Marker discipline.** `apply-plan.mjs` prefixes every comment it posts with
`[review-l10n]`; that is how the next run tells its own voice from a translator's.
Do not post Weblate comments through any other path.
