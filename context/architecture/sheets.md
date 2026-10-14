# Sheets

*(pending PR: everything below on keyboard lift, `topInset` and snap-point resolution; on main, sheet inputs do not lift the sheet)*

## Purpose

The shared `Sheet` (`src/components/Sheet`, a `@gorhom/bottom-sheet` `BottomSheetModal`) and how its inputs behave with the keyboard: input registration, the status-bar clamp, percentage snap points, and the scroll view's focused-input reveal. Not covered: what any one sheet does (each flow doc owns its sheets, e.g. `settings.md`, `remote-servers.md`), and the DS sheet in `src/components/ui/Sheet` (redesign layer; it has neither `topInset` nor snap-point resolution).

## Code map

| Path | Role |
| --- | --- |
| `src/components/Sheet/Sheet.tsx` | `BottomSheetModal` wrapper: header, close button, `topInset`, resolved snap points, `keyboardBlurBehavior="restore"`; statics `Sheet.ScrollView`, `.View`, `.Actions`, `.TextInput` (= `BottomSheetTextInput`) |
| `src/components/Sheet/snapPoints.ts` | `resolveSnapPoints` (`'<p>%'` → px against the container height `Sheet` passes, capped), `fullHeightSnapPoint` |
| `src/components/Sheet/SheetScrollView.tsx` | `Sheet.ScrollView`: gorhom `BottomSheetScrollView` plus the focused-input reveal; merges the caller's ref (lists pass one via `renderScrollComponent`) and chains `onScroll` / `onLayout` / `onContentSizeChange` |
| `src/components/Sheet/revealOffset.ts` | Pure minimum-delta scroll target |
| `src/components/Sheet/useClampedLiftRestore.ts` | Works around gorhom's lost restore after a clamped lift (see Traps); wraps `onChange` and `onAnimate` |
| `src/components/Sheet/DismissKeyboardOnRotation.tsx` | Rendered inside the modal; owns the only screen-height read (`Dimensions.get('screen')`, re-read on `change`); on a screen-height change, dismisses the keyboard if this sheet's gorhom keyboard `target` is set (see Traps) |
| `src/components/TextInput/SheetAwareNativeInput.tsx` | `SheetAwareNativeInput` (gorhom `BottomSheetTextInput` inside a sheet, RN `TextInput` outside) and `renderSheetAwareInput`, the Paper `render` the shared `TextInput` uses by default |
| `src/components/PalsHub/AuthSheet/AuthSheet.tsx` | Uses Paper `TextInput` directly, so passes `render={renderSheetAwareInput}` itself |
| `__mocks__/external/@gorhom/bottom-sheet.js` | Suite-wide mock: `useBottomSheetInternal` (null by default, override per test), `BottomSheetScrollView` ref with `scrollTo` / `getInnerViewRef` |

## How it works

Focusing a registered input sets gorhom's keyboard `target`; the following keyboard `SHOWN` lifts the sheet (`keyboardBehavior` default `interactive`). If the sheet plus keyboard fits below `topInset`, the whole sheet translates and nothing scrolls. Otherwise gorhom clamps the sheet top at `topInset` and shrinks the content; `Sheet.ScrollView` sees a smaller `onLayout` height, and on the next frame measures the focused input against its inner view and scrolls by the minimum delta that puts the input's bottom edge inside the viewport (`animated: false`). Content size changes (a growing multiline input) schedule the same reveal. Keyboard hide restores the snap point: gorhom's `restore` for an unclamped lift, `useClampedLiftRestore` for a clamped one.

## Contracts and invariants

- **Rest geometry.** With the keyboard closed, every sheet's top edge is where it was before `topInset` existed: `'<p>%'` resolves to `p/100 ×` `useSafeAreaFrame().height`, the box gorhom's modal host fills, capped at `fullHeightSnapPoint` (`snapPoints.ts`); a frame change (rotation, or a window resize in split screen, freeform, Split View, Stage Manager or Slide Over) re-resolves the points and the `maxDynamicContentSize` cap, as gorhom's own percentages did on main. Numeric points, `displayFullHeight` and dynamic sizing pass through. `snapPoints`, `onChange` and `onAnimate` are destructured out of the props before the `{...props}` spread, so the spread cannot reintroduce the raw value or bypass the wrapped handlers.
- **Focused input visible.** In a sheet, the focused input is fully above the keyboard; a multiline input taller than the viewport keeps its bottom edge visible while typing at the end.
- **Actions reachable.** When lifted, `Sheet.Actions` sits above the keyboard.
- **Status bar.** A lifted sheet never goes above `insets.top` (`topInset` in `Sheet.tsx`).
- **Every sheet input is registered.** Inside a `Sheet`, inputs are the shared `TextInput` (registered by default), `Sheet.TextInput`, or Paper `TextInput` with `render={renderSheetAwareInput}`. A raw RN `TextInput` in a sheet never lifts it.
- **testIDs stay on the native field.** The registration path forwards every Paper render prop, including `testID` and `ref`, so e2e selectors and Paper's focus/blur/clear are unchanged.
- **No lift without own focus.** Detection is per sheet context; a stacked lower sheet never moves for an input in the sheet above. The reveal's `measureLayout` fails for an input outside the scroll view, and failure is a no-op.
- **One engine, no band.** gorhom is the only keyboard engine in a sheet. `Sheet.ScrollView` adds no padding or spacer, never scrolls an input that is already inside the viewport, and never scrolls past the content end (`revealOffset.ts`).

