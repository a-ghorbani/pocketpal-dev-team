# WHAT — TASK-20260506-1518: Settings toggle to enable/disable TTS, defaulting based on device memory

Delta on `context/architecture/tts.md` (bootstrap — file does not yet exist; see §0 below).

This WHAT is intentionally narrow. It documents only the **TTS availability gate** — the single boolean every TTS consumer reads to decide whether the feature exists at all — and the small `init()` lifecycle change required to make the gate honour an opt-in safely. It does NOT attempt to document the rest of the TTS subsystem (engines, streaming, downloads, voices in detail, thinking-stripper). Those will accrue in `tts.md` lazily as future stories touch them.

---

## Conventions

- **(C)** = current behaviour, documented from code
- **(P)** = proposal, open for challenge
- **(?)** = open question, decision needed
- **(D)** = decision (resolved)

---

## 0. Drift check

There is no existing `context/architecture/tts.md`. This story bootstraps it. The implementer absorbs the §1–§9 content of this delta into a new `context/architecture/tts.md` in the same PR (per the architecture-library lifecycle).

Verified against code at `worktrees/TASK-20260506-1518/`:

- (C) `TTS_MIN_RAM_BYTES = 4 * 1024 * 1024 * 1024` — `src/services/tts/constants.ts:9`.
- (C) `isTTSAvailable` declared with default `false` — `src/store/TTSStore.ts:78`.
- (C) `isTTSAvailable` is set exactly once, inside `init()`, from `DeviceInfo.getTotalMemory() >= TTS_MIN_RAM_BYTES` — `src/store/TTSStore.ts:140-151`.
- (C) `init()` early-returns when `available === false` at `src/store/TTSStore.ts:153-155`. The early return skips: per-engine `isInstalled()` checks, `currentVoice` reconciliation, `AppState.change` listener registration, and the `chatSessionStore.activeSessionId` reaction. (See §4e for why this matters under the new gate.)
- (C) `init()` is fire-and-forget at app boot — `App.tsx:71-75`.
- (C) `makePersistable` persists `['autoSpeakEnabled', 'currentVoice', 'supertonicSteps']` only — `src/store/TTSStore.ts:123-127`.
- (C) Consumers reading `ttsStore.isTTSAvailable`:
  - `src/components/TextMessage/PlayButton.tsx:34` (early-return null)
  - `src/components/VoiceChip/VoiceChip.tsx:39, 61` (early-return null)
  - Internal guards in `TTSStore.ts:337` (`play`), `:394` (`preview`), `:441` (`onAssistantMessageStart`), `:551` (`onAssistantMessageComplete`)
- (C) Settings screen uses `Card.Title` sections; `memorySettings` Card spans `SettingsScreen.tsx:732-811` and follows the `switchContainer` + `<Switch>` + `<Divider />` pattern repeatedly.

No drift detected against the orchestrator's pointers. The §0 list above is the complete set of code locations this delta touches, directly or by contract.

---

## 1. Data model

### 1a. `TTSStore` fields participating in the availability gate

```
TTSStore
  // Existing — current behaviour
  isTTSAvailable: boolean                    // (C) was directly written by init(); (P) becomes a computed/derived value, see §5
  // Existing internal — (C)
  initialized: boolean                       // idempotency guard for init()

  // (P) New
  deviceMeetsMemory: boolean                 // (P) set once in init() from DeviceInfo.getTotalMemory() >= TTS_MIN_RAM_BYTES; replaces the direct write to isTTSAvailable
  userTTSOverride: boolean | null            // (P) persisted user choice; null = "never set" (first-run sentinel); see D1
```

**Persisted to `AsyncStorage` under name `TTSStore`**: existing `['autoSpeakEnabled', 'currentVoice', 'supertonicSteps']` plus (P) `userTTSOverride`.

**Computed at runtime, NOT persisted**: `isTTSAvailable`, `deviceMeetsMemory`.

### 1b. Glossary

