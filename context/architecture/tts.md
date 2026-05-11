# TTS Flow

**Purpose**: cumulative architecture truth for the text-to-speech subsystem,
scoped narrowly to the **TTS availability gate** — the boolean every
TTS-aware surface reads to decide whether the feature exists at all.
Bootstrapped from TASK-20260506-1518. Other parts of the TTS subsystem
(engines, downloads, streaming, AppState handling, thinking-stripper) are
intentionally absent and will be added by future stories that touch them.

Convention used in this doc:

- **(C)** = current behaviour, documented from code
- **(D)** = decision (was an open question, now resolved)

---

## 1. Data model

### 1a. `TTSStore` fields participating in the availability gate

```
TTSStore
  isTTSAvailable: boolean                    // (C) MobX computed/getter — derived, no writer
  initialized: boolean                       // (C) idempotency guard for init()

  deviceMeetsMemory: boolean                 // (C) set once in init() from DeviceInfo.getTotalMemory() >= TTS_MIN_RAM_BYTES
  userTTSOverride: boolean | null            // (C) persisted user choice; null = "never set" (first-run sentinel); see D1
```

**Persisted to `AsyncStorage` under name `TTSStore`**: existing
`['autoSpeakEnabled', 'currentVoice', 'supertonicSteps']` plus (C)
`userTTSOverride`.

**Computed at runtime, NOT persisted**: `isTTSAvailable`, `deviceMeetsMemory`.

### 1b. Glossary

- **TTS availability gate** — the single boolean (`isTTSAvailable`) read by every TTS-consuming component to decide whether to render TTS UI or take TTS actions at all. When `false`, components hide themselves and store actions early-return.
- **Memory threshold** — `TTS_MIN_RAM_BYTES` (4 GiB). The total-RAM cutoff above which TTS is considered safe by default.
- **Device meets memory** — `DeviceInfo.getTotalMemory() >= TTS_MIN_RAM_BYTES`. Computed once at boot. RAM doesn't change at runtime, so this is never re-checked.
- **User override** — the persisted user-controlled toggle. Lets curious users on low-memory devices opt in, and lets users on high-memory devices opt out. Survives app restart.
- **First-run** — the boot at which `userTTSOverride` has no persisted value yet (i.e., `null` after hydration).

---

## 1c. External shape

No external / wire-format changes. TTS availability is purely an internal store concern.

---

## 2. Event flow

No event-driven flow involved. The gate is a synchronous read of a derived value. (Streaming events, AppState handling, and download events live in TTSStore but are out of scope for this section.)

---

## 3. State machine

No finite-state lifecycle. The gate is a boolean derivation. (The engine download lifecycle and the playback state machine live in TTSStore but are out of scope for this section.)

---

## 4. Contract

### 4a. The TTS availability gate

The gate is a single boolean, `ttsStore.isTTSAvailable`, that every TTS-aware surface reads.

1. (C) **Final formula**:

   ```
   isTTSAvailable =
     userTTSOverride === true  ? true  :
     userTTSOverride === false ? false :
                                 deviceMeetsMemory   // first-run / null
   ```

   Both directions of the user override take effect: explicit `true` forces the gate open; explicit `false` forces it closed; `null` (no choice yet) falls back to the device default. Scenario D in §6 walks through why a simpler `deviceMeetsMemory || userTTSOverride === true` formula does not cover the opt-out path.

2. (C) On first run (no persisted `userTTSOverride`), the **effective default** of the user override equals `deviceMeetsMemory`. So:
   - Device with ≥ 4 GiB and no user choice yet → `isTTSAvailable === true`.
   - Device with < 4 GiB and no user choice yet → `isTTSAvailable === false`.
3. (C) Once the user toggles the Settings switch, their explicit choice is persisted and used on every subsequent boot.
4. (C) `deviceMeetsMemory` is set exactly once per session, during `init()`, from `DeviceInfo.getTotalMemory()`. It is never re-checked.
5. (C) Setting `userTTSOverride` from `true` to `false` while audio is in flight or while a streaming session is open MUST stop in-flight audio and release the active engine, mirroring how `setAutoSpeak(false)` already releases the engine when auto-speak goes off. Rationale: a user disabling TTS expects audio to stop immediately; leaving 200–450 MB of native engine resources allocated after the user has explicitly opted out is wrong.
6. (C) The user-facing toggle in Settings reflects `userTTSOverride ?? deviceMeetsMemory` so that on first run, the switch correctly shows the device-default state without yet writing a persisted value.

