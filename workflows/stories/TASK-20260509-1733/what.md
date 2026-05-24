# Tool-Loop Cache Stabilization — Architecture Delta

**Purpose**: story-scoped delta on `context/architecture/chat-flow.md` for
TASK-20260509-1733 (GOOA-19). Captures the design contracts the
implementation must obey to satisfy intent-brief Steps 1–4: per-turn KV
diagnostics, byte-stable `assistant_turn.steps[]` → API message
reconstruction, lazy-grammar mode where the template supports it, and a
flag-gated unconstrained→constrained two-stage fallback.

Layered on PR #709 (branch `pr-709`); references in `worktrees/PR-709/…`
are the source of truth for **(C)**.

- **(C)** current behaviour from PR #709 source
- **(P)** proposal, open for challenge
- **(?)** open question
- **(D)** decision

---

## 1. Data model

Chat-flow §1 already documents the rolled-up `AssistantTurn { steps: AgentStep[] }`
shape. This story does **not** change the persisted schema. It adds
in-memory diagnostics that ride alongside the run, plus a new wire
contract on the existing step → API-message projection.

### 1a. Existing shapes (C)

From `worktrees/PR-709/src/utils/types.ts:35-70`:

```
AgentStep
  content?:          string                  // visible preamble / final answer
  reasoningContent?: string                  // <think>…</think>
  toolCalls?:        AgentToolCall[]
  toolOutcomes?:     AgentToolOutcome[]
  partial?:          boolean

AgentToolCall
  id:        string                          // synthesized `call_<seed>_<idx>` when llama.rn returns null
  type?:     'function'
  function:  { name: string; arguments: string | Record<string, unknown> }
  metrics?:  { tokens, durationMs }

AgentToolOutcome
  callId:          string
  toolName:        string
  result:          TalentResult
  responseContent: string                    // sent back as role:'tool' content
```

(C) `function.arguments` is **either string or object** depending on
llama.rn's parse path (`chat.ts:48-62` `toWireToolCall`). This is the
proximate cause of byte-instability across turns.

### 1b. New per-turn diagnostic record (P)

In-memory ring, dev-mode only, not persisted, not user-visible. One
entry per `step_started`, finalized on `run_finished` / `run_failed`.

```
TurnDiagnostic
  turn:                number
  messageId:           string
  startedAtMs:         number
  promptHash:          string                // stable hash of rendered prompt string
  promptByteLength:    number
  promptTokenLength:   number | null         // surfaced from native
  lcpTokensVsPrev:     number | null         // tokens; LCP vs prior turn
  lcpRatio:            number | null         // lcpTokensVsPrev / promptTokenLength
  tokensCached:        number | null         // from CompletionResult (new, §1b.iii)
  nPast:               number | null         // from CompletionResult (new)
  promptMs:            number | null         // CompletionResult.timings.prompt_ms (existing)
  promptPerSecond:     number | null
  templateGrammarMode: 'lazy' | 'eager'
  twoStageFlag:        boolean
  twoStageStage?:      'unconstrained' | 'constrained'
```

Rules: (1) recorder reads only event payloads + `lastResult`; never
store state. (2) `promptHash` content-only and deterministic; **(?)**
algorithm. **(P)** FNV-1a-64 hex. (3) `lcpTokensVsPrev` in **token**
space, not string space — must match runtime cache addressing.
(4) writes only under `__DEV__`; production no-op (I6).

### 1b.iii Native fields to re-include on `CompletionResult` (P)

`completionTypes.ts:78` says `CompletionResult` "excludes local-only
fields (chat_format, tokens_cached, completion_probabilities)" — a
deliberate truncation. **(P)** re-include `tokensCached`, `nPast`,
and `promptTokenLength` (the latter mapped from native
`prompt_token_count`; see §1c D-naming-snake-on-wire-camel-in-app):

```ts
interface CompletionResult {
  // …existing…
  tokensCached?:       number;   // (P) mapped from native `tokens_cached`
  nPast?:              number;   // (P) mapped from native `n_past`
  promptTokenLength?:  number;   // (P) mapped from native `prompt_token_count`
}
```

`LocalCompletionEngine.completion` (`api/completionEngines.ts:36-51`)
forwards all three; the snake→camel mapping lives there.
`OpenAICompletionEngine` leaves them undefined; recorder treats
`undefined` as "unavailable," not as a budget violation.

### 1c. Tokenized-prompt-length surfacing (D)

Two paths: (P-A) new `tokenizePrompt(prompt) → number` bridge call;
(P-B) piggyback on completion. **(D) D-prompt-token-length-piggyback**:
choose P-B. One bridge round-trip per turn vs two; mobile-budget
constraint (I6). LCP-vs-prior-turn requires the prior tokens, kept in
a JS-side `Map<promptHash, number>` LRU on the recorder.

**Naming convention (D) D-naming-snake-on-wire-camel-in-app**: the
native llama.rn bridge surface emits `snake_case` (matching
llama.cpp). The TypeScript app surface uses `camelCase`. The mapping
is performed once, at the engine boundary
(`api/completionEngines.ts`'s `LocalCompletionEngine.completion`
result-shaping step), and from that point on the app uses the
camelCase name end-to-end:

| Wire (native) | App (TS, end-to-end) |
| --- | --- |
| `prompt_token_count` | `promptTokenLength` |
| `tokens_cached` | `tokensCached` |
| `n_past` | `nPast` |
| `prompt_ms` (already exists) | `promptMs` |

`TurnDiagnostic` (§1b) uses the camelCase names; `CompletionResult`
(the app-side type returned to runners) likewise exposes only the
camelCase names. Snake-case appears only in the engine adapter.

### 1d. Lazy-grammar config (P)

Computed once per `(modelHash, toolsetHash)` at session start; not
persisted; not re-probed mid-conversation.