- **TTS availability gate** — the single boolean (`isTTSAvailable`) read by every TTS-consuming component to decide whether to render TTS UI or take TTS actions at all. When `false`, components hide themselves and store actions early-return.
- **Memory threshold** — `TTS_MIN_RAM_BYTES` (4 GiB). The total-RAM cutoff above which TTS is considered safe by default.
- **Device meets memory** — `DeviceInfo.getTotalMemory() >= TTS_MIN_RAM_BYTES`. Computed once at boot. RAM doesn't change at runtime, so this is never re-checked.
- **User override** — the persisted user-controlled toggle. Lets curious users on low-memory devices opt in, and lets users on high-memory devices opt out. Survives app restart.
- **First-run** — the boot at which `userTTSOverride` has no persisted value yet (i.e., `null` after hydration).

---

## 1c. External shape

No external / wire-format changes. TTS availability is purely an internal store concern. (No change.)

---

## 2. Event flow

No event-driven flow involved. The gate is a synchronous read of a derived value. (No change to streaming events, AppState handling, or download events.)

---

## 3. State machine

No finite-state lifecycle. The gate is a boolean derivation. (Engine download lifecycle and playback state machine are out of scope for this WHAT — they live in TTSStore but are unaffected by this change.)

---

## 4. Contract

### 4a. The TTS availability gate

The gate is a single boolean, `ttsStore.isTTSAvailable`, that every TTS-aware surface reads.

1. (P) **Final formula**:

   ```
   isTTSAvailable =
     userTTSOverride === true  ? true  :
     userTTSOverride === false ? false :
                                 deviceMeetsMemory   // first-run / null
   ```

   Both directions of the user override take effect: explicit `true` forces the gate open; explicit `false` forces it closed; `null` (no choice yet) falls back to the device default. Scenario D in §6 walks through why a simpler `deviceMeetsMemory || userTTSOverride === true` formula does not cover the opt-out path.

2. (P) On first run (no persisted `userTTSOverride`), the **effective default** of the user override equals `deviceMeetsMemory`. So:
   - Device with ≥ 4 GiB and no user choice yet → `isTTSAvailable === true` (unchanged from today).
   - Device with < 4 GiB and no user choice yet → `isTTSAvailable === false` (unchanged from today).
3. (P) Once the user toggles the Settings switch, their explicit choice is persisted and used on every subsequent boot.
4. (P) `deviceMeetsMemory` is set exactly once per session, during `init()`, from `DeviceInfo.getTotalMemory()`. It is never re-checked. (Same lifetime semantics the current `isTTSAvailable` already has.)
5. (P) Setting `userTTSOverride` from `true` to `false` while audio is in flight or while a streaming session is open MUST stop in-flight audio and release the active engine, mirroring how `setAutoSpeak(false)` already releases the engine when auto-speak goes off (see `TTSStore.ts:215-227`). Rationale: a user disabling TTS expects audio to stop immediately; leaving 200–450 MB of native engine resources allocated after the user has explicitly opted out is wrong.
6. (P) The user-facing toggle in Settings reflects `userTTSOverride ?? deviceMeetsMemory` so that on first run, the switch correctly shows the device-default state without yet writing a persisted value.

### 4b. Settings toggle (UI contract)

1. (P) Lives inside an existing `Card` section in `SettingsScreen.tsx`. Per the intent brief, it is placed where it "looks natural — no new section, not promoted, not hidden." `memorySettings` is the most natural fit (toggle is gated on memory; that section already groups memory-related switches). The exact section choice is the planner's call within these constraints.
2. (P) Renders a single `<Switch>` row using the existing `switchContainer`/`textContainer`/`Switch` pattern already used by `useMlock`, `useMmap`, and `weight-repacking` switches in the same file (see `SettingsScreen.tsx:738-805`).
3. (P) Switch value is the **effective** override: `userTTSOverride ?? deviceMeetsMemory`. Toggling it calls a single store action that writes `userTTSOverride` (true or false, never null after the user has touched it).
4. (P) Below-threshold devices (`!deviceMeetsMemory`) display a small helper line under the toggle warning that TTS may not work reliably. The exact copy is the planner/implementer's to finalise; intent gives "Your device's memory is low — this may not work reliably." as a reference. The helper line is hidden when `deviceMeetsMemory` is true (no need to caveat the safe path).
5. (P) The toggle is always interactive — users on high-memory devices can turn TTS off too, and users on low-memory devices can opt in. No `disabled` state.

### 4c. Hard invariants

