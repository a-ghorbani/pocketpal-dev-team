# Voice Mode Flow

> **Status: pending PR, stacked on draft PR #786.** It needs on-device ASR, which exists only on #786's branch (`asr.md`), so it lands after #786.

## Purpose

Hands-free voice mode inside a chat: the user speaks, the reply is spoken, and the chat itself is the transcript. Covers entry (paywall seam, model, setup, combined memory fit), the session controller and its state machine, the cascade engine (Whisper, the normal send path, TTS), the spoken rewrite after an interrupt, and the voice view and bar. Elsewhere: Whisper and dictation (`asr.md`), TTS engines and the stream (`tts.md`), the send path and keep-awake (`chat-flow.md`), purchases (`in-app-purchase.md`).

## Code map

| Path | Role |
| --- | --- |
| `src/hooks/useVoiceMode.ts` | `VoiceModeController` (created once per chat screen) and the hook: entry order, mic capture, turns, every exit; returns `requestEntry`, `sheet`, `setupDone`, `continueAnyway`, `chooseSmallerModel`, `tapCloud`, `toggleMute`, `end` |
| `src/store/VoiceModeStore.ts` | `voiceModeStore` (`phase`, `micMuted`, `presentation`, `lastError`, dev `unlockOverride`; derived `supported`, `isUnlocked`) and the `voiceEntitlement` instance with its default source |
| `src/services/voice/entitlement.ts` | `VoiceEntitlement`: the swappable `source` (`isUnlocked`, `openPaywall`) and `register` |
| `src/services/voice/cascadeEngine.ts` | `CascadeVoiceEngine`: `prepare` / `release` residency, `runTurn` → `{done, interrupt}` |
| `src/services/voice/types.ts` | the engine seam: `VoiceEngine`, `VoiceTurnPort` (`send(text, onTurnCreated)`, `stop`), `VoiceTurnEvents`, `VoiceTurnOutcome` |
| `src/services/voice/endpointer.ts` | `Endpointer`: lead-in trim, 600 ms hang after speech, 25 s cap, manual tap |
| `src/services/voice/memoryFit.ts` | pure `voiceMemoryFit` → `fits` / `tight` / `wont_fit` plus the breakdown |
| `src/services/voice/readiness.ts` | `isVoiceModeVoice` (neural only), `isMicGranted` (no prompt) |
| `src/services/voice/constants.ts` | `VOICE_ENDPOINT_HANG_MS`, `VOICE_FIRST_CHUNK_HOLD_MS`, `VOICE_MODE_UNLOCKED_DEFAULT` |
| `src/components/VoiceModeButton/` | composer button (waveform, lock badge), in Send's slot while the input is empty |
| `src/components/VoiceModeView/` | full-screen overlay: cloud, status, mute, End; pull-down and Android back collapse it; `VoiceModeControlsContext`; `voiceStatus` |
| `src/components/VoiceBar/` | the collapsed session in the composer's slot; tap or swipe up expands |
| `src/components/VoiceCloud/` | SVG radial-gradient blobs with Reanimated motion per visual; `voiceVisual(phase, micMuted)` |
| `src/components/VoiceSetupSheet/`, `VoiceMemorySheet/` | first-use setup (Whisper base, neural voice, mic); memory breakdown with Continue anyway / Choose a smaller model |
| `src/components/SpokenMarker/` | "Spoken" marker under rows with `metadata.spoken` (rendered by `Message`) |
| `src/screens/ChatScreen/ChatScreen.tsx` | builds the turn port from `handleSendPress` / `handleStopPress`, mounts the hook, provides the controls, renders the view and both sheets |
| `src/components/ChatInput/ChatInput.tsx`, `ChatView/ChatView.tsx` | `onVoicePress` / `onVoiceModePress`; ChatView shows `VoiceBar` instead of `ChatInput` while `phase ≠ closed` |
| `src/__automation__/voiceAutomation.ts`, `adapters/VoiceAdapter.tsx` | E2E driver for visual captures (`pocketpal://voice?cmd=` on iOS, the bridge input on Android) |

## How it works

`requestEntry`, in order: locked → `voiceEntitlement.source.openPaywall()`; no `activeModelId` → ChatView's model picker (no resume after the pick); `isContextLoading` → nothing; setup incomplete (base not `ready`, voice null or `system`, mic not granted) → setup sheet, whose Continue downloads base with `{select: false}`, then `ensureMicPermission()`, then `setupDone`; then `voiceMemoryFit`: `fits` enters, `tight` / `wont_fit` open the memory sheet. Enter: `setVoiceOutputActive(true, {holdFirstChunk: model is local})`, `ttsStore.stop()`, one keep-awake hold, `engine.prepare()`, then `listening` and `full`.

```
closed ─enter→ listening ─endpoint (hang | tap with speech | cap)→ transcribing
transcribing ─empty | VAD reject→ listening        ─throw→ listening (transcribe_failed)
transcribing ─text→ thinking ─first chunk plays→ speaking ─run settled ∧ TTS idle→ listening
thinking ─settled, nothing spoken→ listening (reply_failed if it failed)
speaking ─tap→ interrupt → listening              ─finalize rejects→ listening (speech_failed)
any ─End | background | blur | chat switch | activeModelId / contextId change | unmount | mic failure→ closed
```

`micMuted` and `presentation` are independent of `phase`. A turn: `energyVad`, `whisperAsrEngine.transcribe` (base, `spokenLanguage`), `port.send(text, onTurnCreated)` (= `handleSendPress(…, {spoken: true, onTurnCreated})`), `speechStarted` when `ttsStore.voiceSpoken.messageId` is this turn, `done` after the send settles and `playbackState` is idle.