```
TemplateGrammarSupport
  supportsTriggers:  boolean        // grammar_triggers non-empty
  triggerMarkers:    string[]       // already cached (C)
```

(C) markers are extracted from
`getFormattedChat({tools, jinja:true}).grammar_triggers` and cached at
`services/agent/triggerMarkers.ts:44-78`. New field is
`supportsTriggers = triggerMarkers.length > 0`.

**(D) D-capability-probe-once**: `supportsTriggers` is a property of
the `(model, toolset)` pair, not of any individual turn. Probing it
with the live `messages` array makes the outcome input-dependent (a
template might emit `grammar_triggers` only past some context length,
or only when prior assistant messages contain a marker — this is
template-author-defined behavior). To keep the capability flag stable,
it is **probed once per session** for each `(modelHash, toolsetHash)`
key with a **synthetic minimal-message body** (`[{role:'system',
content:''}, {role:'user', content:''}]`) and cached in
`templateGrammarSupportCache` (§5). On toolset change mid-session
(rare; tools are pal-derived and stable for a chat) the cache is
invalidated for the new key and re-probed.

Invariant **I8**: trigger-presence outcome is deterministic for a
given `(modelHash, toolsetHash)` regardless of conversation history.
`how.md` tests this by probing the same `(model, toolset)` pair with
two different message bodies (empty vs ~2k-token) and asserting equal
`supportsTriggers` values.

**(P)** When true, stay LAZY (PR #709 default — `tool_choice:'auto'`
+ `tools` + `jinja:true`). When false, fall back to EAGER whole-turn
JSON-schema constraint. See §1b.iii wire and §8 D-grammar-vs-prefix-
layer.

### 1e. Two-stage fallback flag (P)

Single boolean settings field, off by default:

```
CompletionParams (extension)
  enable_two_stage_fallback?: boolean   // (P) default false
```

Add as a version-5 migration in `completionSettingsVersions.ts:57-99`.
Only persisted addition this story makes.

### 1f. Glossary

- **LCP** — Longest Common Prefix in token space between turn-N's
  prompt tokens and turn-(N-1)'s.
- **Prefill reuse ratio** — `tokensCached / promptTokenLength`.
  Intent's ≥80% target is on this ratio for **append-only** turns;
  this is the canonical metric (§6 S7, C9 below); `lcpRatio` is the
  testable proxy when `tokensCached` is unavailable (e.g. on
  `OpenAICompletionEngine`).
- **Append-only turn** — turn N's prompt is turn-(N-1)'s prompt plus
  a strictly-longer suffix. Byte-stable serialization is what makes
  this property hold.
- **Lazy grammar** — installed only after a trigger token is seen
  (`tool_choice:'auto'` + `grammar_triggers`); prefix unconstrained.
- **Eager grammar** — applied whole-turn from the first token (e.g.
  `grammar: JSON_GBNF`). Used today only on the dev-tools screen.
- **Two-stage fallback** — Step-4 path: unconstrained run to detect
  intent, then a short args-only constrained run.

---

## 1b. External shape — wire to llama.rn

(C) Per-turn call site `services/agent/AgentRunner.ts:326-359`:

```js
engine.completion(
  {
    ...sessionCompletionSettings,   // version, jinja:true, enable_thinking, sampling
    messages,                       // ChatMessage[] flattened from steps[]
    stop: stopWords,
    tools,                          // pal-derived schemas
    tool_choice: 'auto',            // pal config
    // grammar: undefined  -- LAZY default
  },
  streamingCallback,
)
```

llama.rn renders `messages` to a prompt string via the model's chat
template (Jinja under `jinja:true`, falling back to chat-formatter in
`applyChatTemplate` `utils/chat.ts:180-229`), tokenizes, and decides
KV reuse from token-prefix identity vs the context's last-cached
prefix. **Grammar is not in the cache-match path (D)** — see §8.

### 1b.i Diagnostic observation point (P)

Recorder observes the rendered prompt string at the same boundary
llama.rn sees it, **without** changing what llama.rn does. Two
options: (P-A) call `applyChatTemplate(...)` from JS and pass
`prompt:` instead of `messages:` (changes production path); (P-B)
call `context.getFormattedChat(messages, undefined, {tools, jinja:true})`
purely to capture the rendered prompt — `JinjaFormattedChatResult`
already returns `prompt` (mock at `__mocks__/external/llama.rn.ts:35-39`).

**(P)** P-B. Costs one extra Jinja render per turn (cheap); does not
alter runtime-visible bytes (I4). Two distinct caches:

1. **Capability probe** (§1d, D-capability-probe-once) — keyed on
   `(modelHash, toolsetHash)`, probed once with a synthetic
   minimal-message body. Stores `supportsTriggers` and
   `triggerMarkers` (string list).