- **I1**: `isTTSAvailable` has exactly one mathematical definition — the formula in §4a.1. No code path may write it directly.
- **I2**: `deviceMeetsMemory` has exactly one writer: `TTSStore.init()`. After init it is immutable for the session.
- **I3**: `userTTSOverride` has exactly one writer: the public store action invoked by the Settings toggle. No internal store path may flip it.
- **I4**: First-run default of the toggle MUST equal `deviceMeetsMemory`. A < 4 GiB device must NOT see TTS UI just because the user hasn't visited Settings yet. (Preserves today's safe default.)
- **I5**: Every existing consumer of `ttsStore.isTTSAvailable` keeps reading the same field with the same semantics. The gate's *definition* changes; its *interface* does not. (Components in §0 list and the four internal guards in `TTSStore.ts` need zero behavioural changes.)
- **I6**: When `userTTSOverride` is set from `true` to `false`, the action initiates `stop()` followed by `ttsRuntime.release()`, mirroring `setAutoSpeak(false)` (`TTSStore.ts:215-227`). Errors are swallowed and logged. The action itself is synchronous; the stop+release runs asynchronously, fire-and-forget.
- **I7**: `userTTSOverride` is persisted to AsyncStorage via the existing `makePersistable` config. No new persistence mechanism. Hydration follows the same `mobx-persist-store` lifecycle as `autoSpeakEnabled`.
- **I8**: `init()` MUST register the `AppState.change` listener and the `chatSessionStore.activeSessionId` reaction unconditionally, regardless of `deviceMeetsMemory`. The four call-site guards in §4d (`play`, `preview`, `onAssistantMessageStart`, `onAssistantMessageComplete`) — plus the component-level guards in `PlayButton` and `VoiceChip` — are now the only places `isTTSAvailable` is consulted to decide whether TTS work happens. Lifecycle hooks must run for any session in which a user might opt in. (See §4e for rationale.)

### 4d. What each component does

| Component                          | Renders                                                                                                                                                                          | Does NOT render                                                                                                            |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `SettingsScreen` (TTS toggle row)  | (P) A `<Switch>` whose value is `userTTSOverride ?? deviceMeetsMemory`. (P) A helper line below it iff `!deviceMeetsMemory`.                                                     | A new section/Card; copy that promotes TTS; any "advanced" / hidden surfacing.                                             |
| `PlayButton`                       | (C) Returns `null` when `!ttsStore.isTTSAvailable`. (P) Unchanged — same field, new definition.                                                                                  | Any direct read of memory, override, or threshold.                                                                         |
| `VoiceChip`                        | (C) Returns `null` when `!ttsStore.isTTSAvailable`. (P) Unchanged — same field, new definition.                                                                                  | Any direct read of memory, override, or threshold.                                                                         |
| `TTSStore.play / preview / onAssistantMessage*` | (C) Early-return when `!isTTSAvailable`. (P) Unchanged behaviour; the boolean is now derived but read identically.                                                  | Direct reads of `userTTSOverride` or `deviceMeetsMemory` for gate decisions (those are implementation detail of the gate). |

### 4e. `init()` lifecycle change

Today (`TTSStore.ts:153-155`), when `available === false`, `init()` early-returns BEFORE the `isInstalled()` checks, the `currentVoice` reconciliation, the `AppState.change` listener registration, and the `chatSessionStore.activeSessionId` reaction registration. Under the current code that's safe because a low-memory device can never flip availability on at runtime. Under this WHAT, a low-memory user can flip `userTTSOverride = true` and `isTTSAvailable` becomes true mid-session — at which point those skipped lifecycle hooks MUST already be in place, because:

- Without the AppState listener, backgrounding the app does not release engine RAM (200–450 MB stays allocated, exactly the worst case on a low-memory device).
- Without the session reaction, switching chat sessions does not stop in-flight TTS.
- Without `isInstalled()` checks, the per-engine download states stay at their initial `not_installed` defaults; the user attempting to play would be unable to use an engine that is, in fact, already downloaded.
- Without `currentVoice` reconciliation, a persisted voice whose model files were deleted would crash on first play.