## Contracts and invariants

- **Voice never writes the TTS gate or auto-speak.** One getter, `ttsStore.streamsReplies` (`voiceOutputActive || (isTTSAvailable && autoSpeakEnabled)`), opens the stream; with voice closed it equals the chat predicate (`tts.md`).
- **Single writers.** `phase` / `micMuted` / `lastError`: the controller only. `presentation`: `setPresentation` from the view, bar and back. `voiceOutputActive`: controller enter / exit. `unlockOverride`: dev / E2E drivers, persisted only under `__DEV__ || __E2E__`.
- **Voice turns are chat turns.** Every turn goes through `handleSendPress` under the generation lease; `applyEventToStore` stays the only store writer during a run.
- **The spoken rewrite runs only after the send settles**, and only if `voiceSpoken.messageId` is this turn's, in any phase (End right after the first chunk starts still rewrites; a `voiceSpoken` left from an earlier turn never does). `rewriteTurnToSpoken` keeps every step's tool calls, outcomes and reasoning, clears content, and puts the spoken text in the last step, so the next prompt holds only what was heard. `interrupt()` after `done` is a no-op.
- **Whisper is resident for the session**: `prepare` preloads base; nothing releases it until exit. Every exit runs, in order: `phase = closed`, mic stop, `turn.interrupt()`, `engine.release()` (Whisper, and TTS only when auto-speak is off), the keep-awake release, `setVoiceOutputActive(false)`. A re-entry awaits the previous exit.
- **Dictation's rules hold.** `wont_fit` is exactly `whisperFits` / `hasMemoryForCapture('base')`, so voice never runs where dictation would refuse base. Voice and dictation never overlap: the button needs dictation idle, and the composer is gone while `phase ≠ closed`. `useVoiceCapture` and `SpeechSegmenter` are untouched.
- **The mic runs only in `listening ∧ !micMuted`**, started imperatively by the controller on its own transitions, never by a reaction on `phase`, so a forced phase (automation) starts nothing. No echo capture: there is no barge-in.
- **Neural voices only.** The `system` engine reports no chunk progress, which `speaking` and the rewrite need.
- **The paywall is a seam.** Default locked, `openPaywall` only warns; the purchase flow calls `voiceEntitlement.register(source)` (`in-app-purchase.md`). A release build before that ships the icon locked.

## Traps and decisions

- **First audio at the first clause is a speech-library patch** (`release.md`): `firstChunk: 'clause'` cuts the first chunk at the earliest of a sentence end, `[,;:—]`+space after 3 words, or 12 words. Chat auto-speak never passes it.
- **Markdown is stripped in `TTSStore` for voice streams** (`stripMarkdown: false` to the engine), so stream progress offsets index the text the store appended. Thinking placeholders are recorded as ranges at the real append and excluded from `voiceSpoken.text`; string matching fails when a placeholder shares a chunk with reply text. `voiceSpoken` survives `stop()`.
- **A local model holds the first voice chunk** until the reply settles or 1.5 s pass: synthesis next to decoding roughly doubled time to first audio on Pixel 9 / S23. Measured on CPU only, so every local backend holds; remote models never do.
- **The library's chunk-progress callback is one global slot**, cleared by a stream's cleanup. A new stream is created only after the previous one's cancel resolves (`waitFor`), and a turn ends only at `playbackState` idle, after finalize's cleanup. A second or third turn that never reaches `speaking` points here.
- **Keep-awake is counted** (`chat-flow.md`): the voice hold and a turn's hold coexist.
- **Exit on chat switch, background, blur and model change**: mic and Whisper can't run backgrounded, and the memory fit would be stale. iOS `inactive` (call, Control Center) doesn't end the session; returning to `active` while listening restarts capture.
- **`transcribing` and `thinking` share one cloud look**; errors are a subtitle until the next phase change, since every failure resumes listening.
- **Overlay, not a route**: `useChatSession` must stay mounted, and the bar shares the chat.
- **The cloud uses theme tokens** (`secondary`, `tertiary`, `accent.peach`, `inverseSecondary`), so in dark mode the periwinkle blob turns teal. It honours reduced motion.
- **Android gets no automation deep-link hosts**, so voice captures there go through `VoiceAdapter` (`voice-command-input`).

## Verification

- Unit: `src/services/voice/__tests__/` (`cascadeEngine` holds the rewrite races, `endpointer`, `memoryFit`), `src/hooks/__tests__/useVoiceMode.test.ts` (entry order, exit matrix, mute, forced phase), `src/store/__tests__/VoiceModeStore.test.ts`, the `Voice*` component suites, `ChatScreen.voiceMode.test.tsx`, `ChatInput.test.tsx` (button swap and hiding), `ChatView.voiceInput.test.tsx` (bar replaces the composer), `src/services/tts/__tests__/speechLibFirstChunk.test.ts` (the patched built module), `TTSStore.test.ts` (voice stream, hold), `src/__automation__/__tests__/voiceAutomation.test.ts`.
- Visual: a per-task Flavour B spec driven by `voice?cmd=` (`docs/workflows/visual-capture.md`).
- By hand, on a high-tier Android phone and an iPhone with a neural voice, local model in airplane mode: a spoken turn (user and assistant rows marked Spoken, first audio before the reply ends); a tap mid-speech leaves only the spoken text; End while transcribing, thinking and speaking; mute; pull down to the bar and back; iOS listening → speech → listening still captures; the screen stays on through a 2-minute silent listen and sleeps after End; second and third turns still reach `speaking`.
