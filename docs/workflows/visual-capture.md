# Visual Capture Workflow

When a story has `Visual Confirmation: YES`, the reviewer runs this procedure to capture screenshots.

There are **two flavours**, picked by what the change touches:

| Surface | Flavour | Spec |
| --- | --- | --- |
| Chat output (prompt → assistant response) | **Parametrized** | `e2e/specs/visual-capture.spec.ts` driven by `VISUAL_CAPTURES` env JSON |
| Anything else (settings panel, sheet, header indicator, drawer state, etc.) | **Per-story** | `e2e/specs/visual-capture/<TASK-ID>.spec.ts` authored on the story branch |

Decision rule: if the surface can be reached by "send a prompt, screenshot the response," use the parametrized flavour. Otherwise write a per-story spec.

## Flavour A — Parametrized (chat output)

1. Read the `Visual Confirmation` section in the story for the `VISUAL_CAPTURES` JSON.
2. Run from the task worktree:

```bash
cd "${WORKTREE_PATH}"
yarn ios:build:e2e
cd e2e && yarn install && cd ..
VISUAL_CAPTURES='[the JSON from the story]' yarn e2e:ios --spec visual-capture --skip-build
```

3. Screenshots land in `e2e/debug-output/screenshots/visual-captures/`.
4. Attach to the PR as a comment, or note the local screenshot path for human verification.

## Flavour B — Per-story (ad-hoc UI surfaces)

When the surface isn't chat output, the agent authors a one-off spec on the story branch that drives Appium directly to the affected surfaces using the existing Page Object Model (`e2e/pages/`). The spec lives at:

```
e2e/specs/visual-capture/<TASK-ID>.spec.ts
```

### Conventions

- **POM-first.** Compose existing page helpers; extend `e2e/pages/` only if a navigation step is genuinely new (more likely to be reused by future slices touching the same surface).
- **Output dir.** Each capture writes to `e2e/debug-output/screenshots/visual-captures/<TASK-ID>/<label>/<name>.png` where `<label>` comes from `VISUAL_CAPTURE_LABEL` (defaults to `post`).
- **Best-effort.** Wrap each capture in a try/catch so a failure on one surface doesn't skip the others. Failures write `<name>-failed.txt` alongside.
- **Lifecycle.** The spec is committed to the PR. At merge time the reviewer decides:
  - Delete if the surface is unlikely to be re-captured.
  - Keep if the slice belongs to a multi-phase rollout (e.g. each FOU-112 redesign slice may re-capture the same surfaces).
- **Network + state.** Note any external dependencies (Palshub fetch, cached model, auth state) in the spec header so reruns are reproducible.

### Pre/post comparison

When the story asks for both the pre-swap reference and the post-swap result, run the same spec against `main` and the branch:

```bash
# post (this branch, label defaults to 'post'):
VISUAL_CAPTURE_LABEL=post \
  yarn e2e:ios --spec visual-capture/<TASK-ID> --skip-build

# pre (main, with the spec cherry-picked over):
git checkout main
git checkout feature/<branch> -- e2e/specs/visual-capture/<TASK-ID>.spec.ts
VISUAL_CAPTURE_LABEL=pre \
  yarn e2e:ios --spec visual-capture/<TASK-ID> --skip-build

# clean up the cherry-picked file before switching branches again:
git checkout -- e2e/specs/visual-capture/<TASK-ID>.spec.ts
git checkout feature/<branch>
```

The two output dirs (`<TASK-ID>/pre/` and `<TASK-ID>/post/`) are then diffed by the reviewer or attached side-by-side as PR comments.

For changes that touch app state (new screens, new flags), an alternative is to keep two sibling worktrees — one on `main`, one on the branch — and run the same built `.app` against each. Pick whichever the reviewer finds simpler.

## Failure handling

If a capture fails due to model download timeout, inference error, simulator instability, or missing network state, do **not** block the PR by default. Record the failure in the review report and ask the human to run the capture manually if visual proof is still needed.

For Surface-style mechanical-parity changes (Phase 2 design-system rebuilds), a unit test asserting the relevant style invariant (e.g. `elevation` default matching Paper) is acceptable evidence in lieu of screenshots when the capture infrastructure can't be exercised. State this explicitly in the PR body.
