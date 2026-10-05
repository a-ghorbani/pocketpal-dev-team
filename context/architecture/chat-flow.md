# Chat Flow

## Purpose

How a chat turn is sent, streamed, persisted and rendered: tool-call and reasoning display, pending indicator, footer, context banner, reasoning pill, keyboard, session list. Elsewhere: the `runAgent()` loop (`agent-runner.md`), the remote wire and `/props` (`remote-servers.md`), talents (`pals-and-talents.md`), n_ctx and `activeModelCaps` (`model-loading.md`), text-to-speech (`tts.md`).

**Not on `main` yet:** the `redesign/phase-3` branch reskins the footer, header, and action bar, and open PRs #895–#897 add remote timing parts and a `remote-waking` banner. The previous version of this doc described them (`git show 1ad6ce1:context/architecture/chat-flow.md`); distill them back in as each lands.

## Code map

| Path | Role |
| --- | --- |
| `src/hooks/useChatSession.ts` | send / stop, `prepareCompletion`, `applyEventToStore`, `deriveSnapshotFromResult`, catch path |
| `src/services/agent/agentStateReducer.ts` | pure reducer from `AgentEvent` to `agentUiState` |
| `src/store/ChatSessionStore.ts` | sessions, messages, step writers, run UI state, banner state, `groupedSessions`; composer drafts (`sessionDrafts`, `NEW_CHAT_DRAFT_KEY`, `restoreUnsentText`) |
| `src/utils/chat.ts` | `stepToApiMessages` (turn to flat OpenAI messages), `derivedText`, `removeThinkingParts` |
| `src/screens/ChatScreen/ChatScreen.tsx` | wires the hook into `ChatView`; reasoning pill cycle (`persistReasoning`) |
| `src/components/ChatView/ChatView.tsx` | inverted list, `isPending`, keyboard, snackbars, the send funnel (`wrappedOnSendPress`) and the draft save / restore on a chat switch |
| `src/components/ChatView/BannerRow.tsx` | the single input-slot banner; does the cross-store reads |
| `src/utils/bannerVariantResolver.ts` | pure `resolveBannerVariant`, thresholds, `CONTEXT_LADDER` |
| `src/components/IncreaseContextSheet/`, `src/hooks/usePalLoadHint.ts` | increase-context slider, fit check and reload; the heavy-talent snackbar |
| `src/components/Message/Message.tsx` | row dispatcher; `renderAssistantTurn`; owns the one `AssistantTurnFooter` |
| `src/components/{TextMessage,ReasoningBlock,ThinkingBubble,Bubble}/` | content block; reasoning block; collapse state; pure shape |
| `src/components/TalentSurface/` | per-call dispatcher: `ToolErrorBlock` / TalentUI + `ToolMetricsFooter` / `ToolUsedChip` |
| `src/components/ToolConfirmationSheet/` | the approve / decline sheet for a gated tool call, hosted by `ChatScreen` |
| `src/components/AssistantTurnFooter/`, `PendingIndicator/` | turn chrome; the dot row under the newest turn |
| `src/utils/reasoningCapability.ts` | `resolveReasoningCapability`; UI in `ChatInput`, `ModelSettingsSheet` |
| `src/components/SidebarContent/` | drawer session list and pin menu |
| `src/components/ChatSearchBar/` | find-in-page bar: the draft, the debounced commit, the Android back handler |
| `src/utils/searchIndex.ts` | the visible-text projection behind the search count, the highlight and the jump fraction |

## How it works

1. `handleSendPress` records the open chat, then takes the generation lease (`model-loading.md`), waiting behind "Stopping…" while a stopped run drains. If the open chat changed meanwhile, it ends the lease, writes nothing, and puts the text back as the original chat's draft. Otherwise it reads the model and session and adds the user row. `prepareCompletion` builds the params and **creates the empty `assistant_turn` row before the run starts**.
2. The hook runs `for await` over `runAgent`. Each event goes through `agentStateReducer`, then `applyEventToStore`.
3. `applyEventToStore` routes events to store writes:
   - `step_started` → `pushAgentStep`
   - `token` → `updateActiveStepStreaming` (throttled to 30 ms), plus the TTS chunk and learn-from-stream
   - `step_finished` → `appendToolCall`, then `finalizeActiveStep`
   - `tool_call_finished` → `appendToolOutcome`
   - `run_finished` → `updateMessage`, then `recordCompletionSnapshot`
