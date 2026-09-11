# TTS Flow

## Purpose

Text-to-speech: the availability gate, on-demand neural-engine model downloads (and why they force re-downloads), the single-slot native runtime, and the Supertonic language setting. The streaming-hook callers belong to `chat-flow.md`; Settings layout to `settings.md`. `asr.md` twins this gate/download pattern.

## Code map

| Path | Role |
| --- | --- |
| `src/store/TTSStore.ts` | `ttsStore`: the gate (`isTTSAvailable`), playback state, per-engine download state, streaming hooks, persisted preferences |
| `src/services/tts/constants.ts` | download URLs, file manifests, estimated bytes, `TTS_MIN_RAM_BYTES`, `SUPERTONIC_MODEL_VERSION` and the sentinel filename |
| `src/services/tts/engines/{supertonic,kokoro,kitten,system}/index.ts` | `Engine` implementations: `isInstalled`, `downloadModel`, `reclaimLegacySpace`, `loadInto`, `play`, `playStreaming` |
| `src/services/tts/runtime.ts` | `ttsRuntime`: one native engine loaded at a time; serialises `acquire` / `release` / `stop` |
| `src/services/tts/engineRegistry.ts` | `getEngine`, `getAllEngines` (singleton engines) |
| `src/services/tts/streamingHandle.ts`, `thinkingStripper.ts` | streaming into the engine; `<think>` stripping |
| `src/components/TTSSetupSheet/` | setup sheet; `HeroRow.tsx` holds the steps control and the Supertonic language picker; `engineMeta.ts` holds `sizeMb` labels |
| `src/components/SearchableSelectSheet/` | the searchable sheet the language picker opens |
| `src/components/TextMessage/PlayButton.tsx`, `src/components/VoiceChip/VoiceChip.tsx` | gate consumers; both render `null` when the gate is closed |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | the availability switch (`tts-availability-switch`) in the App Settings card |
| `App.tsx` | calls `ttsStore.init()` once at boot |
| `src/hooks/useChatSession.ts` | drives `onAssistantMessageStart` / `Chunk` / `Complete` |
| `android/app/src/main/res/xml/backup_rules_*.xml` | exclude `files/tts/` from Android backup and device transfer |
| `src/__automation__/ttsAutomation.ts` | E2E-only driver for download / synthesise / release |

## How it works

`TTSStore.init()` (idempotent) sets `deviceMeetsMemory`, derives each neural engine's `*DownloadState` from `isInstalled()`, clears a persisted `currentVoice` whose engine is not installed, then registers an AppState listener and a `chatSessionStore.activeSessionId` reaction that calls `stop()`.

The gate is the getter `isTTSAvailable`: an explicit `userTTSOverride` (`true` / `false`) wins, and `null` falls back to `deviceMeetsMemory`.

Playback entry points: `play()` (replay), `preview()` (audition), and `onAssistantMessageStart()` which opens a `StreamingHandle` fed by `onAssistantMessageChunk()`; `onAssistantMessageComplete()` finalises it or falls back to `play()`. Engines run through `ttsRuntime.acquire()`, which swaps the loaded engine via `loadInto()`.

`downloadNeuralEngine(id)`: `reclaimLegacySpace()` (if implemented) → free-disk preflight at `estimatedBytes * 1.2` → `engine.downloadModel()` → auto-select a voice, preferring the one stashed in `pendingVoiceRestore`.

## Contracts and invariants

