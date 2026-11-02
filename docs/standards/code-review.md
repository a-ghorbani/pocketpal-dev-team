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
- the story's `evidence.md` (what was proven, with receipts), `decisions.md`, and WHAT §8 (what was decided). Re-raise a decided item only with new evidence that it is wrong, and name that evidence.
- the touched flow docs: `context/architecture/<flow>.md` named in the story's `ARCHITECTURE_DOCS`, else the flows whose README index rows cover the changed files. A behaviour change a flow doc describes, with no matching update to that doc in the same round (or a line for unlanded code without `(pending #<PR>)`), is an Architecture finding on a pipeline PR (a story exists); on an external PR, note it in `final.md` for the orchestrator and leave it out of the published review.
- `context/patterns.md`
- project-local standards referenced by the change
- existing CI or implementation verification output

If critical context is missing, state it explicitly.

## Review Principles

1. Follow the risk first.
2. Read beyond the diff — callers, callees, surrounding patterns. In an observable-store architecture a store-only diff can move every screen that reads the store, so assign reviewers by the behaviour a change moves, not by the files it touches.
3. Cite proof — code, contracts, tests, concrete failure modes.
4. Skip minor style churn unless it affects safety, readability, or consistency.
5. Separate confirmed defects from unproven verification.
6. Review for the next engineer too — call out hidden invariants and future traps.
7. Prefer the simpler fix and don't grow the scope. Close a finding with the smallest change that handles it correctly; prefer an existing state or path when it does the job. Hardening, defence in depth, or an improvement whose fix costs more than the risk it removes is a SUGGESTION; a real, reachable defect (wrong behaviour, data loss, a reachable security sink) keeps its severity whatever the fix costs (see Adversarial verification).
8. Code with no reader in the change, no trace to the request, or guarding a path nothing reaches is a finding too (Architecture lens). Removing it is a valid fix.

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

- `pocketpal-review-map-architect`
- `pocketpal-flow-analyst`
- `pocketpal-requirements-mapper`

When no role subreviews are required, `pocketpal-code-reviewer` applies every lens.

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

Use the required high-risk role reviewers listed above. Each role returns only concrete findings with severity, lens, confidence, file:line, impact, evidence, and fix, or `NOTHING_FOUND`.

If high-risk role subreviews were required but not completed, the final review must be marked incomplete. It may summarize found issues, but it must not claim a complete approval/request-changes review.

The `local-invariants` role reviews changed lines for small contract breaks defined by that reviewer.

## Required Lenses

- **Correctness** _(QA)_: broken behavior, bad assumptions, null handling, state mistakes, async races, retries, cancellation, stale state, error paths.
- **Architecture and boundaries** _(Architect)_: coupling, layering, public contracts, hidden dependencies, over-engineering.
- **Maintainability and readability** _(Architect)_: duplication, naming, fragile logic, magic constants, hard-to-test design. (Owned by the architect role in high-risk reviews; `pocketpal-code-reviewer` applies it when no role subreviews are required.)
- **Comment load** _(Architect; part of Maintainability, reported under that lens)_: over-commenting is a recurring defect in this repo, so review it explicitly rather than waiting to be asked. Classify every questionable comment with the four-case test under "Comments" below. A finding **must name which case**: "too many comments" is not actionable, "this is case 2 — the comment exists because the function does three things" is. Volume itself is evidence: a diff that needs heavy commentary is reporting a clarity or design problem, and the remedy is the code, not better prose. Also flag task narrative in source (naming the bug just fixed, round numbers, plan-step restatements) — that rots into archaeology.
- **Tests and verification** _(QA)_: missing coverage, weak assertions, mocks that hide contracts, skipped tests, manual validation gaps. **Coverage floor: 60%** (statements, branches, functions, lines) for the changed surface; below it is a `BLOCKER` unless explicitly waived.
- **Security and privacy** _(Security)_: PocketPal is an **on-device app, not a server** — review against the mobile threat model, not a server perimeter. The real trust boundaries are: (a) model-generated content reaching render/execution surfaces (markdown/HTML/WebView/JS, tool-call/JSON parsing); (b) external content entering the app (downloaded GGUF models, web-search/internet results, deep links / App Intents / Shortcuts params, PalsHub rows); (c) on-device data at rest and in logs (chat history, API keys, server/auth tokens, crash reports); (d) the native bridge and capability allowlist (Pals-as-apps WebView bridge); (e) debug/E2E hooks reachable in production builds. A security finding on a trust-boundary diff must name an untrusted **source** and the **sink** it reaches unsanitized, and show the sink is **reachable on `main`** with that input (the call path, `file:line` per hop). A guard on a path no attacker-controlled input reaches is defence in depth: at most a SUGGESTION, whatever the theoretical impact.
- **Data and migration safety** _(Data, Security)_: schema changes, persisted state, cache invalidation, backward compatibility, rollback.
- **Performance and resources** _(Perf, Mobile Platform)_: hot paths, unbounded work, repeated I/O, memory, storage, startup time, battery. PocketPal runs LLMs on phones; any change that could plausibly increase RAM/heap, model load time, bundle size, startup, or battery use must be flagged at `CONCERN` minimum.
- **UX and accessibility** _(UX/A11y)_: user-visible flows, honest states, error messages, accessibility, copy consistency, lost affordances.
- **Platform and native verification** _(Mobile Platform)_: `NATIVE_CHANGES=YES` requires `pod install`, an iOS build, and an Android build before approval. Also consider cross-OS/chip compatibility — iOS version floor, Android API min, arm64 vs simulator, llama.rn backend variants, on-device vs emulator.