4. `run_failed` is rethrown into the catch path. The catch path runs UI stop, then either:
   - tags a turn that has partial content as `{interrupted, copyable, completionResult}`, or
   - deletes the empty turn and adds a system message (for "Context is full", it records a full snapshot instead).
5. `ChatView` renders one `Message` per row. `PendingIndicatorView` lives in the header of the inverted list, which puts it at the visual bottom.

```
idle ─run_started→ prefill ─content/reasoning token→ streaming_text
─marker_seen | token with toolCalls→ generating_tool_call ─tool_call_started→ executing_tool
any ─step_started (initial or follow-up)→ prefill
─run_finished→ done      ─run_failed→ failed (catch path then resets to idle)
```

## Contracts and invariants

**Storage and wire**

- Storage is rolled up: one `assistant_turn` row per turn, with outcomes nested in their step. Messages are stored newest-first (`[0]`). On the wire, `stepToApiMessages` flattens a step to an assistant message (`content`, `tool_calls`, `reasoning_content`), then one `tool` message per outcome (`src/utils/chat.ts:77`).
- Orphan guard: a call with no outcome gets a synthetic `{role:'tool', content:'aborted'}` message (`chat.ts:99`). Strict Jinja templates reject an unanswered `tool_call_id`, and an abort mid-tool leaves one behind.
- `step.toolCalls[i].id === outcome.callId` holds by construction: `appendToolCall` runs once per step, on `step_finished`, with the runner's normalised ids. Token deltas never write `toolCalls` (`useChatSession.ts:373-376`).

**Single writers**

- `applyEventToStore` is the only store writer during a run. Each step field has exactly one store action, as listed under How it works. `agentUiState` changes only through `setAgentUiState`, called with the reducer's output.
- Turn metadata:
  - `run_finished` writes `timings`, `completionResult`, `copyable` and `hitMaxTurns`.
  - The catch path writes `interrupted`, `copyable`, `completionResult` and `truncationLikely`.
  - The empty turn has no `copyable`.
- `lastCompletionResult` has one writer, `recordCompletionSnapshot`, called right after `metadata.completionResult` is written. That same action clears `dismissedBannerVariants` and updates `consecutiveFullFailures`. `setActiveSession` hydrates the snapshot from the newest turn. `resetActiveSession` and `removeMessagesFromId` (edit or regenerate) clear it.
- **`isStopping` means a send is waiting for the previous run to drain.** Only the send path writes it, around `acquireGeneration`; each send clears it when its own acquire resolves. Stop intent is the lease's `AbortSignal`: `handleStopPress` calls `lease.abort()` and the TTS stop, nothing else. While it is set, Send (`disabled`, `accessibilityState.disabled`), Regenerate, Regenerate with and Edit are disabled and ChatView's send funnel returns keeping the input, so at most one send waits. "Stopping…" also shows when Regenerate or Edit queue behind a live, unstopped run; that path is not gated.
- **UI stop clears the run UI at the abort, not at the drain.** `inferencing`, `isStreaming`, `isGenerating`, `agentUiState` (idle), `toolCallTokenCount` and keep-awake are cleared at the first of: the signal's `abort` event, finding it already aborted, or the send path's `finally`. A release-initiated abort gets the same UI. Run UI is set only while the signal is not aborted. After UI stop the loop writes persistence only, keyed by the run's own `messageId` / `sessionId`; `lease.end()` is the send path's last statement.
- **Keep-awake has two call sites in `useChatSession` and nowhere else**: taken when the send path sets run UI, released by UI stop.
- **The pending tool confirmation is hook-local React state, not a store field**, so `applyEventToStore` stays the only store writer during a run. `useChatSession` sets it from `confirmToolCall` and clears it on resolve, in the send path's `finally`, and on unmount (resolving `false`), so a pending confirmation never outlives its run. Answers are keyed by `callId` and the first one for an id wins: any other id, or a second answer for a settled id, is a no-op. That is what makes a late `onDismiss` from the previous call's close animation harmless while the next call is already pending, because the shared `Sheet` reports a programmatic close as a dismiss. `ChatScreen` keys the sheet by `callId` so each call gets a fresh instance, and dismissing is a decline.
- `contextInitParams.n_ctx` is a single global, written only by `setNContext` (Settings, `IncreaseContextSheet`). Sessions cannot override it.
- `persistReasoning` sets `newChatThinkingOverride` / `newChatReasoningEffort` only when there is no session. Creating, resetting or switching a session clears them, and a staged override makes the new session `'custom'`.
- **`sessionDrafts` writers:** ChatView on a chat switch (only when the composer changed since it last synced, joining) and on send (clears the open key, the new-chat key included); `deleteSession`; a cancelled send (`restoreUnsentText`: restored text first, nothing for a deleted chat).
- `ChatSessionStore` never reads `ModelStore`. `BannerRow`, `ChatView` and `usePalLoadHint` do the cross-store reads.

