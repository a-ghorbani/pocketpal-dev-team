# Visual Capture Workflow

When a story has `Visual Evidence Required: YES`, the pipeline creates or verifies durable visual evidence before approval.

Visual evidence is an artifact requirement, not a request for the user to inspect the UI. Do not ask the user to inspect UI manually unless the required capture infrastructure, device, simulator, or design source is unavailable after documented attempts.

There are **three flavours**, picked by what the change touches:

| Surface | Flavour | Spec |
| --- | --- | --- |
| Chat output (prompt → assistant response) | **Parametrized** | `e2e/specs/visual-capture.spec.ts` driven by `VISUAL_CAPTURES` env JSON |
| Anything else (settings panel, sheet, header indicator, drawer state, etc.) | **Per-task, one-shot** | `e2e/specs/visual-capture/<TASK-ID>.spec.ts` authored in the worktree, **gitignored**, dies with the worktree |
| **Figma-sourced screen / component** (any redesign-rollout slice) | **Figma parity diff** | Pair of `<screen>-figma.png` + `<screen>-sim.png` committed under `workflows/stories/<TASK-ID>/visual-diff/`. Drive via the [`figma-implement`](../../.claude/skills/figma-implement/SKILL.md) skill; reviewed by the `pocketpal-design-parity-reviewer` subagent. |

Decision rule:

- "Send a prompt, screenshot the response" → Flavour A.
- "Drive Appium to a non-chat surface that isn't tied to a Figma spec" → Flavour B.
- "Implementing a Figma node id" → Flavour C (mandatory side-by-side captures committed into the story dir; the parity reviewer is a pipeline gate).

## Ownership

| Step | Owner |
| --- | --- |
| Decide whether evidence is required | `pocketpal-intake` sets `Visual Evidence Required=YES`; `pocketpal-pipeline-reviewer` **re-derives it from the actual diff** so a missed flag can't skip the gate. Any change under `src/` to a screen, component, style, theme, or rendering path ⇒ required. |
| Produce captures (Flavour A / B) | `pocketpal-tester` writes the PNGs and hands their paths to the reviewer in the Test Report. |
| Produce captures (Flavour C) | `pocketpal-implementer` via the `figma-implement` skill (committed side-by-sides under the story dir). |
| Post captures to the PR | `pocketpal-pipeline-reviewer`, immediately after `gh pr create`, via `tools/post-pr-visual-evidence.sh`. |
| Enforce | `pocketpal-pipeline-reviewer` — "UI changed but no visual-evidence comment on the PR" is a `BLOCKER`. |

## Posting to the PR (mandatory)

Captures are not evidence until they are on the PR. After the draft PR exists, post them as an inline comment:

```bash
# run from the task worktree (so gh infers the pocketpal-ai repo)
./tools/post-pr-visual-evidence.sh <PR-number> \
  --title "Visual evidence — <short label>" \
  <path/to/capture-1.png> <path/to/capture-2.png> ...
```

The helper uploads each PNG to GitHub's `user-attachments` CDN via the `gh image` extension — public URLs that render inline, so nothing is committed to the app repo — and posts one comment. If no GitHub session token is available it prints `MANUAL_POST_REQUIRED` with the exact hand-run command and exits non-zero; record that as a pending condition on the PR and do **not** report the evidence as posted. Recording only a local screenshot path is a fallback for a documented capture/post failure (see Failure handling), never the default when posting is possible.

## Flavour A — Parametrized (chat output)

1. Read the `Visual evidence` section in the story for the `VISUAL_CAPTURES` JSON.
2. Run from the task worktree:

```bash
cd "${WORKTREE_PATH}"
yarn ios:build:e2e
cd e2e && yarn install && cd ..
VISUAL_CAPTURES='[the JSON from the story]' yarn e2e:ios --spec visual-capture --skip-build
```

3. Screenshots land in `e2e/debug-output/screenshots/visual-captures/`.
4. Hand the capture paths to the reviewer in the Test Report. The reviewer posts them to the PR via `tools/post-pr-visual-evidence.sh` after the draft PR exists (see **Posting to the PR**).

## Flavour B — Per-task one-shot (ad-hoc UI surfaces)

When the surface isn't chat output, author a one-off spec **in the worktree** that drives Appium directly to the affected surfaces using the existing Page Object Model (`e2e/pages/`). The spec lives at:

```
e2e/specs/visual-capture/<TASK-ID>.spec.ts   (gitignored — pattern: e2e/specs/visual-capture/TASK-*.spec.ts)
```

### Rationale for discarding instead of preserving

These specs are one-shot pre/post diff harnesses tied to a specific PR review. Once the PR merges, `main` *is* the post-state — re-running the spec compares post-against-post, which is meaningless. Long-term preservation also accumulates per-task specs that drift silently as the UI evolves, with no signal value when they break.

