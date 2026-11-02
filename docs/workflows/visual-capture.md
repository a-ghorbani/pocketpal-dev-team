# Visual Capture Workflow

When a story's `evidence.md` has rows whose receipt is a capture, the pipeline creates durable visual evidence before approval. It is an artifact requirement: never ask the user to inspect UI manually unless the capture infrastructure, device, simulator, or design source is unavailable after documented attempts.

Three flavours, by what the change touches:

| Surface | Flavour | Spec |
| --- | --- | --- |
| Chat output (prompt → assistant response) | **Parametrized** | `e2e/specs/visual-capture.spec.ts` driven by `VISUAL_CAPTURES` env JSON |
| Anything else (settings panel, sheet, header indicator, drawer state, etc.) | **Per-task, one-shot** | `e2e/specs/visual-capture/<TASK-ID>.spec.ts` authored in the worktree, **gitignored**, dies with the worktree |
| **Figma-sourced screen / component** (any redesign-rollout slice) | **Figma parity diff** | `<screen>-figma.png` + `<screen>-sim.png` under `<STORY_DIR>/visual-diff/`, posted to the PR; via [`figma-implement`](../../skills/figma-implement/SKILL.md), reviewed by `pocketpal-design-parity-reviewer`. |

Decision rule:

- "Send a prompt, screenshot the response" → Flavour A.
- "Drive Appium to a non-chat surface that isn't tied to a Figma spec" → Flavour B.
- "Implementing a Figma node id" → Flavour C (mandatory side-by-sides in the story dir, posted to the PR; the parity reviewer is a pipeline gate).

## Ownership

| Step | Owner |
| --- | --- |
| Decide whether evidence is required | `pocketpal-intake` adds capture rows to `evidence.md` from the claim; architect and implementer add rows for surfaces they touch; `pocketpal-pipeline-reviewer` **re-derives it from the diff** so a missing row can't skip the gate. Any `src/` change to a screen, component, style, theme, or rendering path ⇒ required. |
| Produce captures (Flavour A / B) | `pocketpal-tester` writes the PNGs and hands their paths to the reviewer in the Test Report. |
| Produce captures (Flavour C) | `pocketpal-implementer` via the `figma-implement` skill. |
| Post captures to the PR | `pocketpal-pipeline-reviewer` (Flavour C pairs included), immediately after `tools/ghb pr create`, via `tools/post-pr-visual-evidence.sh`. |
| Enforce | `pocketpal-pipeline-reviewer` — "UI changed but no visual-evidence comment on the PR" is a `BLOCKER`. |

Device runs claim a phone through agistry first and release it after. This host has no iOS toolchain: the `yarn e2e:ios`, `yarn ios:build:e2e` and `xcrun simctl` steps below run through `ios-router`.

## Freshness and build prerequisites

Read `visual-capture-runbook.md` (next to this file) before capturing. Rules:

- A capture post-dates the **installed** bundle, which post-dates the built APK, which post-dates the last shippable `src/` commit (tests excluded). Hash the bundle inside the installed package before and after the run; capture with reset disabled.
- A release bundle is Hermes bytecode: search with `strings -a` plus the UTF-16LE form, calibrated on a known marker, never plain `grep`.
- On a re-capture round check each expected file's mtime individually. Record device, OS, locale, and navigation mode beside the shots.
- What a screenshot cannot show (a11y props, hit areas, step counts, something that no longer happens) needs a test or an a11y-tree dump.
- Never revert a local build prerequisite; keep it unstaged (`git add <paths>`, `git commit -- <paths>`, never `add -A`). Its leak check is commit-scoped: `git diff origin/main...HEAD --name-only | grep -c '^android/'` must be 0. A fresh baseline worktree needs it re-applied (`sync-worktree-config.sh` does not carry `android/app/build.gradle`).

## Posting to the PR (mandatory)

Captures are not evidence until they are on the PR, and each must show what it proves. Pick the layout by the PR's claim:

| Claim | Layout | Captures |
| --- | --- | --- |
| A fix | Before / after | the bug on `origin/main`, the fix on the branch |
| No regression | Before / after | the same surface on `origin/main` and the branch |
| A new feature | Description / screenshot | one row per state, captioned with what it shows |

Capture only the surfaces the change touches. After the draft PR exists, post them as an inline comment; the helper builds the table and refuses an uncaptioned image:

```bash
# run from the task worktree (so gh infers the pocketpal-ai repo)
../../tools/post-pr-visual-evidence.sh <PR-number> --before-after \
  --title "Visual evidence — <short label>" \
  "Long model name truncates=pre/name.png" post/name.png ...

../../tools/post-pr-visual-evidence.sh <PR-number> \
  --title "Visual evidence — <short label>" \
  "Voice toggle in Settings=settings.png" "Reply read aloud=chat.png" ...
```

