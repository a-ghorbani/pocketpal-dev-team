# Voice Input (ASR / STT) Flow

**Purpose**: cumulative architecture truth for the on-device speech-to-text
subsystem — push-to-talk voice input for the chat composer. Scoped to the
**ASR availability gate** (the boolean every ASR-aware surface reads), the
**per-tier Whisper model wire** (download origin + version sentinel), the
**push-to-talk capture FSM**, and the **build/native coexistence** of
whisper.rn alongside llama.rn. `tts.md` is the sibling pattern this flow twins
(gate / neural-model download / sentinel / forced re-download); `chat-flow.md`
owns the composer seam this feature writes into; `model-loading.md` is
referenced only to explain why the ASR model is **not** routed through the LLM
model pipeline.

Convention used in this doc:

- **(C)** = current behaviour, documented from code
- **(D)** = decision (was an open question, now resolved)

---

## 1. Data model

### 1a. `ASRStore` fields

```
ASRStore
  asrAvailable: boolean                      // (C) MobX getter — derived, no writer. Formula §4a.1
  deviceMeetsMemory: boolean                 // (C) set once in init() from getTotalMemory() >= ASR_MIN_RAM_BYTES
  userASROverride: boolean | null            // (C) persisted; null = first-run sentinel (mirrors userTTSOverride)
  initialized: boolean                       // (C) idempotency guard for init()

  selectedTier: AsrTier                      // (C) persisted; which Whisper model the user uses
  downloadStates: Record<AsrTier, AsrDownloadState>   // (C) per-tier; derived from disk on init()
  downloadProgress: Record<AsrTier, number>           // (C) 0..1, transient
  downloadError: Record<AsrTier, string|null>         // (C) transient
  freeDiskBytes: number | null               // (C) refreshed on setup-surface open

  captureState: CaptureState                 // (C) push-to-talk FSM §3
  lastError: AsrErrorKind | null             // (C) transient; surfaced in composer
```

```
AsrTier = 'base' | 'small' | 'large-turbo'   // (C) base q5_1, small q8_0 (default), large-v3-turbo q5_0
AsrDownloadState = 'not_installed'|'downloading'|'ready'|'error'  // (C) reuses the TTS NeuralDownloadState shape
CaptureState = 'idle' | 'requesting_perm' | 'recording' | 'transcribing' | 'error'  // (C)
AsrErrorKind = 'permission_denied' | 'permission_blocked' | 'too_short' | 'transcribe_failed' | 'not_installed'  // (C)
```

**Persisted** (AsyncStorage, store name `ASRStore`, via `makePersistable` like
TTSStore): `userASROverride`, `selectedTier`. **Derived, not persisted**:
`asrAvailable`. **Transient**: `downloadStates`, `downloadProgress`,
`downloadError`, `freeDiskBytes`, `captureState`, `lastError`,
`deviceMeetsMemory`.

**Install truth lives on disk** (`WhisperAsrEngine.isInstalled(tier)` — model
file + sentinel present), **never** mirrored by a persisted store flag (mirrors
TTS `I-M1`).

**Glossary**:

- **ASR availability gate** — single boolean `asrStore.asrAvailable`, read by
  the composer mic button and the Settings surface; when false the mic is not
  offered.
- **Tier** — one of three Whisper model sizes (low-end `base`, default `small`,
  flagship `large-turbo`); each tier is its own on-disk install (`asr/<tier>/`)
  with its own sentinel.
- **Energy-VAD gate** — an energy/duration floor applied to captured PCM
  **before** the decoder, required because Whisper hallucinates on silence.
  NOT whisper.rn's `initWhisperVad()` (crash, whisper.rn issue #308) in v1.
- **CoreML sidecar** — on iOS, a `ggml-<size>-encoder.mlmodelc` directory
  enabling ANE encoder offload (~6×). Optional accelerator: absence degrades to
  the GGUF CPU path; it never blocks transcription. v1 does not yet bundle one,
  so transcription uses the CPU/GPU path via `useCoreMLIos` best-effort.

