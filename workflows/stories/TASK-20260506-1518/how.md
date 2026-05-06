# Implementation Plan: Settings toggle to enable/disable TTS, defaulting based on device memory

**Purpose**: land WHAT §1–§9 — turn `isTTSAvailable` into a derived value over `deviceMeetsMemory` + `userTTSOverride`, persist the override via `mobx-persist-store`, expose a single toggle row in the existing `memorySettings` Card of `SettingsScreen`, and bootstrap `context/architecture/tts.md` from §1–§9 of WHAT in the same PR. Reference WHAT sections by number; do not re-derive design content here.

---

## Metadata

- **Task ID**: TASK-20260506-1518
- **Worktree**: `./worktrees/TASK-20260506-1518`
- **Branch**: `feature/TASK-20260506-1518`
- **Native Changes**: NO
- **Visual Confirmation**: YES
- **Intent Brief**: `./workflows/stories/TASK-20260506-1518/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260506-1518/what.md`
- **Architecture doc(s) being updated**: `./context/architecture/tts.md` (NEW — this PR seeds the file from WHAT §1–§9)
- **Status**: draft

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — `TTSStore` field reshape: introduce `deviceMeetsMemory`, `userTTSOverride`, computed `isTTSAvailable` | DONE | `48be284` | Combined with Step 2 in one commit. Consumer test files (PlayButton, VoiceChip, TTSSetupSheet) and mock store updated alongside, since the getter-shape made `isTTSAvailable` readonly at the type level. |
| Step 2 — `init()` lifecycle change: drop the `!available` early return; assign `deviceMeetsMemory` only | DONE | `48be284` | Same commit as Step 1. The lifecycle hooks (isInstalled, AppState listener, session reaction) now run unconditionally per I8. |
| Step 3 — `setUserTTSOverride` action with stop+release on OFF | DONE | `b50c904` | Mirrors `setAutoSpeak(false)`'s fire-and-forget stop+release path. |
| Step 4 — Add `userTTSOverride` to `makePersistable` properties | DONE | `a8d269e` | No migration needed — pre-existing users hydrate `null` and fall through to `deviceMeetsMemory`. |
| Step 5 — Update mock store and TTSStore unit tests for the new derivation, persistence, and lifecycle | DONE | `afc4fec` | Mock now mirrors the real shape (`isTTSAvailable` is a getter, inputs are `deviceMeetsMemory`/`userTTSOverride`) — deviation from the HOW's "keep it a plain boolean" note, required to satisfy TypeScript. New tests cover §6.A–E, §9a, §9d, §9e, plus a structural assertion for I7/D7. |
| Step 6 — Add l10n strings for toggle label, description, and helper line | DONE | `6a2626d` | Three keys in `settings`: `ttsAvailability`, `ttsAvailabilityDescription`, `ttsAvailabilityLowMemoryWarning`. `yarn l10n:validate` passes. |
| Step 7 — Render the TTS toggle row in `SettingsScreen` `memorySettings` Card | DONE | `17f1ac8` | Inserted between Memory Mapping and the Android-only Weight Repacking block, matching the surrounding switch row pattern. |
| Step 8 — `SettingsScreen` tests for high-memory ON/OFF, low-memory OFF/ON, helper-line visibility | DONE | `9ca3af6` | Five tests covering §6.A–D and §9f. |
| Step 9 — Bootstrap `context/architecture/tts.md` from WHAT §1–§9 (in dev-team repo) | DONE | `75f405f` (dev-team repo) | All `(P)` markers promoted to `(C)`; D1–D8 preserved. The `(?)` legend bullet was dropped (no open questions remain). |
| Cleanup reminders applied | n/a | - | none — WHAT §10 / Cleanup reminders is empty |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/store/TTSStore.ts` | edit | §1a, §4a, §4e, §5, I1–I3, I6–I8 |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | edit | §4b, §4d, D5 |
| `src/locales/en.json` | edit | §4b (UI strings only — en is the canonical source; other languages stay untouched per Weblate workflow) |
| `__mocks__/stores/ttsStore.ts` | edit | §1a (add `deviceMeetsMemory`, `userTTSOverride`, `setUserTTSOverride`) |
| `src/store/__tests__/TTSStore.test.ts` | edit | tests for §4a, §4e, §6.A–E, §9a, §9c, §9d, §9e |
| `src/screens/SettingsScreen/__tests__/SettingsScreen.test.tsx` | edit | tests for §6.A, §6.B, §6.C, §6.D, §9f |
| `context/architecture/tts.md` | add (in dev-team repo, NOT submodule) | seeds the new flow doc from WHAT §1–§9 |

No native files touched (`NATIVE_CHANGES=NO`).

---

## Implementation Steps

### Step 1: Reshape `TTSStore` fields — introduce `deviceMeetsMemory`, `userTTSOverride`, and a computed `isTTSAvailable`

**Implements**: WHAT §1a, §4a.1, §5, invariants I1, I2.

**Files**:

- `src/store/TTSStore.ts` — replace the directly-assigned `isTTSAvailable: boolean = false` field with the two-input derivation.

**Approach**:

1. Remove the field declaration `isTTSAvailable: boolean = false` (currently `TTSStore.ts:78`).
2. Add observable field `deviceMeetsMemory: boolean = false` in its place. Comment: "Set once in init() from getTotalMemory() >= TTS_MIN_RAM_BYTES; never re-checked. See architecture/tts.md §1a."
3. Add observable field `userTTSOverride: boolean | null = null`. Comment: "Tristate persisted user choice. null = not set (mirrors deviceMeetsMemory). See architecture/tts.md §4a, D1."
4. Add a MobX `get isTTSAvailable(): boolean` accessor implementing the formula in WHAT §4a.1: `userTTSOverride === true ? true : userTTSOverride === false ? false : deviceMeetsMemory`. Place it directly after the field declarations so call sites reading `this.isTTSAvailable` continue to work without change (I5).
5. `makeAutoObservable` already converts getters to `computed`s by default — no extra annotation required. Verify by running the existing TTSStore tests; the `isTTSAvailable` reads in `play`, `preview`, `onAssistantMessageStart`, `onAssistantMessageComplete` should compile unchanged.

**Verification**:

- `yarn lint src/store/TTSStore.ts` passes.
- `yarn typecheck` passes.
- `yarn test src/store/__tests__/TTSStore.test.ts` — pre-existing tests still pass with no edits, because `init()` is updated in Step 2 to write `deviceMeetsMemory` and the getter resolves identically to the old field on those device-only inputs.

### Step 2: `init()` lifecycle change — write `deviceMeetsMemory`, drop the `!available` early-return

**Implements**: WHAT §4e, invariant I8, decision D8, edge case §9d.

**Files**:

- `src/store/TTSStore.ts` (`init()`, currently `TTSStore.ts:134-197`).

**Approach**:

1. After the `getTotalMemory()` try/catch block, replace the `runInAction` that wrote `this.isTTSAvailable = available` with `this.deviceMeetsMemory = totalMemory >= TTS_MIN_RAM_BYTES`. Keep the `runInAction` wrapper.
2. Remove the `if (!available) { return; }` block at `TTSStore.ts:153-155`. The remainder of `init()` (`isInstalled()` parallel loop, `currentVoice` reconciliation, `AppState.addEventListener`, `chatSessionStore.activeSessionId` reaction) now runs unconditionally for every device — see WHAT §4e for the per-call safety check.
3. Leave the four call-site guards (`play`, `preview`, `onAssistantMessageStart`, `onAssistantMessageComplete`) as-is. They already read `this.isTTSAvailable`, which now resolves through the getter (I5).
4. The `getTotalMemory` failure branch (`totalMemory = 0`) already produces `deviceMeetsMemory = false`; covered by §9d — the override path remains usable.

**Verification**:

- `yarn lint src/store/TTSStore.ts` passes.
- `yarn typecheck` passes.
- `yarn test src/store/__tests__/TTSStore.test.ts` — the existing low-memory test at `TTSStore.test.ts:171-179` (`registers no listeners`) WILL fail because we now register listeners unconditionally; this is intentional and Step 5 updates the assertion to match I8.

### Step 3: Add `setUserTTSOverride` action with stop+release on OFF

**Implements**: WHAT §4a.5, §4b.3, invariants I3 and I6, decision D6.

**Files**:

- `src/store/TTSStore.ts` — add new public action.

**Approach**:

1. Add a public method `setUserTTSOverride(value: boolean): void` immediately after `setAutoSpeak` (so the two related actions sit together — WHAT §4a.5 explicitly mirrors `setAutoSpeak`'s pattern).
2. Body: capture previous effective state via `const wasAvailable = this.isTTSAvailable;`. Then assign `this.userTTSOverride = value;`. If `wasAvailable && !value`, fire-and-forget `this.stop().then(() => ttsRuntime.release()).catch(err => console.warn('[TTSStore] release on TTS opt-out failed:', err));` — same shape as `setAutoSpeak(false)` at `TTSStore.ts:217-227`.
3. The action itself stays synchronous (I6); the stop+release runs async, fire-and-forget. No `runInAction` needed because the assignment is a single observable write and `makeAutoObservable` wraps the method as an action.
4. Do NOT clear `userTTSOverride` back to `null` (D4) — once the user has touched the toggle, the explicit boolean is recorded.

**Verification**:

- `yarn lint src/store/TTSStore.ts` passes.
- `yarn typecheck` passes.
- New unit tests added in Step 5 cover scenarios §6.C, §6.D, §6.E.

### Step 4: Persist `userTTSOverride` via the existing `mobx-persist-store` config

**Implements**: WHAT §1a (persisted shape), invariant I7, decision D7.

**Files**:

- `src/store/TTSStore.ts` (`makePersistable` call in the constructor at `TTSStore.ts:123-127`).

**Approach**:

1. Append `'userTTSOverride'` to the `properties` array in `makePersistable`. The array becomes `['autoSpeakEnabled', 'currentVoice', 'supertonicSteps', 'userTTSOverride']`.
2. No migration is needed: pre-existing users have no `userTTSOverride` key in AsyncStorage; on next boot the field hydrates as its initial value (`null`), which by the formula in §4a.1 falls through to `deviceMeetsMemory` — exactly today's behaviour (§9c).
3. No new storage layer or new store added — the field rides on the existing `TTSStore` `AsyncStorage` blob (D7).

**Verification**:

- `yarn typecheck` passes.
- Hydration-survival is covered by the unit test in Step 5 that constructs two stores in sequence and asserts the second sees the persisted value (mirrors the existing pattern in `TTSStore.test.ts` for `autoSpeakEnabled`).

### Step 5: Update mock store and TTSStore unit tests for the new derivation, persistence, and lifecycle

**Implements**: tests for WHAT §4a (formula), §4e (lifecycle), §6.A, §6.B, §6.C, §6.D, §6.E, §9a (pre-hydration), §9c (post-migration boot), §9d (`getTotalMemory` failure), §9e (rapid toggles).

**Files**:

- `__mocks__/stores/ttsStore.ts` — extend the mock with `deviceMeetsMemory`, `userTTSOverride`, `setUserTTSOverride`.
- `src/store/__tests__/TTSStore.test.ts` — update existing tests; add new tests for the override formula, lifecycle change, persistence, and stop+release on OFF.

**Approach**:

1. **Mock update** (`__mocks__/stores/ttsStore.ts`):
   - Add observable fields `deviceMeetsMemory: boolean = false` and `userTTSOverride: boolean | null = null`.
   - `isTTSAvailable` is currently a plain boolean; keep it that way (mocks need to be settable from tests, see existing pattern at `PlayButton.test.tsx:36, 45`). Existing tests that write `ttsStore.isTTSAvailable = true` continue to work.
   - Add `setUserTTSOverride: jest.fn()` and register it in the `makeAutoObservable` non-observable list.
2. **Existing TTSStore tests to update**:
   - `'sets isTTSAvailable=false when total memory < 4 GiB and registers no listeners'` (`TTSStore.test.ts:171-179`) — rename to `'sets deviceMeetsMemory=false when total memory < 4 GiB; isTTSAvailable=false; lifecycle hooks STILL register (I8)'`. Assert `mockAddEventListener` IS now called (the negation flips per §4e).
   - `'is idempotent: second init() does not re-run memory check or re-register listeners'` (`TTSStore.test.ts:194-203`) — keep as-is; idempotency is preserved.
   - `'no-ops when isTTSAvailable is false'` family in `play()`, `onAssistantMessageStart`, `onAssistantMessageComplete` — keep as-is; the call-site guards still gate the work, only the lifecycle is unconditional.
3. **New tests to add** (group under a new `describe('availability gate (override formula)')` block; place after the existing `'memory gate'` block):
   - **§6.A** — high-memory, no override → `deviceMeetsMemory=true`, `userTTSOverride=null`, `isTTSAvailable=true`.
   - **§6.B** — low-memory, no override → `deviceMeetsMemory=false`, `userTTSOverride=null`, `isTTSAvailable=false`. Assert the AppState listener IS registered (I8).
   - **§6.C** — low-memory + `setUserTTSOverride(true)` → `isTTSAvailable=true`. PlayButton-level rendering is covered separately in component tests; here we just assert the boolean.
   - **§6.D** — high-memory + `setUserTTSOverride(false)` → `isTTSAvailable=false` (proves the naive `||` formula is wrong; covers D2). Also assert `mockSystemStop` (or current engine's stop) was called and `ttsRuntime.release` was invoked (mirrors the existing `setAutoSpeak(false)` release-pattern test, if one exists; otherwise add an inline mock — see `TTSStore.ts:217-227` for the pattern this matches).
   - **§6.E** — start in §6.C state, then `setUserTTSOverride(false)` → `isTTSAvailable=false`, override is `false` (NOT `null` — D4).
   - **§9a — pre-hydration read** — construct a fresh store, do NOT call `init()`, assert `isTTSAvailable === false` (matches today's pre-init default; the getter resolves to `deviceMeetsMemory=false ∧ override=null → false`).
   - **§9d — `getTotalMemory` failure** — `(DeviceInfo.getTotalMemory as jest.Mock).mockRejectedValueOnce(new Error('boom'))`, run `init()`, assert `deviceMeetsMemory=false`. Then `setUserTTSOverride(true)` → `isTTSAvailable=true` (override path still works after a memory-read failure).
   - **§9e — rapid toggles** — call `setUserTTSOverride(true)` then `setUserTTSOverride(false)` then `setUserTTSOverride(true)` synchronously; assert final `userTTSOverride === true` and `isTTSAvailable === true` (last write wins; no debouncing).
   - **Persistence (§9c)** — assert that after `setUserTTSOverride(true)` the new value is on the in-memory observable; the actual AsyncStorage round-trip is owned by `mobx-persist-store` itself (the existing `makePersistable` mock at `TTSStore.test.ts:4-6` short-circuits this) so we only assert the property is included in the persisted set by inspecting `properties` via a new test that imports `makePersistable` mock and checks the call args.
4. Group all the new lifecycle assertions under a `describe('init() lifecycle (I8 — runs unconditionally)')` block confirming that for `2 * GIB` device: `mockAddEventListener` called once, `isInstalled` called for all three engines, `chatSessionStore.activeSessionId` reaction registered (existing test at `TTSStore.test.ts:763-803` already covers parallel `isInstalled`; extend the low-memory device path).

**Verification**:

- `yarn lint __mocks__/stores/ttsStore.ts src/store/__tests__/TTSStore.test.ts` passes.
- `yarn typecheck` passes.
- `yarn test src/store/__tests__/TTSStore.test.ts` — all old + new tests pass.

### Step 6: Add l10n strings for the toggle label, description, and helper line

**Implements**: WHAT §4b (UI contract) — UI strings only.

**Files**:

- `src/locales/en.json` — only `en.json` is editable here per the Weblate workflow (other languages are managed by translators on Weblate; CI's `validate-l10n.js` will flag missing keys but translators add them).

**Approach**:

1. Inside the `settings` namespace (after the `weightRepackingDescription` line at `en.json:89` so the new keys sit next to the other memory-section strings), add:
   - `"ttsAvailability": "Text-to-speech"` — toggle label. Short, neutral, mirrors the `"Use Memory Lock"` / `"Memory Mapping"` style of adjacent rows.
   - `"ttsAvailabilityDescription": "Read assistant replies aloud."` — the always-visible description below the label, matching the `useMlockDescription` / `useMmapDescription` pattern (every other switch in the Card has a description; not having one would look out of place).
   - `"ttsAvailabilityLowMemoryWarning": "Your device's memory is low — this may not work reliably."` — the conditional helper line that renders only when `!deviceMeetsMemory` (WHAT §4b.4 quotes this exact reference copy from the intent brief).
2. Do NOT touch any other `src/locales/*.json` file. Translators pick up the new keys via Weblate; the lazy-load fallback (`_.merge({}, enData, langData)`) means missing translations render the English string until Weblate fills them in.

**Verification**:

- `node scripts/validate-l10n.js` passes (the script tolerates missing-in-other-languages because it only validates *integrated* languages' placeholder consistency, not key parity).
- `yarn typecheck` passes (`typeof en` widens automatically; new keys flow into the `l10n` type).

### Step 7: Render the TTS toggle row in `SettingsScreen` `memorySettings` Card

**Implements**: WHAT §4b (UI contract), §4d (Settings row), decision D5.

**Files**:

- `src/screens/SettingsScreen/SettingsScreen.tsx` — add a switch row inside the `memorySettings` Card.

**Approach**:

1. Add an import for `ttsStore` next to the other store imports near the top of the file (the `modelStore`/`uiStore` import line — search for `modelStore` to locate it).
2. In the Memory Settings Card (`SettingsScreen.tsx:732-811`), insert the new row immediately AFTER the "Memory Mapping" switch row's closing `<Divider />` (`SettingsScreen.tsx:779`) and BEFORE the Android-only "Enable Weight Repacking" block. Rationale: this places it between the unconditional rows and the platform-conditional block, which keeps the iOS layout coherent (the row appears in a stable position regardless of platform).
3. Use the existing `<View style={styles.settingItemContainer}>` → `<View style={styles.switchContainer}>` → `<View style={styles.textContainer}>` → label `<Text variant="titleMedium" style={styles.textLabel}>` + description `<Text variant="labelSmall" style={styles.textDescription}>` → `<Switch />` pattern, copied verbatim from the "Use Memory Lock" row (`SettingsScreen.tsx:738-752`) so spacing, typography, and layout match.
4. Switch props:
   - `testID="tts-availability-switch"` (matches the project's kebab-case testID convention used by `use-mlock-switch`, `use-mmap-switch`, `weight-repacking-switch`).
   - `value={ttsStore.userTTSOverride ?? ttsStore.deviceMeetsMemory}` — per WHAT §4b.3.
   - `onValueChange={value => ttsStore.setUserTTSOverride(value)}`.
   - No `disabled` prop (WHAT §4b.5 explicitly forbids it).
5. Conditionally render the helper line: `{!ttsStore.deviceMeetsMemory && (<Text variant="labelSmall" style={styles.textDescription}>{l10n.settings.ttsAvailabilityLowMemoryWarning}</Text>)}`. Place it inside the `textContainer`, after the existing description `Text` — same anchor the `useMmapFalseDescription` would naturally sit at if the surrounding code had a precedent (it does not; the helper line is a small, self-contained addition consistent with `labelSmall` / `textDescription` styling).
6. Add a `<Divider />` after the new row, mirroring every other row in this Card. The existing trailing `modelReloadNotice` text at `SettingsScreen.tsx:807-809` continues to apply (turning TTS on/off does not require model reload, but the notice is for the Card as a whole — leave it alone).
7. The `SettingsScreen` component is already wrapped with `observer` (verified by reading other `ttsStore`/`modelStore` reads in the file), so the row reactively re-renders on `setUserTTSOverride` writes without further change.

**Pre-hydration note** (incorporates the WHAT round-2 critic SUGGESTION): on first render after a cold start, `userTTSOverride` may briefly be `null` and `deviceMeetsMemory` may briefly be `false` (before `init()` finishes the `getTotalMemory()` await). The toggle will render as OFF and the helper line as visible during this window — typically a few milliseconds. This matches today's pre-hydration `isTTSAvailable=false` behaviour (§9a) and is acceptable; no spinner / placeholder is required.

**Verification**:

- `yarn lint src/screens/SettingsScreen/SettingsScreen.tsx` passes.
- `yarn typecheck` passes.
- Manual: render the screen — the row appears between Memory Mapping and Weight Repacking (Android) / between Memory Mapping and the modelReloadNotice (iOS).

### Step 8: `SettingsScreen` tests for high-memory ON/OFF, low-memory OFF/ON, helper-line visibility

**Implements**: tests for WHAT §6.A (high-memory default ON, helper hidden), §6.B (low-memory default OFF, helper visible), §6.C (low-memory opt-in), §6.D (high-memory opt-out), §9f (low-memory + opt-in keeps helper visible).

**Files**:

- `src/screens/SettingsScreen/__tests__/SettingsScreen.test.tsx` — add four new tests in a `describe('TTS availability toggle')` block; they follow the existing `'toggles Auto Offload/Load switch'` pattern (`SettingsScreen.test.tsx:101-113`).

**Approach**:

The mock `ttsStore` from `__mocks__/stores/ttsStore.ts` is auto-injected into the screen via `jest/setup.ts` (`mockTTSStore`). Tests mutate `ttsStore.deviceMeetsMemory` and `ttsStore.userTTSOverride` directly and call `getByTestId('tts-availability-switch')` to find the row.

1. **§6.A — high-memory, no override → switch ON, helper hidden**
   - Set `ttsStore.deviceMeetsMemory = true; ttsStore.userTTSOverride = null;` before render.
   - Assert `switch.props.value === true`.
   - Assert `queryByText(l10n.settings.ttsAvailabilityLowMemoryWarning)` returns `null`.
2. **§6.B — low-memory, no override → switch OFF, helper visible**
   - Set `ttsStore.deviceMeetsMemory = false; ttsStore.userTTSOverride = null;`.
   - Assert `switch.props.value === false`.
   - Assert `getByText(l10n.settings.ttsAvailabilityLowMemoryWarning)` is truthy.
3. **§6.C — low-memory opt-in calls `setUserTTSOverride(true)`**
   - Same initial state as §6.B.
   - `fireEvent(switch, 'valueChange', true)`.
   - Assert `ttsStore.setUserTTSOverride` was called with `true`.
4. **§6.D — high-memory opt-out calls `setUserTTSOverride(false)`**
   - Set `ttsStore.deviceMeetsMemory = true; ttsStore.userTTSOverride = null;`.
   - `fireEvent(switch, 'valueChange', false)`.
   - Assert `ttsStore.setUserTTSOverride` was called with `false`.
5. **§9f — low-memory + opt-in still shows helper line**
   - Set `ttsStore.deviceMeetsMemory = false; ttsStore.userTTSOverride = true;`.
   - Render and assert: `switch.props.value === true` AND helper-line `getByText` is truthy (helper tracks `deviceMeetsMemory`, NOT the override).

After each test, reset `ttsStore.userTTSOverride = null; ttsStore.deviceMeetsMemory = false;` in `afterEach` — the existing `beforeEach` at `SettingsScreen.test.tsx:21` runs `jest.clearAllMocks()` which resets the `setUserTTSOverride` `jest.fn()` but does NOT reset observable fields.

**Verification**:

- `yarn lint src/screens/SettingsScreen/__tests__/SettingsScreen.test.tsx` passes.
- `yarn typecheck` passes.
- `yarn test src/screens/SettingsScreen/__tests__/SettingsScreen.test.tsx` — all old + new tests pass.

### Step 9: Bootstrap `context/architecture/tts.md` from WHAT §1–§9

**Implements**: AGENTS.md "Architecture library" rule — every PR that changes behaviour described in `context/architecture/*.md` must update the relevant doc in the same PR. There is no existing `tts.md`; this PR seeds it (per WHAT §0 and the closing appendix).

**Files**:

- `context/architecture/tts.md` — NEW file in the **dev-team repo** (`/Users/aghorbani/codes/pocketpal-dev-team/context/architecture/tts.md`). Note: this is NOT inside `repos/pocketpal-ai/` — the architecture library lives in the dev-team control plane, not the submodule. The dev-team repo edit lands in the dev-team commit, not the pocketpal-ai PR.

**Approach**:

1. Copy the content of WHAT §1–§9 into a new `tts.md`. Match the structure used by `context/architecture/benchmark-matrix.md`: a one-line `**Purpose**:` opener, the `(C)` / `(D)` legend, then numbered sections.
2. Convert markers per the architecture lifecycle rule:
   - Every `(P)` becomes `(C)` — the proposal lands in this PR, so it is now current truth.
   - Every `(D)` stays `(D)` — decisions remain decisions.
   - Confirm zero `(?)` markers remain (WHAT has none — verified via `grep '(?)' workflows/stories/TASK-20260506-1518/what.md` returns empty).
3. Scope: include only sections §1–§9. Do NOT carry over §0 (drift check; story-scoped), §10 (what-the-doc-is-not; story-scoped), §11 (alternatives considered; story-scoped), or the Review History.
4. Add a short opening paragraph: "Bootstrapped from TASK-20260506-1518. Scoped narrowly to the **TTS availability gate** — the boolean that determines whether TTS UI renders at all. Other parts of the TTS subsystem (engines, downloads, streaming, AppState handling, thinking-stripper) are intentionally absent and will be added by future stories that touch them."
5. Leave `workflows/stories/TASK-20260506-1518/what.md` intact — it stays as the archival story-scoped delta (per the architecture-library lifecycle README).

**Verification**:

- `grep -n '(P)' context/architecture/tts.md` returns no matches.
- `grep -n '(?)' context/architecture/tts.md` returns no matches.
- `(D)` markers from WHAT D1–D8 are preserved.
- The file renders cleanly when previewed (markdown linter, if any, passes).

---

## Testable-Contract Coverage

| Contract item | Verified by |
| ------------- | ----------- |
| §6.A — high-memory device, first run (default ON) | `TTSStore.test.ts` new test in `'availability gate (override formula)'` block + `SettingsScreen.test.tsx` `'high-memory, no override → switch ON, helper hidden'` |
| §6.B — low-memory device, first run (default OFF, helper visible) | `TTSStore.test.ts` new test (memory + lifecycle assertions per I8) + `SettingsScreen.test.tsx` `'low-memory, no override → switch OFF, helper visible'` |
| §6.C — low-memory device, user opts in | `TTSStore.test.ts` `setUserTTSOverride(true)` test + `SettingsScreen.test.tsx` `'low-memory opt-in calls setUserTTSOverride(true)'` |
| §6.D — high-memory device, user opts out (formula proves opt-out actually closes the gate) | `TTSStore.test.ts` `setUserTTSOverride(false)` test asserting `isTTSAvailable === false` AND `stop` + `ttsRuntime.release` invoked + `SettingsScreen.test.tsx` `'high-memory opt-out calls setUserTTSOverride(false)'` |
| §6.E — user toggles back from opt-in to off (low-memory) | `TTSStore.test.ts` chained `setUserTTSOverride(true)` then `setUserTTSOverride(false)` test |
| §9a — pre-hydration reads of `isTTSAvailable` | `TTSStore.test.ts` new test: fresh store, no `init()`, `isTTSAvailable === false` |
| §9c — pre-existing users (post-migration boot) | Implicitly covered by §6.A / §6.B passing without any migration code; unit test asserts `userTTSOverride` initial value is `null` and the gate matches `deviceMeetsMemory` |
| §9d — `getTotalMemory` failure at boot | `TTSStore.test.ts` new test: `mockRejectedValueOnce`, then `setUserTTSOverride(true)` → `isTTSAvailable === true` |
| §9e — multiple rapid toggles | `TTSStore.test.ts` new test: three synchronous `setUserTTSOverride` calls; final value wins |
| §9f — low-memory device that is already opted in | `SettingsScreen.test.tsx` `'low-memory + opt-in still shows helper line'` |
| I8 — `init()` runs lifecycle work unconditionally | `TTSStore.test.ts` updated low-memory test: assert `mockAddEventListener` IS called, `isInstalled` IS called, session reaction IS registered |

Note: invariants I1–I7 are structural (single-writer, derived field, persistence config); they're enforced by code shape, not by individual tests. The §6.A–E tests collectively prove they hold.

---

## Native Verification (NATIVE_CHANGES=NO)

Not required. No native modules, `package.json`, `ios/`, `android/`, Podfile, or build.gradle changes.

---

## Visual Confirmation (Visual Confirmation=YES)

The reviewer captures three screenshots covering the two device classes and the helper-line conditional. The simulator's reported total memory determines `deviceMeetsMemory` — the iOS Simulator typically reports 8 GiB+ (high-memory class), so the low-memory shots require either (a) a low-memory Android emulator (Pixel 2 with 1.5 GiB RAM AVD reports < 4 GiB) or (b) a small dev-only override. Both paths are acceptable; the reviewer picks one and notes it.

```json
[
  {
    "label": "High-memory device — toggle ON, helper line hidden (§6.A)",
    "prompt": "Open Settings, scroll to the Memory Settings card.",
    "look_for": "A 'Text-to-speech' switch row sits between 'Memory Mapping' and either 'Enable Weight Repacking' (Android) or the 'Model reload needed' notice (iOS). The switch is ON. No 'Your device's memory is low' helper line is visible."
  },
  {
    "label": "Low-memory device — toggle OFF, helper line visible (§6.B)",
    "prompt": "Open Settings on a < 4 GiB device (e.g., Pixel 2 emulator with 1.5 GiB RAM), scroll to the Memory Settings card.",
    "look_for": "The 'Text-to-speech' switch row is visible. The switch is OFF. Below the row's description, a smaller helper line reads 'Your device's memory is low — this may not work reliably.'"
  },
  {
    "label": "Low-memory device — opted in, switch ON, helper still visible (§9f)",
    "prompt": "On the same low-memory device as above, tap the Text-to-speech switch to turn it ON. Stay on the Settings screen.",
    "look_for": "The switch is now ON. The 'Your device's memory is low — this may not work reliably.' helper line is STILL visible (it tracks the device, not the user choice). Returning to a chat with a model reply should now show the PlayButton (gate is open)."
  }
]
```

---

## Deferred Items

WHAT §10 / Cleanup reminders is empty. No deferred items.

The following are explicitly out of scope for this story and will not be implemented here (even if a reader is tempted):

- Crash-recovery / auto-revert when TTS fails on a low-memory device. Intent brief D3 explicitly forbids this; rationale documented in WHAT §8 D3.
- Documentation of the rest of the TTS subsystem (engines, downloads, streaming, AppState, thinking-stripper) in `tts.md`. WHAT §10 deliberately keeps the bootstrapped doc narrow to the availability gate; future stories accrue.

---

## What this plan is NOT

- Not a design doc — design lives in `what.md`.
- Not a justification — `intent-brief.md` is where the request lives.
- Not a redesign of how `init()` or `setAutoSpeak` are structured beyond what §4e and I6 require.
- Not exhaustive — only the steps the implementer needs. The implementer reads WHAT for invariants, not this plan.

---

## Last Agent Handoff

```yaml
from_agent: implementer
to_agent: tester
timestamp: 2026-05-06T16:00:00Z
status: "Implementation complete; all 9 steps done; ready for tester."
completed:
  - Step 1+2: TTSStore field reshape + init() lifecycle change (commit 48be284)
  - Step 3: setUserTTSOverride action with stop+release (commit b50c904)
  - Step 4: persist userTTSOverride via makePersistable (commit a8d269e)
  - Step 5: mock + TTSStore unit tests (commit afc4fec; 74 tests passing)
  - Step 6: l10n strings in en.json (commit 6a2626d)
  - Step 7: SettingsScreen toggle row (commit 17f1ac8)
  - Step 8: SettingsScreen tests (commit 9ca3af6; 17 tests passing)
  - Step 9: context/architecture/tts.md bootstrap (commit 75f405f in dev-team repo)
verification:
  lint: PASS (changed files clean)
  typecheck: PASS
  related_tests: PASS (112/112 across TTSStore, SettingsScreen, PlayButton, VoiceChip, TTSSetupSheet)
  l10n_validate: PASS
  native_build: N/A (NATIVE_CHANGES=NO)
deviations:
  - Step 1's verification block expects typecheck to pass after Step 1 alone,
    but converting `isTTSAvailable` from a public field to a getter makes it
    readonly at the type level. Existing tests (PlayButton, VoiceChip,
    TTSSetupSheet) wrote `ttsStore.isTTSAvailable = true|false` directly,
    which now TS-errors. Updated those tests to write `deviceMeetsMemory`
    and `userTTSOverride` instead — semantically identical via the new
    derivation. Combined with Step 2 in a single commit so the worktree is
    typecheck-clean at every commit boundary.
  - Step 5's mock-store note suggested keeping `isTTSAvailable` as a plain
    settable boolean on the mock. That works at runtime but TypeScript types
    consumers against the *real* TTSStore, so writes from tests still
    TS-error. Kept the mock structurally aligned with the real store
    (getter + writable inputs); tests now mutate the inputs.
next_steps:
  - Tester: write any additional unit/integration tests not already covered.
  - Visual confirmation captures (3 listed in §"Visual Confirmation" of how.md)
    are pending — environment did not support running the simulator/emulator.
    Pipeline-reviewer can flag.
blockers: []
context_for_next_agent: |
  All 9 plan steps are DONE with atomic commits. Architecture doc
  (context/architecture/tts.md) committed in the dev-team repo.
  Existing 112-test surface across TTSStore, SettingsScreen, PlayButton,
  VoiceChip, and TTSSetupSheet all passes. The §6.A-E + §9a/d/e/f
  scenarios from WHAT have direct test coverage; I1-I8 invariants are
  enforced structurally (single-writer, getter-only isTTSAvailable,
  unconditional lifecycle in init()).
```
