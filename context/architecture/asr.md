# Voice Input (ASR) Flow

> **Status:** on `main` since #786 (whisper.rn 0.7.4). `whisperFits.ts` / `deviceMemory.ts`, the rule shared with voice mode, are on `main` since #1007. One in-use tier shared with voice mode, base by default, and the mic's in-place setup sheet: on `main` since #1017.

## Purpose

On-device tap-to-record speech-to-text for the chat composer: availability gate, per-tier Whisper download and sentinel, capture state machine, and whisper.rn / llama.rn native coexistence. Gate and download copy `tts.md`; the composer seam belongs to `chat-flow.md`; the model deliberately stays out of `model-loading.md`'s pipeline.

## Code map

| Path | Role |
| --- | --- |
| `src/store/ASRStore.ts` | `asrStore`: the gate (`asrAvailable`), `selectedTier` (the in-use tier, shared with voice mode) and its reconcile, `setupTier`, per-tier download state, `captureState` / `lastError` / `inputLevels`, AppState release |
| `src/services/asr/constants.ts` | `ASR_TIERS` (URL, filename, exact bytes), `ASR_MODEL_VERSION`, VAD floor and frame, `ASR_MAX_RECORD_MS`, `ASR_NO_AUDIO_MS`, `ASR_CHUNK_BYTES`, `ASR_LEVEL_HISTORY`, `ASR_DISK_HEADROOM_FACTOR`, `ASR_INSUFFICIENT_STORAGE` |
| `src/services/asr/engines/whisper/index.ts` | `whisperAsrEngine`: per-tier `isInstalled` / `downloadModel` / `reclaimLegacySpace`, a deduplicated `initWhisper` context, `preload`, `transcribe` (with `language` and `prompt`; returns text and the decoded language), `cancelTranscription`, `release` (stops an in-flight decode and waits for it before freeing) |
| `src/services/asr/whisperFits.ts`, `deviceMemory.ts` | pure `whisperFits(memory, chatBytes, whisperBytes)`, `memoryBudget` (iOS: `ASR_IOS_CEILING_SHARE` of the ceiling) and `androidMemoryBudget`: the fit rule shared by dictation and voice mode (`voice-mode.md`); `readDeviceMemory(modelStore)`: Android total RAM (null when unreadable), iOS `availableMemoryCeiling` (free memory before any load) |
| `src/services/asr/speechSegmenter.ts` | `SpeechSegmenter`: cuts the live PCM stream at a pause (`ASR_SEGMENT_PAUSE_MS`) once a segment reaches `ASR_MIN_SEGMENT_MS`, or at `ASR_MAX_SEGMENT_MS`, trims silence before speech to `ASR_SEGMENT_LEAD_IN_MS` |
| `src/services/asr/energyVad.ts` | `energyVad` (voiced-frame gate), `inputLevel` (chunk loudness for the waveform), `int16PcmToFloat32` |
| `src/hooks/useVoiceCapture.ts` | the capture lifecycle (`start` / `stop` / `cancel`): permission, `AudioRecord` PCM stream, levels, VAD, transcribe, release. Mounted once, in `ChatInput` |
| `src/utils/asrMicPermission.ts` | `ensureMicPermission` (returns granted, denied or blocked; Android blocked-without-dialog timeout), `openMicSettings` |
| `src/components/MicButton/` | the composer mic, next to send; renders `null` when the gate is closed, opens `MicSetupSheet` when the in-use tier isn't ready, else `onStart`. `ChatInput` passes `micBeforeSend` (cancels send/stop's 16 px left margin) unless the video button follows; the send wrapper is `pointerEvents="box-none"` so that margin doesn't cover the mic. No mic for a video pal: ChatView withholds `appendTranscript`, because that composer shows `promptText`, which dictation doesn't write |
| `src/components/MicSetupSheet/` | the mic's download-only setup: the `setupTier` row, Download / Downloading… / Retry, Cancel. Mounted by `MicButton` only while open (keeps the composer's render count), closes itself once a tier is ready |
| `src/components/WhisperModelRow/`, `src/utils/asrTierLabel.ts` | the Whisper row both setup sheets share (name, size, progress, low-disk and failed lines; testIDs `<prefix>-stt` / `<prefix>-low-disk`); `asrTierLabel` / `asrTierHint`, the one tier → copy mapping |
| `src/components/VoiceRecordingBar/` | replaces `ChatInput`'s control row while `recording` / `transcribing`: cancel, waveform from `inputLevels` (or a transcribing label, which says when it waits for the chat reply), stop; below them `Language: auto` or `Language: <CODE> (tap to reset)`, whose tap clears `spokenLanguage` so the next segment auto-detects |
| `patches/@fugood+react-native-audio-pcm-stream+1.1.4.patch` | iOS: activate the `AVAudioSession` before recording (see Traps) |
| `src/components/ChatView/ChatView.tsx` | `appendTranscript`, and the `asr-error-snackbar` keyed by `lastError` |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | the `asr-availability-switch` toggle; below the hands-free switch, per-tier rows (hint, size; Download, or `asr-in-use-<tier>` / `asr-use-<tier>` with Remove), shown when `asrAvailable ∨ voiceModeStore.supported` |
| `App.tsx` | `asrStore.init()` |
| `ios/Podfile`, `ios/PocketPal/Info.plist`, `android/app/src/main/AndroidManifest.xml`, `android/app/src/main/res/xml/backup_rules_12_plus.xml` | the native wiring (see Traps and decisions) |
| `src/__automation__/asrAutomation.ts` | E2E deep links that put the app into specific gate, error, recording and transcribing states for visual capture; `tiers::<csv>` installs exactly those tiers, the first one in use |