**Rendering**

- Within a step, blocks render in this order: reasoning (if non-empty), content (if non-empty), then one block per call in `toolCalls` order. An empty field emits nothing (`Message.tsx:340`).
- `ReasoningBlock` renders outside the bubble shell and never shows the sender name. The name goes on the first content block.
- Reasoning collapses once the step has content or `partial === false`, and only on that transition. After the user toggles it, `ThinkingBubble.userToggledRef` keeps the user's choice.
- For each call, `TalentSurface` renders nothing until the outcome exists, then `ToolErrorBlock` for an error, else the registered TalentUI's non-null `renderResult` (plus `ToolMetricsFooter` when `call.metrics` is set), else `ToolUsedChip`. A missing TalentUI (e.g. in an old chat) falls back to the chip.
- **A gate outcome renders its user-facing text, never its model-facing one.** Declined, cancelled and timed-out are error results, so `TalentSurface` routes them to `ToolErrorBlock` and they never reach the chip. What shows is the outcome's `errorMessage`; the `summary` / `responseContent` half carries the steering wording addressed to the model ("Do not call it again unless the user asks") and stays off the screen. The runner authors both (`agent-runner.md`).
- `ToolUsedChip` expands on tap to show the persisted call arguments and the outcome's `responseContent` with the untrusted markers stripped for display. It expands for every tool, never branching on a tool's source, and stays a plain row when there is nothing to show, so an old chip is unchanged. It adds no redaction of its own: the response was already redacted before it was stored. Because the chip re-renders on every streaming token, it is `React.memo`'d and both the argument formatting and the marker stripping sit behind a `useMemo` that runs only once the chip is expanded. Its tappable row carries a 44 dp minimum touch target, which leaves the visual density unchanged and is pinned by a unit test — a hit area is not provable by a screenshot.
- Every assistant row has exactly one `AssistantTurnFooter`, attached in `Message`'s outer JSX and never inside `Bubble`. It renders iff `timings || copyable || interrupted`, and each part checks its own field (see "Completion timings"). The run's outcome is not checked. The two remote parts are the exception: they check the turn's origin as well.
- Copy (`derivedText`) joins step contents only, with no reasoning and no tool JSON.
- `Message` must stay an `observer`. Streaming swaps `steps[last]` under a stable row reference, which a memo would miss.

**Completion timings**