2. **Per-turn rendered prompt for diagnostics** — the recorder
   re-renders the live `messages` via `getFormattedChat(messages,
   undefined, {tools, jinja:true})` purely to compute `promptHash` /
   `promptByteLength`. This render is NOT used to decide grammar
   mode; it is read-only diagnostic state. Not cached across turns
   (each turn's messages are different by construction).

### 1b.ii Lazy mode params — no change vs PR #709 (C)

```
{ tools, tool_choice:'auto', jinja:true, /* no grammar */ }
```

This story does not introduce LAZY; it confirms it as the explicit
default and adds an EAGER fallback for templates that don't support
triggers.

### 1b.iii Eager mode params (P, fallback only)

When `templateGrammarSupport.supportsTriggers === false`:

```
{ tools, tool_choice:'auto', jinja:true,
  grammar: <whole-turn JSON-schema GBNF compiled from tools> }
```

Computed once per `(contextId, toolNames)` and cached alongside trigger
markers. **(?)** GBNF source — llama.rn helper, hand-rolled, or the
permissive `JSON_GBNF` used in the dev-tools screen
(`TestCompletionScreen.tsx:511`). **(P)** start with permissive
`JSON_GBNF`; tighten if Step-1 logs justify it.

### 1b.iv Two-stage fallback wire (P)

Activates only when `enable_two_stage_fallback === true` AND the
TWO_STAGE selector predicate fires (§3 hysteresis) AND model just
emitted tool-call intent.

1. **Stage A — unconstrained**. Wire: same `messages`, drop `tools`
   (or `tool_choice:'none'`), no grammar; trigger markers still scanned
   in stream. On marker seen, runner calls `engine.stopCompletion()`.
   **(D) D-stage-a-hard-stop**: hard-stop on marker. Args come from
   stage B; preserves prefix reuse for stage B and bounds stage-A
   tail length.
2. **Stage A finalize before stage B starts**. The runner
   immediately runs the existing post-completion path that produces
   `finishedResult.content` from the partial-preamble accumulated
   text — i.e. the same `removeThinkingParts` / parsed-preamble
   normalization that I7 already pins. The preamble step that
   ultimately persists is **the same `finishedResult.content`
   string** stage B uses to construct its prompt.
3. **Stage B — args-only constrained**. Prompt = stage-A prompt +
   `finishedResult.content` (the preamble step's persisted content,
   not the raw accumulated_text) + a forced opener (family-specific,
   e.g. `<tool_call>` for ChatML). Apply per-tool-args GBNF. Run to
   completion; parse args; emit `step_finished` for the tool call.
4. Follow-up step routes through the normal stable path.

**(D) D-two-stage-prefix-continuity**: stage B's transient prompt is
constructed from `finishedResult.content` (not raw accumulated_text)
so that the synthetic mid-step assistant message stage B sees is
**byte-identical** to what eventually gets persisted as the preamble
step's `step.content`. This is the prefix-equality property required
by I1/I3 across the boundary into the next persisted turn:
`stageB_prompt[0:|stageA_prompt + finishedResult.content + opener|]
== prompt_for_turn_N+1[0:same length]` modulo the forced opener,
which is sliced off before persistence (the opener is a stage-B-only
synthetic prefix; it never enters `step.content`). The opener choice
is family-specific and lives in `triggerMarkers.ts`-adjacent
metadata; if no opener is known for a template family, TWO_STAGE
is not eligible for that family (falls through to LAZY/EAGER).

The cost of this decision: stage A must complete its post-completion
preamble normalization before stage B can issue. In practice that
normalization is ~sub-ms (regex strip), so the user-visible latency
add is dominated by stage-B prefill, not the finalize step.

**(P)** Lives inside the runner (only layer with abort signal +
engine handle); must NOT alter byte serialization for any other turn.

**(?)** Q4 — opener-table coverage: which template families do we
have a known forced-opener for at PR-709 time? **(P)** seed with
ChatML (`<tool_call>`) and Llama3 (`<|start_header_id|>function`);
expand as Step-1 logs surface other families. If the opener is
unknown, the selector falls back to LAZY/EAGER for that turn.

---

## 2. Event flow

Existing event stream (chat-flow §2) is unchanged. This story adds
**diagnostic emission points** that listen to existing events; no new
`AgentEvent` types.

```
run_started                                 ─▶ diag: open run-record
  step_started turn=N isFollowUp=…          ─▶ diag: open turn-N record, render+hash prompt, tokenize, compute LCP vs (N-1)
    token+
    [marker_seen]
  step_finished turn=N (toolCalls?)         ─▶ diag: capture tokensCached/nPast/promptMs from lastResult
  [tool_call_started + tool_call_finished]+
  [step_started turn=N+1 isFollowUp=true    ─▶ diag: open turn-(N+1) record …
   token+
   step_finished turn=N+1]
run_finished | run_failed                   ─▶ diag: flush run-record to dev console
```

**(P)** Recorder is one object with three methods (`onStepStarted`,
`onStepFinished`, `onRunFinished`), wired into
`useChatSession.ts:455-473`'s `for await` adjacent to the existing
`agentStateReducer` + `applyEventToStore` calls.

Two-stage fallback runs TWO `engine.completion` calls inside one
step. The event surface stays unchanged; the recorder receives two
prompts/tokens/results and writes them as `twoStageStage:'unconstrained'`
then `twoStageStage:'constrained'`. The composite turn-record's
top-level `tokensCached` reports stage B; stage A is captured on a
sub-record. **(?)** precise sub-record shape.

---

## 3. State machine

Chat-flow §3 reducer is **unchanged**. Lazy/eager/two-stage is a
runner-internal selector, not a UI status. The selector reads from a
short window of prior diagnostics (not just one turn) so a single
noisy turn does not flip mode and a single recovered turn does not
flap back.

```
inputs:
  tgs     = templateGrammarSupport.supportsTriggers
  flag    = settings.enable_two_stage_fallback
  window  = last 3 append-only turn diagnostics for this session
  state   = currentMode  ∈ {LAZY|EAGER, TWO_STAGE}  (initial: LAZY|EAGER per tgs)

  -- "append-only turn" (testable):
  -- the messages array passed to engine.completion this turn
  -- is a strict prefix-extension of the prior turn's messages,
  -- by token comparison (no edit/delete since prior turn).
  -- Edits/deletes/retries reset the window (not append-only).

decision:
  if NOT flag: return tgs ? LAZY : EAGER
  if window has < 2 append-only turns measured: return tgs ? LAZY : EAGER

  enterTwoStage = (≥2 of last 3 append-only turns have
                    canonicalReuseRatio < 0.80)
  exitTwoStage  = (≥2 of last 3 append-only turns have
                    canonicalReuseRatio ≥ 0.85)

  if state == LAZY|EAGER and enterTwoStage: state := TWO_STAGE
  if state == TWO_STAGE and exitTwoStage:   state := tgs ? LAZY : EAGER
  return state

  -- "canonicalReuseRatio" = tokensCached / promptTokenLength when
  --   tokensCached is available (LocalCompletionEngine);
  --   else lcpRatio. See C9 below and §1f glossary.
```

The 0.80 / 0.85 hysteresis band keeps the selector from flapping when
ratios sit near 0.80. Window of 3 turns means single-turn anomalies
(e.g. one bad measurement, one mid-conversation edit treated as
non-append-only and skipped from the window) cannot flip mode by
themselves.

**(?)** Q5 — window size + threshold band: 3 / 0.80 / 0.85 are the
intent brief's numbers softened with a 0.05 band; bench data may
justify different values. **(P)** keep as written until Step-1 logs
land; revisit in Step-3 retro.

User-visible feedback:

| Mode      | UX                                                    |
| --------- | ----------------------------------------------------- |
| LAZY      | identical to PR #709 today                            |
| EAGER     | identical to PR #709 today                            |
| TWO_STAGE | identical end-state; (?) optional inter-stage marker — see §8 D-out-of-scope |

---

## 4. Contract

### 4a. Byte-stable serialization (P)

The single most important rule. The reconstruction path —
`stepToApiMessages` (`utils/chat.ts:72-89`) and the in-runner
`buildNextTurnMessages` (`services/agent/AgentRunner.ts:196-238`) —
must emit byte-identical output for byte-identical inputs.

1. **Tool-arg stringification, single site**. (C) `chat.ts:48-62`
   does `typeof argsValue === 'string' ? argsValue : JSON.stringify(argsValue ?? {})`.
   (C) `AgentRunner.ts:206-216` duplicates this inline. **(P)** Extract
   one shared `toWireArguments(args)` helper; both call sites use it.
2. **Deterministic key ordering**. **(P)** sort keys lexicographically
   at every depth at the stringification site. V8 insertion-order is
   stable in practice but not portable across hosts and not preserved
   across all parsers; sorting is byte-identical regardless. See
   D-canonical-arg-stringification (§8) and S5.
3. **No whitespace**. `JSON.stringify(value)` (no indent). No trailing
   newlines.
4. **Assistant `content` projection** (I7). (C) `AgentRunner.ts:459-465`
   uses `finishedResult.content` (parsed preamble), NOT
   `finishedResult.text` (raw bytes including tool-call markers + full
   args JSON). The comment at lines 449-458 documents this as the
   cause of "tool_call rendered TWICE on replay." **(P)** Lock as I7;
   add a regression test that fails if any path feeds `text` into
   `ChatMessage.content`.
5. **Reasoning-content projection**. (C) `chat.ts:80-82` and
   `AgentRunner.ts:218-220` both attach `reasoning_content` only when
   non-empty. **(P)** Unify: empty → omitted; non-empty → verbatim.
   `removeThinkingParts` (`chat.ts:398-423`) is regex-based and
   idempotent on already-stripped text — that property must hold for
   replays.
6. **Orphan-pair synthesis** (P). If a step has N `toolCalls` but < N
   `toolOutcomes` (mid-execution abort, crash), the next-turn wire
   currently sends an assistant-with-tool_calls whose `tool_call_id`
   has no matching reply. Strict Jinja templates reject this. **(P)**
   At wire-time, `stepToApiMessages` synthesizes the missing outcomes
   as `{role:'tool', tool_call_id:<call.id>, content:'aborted'}`.
   Persisted `step.toolOutcomes` is **never** retroactively populated —
   synthesis is wire-only. See §6 S4 and §9.9a.

### 4b. Diagnostic instrumentation contract (P)

1. Recorder reads only from events, computed prompts, and completion
   results. It must NEVER mutate `messages`, the prompt string, sampling
   params, or anything the runtime sees (I4).
2. Recorder writes to dev console under `__DEV__`; tree-shaken in
   production (I6).
3. At most one `Map<contextId, RingBuffer<TurnDiagnostic>>` in module
   scope; bounded ring (e.g. 32 entries / context).
4. `promptHash` and tokenization for LCP are guarded; failure
   degrades to `null` and never breaks the run.

### 4c. Hard invariants

- **I1 — byte-stable serialization across the 6 scenarios**. For any
  two calls to `convertToChatMessages([same persisted state])` /
  `buildNextTurnMessages([same args])` separated by retry, reload, or
  app restart, output bytes are identical. Tests cover the §6
  scenarios S1–S6.
- **I2 — grammar selection is independent of the cache-prefix layer**.
  Lazy/eager/two-stage decisions live in the runner / engine call
  layer. Any change that touches `convertToChatMessages` /
  `stepToApiMessages` / `applyChatTemplate` to influence grammar mode
  is a bug. Backed by D-grammar-vs-prefix-layer.
- **I3 — two-stage fallback only when triggered, args-only
  constrained pass**. Flag on AND TWO_STAGE selector predicate fires
  (§3 hysteresis on canonicalReuseRatio) AND tool-call intent.
  Stage-B grammar applies to args only, not the whole turn.
- **I4 — instrumentation must never alter the bytes the runtime
  sees**. Recorder may render the prompt for hashing (via
  `getFormattedChat` reuse) but must not pass that string back as
  `prompt:` and must not rewrite `messages`.
- **I5 — native bridge surfaces tokenized prompt length without
  changing the prompt itself**. New camelCase fields on
  `CompletionResult` (`tokensCached`, `nPast`, `promptTokenLength`)
  are read-only on the app side; native (snake_case) fields are
  mapped once at the engine boundary (§1c
  D-naming-snake-on-wire-camel-in-app).
- **I6 — mobile-budget guardrail**. No steady-state memory or per-turn-
  latency regression on the default (LAZY) path vs PR #709 baseline.
  Recorder is dev-only; trigger-marker cache and prompt-token LRU are
  bounded; two-stage is off by default. Operationalized in §4c-supplement.
- **I7 — assistant follow-up content uses `finishedResult.content`,
  not `text`**. Today documented as a comment; promote to invariant
  with a regression test.
- **I8 — capability-probe stability**. `supportsTriggers` is
  deterministic for a given `(modelHash, toolsetHash)` regardless of
  conversation history. Probed once per session; see §1d
  D-capability-probe-once.

### 4c-supplement. Operational metrics for I6 (P)

`how.md` is responsible for capturing baselines and gating merge.
This story fixes the metrics, the window, and the margin so `how.md`
cannot ship without them.

| Metric | Where measured | Window | Acceptance margin |
| --- | --- | --- | --- |
| `prompt_ms` per turn (LAZY default path) | `CompletionResult.timings.prompt_ms` per turn | turns 3..10 of canonical 3-turn S7 scenario, 5 repetitions, median per turn then averaged across turns 3..10 | post-merge ≤ 1.05 × pre-merge baseline (±5%) |
| Steady-state RSS | OS-level RSS reading after turn 10 (e.g. `adb shell dumpsys meminfo` on Android, `xcrun simctl spawn ... vmmap` on iOS sim, or whatever profiler `how.md` standardizes) | sampled at the end of each repetition; median of 5 | post-merge ≤ pre-merge + 10 MB |
| `tokensCached / promptTokenLength` (canonical reuse, S7) | `CompletionResult.tokensCached` per turn | turns 2..10 (turn 1 is full-prefill by definition) | ≥ 0.80 (intent acceptance #3); see §6 S7, D-canonical-reuse-metric |
| Recorder-disabled production-build size delta | bundle output | one measurement | ≤ +10 KB gz vs pre-merge |

**Baseline-capture protocol** (operationalized in `how.md`):

1. Tester checks out PR #709-base (`pr-709` branch tip pre-merge of
   this story) and runs the canonical 3-turn S7 scenario 5x on a
   nominated device + model pair. Records `prompt_ms` per turn and
   RSS snapshot.
2. Tester then checks out `feature/TASK-20260509-1733` and reruns the
   same scenario 5x on the **same device + same model file**.
3. Acceptance gate: above table's margins all hold. If RSS or
   `prompt_ms` exceeds margin, the merge is blocked pending a
   recorder-overhead investigation.
4. Device + model pair: at least one Android mid-tier device + qwen25
   1.5B; nominal coverage matrix in `how.md`.

This is a contract on `how.md`'s test plan; this `what.md` does not
prescribe the exact device list or profiler tool — only the metrics,
the window, and the margin.

### 4d. What each component renders / writes

| Component | Renders / writes | Does NOT |
| --- | --- | --- |
| `convertToChatMessages` (`utils/chat.ts`) | flat `ChatMessage[]` from full session | turn-internal step outcomes |
| `stepToApiMessages` (`utils/chat.ts`) | one assistant + N tool messages per step; orphan-pair synthesis at wire time | whole-session ordering |
| `buildNextTurnMessages` (`AgentRunner.ts`) | mid-loop append of one assistant + N tool messages | mutate prior turns |
| `toWireArguments` (P, new) | canonical sorted-key JSON string | anything else |
| `applyChatTemplate` | rendered prompt string | tokenize, KV cache |
| `LocalCompletionEngine.completion` | params forward + `CompletionResult` (now with `tokensCached`, `nPast`, `promptTokenLength`); snake→camel mapping at boundary | message construction |
| `AgentRunner.runAgent` | event stream; lazy/eager/two-stage selection | store writes (I2) |
| `TurnDiagnosticRecorder` (P, new) | dev-mode `TurnDiagnostic` records | runtime-visible bytes (I4) |
| `triggerMarkerCache` | string[] markers; (P) also `supportsTriggers` boolean | runtime-visible bytes |

---

## 5. Layer ownership (single-writer rule)

Existing chat-flow §5 ownership unchanged. New mutable surfaces:

| Field | Single writer |
| --- | --- |
| `TurnDiagnostic` ring entries | `TurnDiagnosticRecorder.{onStepStarted,onStepFinished,onRunFinished}` from `useChatSession.ts` event loop |
| `promptTokenCountLRU` (P) | `TurnDiagnosticRecorder` only (LRU keyed by `promptHash`) |
| `templateGrammarSupportCache` (P) | `triggerMarkerCache.probeOnce(modelHash, toolsetHash)` — single function that probes via synthetic minimal-message body on miss and returns cached `{supportsTriggers, triggerMarkers}` thereafter (§1d D-capability-probe-once) |
| `eagerGrammarCache` (P, GBNF) | `eagerGrammarCache.getOrCompute(modelHash, toolsetHash)` — single function performs both miss-path computation (the only writer) and cached-path read; reset on context swap |
| `enable_two_stage_fallback` (P, persisted) | settings UI only (gated on Step-4 going live); migration v5 in `completionSettingsVersions.ts` |
| `CompletionResult.tokensCached` / `nPast` / `promptTokenLength` (P) | `LocalCompletionEngine.completion` (mapped snake→camel at the engine boundary, §1c); `OpenAICompletionEngine` leaves undefined |
| Wire-only synthesized orphan-pair `{role:'tool', content:'aborted'}` (P) | `stepToApiMessages` only — persisted `step.toolOutcomes` never retroactively populated |

Multi-writer pain to keep in mind: chat-flow §5 records that
`step.toolCalls` was previously written from two sites and got
collapsed in cleanup #1. Same discipline for the diagnostic record —
single recorder, single ring per context, no scattered console.logs
that duplicate the same fields.

**Deferred cleanups** (out of scope here):

1. Move `tools` shape into a dedicated typed module rather than the
   `as ToolDefinition[]` cast in `useChatSession.ts:427`.
2. Unify `toWireToolCall` (chat.ts) and the inline tool-call
   stringification in `buildNextTurnMessages` into one shared helper
   (this story creates the helper; the chat-flow §5 promotion is the
   cleanup).

---

## 6. Canonical scenarios

Each scenario is a concrete shape the implementation + a unit test
must produce. Tests live under
`worktrees/TASK-20260509-1733/src/utils/__tests__/chat.test.ts` and
`.../services/agent/__tests__/AgentRunner.test.ts` (chat-flow §6
convention). S1–S6 are the 6 byte-stability scenarios from intent
Step 2; S7 covers Step 3, S8 covers Step 4.

### S1. Successful completion (text-only turn)

```
in:  steps = [{ content: "Hi!" }]
─────────────────────────────────────────
wire: [ { role:'assistant', content:'Hi!' } ]
hash stable across two calls; LCP vs prior turn ≈ full prior length
diag: templateGrammarMode='lazy' (default); twoStageFlag=false
```

### S2. Retry of a tool-using turn

```
state turn N persisted:
  steps = [
    { content:'Let me check.',
      toolCalls:    [{id:'call_42_0', function:{name:'datetime', arguments:'{}'}}],
      toolOutcomes: [{callId:'call_42_0', responseContent:'2026-05-09T17:33Z'}] },
    { content:"It's 8:28 AM." }
  ]
user taps "try again" → handleTryAgain walks back to prior user
message, removes assistant turn, resubmits.
─────────────────────────────────────────
wire on retry-N (turn replayed in transcript):
  { role:'assistant', content:'Let me check.',
    tool_calls:[{ id:'call_42_0', type:'function',
                  function:{ name:'datetime', arguments:'{}' } }] }
  { role:'tool', tool_call_id:'call_42_0', content:'2026-05-09T17:33Z' }
  { role:'assistant', content:"It's 8:28 AM." }
hash on retry == hash on original (modulo user-msg id/timestamp,
both byte-stable per their own writers).
```

### S3. Reload of the conversation (restart-then-resend)

```
restart app; load chat from disk; send a new user message.
─────────────────────────────────────────
bytes for messages[0..N-1] === bytes captured pre-restart.
Specifically: tool-arg strings re-stringified from persisted parsed
form match byte-for-byte the persisted-as-string form, because
toWireArguments is the only stringifier and uses sorted keys.
```

### S4. Orphan-pair synthesis

```
state: a step has toolCalls=[A,B] but toolOutcomes=[A_outcome] only.
─────────────────────────────────────────
wire from stepToApiMessages:
  { role:'assistant', content:'…', tool_calls:[A, B] }
  { role:'tool', tool_call_id:A.id, content: A_outcome.responseContent }
  { role:'tool', tool_call_id:B.id, content:'aborted' }    ← synthesized
persisted state: step.toolOutcomes still [A_outcome] only.
```

### S5. Tool-arg stringification (whitespace, key ordering, escaping)

```
in: call.function.arguments = { z:1, a:'héllo "world"', nested:{ y:2, x:1 } }
─────────────────────────────────────────
toWireArguments output:
  '{"a":"héllo \\"world\\"","nested":{"x":1,"y":2},"z":1}'
   - OBJECT keys sorted lexicographically at every depth
     (UTF-16 code-unit comparison; matches V8's sort default)
   - ARRAY element order preserved verbatim
   - non-ASCII NOT \uXXXX-escaped (default JSON.stringify)
   - internal quotes JSON-escaped
two calls with the same input produce the same bytes; round-trip
JSON.parse(out) deep-equals the input.
```

Numeric-string object keys (e.g. `{"10":x, "2":y}`) are sorted
lexicographically alongside string keys: in this example the output
is `{"10":x,"2":y}`, NOT `{"2":y,"10":x}`. This makes the result
independent of host JS engine enumeration order — see §9d.

### S6. Reasoning-text retention / `assistant.content` projection

```
in: step = { reasoningContent:'Let me think…', content:'The answer is 42.' }
    finishedResult = {
      text:              '<think>Let me think…</think>The answer is 42.',
      content:           'The answer is 42.',
      reasoning_content: 'Let me think…' }
─────────────────────────────────────────
next-turn wire (via stepToApiMessages):
  { role:'assistant',
    content: 'The answer is 42.',                  ← NOT `text` (I7)
    reasoning_content: 'Let me think…' }
include_thinking_in_context=false branch: reasoning_content removed;
content unchanged.
two calls with the same step produce the same bytes.
```

### S7. Long-context append-only turn under LAZY grammar

```
template supports grammar_triggers (qwen25 / ChatML). Turn N's prompt
is turn (N-1)'s prompt + new user message + new assistant→tool→
assistant block.
─────────────────────────────────────────
diag turn N:
  templateGrammarMode = 'lazy'
  promptTokenLength    = T_N
  tokensCached         ≥ 0.80 * T_N        ← canonical acceptance gate
  lcpTokensVsPrev      (advisory; see below)
  promptMs             ≪ full-prefill baseline
This is the success criterion for intent acceptance #3.
```

**(D) D-canonical-reuse-metric**: the ≥80% acceptance gate is on
`tokensCached / promptTokenLength` — what the runtime actually
reused. `lcpTokensVsPrev / promptTokenLength` is the **advisory
proxy** used (a) when `tokensCached` is unavailable (e.g. on
`OpenAICompletionEngine`, §9f) and (b) as a debugging signal when
`tokensCached` falls short of LCP, which indicates a runtime-side
cache eviction or context reset rather than a prompt-prefix problem.

These two ratios measure different things:
- LCP-vs-prior-turn = "did the bytes of my prompt prefix-match the
  prior turn's bytes?" — a property of the renderer (us).
- `tokensCached / promptTokenLength` = "what fraction of my tokens
  did the runtime actually reuse?" — a property of the runtime
  (llama.rn / llama.cpp's KV-cache match path).

LCP can be high while `tokensCached` is low (runtime evicted the
cache between turns); `tokensCached` can be high while LCP is low
(unusual; indicates a tokenizer-layer dedup we don't expect — flag
as bug). The acceptance gate is on the **runtime-observed** quantity
because that is what the user-perceived prefill latency depends on.
LCP shows up as a sub-acceptance signal in the diagnostic record so
we can distinguish the two failure modes.

### S8. Long-context append-only turn under TWO-STAGE fallback

```
flag enable_two_stage_fallback = true; TWO_STAGE selector fires
(≥2 of last 3 append-only turns with lcpRatio < 0.80; see §3)
→ runner picks TWO_STAGE.
─────────────────────────────────────────
stage A (unconstrained):
  wire: { messages, jinja:true, /* no tools, no grammar */ }
  trigger marker seen → engine.stopCompletion()
  runner runs post-completion finalize → finishedResult.content
    (parsed preamble; I7).
  diag sub-record: twoStageStage='unconstrained',
    tokensCachedRatio_A ≥ 0.80 (canonical metric, §6 S7)
stage B (args-only constrained):
  wire: { messages: messages
                  + [{role:'assistant', content: finishedResult.content}]
                  + [forced-opener-synthetic-prefix],
          tools, grammar: <args-only GBNF> }
  diag sub-record: twoStageStage='constrained'
combined turn outcome:
  step.content      = finishedResult.content       ← byte-identical to
                                                     what stage B saw
  step.toolCalls    = structurally-valid args from stage B
  step.toolOutcomes follow normally
acceptance:
  (a) tool args structurally valid
  (b) stage-A tokensCachedRatio ≥ 0.80 (stage-B is a short tail;
      not held to the same bar)
  (c) PREFIX-EQUALITY (D-two-stage-prefix-continuity):
      buildNextTurnMessages(state-after-this-turn) rendered prompt's
      first |stage-A-prompt + step.content| bytes ==
      stage-B's first |stage-A-prompt + finishedResult.content| bytes.
      Tested in AgentRunner.test.ts by reconstructing the next-turn
      prompt and asserting on the prefix slice.
```

---

## 7. State signals

No new signals. Existing `agentUiState.status` covers all UX states.
Diagnostic mode toggles are dev-only flags, not signals.

If the (?) "preparing tool call" UX marker (intent Q3) becomes a real
ask, we'd add a single derived `agentUiState.twoStageStage`. Per §8
D-out-of-scope, deferred.

---

## 8. Decisions

- **D-grammar-vs-prefix-layer**: grammar selection is **not** in the
  cache-match path. Lazy/eager/two-stage decisions live in the
  runner / engine call layer; they do not touch
  `convertToChatMessages` / `stepToApiMessages` / `applyChatTemplate`.
  Confirmed by Sage's GOOA-18 memo: in `llama.rn`, KV reuse is decided
  from token-prefix identity before grammar samples a token. Backed
  by I2.
- **D-fallback-default-off**: `enable_two_stage_fallback` defaults
  `false`. Until Step-1 logs prove a real-world reuse drop on
  representative models, the two-stage path is a complexity risk
  that can mask other bugs. The flag exists so we can A/B-verify
  Step 4 once instrumentation has data.
- **D-canonical-arg-stringification**: tool-call arguments are
  serialized with lexicographic key ordering at every depth via a
  single `toWireArguments` helper. (See §4a.2 and S5.) Insertion-
  order is V8-stable but not portable across hosts and not preserved
  across all parsers; sorted ordering is byte-identical regardless.
- **D-numeric-key-host-independence**: numeric-string object keys
  are sorted alongside string keys (UTF-16 code-unit), not given
  ascending-numeric priority. Closes the prior (?) about V8
  enumeration order — see §9d.
- **D-capability-probe-once**: `supportsTriggers` is probed once per
  `(modelHash, toolsetHash)` at session start with a synthetic
  minimal-message body; not re-probed mid-conversation. See §1d and
  I8.
- **D-prompt-token-length-piggyback**: tokenized prompt length is
  surfaced via `CompletionResult.promptTokenLength` (mapped from
  native `prompt_token_count`) rather than a separate
  `tokenizePrompt` bridge call. See §1c.
- **D-naming-snake-on-wire-camel-in-app**: native llama.rn fields are
  snake_case; the engine boundary maps them to camelCase, and the
  rest of the app uses camelCase only. See §1c.
- **D-stage-a-hard-stop**: stage A in TWO_STAGE hard-stops on first
  trigger marker, not let-complete. See §1b.iv.
- **D-two-stage-prefix-continuity**: stage B's transient prompt uses
  `finishedResult.content` (not raw accumulated_text) so the synthetic
  mid-step assistant message is byte-identical to what eventually
  persists as the preamble step. Stage A finalizes the preamble step
  before stage B issues. See §1b.iv and §6 S8 (c).
- **D-canonical-reuse-metric**: the ≥80% acceptance gate is on
  `tokensCached / promptTokenLength`; `lcpRatio` is the testable
  proxy when `tokensCached` is unavailable, and a debugging signal
  for distinguishing renderer vs runtime cache failures. See §6 S7
  and §1f.
- **D-out-of-scope**:
  - upstream `llama.cpp` patches (read the Sage memo's "Watch-for"
    list, do not block);
  - `llama.rn` bridge changes beyond exposing `tokens_cached`,
    `n_past`, and `prompt_token_count` (mapped to camelCase at the
    engine boundary; §1c);
  - any new chat-template authoring;
  - "preparing tool call" UX marker (intent Q3) — if Step-4 needs UX,
    open a separate story;
  - chat-flow §5 deferred state-signal de-duplication.

### Open questions promoted from the intent brief (?)

- **(?)** **Q1 — bench matrix**: which target model families are most
  sensitive to eager grammar on long turns?
  - **(P)** Bench dimensions: standard decoder-only (qwen25, llama3,
    llama32), SWA (gemma3, mistral-7B-v0.3 with SWA), hybrid (zamba2,
    granite-1B-MoE), recurrent (rwkv-7, mamba-2). Measure prefill
    reuse on a 3-turn tool loop with a shared prefix >2k tokens. SWA
    and recurrent are highest-risk per the Sage memo. The matrix is
    `how.md`'s job; this `what.md` only fixes the dimensions.
- **(?)** **Q2 — runtime-vs-product isolation**: does the failure
  reproduce in raw `llama.rn` outside PocketPal's reducer/store?
  - **(P)** Step-1 logs answer this. If turn-N append-only reuse is
    ≥80% on PocketPal's path, isolated to PR #709's reconstruction —
    no harness needed. If reuse <80% AND Step-2 unit tests don't lift
    it, run a 30-min `llama.rn`-only harness. Lives in `how.md`.
- **(?)** **Q3 — preparing-tool-call marker**: do we expose a marker
  earlier when args come from a short second pass?
  - **(P)** Not in scope. Pending indicator (chat-flow D4) already
    covers the "model is working" affordance during both stages. If
    Step-4 ships and the second pass is user-perceivable, open a
    separate UX issue.

---

## 9. Edge cases

### 9a. Orphan tool/assistant pair (mid-tool abort, prior session)

User aborted while tool B was in flight. On the next user message,
persisted state has `step.toolCalls=[A,B]` but
`step.toolOutcomes=[A_outcome]`. Wire-time synthesis (P, §4a.6, S4)
emits `{role:'tool', tool_call_id:B.id, content:'aborted'}` so strict
Jinja templates' tool_call_id back-ref check holds. Persistence not
retroactively mutated; bytes match across reloads. **(?)** literal
`'aborted'` vs more specific reason. **(P)** keep `'aborted'` — it
matches intent brief verbatim; bench will surface model misbehavior.

### 9b. Retry of a tool turn

`handleTryAgain` (`useMessageActions.ts:80-103`) walks back to the
prior user message and resubmits, removing the prior assistant turn
first. The retry does not carry the prior failed tool call. Byte
stability concern limited to (a) user-message bytes matching and (b)
preceding turns serializing identically (S2).

### 9c. Conversation reload

Persisted `function.arguments` may be string OR parsed object
(`chat.ts:48-62`). On reload, `toWireArguments` produces the same
canonical string regardless. Byte stability holds (S3).

### 9d. Non-ASCII / nested objects / escaped quotes / numeric keys

`JSON.stringify` emits non-ASCII as literal UTF-8 (not
`\uXXXX`-escaped) and JSON-escapes internal quotes. Combined with
sorted keys (§4a.2, §6 S5) this is deterministic.

**(D) D-numeric-key-host-independence**: `toWireArguments` sorts ALL
object keys lexicographically (UTF-16 code-unit comparison) at every
depth, INCLUDING numeric-string keys. This makes V8's
numeric-keys-enumerated-ascending-before-string-keys behavior
irrelevant — the canonical stringifier never reads insertion order or
enumeration order; it reads `Object.keys(o).sort()` and emits in
sorted order. Therefore S5's byte-stability claim holds regardless of
host JS engine. The previous (?) about numeric-key normalization at
the schema layer is closed: nothing to normalize.

### 9e. Template without grammar triggers

(C) `extractTextMarkers(triggers)` returns `[]` when the template
emits no `grammar_triggers`. (C) `useChatSession.ts:440-442` falls
through gracefully — `triggerMarkers` is `[]`, marker detection
disabled, `tool_call_started` drives the UX flip "one beat later."
**(P)** the same fact drives LAZY → EAGER fallback in §3, so the
selector reads from one source.

### 9f. Engine without `tokensCached` / `nPast`

`OpenAICompletionEngine` has no equivalent. Recorder treats these as
`null` and the §3 selector falls back to `lcpRatio` as the
canonicalReuseRatio source (D-canonical-reuse-metric). If even
`lcpRatio` is unavailable (first turn), the TWO_STAGE selector cannot
fire — the flag does not auto-disable; it just has no effect.

### 9g. Diagnostic recorder failure

Any recorder failure (hash crash, render throw, LRU corruption) is
caught and degraded silently — never breaks the run (I4 + I6).
`console.warn` once per failure class per session.

### 9h. Two-stage stage-A early stop without a marker

If trigger marker never fires during stage A (model decided not to
call a tool), stage A runs to natural completion. No stage B; result
treated as a normal text turn. End-state identical to a LAZY turn
that didn't call a tool.

---

## 10. What this doc is NOT

- not an implementation plan (`how.md`)
- not a test plan — fixes the **shapes** tests must produce (§6), not
  the suite
- not a record of bench results (CI artifacts / linked GOOA issues)
- not a TODO list

When this doc and a commit on `feature/TASK-20260509-1733` disagree,
the commit wins — but the same PR must update this doc. On merge, the
following collapse from `(P)` to `(C)`/`(D)` and absorb into
`context/architecture/chat-flow.md`: §1b.iii new `CompletionResult`
fields, §4a.1–6 byte-stable rules, §4c I1–I7, §5 single-writer
additions, §8 D-grammar-vs-prefix-layer / D-fallback-default-off /
D-canonical-arg-stringification.

**Cleanup reminders**:

1. `TurnDiagnosticRecorder` ring + console emission is dev-mode
   instrumentation; remove on GOOA-19 sign-off (or promote to a
   dedicated store if surfaced in-app).
2. `enable_two_stage_fallback` is a temporary feature gate; retire
   in a follow-up once bench data justifies default-on or default-
   off-forever — do not let it ossify.
3. Orphan-pair literal `'aborted'` (§9a) is provisional; promote to
   tested constant or reason enum once model-behavior data exists.
