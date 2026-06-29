# PocketPal Code Review Standard

The contract for PocketPal review workflows: lenses, severity, evidence, and output. Tool- and role-specific reviewers import this file and add their own operating bits on top.

## Ownership

This file is the canonical review policy. It owns review goals, lenses, roles, severity, evidence rules, high-risk classification, and output contracts.

It does not own target setup, worktree creation, GitHub commands, reviewer execution, or final synthesis mechanics. Skills and agents may add operating details, but they must not redefine or weaken this standard.

## Goal

Prevent bad code from landing; keep good code maintainable. Strong reviews optimize for:

- correct behavior under normal and edge conditions
- low regression risk
- maintainable design and clear ownership boundaries
- safe handling of data, dependencies, user-visible changes
- evidence-backed findings instead of stylistic noise

## Canonical Inputs

Load whatever is available:

- the change set (PR diff, branch diff, worktree diff)
- the story, issue, or acceptance criteria
- `context/patterns.md`
- project-local standards referenced by the change
- existing CI or implementation verification output

If critical context is missing, state it explicitly.

## Review Principles

1. Follow the risk first.
2. Read beyond the diff — callers, callees, surrounding patterns.
3. Cite proof — code, contracts, tests, concrete failure modes.
4. Skip minor style churn unless it affects safety, readability, or consistency.
5. Separate confirmed defects from unproven verification.
6. Review for the next engineer too — call out hidden invariants and future traps.

## Role Reviewers

Role worldview and file-focus guidance belong to the named role reviewers. This standard owns only the required role IDs and the contract they must follow.

Required high-risk role reviewers:

- `architect`
- `qa`
- `security`
- `performance`
- `mobile`
- `data`
- `ux`
- `local-invariants`

Review-map helper roles:

- `map-architect`
- `flow-analyst`
- `requirements-mapper`

Each role reviewer returns only concrete findings or `NOTHING_FOUND`. Map helper roles produce orientation notes for `review-map.md`, not final review findings.

## Working Method

For each lens below, apply the listed concerns as the floor and surface anything else a PocketPal reviewer would notice in this diff. Findings stay grouped by lens to match the output table.

Mark a lens N/A only if it is clearly not relevant to the diff.

For large or high-risk reviews, read-only role subreviews are required before a complete final review. A review is high-risk when any of these conditions apply:

- changed files > 10
- native dependency or native code changes
- persistence, migration, or schema changes
- security/trust-boundary changes
- model/tool execution changes
- multi-surface changes
- user explicitly asks for a robust/deep review

Use the required high-risk role reviewers listed above. Each role returns only concrete findings with severity, file:line, impact, evidence, and fix, or `NOTHING_FOUND`.

If high-risk role subreviews were required but not completed, the final review must be marked incomplete. It may summarize found issues, but it must not claim a complete approval/request-changes review.

The `local-invariants` role reviews changed lines for small contract breaks defined by that reviewer.

## Required Lenses

- **Correctness** _(QA)_: broken behavior, bad assumptions, null handling, state mistakes, async races, retries, cancellation, stale state, error paths.
- **Architecture and boundaries** _(Architect)_: coupling, layering, public contracts, hidden dependencies, over-engineering.
- **Maintainability and readability** _(Architect)_: duplication, naming, fragile logic, magic constants, hard-to-test design. (Owned by the architect role in high-risk reviews; the lead applies it against the diff directly when no architect subreview ran.)
- **Tests and verification** _(QA)_: missing coverage, weak assertions, mocks that hide contracts, skipped tests, manual validation gaps. **Coverage floor: 60%** (statements, branches, functions, lines) for the changed surface; below it is a `BLOCKER` unless explicitly waived.
- **Security and privacy** _(Security)_: PocketPal is an **on-device app, not a server** — review against the mobile threat model, not a server perimeter. The real trust boundaries are: (a) model-generated content reaching render/execution surfaces (markdown/HTML/WebView/JS, tool-call/JSON parsing); (b) external content entering the app (downloaded GGUF models, web-search/internet results, deep links / App Intents / Shortcuts params, PalsHub rows); (c) on-device data at rest and in logs (chat history, API keys, server/auth tokens, crash reports); (d) the native bridge and capability allowlist (Pals-as-apps WebView bridge); (e) debug/E2E hooks reachable in production builds. A security finding on a trust-boundary diff must name an untrusted **source** and the **sink** it reaches unsanitized.
- **Data and migration safety** _(Data, Security)_: schema changes, persisted state, cache invalidation, backward compatibility, rollback.
- **Performance and resources** _(Perf, Mobile Platform)_: hot paths, unbounded work, repeated I/O, memory, storage, startup time, battery. PocketPal runs LLMs on phones; any change that could plausibly increase RAM/heap, model load time, bundle size, startup, or battery use must be flagged at `CONCERN` minimum.
- **UX and accessibility** _(UX/A11y)_: user-visible flows, honest states, error messages, accessibility, copy consistency, lost affordances.
- **Platform and native verification** _(Mobile Platform)_: `NATIVE_CHANGES=YES` requires `pod install`, an iOS build, and an Android build before approval. Also consider cross-OS/chip compatibility — iOS version floor, Android API min, arm64 vs simulator, llama.rn backend variants, on-device vs emulator.

## PocketPal-Specific Checks