- One type for both engines: `CompletionTimings` in `src/utils/completionTypes.ts`, nine named fields (`prompt_n`, `prompt_ms`, `prompt_per_token_ms`, `prompt_per_second`, `predicted_n`, `predicted_ms`, `predicted_per_token_ms`, `predicted_per_second`, `cache_n`) and **no index signature**, so an unread field cannot ride along unnamed.
- **What is persisted is a superset of what the engines report.** `metadata.timings` holds `PersistedTurnTimings` (same module): the nine plus `time_to_first_token_ms`, `draft_tokens` and `draft_tokens_accepted`, which `useChatSession` measures itself. They sit under one key with one rename consequence, so the writer and `AssistantTurnFooter` both name that type rather than reaching into an `any` metadata bag. TTFT is stored as `null` when no first token arrived.
- **Finite on write, tolerated on read.** `normaliseTimings` keeps only fields holding a finite number and drops everything else; an object with nothing left becomes `undefined`, so a turn carries no `timings` rather than an empty one. The remote engine normalises through `readFinish`, the local engine wraps llama.rn's result, and those are the only writers.
- The read side assumes nothing, because rows persisted by older builds hold the raw server object. Every numeric read in `AssistantTurnFooter` goes through `finiteNumber`, compared against `undefined` so a reported `0` still renders, and a part renders only for a finite value. A stored string used to throw in render (`.toFixed`) and a stored `NaN` used to print the literal text `NaN`; both now render no part.
- Stored rows are never migrated. Tolerating the read is what makes them safe.
- Two parts are **origin-gated, not presence-gated**: prompt speed (`prompt_per_second`, `components.bubble.promptTokensPerSec`) and cached tokens (`cache_n`, `components.bubble.cachedTokens`) render only when `completionResult.isRemote` is true. llama.rn reports both on local turns too, so presence alone would silently change the local footer; what the local footer shows is a separate decision. A remote turn missing prompt speed therefore means the server did not report it, while a local turn shows no such part whatever the engine reported.
- `cache_n` renders at `0`: a build that does not report prompt-cache reuse omits the key, while a cold prompt on a build that does reports `0`, and those are different facts.

**Pending indicator**

- The indicator belongs to `ChatView` and renders below the newest turn, never inside it. It is visible iff the status is prefill, generating_tool_call or executing_tool, or `isStopping` is set (`ChatView.tsx:822`). Because every `step_started` returns to `prefill`, it covers both dead zones: while the tool runs and before the follow-up's first token.
- The suffix reads "Stopping…" while a send waits for a drain; the Stop tap itself shows none. Otherwise it shows a label only while `pendingTalentNames` is non-empty, the token count from 10 tokens, and the elapsed time from 1 s.
- The reducer keeps the first talent names it sees and never clears them on a content token, because later deltas drop the function name.

**Context banner**

