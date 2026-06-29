---
name: review-pr
description: Review a PocketPal pull request, branch, or review worktree. Use for external PR reviews, requested code-review passes, risk classification, role-subreview orchestration, review-map creation, verification, and final review output.
argument-hint: "<pr-number | branch-ref | worktree-path>"
---

# Review PR

Review the requested PocketPal change as a code-review workflow, not as implementation work.

The user may invoke this skill with a PR number, branch ref, or worktree path:

```text
/review-pr <pr-number | branch-ref | worktree-path>
```

## Operating Contract

Use this skill as the orchestration layer.

Read `docs/standards/code-review.md` before making review judgments.

Use the PocketPal role reviewers when role subreviews are required.

Do not mutate `repos/pocketpal-ai/`, this is read only, instead use worktrees.

Do not produce a complete high-risk final review unless required role subreviews completed.

## Inputs To Resolve

Resolve these before classification:

- Target identifier: PR number, branch ref, or worktree path.
- Review ID: `PR-<number>` for PRs, or a stable name derived from the branch/worktree.
- Worktree path under `worktrees/`.
- Base ref and head ref.
- PR metadata, changed filenames, diff, linked issue, and acceptance criteria when available.
- Existing review artifact folder for the current round, or the next new round folder.

If essential target information is missing and cannot be found locally or from GitHub, stop and ask for the missing target.

## Worktree Setup

For PR targets, fetch the PR branch from `repos/pocketpal-ai`, then create or reuse a dedicated review worktree from that fetched ref.

```bash
MAIN_REPO="./repos/pocketpal-ai"
PR_NUMBER="{PR_NUMBER}"
REVIEW_ID="PR-${PR_NUMBER}"
WORKTREE_PATH="./worktrees/${REVIEW_ID}"

cd "${MAIN_REPO}"
PR_INFO=$(gh pr view ${PR_NUMBER} --json title,body,author,files,additions,deletions,commits,url,headRefName)
git fetch origin "pull/${PR_NUMBER}/head:pr-${PR_NUMBER}"
cd - >/dev/null

[ -d "${WORKTREE_PATH}" ] || ./tools/create-worktree.sh "${REVIEW_ID}" --branch "pr-${PR_NUMBER}" --ref "pr-${PR_NUMBER}"
./tools/sync-worktree-config.sh "${WORKTREE_PATH}"
cd "${WORKTREE_PATH}"
```

If an expected worktree path is missing but `git worktree list` contains a stale entry, do not remove it with raw git or filesystem commands.

Create or reuse an allowed task or PR worktree according to the loaded repo instructions, or report the blocker.

## Context To Read

Read only the context that applies to the review target.

- `context/pocketpal-overview.md` for product and domain orientation.
- `docs/standards/architecture.md` for app boundaries, runtime surfaces, and data-flow orientation.
- `context/patterns.md` for local implementation and test conventions.
- `docs/workflows/visual-capture.md` when UI screenshots or visual evidence are relevant.

## Review Artifact Folder

Write durable artifacts in the following folder:

```text
workflows/reviews/<TARGET_ID>/round-<N>/
```

Determine `N` as `(highest existing round-<k> dir for this TARGET_ID) + 1`, unless explicitly continuing an in-progress round. The max-2-rounds cap and escalation are owned by the caller (the `/start-task` delivery loop). A standalone `/review-pr` run performs a single round, states its round number, and does not enforce the cap itself.

For a complete high-risk review, these files are required:

- `review-map.md`
- `architect.md`
- `qa.md`
- `security.md`
- `performance.md`
- `mobile.md`
- `data.md`
- `ux.md`
- `local-invariants.md`
- `verification.md`
- `final.md`

If a required role artifact is missing, the final review must say `review_complete: no` and `role_subreviews: BLOCKED`.

## Review Map

Create `review-map.md` before role review.

The map is orientation for reviewers, not the final verdict.

Include:

- target metadata: target, base/head refs, worktree path, story/PR links.
- changed file groups.
- runtime and data-flow notes.
- requirements and acceptance-criteria coverage.
- risk classification.
- required role reviewers.
- suggested file focus per role.
- verification required by policy.

For large or ambiguous reviews, use these map helper agents before writing the final map:

- `pocketpal-review-map-architect`
- `pocketpal-flow-analyst`
- `pocketpal-requirements-mapper`

Summarize helper output into `review-map.md`.

Do not treat helper output as final review findings.

## Risk Classification

Classify the review as high risk when any condition is true:

- changed files > 10.
- native dependency or native code changes.
- persistence, migration, or schema changes.
- security or trust-boundary changes.
- model, tool, or execution changes.
- multi-surface changes.
- the user explicitly asks for a robust, deep, or role-based review.

For high-risk reviews, run all required role subreviews. Role agents:

- `pocketpal-architect-reviewer`
- `pocketpal-qa-reviewer`
- `pocketpal-security-reviewer`
- `pocketpal-performance-reviewer`
- `pocketpal-mobile-reviewer`
- `pocketpal-data-reviewer`
- `pocketpal-ux-reviewer`
- `pocketpal-local-invariants-reviewer`

## Subreview Gate

This gate is mandatory for high-risk reviews.

If role subreviews are required, run read-only role subreviews before issuing the final review.

If required role reviewers cannot run, do not produce a complete final review.

Mark the output as `review_complete: no` and `role_subreviews: BLOCKED`.

Use this delegation shape:

```text
Use <role-agent-name>.
Target: <target>
Worktree: <review worktree>
Base ref: <base SHA/ref>
Head ref: <head SHA/ref>
Review map: workflows/reviews/<TARGET_ID>/round-<N>/review-map.md
Output artifact: workflows/reviews/<TARGET_ID>/round-<N>/<role>.md

Return only concrete findings with severity, lens, file:line, impact, evidence, and fix, or NOTHING_FOUND.
Write the result to the output artifact when file writes are available.
Do not modify source files or review inputs.
```

Role reviewers may write role artifacts directly.

If a role reviewer returns output without writing the artifact, write that output verbatim to the required artifact path before final review synthesis.

Use the role artifacts to produce the final review.

Each role artifact must use this shape:

```markdown
# <Role> Review: <TARGET_ID> Round <N>

status: FINDINGS | NOTHING_FOUND

## Findings

### <ID>: <Title>

severity: BLOCKER | CONCERN | SUGGESTION confidence: high | med | low lens: Correctness | Architecture | Maintainability | Tests | Security | Data / Migration | Performance/Resources | UX / Accessibility | Platform / Native path: relative/path.ts line: 123 impact: One sentence. evidence: Short quote or concrete code reference. fix: One sentence.
```

## Verification

Run feasible verification from the app worktree.

Before JS tests, ensure dependencies exist:

- run `yarn install` in the app worktree when `node_modules` or `jest` is missing.
- run `yarn install` in `e2e/` before E2E commands.

Native dependency or native code changes require:

- `pod install`.
- iOS build.
- Android build.

Missing required native verification is a blocking review issue unless the user explicitly changes the requirement.

Write verification status to `verification.md`.

## Final Synthesis

Read all role artifacts and `verification.md`, then write `final.md`.

Use `final.md` as the team-facing review response and synthesis record. It should contain the final normalized findings, role subreview status, verification status, residual risks, open questions, and review-completeness fields in the standard output shape.

Before final output:

- Confirm every required role artifact exists, or mark the review incomplete.
- Merge duplicate findings.
- Refute each BLOCKER/CONCERN (standard's Adversarial verification) as a reviewer independent of the one that raised it; record `refutation: stands` or drop/downgrade with `refutation: withdrawn — <reason>`.
- Apply the mechanical verification gate: no `APPROVE` / `review_complete: yes` over `NOT_RUN` checks.
- Include short synthesis notes only when they matter, such as unavailable reviewers, merged duplicates, missing role artifacts, or verification gaps.

## Final Response

Write `final.md` using the standard output shape from `docs/standards/code-review.md`.

Respond from `final.md`.

The final response must be team-shareable.

Include:

- `role_subreviews: COMPLETED | BLOCKED | NOT_REQUIRED`.
- `review_complete: no` when required role subreviews did not complete.
- findings grouped by severity.
- verification status.
- residual risks and open questions.

For a complete high-risk review, `role_subreviews` must be `COMPLETED`.