## How it works

`ASRStore` reads the model picker's device tier (`modelStore.deviceTier`, `deviceRules/classify.ts`): `deviceSupported` is `high` or `flagship` (`ASR_DEVICE_TIERS`), and false while the tier is unresolved. `init()` awaits `makePersistable`'s hydration and the disk scan together, marks each installed tier `ready` (never over `downloading`, and never writes `not_installed`, so a download or error from before the scan survives), then reconciles `selectedTier`: kept if ready, else the first ready tier in `ASR_TIER_ORDER`, else `ASR_DEFAULT_TIER` (base). The same step is the migration; it runs every launch. Then it registers an AppState listener. `asrAvailable` uses TTS's tristate formula: explicit `userASROverride` wins, `null` falls back to `deviceSupported`.

The capture state machine (`captureState`, driven by `useVoiceCapture`):

```
idle ─tap mic→ requesting_perm ─granted→ recording ─stop / 3 min cap→ transcribing ─text→ idle (appended)
               requesting_perm ─denied / blocked→ error         requesting_perm ─AudioRecord.init throws→ error(transcribe_failed)
               recording ─stop, VAD fails→ idle (silently)       transcribing ─empty text→ idle (silently)
               recording ─cancel→ idle (buffer discarded)
               recording ─app backgrounded→ transcribing (as stop)
               transcribing ─cancel→ idle (whisper stopped, result dropped)
               transcribing ─chat generating on CPU→ transcribing (waitingForChat) ─reply done→ decode
               transcribing ─every segment threw→ error(transcribe_failed)
               transcribing ─some segments threw→ append, error(transcript_partial)
error ─tap mic→ requesting_perm        (error is a re-armable resting state)
```

