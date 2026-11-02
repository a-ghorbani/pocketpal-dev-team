# Visual Capture Workflow

When a story's `evidence.md` has rows whose receipt is a capture, the pipeline creates durable visual evidence before approval.

Visual evidence is an artifact requirement, not a request for the user to inspect the UI. Do not ask the user to inspect UI manually unless the required capture infrastructure, device, simulator, or design source is unavailable after documented attempts.

There are **three flavours**, picked by what the change touches:

| Surface | Flavour | Spec |
| --- | --- | --- |
| Chat output (prompt → assistant response) | **Parametrized** | `e2e/specs/visual-capture.spec.ts` driven by `VISUAL_CAPTURES` env JSON |
| Anything else (settings panel, sheet, header indicator, drawer state, etc.) | **Per-task, one-shot** | `e2e/specs/visual-capture/<TASK-ID>.spec.ts` authored in the worktree, **gitignored**, dies with the worktree |
| **Figma-sourced screen / component** (any redesign-rollout slice) | **Figma parity diff** | Pair of `<screen>-figma.png` + `<screen>-sim.png` saved under `<STORY_DIR>/visual-diff/` and posted to the PR. Drive via the [`figma-implement`](../../skills/figma-implement/SKILL.md) skill; reviewed by the `pocketpal-design-parity-reviewer` subagent. |

Decision rule:

- "Send a prompt, screenshot the response" → Flavour A.
- "Drive Appium to a non-chat surface that isn't tied to a Figma spec" → Flavour B.
- "Implementing a Figma node id" → Flavour C (mandatory side-by-side captures saved in the story dir and posted to the PR; the parity reviewer is a pipeline gate).

## Ownership

| Step | Owner |
| --- | --- |
| Decide whether evidence is required | `pocketpal-intake` adds capture rows to `evidence.md` from the claim; the architect and implementer add rows for surfaces they touch; `pocketpal-pipeline-reviewer` **re-derives it from the actual diff** so a missing row can't skip the gate. Any change under `src/` to a screen, component, style, theme, or rendering path ⇒ required. |
| Produce captures (Flavour A / B) | `pocketpal-tester` writes the PNGs and hands their paths to the reviewer in the Test Report. |
| Produce captures (Flavour C) | `pocketpal-implementer` via the `figma-implement` skill (side-by-sides saved under the story dir). |
| Post captures to the PR | `pocketpal-pipeline-reviewer` (Flavour C pairs included), immediately after `gh pr create`, via `tools/post-pr-visual-evidence.sh`. |
| Enforce | `pocketpal-pipeline-reviewer` — "UI changed but no visual-evidence comment on the PR" is a `BLOCKER`. |

Device runs claim a phone through agistry first and release it after. This host has no iOS toolchain: the `yarn e2e:ios`, `yarn ios:build:e2e` and `xcrun simctl` steps below run through `ios-router`.

## Freshness

A capture must post-date the **installed** bundle, which must post-date the built APK, which must
post-date the last shippable `src/` commit. The middle term is the one that gets forgotten:
verifying the APK on disk proves nothing about what the phone is running, and an APK's mtime
updates on any repackage, so a fresh APK can ship a stale bundle. Hash the bundle inside the
installed package, before and after the run, and capture with reset disabled.

```bash
unzip -p <apk> assets/index.android.bundle | sha256sum   # compare against HEAD's rebuilt bundle
git log -1 --format='%cI %h' -- src \
    ':(exclude)src/**/__tests__/**' ':(exclude)src/**/*.test.*'   # tests do not ship; do not gate on them
```

**A release bundle is Hermes bytecode, so a plain `grep` returns zero for everything.** Use
`strings -a` and calibrate on a marker you know is present before trusting an absence. Hermes keeps
**two** string tables: a string containing any non-ASCII character (an ellipsis, a curly quote) is
stored UTF-16LE and invisible to an ASCII search, which reads exactly like a stale bundle — on
precisely the new user-facing copy people reach for as a freshness marker. Search both:
`iconv -f UTF-8 -t UTF-16LE <<<'MARKER' | grep -c -f - <bundle>`.

