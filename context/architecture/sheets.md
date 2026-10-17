# Sheets

## Purpose

The shared `Sheet` (`src/components/Sheet`, a `@gorhom/bottom-sheet` `BottomSheetModal`), its touch handling, and how its inputs behave with the keyboard: input registration, the multi-window opt-out, the status-bar clamp, percentage snap points, and the focused-input reveal. Not covered: individual sheets (their flow docs own them) and the unused DS sheet in `src/components/ui/Sheet`.

## Code map

| Path | Role |
| --- | --- |
| `src/components/Sheet/Sheet.tsx` | `BottomSheetModal` wrapper: header, close button, `topInset`, resolved snap points, `keyboardBlurBehavior="restore"`; statics `Sheet.ScrollView`, `.View`, `.Actions`, `.TextInput` |
| `src/components/Sheet/gorhomInternal.ts` | The only declaration of the gorhom-internal types `SheetContext`, `KeyboardStateValue`, `KeyboardState` |
| `src/components/Sheet/SheetBackground.tsx` | *(pending PR, RN 0.87 stack)* gorhom's default background without its forced `pointerEvents="none"` (Traps); also on `ChatPalModelPickerSheet` |
| `src/components/Sheet/snapPoints.ts` | `resolveSnapPoints` (`'<p>%'` → px against the container height, capped), `fullHeightSnapPoint` |
| `src/components/Sheet/SheetScrollView.tsx` | gorhom `BottomSheetScrollView` plus the focused-input reveal; merges the caller's ref and chains `onScroll` / `onLayout` / `onContentSizeChange`, typed (with `children`) from RN `ScrollViewProps` |
| `src/components/Sheet/revealOffset.ts` | Pure minimum-delta scroll target |
| `src/components/Sheet/screenSize.ts` | One shared `Dimensions` subscription (`useScreenHeight`); the gate `useAppWindowFillsScreen` |
| `src/components/Sheet/DismissKeyboardOnRotation.tsx` | Inside the modal: on a screen-height change, dismisses the keyboard if this sheet's `target` is set |
| `src/components/TextInput/SheetAwareNativeInput.tsx` | RN `TextInput` that registers itself with its sheet (tag in `textInputNodesRef` for the mount, `target` per focus) and dismisses the keyboard on a flip; `renderSheetAwareInput` is the shared `TextInput`'s default Paper `render` |
| `src/components/Sheet/keyboardTarget.ts` | Worklets `setKeyboardTarget` / `clearOwnKeyboardTarget`: UI-runtime writes of `target` alone |
| `src/components/Sheet/Actions.tsx`, `actionsPadding.ts` | `Sheet.Actions`; in a sheet its bottom padding drops the inset the keyboard covers, animated on the UI thread |
| `src/components/PalsHub/AuthSheet/AuthSheet.tsx` | Paper `TextInput` with `render={renderSheetAwareInput}` |
| `src/components/Sheet/__tests__/gorhomVersion.test.ts` | Version tripwire (Traps) |
| `__mocks__/external/@gorhom/bottom-sheet.js` | Suite-wide mock (`useBottomSheetInternal` null by default); `jest/sheetContext.ts` builds an in-sheet context |

## How it works

Focusing a registered input sets gorhom's keyboard `target`; the next keyboard `SHOWN` lifts the sheet (`keyboardBehavior` `interactive`). If sheet plus keyboard fits below `topInset`, the whole sheet translates. Otherwise gorhom clamps the top at `topInset` and shrinks the content; `Sheet.ScrollView` sees a smaller `onLayout` height and, next frame, scrolls by the minimum delta that puts the focused input's bottom edge in view. Content size changes schedule the same reveal. Keyboard hide restores the snap point through gorhom's own `restore`, clamped or not.

When the app window is smaller than the screen (Android split or freeform; iPad Split View, Slide Over or Stage Manager; desktop mode), `SheetAwareNativeInput` does not register a focus, so the sheet stays at its window rest. The gate is read at every focus, never latched.

## Contracts and invariants