### 1b. External shape

- (C) Per-tier Whisper GGML model files are downloaded on demand from
  HuggingFace static files (`ggerganov/whisper.cpp`) by
  `WhisperAsrEngine.downloadModel(tier)`, modeled on `SupertonicEngine`'s
  downloader. Per-tier URL + filename + estimated bytes live in
  `src/services/asr/constants.ts` (`ASR_TIERS`). No PocketPal-served API.
- (C) Library call surface: `whisper.rn` `initWhisper({filePath,
  useCoreMLIos?})` → `context.transcribeData(base64Float32Pcm, {language?})`.
  Audio capture via `@fugood/react-native-audio-pcm-stream`
  (`AudioRecord.init/start/stop/on('data')`), which emits base64-encoded 16-bit
  mono PCM at 16 kHz. The hook decodes int16 → float32, base64-encodes it, and
  passes it to `transcribeData`. All three are new native dependencies
  (`NATIVE_CHANGES=YES`). The Whisper model is **not** an entry in the LLM
  `ModelStore` list (see §4f / D8).

---

## 2. Event flow

```
press-in mic
  ensure RECORD_AUDIO (Android) / NSMicrophoneUsageDescription (iOS)
  granted → start PCM capture (16 kHz mono)        denied → captureState=error(permission_denied)
  token(audio frames)+ → buffer (bounded by ASR_MAX_RECORD_MS)
press-out mic
  stop capture
  decode int16 PCM → float32; energy-VAD gate on buffer
  [buffer below floor] → captureState=error(too_short); no decode
  whisper.transcribeData(buffer, {language='auto'})
  success → appendTranscript(text) into composer; captureState=idle
  failure → captureState=error(transcribe_failed)
```

Per-utterance, single batch decode on release. No streaming partials in v1
(D6). The energy-VAD gate runs between capture-stop and decode and is mandatory
(I-VAD).

---

## 3. State machine

Capture FSM (`captureState`):

```
idle ─press-in→ requesting_perm ─granted→ recording ─press-out→ transcribing ─ok→ idle
       requesting_perm ─denied→ error                recording ─press-out(below floor)→ error
       transcribing ─fail→ error                     error ─press-in→ requesting_perm (retry)
```

| State | User-visible feedback |
| --- | --- |
| `idle` | mic button at rest (offered only when gate open + tier ready) |
| `requesting_perm` | system permission dialog (first time) |
| `recording` | active recording affordance while held |
| `transcribing` | brief in-composer busy affordance after release |
| `error` | transient `ChatView` snackbar keyed by `lastError` (`AsrErrorKind`); `permission_blocked` adds an open-Settings action; no text inserted |

Download FSM reuses the TTS `NeuralDownloadState` shape
(`not_installed → downloading → ready | error`).

---

## 4. Contract

### 4a. ASR availability gate

1. (C) **Formula** (identical structure to TTS `isTTSAvailable`):
   ```
   asrAvailable =
     userASROverride === true  ? true  :
     userASROverride === false ? false :
                                 deviceMeetsMemory   // first-run / null
   ```
2. (C) First run (no persisted override): effective default =
   `deviceMeetsMemory`, set exactly once in `init()` from `getTotalMemory() >=
   ASR_MIN_RAM_BYTES`; never re-checked. A `getTotalMemory()` failure yields
   `deviceMeetsMemory = false` (user can still opt in).
3. (C) The gate decides whether the **feature** is offered. Whether the mic is
   **actionable** also requires the selected tier's `downloadState === 'ready'`.
   Gate-open + not-installed routes to the Settings install surface, not a
   recording mic.
4. (C) `asrAvailable` is read identically by the mic button and the Settings
   surface; no consumer reads `deviceMeetsMemory` / `userASROverride` directly
   for the gate decision.

### 4b. Capture & transcription

