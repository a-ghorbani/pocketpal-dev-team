# TTS Flow

## Purpose

Text-to-speech: the availability gate, on-demand neural-engine model downloads (and why they force re-downloads), the single-slot native runtime, and the Supertonic language setting. The streaming-hook callers belong to `chat-flow.md`; Settings layout to `settings.md`. `asr.md` twins this gate/download pattern.

## Code map

| Path | Role |
| --- | --- |
| `src/store/TTSStore.ts` | `ttsStore`: the gate (`isTTSAvailable`), playback state, per-engine download state, streaming hooks, persisted preferences |
| `src/services/tts/constants.ts` | download URLs, file manifests, estimated bytes, `TTS_MIN_RAM_BYTES`, `TTS_ENGINE_RUNTIME_BYTES` (voice mode's memory fit, keyed by `NeuralEngineId`; pending PR #1007), `SUPERTONIC_MODEL_VERSION` and the sentinel filename |
| `src/services/tts/engines/{supertonic,kokoro,kitten,system}/index.ts` | `Engine` implementations: `isInstalled`, `downloadModel`, `reclaimLegacySpace`, `loadInto`, `play`, `playStreaming` |
| `src/services/tts/engines/phonon/` | Phonon via the `@pocketpalai/react-native-speech-phonon` add-on: `Speech.registerEngine` at module load, `getPhononSupport()` (the add-on probe), pinned per-file downloads, `manifest.ts` (iOS manifest parser) |
| `src/services/tts/runtime.ts` | `ttsRuntime`: one native engine loaded at a time; serialises `acquire` / `release` / `stop` |
| `src/services/tts/engineRegistry.ts` | `getEngine`, `getNeuralEngine`, `getAllEngines` (singleton engines) |
| `src/services/tts/streamingHandle.ts`, `thinkingStripper.ts` | streaming into the engine (stream options `firstChunk`, `onProgress`: pending PR #1007); `<think>` stripping |
| `src/components/TTSSetupSheet/` | setup sheet; `HeroRow.tsx` holds the steps control and the Supertonic language picker; `engineMeta.ts` holds `sizeMb` labels |
| `src/components/SearchableSelectSheet/` | the searchable sheet the language picker opens |
| `src/components/TextMessage/PlayButton.tsx`, `src/components/VoiceChip/VoiceChip.tsx` | gate consumers; both render `null` when the gate is closed |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | the availability switch (`tts-availability-switch`) in the App Settings card |
| `App.tsx` | calls `ttsStore.init()` once at boot |
| `src/hooks/useChatSession.ts` | drives `onAssistantMessageStart` / `Chunk` / `Complete` |
| `android/app/src/main/res/xml/backup_rules_*.xml` | exclude `files/tts/` from Android backup and device transfer |
| `src/__automation__/ttsAutomation.ts` | E2E-only driver for download / synthesise / release, and `time::<engine>`: time to first audio and RTF from `onStart` / `onFinish`, median of 3 |
| `scripts/sync-phonon-notices.js`, `src/assets/licenses/phononThirdPartyNotices.json`, `src/screens/AboutScreen/AboutScreen.tsx` | the add-on's third-party notices, bundled and split by `## ` heading, shown in About's "Open-source notices" sheet; `reflowNotice.ts` joins hard-wrapped paragraph lines but keeps `Copyright` lines, bare URLs and the Apache title/version lines on their own |

## How it works

`TTSStore.init()` (idempotent) sets `deviceMeetsMemory`, awaits `refreshPhononSupport()`, derives each neural engine's `*DownloadState` from `isInstalled()`, clears a persisted `currentVoice` whose engine is not installed, then registers an AppState listener and a `chatSessionStore.activeSessionId` reaction that calls `stop()`.

The gate is the getter `isTTSAvailable`: an explicit `userTTSOverride` (`true` / `false`) wins, and `null` falls back to `deviceMeetsMemory`.

Playback entry points: `play()` (replay), `preview()` (audition), and `onAssistantMessageStart()` which opens a `StreamingHandle` fed by `onAssistantMessageChunk()`; `onAssistantMessageComplete()` finalises it or falls back to `play()`. Engines run through `ttsRuntime.acquire()`, which swaps the loaded engine via `loadInto()`. What the hook forwards to `onAssistantMessageChunk` during an agent turn is defined in `chat-flow.md`, under Speech.

The picker renders `ENGINE_ORDER` (Phonon first, then Kitten, Kokoro, Supertonic) filtered by `isEngineOffered(id)`, which is `id !== 'phonon' || phononSupported`. Order only: no default voice depends on it.

`downloadNeuralEngine(id)`: `reclaimLegacySpace()` (if implemented) → free-disk preflight at `estimatedBytes * 1.2` → `engine.downloadModel()` → auto-select a voice, preferring the one stashed in `pendingVoiceRestore`.

## Contracts and invariants

- **Gate derivation.** `isTTSAvailable` is a getter with no writer. `deviceMeetsMemory` has one writer, `init()`, which runs once per session and falls back to `false` if the memory read throws. `userTTSOverride` has one writer, `setUserTTSOverride`, plus hydration (`TTSStore.ts`).
- **Consumers read only the gate.** `PlayButton`, `VoiceChip`, `play` and `preview` read `isTTSAvailable`, never the two inputs.
- **One getter opens a reply stream** (pending PR #1007). `streamsReplies` (`voiceOutputActive || (isTTSAvailable && autoSpeakEnabled)`) is read by `useChatSession`'s per-run snapshot and by the `onAssistantMessageStart` / `onAssistantMessageComplete`-fallback guards. With voice mode closed it equals the chat predicate. `voiceOutputActive` is written only by voice mode's controller, which never writes the override or `autoSpeakEnabled` (`voice-mode.md`).
- **The Settings switch shows the effective value** `userTTSOverride ?? deviceMeetsMemory`, persisting nothing until touched; the low-memory helper line tracks `!deviceMeetsMemory`, not the override (`SettingsScreen.tsx`).
- **Closing the gate frees the engine.** When `setUserTTSOverride` closes an open gate, it runs `stop()` then `ttsRuntime.release()` as fire-and-forget, the same way `setAutoSpeak(false)` does.
- **`init()` never early-returns on low memory**: a user can opt in mid-session, so listener, reaction and install checks must already exist.
- **AppState releases only on `'background'`.** `'inactive'` fires for Control Center and call sheets and must not tear down a 200–450 MB engine.
- **Install truth lives on disk** (`engine.isInstalled()`); download state is never persisted.
- **Supertonic install check.** Supertonic is installed only when all 5 files, `voices-manifest.json`, and `model-version.json` with `{version: SUPERTONIC_MODEL_VERSION}` are present. The sentinel is the last write of `downloadModel()`, so an interrupted download never looks installed. A failed download deletes the model directory (`engines/supertonic/index.ts`).
- **Reclaim runs before the preflight**, so space a migration is about to free counts. A failed preflight silently returns to `not_installed` and updates `freeDiskBytes`.
- **`SUPERTONIC_MODEL_ESTIMATED_BYTES` is the exact HF byte total** (it feeds the preflight); `ENGINE_META.supertonic.sizeMb` (380) is a hand-copied label of the same total, not derived from it — change both together.
- **Language is always explicit.** Every Supertonic synthesis call passes `this.supertonicLanguage`; the engine's `'na'` default never governs. `setSupertonicLanguage` (the picker) is the single writer.
- **Phonon is offered only on this session's probe**. `phononSupported` starts `false`, is never persisted, and has one writer, `refreshPhononSupport()` (from `init()` and after any failed Phonon play, preview or stream finalize, and after any Phonon stream cancel, since a load failure under a cancelled stream never rejects `finalize`). No SoC, OS or RAM allowlist in the app; the 4 GiB TTS gate still applies to all of TTS.
- **The hide rule touches only a Phonon voice**. On every `supported: false`: if `currentVoice` is Phonon, stop and release when Phonon is the runtime's engine, then clear it. Nothing goes to `pendingVoiceRestore`, nothing is deleted, no Alert or error state; one `console.log('[tts] phonon hidden: <reason>')`.
- **Phonon install check**: every pinned file (Android: 4 checkpoint files, 8 `voices/<Name>.safetensors`, `voices.jsonl`; iOS: the saved `manifest.tsv` and every path it lists) plus `model-version.json` holding `PHONON_MODEL_VERSION` and the platform's pins (Android: `androidRevision`, `voicesRevision`, `voicePins` = the whole `PHONON_VOICE_PINS` set, so a changed voice id, sha256 or metadata also invalidates; iOS: `iosRevision`, `iosManifestSha256`). A pin move therefore reads as not installed, and `reclaimLegacySpace()` deletes the folder. The install check tests existence only; size and sha256 are verified per file at download, where the iOS manifest's sizes must also sum to `PHONON_IOS_MODEL_BYTES`, and a failed download deletes `tts/phonon/`.
- **English 31m only**. No code path builds a URL or `modelPath` for any Phonon model but `gradium/phonon-31m-en` (Android) and its pinned Core ML mirror `palshub/phonon-31m-en-coreml` (iOS); `catalogGuard.test.ts` fails on `phonon-40m` or a non-English voice. The add-on has no catalog: the pins in `constants.ts` are it.
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
- **A silent engine can be a native install failure.** Kokoro, Kitten and Supertonic all run on `onnxruntime-react-native` through `@pocketpalai/react-native-speech`; if onnxruntime's JSI `install()` returns false, no engine speaks and nothing crashes. Its iOS install is patched to read the runtime without `RCTCxxBridge` (`release.md`, pending PR), so re-check all three engines on device after an RN or onnxruntime bump.
- **Voice replies stream differently** (pending PR #1007; `voice-mode.md`): first chunk at the first clause, `voiceSpeechStarted` from stream progress, a first-chunk hold for local models, and `voiceStreamFailed` on a rejected finalize. Chat auto-speak streams are unchanged. Both use `@pocketpalai/react-native-speech` 2.8.1's public API (`firstChunk`, and `onAudioInterruption` from the package root), with no patch.
- **Cancel a stream before releasing the engine.** `Speech.release()` during an active stream leaves its `finalize()` hanging. Chunk-progress listeners stack from 2.6.0 (pending PR #1007); a stream drops its own on finalize or cancel.
- **The add-on caches its probe per process**, except `load-failed`; a rejected or malformed native call is reported as `error` and not cached, and a failed `initialize` with `ERR_PHONON_LOAD` / `ERR_PHONON_UNSUPPORTED` clears the cache. So a first-load failure hides Phonon in the same session; other failures leave a cached `ok`.
- **Never delete Phonon files on hide**. The add-on persists `library-missing` / `symbols-missing` / `load-failed` per device, OS build and library version, and a `load-failed` record lapses when the model folder changes (Android stamps `config.json` / `tokenizer.json` / `model.q8.gguf`; iOS the `bundle.json` sha). Deleting on hide would void the record: re-offer, re-download, fail, in a loop. Cost: up to ~64 MiB (Android) or ~164 MiB (iOS) stays on disk while hidden.
- **The iOS Phonon bundle is precompiled** `.mlmodelc` from the mirror (no `.mlpackage`, no on-device compile, so the 1.2× preflight holds). A device that can't load it gets `load-failed` and Phonon hides; there is no compile fallback. `modelPath` is the inner `phonon-31m-en-coreml/` folder.
- **Voice ids are the display names on both platforms**: the Android file stem the app saves, and the names in the iOS bundle's `bundle.json`. Re-check that list when the mirror pin moves.
- **Bundled notices must match the add-on**. `phononNotices.test.ts` fails unless the JSON sections join to the installed `docs/THIRD_PARTY_NOTICES.md` byte for byte; run `node scripts/sync-phonon-notices.js` after an add-on bump.
- **Backup exclusion.** Engine directories must live under `tts/`. On iOS the exclusion is `NSURLIsExcludedFromBackupKey` set on the `mkdir`; on Android it is the backup-rules XML. A new engine outside `tts/` would be backed up to the cloud.

## Verification

- Unit tests: `src/store/__tests__/TTSStore.test.ts`, `src/services/tts/__tests__/`, `src/components/TTSSetupSheet/__tests__/`. The store mock is `__mocks__/stores/ttsStore.ts`.
- E2E: `e2e/specs/tts-memory-profile.spec.ts`, which downloads, synthesises and releases each engine through `ttsAutomation` (Phonon only with `TTS_PROFILE_PHONON=1`); helpers are in `e2e/helpers/tts-actions.ts`.
- Phonon: `engines/phonon/__tests__/` (`PhononEngine`, `manifest`, `catalogGuard`, `publishGate`: no placeholder pins, published versions, no committed `RNSpeech_phonon*` / `RN_SPEECH_PHONON_*` override). By hand: an unsupported phone (OnePlus 6, `missing-cpu-features`) shows no Phonon group; on a supported one, `time::kitten` / `time::phonon` give `starts` = 1 and a finite RTF.
- By hand:
  - **Gate.** Flip the Settings switch both ways on a device under 4 GiB and on one over it. `PlayButton` and `VoiceChip` should appear and disappear, and turning it off mid-playback should stop audio.
  - **Sentinel.** Overwrite `tts/supertonic/model-version.json` with an older version and relaunch. Supertonic should show as not installed and should restore the previous voice after reinstalling in the same session.
