# Voice Mode Flow

> **Status: pending PR #1007.** On-device ASR (#786, `asr.md`) is on main.

## Purpose

Hands-free voice mode inside a chat: the user speaks, the reply is spoken, and the chat itself is the transcript. Covers entry (paywall seam, model, setup, combined memory fit), the session controller and its state machine, the cascade engine (Whisper, the normal send path, TTS), interrupt handling, and the voice view and bar. Elsewhere: Whisper and dictation (`asr.md`), TTS engines and the stream (`tts.md`), the send path and keep-awake (`chat-flow.md`), purchases (`in-app-purchase.md`).

## Code map

| Path | Role |
| --- | --- |
| `src/hooks/useVoiceMode.ts` | `VoiceModeController` (created once per chat screen) and the hook: entry order, mic capture, turns, every exit; returns `requestEntry`, `sheet`, `setupDone`, `continueAnyway`, `chooseSmallerModel`, `tapCloud`, `toggleMute`, `end` |
| `src/store/VoiceModeStore.ts` | `voiceModeStore` (`phase`, `micMuted`, `presentation`, `lastError`, persisted `userVoiceModeOverride`, E2E `unlockOverride`; derived `deviceSupported`, `supported`, `isOpen`, `isFullViewOpen`, `isUnlocked`) and the `voiceEntitlement` instance with its default source |
| `src/services/voice/entitlement.ts` | `VoiceEntitlement`: the registrable `source` (`isUnlocked`, `openPaywall({onUnlocked})`) and `register` |
| `src/services/voice/cascadeEngine.ts` | `CascadeVoiceEngine`: `prepare` / `release` residency, `runTurn` → `{done, interrupt}` |
| `src/services/voice/types.ts` | the engine interface (one implementation; its readiness and memory checks live in the controller): `VoiceEngine`, `VoiceTurnPort` (`send(text, onTurnCreated)`, `stop`), `VoiceTurnEvents`, `VoiceTurnOutcome` |
| `src/services/voice/endpointer.ts` | `Endpointer`: lead-in trim, 600 ms hang after speech, 25 s cap, manual tap |
| `src/services/voice/memoryFit.ts` | pure `voiceMemoryFit` → `fits` / `tight` / `wont_fit` plus the rows it counted; memory read and budget come from `services/asr` (`readDeviceMemory(modelStore)`, `memoryBudget`) |
| `src/services/voice/readiness.ts` | `isVoiceModeVoice` (neural only), `isMicGranted` (no prompt) |
| `src/services/voice/constants.ts` | `VOICE_ENDPOINT_HANG_MS`, `VOICE_FIRST_CHUNK_HOLD_MS`, `VOICE_CAPTURE_SETTLE_MS`, `VOICE_MIC_WATCHDOG_MS`, `VOICE_START_TIMEOUT_MS`, `VOICE_MODE_UNLOCKED_DEFAULT` |
| `src/components/VoiceModeButton/` | composer button (waveform, lock badge), in Send's slot while the input is empty |
| `src/components/VoiceModeView/` | full-screen overlay: cloud, status, mute, End; it follows a downward drag and collapses on distance or a flick (Android back and "Show chat" too); `VoiceModeControlsContext`; `voiceStatus` |
| `src/services/voice/deviceGate.ts` | `voiceModeDeviceSupported(tier, os)`: voice mode's own device gate |
| `src/components/VoiceBar/` | the collapsed session in the composer's slot; tap, or a drag up past the distance or a flick, expands |
| `src/components/VoiceCloud/` | SVG radial-gradient blobs with Reanimated motion per visual; `voiceVisual(phase, micMuted)` |
| `src/components/VoiceSetupSheet/`, `VoiceMemorySheet/` | first-use setup (Whisper base, neural voice, mic); memory breakdown with Continue anyway / Choose a smaller model |
| `src/screens/ChatScreen/ChatScreen.tsx` | builds the turn port from `handleSendPress` / `handleStopPress`, mounts the hook, provides the controls, renders the view and both sheets, and calls `end()` when a video Pal takes over (the one exit outside the controller) |
| `src/components/ChatInput/ChatInput.tsx`, `ChatView/ChatView.tsx` | `onVoicePress` / `onVoiceModePress`; ChatView shows `VoiceBar` instead of `ChatInput` while `phase ≠ closed` |
| `src/__automation__/voiceAutomation.ts`, `adapters/VoiceAdapter.tsx` | E2E driver for visual captures (`pocketpal://voice?cmd=` on iOS, the bridge input on Android) |