## Comments

A comment is almost always a **symptom**, not a deliverable. Work out which of these it is, and fix *that*:

1. **Bad comment**: it states what the code already says, narrates the change, or records how the answer was reached. → **Delete it.** Names and types already carry it.
2. **Bad code**: prose is needed because the code is not self-explanatory. → **Fix the code.** Rename, extract, drop the cleverness.
3. **Bad design**: the comment justifies an odd approach. → **Fix the design**, or when the oddity is genuinely forced, put the reasoning in `context/architecture/`, not above the call site.
4. **Genuine "why"**: a non-recoverable fact the code cannot show, such as an external constraint, non-obvious platform behaviour, or a trap that looks like a bug and isn't. → **Keep it.** This is the rare case.

The test: *if this line is deleted, what does a competent reader who knows the codebase but not this task lose?* Nothing means case 1. "They would misread the code" means case 2 or 3, so the code should change. "They would repeat a mistake the code cannot warn them about" is case 4.

Nothing about the task belongs in source: no "we hit X", no round numbers, no story anchors. Source describes the current state; the reasoning lives in the story and the architecture docs.

## PocketPal-Specific Checks

- **Localization**: new UI strings must not be hardcoded. Active language registry: `src/locales/index.ts`. Only `en.json` is edited directly; the rest live on Weblate. Editing a non-English locale file is a BLOCKER.
- **Testing patterns**: project test utilities and centralized mocks; no inline store mocks or direct observable mutation outside accepted patterns.
- **MobX patterns**: `observer`, `makeAutoObservable`, `runInAction` for async updates, computed getters, existing singleton/export conventions.
- **Components**: preserve folder structure, TypeScript props, theming, and `testID` patterns for interactive elements.
- **Commits**: commitlint allows `feat`, `fix`, `docs`, `chore` with `type(scope): subject`.
- **Remote-server (llama-server) claims**: it returns `200` for unknown body keys, so a forwarded
  parameter can ship and silently do nothing — verify against what the server reports it applied,
  not against the request succeeding. Only a `404` is a fact about the build (`401` is credentials,
  `400` this request, `500` this moment); none of the others may be cached as a capability. Every
  wire fact carries the upstream build it was measured on. Wire fixtures are verbatim captures,
  redacted for host-identifying paths but never reordered — some fields are positional.

## Severity

- `BLOCKER`: incorrect behavior, broken contract, exploitable security issue, unsafe data change, missing mandatory verification, missing critical test.
- `CONCERN`: real issue that should not merge yet but is below blocker.
- `SUGGESTION`: legitimate improvement, deferrable to the PR's follow-ups (the `Follow-ups` list of the published review); never triggers a fix round.