1. (C) Press-in starts capture only when `asrAvailable &&
   isSelectedTierReady`; otherwise the mic routes to the Settings surface.
   Installing any tier makes it the active tier (`downloadModel` → `setSelectedTier`),
   so a single install makes the mic actionable without a separate selection step;
   removing the active tier reselects a remaining ready tier (or the default).
2. (C) Capture is bounded by `ASR_MAX_RECORD_MS` (30 s); reaching it ends
   capture as if the user released.
3. (I-VAD) The energy-VAD gate (`energyVad`) runs on the decoded float32 buffer
   **before** any decode. A buffer below the RMS floor or shorter than the
   minimum voiced duration yields `too_short` and **no decode**.
4. (C) Transcription is a **single batch** `transcribeData()` on release; the
   resolved trimmed text is the only transcript (no streaming partials, D6).
5. (C) On success the transcript is **appended to the composer, never
   auto-sent** (I-INSERT). The user reviews and presses Send.
6. (C) `language` passed to `transcribeData()` is `'auto'` in v1 (multilingual
   auto-detect, no language picker); the option exists for a future setting.

### 4c. Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| `MicButton` (in `ChatInput`) | Offered only when `asrStore.asrAvailable`. At-rest mic when tier `ready`; a setup affordance routing to Settings when gate-open but not `ready`; recording affordance while held. Self-gates: renders `null` when `!asrAvailable`. | Anything when `!asrAvailable`; any direct read of memory/override; the Send action |
| `ChatView` | Owns `inputText`; exposes `appendTranscript(text)` that **appends** to current `inputText` via `setInputText(prev => prev ? prev + ' ' + text : text)`. Reuses the prop-driven external-write mechanism of the `initialInputText` seam but with **append** semantics, explicitly unlike `initialInputText`'s overwrite. Renders the capture-error snackbar (observer on `asrStore.lastError`; dismiss → `resetCapture()`; ordered after the reload/pal-load snackbars so only one shows per frame). | Capture/transcription logic; auto-send; overwrite of typed text |
| Settings surface (`SettingsScreen` App Settings card) | A `<Switch>` (testID `asr-availability-switch`) whose value is `userASROverride ?? deviceMeetsMemory`; below-threshold helper line iff `!deviceMeetsMemory`; per-tier install/remove controls shown only when `asrAvailable` | A new top-level screen; copy that auto-sends; the capture FSM |

### 4d. Hard invariants

- **I-OFFLINE**: No ASR code path transmits captured audio, PCM, or transcripts
  off-device. The whisper model runs locally via `whisper.rn`; the only network
  call in the subsystem is the HuggingFace **model download**
  (`ASRStore.downloadModel` → `WhisperAsrEngine.downloadModel`). The transcribe
  path makes no network call.
- **I-INSERT**: A successful transcript is appended to the composer and
  **never** auto-sent. Send remains a separate, explicit user action.
