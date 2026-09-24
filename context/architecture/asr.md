# Voice Input (ASR) Flow

> **Status: not on `main`.** This code lives only on `feature/TASK-20260619-2246`, the branch of draft PR #786, cut from `main` before the llama.rn 0.13 upgrade (it pins llama.rn 0.12.4 and whisper.rn 0.6.0; `main` is on 0.13.0-rc.3). The paths below exist there, not on `main`. Re-verify this doc when that PR is rebased.

## Purpose

On-device push-to-talk speech-to-text for the chat composer: availability gate, per-tier Whisper download and sentinel, capture state machine, and whisper.rn / llama.rn native coexistence. Gate and download copy `tts.md`; the composer seam belongs to `chat-flow.md`; the model deliberately stays out of `model-loading.md`'s pipeline.

## Code map

| Path | Role |
| --- | --- |
| `src/store/ASRStore.ts` | `asrStore`: the gate (`asrAvailable`), `selectedTier`, per-tier download state, `captureState` / `lastError`, AppState release |
| `src/services/asr/constants.ts` | `ASR_TIERS` (URL, filename, exact bytes), `ASR_MODEL_VERSION`, VAD floors, `ASR_MAX_RECORD_MS`, `ASR_DISK_HEADROOM_FACTOR`, `ASR_INSUFFICIENT_STORAGE` |
| `src/services/asr/engines/whisper/index.ts` | `whisperAsrEngine`: per-tier `isInstalled` / `downloadModel` / `reclaimLegacySpace`, a lazy `initWhisper` context, `transcribe`, `release` |
| `src/services/asr/energyVad.ts` | `energyVad`, `int16PcmToFloat32` |
| `src/hooks/usePushToTalk.ts` | the capture lifecycle: permission, `AudioRecord` PCM stream, VAD, transcribe, release |
| `src/utils/asrMicPermission.ts` | `ensureMicPermission` (returns granted, denied or blocked), `openMicSettings` |
| `src/components/MicButton/` | the composer mic; renders `null` when the gate is closed and routes to Settings when the tier isn't ready |
| `src/components/ChatView/ChatView.tsx` | `appendTranscript`, and the `asr-error-snackbar` keyed by `lastError` |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | the `asr-availability-switch` toggle and per-tier install / remove rows |
| `App.tsx` | `asrStore.init()` |
| `ios/Podfile`, `ios/PocketPal/Info.plist`, `android/app/src/main/AndroidManifest.xml`, `android/app/src/main/res/xml/backup_rules_12_plus.xml` | the native wiring (see Traps and decisions) |
| `src/__automation__/asrAutomation.ts` | E2E deep links that put the app into specific gate and error states for visual capture |

## How it works

`ASRStore.init()` sets `deviceMeetsMemory` (`>= ASR_MIN_RAM_BYTES`), derives `downloadStates[tier]` from `isInstalled(tier)`, and registers an AppState listener. `asrAvailable` uses TTS's tristate formula: explicit `userASROverride` wins, `null` falls back to `deviceMeetsMemory`.

The capture state machine (`captureState`, driven by `usePushToTalk`):

```
idle ─pressIn→ requesting_perm ─granted→ recording ─pressOut / 30 s cap→ transcribing ─ok→ idle
                requesting_perm ─denied / blocked→ error      requesting_perm ─AudioRecord.init throws→ error(transcribe_failed)
                recording ─app backgrounded→ idle (buffer discarded)
                recording ─pressOut, VAD fails→ error(too_short)
                transcribing ─throw→ error(transcribe_failed)
error ─pressIn→ requesting_perm        (error is a re-armable resting state)
```