## How it works

`requestEntry`, in order: locked → `voiceEntitlement.source.openPaywall({onUnlocked})`, where `onUnlocked` re-runs `requestEntry`; no `activeModelId` → ChatView's model picker (no resume after the pick); `isContextLoading` → nothing; setup incomplete (base not `ready`, voice null or `system`, mic not granted) → setup sheet, whose Continue downloads base with `{select: false}`, then (only if the sheet is still open) `ensureMicPermission()` and `setupDone`; then `voiceMemoryFit`: `fits` enters, `tight` / `wont_fit` open the memory sheet. Enter: `setVoiceOutputActive(true, {holdFirstChunk: model is local})`, `ttsStore.stop()`, one keep-awake hold, `starting` and `full` at once, `engine.prepare()` (limited to `VOICE_START_TIMEOUT_MS`, 45 s), then `listening`. A failed or timed-out prepare, a failed `AudioRecord.init`, or a mic that stays silent shows a localized `uiStore.chatWarning` and exits. The keyboard is closed before entry.

```
closed ─enter→ starting ─prepared→ listening ─endpoint (hang | tap with speech | cap)→ transcribing
transcribing ─empty | VAD reject→ listening        ─throw→ listening (transcribe_failed)
transcribing | thinking ─tap→ cancel → listening
transcribing ─text→ thinking ─first chunk plays→ speaking ─run settled ∧ TTS idle→ listening
thinking ─settled, nothing spoken→ listening (reply_failed if it failed)
speaking ─tap→ interrupt → listening              ─finalize rejects→ listening (speech_failed)
any ─End | background | blur | chat switch* | activeModelId / contextId change | unmount | mic failure | video Pal (ChatScreen)→ closed
any open phase ─audio interruption began→ mic off, running turn interrupted → listening, mic reopened (ended, if it comes, restarts it)
  * except the session a new chat's own spoken send creates (see Traps)
```

`micMuted` and `presentation` are independent of `phase`. A turn: `energyVad`, `whisperAsrEngine.transcribe` (base, `spokenLanguage`), `port.send(text, onTurnCreated)` (= `handleSendPress(…, {spoken: true, onTurnCreated})`), `speechStarted` when `ttsStore.voiceSpeechStarted` is this turn's id, `done` after the send settles and `playbackState` is idle.

## Contracts and invariants