**Required change (P)**: `init()` runs the full `isInstalled()` loop, the `currentVoice` reconciliation, the AppState listener registration, and the session reaction registration unconditionally — i.e., it does NOT early-return on `!deviceMeetsMemory`. Only the *user-visible TTS work* is gated, and that gating now lives at the four call-site guards in `TTSStore.ts` (plus the two component-level early-returns), as it already did in the existing code. The early `return` at `TTSStore.ts:153-155` is removed.

Verified safety of running these on a low-memory device:

- (C) `getEngine(id).isInstalled()` reads disk state only (no engine load). Safe.
- (C) `currentVoice` reconciliation (`TTSStore.ts:176-183`) compares persisted voice against download state. Safe — does not load an engine.
- (C) `AppState` listener installs a JS-side callback. Safe.
- (C) `chatSessionStore` reaction calls `this.stop()`, which internally is a no-op when `playbackState.mode === 'idle'` and `currentVoice == null`. Safe.

(See I8 for the corresponding invariant.)

---

## 5. Layer ownership (single-writer rule)

| Field                    | Single writer                                                                                                                            |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `deviceMeetsMemory`      | (P) `TTSStore.init()` — one assignment per session, derived from `DeviceInfo.getTotalMemory()`.                                          |
| `userTTSOverride`        | (P) The public store action invoked by the Settings toggle (e.g. `setUserTTSOverride(value: boolean)`). Hydrated by `mobx-persist-store` on construction; that hydration counts as a single equivalent writer (the same pattern `autoSpeakEnabled` already uses). |
| `isTTSAvailable`         | (P) **No writer**. It becomes a derived value (MobX `get` / computed) defined per the formula in §4a.1. The previous direct assignment in `init()` is removed. |

Recent bugs / past pain related to multi-writer races: none for these fields specifically — the current `isTTSAvailable` already has a single writer (`init()`). This change preserves that discipline by collapsing the new writer set to two underlying fields, each with one canonical writer, and turning the public-facing field into a pure derivation.

**Deferred cleanups**: none for this story.

---

## 6. Canonical scenarios

Each scenario is the observable outcome a future test or manual QA pass must produce. Concrete state in, observable state / UI out.

### A. High-memory device, first run (default ON)

```
Initial:
  DeviceInfo.getTotalMemory() = 6 GiB
  AsyncStorage TTSStore: { autoSpeakEnabled: false, currentVoice: null, supertonicSteps: 5 }
  (no userTTSOverride persisted)

After ttsStore.init():
  deviceMeetsMemory   = true
  userTTSOverride     = null  (effective: true, mirrors deviceMeetsMemory)
  isTTSAvailable      = true

Observable:
  PlayButton                  → renders
  VoiceChip                   → renders
  Settings TTS toggle value   → ON
  Settings TTS helper line    → hidden
```

### B. Low-memory device, first run (default OFF, helper visible)

```
Initial:
  DeviceInfo.getTotalMemory() = 3 GiB
  (no userTTSOverride persisted)

After ttsStore.init():
  deviceMeetsMemory   = false
  userTTSOverride     = null  (effective: false, mirrors deviceMeetsMemory)
  isTTSAvailable      = false

Observable:
  PlayButton                  → null  (unchanged from today)
  VoiceChip                   → null  (unchanged from today)
  Settings TTS toggle value   → OFF
  Settings TTS helper line    → visible

Lifecycle hooks active (per I8 / §4e):
  AppState listener registered, session reaction active,
  isInstalled() checks ran, currentVoice reconciled.
  (No engine is loaded — gate is closed — so the listener has nothing to release yet.)
```

### C. Low-memory device, user opts in

```
Starting from scenario B, user toggles the switch ON.

  setUserTTSOverride(true)
    → userTTSOverride = true   (persisted)
    → isTTSAvailable  = true   (override === true → forced true)

Observable:
  PlayButton                  → renders
  VoiceChip                   → renders
  Settings TTS toggle value   → ON
  Settings TTS helper line    → still visible (still a low-memory device)

Backgrounding the app now:
  AppState listener (already registered per I8) fires, stops audio,
  releases engine. Engine RAM is freed.

After app restart:
  AsyncStorage TTSStore.userTTSOverride = true is hydrated
  → isTTSAvailable = true (persisted opt-in survives restart)
```

### D. High-memory device, user opts out