### 4b. Settings toggle (UI contract)

1. (C) Lives inside the `appSettings` Card in `SettingsScreen.tsx`, next to Language and Dark Mode. Rationale: although the default is memory-driven, the feature itself is an app-level user preference — a user looking for "TTS settings" would not navigate to Memory Settings. The row uses the icon-prefixed `labelWithIconContainer` pattern (with `VolumeOnIcon`) to match its App Settings siblings.
2. (C) Renders a single `<Switch>` row using the App Settings card's `switchContainer`/`labelWithIconContainer`/`textContainer`/`Switch` pattern. Icon: `VolumeOnIcon` (parity with `GlobeIcon`, `MoonIcon`, `CpuChipIcon` siblings).
3. (C) Switch value is the **effective** override: `userTTSOverride ?? deviceMeetsMemory`. Toggling it calls a single store action that writes `userTTSOverride` (true or false, never null after the user has touched it).
4. (C) Below-threshold devices (`!deviceMeetsMemory`) display a small helper line under the toggle warning that TTS may not work reliably. The helper line is hidden when `deviceMeetsMemory` is true (no need to caveat the safe path).
5. (C) The toggle is always interactive — users on high-memory devices can turn TTS off too, and users on low-memory devices can opt in. No `disabled` state.

### 4c. Hard invariants

- **I1**: `isTTSAvailable` has exactly one mathematical definition — the formula in §4a.1. No code path may write it directly.
- **I2**: `deviceMeetsMemory` has exactly one writer: `TTSStore.init()`. After init it is immutable for the session.
- **I3**: `userTTSOverride` has exactly one writer: the public store action invoked by the Settings toggle. No internal store path may flip it.
- **I4**: First-run default of the toggle MUST equal `deviceMeetsMemory`. A < 4 GiB device must NOT see TTS UI just because the user hasn't visited Settings yet.
- **I5**: Every existing consumer of `ttsStore.isTTSAvailable` keeps reading the same field with the same semantics. The gate's *definition* is derived; its *interface* is unchanged.
- **I6**: When `userTTSOverride` is set from `true` to `false`, the action initiates `stop()` followed by `ttsRuntime.release()`, mirroring `setAutoSpeak(false)`. Errors are swallowed and logged. The action itself is synchronous; the stop+release runs asynchronously, fire-and-forget.
- **I7**: `userTTSOverride` is persisted to AsyncStorage via the existing `makePersistable` config. No new persistence mechanism. Hydration follows the same `mobx-persist-store` lifecycle as `autoSpeakEnabled`.
- **I8**: `init()` MUST register the `AppState.change` listener and the `chatSessionStore.activeSessionId` reaction unconditionally, regardless of `deviceMeetsMemory`. The four call-site guards in §4d (`play`, `preview`, `onAssistantMessageStart`, `onAssistantMessageComplete`) — plus the component-level guards in `PlayButton` and `VoiceChip` — are the only places `isTTSAvailable` is consulted to decide whether TTS work happens. Lifecycle hooks must run for any session in which a user might opt in.

### 4d. What each component does

| Component                          | Renders                                                                                                                                                             | Does NOT render                                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `SettingsScreen` (TTS toggle row)  | A `<Switch>` whose value is `userTTSOverride ?? deviceMeetsMemory`. A helper line below it iff `!deviceMeetsMemory`.                                                | A new section/Card; copy that promotes TTS; any "advanced" / hidden surfacing.                                             |
| `PlayButton`                       | Returns `null` when `!ttsStore.isTTSAvailable`.                                                                                                                     | Any direct read of memory, override, or threshold.                                                                         |
| `VoiceChip`                        | Returns `null` when `!ttsStore.isTTSAvailable`.                                                                                                                     | Any direct read of memory, override, or threshold.                                                                         |
| `TTSStore.play / preview / onAssistantMessage*` | Early-return when `!isTTSAvailable`. The boolean is derived but read identically from these call sites.                                                 | Direct reads of `userTTSOverride` or `deviceMeetsMemory` for gate decisions (those are implementation detail of the gate). |

### 4e. `init()` lifecycle change