Before the permission prompt, `asrStore.hasMemoryForCapture()` (the rule is `whisperFits` for `selectedTier`) must pass, else `lastError = 'insufficient_memory'` (composer snackbar). Android: `modelStore.loadedModelBytes` (the loaded context's `getModelMemoryRequirement`, set on load, cleared on release) plus the tier's `runtimeBytes` must be at most `ASR_ANDROID_RAM_SHARE` of total RAM. iOS: `loadedModelBytes` plus `runtimeBytes` must be at most `ASR_IOS_CEILING_SHARE` (0.8) of `availableMemoryCeiling` (what iOS reported free before any load); no ceiling yet lets it start. Not `largestSuccessfulLoad`: it only grows, and one oversized load confirmed past the chat model's warning would let Q8 plus whisper through again. A failed read lets the recording start. A recording that has delivered no audio chunk after `ASR_NO_AUDIO_MS` (3 s) is torn down as `lastError = 'mic_unavailable'`; silence still delivers chunks and never triggers it. On permission the hook starts capture; the model loads on the first transcription. Each 50 ms chunk (`ASR_CHUNK_BYTES`) goes to a `SpeechSegmenter`; the peak `inputLevel` of every `ASR_LEVEL_CHUNKS` chunks (100 ms) goes to `asrStore.inputLevels` (last `ASR_LEVEL_HISTORY`), which only `VoiceRecordingBar`'s bars observe; the bar also shows the elapsed time from `recordingStartedAt`. Each segment's transcription is queued: `energyVad` gate → wait while `chatBusyOnCpu` (a local chat model is `inferencing` and `context.gpu === false`), with `waitingForChat` set → `transcribe()` (raw int16 bytes as base64, `selectedTier`, `language: spokenLanguage` or auto-detect when null, and the last `ASR_PROMPT_CHARS` of earlier segments as `prompt`). The first non-empty transcript's decoded language is saved to `spokenLanguage`. On stop the remaining audio is queued the same way, the state shows `transcribing` until the queue drains, and the segment texts are joined and passed to `onTranscript` (ChatView's `appendTranscript`).

`ASRStore.downloadModel(tier)`: `reclaimLegacySpace(tier)` → preflight at `estimatedBytes * ASR_DISK_HEADROOM_FACTOR` → engine download → await reconcile → mark `ready`, and select `tier` only if the in-use tier wasn't ready (first install). `selectTier(tier)` (Settings' Use) is the only public writer and ignores a tier that isn't ready; `setSelectedTier` is private. `deleteModel` of the in-use tier selects the first ready tier, else the default. Setup sheets offer `setupTier`: the in-use tier once ready, else the default, never a tier another surface is downloading.

## Contracts and invariants

- **The gate is derived.** `asrAvailable` and `deviceSupported` have no writer; they follow `modelStore.deviceTier`, which can change when the fetched device rules arrive. `userASROverride` is written only by `setUserASROverride` plus hydration. The `__E2E__`-only `asrAutomation` driver writes these fields (and `deviceTier`, `selectedTier`, `downloadStates`) directly and is the one sanctioned exception. The switch shows `userASROverride ?? deviceSupported`.
- **`spokenLanguage` is persisted** and written only by the hook (the first non-empty transcript decoded with auto-detect; a segment sent with a fixed language never writes, so a reset during its decode holds), voice mode's cascade engine (the same rule) and the resets in Settings and on the recording bar (`null`). Settings always shows the row while voice input is on: `Auto-detect`, or `Auto-detected: <name>` (via `languageDisplayNames`, else the upper-case code) with Reset. It stays set across recordings because auto-detect costs an extra encoder pass per call (below).
- **The mic needs gate open and `isSelectedTierReady`.** Otherwise `MicButton` opens `MicSetupSheet` and `start` returns early. The sheet only downloads: it never selects, navigates or starts a capture, and a fresh tap records.
- **One in-use tier.** After reconcile `selectedTier` is ready whenever any tier is; when none is, it is `ASR_DEFAULT_TIER`. Its writers are reconcile, first-install select, the delete fallback and `selectTier`, plus hydration and the E2E driver. Dictation and voice mode both load, transcribe with and budget for it.
- **A download never switches a ready in-use tier**; only the first install selects (`downloadModel` checks before marking ready, after awaiting reconcile).
- **Reconcile waits for hydration.** A hydrated value landing after it would bring back the old persisted `'small'` default.
- **No Whisper consumer names a tier.** Tier literals live only in `constants.ts`, `types.ts` and `asrTierLabel.ts`; `transcribe` requires `tier` (no default).
- **Install truth is on disk, per tier**: `asr/<tier>/` holds the model file and `model-version.json` at `ASR_MODEL_VERSION`; no store mirror. The sentinel is the last write; a failed download deletes the tier dir.
- **A disk shortfall is a download error, not a capture error**: `downloadStates[tier]='error'` with `downloadError[tier] = ASR_INSUFFICIENT_STORAGE`, matched exactly by the Settings row (TTS instead returns silently to `not_installed`).
- **VAD runs before every decode.** A buffer with under `ASR_MIN_SPEECH_MS` of voiced 30 ms frames (frame RMS ≥ `ASR_VAD_RMS_FLOOR`) is never decoded; capture returns to `idle` with no message, since the flat waveform already showed nothing was heard. An empty transcript does the same.
- **Non-speech tags are stripped.** whisper writes silence or noise as `[Music]`, `[BLANK_AUDIO]` or `(music)`, and whisper.rn exposes no suppression option, so `transcribe` removes bracketed tags; a transcript of only tags is empty.
- **whisper gets signed 16-bit PCM.** `transcribeData` decodes its buffer as int16 (`decodePcm16` in whisper.rn's `RNWhisperJSI.cpp`), so the captured bytes go through unchanged.
- **Transcripts are appended, never sent.** `appendTranscript` space-joins onto `inputText`; ChatView stays the only composer writer.
- **Offline.** Capture and transcription make no network calls; the only one is the model download.
- **The model never enters `ModelStore`** (no preset, fit check, auto-load, `ModelCard`); ASR readiness is independent of the LLM.
- **Capture and context are always released.** The recorder: on stop, cancel, error, `ASR_MAX_RECORD_MS`, background (finishes like stop), unmount. The whisper context: after every dictation (success or failure) and on `'background'` while no capture is in progress (never `'inactive'`); re-init is lazy. Voice mode alone keeps the in-use tier resident, for its session (`voice-mode.md`).
- **`release()` never frees under a decode.** It stops an in-flight `transcribeData` and awaits it before `releaseContext`, so the voice exit and the AppState release, which can race, both close cleanly. whisper.rn 0.7.4 already aborts and waits inside `whisperReleaseContext`; this is a clean close, not a crash fix.
- **Engine work is serial.** Every segment `transcribe` and `release` go through one promise queue in the hook, so a release never cuts across a load or a decode. The engine also deduplicates a load in flight, and a load that finishes after `release()` frees its context (a generation counter).
- **A failed segment is dropped.** Later segments still transcribe and stop appends whatever text came back (with a gap where the failure was); a capture with failures and no text shows `transcribe_failed`, one with some text appends it and shows `transcript_partial`.
- **Known gap (iOS, follow-up):** backgrounding finishes the capture, but whisper decodes on Metal and iOS refuses GPU work from a backgrounded app, so the tail segment can fail there. Not device-checked; Android decodes on the CPU and keeps the transcript.
- **`captureState` / `lastError` / `inputLevels` / `recordingStartedAt` / `waitingForChat`** are written by `useVoiceCapture`, plus the snackbar's `resetCapture` on dismiss. Cancel also cancels a pending wait for the chat reply. Async work from a cancelled capture (a pending permission prompt or transcription) is dropped by a per-capture session counter, never written back.

## Traps and decisions

- **Whisper hallucinates text on silence.** That is why the energy gate is required. It deliberately isn't whisper.rn's `initWhisperVad()`, which crashes (whisper.rn issue #308).
- **Segment at pauses, not fixed windows.** whisper.rn ships a realtime transcriber that slices at pauses, but it finds them with the Silero VAD context that crashes (whisper.rn #308), so the hook slices with the energy gate it already has.
- **Segments are at least 15 s.** Whisper decodes a fixed 30 s window per call, so a 2 s segment costs as much as a 25 s one. Cutting at every pause made a 13 s clip with two pauses take 17.8 s from stop to text on a POCO F8 Ultra (Snapdragon SM8850), against 7.9 s for one call. Pause cuts only pay off once dictation passes ~15 s. whisper.rn 0.7.4 does not expose `audio_ctx` for whisper transcription (its `audioCtx` option is Parakeet-only), so a smaller encoder window would need a native patch.
- **Measured costs behind the gate and the policies** (one run each unless noted; Gemma 3 4B Q4_0 unless noted):
  - Auto-detect runs an extra encoder pass on every call: 7.4 s → 4.0 s stop-to-text for a short clip on the F8 Ultra with the language fixed, and 27 s → 14 s on a OnePlus 6. Hence `spokenLanguage`.
  - Live segments shorten the wait only on a fast phone (long clip: 9.3 s → 3.9 s on the F8 Ultra) and cost more CPU in total (58 → 84 core-seconds). On a OnePlus 6 they were slower (47 s → 137 s). A Galaxy S23 (`high`, OpenCL) keeps up with the language fixed: each segment decodes in 6–8 s idle and ~13 s while Gemma generates, and the long clip's wait halves (15.1 → 6.8 s idle, 30.8 → 16.1 s generating) for +56 % / +9 % CPU. Hence live segments on every supported tier.
  - A chat model on the CPU competes with whisper for cores: on the F8 Ultra whisper took 13–172 s (by quant) while Gemma generated, and Gemma fell from ~21 to ~5 tok/s. On OpenCL or Hexagon, whisper took 5.6–7 s and Gemma barely slowed, for Q4_0, Q4_K_M, Q6_K and Q8_0 (llama.rn 0.13.0-rc.5). `context.gpu` is false only on the CPU backend. Hence `chatBusyOnCpu`.
  - Whisper adds 550–650 MB at peak. A 3 GB Redmi 12C ran with 82–140 MB free and lmkd killed other apps; a OnePlus 6 (low tier) worked but slowed Gemma 1B to ~1 tok/s. Hence the `high`/`flagship` gate.
  - Android's free-memory figure is not a usable gate: a 12 GB Galaxy S25 Ultra reported ~2 GB (#982). On the S23 (7.4 GB visible) with Gemma 4B on OpenCL, 0.8–1.0 GB stayed free, whisper took 0.5–0.6 GB, and lmkd killed the foreground app in 3 of 15 runs ("min2x watermark breached, swap low"); the F8 Ultra (12 GB) had no kills. OpenCL and Hexagon copy weights into buffers the kernel cannot reclaim, and Android loads without mmap, so the chat model's estimate is real resident memory. On the S23 the app's estimate tracks resident memory: Gemma 4B 3.23 GB estimated against 3.30 GB RSS (1.3 GB left available), Gemma 3 1B 1.36 GB against 1.47 GB (3.2 GB left). Gemma 4B plus whisper Small is 52 % of the S23's RAM (refused) and about a third of the F8 Ultra's; Gemma 1B is 27 % (allowed). At 0.45 the largest allowed chat model on an 8 GB phone (~2.7 GB) leaves roughly 1.2 GB available before whisper, against the 0.5–0.7 GB minimum seen at each kill. On that S23 (One UI 8.5) `availMem` matched `MemAvailable` (3.97 GB, no model), so #982 did not reproduce there. Hence `ASR_ANDROID_RAM_SHARE` 0.45, a fixed budget instead of a live reading (how game engines size Android budgets: Unreal memory buckets by total RAM).
  - Loading whisper takes 0.1–0.4 s on the F8 Ultra, so dictation does not preload at tap. Voice mode does, at entry: per-turn reloads measured 0.5–2.4 s.
- **Base is the default everywhere** (no per-device or per-language default). Host WER (%, zh CER) on the exact `ASR_TIERS` files, 50 clips per language; auto-detect picked the right language in every clip (fa base 96 %):

  | Tier | en | es | de | ru | zh | fa |
  | --- | --- | --- | --- | --- | --- | --- |
  | base | 4.8 | 13.2 | 22.5 | 26.1 | 14.3 | 88.7 |
  | small | 3.1 | 6.1 | 12.0 | 13.4 | 8.1 | 58.9 |

  Large-turbo: en 2.1. Time to text for a 4.5 s clip, language known / auto-detect (validated against the app's voice trace on the F8 Ultra, within 1 %):

  | Phone | base | small | large-turbo |
  | --- | --- | --- | --- |
  | POCO F8 Ultra | 1.1 / 2.1 s | 3.7 / 7.0 s | 25 s |
  | X8 Pro | 1.5 / 2.9 s | 5.4 / 10.5 s | 41 s |
  | Galaxy S23 | 1.5 / 2.9 s | 5.9 / 11.7 s | 48 s |
  | Pixel 9 | 1.9 / 3.7 s | 5.9 / 11.1 s | 41 s |
  | OnePlus 6 | 3.5 / 6.9 s | 13.9 / 27.7 s | 131 s |

  Peak RSS of whisper alone: 270 / 560 / 960 MB against `runtimeBytes` 330 / 650 / 1200 MB; the estimates stay, conservative. The table was measured with whisper.rn's `armv8.2-a+fp16` library. Phones listing `asimddp` now load a dotprod library (`release.md`, whisper.rn variants; #1019): on the Pixel 9, in-app voice trace (median of 5, same clip played aloud), base 1.7 / 3.0 s → 1.1 / 1.9 s and small 5.7 / 10.7 s → 3.1 / 5.7 s, transcripts unchanged. The OnePlus 6 has no dotprod and keeps its times. Base stays the default.
- **A persisted `'small'` proves no choice.** The old default was persisted with no install behind it, so reconcile treats only a ready tier as chosen (only installs wrote one). A choice that reads not-installed, from a stale sentinel or an `isInstalled` read error (both swallowed), falls back to the first ready tier; accepted.
- **Base is `ggml-base-q8_0.bin`**: measured exact and faster than q5_1. ASR had not shipped to stores when base changed, so no installed copy exists and no migration is needed.
- **Gate per frame, not per buffer.** Whole-buffer RMS let the silence before and after speech pull quiet, clear speech under the floor (a phone speaker at arm's length measured 0.0091 against 0.01), so it was rejected.
- **whisper.rn's own doc comment says `transcribeData` takes float32.** It doesn't; sending float32 bytes produced noise and an empty transcript every time.
- **Re-entrant starts are ignored** while a capture is starting, live or transcribing, because a second start would leak the listener and the timer.
- **`AudioRecord.stop()` returns a bare value** despite its `Promise<string>` type, so the hook wraps it in `Promise.resolve`.
- **`BLOCKED` and `UNAVAILABLE` map to `permission_blocked`** (snackbar offers open-Settings); `permission_denied` re-prompts.
- **iOS: the app's free-memory figure ignores the chat weights.** llama.rn mmaps them, so `os_proc_available_memory` barely moves: on an iPhone 13 Pro it read 4.2 GB with no chat model and 3.7 GB with Gemma 4B Q8 (4.3 GB file) loaded. Gated on that figure, whisper started next to Q8, jetsam took down the audio daemons and the mic delivered no chunks, so the recording ended empty with no error. Hence the estimate against the pre-load free figure, and `mic_unavailable` for a mic that delivers nothing. The full figure was not enough: with 4B Q4 plus Small (3.85 GB against 4.2 GB) whisper's init once aborted the app (`wsp_ggml_abort` in the backend scheduler, an uncatchable native abort) under system memory pressure right after a Q8 eject; it did not reproduce on clean starts. The likely cause is the chat model's GPU memory, wired system-wide and invisible to that figure. The gate keeps a fifth in reserve (3.36 GB on the 13 Pro): 1.7B plus Small passes, 4B Q4 with Small or Base is refused. Restoring 4B needs a native reading that sees GPU or wired memory (`host_statistics64`, or Metal `currentAllocatedSize` against `recommendedMaxWorkingSetSize`). The 3 s wait covers a Bluetooth mic's start (up to ~2 s on Android); not yet verified with a Bluetooth headset.
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
- **`MicSetupSheet` has no header ✕.** `Sheet`'s ✕ closes and calls `onClose` in the same tick, and `onClose` unmounts the sheet mid-animation. Cancel sets local state so the close animates; `onDismiss` then unmounts it. If `onDismiss` stops reaching `onClosed`, `setupOpen` sticks and the mic can't reopen the sheet.

## Verification

- Unit tests on the branch: `src/store/__tests__/ASRStore.test.ts`, `src/hooks/__tests__/useVoiceCapture.test.ts`, `src/components/VoiceRecordingBar/__tests__/`, `src/services/asr/__tests__/energyVad.test.ts`, `src/services/asr/__tests__/speechSegmenter.test.ts`, `src/services/asr/engines/whisper/__tests__/whisperAsrEngine.test.ts`, `src/components/MicButton/__tests__/`, `src/components/MicSetupSheet/__tests__/`, `src/utils/__tests__/asrTierLabel.test.ts`, `src/screens/SettingsScreen/__tests__/SettingsScreen.test.tsx` (voice input), `src/components/ChatView/__tests__/ChatView.voiceInput.test.tsx`, `src/utils/__tests__/asrMicPermission.test.ts`. Mocks: `__mocks__/stores/asrStore.ts` and `__mocks__/external/whisper.rn.ts`.
- `NATIVE_CHANGES=YES`: run `pod install`, then build both iOS and Android.
- By hand:
  - **Happy path.** In airplane mode, tap the mic, speak (the bars should move), and tap stop. The text should be appended and not sent.
  - **Silence.** Tap the mic, stay silent, tap stop. The bars stay flat and the composer returns to normal with no message and no decode.
  - **Cancel.** Tap ✕ while recording, and again while transcribing. Nothing is appended either time.
  - **Background.** Background the app while recording, and again right after stop. Either way the text should be there on return.
  - **Speaker rig.** A second phone playing speech next to the device works; check that it is not on Do Not Disturb with media volume at 0.
  - **Stale sentinel.** Write an older version into `asr/<tier>/model-version.json` and relaunch. The tier should show as not installed.
