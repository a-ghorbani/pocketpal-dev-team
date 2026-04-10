---
description: E2E visual capture workflow for verifying UI changes via screenshots
---

# Visual Capture Workflow

When a story has `Visual Confirmation: YES`, the reviewer runs this to capture screenshots.

## Running Visual Captures

1. Read the `Visual Confirmation` section in the story for the `VISUAL_CAPTURES` JSON
2. Run the visual-capture E2E spec:

```bash
cd "${WORKTREE_PATH}"

# Build the app if not already built
yarn ios:build:e2e

# Run visual capture with the prompts from the story
cd e2e && yarn install && cd ..
VISUAL_CAPTURES='[the JSON from the story]' yarn e2e:ios --spec visual-capture --skip-build
```

3. Screenshots are saved to `e2e/debug-output/screenshots/visual-captures/`
4. After creating the PR, attach screenshots as a comment:

```bash
for img in e2e/debug-output/screenshots/visual-captures/*.png; do
  gh pr comment <PR_NUMBER> --repo a-ghorbani/pocketpal-ai \
    --body "### Visual Confirmation: $(basename "$img" .png)
![$(basename "$img")](screenshot)"
done
```

If `gh` image upload is not available, note in the PR that screenshots are at the path above and the human should run the visual-capture spec locally.

**If the E2E visual capture fails** (model download timeout, inference error, etc.), do NOT block the PR. Note it in the review report and suggest the human run it manually. Visual confirmation is advisory, not a gate.
