# Voice Input (ASR) Flow

> **Status: not on `main`.** This code lives only on `feature/TASK-20260619-2246`, the branch of draft PR #786 (merged up to `main`; llama.rn 0.13.0-rc.5, whisper.rn 0.7.4). The paths below exist there, not on `main`.

## Purpose

On-device tap-to-record speech-to-text for the chat composer: availability gate, per-tier Whisper download and sentinel, capture state machine, and whisper.rn / llama.rn native coexistence. Gate and download copy `tts.md`; the composer seam belongs to `chat-flow.md`; the model deliberately stays out of `model-loading.md`'s pipeline.

## Code map

| Path | Role |
| --- | --- |
| `src/store/ASRStore.ts` | `asrStore`: the gate (`asrAvailable`), `selectedTier`, per-tier download state, `captureState` / `lastError` / `inputLevels`, AppState release |
| `src/services/asr/constants.ts` | `ASR_TIERS` (URL, filename, exact bytes), `ASR_MODEL_VERSION`, VAD floor and frame, `ASR_MAX_RECORD_MS`, `ASR_CHUNK_BYTES`, `ASR_LEVEL_HISTORY`, `ASR_DISK_HEADROOM_FACTOR`, `ASR_INSUFFICIENT_STORAGE` |
| `src/services/asr/engines/whisper/index.ts` | `whisperAsrEngine`: per-tier `isInstalled` / `downloadModel` / `reclaimLegacySpace`, a deduplicated `initWhisper` context (`prepare`), `transcribe` (with `prompt`), `cancelTranscription`, `release` |
| `src/services/asr/speechSegmenter.ts` | `SpeechSegmenter`: cuts the live PCM stream at pauses (`ASR_SEGMENT_PAUSE_MS`) or `ASR_MAX_SEGMENT_MS`, trims silence before speech to `ASR_SEGMENT_LEAD_IN_MS` |
| `src/services/asr/energyVad.ts` | `energyVad` (voiced-frame gate), `inputLevel` (chunk loudness for the waveform), `int16PcmToFloat32` |
| `src/hooks/useVoiceCapture.ts` | the capture lifecycle (`start` / `stop` / `cancel`): permission, `AudioRecord` PCM stream, levels, VAD, transcribe, release. Mounted once, in `ChatInput` |
| `src/utils/asrMicPermission.ts` | `ensureMicPermission` (returns granted, denied or blocked; Android blocked-without-dialog timeout), `openMicSettings` |
| `src/components/MicButton/` | the composer mic, next to send; renders `null` when the gate is closed, routes to Settings when the tier isn't ready, else `onStart` |
| `src/components/VoiceRecordingBar/` | replaces `ChatInput`'s control row while `recording` / `transcribing`: cancel, waveform from `inputLevels` (or a transcribing label), stop |
| `patches/@fugood+react-native-audio-pcm-stream+1.1.4.patch` | iOS: activate the `AVAudioSession` before recording (see Traps) |
| `src/components/ChatView/ChatView.tsx` | `appendTranscript`, and the `asr-error-snackbar` keyed by `lastError` |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | the `asr-availability-switch` toggle and per-tier install / remove rows |
| `App.tsx` | `asrStore.init()` |
| `ios/Podfile`, `ios/PocketPal/Info.plist`, `android/app/src/main/AndroidManifest.xml`, `android/app/src/main/res/xml/backup_rules_12_plus.xml` | the native wiring (see Traps and decisions) |
| `src/__automation__/asrAutomation.ts` | E2E deep links that put the app into specific gate, error, recording and transcribing states for visual capture |

## How it works

`ASRStore.init()` sets `deviceMeetsMemory` (`>= ASR_MIN_RAM_BYTES`), derives `downloadStates[tier]` from `isInstalled(tier)`, and registers an AppState listener. `asrAvailable` uses TTS's tristate formula: explicit `userASROverride` wins, `null` falls back to `deviceMeetsMemory`.

The capture state machine (`captureState`, driven by `useVoiceCapture`):

```
idle ─tap mic→ requesting_perm ─granted→ recording ─stop / 3 min cap→ transcribing ─text→ idle (appended)
               requesting_perm ─denied / blocked→ error         requesting_perm ─AudioRecord.init throws→ error(transcribe_failed)
               recording ─stop, VAD fails→ idle (silently)       transcribing ─empty text→ idle (silently)
               recording ─cancel / app backgrounded→ idle (buffer discarded)
               transcribing ─cancel→ idle (whisper stopped, result dropped)
               transcribing ─throw→ error(transcribe_failed)
error ─tap mic→ requesting_perm        (error is a re-armable resting state)
```