`NOTHING_FOUND` is a valid outcome. Do not invent issues.

## Confidence

Every finding carries a `confidence` separate from its severity:

- `high` — proven by code, contract, or repro you cite.
- `med` — strong inference, not fully proven.
- `low` — plausible but speculative.

Severity is impact-if-real; confidence is likelihood-it's-real. Never collapse the two — a `low`-confidence `BLOCKER` is exactly the finding the refutation step exists to test.

## Adversarial verification

Before any `BLOCKER` or `CONCERN` is accepted into the final review, attempt to **refute** it on two questions:

1. **Is it real?** Argue from the code and contracts why it might NOT be a defect — wrong, already handled elsewhere, unreachable on `main`, masked by an invariant, or already decided in `decisions.md` / WHAT §8.
2. **Is the fix worth it?** For hardening and improvements only: name the fix's cost (new states, guards, tests, the surfaces it touches) against the risk it removes; a fix bigger than its risk makes it a SUGGESTION.

The refutation must be performed by someone other than the role reviewer that produced the finding (the lead synthesizer, or a dedicated skeptic subreview for the highest-stakes findings).

Record the outcome on the finding:

- `refutation: stands` — survived the attempt; it ships.
- `refutation: withdrawn — <reason>` — drop or downgrade it, with the reason. The delivery orchestrator copies these into the story's `decisions.md`; reviewers don't write story files.

A finding that cannot survive a genuine refutation attempt must not ship as a `BLOCKER`/`CONCERN`. This is false-positive suppression with an audit trail, not silent dropping.

## Evidence Rules

1. Cite real file paths and line numbers; read the file before citing it.
2. Quote a small relevant snippet when it helps.
3. Missing-test findings must cite the production code that lacks coverage.
4. Mark inferences as inferences. Mark unrun checks as unrun.
5. Name the revision reviewed. A review is a claim about a specific tree, and a record without one
   does not look incomplete — it looks like a review.
6. For fixture-backed findings, check the fixture's provenance, not just its presence.

## Verdict

- `APPROVE` — no unresolved blockers or concerns, verification complete or N/A, residual risk acceptable. An `APPROVE` that carries only suggestions ends the review.
- `REQUEST_CHANGES` — any blocker, serious unresolved concern, missing mandatory verification, or unproven acceptance criteria.
- `ESCALATE` — needs human product/architecture judgment, or the diff is too ambiguous to review safely.

**Verification gate (mechanical).** `APPROVE` is invalid if any required verification entry is `NOT_RUN` — downgrade to `REQUEST_CHANGES` or `ESCALATE`. `review_complete: yes` requires lint, typecheck, and tests at `PASS`/`N/A`, plus the native builds at `PASS` when `NATIVE_CHANGES=YES`. Never claim a complete approval over unrun checks.

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
verdict: APPROVE | REQUEST_CHANGES | ESCALATE
risk_level: low | medium | high
review_complete: yes | no
role_subreviews: COMPLETED|BLOCKED|NOT_REQUIRED

missing_context: [item, ...] # or []

verification:

- { name: lint, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: typecheck, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: tests, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: native, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }

lens_summary:
  correctness: PASS|ISSUES
  architecture: PASS|ISSUES
  maintainability: PASS|ISSUES
  tests: PASS|ISSUES
  security: PASS|ISSUES|N/A
  data_migration: PASS|ISSUES|N/A
  performance: PASS|ISSUES|N/A
  ux_accessibility: PASS|ISSUES|N/A
  platform_native: PASS|ISSUES|N/A

counts: { blocker: 0, concern: 0, suggestion: 0 }

findings:

- id: R1
  severity: BLOCKER|CONCERN|SUGGESTION
  lens: correctness|architecture|...|platform_native
  confidence: high|med|low
  refutation: stands|withdrawn
  title: short title
  path: relative/path.ts
  line: 123
  impact: one sentence
  evidence: short quoted code
  fix: one sentence

manual_checks: [step, ...]   # or []
residual_risks: [item, ...]  # or []
```

`risk_level: high` when native, persistence, security, or multi-surface changes ship with incomplete verification.