```
Starting from scenario A, user toggles the switch OFF.

  setUserTTSOverride(false)
    → action initiates stop() + ttsRuntime.release()  (per I6, fire-and-forget)
    → userTTSOverride = false  (persisted)
    → isTTSAvailable  = false  (override === false → forced false)

Observable:
  PlayButton                  → null
  VoiceChip                   → null
  Settings TTS toggle value   → OFF
  Settings TTS helper line    → hidden (high-memory device)

After app restart: persisted false hydrates, gate stays closed.
```

A naive formula `isTTSAvailable = deviceMeetsMemory || userTTSOverride === true` would evaluate to `true` here (because `deviceMeetsMemory` is `true`), making opt-out a no-op. The §4a.1 formula explicitly handles `userTTSOverride === false` to force the gate closed.

### E. User toggles back from opt-in to off (low-memory device)

```
Starting from scenario C (low-memory device, userTTSOverride = true), user toggles OFF.

  setUserTTSOverride(false)
    → action initiates stop() + ttsRuntime.release()  (per I6)
    → userTTSOverride = false  (persisted)
    → isTTSAvailable  = false  (override === false → forced false)

Observable:
  PlayButton                  → null
  VoiceChip                   → null
  Settings TTS toggle value   → OFF
  Settings TTS helper line    → still visible (still a low-memory device)

  Note: we do NOT clear back to null. Once the user has touched the toggle their explicit
  choice is recorded as a boolean. This is intentional — see D4. The behavioural difference
  between null and (override == deviceMeetsMemory) is invisible to the gate, so the simpler
  rule wins.
```

---

## 7. State signals

| Signal              | Set by                                                | Read by                                             | True when                                                                  |
| ------------------- | ----------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------- |
| `isTTSAvailable`    | derived (no writer)                                   | `PlayButton`, `VoiceChip`, internal store guards    | `userTTSOverride === true` OR (`userTTSOverride == null` AND `deviceMeetsMemory`) |
| `deviceMeetsMemory` | `TTSStore.init()` once per session                    | `SettingsScreen` (helper-line visibility, toggle default), `isTTSAvailable` derivation | `getTotalMemory() >= TTS_MIN_RAM_BYTES`                                    |
| `userTTSOverride`   | `setUserTTSOverride(...)` from Settings toggle        | `SettingsScreen` (toggle value), `isTTSAvailable` derivation | persisted user choice                                                      |

Overlap check: `isTTSAvailable` is fully derived from the other two — no redundancy. The Settings toggle reads two signals (override and `deviceMeetsMemory`) only because it must distinguish "user hasn't chosen" from the device default; that's necessary, not duplication.

---

## 8. Decisions

- **D1**: Use `boolean | null` for `userTTSOverride` (null = "never set"), not a separate "hasUserChosen" flag. Rationale: collapses two pieces of state into one, matches `mobx-persist-store`'s natural hydration semantics (missing AsyncStorage key → field retains its initial `null` value, which is exactly what we want for first-run detection), and the Settings UI already needs to fall back to `deviceMeetsMemory` when no user choice exists.
- **D2**: `userTTSOverride === false` forces the gate closed, even on high-memory devices. Rationale: opting out must actually disable TTS. Captured in the §4a.1 formula. (Intent brief explicitly supports both directions: "let curious users on lower-memory devices opt in, while keeping the safe default behaviour for everyone else" implies the toggle is bidirectional once exposed.)
- **D3**: No auto-revert if TTS crashes on a low-memory device. Rationale: explicit in the intent brief. Crash attribution is ambiguous (TTS vs. competing LLM model); silently flipping the user's choice would be worse than honouring it.
- **D4**: Toggle the override, do not clear it back to null. Rationale: simpler mental model (on/off), simpler persisted shape (boolean once written), and — per §6.E — the gate is invariant to "null vs override-equals-default" so there's no behavioural reason to ever write null after first user action.
- **D5**: Place the toggle inside `memorySettings` Card. Rationale: the toggle is conceptually about a memory-driven default, the Card already uses the matching switch row pattern, and the orchestrator's pointer flagged it as the natural section. Final placement is the planner's call within "no new section, not promoted, not hidden" — but if the planner picks a different existing Card, they must justify why it's more natural than `memorySettings`.
- **D6**: `setUserTTSOverride(false)` triggers the same stop-and-release path as `setAutoSpeak(false)` (§4a.5 / I6). Rationale: opting out should free engine RAM immediately for the same reasons disabling auto-speak does.
- **D7**: Use `mobx-persist-store` (the existing mechanism) rather than introducing a new store / new storage layer. Rationale: `autoSpeakEnabled` is already persisted the same way. Adding `userTTSOverride` to the `properties` array is the smallest possible change.
- **D8**: `init()` runs its full lifecycle work unconditionally; gating moves entirely to call-site guards. Rationale: low-memory users who opt in mid-session need the AppState listener and session reaction in place before they ever touch the toggle. Skipping them at `init()` and trying to register them lazily on first opt-in would require either a reaction watching `userTTSOverride` (more state) or coupling the toggle action to lifecycle setup (more code paths). Running them unconditionally is cheap (the listener is dormant until `play()` actually runs an engine) and removes a class of latent bugs. See §4e and I8.