- **Voice never writes the TTS gate or auto-speak.** One getter, `ttsStore.streamsReplies` (`voiceOutputActive || (isTTSAvailable && autoSpeakEnabled)`), opens the stream; with voice closed it equals the chat predicate (`tts.md`).
- **Single writers.** `phase` / `micMuted` / `lastError`: the controller only. `presentation`: `setPresentation` from the view, bar and back. `voiceOutputActive`: controller enter / exit. `unlockOverride`: E2E drivers, persisted only under `__E2E__`.
- **Voice turns are chat turns.** Every turn goes through `handleSendPress` under the generation lease; `applyEventToStore` stays the only store writer during a run. A reply's tool calls run concurrently (#999); interrupt and End stop the run through `handleStopPress`, whose abort cancels every call in flight. What is spoken follows chat auto-speak's step rules (`chat-flow.md`, Speech): call echoes are never spoken, a prose preamble before tools is, and `speaking` starts with the first audio.
- **An interrupted reply keeps what the model generated before the stop**, the same as a typed Stop: interrupt cancels the speech stream, stops the run and writes nothing back. Voice turns carry `metadata.spoken = true`; no row renders it.
- **Spoken replies run with thinking off** (`enable_thinking: false` and `reasoning: {enabled: false}` for a `{spoken: true}` send), whatever the chat or Pal says; typed turns are unchanged. `interrupt()` after `done` is a no-op.
- **Whisper is resident for the session**: `prepare` preloads base; nothing releases it until exit. Every exit runs, in order: `phase = closed`, mic stop, `turn.interrupt()`, `engine.release()` (Whisper, and TTS only when auto-speak is off), the keep-awake release, `setVoiceOutputActive(false)`. A re-entry awaits the previous exit.
- **Voice mode has its own device gate**: `high` / `flagship`, plus `mid` on iOS. `supported` is `userVoiceModeOverride ?? deviceSupported`: Settings' Hands-free voice switch (its own override, not dictation's) turns it on below the gate with a "May be slow" helper, or off on a capable phone. The entry memory check still applies. An iPhone 13 Pro (A15, 6 GB) is `mid` and answered in 2.8–5.6 s; Android's `mid` holds an 8 GB OnePlus 6 (SD845; Whisper alone 4–8 s). Dictation keeps its gate; the memory check still screens 4 GB iPhones.
- **Dictation's rules hold.** `wont_fit` is `whisperFits` for base, dictation's rule. The two never overlap: the button needs dictation idle, and the composer is gone while a session is open.
- **The mic runs only in `listening ∧ !micMuted`**, started by the controller's own transitions, never by a reaction on `phase`, so a forced phase starts nothing. No barge-in.
- **Neural voices only.** The `system` engine reports no chunk progress, which `speaking` needs.
- **The paywall is a seam.** Default locked, `openPaywall` only warns; the purchase flow calls `voiceEntitlement.register(source)` (`in-app-purchase.md`), shaped like the Plus gate's `openPlus({onUnlocked})`. A release build before that ships the icon locked.
- **Memory rows are chat + Whisper + voice on both platforms**, against `memoryBudget`: Android `androidMemoryBudget`, iOS `ASR_IOS_CEILING_SHARE` (0.8) of the free memory it reported before any chat model loaded, `availableMemoryCeiling` (`asr.md`; later readings don't count mmap'd chat weights, and a pair that fit the full figure aborted Whisper's init). The share is applied once, in `memoryBudget`, so the sheet's available figure is the reduced one; 4B Q4 + Base won't fit at 4.2 GB. Not yet known means `fits`. The sheet renders the rows as given.

## Traps and decisions

- **First audio at the first clause is the speech library's `firstChunk: 'clause'`** (`@pocketpalai/react-native-speech` 2.6.0, public API, no patch): the first chunk ends at the earliest of a sentence end, `[,;:—]`+space after 3 words, or 12 words. Its markdown buffer won't cut a first clause holding an inline marker (`*`, `_`, `` ` ``, `[`, `<`), so such a reply starts at its sentence end. Chat auto-speak never passes it.
- **Stream progress only marks that speech began** (`voiceSpeechStarted`); the engine strips markdown, as for chat auto-speak.
- **A local model holds the first voice chunk** until the reply settles or 1.5 s pass: synthesis next to decoding roughly doubled time to first audio on Pixel 9 / S23. Measured on CPU only, so every local backend holds; remote models never do.
- **The mic waits `VOICE_CAPTURE_SETTLE_MS` (150 ms) after a stop before it starts again.** On Android the old read thread releases the shared recorder when it ends, so a quick restart could lose the new one.
- **A started mic that sends no audio within `VOICE_MIC_WATCHDOG_MS` (3 s; a Bluetooth headset's mic route takes 1–3 s) is restarted once, then voice mode ends.** iOS `RNLiveAudioStream` only logs a failed start. Neither audio library reports route changes to JS, so it can't re-arm on one.
- **Audio interruptions come from the speech library** (`onAudioInterruption`, iOS `AVAudioSession` and Android audio focus). `began` stops the mic and interrupts any running turn, `transcribing` included. `ended` may never come (Android holds focus only while a chunk plays), so the next move into `listening` reopens the mic, and the watchdog ends the session if it is still taken.
- **The controller is disposed with the chat screen**, so a late paywall `onUnlocked` starts nothing; the effect re-attaches it on mount (StrictMode).
- **The video-Pal exit lives in `ChatScreen`**: `VideoPalScreen` has no voice controls, so ChatScreen calls `end()` when `isVideoPal` turns true.
- **`prepare()` logs its two load times in dev builds only** (durations only). A first load took about 21 s, hence the `starting` hint and the 45 s limit.
- **Chunk-progress listeners stack** (2.6.0): each stream subscribes once and drops it on finalize or cancel, so a stream left neither would hear later streams' progress. A new stream starts only after the previous cancel resolves, and a turn ends only at `playbackState` idle.
- **`Speech.release()` during an active stream leaves its `finalize()` hanging.** A turn's interrupt awaits the stream cancel, and exit releases the models only after the interrupt (then at idle).
- **Phonon is a neural voice like the others** (pending its PR, `tts.md`). Its `TTS_ENGINE_RUNTIME_BYTES` row is the measured `tts_phonon_active` peak; it lands with whichever of the two PRs merges second (the key type is `NeuralEngineId`, so the compiler demands it). If Phonon's hide rule clears the voice mid-session, later replies are not spoken and the next entry opens setup. Setup's default voice is unchanged.
- **Keep-awake is counted** (`chat-flow.md`): the voice hold and a turn's hold coexist.
- **Exit on chat switch, background, blur and model change**: mic and Whisper can't run backgrounded, and the memory fit would be stale. One exemption: `activeSessionId` going from none to an id is ignored from the start of `port.send` until `onTurnCreated` (a new chat's first spoken send creates it), with model and context unchanged; any other switch closes the session. iOS `inactive` doesn't end it; back to `active` while listening restarts capture.
- **The view and bar follow the finger** in UI-thread gesture worklets: the view translates, dims and shrinks a little, then slides away and switches to the bar from the `withTiming` completion (`scheduleOnRN`), or springs back. Reduced motion: no follow, only the snap.
- **After End, the models are freed when the JS thread is idle** (`requestIdleCallback`; RN 0.87 removed `InteractionManager`), so the teardown doesn't land on a scroll. ChatScreen and ChatView read `isFullViewOpen` / `isOpen`, not `phase`, so a turn's phase changes don't re-render the chat; the cloud cancels its loops on unmount.
- **`transcribing` and `thinking` share one cloud look**; errors are a subtitle until the next phase change, since every failure resumes listening.
- **Overlay, not a route**: `useChatSession` must stay mounted, and the bar shares the chat.
- **Android gets no automation deep-link hosts**, so voice captures there go through `VoiceAdapter` (`voice-command-input`).

## Verification

- Unit: `src/services/voice/__tests__/` (interrupt races in `cascadeEngine`), `useVoiceMode.test.ts` (entry, exits, mic, interruptions), `VoiceModeStore.test.ts` (gate), the `Voice*` component suites, `ChatScreen.voice*.test.tsx`, `ChatInput.test.tsx`, `ChatView.voiceInput.test.tsx`, `TTSStore.test.ts` (voice stream, hold, speech started), `voiceAutomation.test.ts`.
- Visual: a per-task Flavour B spec driven by `voice?cmd=` (`docs/workflows/visual-capture.md`).
- By hand, on a high-tier Android phone and an iPhone with a neural voice, local model in airplane mode: a spoken turn (first audio before the reply ends; no thinking pass); a tap mid-speech stops speech and keeps the generated text; End while transcribing, thinking and speaking; mute; drag down to the bar and up again, slowly and with a flick; a tap while thinking cancels; AirPods connected at entry; chat scrolling right after End; iOS listening → speech → listening still captures; the screen stays on through a 2-minute silent listen and sleeps after End; second and third turns still reach `speaking`.