On permission the hook queues `whisperAsrEngine.prepare(tier)`, so the model loads while the user speaks. Each 50 ms chunk (`ASR_CHUNK_BYTES`) goes to a `SpeechSegmenter` and its `inputLevel` to `asrStore.inputLevels` (last `ASR_LEVEL_HISTORY`), which only `VoiceRecordingBar`'s bars observe; the bar also shows the elapsed time from `recordingStartedAt`. When the segmenter cuts a segment, the hook queues its transcription: `energyVad` gate → `transcribe()` (raw int16 bytes as base64, `selectedTier`, `language: 'auto'`, and the last `ASR_PROMPT_CHARS` of earlier segments as `prompt`). On stop the remaining audio is queued the same way, the state shows `transcribing` until the queue drains, and the segment texts are joined and passed to `onTranscript` (ChatView's `appendTranscript`).

`ASRStore.downloadModel(tier)`: `reclaimLegacySpace(tier)` → preflight at `estimatedBytes * ASR_DISK_HEADROOM_FACTOR` → engine download → `setSelectedTier(tier)`.

## Contracts and invariants

- **The gate is derived.** `asrAvailable` has no writer; `deviceMeetsMemory` only `init()`; `userASROverride` only `setUserASROverride` plus hydration. The `__E2E__`-only `asrAutomation` driver writes these fields directly and is the one sanctioned exception. The switch shows `userASROverride ?? deviceMeetsMemory`.
- **The mic needs gate open and `isSelectedTierReady`.** Otherwise `MicButton` routes to Settings and `start` returns early.
- **One install makes the mic usable**: `downloadModel` selects the tier; deleting the active tier reselects the first ready one, else `ASR_DEFAULT_TIER`.
- **Install truth is on disk, per tier**: `asr/<tier>/` holds the model file and `model-version.json` at `ASR_MODEL_VERSION`; no store mirror. The sentinel is the last write; a failed download deletes the tier dir.
- **A disk shortfall is a download error, not a capture error**: `downloadStates[tier]='error'` with `downloadError[tier] = ASR_INSUFFICIENT_STORAGE`, matched exactly by the Settings row (TTS instead returns silently to `not_installed`).
- **VAD runs before every decode.** A buffer with under `ASR_MIN_SPEECH_MS` of voiced 30 ms frames (frame RMS ≥ `ASR_VAD_RMS_FLOOR`) is never decoded; capture returns to `idle` with no message, since the flat waveform already showed nothing was heard. An empty transcript does the same.
- **Non-speech tags are stripped.** whisper writes silence or noise as `[Music]`, `[BLANK_AUDIO]` or `(music)`, and whisper.rn exposes no suppression option, so `transcribe` removes bracketed tags; a transcript of only tags is empty.
- **whisper gets signed 16-bit PCM.** `transcribeData` decodes its buffer as int16 (`decodePcm16` in whisper.rn's `RNWhisperJSI.cpp`), so the captured bytes go through unchanged.
- **Transcripts are appended, never sent.** `appendTranscript` space-joins onto `inputText`; ChatView stays the only composer writer.
- **Offline.** Capture and transcription make no network calls; the only one is the model download.
- **The model never enters `ModelStore`** (no preset, fit check, auto-load, `ModelCard`); ASR readiness is independent of the LLM.
- **Capture and context are always released.** The recorder: on stop, cancel, error, `ASR_MAX_RECORD_MS`, background (buffer discarded), unmount. The ~400 MB whisper context: after every transcription (success or failure) and on `'background'` (never `'inactive'`), so it never sits beside the LLM; re-init is lazy.
- **Engine work is serial.** `prepare`, every segment `transcribe` and `release` go through one promise queue in the hook, so a release never cuts across a load or a decode. The engine also deduplicates a load in flight, and a load that finishes after `release()` frees its context (a generation counter).
- **A failed segment fails the capture.** The remaining segments are skipped and stop shows `transcribe_failed`; partial text is not appended.
- **`captureState` / `lastError` / `inputLevels` / `recordingStartedAt`** are written by `useVoiceCapture`, plus the snackbar's `resetCapture` on dismiss. Async work from a cancelled capture (a pending permission prompt or transcription) is dropped by a per-capture session counter, never written back.

## Traps and decisions

- **Whisper hallucinates text on silence.** That is why the energy gate is required. It deliberately isn't whisper.rn's `initWhisperVad()`, which crashes (whisper.rn issue #308).
- **Segment at pauses, not fixed windows.** whisper.rn ships a realtime transcriber that slices at pauses, but it finds them with the Silero VAD context that crashes (whisper.rn #308), so the hook slices with the energy gate it already has.
- **Gate per frame, not per buffer.** Whole-buffer RMS let the silence before and after speech pull quiet, clear speech under the floor (a phone speaker at arm's length measured 0.0091 against 0.01), so it was rejected.
- **whisper.rn's own doc comment says `transcribeData` takes float32.** It doesn't; sending float32 bytes produced noise and an empty transcript every time.
- **Re-entrant starts are ignored** while a capture is starting, live or transcribing, because a second start would leak the listener and the timer.
- **`AudioRecord.stop()` returns a bare value** despite its `Promise<string>` type, so the hook wraps it in `Promise.resolve`.
- **`BLOCKED` and `UNAVAILABLE` map to `permission_blocked`** (snackbar offers open-Settings); `permission_denied` re-prompts.
- **iOS: the recorder never activated the audio session.** `RNLiveAudioStream` sets the PlayAndRecord category but never calls `setActive:YES`; with TTS having set Playback, `AudioQueueNewInput` got a 0-channel input and no data ever arrived. The patch-package patch adds the activation. `scripts/postinstall.sh` runs patch-package, so a patch that stops applying shows in the install log, not as a build failure.
- **iOS permission handlers are compiled per Podfile list.** react-native-permissions compiles only the handlers named in `setup_permissions(['Microphone'])`, so a new permission needs a new entry there as well as its `Info.plist` string. Android needs `RECORD_AUDIO` in the manifest.
- **Native coexistence with llama.rn.** Both libraries vendor ggml headers with the same filenames:
  - Under `use_frameworks! :linkage => :static`, building whisper-rn as a dynamic framework fails with "Multiple commands produce …/Headers/ggml-*.h". The `pre_install` hook therefore forces `whisper-rn` to a static library, as it already does for `llama-rn`.
  - From llama.rn 0.13.0-rc.5, llama.rn exports bare `ggml_*` on Android (it dropped its `lm_` renaming; the payload gate requires `ggml_backend_hexagon_reg`). Coexistence now rests only on whisper.rn keeping its `wsp_ggml_*` prefix. If whisper.rn drops it too, the two copies collide, and no gate catches that today. Adding whisper.rn also breaks `model-loading.md` I4 (llama.rn is the only ggml-bearing native dependency), so this must be restated in I4 when the PR lands.
  - Both libraries also define a global `class ThreadPool` (`cpp/jsi/ThreadPool`), so the linker binds one library's constructor, destructor and shutdown to the other's. That is harmless only while the two layouts stay identical; an upstream change to either can corrupt memory with no build error.
  - Verified on llama.rn 0.13.0-rc.5 with whisper.rn 0.7.4: CI builds for both platforms and a local iOS link.
- **Why the model isn't in the LLM pipeline.** The iOS CoreML encoder sidecar (`.mlmodelc`) is a directory, which the file-oriented candidate and integrity shape can't express. Routing ASR through `ModelStore` would also leak a non-chat model into every LLM surface. `useCoreMLIos` is on, but no sidecar is downloaded, so iOS decodes on the CPU/GPU path.
- **Opting out releases nothing** (unlike TTS); nothing is resident between utterances.
- **Backup exclusion**: models live under `asr/` (Android XML rules; iOS `NSURLIsExcludedFromBackupKey` at `mkdir`).
- **The Settings route is drawer-typed.** `MicButton` navigates with `DrawerNavigationProp<RootDrawerParamList>` to `ROUTES.SETTINGS`. That matches `main`'s drawer (`app-shell.md`), but `redesign/phase-3` replaces the drawer with bottom tabs and drops `RootDrawerParamList`, so whichever lands second must re-route it.

## Verification

- Unit tests on the branch: `src/store/__tests__/ASRStore.test.ts`, `src/hooks/__tests__/useVoiceCapture.test.ts`, `src/components/VoiceRecordingBar/__tests__/`, `src/services/asr/__tests__/energyVad.test.ts`, `src/services/asr/engines/whisper/__tests__/whisperAsrEngine.test.ts`, `src/components/MicButton/__tests__/`, `src/components/ChatView/__tests__/ChatView.voiceInput.test.tsx`, `src/utils/__tests__/asrMicPermission.test.ts`. Mocks: `__mocks__/stores/asrStore.ts` and `__mocks__/external/whisper.rn.ts`.
- `NATIVE_CHANGES=YES`: run `pod install`, then build both iOS and Android.
- By hand:
  - **Happy path.** In airplane mode, tap the mic, speak (the bars should move), and tap stop. The text should be appended and not sent.
  - **Silence.** Tap the mic, stay silent, tap stop. The bars stay flat and the composer returns to normal with no message and no decode.
  - **Cancel.** Tap ✕ while recording, and again while transcribing. Nothing is appended either time.
  - **Background.** Background the app while recording. The recording should be discarded.
  - **Speaker rig.** A second phone playing speech next to the device works; check that it is not on Do Not Disturb with media volume at 0.
  - **Stale sentinel.** Write an older version into `asr/<tier>/model-version.json` and relaunch. The tier should show as not installed.