The helper uploads each PNG to GitHub's `user-attachments` CDN via the `gh image` extension (inline public URLs; nothing committed to the app repo) and posts one comment as `pocketpal-dev-team[bot]` via `tools/ghb` (`docs/workflows/github-bot-identity.md`). If the upload has no GitHub session token or the comment fails, it prints `MANUAL_POST_REQUIRED` with the exact hand-run command and exits non-zero: record a pending condition on the PR and do **not** report the evidence as posted. A local screenshot path alone is only a fallback for a documented capture/post failure (Failure handling).

## Flavour A — Parametrized (chat output)

1. Build the `VISUAL_CAPTURES` JSON from the chat-output capture rows in `evidence.md`.
2. Run from the task worktree:

```bash
cd "${WORKTREE_PATH}"
yarn ios:build:e2e
cd e2e && yarn install && cd ..
VISUAL_CAPTURES='[the JSON from the story]' yarn e2e:ios --spec visual-capture --skip-build
```

3. Screenshots land in `e2e/debug-output/screenshots/visual-captures/`.
4. Hand the paths to the reviewer in the Test Report; the reviewer posts them after the draft PR exists (**Posting to the PR**).

## Flavour B — Per-task one-shot (ad-hoc UI surfaces)

Author a one-off spec **in the worktree** that drives Appium to the affected surfaces through the Page Object Model (`e2e/pages/`):

```
e2e/specs/visual-capture/<TASK-ID>.spec.ts   (gitignored — pattern: e2e/specs/visual-capture/TASK-*.spec.ts)
```

Only `TASK-*` names are ignored; a PR-fix round uses `TASK-PR-<n>.spec.ts` so it stays out of the app PR.

### Discard, don't preserve

These specs are one-shot pre/post harnesses for one PR: once it merges, `main` is the post-state, and kept specs drift silently. The spec is never committed and dies with the worktree; to keep one, promote it before removal to `e2e/specs/features/<descriptive-name>.spec.ts`.

### Conventions

- **POM-first.** Compose existing page helpers; extend `e2e/pages/` only for a genuinely new navigation step (POM additions ARE committed to the product repo).
- **Output dir.** Each capture writes to `e2e/debug-output/screenshots/visual-captures/<TASK-ID>/<label>/<name>.png` where `<label>` comes from `VISUAL_CAPTURE_LABEL` (defaults to `post`).
- **Best-effort.** Wrap each capture in a try/catch so one failing surface doesn't skip the others.
- **Network + state.** Note external dependencies (Palshub fetch, cached model, auth state) in the spec header so reruns are reproducible.
- **Assertions here do not ship.** Mirror anything load-bearing in a committed unit test.

### Pre/post comparison

The same spec runs with `VISUAL_CAPTURE_LABEL=post` in the worktree and `=pre` in a `<TASK-ID>-base` worktree off `origin/main`, removed with `./tools/remove-worktree.sh` once the captures are copied out; commands in `visual-capture-runbook.md`, Flavour B pre/post. The `<TASK-ID>/pre/` and `<TASK-ID>/post/` dirs are posted side-by-side (**Posting to the PR**); copy them to `<STORY_DIR>/screenshots/` (local story space, never the app branch) when they must outlive the worktree.

## Flavour C — Figma parity diff

When the work is "implement Figma node id X into the app" (any FOU-112 redesign-rollout slice, any task that pins a canonical Figma file), the implementer follows the [`figma-implement`](../../skills/figma-implement/SKILL.md) skill, whose Step 4 produces a `<STORY_DIR>/visual-diff/<screen>-figma.png` + `<screen>-sim.png` pair per screen (light, dark, and RTL variants separately) and says how. The pipeline reviewer posts the pairs with `tools/post-pr-visual-evidence.sh`; the PR comment is the durable copy.

### Why this lives in the story dir (not `e2e/debug-output/`)

`e2e/debug-output/` vanishes with the worktree; Flavour C captures must survive until the parity review and PR post, so they live beside `intent-brief.md` / `what.md` / `evidence.md` (local story space, not the app branch).

### Review gate

The orchestrator routes to `pocketpal-design-parity-reviewer` after the tester, before the pipeline reviewer, with `STORY_DIR` in the handoff. It compares each `*-figma.png` / `*-sim.png` pair, walks the node tree for dropped children, and greps screens for raw hex. Findings route back to the implementer (max 2 parity rounds, then human escalation).

### Bonus: pre/post diff for restyle slices

For FOU-112 slices that restyle an existing screen (e.g. Home / Chat), capture it on `origin/main` as `<screen>-pre.png` and post-restyle as `<screen>-sim.png`; the reviewer compares `pre` vs `sim` (regression) AND `figma` vs `sim` (parity).

## Failure handling

A capture failing on model download timeout, inference error, simulator instability, or missing network state does **not** block the PR by default. Record the **specific** failure (command + error) in the review report; escalate only if visual evidence is still required and no acceptable substitute exists. A documented infra failure is the only escape from the posting gate: a UI change with no captures and no recorded failure is a `BLOCKER`.

For Surface-style mechanical-parity changes (Phase 2 design-system rebuilds), a unit test asserting the style invariant (e.g. `elevation` default matching Paper) is acceptable in lieu of screenshots when capture infrastructure can't be exercised; say so in the PR body.
