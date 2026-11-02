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

## Reviewer and lenses

One role, `pocketpal-reviewer`, prompted with its lens(es); the lenses (Correctness, Architecture and maintainability, Tests, Security and privacy, Performance and resources, Platform, Data and migration, UX and accessibility, Local invariants) and their checks live in `docs/standards/review-lenses.md`. The lead (`/review-pr`) builds the review map itself. Each reviewer returns only concrete findings (severity, lens, confidence, file:line, impact, evidence, fix) or `NOTHING_FOUND`.

## Working Method

Each lens's concerns are a floor; surface anything else a PocketPal reviewer would notice. Group findings by lens; N/A only when clearly irrelevant.

High-risk (read-only parallel subreviews covering every lens that applies before a complete final review) when any holds: changed files > 10; native dependency or native code changes; persistence, migration, or schema changes; security/trust-boundary changes; model/tool execution changes; multi-surface changes; the user asks for a robust/deep review. Otherwise one reviewer applies every lens.

If they did not complete, the final review is marked incomplete: it may summarize issues, never claim a complete approval or request-changes.

## Native verification

Not a lens: checked in verification (the pipeline-reviewer runs it on pipeline work). `NATIVE_CHANGES=YES` requires `pod install`, an iOS build, and an Android build before approval; a native diff without them is a process finding (e.g. a lockfile changed on one platform, the other build unverified). Check native-dependency autolinking, cross-OS/chip compatibility (arm64 vs simulator, llama.rn backend variants, device vs emulator), App Store/Play Store constraints, and that no native artifact comes from the read-only submodule.

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

Before a `BLOCKER`/`CONCERN` enters the final review, someone other than the reviewer that raised it (the lead synthesizer, or a skeptic subreview for the highest stakes) tries to **refute** it:

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
