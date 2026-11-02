# PocketPal Code Review Standard

Canonical review policy; skills and agents add operating details (setup, worktrees, GitHub, execution, synthesis), never redefine or weaken it. Goal: keep bad code out, good code maintainable: correct in edge cases, low regression risk, clear ownership, safe data, dependency, and visible changes, evidence over style noise.

## Canonical Inputs

Load what is available; state missing critical context.

- The diff (PR, branch, or worktree) and the story, issue, or acceptance criteria.
- The story's `evidence.md` (proven, with receipts), `decisions.md`, and WHAT §8 (decided). Re-raise a decided item only with named new evidence it is wrong.
- The touched flow docs (`context/architecture/<flow>.md` in the story's `ARCHITECTURE_DOCS`, else those whose README index rows cover the changed files). A described behaviour change without a same-round doc update (or an unlanded-code line without `(pending #<PR>)`) is an Architecture finding on a pipeline PR (a story exists); on an external PR, note it in `final.md` for the orchestrator only.
- `context/patterns.md`, project standards the change references, existing CI or implementation verification output.

## Review Principles

1. Follow the risk first.
2. Read beyond the diff (callers, callees, patterns). A store-only diff can move every screen reading the store: assign reviewers by behaviour moved, not files touched.
3. Cite proof: code, contracts, tests, concrete failure modes.
4. Skip style churn unless it hurts safety, readability, or consistency.
5. Separate confirmed defects from unproven verification.
6. Review for the next engineer: flag hidden invariants and future traps.
7. Prefer the simpler fix; don't grow scope: the smallest correct change, reusing existing state or paths. Hardening, defence in depth, or an improvement costing more than the risk it removes is a SUGGESTION; a real, reachable defect (wrong behaviour, data loss, reachable security sink) keeps its severity whatever the fix costs.
8. Code with no reader, no trace to the request, or guarding an unreached path is an Architecture finding; removing it is a fix.

## Role Reviewers

- High-risk roles: `architect`, `qa`, `security`, `performance`, `mobile`, `data`, `ux`, `local-invariants` (small contract breaks on changed lines).
- Review-map helpers: `pocketpal-review-map-architect`, `pocketpal-flow-analyst`, `pocketpal-requirements-mapper`. Orientation notes for `review-map.md`, not findings.
- When no role subreviews are required, `pocketpal-code-reviewer` applies every lens.

Each role reviewer returns only concrete findings (severity, lens, confidence, file:line, impact, evidence, fix) or `NOTHING_FOUND`.

## Working Method

Each lens's concerns are a floor; surface anything else a PocketPal reviewer would notice. Group findings by lens; N/A only when clearly irrelevant.

High-risk (read-only subreviews by every high-risk role before a complete final review) when any holds: changed files > 10; native dependency or native code changes; persistence, migration, or schema changes; security/trust-boundary changes; model/tool execution changes; multi-surface changes; the user asks for a robust/deep review.

If they did not complete, the final review is marked incomplete: it may summarize issues, never claim a complete approval or request-changes.

## Required Lenses

- **Correctness** _(QA)_: broken behavior, bad assumptions, nulls, state mistakes, async races, retries, cancellation, stale state, error paths.
- **Architecture and boundaries** _(Architect)_: coupling, layering, public contracts, hidden dependencies, over-engineering.
- **Maintainability and readability** _(Architect)_: duplication, naming, fragile logic, magic constants, hard-to-test design.
- **Comment load** _(Architect; reported under Maintainability)_: a recurring defect here; review it unasked. Classify each questionable comment by the Comments test and **name the case** ("case 2: does three things", never just "too many comments"). Volume signals a clarity or design problem; fix the code. Flag task narrative (Comments).
- **Tests and verification** _(QA)_: missing coverage, weak assertions, contract-hiding mocks, skipped tests, manual validation gaps. **Coverage floor: 60%** (statements, branches, functions, lines) on the changed surface; below it is a `BLOCKER` unless explicitly waived.
- **Security and privacy** _(Security)_: **on-device app, not a server**: mobile threat model. Trust boundaries: (a) model output reaching render/execution surfaces (markdown/HTML/WebView/JS, tool-call/JSON parsing); (b) external content (downloaded GGUF models, web-search results, deep links / App Intents / Shortcuts params, PalsHub rows); (c) data at rest and in logs (chat history, API keys, server/auth tokens, crash reports); (d) the native bridge and capability allowlist (Pals-as-apps WebView); (e) debug/E2E hooks reachable in production. A trust-boundary finding names an untrusted **source**, the **sink** it reaches unsanitized, and shows it **reachable on `main`** with that input (call path, `file:line` per hop). A guard on a path no attacker input reaches is defence in depth: at most a SUGGESTION.
- **Data and migration safety** _(Data, Security)_: schemas, persisted state, cache invalidation, backward compatibility, rollback.
- **Performance and resources** _(Perf, Mobile)_: hot paths, unbounded work, repeated I/O, memory, storage, startup, battery. A plausible rise in RAM/heap, model load time, bundle size, startup, or battery use is at least a `CONCERN`.
- **UX and accessibility** _(UX/A11y)_: visible flows, honest states, error messages, accessibility, copy consistency, lost affordances.
- **Platform and native verification** _(Mobile)_: `NATIVE_CHANGES=YES` requires `pod install`, an iOS build, and an Android build before approval. Check cross-OS/chip compatibility: iOS floor, Android API min, arm64 vs simulator, llama.rn backend variants, device vs emulator.

## Comments

The four-case test and the no-task-narrative rule: `docs/standards/comments.md`.

## PocketPal-Specific Checks

- **Localization**: no hardcoded UI strings (registry `src/locales/index.ts`). Only `en.json` is edited directly; the rest live on Weblate. Editing a non-English locale file is a BLOCKER.
- **Testing**: project test utilities and centralized mocks; no inline store mocks or observable mutation outside accepted patterns.
- **MobX**: `observer`, `makeAutoObservable`, `runInAction` for async updates, computed getters, existing singleton/export conventions.
- **Components**: keep folder structure, TypeScript props, theming, `testID` on interactive elements.
- **Commits**: commitlint allows `feat`, `fix`, `docs`, `chore` as `type(scope): subject`.
- **Remote-server (llama-server) claims**: `200` comes back for unknown body keys, so a forwarded parameter can silently do nothing; verify against what the server reports applied. Only `404` is a fact about the build (`401` credentials, `400` this request, `500` this moment); cache no other as a capability. Every wire fact names the upstream build measured. Wire fixtures are verbatim, redacted for host paths, never reordered (some fields are positional).

## Severity

- `BLOCKER`: incorrect behavior, broken contract, exploitable security issue, unsafe data change, missing mandatory verification, missing critical test.
- `CONCERN`: real issue that should not merge yet.
- `SUGGESTION`: legitimate improvement, deferred to the published review's `Follow-ups` list; never triggers a fix round.

`NOTHING_FOUND` is valid; never invent issues.

## Confidence

Every finding carries `confidence`: `high` (proven by cited code, contract, or repro), `med` (strong inference), `low` (plausible but speculative). Severity is impact-if-real, confidence likelihood-it's-real; never collapse them (a `low`-confidence `BLOCKER` is what refutation tests).

## Adversarial verification

Before a `BLOCKER`/`CONCERN` enters the final review, someone other than its role reviewer (the lead synthesizer, or a skeptic subreview for the highest stakes) tries to **refute** it:

1. **Is it real?** Argue from code and contracts that it is not: wrong, handled elsewhere, unreachable on `main`, masked by an invariant, or already decided in `decisions.md` / WHAT §8.
2. **Is the fix worth it?** Hardening and improvements only: weigh the fix's cost (new states, guards, tests, surfaces touched) against the risk removed; bigger than its risk makes it a SUGGESTION.

Record `refutation: stands` (it ships) or `refutation: withdrawn — <reason>` (drop or downgrade). The delivery orchestrator copies these into `decisions.md`; reviewers don't write story files. A finding that fails a genuine refutation never ships as `BLOCKER`/`CONCERN` (audit trail, not silent dropping).

## Evidence Rules

1. Cite real paths and lines; read the file first.
2. Quote a short snippet when useful.
3. Missing-test findings cite the uncovered production code.
4. Mark inferences as inferences and unrun checks as unrun.
5. Name the revision reviewed; without one a record looks complete but isn't.
6. Fixture-backed findings check the fixture's provenance, not just presence.

## Verdict

- `APPROVE`: no unresolved blockers or concerns, verification complete or N/A, residual risk acceptable. An `APPROVE` with only suggestions ends the review.
- `REQUEST_CHANGES`: any blocker, serious open concern, missing mandatory verification, or unproven acceptance criteria.
- `ESCALATE`: needs human product/architecture judgment, or the diff is too ambiguous to review.

**Verification gate (mechanical).** `APPROVE` is invalid over any required `NOT_RUN` verification: downgrade to `REQUEST_CHANGES` or `ESCALATE`. `review_complete: yes` requires lint, typecheck, and tests at `PASS`/`N/A`, plus native builds at `PASS` when `NATIVE_CHANGES=YES`.

## Output

Human-facing (`final.md`) and headless shapes: `docs/standards/review-output.md`.