- **Gate derivation.** `isTTSAvailable` is a getter with no writer. `deviceMeetsMemory` has one writer, `init()`, which runs once per session and falls back to `false` if the memory read throws. `userTTSOverride` has one writer, `setUserTTSOverride`, plus hydration (`TTSStore.ts`).
- **Consumers read only the gate.** `PlayButton`, `VoiceChip` and the store guards (`play`, `preview`, `onAssistantMessageStart`, `onAssistantMessageComplete`'s fallback) read `isTTSAvailable`, never the two inputs.
- **The Settings switch shows the effective value** `userTTSOverride ?? deviceMeetsMemory`, persisting nothing until touched; the low-memory helper line tracks `!deviceMeetsMemory`, not the override (`SettingsScreen.tsx`).
- **Closing the gate frees the engine.** When `setUserTTSOverride` closes an open gate, it runs `stop()` then `ttsRuntime.release()` as fire-and-forget, the same way `setAutoSpeak(false)` does.
- **`init()` never early-returns on low memory**: a user can opt in mid-session, so listener, reaction and install checks must already exist.
- **AppState releases only on `'background'`.** `'inactive'` fires for Control Center and call sheets and must not tear down a 200–450 MB engine.
- **Install truth lives on disk** (`engine.isInstalled()`); download state is never persisted.
- **Supertonic install check.** Supertonic is installed only when all 5 files, `voices-manifest.json`, and `model-version.json` with `{version: SUPERTONIC_MODEL_VERSION}` are present. The sentinel is the last write of `downloadModel()`, so an interrupted download never looks installed. A failed download deletes the model directory (`engines/supertonic/index.ts`).
- **Reclaim runs before the preflight**, so space a migration is about to free counts. A failed preflight silently returns to `not_installed` and updates `freeDiskBytes`.
- **`SUPERTONIC_MODEL_ESTIMATED_BYTES` is the exact HF byte total** (it feeds the preflight); `ENGINE_META.supertonic.sizeMb` (380) is a hand-copied label of the same total, not derived from it — change both together.
- **Language is always explicit.** Every Supertonic synthesis call passes `this.supertonicLanguage`; the engine's `'na'` default never governs. `setSupertonicLanguage` (the picker) is the single writer.
- **One native engine at a time.** `Speech` is global; callers go through `ttsRuntime.acquire()`, and only an engine's `loadInto()`, run by the runtime, calls `Speech.initialize`. `deleteNeuralEngine` stops and releases a loaded engine before unlinking its files.

## Traps and decisions

- **Forced re-downloads.** A layout or version change is detected by `isInstalled()` returning `false`, which sends the user back to a one-tap install with no background download and no migration UI:
  - **Supertonic v2 → v3.** The filenames are identical, so only the sentinel tells the versions apart. Bumping `SUPERTONIC_MODEL_VERSION` makes every user re-download about 380 MB. Its `reclaimLegacySpace()` deletes the whole directory because per-file reclaim is impossible.
  - **Kokoro.** The FP32 weights are saved locally as `model_fp32.onnx` so old FP16 `model.onnx` installs re-download. FP16 produced silent audio on some devices, and Q8 produced garbage on some Android ONNX Runtime builds.
- **Voice restore only works within one session.** `pendingVoiceRestore` is not persisted, while the cleared `currentVoice` is. If the app restarts before the re-download, the stash is gone and the download falls back to `voices[0]`.
- **Why the override is a tristate.** `userTTSOverride` is `boolean | null`, and it is never written back to `null`. With the naive `deviceMeetsMemory || override === true`, opting out on a high-RAM device would do nothing.
- **The gate is briefly closed at boot**: `deviceMeetsMemory` is `false` until `init()` resolves.
- **No auto-revert** of a low-memory opt-in after a crash: TTS vs LLM attribution is ambiguous.
- **The picker's options come from locale keys.** They are built from the keys of `l10n.voiceAndSpeech.supertonicLanguageNames` (en.json), not from the library's `SupertonicLanguage` union. To add a language, add it to en.json. A persisted code that isn't listed shows the "Auto" label and the stored value is left unchanged.
- **The picker is a sheet.** It uses a `SearchableSelectSheet` because an anchored menu overflows with 32 options. It stacks above the setup sheet through the DS `Sheet`'s `stackBehavior="push"`. Changes to language or steps apply from the next utterance.
- **TTS downloads bypass `DownloadManager`.** Engines call `RNFS.downloadFile` directly, so the requests carry no HF attribution User-Agent, no HF token, and no background download. See `deep-linking.md`, "Traps and decisions".
- **Supertonic voice styles are best-effort.** A failed voice-style download is only logged. `voices-manifest.json` carries `baseUrl`, so the library fetches missing styles lazily on first play, which needs the network.
- **Backup exclusion.** Engine directories must live under `tts/`. On iOS the exclusion is `NSURLIsExcludedFromBackupKey` set on the `mkdir`; on Android it is the backup-rules XML. A new engine outside `tts/` would be backed up to the cloud.

## Verification

- Unit tests: `src/store/__tests__/TTSStore.test.ts`, `src/services/tts/__tests__/`, `src/components/TTSSetupSheet/__tests__/`. The store mock is `__mocks__/stores/ttsStore.ts`.
- E2E: `e2e/specs/tts-memory-profile.spec.ts`, which downloads, synthesises and releases each engine through `ttsAutomation`; helpers are in `e2e/helpers/tts-actions.ts`.
- By hand:
  - **Gate.** Flip the Settings switch both ways on a device under 4 GiB and on one over it. `PlayButton` and `VoiceChip` should appear and disappear, and turning it off mid-playback should stop audio.
  - **Sentinel.** Overwrite `tts/supertonic/model-version.json` with an older version and relaunch. Supertonic should show as not installed and should restore the previous voice after reinstalling in the same session.