`init()` runs the full `isInstalled()` loop, the `currentVoice` reconciliation, the AppState listener registration, and the session reaction registration unconditionally — i.e., it does NOT early-return on `!deviceMeetsMemory`. Only the *user-visible TTS work* is gated, and that gating lives at the four call-site guards in `TTSStore.ts` (plus the two component-level early-returns).

A low-memory user can flip `userTTSOverride = true` and `isTTSAvailable` becomes true mid-session. At that point those lifecycle hooks MUST already be in place, because:

- Without the AppState listener, backgrounding the app does not release engine RAM (200–450 MB stays allocated, exactly the worst case on a low-memory device).
- Without the session reaction, switching chat sessions does not stop in-flight TTS.
- Without `isInstalled()` checks, the per-engine download states stay at their initial `not_installed` defaults; the user attempting to play would be unable to use an engine that is, in fact, already downloaded.
- Without `currentVoice` reconciliation, a persisted voice whose model files were deleted would crash on first play.
- The reconciliation **stashes the cleared voice id** in `pendingVoiceRestore[engineId]` (a non-persisted private map) before nulling `currentVoice`, so a forced engine re-download (e.g. Kokoro FP16 → FP32 model layout migration) restores the user's previously chosen voice on completion instead of falling back to `voices[0]`. Cleared after restore.

Verified safety of running these on a low-memory device:

- (C) `getEngine(id).isInstalled()` reads disk state only (no engine load). Safe.
- (C) `currentVoice` reconciliation compares persisted voice against download state. Safe — does not load an engine.
- (C) `AppState` listener installs a JS-side callback. Safe.
- (C) `chatSessionStore` reaction calls `this.stop()`, which internally is a no-op when `playbackState.mode === 'idle'` and `currentVoice == null`. Safe.

(See I8 for the corresponding invariant.)

---

## 5. Layer ownership (single-writer rule)

| Field                    | Single writer                                                                                                                            |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `deviceMeetsMemory`      | (C) `TTSStore.init()` — one assignment per session, derived from `DeviceInfo.getTotalMemory()`.                                          |
| `userTTSOverride`        | (C) The public store action invoked by the Settings toggle (`setUserTTSOverride(value: boolean)`). Hydrated by `mobx-persist-store` on construction; that hydration counts as a single equivalent writer (the same pattern `autoSpeakEnabled` already uses). |
| `isTTSAvailable`         | (C) **No writer**. It is a derived value (MobX `get` / computed) defined per the formula in §4a.1.                                       |

Recent bugs / past pain related to multi-writer races: none for these fields specifically. Single-writer discipline is preserved by collapsing the writer set to two underlying fields, each with one canonical writer, and turning the public-facing field into a pure derivation.

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
  PlayButton                  → null
  VoiceChip                   → null
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
- **D2**: `userTTSOverride === false` forces the gate closed, even on high-memory devices. Rationale: opting out must actually disable TTS. Captured in the §4a.1 formula. The toggle is bidirectional once exposed.
- **D3**: No auto-revert if TTS crashes on a low-memory device. Rationale: crash attribution is ambiguous (TTS vs. competing LLM model); silently flipping the user's choice would be worse than honouring it.
- **D4**: Toggle the override, do not clear it back to null. Rationale: simpler mental model (on/off), simpler persisted shape (boolean once written), and — per §6.E — the gate is invariant to "null vs override-equals-default" so there's no behavioural reason to ever write null after first user action.
- **D5**: Place the toggle inside the `appSettings` Card (next to Language and Dark Mode), not the `memorySettings` Card. Rationale: although the default is memory-driven, the feature itself is an app-level user preference — a user reasoning "I need TTS" does not navigate to Memory Settings. The earlier `memorySettings` placement was revised before merge.
- **D6**: `setUserTTSOverride(false)` triggers the same stop-and-release path as `setAutoSpeak(false)` (§4a.5 / I6). Rationale: opting out should free engine RAM immediately for the same reasons disabling auto-speak does.
- **D7**: Use `mobx-persist-store` (the existing mechanism) rather than introducing a new store / new storage layer. Rationale: `autoSpeakEnabled` is already persisted the same way. Adding `userTTSOverride` to the `properties` array is the smallest possible change.
- **D8**: `init()` runs its full lifecycle work unconditionally; gating moves entirely to call-site guards. Rationale: low-memory users who opt in mid-session need the AppState listener and session reaction in place before they ever touch the toggle. Skipping them at `init()` and trying to register them lazily on first opt-in would require either a reaction watching `userTTSOverride` (more state) or coupling the toggle action to lifecycle setup (more code paths). Running them unconditionally is cheap (the listener is dormant until `play()` actually runs an engine) and removes a class of latent bugs. See §4e and I8.