- **I-VAD**: The energy-VAD gate runs before every decode; sub-floor buffers
  are not decoded. v1 does **not** call whisper.rn `initWhisperVad()`
  (issue #308 crash); the energy threshold is the endpoint/gate.
- **I-GATE**: `asrAvailable` has exactly one mathematical definition (§4a.1); no
  code path writes it directly. `deviceMeetsMemory` has one writer (`init()`);
  `userASROverride` has one writer (`setUserASROverride`, the Settings toggle).
- **I-DISK-TRUTH**: Per-tier install truth is on disk (`isInstalled(tier)` =
  model file + current-version sentinel); no persisted store flag mirrors it.
  The sentinel is the **final** write of `downloadModel()` so an interrupted
  download never reports installed (mirrors TTS `I-M1`/`I-M2`).
- **I-NO-MODEL-LIST**: The whisper model is never inserted into the LLM
  `ModelStore` list and never participates in `reconcilePresets`, the LLM
  fit-check, auto-load, or `ModelCard`. ASR download is owned solely by
  `ASRStore` (see D8 / §4f).
- **I-CAPTURE-RELEASE**: Native audio capture is released on press-out, error,
  `ASR_MAX_RECORD_MS`, app backgrounding, and component unmount — capture must
  not leak the microphone. The native **whisper context** (the ~400 MB decode
  resource, distinct from the recorder) is likewise released: once a transcribe
  settles (success or failure, in `usePushToTalk`) and when the app backgrounds
  (`ASRStore` AppState `'background'`, mirroring `TTSStore`; never `'inactive'`).
  Re-init is lazy from the on-disk model on the next utterance, so it must never
  sit resident alongside the LLM.

### 4e. Build / native coexistence (GGML symbol conflict — resolved)

Step-0 spike outcome (verified on the app-pinned **llama.rn 0.12.4** +
**whisper.rn 0.6.0**, RN 0.82.1):

- (C) **The two ggml forks use disjoint symbol namespaces.** A `nm -D` scan of
  the prebuilt `node_modules/llama.rn/android/src/main/jniLibs/arm64-v8a/librnllama.so`
  shows 803 `lm_ggml_*` exports, **zero** bare C-ABI `ggml_*`, and **zero** bare
  C-ABI `whisper_*` (the only `whisper`-substring symbols are C++-mangled
  `clip_*whisper_enc*` / `mtmd_audio_preprocessor_whisper` — llama.rn's own
  multimodal encoder, not whisper.cpp's C ABI). whisper.rn's source ggml fork
  uses the **`wsp_ggml_*`** prefix (`WSP_GGML_API`, 408 symbols), with zero
  `lm_ggml_*`. The two prefixes cannot collide.
- (C) **iOS static-link build SUCCEEDED.** A clean Release build
  (`xcodebuild -scheme PocketPal -configuration Release -sdk iphonesimulator`)
  under `use_frameworks! :linkage => :static` (`ios/Podfile`) compiled both
  ggml forks from source and linked them into the final `PocketPal.app` binary
  with **no duplicate-symbol / link errors**. The namespaced/merged CMake
  fallback was **not** required.
- (C) The only Podfile change needed: the existing `pre_install` hook that
  forces `llama-rn` to `static_library` was extended to also force
  `whisper-rn` static. Under `use_frameworks!` both libs vendor identically
  **named** ggml headers (`ggml.h`, `ggml-cpu.h`, …); building whisper-rn as a
  dynamic framework triggered "Multiple commands produce
  .../whisper_rn.framework/Headers/ggml-*.h". Static linkage skips the framework
  Headers dir and resolves it. This is the same class of fix already applied to
  llama-rn, not the symbol-namespacing fallback.
- (C) Android: llama.rn defaults to its prebuilt `.so`; whisper.rn ships its own
  prebuilt `.so`. ggml symbols are per-library-contained and namespaced, so no
  collision. `pickFirst`/excludes resolve only shared RN runtime libs, not ggml.

### 4f. Why not the LLM model pipeline

- (C) `model-loading.md` builds the LLM list from device-rule candidates
  resolved by `hfAsModel` into single-file GGUF (+ optional `mmproj` sibling).
  The iOS CoreML encoder is a `.mlmodelc` directory bundle that the pipeline's
  file-oriented candidate/integrity shape does not express (D8). Routing ASR
  through `ModelStore` would also leak a non-chat entry into every LLM-model
  surface. Hence I-NO-MODEL-LIST: ASR download is bespoke, modeled on the TTS
  engine downloader.

---

## 5. Layer ownership (single-writer rule)

| Field | Single writer |
| --- | --- |
| `asrAvailable` | (C) no writer — derived (§4a.1) |
| `deviceMeetsMemory` | (C) `ASRStore.init()` — once per session |
| `userASROverride` | (C) `setUserASROverride` (Settings toggle); hydration counts as the single equivalent writer (TTS pattern) |
| `selectedTier` | (C) `setSelectedTier` — the sole writer; called by `downloadModel` (active-tier on install success) and `deleteModel` (reselect a remaining ready tier, else default) and hydration |
| `downloadStates`/`downloadProgress`/`downloadError` | (C) `ASRStore.downloadModel`/`deleteModel` orchestration only |
| `captureState` / `lastError` | (C) the capture handler (`usePushToTalk` via `setCaptureState`/`setError`/`resetCapture`) only |
| `inputText` (composer) | (C) `ChatView`; the mic handler calls ChatView's `appendTranscript`, never writes composer state directly |
| ASR install truth | (C) the file system, read by `WhisperAsrEngine.isInstalled(tier)`; no store mirror (I-DISK-TRUTH) |

Cross-store reads: the mic button reads `asrStore.asrAvailable` +
`isSelectedTierReady`; ASR never reads `ModelStore` (I-NO-MODEL-LIST). One
direction only — no cycle. Greenfield: no past multi-writer races.

**Deferred cleanups** (out of current scope):

1. Extract the shared neural-model download/sentinel/disk-preflight helper used
   by both `services/tts` and `services/asr`.
2. Language picker for forced-language transcription (v1 uses auto-detect).
3. Silero VAD hands-free auto-stop / realtime ghost-text partials (V2).
4. Bundle the iOS `.mlmodelc` CoreML encoder sidecar for ANE acceleration.

---

## 6. Canonical scenarios

### A. High-memory device, model installed — happy path

```
asrAvailable=true, tier 'small' downloadState='ready'
user holds mic, speaks 4s, releases
─────
energy-VAD passes → transcribeData() → text appended into composer; NOT sent.
```

### B. Gate open, model not installed

```
asrAvailable=true, selected tier downloadState='not_installed'
user taps mic
─────
routed to the Settings voice-input surface, NOT recording. (§4b.1)
```

### C. Low-memory device, first run

```
getTotalMemory()=3 GiB, no userASROverride
─────
deviceMeetsMemory=false → asrAvailable=false → mic NOT offered.
Settings toggle OFF, helper line visible. User may opt in (→ asrAvailable=true).
```

### D. Permission denied

```
user holds mic first time → RECORD_AUDIO denied
─────
captureState=error(permission_denied); no capture; no text inserted.
```

### E. Silence / too short (VAD)

```
user taps-and-releases mic with no speech
─────
buffer below energy floor → too_short → NO decode → no text inserted. (I-VAD)
```

### F. Offline guarantee

```
device in airplane mode, model already installed
─────
capture + transcribe succeed fully on-device; zero network. (I-OFFLINE)
```

### G. Forced re-download (tier model layout/version change)

```
installed tier sentinel < current version on next launch
─────
isInstalled(tier)=false → not_installed → one clean re-download;
reclaim before disk preflight. (I-DISK-TRUTH)
```

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `asrAvailable` | derived (no writer) | mic button, Settings | `userASROverride===true` OR (`null` AND `deviceMeetsMemory`) |
| `deviceMeetsMemory` | `init()` once | gate derivation, Settings helper line | `getTotalMemory() >= ASR_MIN_RAM_BYTES` |
| `userASROverride` | `setUserASROverride`; hydration | gate derivation, toggle value | persisted user choice |
| `downloadStates[selectedTier]` | `downloadModel`/`deleteModel` | mic actionability, Settings controls | `'ready'` ⇔ `isInstalled(tier)` |
| `selectedTier` | `setSelectedTier` (called by `downloadModel` on success, `deleteModel` on active-tier removal, and hydration) | mic actionability, Settings | the active tier the mic uses |
| `downloadError[tier]` | `downloadModel` (network/IO message, or the disk-cause sentinel on a failed preflight); cleared by `downloadModel`/`deleteModel` | Settings tier row | non-null ⇔ last download attempt failed; equals the disk sentinel ⇔ insufficient storage |
| `captureState` / `lastError` | capture handler | mic affordance, error snackbar | per §3 FSM |

---

## 8. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Dedicated `ASRStore` + `services/asr/`, twin of TTS subsystem | Reuse proven gate/download/sentinel pattern, isolated boundary |
| D2 | Device-memory gate with `boolean\|null` override, identical to TTS | Same low-RAM opt-in/opt-out need; one mental model |
| D3 | Batch-on-release transcription; no realtime streaming in v1 | Sidesteps initWhisperVad crash + Android streaming slowness |
| D4 | Energy-VAD gate before decode, mandatory | Whisper hallucinates on silence; gating is load-bearing |
| D5 | Append transcript into composer, never auto-send | User confirms before sending |
| D6 | No partial ghost text in v1 | No crash-free cheap partial source; deferred to V2 |
| D7 | Three tiers (base q5_1 / small q8_0 / large-v3-turbo q5_0), small default | Matches device tiering; small near-lossless multilingual |
| D8 | ASR model NOT in LLM model pipeline | `.mlmodelc` dir doesn't fit; avoids ModelStore pollution |
| D9 | Append transcript via ChatView `appendTranscript` seam | Reuses `initialInputText` write mechanism but appends; single composer writer |
| D10 | Auto-detect language in v1 (no picker) | Multilingual default; picker is deferred scope |
| D11 | iOS `.mlmodelc` sidecar optional, not blocking | Absence degrades to CPU/GPU path; never blocks transcription |
| D12 | Force whisper-rn static in the Podfile (like llama-rn) | Resolves the use_frameworks! ggml-header copy collision; not the symbol-namespace fallback |

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | Permission permanently denied (don't-ask-again) | `ensureMicPermission` maps to `blocked`; the hook sets `error(permission_blocked)` (distinct from a re-promptable `permission_denied`); the composer error snackbar then offers an open-Settings action |
| 9b | App backgrounded mid-recording | capture released, buffer discarded, captureState→idle; the whisper context is also released (`ASRStore` AppState `'background'` seam); no decode (I-CAPTURE-RELEASE) |
| 9c | Hold exceeds `ASR_MAX_RECORD_MS` | capture ends as if released; transcribe runs on the bounded buffer |
| 9d | Disk too low for a tier | install blocked by the disk preflight (`estimated*1.2`), reclaim-before-gate first. The preflight sets `downloadStates[tier]='error'` + a stable disk-cause sentinel on `downloadError[tier]` (download channel, NOT a capture `AsrErrorKind`); the Settings tier row renders the `insufficientStorage` line. This is a download-channel error, distinct from the capture FSM |
| 9k | Whisper context after a transcribe settles | released back to idle (success or failure); re-init is lazy from the on-disk model on the next utterance (I-CAPTURE-RELEASE) |
| 9e | Transcribe throws / model corrupt | error(transcribe_failed); no text inserted; existing composer text untouched |
| 9f | User holds mic while no LLM model loaded | independent — ASR readiness is tier `downloadState`, not LLM model state (I-NO-MODEL-LIST) |
| 9g | Transcript appended onto existing typed text | `appendTranscript` appends (space-joined), does not overwrite (D9) |
| 9h | Interrupted download before sentinel write | next launch isInstalled(tier)=false → one clean re-download (I-DISK-TRUTH) |
| 9i | iOS device without ANE / no `.mlmodelc` | falls back to CPU/GPU decode path; slower but functional (D11) |
| 9j | whisper.rn + llama.rn loaded together | coexist — ggml symbols namespaced `lm_ggml_*` vs `wsp_ggml_*`; iOS static link verified clean (§4e) |

---

## What this doc is NOT

- Not an implementation plan — file edits, exact action names, l10n keys,
  testIDs belong in the story's `how.md`.
- Not a UI design doc beyond the contract; visual treatment is the
  implementer's call within the §4c constraints.
- Not exhaustive coverage of every future ASR capability — language picker,
  Silero VAD, realtime partials, and the CoreML sidecar are deferred (§5).

When this doc and the code disagree, the code wins; the same PR that lands the
change must update this doc.