---

## 9. Edge cases

### 9a. Pre-hydration reads of `isTTSAvailable`

Before `mobx-persist-store` finishes hydrating, `userTTSOverride` is `null`. The gate then reduces to `deviceMeetsMemory`, which is itself only set after `init()` runs `getTotalMemory()`. Between app boot and the end of `init()`, `isTTSAvailable` resolves to `false` (initial `deviceMeetsMemory = false`, `userTTSOverride = null`). This matches today's behaviour exactly: today, `isTTSAvailable` defaults to `false` and only flips to true after `init()` completes (`TTSStore.ts:78, 148-151`). Components handle this correctly today and continue to handle it correctly under the new derivation. No race introduced.

### 9b. User toggles during in-flight playback

Covered by I6 / D6. Toggling OFF mid-playback initiates an async stop + release (fire-and-forget). Toggling ON mid-playback is a no-op for current playback (nothing to start; `play()` and the streaming hooks are driven by other inputs). The toggle does not auto-start playback.

### 9c. Pre-existing users (post-migration boot)

Users who installed before this change have no `userTTSOverride` in AsyncStorage. On their next boot, `userTTSOverride` hydrates as `null` and the gate evaluates to `deviceMeetsMemory` — exactly today's behaviour. No data migration needed. Users on low-memory devices can now visit Settings and opt in; users on high-memory devices see no behavioural change unless they explicitly opt out.

### 9d. `getTotalMemory()` failure at boot

(C) Today, when `getTotalMemory()` throws, the catch block sets `totalMemory = 0`, so `available` becomes false (`TTSStore.ts:142-148`). (P) Under the new derivation, `deviceMeetsMemory` becomes `false` for the same reason. The user can still opt in via the Settings toggle (the toggle is read directly, not gated on a successful memory read). The helper line will display because `deviceMeetsMemory` is false. This is acceptable — a memory-read failure is rare, and the user explicitly choosing "yes" should still take effect.

### 9e. Multiple rapid toggles

`setUserTTSOverride` is a synchronous MobX action. Rapid toggles produce a sequence of writes; the last one wins. The release-on-OFF path (I6) is async (`stop()` then `ttsRuntime.release()`), but is fire-and-forget with internal error handling, mirroring `setAutoSpeak`'s pattern (`TTSStore.ts:221-226`). No additional debouncing is required.

### 9f. The toggle on a low-memory device that is already opted in

User is on a < 4 GiB device, `userTTSOverride = true`. They visit Settings. The toggle shows ON. The helper line still shows. This is intentional: the user has opted in, but the warning should remain visible so they remember why their device might misbehave. (Helper-line visibility tracks `deviceMeetsMemory`, not the override. See 4b.4.)

---

## 10. What this doc is NOT

- Not a redesign of the rest of `TTSStore` (engines, downloads, streaming, AppState handling).
- Not an implementation plan — file edits, the exact action name, the exact l10n keys, the exact testIDs, the exact helper-line copy all belong in `how.md`.
- Not a UI design doc beyond the contract; visual treatment (icon, spacing, colour, exact placement-within-section) is the implementer's call within the constraints in §4b.
- Not a record of past TTS behaviour changes (those live in commits).
- Not exhaustive coverage of every TTS contract — only the availability gate.