On release the hook concatenates int16 PCM → `int16PcmToFloat32` → `energyVad` → `whisperAsrEngine.transcribe()` (base64 float32, `selectedTier`, `language: 'auto'`) → `onTranscript` (ChatView's `appendTranscript`).

`ASRStore.downloadModel(tier)`: `reclaimLegacySpace(tier)` → preflight at `estimatedBytes * ASR_DISK_HEADROOM_FACTOR` → engine download → `setSelectedTier(tier)`.

## Contracts and invariants

- **The gate is derived.** `asrAvailable` has no writer; `deviceMeetsMemory` only `init()`; `userASROverride` only `setUserASROverride` plus hydration. The `__E2E__`-only `asrAutomation` driver writes these fields directly and is the one sanctioned exception. The switch shows `userASROverride ?? deviceMeetsMemory`.
- **The mic needs gate open and `isSelectedTierReady`.** Otherwise `MicButton` routes to Settings and `onPressIn` returns early.
- **One install makes the mic usable**: `downloadModel` selects the tier; deleting the active tier reselects the first ready one, else `ASR_DEFAULT_TIER`.
- **Install truth is on disk, per tier**: `asr/<tier>/` holds the model file and `model-version.json` at `ASR_MODEL_VERSION`; no store mirror. The sentinel is the last write; a failed download deletes the tier dir.
- **A disk shortfall is a download error, not a capture error**: `downloadStates[tier]='error'` with `downloadError[tier] = ASR_INSUFFICIENT_STORAGE`, matched exactly by the Settings row (TTS instead returns silently to `not_installed`).
- **VAD runs before every decode.** A buffer that fails `energyVad` gets `too_short` and is never decoded.
- **Transcripts are appended, never sent.** `appendTranscript` space-joins onto `inputText`; ChatView stays the only composer writer.
- **Offline.** Capture and transcription make no network calls; the only one is the model download.
- **The model never enters `ModelStore`** (no preset, fit check, auto-load, `ModelCard`); ASR readiness is independent of the LLM.
- **Capture and context are always released.** The recorder: on press-out, error, `ASR_MAX_RECORD_MS`, background (buffer discarded), unmount. The ~400 MB whisper context: after every transcription (success or failure) and on `'background'` (never `'inactive'`), so it never sits beside the LLM; re-init is lazy.
- **`captureState` / `lastError`** are written by `usePushToTalk`, plus the snackbar's `resetCapture` on dismiss.

## Traps and decisions

- **Whisper hallucinates text on silence.** That is why the energy gate is required. It deliberately isn't whisper.rn's `initWhisperVad()`, which crashes (whisper.rn issue #308). The `ASR_MIN_SPEECH_MS` check measures total buffer length, not voiced time.
- **Release during the first-run permission dialog** → `resetCapture()`; otherwise an unattended recording runs to the 30 s cap.
- **Re-entrant presses are ignored** while a capture is starting or live, because a second press would leak the listener and the timer.
- **`AudioRecord.stop()` returns a bare value** despite its `Promise<string>` type, so the hook wraps it in `Promise.resolve`.
- **`BLOCKED` and `UNAVAILABLE` map to `permission_blocked`** (snackbar offers open-Settings); `permission_denied` re-prompts.
- **iOS permission handlers are compiled per Podfile list.** react-native-permissions compiles only the handlers named in `setup_permissions(['Microphone'])`, so a new permission needs a new entry there as well as its `Info.plist` string. Android needs `RECORD_AUDIO` in the manifest.
- **Native coexistence with llama.rn.** Both libraries vendor ggml headers with the same filenames:
  - Under `use_frameworks! :linkage => :static`, building whisper-rn as a dynamic framework fails with "Multiple commands produce …/Headers/ggml-*.h". The `pre_install` hook therefore forces `whisper-rn` to a static library, as it already does for `llama-rn`.
  - From llama.rn 0.13.0-rc.5, llama.rn exports bare `ggml_*` (it dropped its `lm_` renaming; the payload gate requires `ggml_backend_hexagon_reg`). Coexistence now rests only on whisper.rn keeping its `wsp_ggml_*` prefix. If whisper.rn drops it too, the two copies collide, and no gate catches that today. Adding whisper.rn also breaks `model-loading.md` I4 (llama.rn is the only ggml-bearing native dependency), so the ASR branch must restate I4 when it rebases.
  - The clean iOS link was verified only on llama.rn 0.12.4 with whisper.rn 0.6.0; 0.13 ships a prebuilt `rnllama.xcframework`, so re-check the iOS link after the rebase.
- **Why the model isn't in the LLM pipeline.** The iOS CoreML encoder sidecar (`.mlmodelc`) is a directory, which the file-oriented candidate and integrity shape can't express. Routing ASR through `ModelStore` would also leak a non-chat model into every LLM surface. `useCoreMLIos` is on, but no sidecar is downloaded, so iOS decodes on the CPU/GPU path.
- **Opting out releases nothing** (unlike TTS); nothing is resident between utterances.
- **Backup exclusion**: models live under `asr/` (Android XML rules; iOS `NSURLIsExcludedFromBackupKey` at `mkdir`).
- **The Settings route is drawer-typed.** `MicButton` navigates with `DrawerNavigationProp<RootDrawerParamList>` to `ROUTES.SETTINGS`. That matches `main`'s drawer (`app-shell.md`), but `redesign/phase-3` replaces the drawer with bottom tabs and drops `RootDrawerParamList`, so whichever lands second must re-route it.

## Verification

- Unit tests on the branch: `src/store/__tests__/ASRStore.test.ts`, `src/hooks/__tests__/usePushToTalk.test.ts`, `src/services/asr/__tests__/energyVad.test.ts`, `src/services/asr/engines/whisper/__tests__/whisperAsrEngine.test.ts`, `src/components/MicButton/__tests__/`, `src/components/ChatView/__tests__/ChatView.voiceInput.test.tsx`, `src/utils/__tests__/asrMicPermission.test.ts`. Mocks: `__mocks__/stores/asrStore.ts` and `__mocks__/external/whisper.rn.ts`.
- `NATIVE_CHANGES=YES`: run `pod install`, then build both iOS and Android.
- By hand:
  - **Happy path.** In airplane mode, hold the mic, speak, and release. The text should be appended and not sent.
  - **Silence.** Tap and release without speaking. You should get `too_short` and no decode.
  - **Background.** Background the app while recording. The recording should be discarded.
  - **Stale sentinel.** Write an older version into `asr/<tier>/model-version.json` and relaunch. The tier should show as not installed.
