---
name: review-pr
description: Review a PocketPal pull request, branch, or review worktree. Use for external PR reviews, requested code-review passes, risk classification, review-map creation, per-lens reviewer dispatch, verification, and final review output.
argument-hint: "<pr-number | branch-ref | worktree-path>"
---

# Review PR

Orchestrate a code review (not implementation) of a PR number, branch ref, or worktree path: `/review-pr <pr-number | branch-ref | worktree-path>`.

`docs/standards/code-review.md` owns risk, severity, confidence, refutation, verdict, and output; `docs/standards/review-lenses.md` the lenses. Read both before judging. The lead maps, dispatches `pocketpal-reviewer` per lens set, and synthesizes. `repos/pocketpal-ai/` is read-only: use worktrees.

## Inputs To Resolve

Before classification: target (PR number, branch ref, or worktree path); review ID (`PR-<number>`, or a stable name from the branch/worktree); worktree path under `worktrees/`; base and head refs; PR metadata, changed files, diff, linked issue, and acceptance criteria when available; the current round's folder or the next new one.

If essential target information can't be found locally or on GitHub, stop and ask for it.

## Readiness

For a PR produced by this pipeline (a story exists for its branch), run `tools/pr-gates.sh <PR>` first. `ci PEND` (exit 4) means wait and rerun. Any gate FAIL (exit 1: `ci` or `hygiene`) is `NOT_READY`: reply `NOT_READY` with the gate output and stop without creating a round folder. A standalone review the user asked for (an external PR, a branch) proceeds and records the gate output in `verification.md`.

## Worktree Setup

For PR targets, fetch the PR head into `refs/remotes/pr/<n>` (never into `pr-<n>`: that branch may be checked out in the worktree, and git refuses), then create or reuse the review worktree at that head.

```bash
ROOT="$(git rev-parse --show-toplevel)"
MAIN_REPO="$ROOT/repos/pocketpal-ai"
PR_NUMBER="{PR_NUMBER}"
REVIEW_ID="PR-${PR_NUMBER}"
WORKTREE_PATH="$ROOT/worktrees/${REVIEW_ID}"
PR_REF="refs/remotes/pr/${PR_NUMBER}"

PR_INFO=$(gh pr view "${PR_NUMBER}" --repo a-ghorbani/pocketpal-ai --json title,body,author,files,additions,deletions,commits,url,headRefName,headRefOid)
HEAD_SHA=$(jq -r .headRefOid <<<"$PR_INFO")
git -C "$MAIN_REPO" fetch origin "+pull/${PR_NUMBER}/head:${PR_REF}"

[ -d "${WORKTREE_PATH}" ] || "$ROOT/tools/create-worktree.sh" "${REVIEW_ID}" --branch "pr-${PR_NUMBER}" --ref "${PR_REF}"
"$ROOT/tools/sync-worktree-config.sh" "${WORKTREE_PATH}"
```

The worktree is also the PR-fix worktree, so move it to the PR head by fast-forward only: stop and report when it has a dirty tree or commits not on `${PR_REF}`; otherwise `git -C "${WORKTREE_PATH}" merge --ff-only "${PR_REF}"`. Confirm `git -C "${WORKTREE_PATH}" rev-parse HEAD` equals `HEAD_SHA`, and record that SHA as the reviewed revision in `review-map.md`.

If an expected worktree path is missing but `git worktree list` has a stale entry, never remove it with raw git or filesystem commands. Create or reuse an allowed worktree per repo instructions, or report the blocker.

## Context To Read

Read only what applies:

- `context/pocketpal-overview.md` (product, domain), `docs/standards/architecture.md` (boundaries, runtime surfaces, data flow), `context/patterns.md` (implementation and test conventions).
- `docs/workflows/visual-capture.md` when UI screenshots or visual evidence matter.
- The story's `evidence.md`, `decisions.md`, and `what.md` for pipeline changes; pass their paths to every reviewer (use: standard's Canonical Inputs).
- The touched flow docs (`context/architecture/<flow>.md`: the story's `ARCHITECTURE_DOCS`, else the README index rows matching the changed files), passed to the reviewer holding the Architecture lens.
- Lessons for the surfaces the diff touches (`tools/context search <terms>`), passed to the reviewers whose lenses they concern.
- Earlier rounds' `final.md` for this target: report a finding already fixed once and now back as a design problem, not another fix.

## Review Artifact Folder

Write artifacts to `workflows/reviews/<TARGET_ID>/round-<N>/`, where `N` is the highest existing `round-<k>` for this TARGET_ID plus 1, unless explicitly continuing an in-progress round. The max-2-rounds cap and escalation belong to the caller (the `/start-task` loop); a standalone run does one round, states its number, and enforces no cap.

Required files: `review-map.md`, one `reviewer-<lens-set>.md` per reviewer (e.g. `reviewer-all.md`, `reviewer-security.md`, `reviewer-correctness-tests.md`), `verification.md`, `final.md`.

A missing required reviewer artifact means `review_complete: no` and `lens_subreviews: BLOCKED`.

## Review Map

The lead writes `review-map.md` before dispatch; it orients, it is no verdict. Include:

- target metadata: target, base ref, reviewed head SHA (`headRefOid`), worktree path, story/PR links;
- change areas: changed files grouped by area, key files, what each does, cross-cutting concerns;
- runtime and data-flow notes: upstream callers, downstream effects; state, data, network, persistence, native boundaries; async, streaming, lifecycle, retry paths; hidden coupling between changed files; touched flow docs; a diagram only when it clarifies; each claim confirmed in code;
- requirements → files: each story/PR/issue/acceptance-criteria requirement, tied to its text, mapped to files, verification, and lens; missing or ambiguous ones are review risks;
- risk classification, lenses that apply (N/A ones with a reason), the reviewer split, file focus per reviewer, verification required by policy.

Keep findings out of the map unless an obvious blocker changes review planning.

## Risk Classification and Dispatch

High risk per the standard's Working Method (a request for a deep or lens-based review counts too).

- **Low risk:** `lens_subreviews: NOT_REQUIRED`; one `pocketpal-reviewer` with `LENSES: all` (artifact `reviewer-all.md`).
- **High risk:** parallel `pocketpal-reviewer`s with one or a few lenses each, covering every lens that applies exactly once. Each high-risk surface in the map gets its lens a reviewer of its own (trust boundary → Security, schema/persistence → Data, perf-sensitive path → Performance, platform UI → Platform); the other applicable lenses are grouped by shared areas (e.g. Correctness + Tests + Local invariants).

## Subreview Gate

Mandatory for high-risk reviews: run the read-only lens subreviews before the final review. If a required reviewer cannot run, produce no complete final review: mark `review_complete: no` and `lens_subreviews: BLOCKED`.

Delegation shape:

```text
Use pocketpal-reviewer.
LENSES: <lens list | all>
Target: <target>
Worktree: <review worktree>
Base ref: <base SHA/ref>
Head ref: <head SHA/ref>
Review map: workflows/reviews/<TARGET_ID>/round-<N>/review-map.md
Output artifact: workflows/reviews/<TARGET_ID>/round-<N>/reviewer-<lens-set>.md

```

If a reviewer returns output without writing it, write it verbatim to the artifact path before synthesis. The final review is built from the reviewer artifacts, each in this shape:

```markdown
# Review (<lenses>): <TARGET_ID> Round <N>

status: FINDINGS | NOTHING_FOUND

## Findings

### <ID>: <Title>

severity: BLOCKER | CONCERN | SUGGESTION
lens: Correctness | Architecture | Maintainability (incl. comment load) | Tests | Security | Data / Migration | Performance/Resources | UX / Accessibility | Platform | Local invariants
confidence: high | med | low
path: relative/path.ts
line: 123
impact: One sentence.
evidence: Short quote or concrete code reference.
fix: One sentence.
```

## Verification

Run feasible verification from the app worktree and write the status to `verification.md`. Run `yarn install` in the worktree when `node_modules` or `jest` is missing, and in `e2e/` before E2E commands. Native dependency or code changes require `pod install`, an iOS build, and an Android build; missing them is blocking unless the user explicitly changes the requirement.

## Final Synthesis

Read all reviewer artifacts and `verification.md`, then write `final.md` in the human-facing shape (`docs/standards/review-output.md`): the team-facing, local synthesis record (Publish posts the public form). Before writing:

- Confirm every required reviewer artifact exists, or mark the review incomplete.
- Merge duplicate findings.
- Normalize each finding's severity and confidence against the standard.
- Refute each BLOCKER/CONCERN (standard's Adversarial verification) as a reviewer independent of the one that raised it; record `refutation: stands` or drop/downgrade with `refutation: withdrawn — <reason>`.
- Apply the mechanical verification gate: no `APPROVE` / `review_complete: yes` over `NOT_RUN` checks.
- Include short synthesis notes only when they matter, such as unavailable reviewers, merged duplicates, missing reviewer artifacts, or verification gaps.

## Final Response

Respond from `final.md`, team-shareable: `lens_subreviews: COMPLETED | BLOCKED | NOT_REQUIRED` (`COMPLETED` for a complete high-risk review), `review_complete: no` when required subreviews did not complete, findings grouped by severity, verification status, residual risks, and open questions.

## Publish

For a PR target, post the verdict to the PR with `tools/ghb pr review <n> --comment` and a body file (always `--comment`: the bot authors pipeline PRs, and GitHub refuses a review that requests changes on the author's own PR):

- verdict, reviewed head SHA, and verification status;
- BLOCKER/CONCERN findings, one line each: severity, `path:line`, the fix;
- `SUGGESTION`s, one line each, under a `Follow-ups` heading (the PR's follow-ups; the operator may file them);
- ends with the signature line from `AGENTS.md`.

Public references only (`AGENTS.md`, Public artifacts): no round numbers, review or story paths, task IDs, or story anchors. Keep it short.