On a re-capture round check each expected file's mtime **individually**: a spec that skips a case
leaves the previous run's file in place, and a partly refreshed directory looks identical to a fully
refreshed one. Record the device, OS, locale and **navigation mode** beside the shots — nav mode
changes bottom insets, so a gesture-mode capture proves nothing about three-button clearance.

Some changes cannot be evidenced by a screenshot at all — a11y props, hit areas, a step count,
something that no longer happens. Those need a test or an a11y-tree dump, not a better capture.

## Local build prerequisites

**Never revert a local build prerequisite.** Leave it modified and unstaged for the life of the work
and keep it out of commits by never staging it — `git add <paths>` and `git commit -- <paths>`,
never `add -A`. Reverting it as housekeeping once coding finishes kills the rebuild and leaves the
capture step with no fresh artefact.

The leak check is therefore **commit-scoped**. A two-dot `git diff origin/main -- android/` compares
the working tree, so it reads non-empty while the prerequisite is correctly in place — a false
violation whose natural remedy is the revert:

```bash
git diff origin/main...HEAD --name-only | grep -c '^android/'   # must be 0
```

A fresh baseline worktree (for a "before" capture off `origin/main`) needs the prerequisite
re-applied; `sync-worktree-config.sh` does not carry `android/app/build.gradle`.

## Posting to the PR (mandatory)

Captures are not evidence until they are on the PR. A dump of screenshots isn't evidence either: each one has to show what it proves. Pick the layout by what the PR claims:

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

The helper uploads each PNG to GitHub's `user-attachments` CDN via the `gh image` extension — public URLs that render inline, so nothing is committed to the app repo — and posts one comment as `pocketpal-dev-team[bot]` via `tools/ghb` (see `docs/workflows/github-bot-identity.md`). If no GitHub session token is available for the upload, or the comment fails, it prints `MANUAL_POST_REQUIRED` with the exact hand-run command and exits non-zero; record that as a pending condition on the PR and do **not** report the evidence as posted. Recording only a local screenshot path is a fallback for a documented capture/post failure (see Failure handling), never the default when posting is possible.

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
4. Hand the capture paths to the reviewer in the Test Report. The reviewer posts them to the PR via `tools/post-pr-visual-evidence.sh` after the draft PR exists (see **Posting to the PR**).

## Flavour B — Per-task one-shot (ad-hoc UI surfaces)

When the surface isn't chat output, author a one-off spec **in the worktree** that drives Appium directly to the affected surfaces using the existing Page Object Model (`e2e/pages/`). The spec lives at:

```
e2e/specs/visual-capture/<TASK-ID>.spec.ts   (gitignored — pattern: e2e/specs/visual-capture/TASK-*.spec.ts)
```

Only `TASK-*` names are ignored. A PR-fix round names its spec `TASK-PR-<n>.spec.ts` so it does not leak into the app PR.

### Rationale for discarding instead of preserving

These specs are one-shot pre/post diff harnesses tied to a specific PR review. Once the PR merges, `main` *is* the post-state — re-running the spec compares post-against-post, which is meaningless. Long-term preservation also accumulates per-task specs that drift silently as the UI evolves, with no signal value when they break.

The spec is never committed, so it is gone once the worktree is removed. To keep one, promote it before removal to a durable spec at `e2e/specs/features/<descriptive-name>.spec.ts`.

### Conventions

- **POM-first.** Compose existing page helpers; extend `e2e/pages/` only if a navigation step is genuinely new (more likely to be reused by future slices — those POM additions ARE committed to the product repo).
- **Output dir.** Each capture writes to `e2e/debug-output/screenshots/visual-captures/<TASK-ID>/<label>/<name>.png` where `<label>` comes from `VISUAL_CAPTURE_LABEL` (defaults to `post`).
- **Best-effort.** Wrap each capture in a try/catch so a failure on one surface doesn't skip the others.
- **Network + state.** Note any external dependencies (Palshub fetch, cached model, auth state) in the spec header so reruns are reproducible while the worktree exists.
- **Assertions in these specs do not ship.** Mirror anything load-bearing in a committed unit test.

### Pre/post comparison

The same spec runs against `main` and the branch:

```bash
# post (in the worktree, label defaults to 'post'):
VISUAL_CAPTURE_LABEL=post \
  yarn e2e:ios --spec visual-capture/<TASK-ID> --skip-build

# pre, in a separate baseline worktree off origin/main (from the dev-team root):
./tools/create-worktree.sh <TASK-ID>-base --detach --ref origin/main
cd worktrees/<TASK-ID>-base
cp ../<TASK-ID>/e2e/specs/visual-capture/<TASK-ID>.spec.ts e2e/specs/visual-capture/
git checkout feature/<branch> -- <any e2e/pages/*.ts or e2e/helpers/*.ts files the spec depends on> \
  <any product files with new testIDs the spec depends on>
yarn install && (cd ios && pod install) && yarn ios:build:e2e
VISUAL_CAPTURE_LABEL=pre \
  yarn e2e:ios --spec visual-capture/<TASK-ID> --skip-build

# after copying the pre captures out (from the dev-team root):
./tools/remove-worktree.sh <TASK-ID>-base --yes
```

The two output dirs (`<TASK-ID>/pre/` and `<TASK-ID>/post/`) are posted side-by-side to the PR (**Posting to the PR**). Copy them to `<STORY_DIR>/screenshots/` when they must outlive the worktree; that dir is local story space, never on the app branch.

## Flavour C — Figma parity diff

When the work is "implement Figma node id X into the app" (any FOU-112 redesign-rollout slice, any task that pins a canonical Figma file), the implementer follows the [`figma-implement`](../../skills/figma-implement/SKILL.md) skill, which mandates a side-by-side per screen:

```
<STORY_DIR>/visual-diff/<screen>-figma.png
<STORY_DIR>/visual-diff/<screen>-sim.png
```

When light + dark + RTL are in scope, capture each variant separately (`<screen>-light-figma.png`, etc.).

### How to produce each pair

1. **Figma render**: `mcp__plugin_figma_figma__get_screenshot(fileKey, nodeId, maxDimension=2622)` → download the PNG.
2. **Sim screenshot**: build + run the app on a sim whose width matches the design (iPhone 17 Pro / 13 Pro for 393pt designs). Either drive Appium (Flavour B-style spec under `e2e/specs/visual-capture/<TASK-ID>.spec.ts`) or capture by hand with `xcrun simctl io <udid> screenshot`.
3. Save both PNGs in the story dir. The pipeline reviewer posts them to the PR with `tools/post-pr-visual-evidence.sh`; the PR comment is the durable copy.

### Why this lives in the story dir (not `e2e/debug-output/`)

`e2e/debug-output/` vanishes with the worktree. Flavour C captures must survive until the parity review and PR post, so they live alongside `intent-brief.md` / `what.md` / `evidence.md` (local story space, not the app branch).

### Review gate

The orchestrator routes to the `pocketpal-design-parity-reviewer` after the tester, before the pipeline reviewer, with `STORY_DIR` in the handoff. It compares each `*-figma.png` against `*-sim.png` pair, walks the Figma node tree to catch silently-dropped children, and greps for raw hex in screens. Its findings route back to the implementer (max 2 parity rounds before human escalation).

### Bonus: pre/post diff for restyle slices

For FOU-112 phase slices that touch an existing screen (e.g. theming a previously-styled Home / Chat), capture the same screen on `origin/main` before the restyle to file `<screen>-pre.png`, and the post-restyle as `<screen>-sim.png`. The reviewer compares `pre` vs `sim` (regression check) AND `figma` vs `sim` (design parity).

## Failure handling

If a capture fails due to model download timeout, inference error, simulator instability, or missing network state, do **not** block the PR by default. Record the **specific, documented** failure (command + error) in the review report and escalate only if visual evidence is still required and no acceptable substitute evidence exists. A documented infra failure is the only escape from the posting gate — silently shipping a UI change with no captures and no recorded failure is a `BLOCKER`, not a skip.

For Surface-style mechanical-parity changes (Phase 2 design-system rebuilds), a unit test asserting the relevant style invariant (e.g. `elevation` default matching Paper) is acceptable evidence in lieu of screenshots when the capture infrastructure can't be exercised. State this explicitly in the PR body.
