# Visual-diff procedure for FOU-114 (Step 14 of how.md)

This slice is an invisible foundation slice — I1 demands pixel-equivalence
with the pre-refactor build. The visual diff against `origin/main` is the
**reviewer-side acceptance step** that closes the I1 claim before merge.

## What we have already

- `screenshots/ios-sim-feature-branch-chat-light.png` — feature branch,
  iOS simulator (iPhone 17 Pro, sim UDID `E91D608C-FC2D-4660-9C73-0DB732C84626`),
  cold-launched on the worktree's `yarn ios:build:e2e` artifact. Renders
  the empty Chat screen ("Activate Model To Get Started"). Background
  white, headline + body in Inter (no Fraunces appears — confirms §9j:
  no consumer references the new typography surface in this slice).
- `screenshots/ios-sim-feature-branch-chat-dark.png` — same simulator,
  same build. (Note: dark mode here is the system appearance, not the
  app's `uiStore.colorScheme` which persists and only updates on
  app-driven Settings change. A reviewer who wants a true dark-mode
  capture should toggle dark mode from inside the app: Settings → "Dark
  mode" toggle.)

E2E quick-smoke also passes against the same artifact (model download
+ load + inference round-trip "Hello! How can I help you today?"
in 11ms/token). The app launches and renders correctly.

## What the reviewer must do before merge

Per how.md Step 14, the diff requires the SAME simulator / emulator
instance and the SAME screen state for an apples-to-apples comparison
between this branch and `origin/main`.

The implementer's machine ran out of disk after the feature-branch
build (8.2GB iOS build + 4.8GB node_modules + 2.1GB Android build +
3.6GB DerivedData × 3 historical), leaving only 247MB free — not enough
to host a second concurrent build of `origin/main` for side-by-side
capture. The reviewer (or a CI step) runs the reference capture:

```bash
# 1. Reference worktree off origin/main
./tools/create-worktree.sh TASK-20260519-2110-ref --ref origin/main
cd worktrees/TASK-20260519-2110-ref
yarn install --frozen-lockfile
cd ios && bundle exec pod install && cd ..

# 2. Reference iOS sim build
yarn ios:build:e2e
xcrun simctl boot E91D608C-FC2D-4660-9C73-0DB732C84626 || true
xcrun simctl install E91D608C-FC2D-4660-9C73-0DB732C84626 \
  ios/build/Build/Products/Release-iphonesimulator/PocketPal.app
xcrun simctl launch E91D608C-FC2D-4660-9C73-0DB732C84626 ai.pocketpal
sleep 8
xcrun simctl io E91D608C-FC2D-4660-9C73-0DB732C84626 screenshot \
  ../../workflows/stories/TASK-20260519-2110/screenshots/ios-sim-origin-main-chat-light.png

# Toggle dark from inside the app (Settings → Dark mode), wait, capture:
xcrun simctl io E91D608C-FC2D-4660-9C73-0DB732C84626 screenshot \
  ../../workflows/stories/TASK-20260519-2110/screenshots/ios-sim-origin-main-chat-dark.png

# 3. Reference Settings screen (light + dark) — tap drawer → Settings,
#    capture, toggle, capture.

# 4. Repeat steps 2–3 on an Android emulator (Pixel 7-class, AVD UDID
#    of choice). yarn android:build:e2e for the reference build.

# 5. Side-by-side compare (8 pairs total = 4 screens × 2 platforms).
#    `compare -metric AE` (ImageMagick) on each pair; or human visual
#    inspection at 1:1 zoom.

# 6. Remove the reference worktree once captures are saved:
./tools/remove-worktree.sh TASK-20260519-2110-ref --yes
```

## Acceptance

Per WHAT §1d row 2 / D10, this slice's invisibility is guaranteed at
the source level:

1. `tokens.colors.*` for both light and dark modes was copied **verbatim**
   from `createBaseColors(AppTheme.{Light,Dark})` + `createSemanticColors(_, isDark)`
   in the pre-refactor `src/utils/theme.ts`. Dark values further
   subjected to D6 resolution (current dark wins on canonical
   disagreement) — see `dark-tokens.json`.
2. `theme.fonts.*` is constructed verbatim — same `configureFonts(...)`
   output, same custom variants (bold/medium/thin/light/semibold),
   same per-variant overrides (`displayMedium`, `titleSmall`), same
   custom TextStyles (`titleMediumLight`, `dateDividerTextStyle`,
   `emptyChatPlaceholderTextStyle`, `inputTextStyle`, all
   `receivedMessage*`/`sentMessage*`, `userAvatarTextStyle`,
   `userNameTextStyle`).
3. `theme.spacing.default` (= 16), `theme.borders.{inputBorderRadius:
   16, messageBorderRadius: 15, default: 12}`, `theme.insets`,
   `theme.icons` all preserved verbatim.
4. The new surface (`theme.typography.*`, `theme.radius.*`,
   `theme.stroke.*`) is **read by zero consumers** in this slice —
   confirmed by `grep -rn "theme\.typography\.\|theme\.radius\.\|theme\.stroke\." src/`
   returning no hits.
5. The 18 MD3-typescale consumers + 4 `theme.spacing.default`
   consumers are unchanged in count and code.

If the reviewer's reference comparison shows ANY visible delta on the
8 pairs, that is a bug in (1), (2), or (3) — fix the migration table
entry; do NOT reclassify the delta as an intentional design change
(this slice is invisible by definition).

If the dark-mode comparison shows a light flash on mount, the
hydration gate (§4c.4 / D11 / Scenario H) is the design that
eliminates it — that gate is already in place at `App.tsx:213-231`
(`AppWithMigrationWrapper`) and exercised by the App.test.tsx unit
test.

## Reviewer sign-off field

After the 8-pair comparison:

- [ ] iOS Chat (light)      — no visible diff observed
- [ ] iOS Chat (dark)       — no visible diff observed
- [ ] iOS Settings (light)  — no visible diff observed
- [ ] iOS Settings (dark)   — no visible diff observed
- [ ] Android Chat (light)  — no visible diff observed
- [ ] Android Chat (dark)   — no visible diff observed
- [ ] Android Settings (light) — no visible diff observed
- [ ] Android Settings (dark)  — no visible diff observed
- [ ] No light-mode flicker on dark-mode cold start
