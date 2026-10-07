# Agent Runner

## Purpose

`runAgent()` is the event-producing core of every chat turn: it drives engine completions, dispatches tool calls, and emits a typed event stream. This doc owns the event order and the abort, error and turn-cap contracts. Rendering, `AgentUiState` and per-event persistence belong to `chat-flow.md`; what a talent is and how a Pal opts in belongs to `pals-and-talents.md`.

## Code map

| Path | Role |
| --- | --- |
| `src/services/agent/AgentRunner.ts` | `runAgent` async generator, `EventQueue` (callback-to-iterator bridge), `executeOne`, `normalizeToolCallIds`, `buildNextTurnMessages`, `DEFAULT_MAX_TURNS` |
| `src/services/agent/AgentRunner.types.ts` | `AgentEvent` union, `AgentRunOptions`, `ToolConfirmationRequest` (PR #921 only), `AgentRunResult`, `AgentUiState` |
| `src/services/agent/agentStateReducer.ts` | pure `AgentEvent` to `AgentUiState` reducer (consumer side) |
| `src/services/agent/triggerMarkers.ts` | per-context cache of tool-call trigger markers from `grammar_triggers` |
| `src/services/agent/index.ts` | public surface |
| `src/hooks/useChatSession.ts` | sole consumer: builds options, iterates events, passes the signal of its per-run `abortRef` controller (PR #955: its generation lease's signal, `model-loading.md`) |
| `src/api/completionEngines.ts` | `CompletionEngine` implementations the runner calls |

## How it works

`useChatSession.handleSendPress` builds `AgentRunOptions`: `allowedTalentNames` from `pal.pact.talents`, `talentLookup` as `talentRegistry.get`, `triggerMarkers` from `triggerCacheRef.current.getMarkers(...)`, and the signal of its per-run `abortRef` controller (*(PR #955 only)* the signal of the generation lease it holds for the run). It then consumes `runAgent(opts)` with `for await`, running `agentStateReducer` then `applyEventToStore` per event, and rethrows on `run_failed`.

Each loop turn:
1. if the signal is aborted, leave the loop before `step_started` and end with `run_finished`; else emit `step_started` (*(PR #955 only)* `step_started` first, then on an aborted signal `step_finished` with no calls);
2. call `engine.completion` with a stream callback that pushes `token` and, at most once per step, `marker_seen` into the `EventQueue`;
3. drain the queue until the promise settles;
4. emit `step_finished` carrying the normalized tool calls;
5. if there are calls, run each serially through `executeOne` between `tool_call_started` and `tool_call_finished`;
6. rebuild `messages` with `buildNextTurnMessages` and loop.

A step with no tool calls ends the run with `run_finished`. When `turn` reaches `maxTurns` while the model still wants tools, the runner schedules one forced final turn: `tools` stripped, a user-role budget-exhausted nudge appended.

## Contracts and invariants

- **Event order.** There is exactly one `run_started` first. Each `step_started(N)` is followed by `step_finished(N)` before any `tool_call_*` for that step. Each `tool_call_started` gets exactly one `tool_call_finished` before the next call or step. The run ends with exactly one of `run_finished` / `run_failed` (`runAgent`).
- **Within a chunk, `token` is enqueued before `marker_seen`.** The reducer relies on this order.
- **Engine failure emits no `step_finished`.** A rejected `engine.completion` yields `run_failed` and returns, so the consumer's in-flight step keeps `partial: true`. Any other throw in the generator also becomes `run_failed`.
- **Tool failures are outcomes, not run failures.** `executeOne` never throws. It returns a `type:'error'` result for all of these: a name not in `allowedTalentNames` ("not enabled for this Pal"), an empty name, a name with no registered engine ("not available on this device"), invalid JSON arguments, an engine throw, or (PR #921 only) any gate outcome below. The loop continues to a follow-up turn so the model decides what to do.
- *(PR #921 only)* **Gates are engine-declared and runner-enforced.** An engine declaring `requiresConfirmation` is asked about through `AgentRunOptions.confirmToolCall` after the arg parse and before `execute`; one declaring a finite `timeoutMs > 0` has `execute` raced against that deadline and the run signal, receiving `ctx.signal`. Declined, cancelled and timed-out are ordinary error outcomes, so `tool_call_started` / `tool_call_finished` still pair on every branch. `confirmToolCall` cannot make a run emit `run_failed` by any path — a rejection, a `false`, a missing handler, a throwing `requiresConfirmation` getter, or a synchronous throw — and that is enforced structurally, by running the gate inside the same `try` that wraps `execute`, rather than by the gate's own error handling.
- *(PR #921 only)* **A gate outcome carries two texts.** `toolErrorOutcome` takes a model-facing `summary`, which is also what goes on the wire as `responseContent`, and a separate user-facing `errorMessage` — for declined, cancelled and timed-out alike. The steering wording ("Do not call it again unless the user asks") must never reach the screen, and the user-facing line must never reach the model. The strings stay English here, because the runner imports no l10n (`chat-flow.md` owns what renders them).
- *(PR #921 only)* **Confirmation fails closed.** A missing `confirmToolCall`, a `false`, or a rejection all decline. The prompt is raced against the run signal, so an abort resolves the call as cancelled even if the consumer's promise never settles; an already-aborted signal cancels without prompting. An unanswered gate parks the run indefinitely: there is deliberately no deadline, because a timer would override a user still reading the sheet. It is bounded by the answer or by Stop, and the screen is released to sleep while it is pending — re-taken on the answer only while the run is still generating (`chat-flow.md`).
- *(PR #921 only)* **An engine declaring neither gate runs the pre-change path** — `execute(args)` with one argument, no race and no timer — so built-ins behave exactly as before. A test asserts the call arity, because the deadline branch always passes a `ctx`. *(PR #963 only)* Whichever of #921 and #963 lands second reconciles: this branch passes `{signal}` when the run has one, and the arity test flips.
- **The whitelist check runs before the registry lookup.** A talent registered globally is still refused for a Pal whose PACT omits it.
- **Tool-call ids are never null downstream.** `normalizeToolCallIds` fills a missing id with `call_<seed>_<idx>`, where the seed is the run's `Date.now()` plus the turn. The same list rides `step_finished.toolCalls` and the outcomes' `callId`, so `step.toolCalls[i].id === outcome.callId` holds by construction. Strict Jinja templates reject `tool_call_id: null` on the next turn. *(PR #921 only)* It also replaces an id an earlier call in the same batch already used, because the confirmation sheet settles a pending call by id: with a repeat, a late `onDismiss` from the previous call's close animation would answer a different call than the one it closed.
- **The runner owns the Stop → `engine.stopCompletion` translation.** Its `abort` listener (`onAbort`) calls it; a failure is logged, never thrown. On `main` only `handleStopPress` aborts the run signal; `ModelStore._releaseContextInternal` calls `engine.stopCompletion()` and awaits the active completion itself, without aborting the run. *(PR #955 only)* One call per abort while a completion it started is unsettled (`stopQuietly`); Stop and a context release both just abort the lease.
- **Runner exit.** On `main`, `finally` only removes the abort listener. *(PR #955 only)* The runner never ends while a completion it started is unsettled: if the consumer stops iterating or a yield throws, `finally` stops it once (not again when the signal already aborted it) and awaits it, so the holder's `lease.end()`, and the release waiting on it, follow the engine.
- **Zero React / MobX / store imports in the runner.** Everything arrives through `AgentRunOptions`. It never persists, renders, or holds UI status.
- **`AgentRunResult.steps` is always `[]`.** The consumer reconstructs steps from events. `hitMaxTurns` is `turn >= maxTurns` at exit.
- **The iterator is single-consumer.** `EventQueue` has one waiter slot. There is no concurrent-run guard inside the runner. *(PR #955 only)* The generation lease serialises runs (`model-loading.md`).
- **`DEFAULT_MAX_TURNS` (5) is exported on purpose.** `useChatSession` passes it as `maxToolTurns` to `collectSystemPromptFragments`, and the search grounding fragment advertises `maxToolTurns - 1` tool calls (`WebSearchEngine.systemPromptFragment`). Changing the cap changes the prompt.

## Traps and decisions

- **Abort does not interrupt a running tool.** Once `engine.execute` is awaited it runs to completion, `tool_call_finished` is emitted, and the loop breaks at the turn boundary on `signal.aborted`; timeouts belong to the talent/provider (for example `withTimeout` in `src/services/search/providers/http.ts`). *(PR #963 only)* The runner still never interrupts a tool, but `executeOne` passes the run signal itself as `ctx.signal` to every engine whenever the run has one, with no race, timer or wrapping controller; the engine cancels cooperatively. The search engines do, so Stop ends an in-flight search at once as a `cancelled` error outcome; local engines ignore `ctx`. Later calls in the same batch still dispatch, and a search there returns `cancelled` without a fetch. *(PR #921 only)* An engine that declares a deadline opts into cooperative cancellation: it receives `ctx.signal`, Stop resolves the call immediately rather than after the deadline, and a late settle is ignored. Network tools need this because a run must not hold "Stopping…" for the length of a request.
- **Aborted runs end in `run_finished`, not `run_failed`,** so the hook writes the same metadata as a clean finish; the run UI was already reset to idle at the abort (`chat-flow.md`, UI stop). The `interrupted` tag and the empty-turn delete belong to the hook's catch path, reached only when the engine rejects (see `chat-flow.md`, How it works).
- **`token.delta.content` / `reasoningContent` are cumulative for the step, not increments,** despite the name: both engines pass accumulated text, as llama.rn's callback does (`openai.ts` "Pass accumulated content"). A consumer must replace, or diff against the previous value (as the TTS path does).
- **One stop is enough, and it must be.** Timers do not fire in the background, so nothing repeats a stop. Native's flag stays set until the next `llamaCompletion`, whose `rewind()` runs on the JS thread before scheduling. *(PR #955 only)* The patch re-applies a stop that arrived during `getFormattedChat` (`release.md`), shipped only because Metro resolves llama.rn's `src/`. `bench` sees a stale stop. `OpenAICompletionEngine` creates its controller synchronously and the request rejects on an already-aborted signal. On every llama.rn upgrade re-check that `rewind()` is the only native clear.
- **Stream chunks after abort are dropped twice.** `llama.rn`'s `stopCompletion` is non-blocking and native keeps calling back for seconds. The runner's stream callback ignores chunks once `signal.aborted`, and the hook's loop also skips queued `token` events. Lifecycle events still flow.
- **The next-turn assistant message uses `result.content`, never `result.text`.** `text` contains the raw tool-call markup and arguments. Replaying it would render the call twice, double the prompt, and break the KV-cache prefix match.
- **Forced final turn.** Tools are stripped, marker scanning is off, and any `tool_calls` the model still emits are ignored. An abort during the last tool round skips it. This design makes the run end with an answer instead of an unanswered tool request.
- **Metrics are per step, copied onto each call.** `metrics = {tokens, durationMs}` counts tool-call token events and the time from the first one. It is attached only when such tokens were seen, and repeated on every call of a multi-tool step, which overstates per-call cost. The stream cannot attribute tokens to individual calls.
- **Tool dispatch is serial.** Paired start/finish events interleave cleanly with yields, and today's local talents gain nothing from parallelism. Reassess if network talents multiply.
- **An async generator, not a callback.** `for await` lets the consumer run the reducer and persistence in lockstep with each event.
- **Marker detection is local-only.** `triggerMarkers` come from a local Jinja `getFormattedChat` call, so they are `[]` in server mode (no `modelStore.context`) and on compute failure. `tool_call_started` then drives the status flip one beat later. The closure form of `getFormattedChat` is required. A bare `.bind` calls it without `{tools, jinja: true}` and silently returns no markers.

## Verification

- Unit: `src/services/agent/__tests__/` (`AgentRunner.test.ts` covers event order, abort, forced final, the no-store-imports check, and (PR #921 only) the gates — approve, decline, fail-closed, abort while pending, deadline, Stop mid-execute, and the untouched ungated path; (PR #963 only) `run signal reaches the talent`: `ctx.signal` is the run signal itself, args-only `execute` without a signal, both searches of a batch cancelled by Stop during the first; `agentStateReducer.test.ts`; `triggerMarkers.test.ts`).
- Hook integration: `src/hooks/__tests__/useChatSession*.test.ts`.
- e2e: `e2e/specs/features/talent-tool-use.spec.ts` (Pal with `render_html`; tool call and follow-up on device).
- By hand: ask a Pal with `calculate` for arithmetic and tap Stop mid-stream. Send returns at once, the partial text stays with a normal footer, and no follow-up turn runs.