When this doc and the code disagree, the code wins; the same PR that lands the change must update `context/architecture/tts.md`.

**Cleanup reminders**: none.

---

## 11. Alternatives considered

- **Single persisted boolean `ttsEnabled` with default seeded from `deviceMeetsMemory` at first launch.** Rejected. `mobx-persist-store` hydrates synchronously from AsyncStorage at construction time, but `DeviceInfo.getTotalMemory()` is async and runs later in `init()`. Seeding the persisted boolean from `deviceMeetsMemory` would require either (a) writing the seed AFTER the first `init()` completes — meaning we cannot tell "user has explicitly toggled this to match the device default" from "we just seeded it" on the next boot, defeating future logic that might want that distinction, or (b) computing memory synchronously, which the API doesn't support. The tristate (`true | false | null`) sidesteps the race entirely: hydration produces `null` on first run, and we never need to write a seed.

- **Reaction-driven write to `isTTSAvailable` (keep it as a stored field, mutate it from a `reaction` over the two inputs).** Rejected. Three writers (`init`, the reaction, `setUserTTSOverride`) is strictly more state and strictly more code than a derived `get`. MobX `computed` semantics already give us memoised, reactive recomputation for free.

- **Computed `get isTTSAvailable()` derived from `deviceMeetsMemory` and `userTTSOverride` (chosen).** Wins because: (i) zero writers — I1 is enforced by the type system, not by discipline; (ii) every existing consumer's read site stays identical (I5); (iii) MobX reactivity is the existing mechanism in this store, no new patterns introduced.

---

## Appendix: required edits to `context/architecture/tts.md` on PR merge

Bootstrap the file. The implementer absorbs §1–§9 of this delta into the new architecture file, replacing every (P) marker with (C) and every (D) marker as-is (decisions remain decisions). The file should match the template in `templates/what-template.md`, scoped narrowly to the availability gate. Other sections of `tts.md` (engines, streaming, downloads, AppState handling, thinking-stripper) are intentionally absent and will be added by future stories that touch them.

---

## Review History

### Round 1 — architect-critic: HAS_BLOCKERS

- **BLOCKER 1 — Opt-in path on low-memory devices skips listener registration**: **FIXED**. Added §4e (`init()` lifecycle change) explaining the existing early-return at `TTSStore.ts:153-155` and why it must be removed under this WHAT, including a per-call safety check for each of the four lifecycle steps. Added **I8** requiring `init()` to run lifecycle work unconditionally. Added **D8** capturing the rationale for "run lifecycle unconditionally vs. lazy registration on first opt-in." Updated §0 drift-check entry on the early-return so the contract is explicit. Updated scenarios B and C to note the lifecycle hooks are active. Updated the appendix to absorb §1–§9 (was §1–§6).

- **BLOCKER 2 — §4a.1 formula contradicts §6.D / §7 / D2**: **FIXED**. §4a.1 now contains the corrected tristate formula directly. **I1** now points at "the formula in §4a.1" instead of restating the wrong version. §6.D walks through the naive formula's failure as motivation for the corrected one rather than as the formula's first definition. §6.E renamed to "User toggles back from opt-in to off (low-memory device)" with a matching example.

- **CONCERN 1 — No alternatives enumerated**: **FIXED**. Added §11 with three alternatives: single persisted boolean (rejected for hydration-race reason given), reaction-driven write (rejected for strictly-more-state reason), and the chosen computed derivation.

- **CONCERN 2 — I6 says "before the action returns" but mirrors a fire-and-forget caller**: **FIXED**. **I6** reworded: "the action initiates `stop()` followed by `ttsRuntime.release()`, mirroring `setAutoSpeak(false)`. Errors are swallowed and logged. The action itself is synchronous; the stop+release runs asynchronously, fire-and-forget." §6.D and §9b updated to use the same wording.

- **SUGGESTION 1 — D1 wording on hydration semantics**: **FIXED**. D1 reworded: "missing AsyncStorage key → field retains its initial `null` value, which is exactly what we want for first-run detection."

- **SUGGESTION 2 — §6.E example mismatched with narrative**: **FIXED**. Renamed scenario E to "User toggles back from opt-in to off (low-memory device)" and tightened the example to match.
