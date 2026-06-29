# Reconcile main → redesign/phase-3 — Brief (reconcile-lead)

You are the lead for reconciling the redesign integration branch with `main` so the eventual
flip is conflict-free. This is judgment-heavy MERGE work, not a feature. You report to the PM
(`redesign-phase3-lead`, session `5720f24d-6d3a-4cf9-8da2-c1afce16ab05`).

## 0. Register in agistry first
`~/.claude/skills/agistry/agistry.sh` — role `reconcile-lead`, task "Reconcile main→redesign/phase-3
(merge, resolve conflicts, re-green CI+native); reports to redesign-phase3-lead". When done or
blocked on a judgment call, `agistry.sh send` the PM session above. agistry delivery has been flaky —
the PM may also relay via tmux; that's fine.

## 1. Where you are
- Worktree: `worktrees/RECONCILE-phase3`, branch `reconcile/phase3-main` @ `276663a9`
  (= `origin/redesign/phase-3`, all 7 Phase-3 redesign slices). **Work here. Never touch `main`.**
- Baseline you're merging IN: `origin/main` (`cbc33b03` is the merge-base; main is **83 commits**
  ahead of the branch, branch is 9 commits of real redesign work ahead of base).
- Pre-flight: `cd` into the worktree; confirm branch is `reconcile/phase3-main`, NOT main; confirm
  you are NOT in `repos/pocketpal-ai/`.

## 2. The merge
`git fetch origin main` then `git merge origin/main`. Expect conflicts in ~20 files. Resolve by
INTENT, documenting each decision. Guiding principle:
- **main = newer product/runtime truth** for non-UI concerns (billing, locales, auth, native deps,
  store/server logic main changed after the branch point).
- **redesign branch = truth** for design/UI/nav/theming/DS.

### Known conflicts + how to resolve
1. **`src/locales/pt_BR.json` + `LANGUAGE_ORDER` + l10n validation tests** — main ADDED pt_BR and
   registered it; the branch predates that and appears to "delete" it. **Take main's side**: keep
   pt_BR.json, keep it in `LANGUAGE_ORDER`/registry, keep the validation-test additions. The branch
   did not intend to remove pt_BR.
2. **Drawer-deprecation comment** — the redesign REMOVED the drawer (bottom-tab migration). Keep the
   redesign intent (drawer gone); just reconcile the stale comment text so it reads cleanly.
3. **⚠️ "Deletions masquerading as redesign" — investigate each, do NOT blind-resolve.** The branch
   still CONTAINS files main DELETED after the merge-base (e.g. `reasoningCapability`, `serverTypes`,
   `ServerStore`). Default is to take **main's removal** (these are main's deletions, not redesign's
   intent). BUT first check: did any redesign Phase-3 code start CONSUMING those symbols? If a
   redesign slice added a real dependency on something main removed, that's a genuine semantic
   conflict — surface it to the PM rather than guessing. `git log --oneline cbc33b03..origin/main --
   <file>` shows main's intent per file.

For every conflict: prefer the resolution that keeps BOTH the redesign UI and main's newer logic.
Write a one-line rationale per resolved file — you'll need them for the PR body.

## 3. Verify (this is NATIVE_CHANGES=YES)
main includes a Play Billing 8.2.1 native rewrite + other native deltas, so a JS-only check is NOT
enough. Required before "green":
- `yarn install` (lockfile may need reconcile — keep main's dependency versions unless redesign
  explicitly bumped something).
- `yarn lint && yarn typecheck && yarn test` (full suite).
- `cd ios && pod install`, then an **iOS build**; then an **Android build**.
- If the merged `package.json`/`Podfile.lock`/`yarn.lock` conflict, resolve toward main's newer
  native deps unless a redesign change requires otherwise.

## 4. Output
- Commit the merge on `reconcile/phase3-main` (a merge commit is fine; do NOT squash away the history).
- Open a **PR from `reconcile/phase3-main` INTO `redesign/phase-3`** (NOT into main). PR body: list
  every conflicted file + the one-line resolution rationale; note native build results (iOS/Android
  pass/fail with evidence); flag any judgment calls you escalated.
- Do **NOT** push `redesign/phase-3` directly and do **NOT** target `main`. The PR is the review surface.
- `agistry.sh send` the PM (`redesign-phase3-lead`) when the PR is open + builds green, or earlier if
  blocked on a semantic-conflict judgment call.

## Constraints
- Never commit/build/switch branches in `repos/pocketpal-ai/` (the submodule) — you are in a worktree,
  that's the correct place to build/test.
- Never target or push `main`. Public artifacts (PR/commit): no internal tracker IDs, no story anchors.
- Manage your own context; if the native builds are long, run them and report rather than idling.