- **Rest geometry.** With the keyboard closed, every sheet's top edge is where it was before `topInset`: `'<p>%'` resolves to `p/100 ×` `useSafeAreaFrame().height`, capped at `fullHeightSnapPoint`, re-resolved on a frame change. Numeric points, `displayFullHeight` and dynamic sizing pass through. Only `snapPoints` is destructured before the `{...props}` spread.
- **Focused input visible.** In a full-screen sheet the focused input is fully above the keyboard; a multiline input taller than the viewport keeps its bottom edge visible while typing at the end.
- **Actions reachable.** In a sheet the bar's bottom padding is `10 + max(0, insets.bottom − covered)`, `covered` = `heightWithinContainer` while lifted (`SHOWN` and `animatedPosition` more than 1 above `highestDetentPosition`), else 0. The bar owns `paddingBottom`; the caller's `style` wins otherwise.
- **Status bar.** A lifted sheet never goes above `insets.top`.
- **A tap inside a sheet never closes it**; only the backdrop outside it does.
- **Every sheet input is `SheetAwareNativeInput`, rendering RN `TextInput`; RNGH's `TextInput` is never rendered in a sheet.** So a drag that starts on a field scrolls the sheet on Android. A raw RN `TextInput` never lifts the sheet.
- **Single writer.** `SheetAwareNativeInput` is the only app writer of `target` and `textInputNodesRef`, and never clears a target it does not own; gorhom's own writes carry `target` through.
- **Focus registers in full screen only.** A windowed focus never writes `target`. Blur and unmount clear only their own target; a full-screen blur into another registered field keeps it, a windowed one does not. Exception: Known limitation 5.
- **A flip while focused dismisses the keyboard.** A flip is a render where the gate and the frame width both changed; the focused input calls `Keyboard.dismiss()` in either direction and the hide restores the sheet to window rest. Nothing remounts, so text, refs and selection survive.
- **testIDs stay on the native field.** Every Paper render prop, `testID` and `ref` included, is forwarded.
- **No lift without own focus.** Detection is per sheet context, so a stacked lower sheet never moves for an input above it. A reveal for an input outside the scroll view is a no-op.
- **One engine, no band.** gorhom is the only keyboard engine in a sheet. `Sheet.ScrollView` adds no spacer, never scrolls an input already in view, and never scrolls past the content end.

## Traps and decisions

- **gorhom is pinned at exactly 5.2.14, unpatched** (it uses `StyleSheet.absoluteFill`), on RN 0.87.1, reanimated 4.7.1 / worklets 0.13.0 and RNGH 2.33.1 *(pending PR)*. `gorhomVersion.test.ts` reads the installed and declared versions with `fs` (Jest maps every gorhom path to the mock) and fails on any other; its failure message lists what to re-diff on an upgrade. Also check the background container still passes its fill in `style` and forces `none`, and the content stays a `box-none` sibling above it (`SheetBackground`).
- **gorhom's size reads.** The keyboard offset (`screen height − kb.height − kb.screenY`, screen-space) captures the screen height per present; the container offset (window-space) reads the window height per container layout; `layoutState.window` (iOS interactive-dismiss check) is seeded at import, updated only by a `change` while mounted. `heightWithinContainer` is recomputed only on keyboard `status`/`height` changes, from the container offset of that moment, so a rotation or window change with the keyboard up recomputes nothing.
- **Dimensions listener leak, accepted.** Each present adds a `change` listener gorhom never removes: a small layout state and one trivial UI write per `change`. Xiaomi after 100 presents: rotation frames 12.0% janky, p90 57 ms.
- **Clamped-lift restore is gorhom's own.** 5.2.14 records an off-detent lift with the highest detent's index, so `restore` returns a clamped lift to rest and a hide/show pair mid-restore (Return to the next field) re-lifts.
- **Plain inputs never lift.** gorhom only caches a `SHOWN` with no `target`.
- **Backdrop fall-through (Android)** *(pending PR, RN 0.87 stack)*. With `enableContentPanningGesture={false}` the content has no RNGH handler, and gorhom forces the background to `pointerEvents="none"`. RNGH's hit test passes through a `ViewGroup` with no background, so a blank tap inside reaches the backdrop's `Gesture.Tap` (every phone tried; never on RN 0.82 with RNGH 2.28). `SheetBackground` takes those touches.
- **RNGH `TextInput` blocks drag-to-scroll (Android, RNGH 2.33.1).** gorhom's `BottomSheetTextInput` renders RNGH's field, whose handler won't share with the scroll view's, so sheets render RN's field and register it themselves. `target` writes are UI-runtime and touch `target` alone (a JS `set(fn)` queues a stale whole-state snapshot); the tag is captured at mount, since the host ref is gone by cleanup. A pull down starting on a field does not pan the sheet.
- **Bar inset is dead under a docked keyboard**, which covers the nav bar or home indicator. The padding is keyed on the sheet's position, not `status`, because a gesture release with the keyboard up leaves `SHOWN` at a detent. Every highest detent sits at least `FULL_HEIGHT_TOP_GAP` below the top, so every lift moves the sheet; `extend` sheets and raw numeric points keep the inset. The reveal fires on shrink only, so a restore with a field still focused can scroll by up to the inset.
- **Paper calls `render` as a plain function**, so `render` returns `<SheetAwareNativeInput/>` to get its own fiber; detection sits at the input because a component rendering `<Sheet>` is outside its own sheet context.
- **`interactive` clamps to the container top**, hence `topInset`. `SearchableSelectSheet` still opts into `extend` (optional now); windowed, its search field sits at the sheet top.
- **`%` snap points resolve against the root frame** because gorhom's container is shrunk by `topInset`. The `SafeAreaProvider` frame equals gorhom's uninset container in every window mode; the screen height does not.
- **No KASV inside a sheet.** `KeyboardAwareScrollView` scrolls and pads without knowing gorhom's lift, so it double-corrects. `Dialog` keeps it.
- **`DismissKeyboardOnRotation` is kept.** A rotation with the keyboard up keeps the old `heightWithinContainer` and collapses the content to the handle; without the component, iPhone shows a blank landscape sheet (3/3). Keyboard hide recovers it. Keyed on screen height, so a frame-only change (divider drag, keyboard resize) never dismisses.
- **The windowed opt-out is kept.** The window-space container offset and screen-space keyboard offset disagree in a window: a window the OS moves for the IME (Android bottom pane) blanks the sheet on focus, and an iPad Stage Manager full ↔ windowed change while focused strands a blank sheet without the opt-out (3/3).
  - Gate: `|max(frame) − max(screen)| < 1 ∧ |min(frame) − min(screen)| < 1` dp, frame = `useSafeAreaFrame()`, screen = `Dimensions.get('screen')`. Sorted, because a rotation transiently transposes them; 1 dp, because the frame is float dp of int px; any dimension, so narrower-only windows are opted out too. Misdetection costs a lift, never a blank; in full screen the frame equals the screen and the IME never changes it.
  - Rejected: `BottomSheetTextInput` (RNGH field); `android_keyboardInputMode="adjustResize"` (Android only; strands a sheet lifted when the window goes windowed).
  - The flip dismiss is width-guarded because an IME never changes frame width. Windowed → full also dismisses, so a cached `SHOWN` cannot replay; height-only changes do not (Known limitation 5).
