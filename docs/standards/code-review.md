# PocketPal Code Review Standard

The contract for PocketPal review workflows: lenses, severity, evidence, and
output. Tool- and role-specific reviewers import this file and add their own
operating bits on top.

## Ownership

This file is the canonical review policy. It owns review goals, lenses, roles,
severity, evidence rules, high-risk classification, and output contracts.

It does not own target setup, worktree creation, GitHub commands, reviewer
execution, or final synthesis mechanics. Skills and agents may add operating
details, but they must not redefine or weaken this standard.

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

Role worldview and file-focus guidance belong to the named role reviewers. This
standard owns only the required role IDs and the contract they must follow.

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

Each role reviewer returns only concrete findings or `NOTHING_FOUND`. Map helper
roles produce orientation notes for `review-map.md`, not final review findings.

## Working Method

For each lens below, apply the listed concerns as the floor and surface anything
else a PocketPal reviewer would notice in this diff. Findings stay grouped by
lens to match the output table.

Mark a lens N/A only if it is clearly not relevant to the diff.

For large or high-risk reviews, read-only role subreviews are required before a
complete final review. A review is high-risk when any of these conditions apply:
- changed files > 10
- native dependency or native code changes
- persistence, migration, or schema changes
- security/trust-boundary changes
- model/tool execution changes
- multi-surface changes
- user explicitly asks for a robust/deep review

Use the required high-risk role reviewers listed above. Each role returns only
concrete findings with severity, file:line, impact, evidence, and fix, or
`NOTHING_FOUND`.

If high-risk role subreviews were required but not completed, the final review
must be marked incomplete. It may summarize found issues, but it must not
claim a complete approval/request-changes review.

The `local-invariants` role reviews changed lines for small contract breaks
defined by that reviewer.

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

Open with review metadata:

```markdown
verdict: APPROVE | REQUEST_CHANGES | ESCALATE
risk_level: low | medium | high
review_complete: yes | no
role_subreviews: COMPLETED | BLOCKED | NOT_REQUIRED
```

Then include a per-lens summary table:

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

The final review must be team-shareable (including the necessary details the team need to fix).
Deduplicate role findings, normalize severity, and include enough detail for the team to act without asking "where?".
Every `ISSUES` lens row must have at least one matching finding.

## Headless Output

Deterministic, compact, no prose:

```markdown
verdict: APPROVE | REQUEST_CHANGES | ESCALATE
risk_level: low | medium | high
review_complete: yes | no
role_subreviews: COMPLETED|BLOCKED|NOT_REQUIRED

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