## Traps and decisions

- **Plain inputs never lift a sheet.** gorhom caches a `SHOWN` that arrives with no `target` and does nothing; only `BottomSheetTextInput`'s focus sets the target. Paper renders RN's `TextInput`, so before registration both key sheets stayed put under the keyboard.
- **Paper calls `render` as a plain function** inside its own component. Detection needs its own fiber, so `render` is `renderSheetAwareInput` returning `<SheetAwareNativeInput/>`, never the component itself. A component that renders `<Sheet>` is outside its own sheet context, which is why detection lives at the input's mount site.
- **`interactive` clamps to the container top.** Without `topInset` a tall sheet would be clamped under the status bar (the reason `SearchableSelectSheet` still opts into `extend`; dropping that override is optional now, not done).
- **A clamped lift never restores on its own (gorhom 5.2.8).** `animateToPosition` records a lift it cannot match to a detent with `highestDetentPosition` (pixels) as the index, so `restore` reads `detents[<pixels>]`, gets `undefined` and leaves the sheet at `topInset`. `useClampedLiftRestore` tracks the target index from `onAnimate` (animation start, `-1` for a close) and `onChange` (completion); one frame after `keyboardDidHide` it re-checks that index against the current snap points and, only if it is still past the last detent, calls `snapToIndex(highest)`, the detent gorhom restores to when unclamped. Checking inside the frame means a close or snap that starts before it (swipe or X while lifted) is not undone; snap points are read from a ref so a parent re-render does not cancel the pending frame. Residual risk: a close whose `runOnJS` `onAnimate` reaches JS after the frame. Measured on Xiaomi (Android 16): 50/60/70/80% and full-height sheets back at rest y with back and IME done. Drop the hook when gorhom indexes the clamped lift correctly.
- **`%` snap points resolve against the root frame because of `topInset`.** gorhom normalises percentages against its container, which `topInset` shrinks; resolving in `Sheet` keeps every percentage sheet at its old height. The frame is the `SafeAreaProvider` view's measured size, and only flex-1 wrappers sit between it and the `BottomSheetModalProvider` host, so it equals gorhom's uninset container in every window mode (full screen: 50% on a 2424 px Pixel 9 sits at y=1212). The screen height is not a substitute: in a multi-window pane it exceeds the container and every sheet at 50% or more opens at full pane height. Rotation dismissal stays keyed on screen height, so a frame-only change (divider drag, keyboard-driven resize) never dismisses the keyboard.
- **KASV inside a sheet double-corrects.** `react-native-keyboard-controller`'s `KeyboardAwareScrollView` scrolls by window geometry measured when the keyboard starts moving and appends a `keyboardHeight + 1` spacer, with no knowledge of gorhom's lift; its `scrollTo` can also be reset by gorhom's scroll lock. `Sheet.ScrollView` therefore runs no KASV, and `bottomOffset` is gone from its callers. `Dialog` is not a sheet and keeps KASV.
- **Rotation mid-lift strands the sheet (gorhom 5.2.8).** `heightWithinContainer` is computed only on keyboard show/hide, from import-time `SCREEN_HEIGHT`/`WINDOW_HEIGHT` and the container offset measured at that moment; iOS posts the rotation's keyboard show before the container re-measures, and nothing recomputes it afterwards, so the content collapses to the handle (iPad: blank sheet, header clipped). Keyboard hide recovers it, so `DismissKeyboardOnRotation` dismisses on rotation. The same frozen constants likely explain the ~52 pt landscape lift on iPad (field stays under the keyboard; unfixed, main hides it too).
- **Reveal trigger.** On a clamped lift, Android (Galaxy S23, Android 16) emits a single shrinking `onLayout` for the scroll view, and the reveal scroll is not reverted (the sheet is unlocked after the lift). An unclamped lift emits none, and none is needed. If a platform ever lifts without an `onLayout`, the fallback is a `useAnimatedReaction` on `useBottomSheetInternal(true)?.animatedAnimationState.value.status` going from running to stopped while the keyboard is shown, re-measuring the viewport.
- **`onScroll` is always passed** so the reveal knows the offset; gorhom then crosses to JS once per scroll frame on every `Sheet.ScrollView` (the HF list sheets included). The handler only writes a ref.

## Verification

- Unit: `src/components/Sheet/__tests__/{Sheet,snapPoints,revealOffset,SheetScrollView}.test.ts(x)`, `src/components/TextInput/__tests__/SheetAwareNativeInput.test.tsx`. Jest cannot see the lift, the clamp or the reveal: the gorhom mocks are plain Views. `Sheet.test.tsx` covers the clamped-lift snap-back from a captured `keyboardDidHide` listener; `jest/setup.ts` makes `Keyboard.addListener` return a subscription, since the automocked emitter returns none.
- By hand, keyboard open: Settings › Set Token (clamped lift: header below the status bar, input and Save visible); Settings › Internet Search › Set Key (unclamped: the whole sheet sits on the keyboard); a saved remote server's details, focusing the API key field (Save above the keyboard); About › feedback, typing past the viewport. With the keyboard closed, compare sheet top edges against main.
