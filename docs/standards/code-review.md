# PocketPal Code Review Standard

The contract for PocketPal review workflows: lenses, severity, evidence, and
output. Tool- and role-specific reviewers import this file and add their own
operating bits on top.

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

## Roles

A strong review applies multiple expert perspectives. Adopt these personas
as the lenses below call for them:

- **Architect** — software architect for mobile/RN apps; thinks in contracts,
  layering, dependency direction.
- **QA** — test engineer; thinks in edge cases, coverage gaps, contract
  assumptions.
- **Security** — application security engineer; thinks in trust boundaries
  and attacker model.
- **Perf** — mobile performance engineer who has shipped React Native apps
  with on-device LLMs.
- **Mobile Platform** — iOS/Android platform engineer; thinks in version
  floors, ABI, JSI bridges, native dependencies.
- **UX/A11y** — designer plus accessibility specialist.
- **Domain** — peer engineer who will maintain this code.

## Working Method

For each lens below, mentally adopt the named role(s) *before* reading the
code. Apply the listed concerns as the **floor** — and surface anything else
that role would notice in this diff, even if it is not in the bullet list.
Findings stay grouped by lens (to match the output table), but the
perspective behind each finding is the role's.

Mark a lens N/A only if it is clearly not relevant to the diff.

## Required Lenses

- **Correctness** *(Domain, QA)*: broken behavior, bad assumptions, null
  handling, state mistakes, async races, retries, cancellation, stale state,
  error paths.
- **Architecture and boundaries** *(Architect)*: coupling, layering, public
  contracts, hidden dependencies, over-engineering.
- **Maintainability and readability** *(Domain)*: duplication, naming,
  fragile logic, magic constants, hard-to-test design.
- **Tests and verification** *(QA)*: missing coverage, weak assertions, mocks
  that hide contracts, skipped tests, manual validation gaps.
- **Security and privacy** *(Security)*: secrets, unsafe logging, trust
  boundaries, input validation, injection, path risks, risky dependencies.
- **Data and migration safety** *(Domain, Security)*: schema changes,
  persisted state, cache invalidation, backward compatibility, rollback.
- **Performance and resources** *(Perf, Mobile Platform)*: hot paths,
  unbounded work, repeated I/O, memory, storage, startup time, battery.
  PocketPal runs LLMs on phones; any change that could plausibly increase
  RAM/heap, model load time, bundle size, startup, or battery use must be
  flagged at `CONCERN` minimum.
- **UX and accessibility** *(UX/A11y)*: user-visible flows, honest states,
  error messages, accessibility, copy consistency, lost affordances.
- **Platform and native verification** *(Mobile Platform)*: `NATIVE_CHANGES=YES`
  requires `pod install`, an iOS build, and an Android build before approval.
  Also consider cross-OS/chip compatibility — iOS version floor, Android API
  min, arm64 vs simulator, llama.rn backend variants, on-device vs emulator.

## PocketPal-Specific Checks

- **Localization**: new UI strings must not be hardcoded. Active language
  registry: `src/locales/index.ts`. Only `en.json` is edited directly; the
  rest live on Weblate.
- **Testing patterns**: project test utilities and centralized mocks; no
  inline store mocks or direct observable mutation outside accepted patterns.
- **MobX patterns**: `observer`, `makeAutoObservable`, `runInAction` for async
  updates, computed getters, existing singleton/export conventions.
- **Components**: preserve folder structure, TypeScript props, theming, and
  `testID` patterns for interactive elements.
- **Commits**: commitlint allows `feat`, `fix`, `docs`, `chore` with
  `type(scope): subject`.

## Severity

- `BLOCKER`: incorrect behavior, broken contract, exploitable security issue,
  unsafe data change, missing mandatory verification, missing critical test.
- `CONCERN`: real issue that should not merge yet but is below blocker.
- `SUGGESTION`: legitimate improvement, deferrable.

`NOTHING_FOUND` is a valid outcome. Do not invent issues.

## Evidence Rules

1. Cite real file paths and line numbers; read the file before citing it.
2. Quote a small relevant snippet when it helps.
3. Missing-test findings must cite the production code that lacks coverage.
4. Mark inferences as inferences. Mark unrun checks as unrun.

## Verdict

- `APPROVE` — no unresolved blockers or concerns, verification complete or
  N/A, residual risk acceptable.
- `REQUEST_CHANGES` — any blocker, serious unresolved concern, missing
  mandatory verification, or unproven acceptance criteria.
- `ESCALATE` — needs human product/architecture judgment, or the diff is too
  ambiguous to review safely.

## Human-Facing Output

Open with a per-lens summary table:

```markdown
| Lens                  | Status              | Issues |
|-----------------------|---------------------|--------|
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

Then: findings ordered by severity, open questions, verification status,
residual risks, decision summary.

If nothing was found, say so explicitly and call out remaining verification
gaps.

## Headless Output

Deterministic, compact, no prose:

```markdown
verdict: APPROVE | REQUEST_CHANGES | ESCALATE
risk_level: low | medium | high
review_complete: yes | no

missing_context: [item, ...]   # or []

verification:
  - { name: lint,      status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
  - { name: typecheck, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
  - { name: tests,     status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
  - { name: native,    status: PASS|FAIL|NOT_RUN|N/A, notes: ... }

lens_summary:
  correctness:      PASS|ISSUES
  architecture:     PASS|ISSUES
  maintainability:  PASS|ISSUES
  tests:            PASS|ISSUES
  security:         PASS|ISSUES|N/A
  data_migration:   PASS|ISSUES|N/A
  performance:      PASS|ISSUES|N/A
  ux_accessibility: PASS|ISSUES|N/A
  platform_native:  PASS|ISSUES|N/A

counts: { blocker: 0, concern: 0, suggestion: 0 }

findings:
  - id: R1
    severity: BLOCKER|CONCERN|SUGGESTION
    lens: correctness|architecture|...|platform_native
    title: short title
    path: relative/path.ts
    line: 123
    impact: one sentence
    evidence: short quoted code
    fix: one sentence

manual_checks: [step, ...]    # or []
residual_risks: [item, ...]   # or []
```

`risk_level: high` when native, persistence, security, or multi-surface
changes ship with incomplete verification.