- **Localization**: new UI strings must not be hardcoded. Active language registry: `src/locales/index.ts`. Only `en.json` is edited directly; the rest live on Weblate.
- **Testing patterns**: project test utilities and centralized mocks; no inline store mocks or direct observable mutation outside accepted patterns.
- **MobX patterns**: `observer`, `makeAutoObservable`, `runInAction` for async updates, computed getters, existing singleton/export conventions.
- **Components**: preserve folder structure, TypeScript props, theming, and `testID` patterns for interactive elements.
- **Commits**: commitlint allows `feat`, `fix`, `docs`, `chore` with `type(scope): subject`.

## Severity

- `BLOCKER`: incorrect behavior, broken contract, exploitable security issue, unsafe data change, missing mandatory verification, missing critical test.
- `CONCERN`: real issue that should not merge yet but is below blocker.
- `SUGGESTION`: legitimate improvement, deferrable.

`NOTHING_FOUND` is a valid outcome. Do not invent issues.

## Confidence

Every finding carries a `confidence` separate from its severity:

- `high` — proven by code, contract, or repro you cite.
- `med` — strong inference, not fully proven.
- `low` — plausible but speculative.

Severity is impact-if-real; confidence is likelihood-it's-real. Never collapse the two — a `low`-confidence `BLOCKER` is exactly the finding the refutation step exists to test.

## Adversarial verification

Before any `BLOCKER` or `CONCERN` is accepted into the final review, attempt to **refute** it: argue from the code and contracts why it might NOT be a real defect — wrong, already handled elsewhere, unreachable, or masked by an invariant. The refutation must be performed by someone other than the role reviewer that produced the finding (the lead synthesizer, or a dedicated skeptic subreview for the highest-stakes findings).

Record the outcome on the finding:

- `refutation: stands` — survived the attempt; it ships.
- `refutation: withdrawn — <reason>` — drop or downgrade it, with the reason.

A finding that cannot survive a genuine refutation attempt must not ship as a `BLOCKER`/`CONCERN`. This is false-positive suppression with an audit trail, not silent dropping.

## Evidence Rules

1. Cite real file paths and line numbers; read the file before citing it.
2. Quote a small relevant snippet when it helps.
3. Missing-test findings must cite the production code that lacks coverage.
4. Mark inferences as inferences. Mark unrun checks as unrun.

## Verdict

- `APPROVE` — no unresolved blockers or concerns, verification complete or N/A, residual risk acceptable.
- `REQUEST_CHANGES` — any blocker, serious unresolved concern, missing mandatory verification, or unproven acceptance criteria.
- `ESCALATE` — needs human product/architecture judgment, or the diff is too ambiguous to review safely.

**Verification gate (mechanical).** `APPROVE` is invalid if any required verification entry is `NOT_RUN` — downgrade to `REQUEST_CHANGES` or `ESCALATE`. `review_complete: yes` requires lint, typecheck, and tests at `PASS`/`N/A`, plus the native builds at `PASS` when `NATIVE_CHANGES=YES`. Never claim a complete approval over unrun checks.

## Human-Facing Output

Open with review metadata:

```markdown
verdict: APPROVE | REQUEST_CHANGES | ESCALATE risk_level: low | medium | high review_complete: yes | no role_subreviews: COMPLETED | BLOCKED | NOT_REQUIRED
```

Then include a per-lens summary table:

```markdown
| Lens                  | Status              | Issues |
| --------------------- | ------------------- | ------ |
| Correctness           | PASS / ISSUES       | n      |
| Architecture          | PASS / ISSUES       | n      |
| Maintainability       | PASS / ISSUES       | n      |
| Tests                 | PASS / ISSUES       | n      |
| Security              | PASS / ISSUES / N/A | n      |
| Data / Migration      | PASS / ISSUES / N/A | n      |
| Performance/Resources | PASS / ISSUES / N/A | n      |
| UX / Accessibility    | PASS / ISSUES / N/A | n      |
| Platform / Native     | PASS / ISSUES / N/A | n      |
```

Then: findings ordered by severity (each stating its `confidence` and `refutation` outcome), open questions, verification status, residual risks, decision summary.

If nothing was found, say so explicitly and call out remaining verification gaps.

The final review must be team-shareable (including the necessary details the team need to fix). Deduplicate role findings, normalize severity, and include enough detail for the team to act without asking "where?". Every `ISSUES` lens row must have at least one matching finding.

## Headless Output

Deterministic, compact, no prose:

```markdown
verdict: APPROVE | REQUEST_CHANGES | ESCALATE risk_level: low | medium | high review_complete: yes | no role_subreviews: COMPLETED|BLOCKED|NOT_REQUIRED

missing_context: [item, ...] # or []

verification:

- { name: lint, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: typecheck, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: tests, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: native, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }

lens_summary: correctness: PASS|ISSUES architecture: PASS|ISSUES maintainability: PASS|ISSUES tests: PASS|ISSUES security: PASS|ISSUES|N/A data_migration: PASS|ISSUES|N/A performance: PASS|ISSUES|N/A ux_accessibility: PASS|ISSUES|N/A platform_native: PASS|ISSUES|N/A

counts: { blocker: 0, concern: 0, suggestion: 0 }

findings:

- id: R1 severity: BLOCKER|CONCERN|SUGGESTION confidence: high|med|low refutation: stands|withdrawn lens: correctness|architecture|...|platform_native title: short title path: relative/path.ts line: 123 impact: one sentence evidence: short quoted code fix: one sentence

manual_checks: [step, ...] # or [] residual_risks: [item, ...] # or []
```

`risk_level: high` when native, persistence, security, or multi-surface changes ship with incomplete verification.
