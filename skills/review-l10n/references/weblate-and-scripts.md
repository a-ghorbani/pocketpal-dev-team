# Wired list, scripts, and hosted.weblate.org

Read from `skills/review-l10n/SKILL.md` when touching the wired list, a script, or the Weblate API.

## The wired list is derived, never written down

Which languages ship is decided by `languageRegistry` in `repos/pocketpal-ai/src/locales/index.ts`, and `wired-langs.mjs` reads it from the PR's **base commit** (not the local submodule checkout, which lags `main`). Nothing else may carry a copy.

This is a scar, not a style preference. The list used to be hardcoded in `coverage.mjs` and `decide.mjs`; PR #826 wired `pl`/`pt` and nobody updated the copies, so for weeks three shipping languages were excluded from **both** gate layers — including the "non-overridable" placeholder check. The failure was invisible because a skipped language and a clean language produce identical output.

Two consequences hold that shut:

- If the list cannot be derived, `decide.mjs` gates **every** changed locale rather than fall back to a default. Over-blocking is a nuisance; under-blocking ships a broken placeholder.
- `decide.mjs` always prints the `gated` / `SKIPPED` split. Coverage is stated, never implied — "we reviewed 10 of 13" must be visible in the run, not inferred from its silence.

## See also

- `scripts/wired-langs.mjs` — derives the wired list from `src/locales/index.ts`. Exits 3 rather than guess.
- `scripts/coverage.mjs` — coverage logic.
- `scripts/find-placeholder-issues.mjs` — placeholder mismatch scanner.
- `scripts/diff-entries.mjs` — per-language diff producer.
- `scripts/weblate-client.mjs` — shared Weblate client: token, throttle/429 retry, lang remap, the `[review-l10n]` marker, unit lookup, comment/suggestion reads.
- `scripts/apply-plan.mjs` — Weblate API executor (overwrites, suggestions-as-comments, comments, replies).
- `scripts/fetch-feedback.mjs` — pull translator comments + pending suggestions + 180-day edit history → `feedback.json`, per-language `feedback-<lang>.md` and `history-<lang>.md`.
- `scripts/build-feedback-plan.mjs` — validate the feedback reviewers' resolutions → `feedback-plan.json` (replies + adopted wording).
- `scripts/find-missing.mjs` — `--fill`: list en keys missing/empty in a locale.
- `scripts/build-fill-plan.mjs` — `--fill`: validate subagent translations → fill plan (overwrites, state=10).
- `scripts/auto-review.sh` — `--auto` pre-review: discover PR, fetch, machine checks, per-lang diff split.
- `scripts/decide.mjs` — `--auto` merge-gate decision engine → `decision.json` + `plan.json`.
- `scripts/apply-decision.sh` — `--auto` act path: Weblate writes plus a recorded MERGE/HOLD recommendation; never merges or comments on GitHub (dry-run by default).
- `repos/pocketpal-ai/scripts/validate-l10n.js` — the repo's own (registry-aware) validator.
- Memory: locale registry lives in `repos/pocketpal-ai/src/locales/index.ts`.

## hosted.weblate.org gotchas (verified 2026-05-12)

- **Language code remap.** PocketPal repo uses `zh` for the Simplified Chinese file, but hosted.weblate.org's translation slug is `zh_Hans`. `apply-plan.mjs` remaps automatically via `LANG_REMAP`; if you add a new language and the unit lookup 404s, check what hosted.weblate.org calls it (e.g. `GET /api/translations/pocketpal-ai/translations/<code>/`) and update the map. Other PocketPal codes (`fa`, `he`, `id`, `ja`, `ko`, `ms`, `ru`, `uk`, `zh_Hant`) match Weblate 1:1.
- **No public suggestion API.** Neither `POST /api/units/<id>/suggestions/` nor `POST /api/suggestions/` exist on hosted.weblate.org (both return 404). Suggestions in the Weblate sense — proposed target visible alongside the current translation — are only creatable through the web UI. `apply-plan.mjs` falls back to posting the proposal + rationale as a comment, leaving the target untouched. Pass `--no-suggestion-fallback` if you'd rather fail loudly.
- **Comments endpoint.** `POST /api/units/<id>/comments/` with `{comment, scope}` works. Use `scope: "translation"` so the comment is scoped to the language, not the source string.
- **Reads that work (verified 2026-09-04).** `GET /api/units/<id>/comments/` → `{results:[{comment, timestamp, user}]}`; `GET /api/units/<id>/suggestions/` → `{results:[{target, user, timestamp, votes}]}`; unit search `?q=has:comment OR has:suggestion`; `GET /api/users/?page_size=1` returns the token's own account (used to tell maintainer comments from translators'). `GET /api/units/<id>/changes/` is 404.
- **Comments post under the token owner's name.** There is no bot identity; the `[review-l10n]` marker is the only thing that distinguishes the skill's comments from the maintainer's own.
- **Unit lookup.** `GET /api/translations/<project>/<component>/<lang>/units/?q=context:<key>` returns results matched by Weblate's substring search; always re-filter client-side on exact `context` equality (the skill does this).