- Only one banner shows at a time. `resolveBannerVariant` is pure and returns the first match in this order: full, warning, remote-hedged, html-soft-cap, none (`bannerVariantResolver.ts:47`). The full and warning variants need both `effectiveNCtx` and a known `used`.
- `effectiveNCtx` is `activeModelCaps.effectiveContextLength` (`BannerRow.tsx:105`): the local `n_ctx`, or the active remote model's `/props` window. It is > 0 or undefined, never 0, because a 0 would read as a false "full".
- `contextFull` is `context_full || truncated || (remote && stopped_limit)`, or is set by the catch path. Full shows only while `used >= nCtx - AUTOCLEAR_RUNWAY`. That freshness check runs when the banner is read, so raising n_ctx clears the banner without a new turn.
- A dismissal lasts until the next snapshot, a session switch, reset or delete, or an edit or regenerate.
- A remote full always uses the `contextFullRemote` copy, which offers no increase advice.
- The increase CTA shows only when `hasFittingUpgrade` finds a ladder tier that `fits`. Confirm runs `setNContext` → `releaseContext` → `initContext`. On failure it restores the old value and re-inits, so the model is not left unloaded (if that re-init also fails, the banner's New-chat action stays reachable).
- Snackbars are separate from the banner and gated on `useIsFocused()`. The pal-load hint is also gated on `!reloadSnackbar`, and `onReloadStart` dismisses it in the same handler, so no frame shows two.

**Reasoning**

- `resolveReasoningCapability` is the only reader. It returns `Model.reasoning` for a local model or `ServerStore.remoteReasoning[id]` for a remote one, and falls back to the legacy `supportsThinking` field. Axis 2 is zeroed when axis 1 is `'no'`.
- Writers: `Model.reasoning` in `ModelStore` (load-time detection, `recordReasoningObserved`, `setReasoningOverride`), which routes remote ids to `ServerStore.remoteReasoning` (`recordRemoteReasoningObserved`, `setRemoteReasoningOverride`). Precedence is user > learned > detected: detection skips a `user` or `learned` entry (`ModelStore.ts:3266`).
- The first reasoning token calls `recordReasoningObserved` (which routes remote models to `ServerStore`). It never overrides `source: 'user'` or an existing `'yes'`.
- On the local wire, `reasoning_format` is always `'auto'` so think markers don't leak into content. `chat_template_kwargs` carries `enable_thinking: false`, sent only to reasoning-capable models, and `reasoning_effort` (`useChatSession.ts:162`).
- "Off" is only a hint: any reasoning the model returns is still displayed. `src/services/tts/thinkingStripper.ts` strips it from audio only.
- Effort values are stored in `EFFORT_LEVELS` order. The pill steps through them from off and back to off, and is hidden when axis 1 is `'no'`.

**Keyboard**

- One `keyboardOcclusion = max(0, |keyboard.height| − insets.bottom)` drives the input translate, the suggested-prompts overlay and the list spacer (`ChatView.tsx:424`). The layout math has no `Platform.Version` fork.

**Search** (PR #622 only)

- Find-in-page never swaps `ChatView.messages`; the empty state and banners stay tied to the real conversation.
- Count equals highlight: one projection counts and marks, and `TextMessage` skips link preview while a query is committed.
- The store holds only the committed query. Keystrokes stay in `ChatSearchBar`'s draft; a 200 ms debounce commits, navigation flushes a pending commit instead of moving, unmount cancels it.
- `ChatView` scrolls for search once per `searchNavSeq` step (every commit and next / previous), never on re-render.
- Android back exits search only while the bar is mounted and the screen focused (`useFocusEffect`).

## Traps and decisions

- **Fenced code is not searchable.** `CodeRenderer` re-reads the raw HTML, so `<pre>` is excluded from count and marks.
- **The search jump target is an html-length estimate**, placed via `viewPosition` / `viewOffset` above the keyboard rather than by layout measurement.
- **A 0-result commit consumes its navigation request**, so a match produced later by streaming does not scroll.
- **Decision: find-in-page, not filtering** (#603): filtering made a zero-result search look like an empty new chat.

- **Flush before structural writes.** `pushAgentStep` and `finalizeActiveStep` call `flushStreamingUpdate` first. Otherwise the previous step's last tokens land on the new step and show up duplicated under the tool block. Any new step writer must flush too.
- **Reference-equality publishing.** An unchanged reducer returns the same reference and the hook skips the write; a deep observable proxies its values, so the setter itself can't tell.
- **Isolated indicator.** The tool-token count is bucketed and `PendingIndicatorView` is its own observer. Without both, the FlatList header remounts on every token, which kills the dot animation and the timer.
- **100 ms yield.** Without it, Stop taps wait behind microtask resumption for seconds. It is a `setTimeout` raced against the lease signal: JS timers do not fire while the app is backgrounded, and a background auto-release waits for this run's `lease.end()`, so an abort must end the yield itself.
- **String-coupled native errors.** The catch path regex-matches the llama.rn errors "Context is full", "Failed to parse tool call arguments as JSON" and "failed to create MTP draft context"; a reword silently shows the raw error instead. Re-check on every llama.rn upgrade.
- **The user row is written after acquire.** Writing it first would put it into the prompt's `currentMessages` twice and stamp the pre-switch `contextId`; so during a drain wait the composer is empty and only "Stopping…" shows. A chat switch during the wait cancels the send: its text (not its images) becomes the original chat's draft. Delivering would start a run for a chat that is not open, with the global run UI shown in another.
- **The composer's leave-save can erase a draft.** ChatView saves the draft of the chat it leaves in an effect after the switch, and an empty save deletes. It writes only when the composer changed since it last synced (restore or send), joining if the store moved meanwhile; otherwise a cancelled send's restored text would be erased.
- **A user Stop is not a failure.** Both engines resolve an aborted completion, so the run ends through `run_finished` with clean-finish metadata; `interrupted` and the empty-turn delete happen only when the engine rejects (`useChatSession.ts:774`).
- **Prompt overflow throws before any token.** The empty turn is deleted, and the full snapshot is kept only in memory, so a session switch loses it.
- **`used` counts the whole prompt, and unknown is not zero.** A llama.cpp server's `timings.prompt_n` excludes the prefix it served from KV cache, so the remote prompt total is `prompt_n + cache_n`, each key guarded on its own — now in `readFinish` (`src/api/servers/index.ts`), one function every server type shares because field presence decides. With normalised timings the sum runs on numbers, so a non-finite `cache_n` counts as absent instead of concatenating into a string token count. An old build omits `cache_n` and falls back to `prompt_n`. llama.rn's local `tokens_evaluated` is already the whole prompt. With no prompt count, `used` is absent (`useChatSession.ts:251`), and the resolver shows no full or warning banner.
- **Catch-path `used` reads the resolved window.** The abort and context-full sites pin `used` to `activeModelCaps.effectiveContextLength`, not `activeContextSettings.n_ctx`, which is never set for a remote model; a `0` there would fail the freshness gate and hide every remote full. When the window is unknown, `used` is absent.
- **`include_thinking_in_context: false` strips only inline `<think>` tags from prior `content`.** `stepToApiMessages` still sends `step.reasoningContent` as `reasoning_content`.
- **Timings and snapshot come from the run's last completion** (`finalResult`), not an aggregate over steps.
- **Session-list keys are localized labels.** `groupedSessions` keys each group by its label and inserts pinned first. If two labels translate the same, a group vanishes silently. Only `locales.test.ts` guards this.
- **Pinning is best-effort on purpose.** Failures are only logged (a pin is easy to retry; a row that doesn't move is honest feedback), and the store mirrors the pin only after `setSessionPinned` resolves. Export leaves out `pinned` and `settingsSource`, which are local state.
- **`star.svg` is stroke-only.** `.svgrrc` rewrites its stroke colour to the `fill` prop, so `fill="none"` paints nothing: for an outline, omit `fill` and pass `stroke`. SVGs are mocked in jest, so only a device capture catches a blank icon.
- **Android `keyboardDismissMode='none'`.** With `interactive`, every drag dismissed the keyboard, so hidden content could never be scrolled into view. The spacer tracks occlusion because an in-flight gate dropped it early on API ≤ 29.
- **Decision: rolled-up storage.** A turn renders as N blocks in one FlatList row, and `Message` owns the chrome. Per-step rows were rejected because they need footers coordinated across rows. Chrome inside `Bubble` was rejected because it caused the duplicate-footer bug, so `Bubble` stays a pure shape. There is no per-call placeholder: one ChatView indicator owns all feedback.

## Verification

- **Unit:** the `__tests__/` folders next to each code-map entry; key ones are `Message.assistantTurn` (block order, footer), `ChatView.assistantTurn` (indicator), `ChatView.keyboard`, `BannerRow`, `bannerVariantResolver`, `useChatSession.*` (`useChatSession.stop` for Stop, drain and release-initiated stop), `ChatSessionStore.assistantTurn`.
- **E2E** (`e2e/specs/features/`): `talent-tool-use`, `thinking`, `thinking-pal-override`, `graded-effort-override`, `remote-reasoning`, `context-banner`.
- **By hand:**
  - A `render_html` turn: the indicator covers both dead zones, and the turn has one footer.
  - Stop mid-stream: Send returns at once with no indicator, and the turn keeps its partial text with a normal footer (copy, plus timings when the engine returned them), not an interrupted one. Send again at once: "Stopping…" shows only until the previous run drains, then the user row and the normal indicator appear together. Send reads disabled to TalkBack / VoiceOver during the wait. Switch chat while "Stopping…" shows: nothing lands in either chat; the text is in the original chat's composer on return.
  - Fill n_ctx until the full banner appears. Raising n_ctx should clear it.
  - Android API 29: the keyboard does not hide the newest turn.
- **Search:** `ChatSearchBar`, `searchIndex`, `ChatSessionStore` (search), `ChatView.search`, `searchJump`, `TextMessage` tests. By hand: a tall message's bottom match lands above the composer; Android back closes search, staying in chat.