- **Known limitations (recovery: close and reopen the sheet).**
  1. Android, rotating a focused sheet and back: Xiaomi 0/20; Galaxy S23 New Pal stays at the clamp top, keyboard down, in 3/20; OnePlus 6 (Android 11): after a lifted rotation round trip, clamped lifts alternate blank and fine.
  2. iPad, full screen → floating while focused, then back: the sheet sits 22 pt below rest and a refocus lifts the bar 12 pt under the keyboard.
  3. Opened, rotated, then focused: partial lift, field behind the keyboard (Xiaomi 3/3; S23 and OnePlus 6 fine), as the screen height is captured at present.
  4. Android 3-button landscape: the frame excludes the side nav bar, so the gate reads windowed (no lift, never blank). Accepted; unmeasurable on the fleet (its landscape keyboards float or go fullscreen).
  5. A height-only window change while focused keeps the old registration until a real blur (Android back does not blur): full-screen focus moved to a bottom pane blanks (Xiaomi 3/3, S23 1/1); windowed focus gets no lift after split → full (Xiaomi 3/3).
- **Reveal trigger.** A clamped lift emits one shrinking `onLayout` on Android; an unclamped lift needs none.
- **`onScroll` is always passed** for the reveal's offset: one JS crossing per scroll frame.

## Verification

- Unit: `src/components/Sheet/__tests__/` (including `gorhomVersion`), `SheetAwareNativeInput.test.tsx`, and the `EnhancedSearchBar`, `SearchableSelectSheet` and `AuthSheet` suites. Jest cannot see the lift, clamp, reveal or hit test.
- Perf (pending PR, `yarn test:perf`): `Sheet.perf-test.tsx` and `ChatPalModelPickerSheet.perf-test.tsx` (open and close from the owner's state; the picker is conditionally mounted as `ChatView` does, so its scenario measures mount and unmount, not the `isVisible` effects). Under the gorhom mock `present`/`close` do nothing and content always renders, so they count only the visibility handling: 3 commits each.
- By hand, full screen: Set Token (clamped: header below the status bar, Save visible, at rest after hide); Set Key (unclamped); feedback, typing past the viewport; New Pal name → Return stays lifted; on Android a drag from a field scrolls the sheet; a lifted bar sits 10 dp/pt above the keyboard; closed sheets' top edges match main; a blank tap in HF search, language select or the Pal picker keeps it open.
- By hand, windowed (Android split and freeform; iPad floating and tiled): Set Token, Set Key, the author filter and a searchable select never lift and never blank, field to field or dragging the divider.
- By hand, with a field focused: rotating a lifted New Pal or HF token sheet on iPhone dismisses the keyboard and draws header and fields; Android `am start --windowingMode 5` / `1` on the running app and iPad Stage Manager full ↔ windowed close the keyboard and never leave a blank sheet.