If you ever regret a discard (e.g. a future slice touches the same surfaces and would have benefited from re-using a prior spec), the spec is still recoverable from the git history of the worktree branch via `git log --diff-filter=D --all -- "e2e/specs/visual-capture/*"` before the worktree is removed. At that point, promote it to a durable spec at `e2e/specs/features/<descriptive-name>.spec.ts` and remove the `gitignore` rule for that file.

### Conventions

- **POM-first.** Compose existing page helpers; extend `e2e/pages/` only if a navigation step is genuinely new (more likely to be reused by future slices — those POM additions ARE committed to the product repo).
- **Output dir.** Each capture writes to `e2e/debug-output/screenshots/visual-captures/<TASK-ID>/<label>/<name>.png` where `<label>` comes from `VISUAL_CAPTURE_LABEL` (defaults to `post`).
- **Best-effort.** Wrap each capture in a try/catch so a failure on one surface doesn't skip the others.
- **Network + state.** Note any external dependencies (Palshub fetch, cached model, auth state) in the spec header so reruns are reproducible while the worktree exists.

### Pre/post comparison

The same spec runs against `main` and the branch:

```bash
# post (in the worktree, label defaults to 'post'):
VISUAL_CAPTURE_LABEL=post \
  yarn e2e:ios --spec visual-capture/<TASK-ID> --skip-build

# pre (cherry-pick spec + any new testID/helper commits onto main, then re-run):
git checkout origin/main
git checkout feature/<branch> -- e2e/specs/visual-capture/<TASK-ID>.spec.ts \
  <any e2e/pages/*.ts or e2e/helpers/*.ts files the spec depends on> \
  <any product files with new testIDs the spec depends on>
yarn install && (cd ios && pod install) && yarn ios:build:e2e
VISUAL_CAPTURE_LABEL=pre \
  yarn e2e:ios --spec visual-capture/<TASK-ID> --skip-build

# back to branch:
git checkout feature/<branch>
```

The two output dirs (`<TASK-ID>/pre/` and `<TASK-ID>/post/`) are diffed by the reviewer or attached side-by-side as PR comments. Screenshots can be committed to the dev-team story dir at `workflows/stories/<TASK-ID>/screenshots/` if they need to be referenced from the PR.

## Flavour C — Figma parity diff

When the work is "implement Figma node id X into the app" (any FOU-112 redesign-rollout slice, any task that pins a canonical Figma file), the implementer follows the [`figma-implement`](../../.claude/skills/figma-implement/SKILL.md) skill, which mandates a committed side-by-side per screen:

```
workflows/stories/<TASK-ID>/visual-diff/<screen>-figma.png
workflows/stories/<TASK-ID>/visual-diff/<screen>-sim.png
```

When light + dark + RTL are in scope, capture each variant separately (`<screen>-light-figma.png`, etc.).

### How to produce each pair

1. **Figma render**: `mcp__plugin_figma_figma__get_screenshot(fileKey, nodeId, maxDimension=2622)` → download the PNG.
2. **Sim screenshot**: build + run the app on a sim whose width matches the design (iPhone 17 Pro / 13 Pro for 393pt designs). Either drive Appium (Flavour B-style spec under `e2e/specs/visual-capture/<TASK-ID>.spec.ts`) or capture by hand with `xcrun simctl io <udid> screenshot`.
3. Commit both PNGs into the story dir on the same branch as the implementation.

### Why this lives in the story dir (not `e2e/debug-output/`)

`e2e/debug-output/` is gitignored — captures vanish with the worktree. Flavour C captures need to survive the PR review and are referenced from the parity-review subagent's report, so they live alongside `intent-brief.md` / `what.md` / `how.md`.

### Review gate

The `pocketpal-design-parity-reviewer` subagent runs after the implementer, before the pipeline reviewer. It compares each `*-figma.png` against `*-sim.png` pair, walks the Figma node tree to catch silently-dropped children, and greps for raw hex in screens. Its findings route back to the implementer (max 2 parity rounds before human escalation).

### Bonus: pre/post diff for restyle slices

For FOU-112 phase slices that touch an existing screen (e.g. theming a previously-styled Home / Chat), capture the same screen on `origin/main` before the restyle to file `<screen>-pre.png`, and the post-restyle as `<screen>-sim.png`. The reviewer compares `pre` vs `sim` (regression check) AND `figma` vs `sim` (design parity).

## Failure handling

If a capture fails due to model download timeout, inference error, simulator instability, or missing network state, do **not** block the PR by default. Record the **specific, documented** failure (command + error) in the review report and escalate only if visual evidence is still required and no acceptable substitute evidence exists. A documented infra failure is the only escape from the posting gate — silently shipping a UI change with no captures and no recorded failure is a `BLOCKER`, not a skip.

For Surface-style mechanical-parity changes (Phase 2 design-system rebuilds), a unit test asserting the relevant style invariant (e.g. `elevation` default matching Paper) is acceptable evidence in lieu of screenshots when the capture infrastructure can't be exercised. State this explicitly in the PR body.