---

## 9. Edge cases

### 9a. Pre-hydration reads of `isTTSAvailable`

Before `mobx-persist-store` finishes hydrating, `userTTSOverride` is `null`. The gate then reduces to `deviceMeetsMemory`, which is itself only set after `init()` runs `getTotalMemory()`. Between app boot and the end of `init()`, `isTTSAvailable` resolves to `false` (initial `deviceMeetsMemory = false`, `userTTSOverride = null`). Components handle this correctly.

### 9b. User toggles during in-flight playback

Covered by I6 / D6. Toggling OFF mid-playback initiates an async stop + release (fire-and-forget). Toggling ON mid-playback is a no-op for current playback (nothing to start; `play()` and the streaming hooks are driven by other inputs). The toggle does not auto-start playback.

### 9c. Pre-existing users (post-migration boot)

Users who installed before this change have no `userTTSOverride` in AsyncStorage. On their next boot, `userTTSOverride` hydrates as `null` and the gate evaluates to `deviceMeetsMemory` — the device-default behaviour. No data migration needed. Users on low-memory devices can now visit Settings and opt in; users on high-memory devices see no behavioural change unless they explicitly opt out.

### 9d. `getTotalMemory()` failure at boot

(C) When `getTotalMemory()` throws, the catch block sets `totalMemory = 0`, so `deviceMeetsMemory` becomes `false`. The user can still opt in via the Settings toggle (the toggle is read directly, not gated on a successful memory read). The helper line will display because `deviceMeetsMemory` is false. This is acceptable — a memory-read failure is rare, and the user explicitly choosing "yes" should still take effect.

### 9e. Multiple rapid toggles

`setUserTTSOverride` is a synchronous MobX action. Rapid toggles produce a sequence of writes; the last one wins. The release-on-OFF path (I6) is async (`stop()` then `ttsRuntime.release()`), but is fire-and-forget with internal error handling, mirroring `setAutoSpeak`'s pattern. No additional debouncing is required.

### 9f. The toggle on a low-memory device that is already opted in

User is on a < 4 GiB device, `userTTSOverride = true`. They visit Settings. The toggle shows ON. The helper line still shows. This is intentional: the user has opted in, but the warning should remain visible so they remember why their device might misbehave. (Helper-line visibility tracks `deviceMeetsMemory`, not the override.)

### 9g. Engine model-layout migration (Kokoro FP16 → FP32 example)

When an engine changes its on-disk file layout (e.g. Kokoro renamed its weight file `model.onnx` → `model_fp32.onnx`), legacy installs report `isInstalled() === false` on next boot, which forces a fresh download. Two safeguards apply:

1. **Voice restore** — `init()` stashes the cleared `currentVoice.id` in `pendingVoiceRestore[engineId]` before nulling it; the next successful download restores that voice when still present in the new voice list, else falls back to `voices[0]`. Persisted selection survives the forced re-download.
2. **Legacy disk reclaim before the gate** — engines that implement the optional `reclaimLegacySpace()` hook have it invoked by `downloadNeuralEngine()` **before** the disk-space preflight, so any space the migration is about to free counts toward the buffered threshold. Borderline devices upgrading from a smaller legacy footprint to a larger new one are not wrongly blocked. The reclaim is idempotent and safe when there is nothing to free.

---

## What this doc is NOT

- Not a redesign of the rest of `TTSStore` (engines, downloads, streaming, AppState handling).
- Not an implementation plan — file edits, the exact action name, the exact l10n keys, the exact testIDs, the exact helper-line copy all belong in the corresponding story's `how.md`.
- Not a UI design doc beyond the contract; visual treatment (icon, spacing, colour, exact placement-within-section) is the implementer's call within the constraints in §4b.
- Not a record of past TTS behaviour changes (those live in commits).
- Not exhaustive coverage of every TTS contract — only the availability gate.

When this doc and the code disagree, the code wins; the same PR that lands the change must update `context/architecture/tts.md`.
