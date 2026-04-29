# Visual Capture Workflow

When a story has `Visual Confirmation: YES`, the reviewer runs this procedure to
capture screenshots.

## Run Visual Captures

1. Read the `Visual Confirmation` section in the story for the `VISUAL_CAPTURES` JSON.
2. Run the visual-capture E2E spec from the task worktree:

```bash
cd "${WORKTREE_PATH}"
yarn ios:build:e2e
cd e2e && yarn install && cd ..
VISUAL_CAPTURES='[the JSON from the story]' yarn e2e:ios --spec visual-capture --skip-build
```

3. Screenshots are saved to
   `e2e/debug-output/screenshots/visual-captures/`.
4. After creating the PR, attach screenshots as a comment or note the local
   screenshot path for human verification.

If visual capture fails due to model download timeout, inference error, or
simulator instability, do not block the PR by default. Record the failure in the
review report and ask the human to run the capture manually if visual proof is
still needed.
