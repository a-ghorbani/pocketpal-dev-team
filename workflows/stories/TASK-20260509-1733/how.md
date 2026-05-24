# Implementation Plan: PocketPal-side stabilization for tool-loop KV cache reuse

**Purpose**: executable worklist for `feature/TASK-20260509-1733`. Lands the four scope steps from `intent-brief.md` against the design contracts in `what.md` (LGTM round 2). Reference WHAT sections by number; do not re-derive design content here.

---

## Metadata

- **Task ID**: TASK-20260509-1733
- **Worktree**: `./worktrees/TASK-20260509-1733`
- **Branch**: `feature/TASK-20260509-1733` (stacked on `feature/TASK-20260502-2115` = PR #709 head)
- **Native Changes**: NO — verified: this PR touches no `package.json`, `ios/`, `android/`, `Podfile`, or `build.gradle`. The new fields (`tokensCached`, `promptTokenLength`) are surfaced from already-exposed `NativeCompletionResult` typings in `llama.rn` — pure JS/TS consumption, no bridge edit, no native rebuild required. Per AGENTS.md the gate is exactly that file list. The on-device baseline-vs-feature scenario (`prompt_ms` / RSS / `tokensCached/promptTokenLength`) is still required as the I6 acceptance gate; it has been folded into Step 1.4's I6 acceptance gate referenced from WHAT §4c-supplement (see "On-device I6 acceptance gate" section below). It is a perf/canary device baseline, not a native build gate.
- **Visual Confirmation**: NO — instrumentation, serialization, grammar mode, runtime fallback. No new user-visible chrome (intent Q3 marker is out of scope per WHAT §8 D-out-of-scope).
- **Intent Brief**: `./workflows/stories/TASK-20260509-1733/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260509-1733/what.md`
- **Architecture doc being updated**: `./context/architecture/chat-flow.md` (absorb WHAT §1, §1b, §1c, §1d, §1e, §2, §3, §4, §5, §6, §8, §9 deltas in this PR; see Architecture Doc Absorption row in Progress Tracking)
- **Status**: draft

---

## Decision log absorbed from WHAT review (planner-side)

These were minor stylistic notes the architect-critic flagged for the planner; resolutions:

- **Path normalization**: WHAT references `services/agent/AgentRunner.ts`. This `how.md` uses the full path `src/services/agent/AgentRunner.ts` (and `src/utils/...`, `src/api/...`) everywhere.
- **`prompt_ms` rename**: option (a) — rename in place. `prompt_ms` exists in exactly one production call-site (`src/utils/completionTypes.ts:89`) and is otherwise untouched in production code today (verified by `grep -rn "prompt_ms" worktrees/TASK-20260509-1733/src/`). The diagnostic recorder will read `result.timings.promptMs`. Rename happens at the engine boundary in `LocalCompletionEngine.completion` together with the snake→camel mapping for `tokensCached` and `promptTokenLength` (one consistent migration, not two). The native shape (`NativeCompletionResultTimings.prompt_ms`) is unaffected — that is upstream. Test files reading `CompletionResult.timings.prompt_ms` (where `result: CompletionResult`) will be discovered by the typecheck sweep (the dropped index signature converts each missed reader into a compile error); test files reading `NativeCompletionResult.timings.prompt_ms` stay snake_case and are not touched.
- **WHAT §10 closing list says "I1–I7"** but defines I1–I8. This `how.md` references all 8 invariants where applicable; I8 is enforced by `lazyGrammar.test.ts` (Step 3.2).
- **WHAT §1d synthetic minimal-message body** uses `[{role:'system',content:''},{role:'user',content:''}]`. Some Jinja templates reject empty-content messages. **Decision**: fall back to a single-space content (`' '`) — pure-data choice, no extra round-trip needed, behavior verified inline as part of Step 3.1 (`probeOnce` unit test asserts the synthetic body renders without throw on the qwen25/llama3 templates already in the test fixture set). If a template still rejects (rare, e.g. some MoE chat templates), `probeOnce` catches the throw, sets `supportsTriggers=false` (eager fallback), and `console.warn`s once.
- **camelCase additions among existing snake_case in `CompletionResult`**: deliberate, per WHAT §1c D-naming-snake-on-wire-camel-in-app. One-line migration note added in code comment on `completionTypes.ts`: "*new fields are camelCase per WHAT §1c; existing snake_case fields stay snake_case until a separate cleanup story renames them*". Wire boundary remains snake_case; app-side gradually migrates in a follow-up.
- **Surfacing tokenized prompt length from native — chosen path**: option (c) — **already-exposed path**. Verified in `repos/pocketpal-ai/node_modules/llama.rn/lib/typescript/types.d.ts:329-378`:
  - `NativeCompletionResult.tokens_cached: number` — already on the type, just truncated by today's `LocalCompletionEngine.completion` mapping (`src/api/completionEngines.ts:36-51`).
  - `NativeCompletionResultTimings.cache_n: number` — prompt tokens served from cache.
  - `NativeCompletionResultTimings.prompt_n: number` — prompt tokens processed (i.e. not from cache) this turn.
  - **Derived / mapped fields**:
    - `tokensCached := result.tokens_cached` (direct).
    - `promptTokenLength := result.timings.cache_n + result.timings.prompt_n` (**derived**, *not* a direct rename — `cache_n + prompt_n` = total prompt tokens; the runtime does not expose a single `prompt_token_count` field. WHAT §1c's rename-table row `prompt_token_count → promptTokenLength` is wording shorthand; the actual derivation is `cache_n + prompt_n → promptTokenLength`. The architecture-doc absorption step amends the renamed row in `chat-flow.md` accordingly — see Architecture doc absorption section).
    - **No `nPast`** on `CompletionResult`. Earlier draft computed `nPast = cache_n + prompt_n`, but that is positionally identical to `promptTokenLength` and adds no signal. WHAT §1b permits `nPast: number | null` on `TurnDiagnostic` — the diagnostic recorder keeps the slot but populates it as `null` (the runtime doesn't expose a separate `n_past`). The architect's invariant table absorbs the `null` semantics. The `§1c` rename-table row `n_past → nPast`, the Affected-Files row for `completionTypes.ts`, the engine boundary mapping in `completionEngines.ts`, and the diagnostic recorder no longer compute or read `nPast` on `CompletionResult`; only the `TurnDiagnostic.nPast` slot remains, fixed to `null`, for forward-compatibility.
  - **No `llama.rn` upstream PR. No `patch-package`. No new bridge call.** D-prompt-token-length-piggyback (WHAT §1c) holds with one fewer hop than originally drafted.

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1.0 — Extend `CompletionResult` + engine boundary mapping | pending | A | new camelCase fields; `prompt_ms`→`promptMs` rename |
| Step 1.1 — `TurnDiagnostic` type + recorder module + LRU | pending | A | dev-only, tree-shaken in prod (I6) |
| Step 1.2 — Wire recorder into `useChatSession` event loop | pending | A | three callbacks adjacent to existing `for await` |
| Step 1.3 — Diagnostic prompt-render via `getFormattedChat` (read-only) | pending | A | I4 — never alter runtime bytes |
| Step 1.4 — Tests: `turnDiagnostics.test.ts` (recorder unit) + dev-mode tree-shake assertion | pending | A |  |
| Step 2.1 — Extract `toWireArguments` helper (sorted keys) | pending | B | single stringification site (I1, S5) |
| Step 2.2 — Use `toWireArguments` in both `chat.ts:toWireToolCall` and `AgentRunner.ts:buildNextTurnMessages` | pending | B | dedupe |
| Step 2.3 — Promote I7 (`finishedResult.content` not `text`) — already on hot path; add regression test | pending | B | S6 |
| Step 2.4 — Tests: `chat.byteStability.test.ts` covers S1–S6 | pending | B | 6-scenario byte-stable suite |
| Step 3.1 — `probeOnce(modelHash, toolsetHash)` capability probe in `triggerMarkers.ts` | pending | C | D-capability-probe-once |
| Step 3.2 — LAZY-default + EAGER fallback selector in runner; `eagerGrammarCache.getOrCompute` | pending | C | I2, §1b.iii |
| Step 3.3 — Tests: `lazyGrammar.test.ts` — I8 stability + EAGER fallback | pending | C |  |
| Step 4.0 — Decision gate: split-out check | pending | D-or-followup | criterion below; record outcome |
| Step 4.1 — `enable_two_stage_fallback` flag + completionSettings v5 migration | pending | D | WHAT §1e |
| Step 4.2 — TWO_STAGE selector with hysteresis (3-turn window, 0.80/0.85) | pending | D | WHAT §3 |
| Step 4.3 — Stage-A unconstrained run + hard-stop on marker (`engine.stopCompletion()`) | pending | D | D-stage-a-hard-stop |
| Step 4.4 — Stage-B args-only constrained run + forced-opener prefix continuity | pending | D | D-two-stage-prefix-continuity |
| Step 4.5 — Tests: `twoStageFallback.test.ts` covers S8 + I3 + prefix-equality slice | pending | D |  |
| Architecture doc absorbed | pending | A–D | merge WHAT §1/§1b/§1c/§1d/§1e/§2/§3/§4/§5/§6/§8/§9 deltas into `context/architecture/chat-flow.md`; final commit of the PR |
| Cleanup reminders applied | pending | A–D | recorder dev-only guard verified; flag retire-note added to chat-flow.md §10 |
| On-device I6 acceptance gate (canonical S7 baseline-vs-feature scenario, qwen25 1.5B Android mid-tier) | pending | tail of D | MANDATORY before "ready" — perf/canary device baseline; not a native build gate (Native Changes=NO) |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/utils/completionTypes.ts` | edit — add `tokensCached`, `promptTokenLength` (no `nPast` on `CompletionResult`); rename `timings.prompt_ms` → `timings.promptMs` (TS-only); add code comment about camelCase migration | §1b.iii, §1c, I5 |
| `src/api/completionEngines.ts` | edit — `LocalCompletionEngine.completion` maps `tokens_cached → tokensCached` and `timings.cache_n + timings.prompt_n → promptTokenLength` (derived sum) and `timings.prompt_ms → timings.promptMs`; `OpenAICompletionEngine` leaves new fields undefined (documented) | §1c, §5, §9f |
| `src/utils/chat.ts` | edit — extract `toWireArguments(args)` helper used by `toWireToolCall` (line 48-62); orphan-pair synthesis already present (line 99-113) — verify, no behaviour change; `removeThinkingParts` (398-423) — read-only, document idempotency | §4a.1–6, §6 S1–S6, §9c |
| `src/services/agent/AgentRunner.ts` | edit — `buildNextTurnMessages` (196-238) uses `toWireArguments`; runner-level grammar selector (LAZY/EAGER/TWO_STAGE) wraps the existing `engine.completion` call; I7 stays (no new code; regression test added in Step 2.3) | §1b.iv, §3, §4a.4, §8, I2/I3/I7 |
| `src/services/agent/triggerMarkers.ts` | edit — add `probeOnce(modelHash, toolsetHash, getFormattedChat)` returning `{supportsTriggers, triggerMarkers}` keyed on the (model, toolset) pair; existing `getMarkers` becomes a thin wrapper that calls `probeOnce` with the live messages replaced by the synthetic minimal body | §1d, §5, I8 |
| `src/utils/turnDiagnostics.ts` (NEW) | add — `TurnDiagnostic` type, `TurnDiagnosticRecorder` (3 methods), FNV-1a-64 hash, `Map<promptHash, number>` LRU bounded to 32 entries / context, dev-mode tree-shaken via `if (__DEV__)` guard at every public entry point | §1b, §4b, I4/I6 |
| `src/utils/eagerGrammar.ts` (NEW) | add — `eagerGrammarCache` (single `getOrCompute(modelHash, toolsetHash, tools)` writer; reset on context swap); seeds with permissive `JSON_GBNF` (mirrors `TestCompletionScreen.tsx:511`) | §1b.iii, §5 |
| `src/utils/twoStageFallback.ts` (NEW) | add — selector predicate (3-turn hysteresis), forced-opener table (ChatML `<tool_call>`, Llama3 `<\|start_header_id\|>function`), Stage-A→Stage-B orchestration helpers; runner imports them | §1b.iv, §3, §1e, D-two-stage-prefix-continuity |
| `src/utils/completionSettingsVersions.ts` | edit — v5 migration adds `enable_two_stage_fallback: false` default | §1e |
| `src/hooks/useChatSession.ts` | edit — instantiate `TurnDiagnosticRecorder` via `useRef` (alongside `triggerCacheRef`); pass three callbacks to runner via a new `diagnostics?` field on `AgentRunOptions`; pass `enable_two_stage_fallback` flag through to runner; pass `eagerGrammarCache` and `templateGrammarSupport` snapshot | §2, §3 |
| `src/services/agent/AgentRunner.types.ts` | edit — extend `AgentRunOptions` with optional `diagnostics?: TurnDiagnosticRecorder`, `templateGrammarSupport?`, `eagerGrammarCache?`, `twoStageFallbackEnabled?: boolean` | §1b.iv, §1d |
| `src/utils/__tests__/chat.byteStability.test.ts` (NEW) | add — covers S1, S2, S3, S4, S5, S6 | §6 S1–S6, I1, I7 |
| `src/utils/__tests__/turnDiagnostics.test.ts` (NEW) | add — recorder unit (hash determinism, LRU bound, dev-only guard, no-mutation invariant I4, recorder-failure degradation §9g) | §1b, §4b, I4/I6 |
| `src/services/agent/__tests__/lazyGrammar.test.ts` (NEW) | add — I8 stability (same `(modelHash, toolsetHash)`, two different message bodies → equal `supportsTriggers`); EAGER fallback when `triggerMarkers===[]` (§9e) | §1d, §1b.iii, I2/I8 |
| `src/services/agent/__tests__/twoStageFallback.test.ts` (NEW) | add — S8: stage A hard-stop, stage B args-only, prefix-equality slice; selector hysteresis on 3-turn window; flag-off no-op; missing-opener falls through (§1b.iv "if no opener known"); §9h stage-A no-marker behaviour | §1b.iv, §3, §6 S8, I3 |
| `src/services/agent/__tests__/AgentRunner.test.ts` | edit — add a regression case asserting `messages[N].content === finishedResult.content` (NOT `.text`) on a tool-using turn | I7, §6 S6 |
| `src/api/__tests__/completionEngines.test.ts` | edit — assert mapping: native `tokens_cached:5, timings.cache_n:50, timings.prompt_n:7, timings.prompt_ms:120` → app `{tokensCached:5, promptTokenLength:57, timings.promptMs:120}` (no `nPast` on `CompletionResult` — runtime does not expose a separate `n_past`) | §1c |
| `__mocks__/external/llama.rn.ts` | edit — extend the mock `NativeCompletionResult` returned by `completion(...)` to include `tokens_cached`, `timings.cache_n`, `timings.prompt_n` so engine-mapping tests have data; also extend the mock streaming-callback path used by `twoStageFallback.test.ts` (Step 4.5 marker-mid-stream case) so the test can feed a stream containing the trigger marker mid-way | §1c, test fixture, §6 S8 |
| Test files reading `CompletionResult.timings.promptMs` (sweep on typecheck failure) | edit — discover via the typecheck sweep enabled by dropping the `[key: string]: number \| undefined` index signature; renames any `result.timings.prompt_ms` → `result.timings.promptMs` where `result: CompletionResult`. Test files reading `NativeCompletionResult.timings.prompt_ms` are NOT touched (snake_case stays at the wire boundary) | §1c |
| `context/architecture/chat-flow.md` | edit — absorb WHAT deltas (one commit at the end of D, before Native verification commit, as per AGENTS.md "doc updates land in the same PR") | WHAT §10 closing |

> **Out of scope (read-only)**: `repos/pocketpal-ai/`, `worktrees/PR-709/`, the `llama.rn` package itself. The TS surface change for `NativeCompletionResult` is purely consumed (no edit to `node_modules/llama.rn`).

---

## Implementation Steps

Each step: one logical change, one commit (or commit-able chunk). Grouped under commits A–D (commit ordering matters — see Phasing in this story's intent — Step 1 measurement layer must land first; Step 2 byte-stable serialization is the core fix that everything else assumes; Step 3 lazy grammar is self-contained on top of the capability probe; Step 4 is invasive, flag-gated, off by default, and may split into a follow-up PR).

### Commit A — Step 1: Per-turn KV diagnostics (measurement layer)

#### Step 1.0: Extend `CompletionResult` + engine boundary mapping

**Implements**: WHAT §1b.iii, §1c (D-naming-snake-on-wire-camel-in-app, D-prompt-token-length-piggyback), I5.

**Files**:

- `src/utils/completionTypes.ts` — add `tokensCached?: number; promptTokenLength?: number` to `CompletionResult` (no `nPast` — see Decision-log; runtime exposes no separate `n_past` field, and `cache_n + prompt_n` is identical to `promptTokenLength`). Rename `timings.prompt_ms?` → `timings.promptMs?` and remove the loose `[key: string]: number | undefined` index signature so the rename is a real type error if missed elsewhere — this is the **discovery mechanism** for missed test-file readers (the typecheck sweep below). Add code comment: *"camelCase additions are deliberate per WHAT §1c — full snake→camel migration of pre-existing fields is a separate cleanup story"*.
- `src/api/completionEngines.ts` — in `LocalCompletionEngine.completion`'s return shape: map `result.tokens_cached → tokensCached`; `result.timings.cache_n + result.timings.prompt_n → promptTokenLength` (derived sum, not a direct rename — code comment links to WHAT §1c); rewrite `timings` into a fresh object that emits `promptMs` from `result.timings.prompt_ms` and forwards the other already-camelCase timings fields (`predicted_per_second` → `predictedPerSecond`, etc. — but **only `prompt_ms` is in WHAT's rename table; do NOT rename other timings fields in this PR**; keep them snake_case to stay scoped). For `OpenAICompletionEngine.completion`, leave the two new fields undefined (existing return shape unchanged) — add inline comment "*WHAT §9f: silent-disable; recorder treats undefined as 'unavailable'*".

**Approach**: 1 file edit each. The mapping is one expression per field; ~12 LOC.

**Verification**:

- `yarn lint` passes.
- `yarn typecheck` passes. The `prompt_ms` rename + dropped index signature is the **discovery mechanism** for missed test-file readers: any test that reads `result.timings.prompt_ms` where `result: CompletionResult` becomes a compile error and is renamed in the same commit. Tests that read `nativeResult.timings.prompt_ms` where the value is `NativeCompletionResult` stay snake_case (unaffected). Current grep shows only the type def site as a production reader.
- `yarn test --findRelatedTests src/api/completionEngines.ts` passes; the updated `completionEngines.test.ts` asserts the mapping (Step 1.4 / `Affected Files`).

#### Step 1.1: `TurnDiagnostic` type + recorder module + LRU

**Implements**: WHAT §1b, §4b, §5, I4, I6.

**Files**:

- `src/utils/turnDiagnostics.ts` (NEW). Exports:
  - `interface TurnDiagnostic { ... }` — exactly as WHAT §1b lists. The `nPast: number | null` slot is retained for forward-compatibility but the recorder always populates it as `null` (the runtime exposes no separate `n_past` field; `cache_n + prompt_n` is captured as `promptTokenLength`). Code comment: *"`nPast === null` here means 'unavailable from the runtime' — do not derive from `cache_n + prompt_n`, which is `promptTokenLength`."*
  - `interface TurnDiagnosticRecorder { onStepStarted(...), onStepFinished(...), onRunFinished(...) }`.
  - `createTurnDiagnosticRecorder(): TurnDiagnosticRecorder` — factory pattern (matches `triggerMarkers.ts`); per-context `Map<contextId, RingBuffer<TurnDiagnostic>>` ring of 32; per-context `Map<promptHash, number>` LRU of 32 for `lcpTokensVsPrev`.
  - Internal: FNV-1a-64 hex hash function (`promptHash` per WHAT §1b note 2), pure JS, no deps.
  - Every public method body starts with `if (!__DEV__) return;` — operationalizes I6 tree-shake (Metro/Babel's `transform-inline-environment-variables` + `babel-plugin-transform-remove-console`-style dead-code elimination drop the whole body in release builds).
  - Each method wrapped in a try/catch that `console.warn`s once per failure class and degrades to no-op (I4 + §9g).

**Approach**: ~150 LOC self-contained module. Zero React/MobX imports. No store imports. Imports `__DEV__` from React Native global.

**Verification**:

- `yarn lint`, `yarn typecheck`.
- `yarn test --findRelatedTests src/utils/turnDiagnostics.ts` covers Step 1.4.

#### Step 1.2: Wire recorder into `useChatSession` event loop

**Implements**: WHAT §2 (diagnostic emission points), §5 single-writer for `TurnDiagnostic` ring entries.

**Files**:

- `src/services/agent/AgentRunner.types.ts` — extend `AgentRunOptions` with optional fields: `diagnostics?: TurnDiagnosticRecorder; templateGrammarSupport?: TemplateGrammarSupport; eagerGrammarCache?: EagerGrammarCache; twoStageFallbackEnabled?: boolean`. None of them are required — runner falls back to LAZY-only behaviour if absent.
- `src/services/agent/AgentRunner.ts` — at `step_started` (line 299), `step_finished` (line 416), and `run_finished` (line 484) yield-sites, emit a corresponding recorder call when `options.diagnostics` is provided. Each call is wrapped in try/catch (recorder may throw → warn-and-continue per §9g). Recorder reads only event payload + `lastResult`; no store state, no message mutation (I4).
- `src/hooks/useChatSession.ts` — instantiate `recorderRef = useRef(createTurnDiagnosticRecorder())`; pass `diagnostics: recorderRef.current` into `runAgent({...})` at line 515.

**Approach**: pass-through; runner gains 3 try/catch blocks of ~5 LOC each; hook gains 1 useRef and 1 option field. Production behaviour unchanged when `diagnostics` is absent (defensive `if (options.diagnostics)` checks gate every site).

**Verification**:

- `yarn lint`, `yarn typecheck`.
- Existing `AgentRunner.test.ts` still passes (no diagnostics injected → no behaviour change).
- New unit test in `turnDiagnostics.test.ts` verifies the recorder receives one call per step boundary when injected.

#### Step 1.3: Diagnostic prompt-render via `getFormattedChat`

**Implements**: WHAT §1b.i (P-B chosen), I4.

**Files**:

- `src/utils/turnDiagnostics.ts` — recorder's `onStepStarted` accepts a `getFormattedChat: () => Promise<JinjaFormattedChatResult>` closure that the hook supplies. The recorder calls it once per turn, hashes `result.prompt`, and computes `promptByteLength = result.prompt.length`. Failure → `null` for both fields, `console.warn` once.
- `src/hooks/useChatSession.ts` — at runner-instantiation site, expose a per-turn closure: the hook already calls `getFormattedChat` for trigger markers (line 504); the recorder gets a separate closure that re-renders with the live `messages` array, NOT the synthetic minimal body. Two distinct closures, one for capability probe, one for per-turn diagnostics — exactly per WHAT §1b.i.

**Approach**: ~30 LOC; reuses existing `getFormattedChat` infrastructure.

**Verification**:

- `yarn lint`, `yarn typecheck`.
- `turnDiagnostics.test.ts` mocks `getFormattedChat` to return a known prompt and asserts `promptHash` is FNV-1a-64 deterministic.

#### Step 1.4: Tests — `turnDiagnostics.test.ts` + engine mapping test

**Implements**: WHAT §6 (cross-cutting), I4/I6 enforcement.

**Files**:

- `src/utils/__tests__/turnDiagnostics.test.ts` (NEW): hash determinism (same input → same FNV-1a-64); LRU bounded to 32 entries / context (33rd push evicts oldest); recorder no-op when `__DEV__===false` (jest sets `__DEV__=true` by default; this test temporarily flips the global); recorder methods never throw on injected failures (hash fn raises → `null` field, single `console.warn`); recorder never mutates the input event objects (deep-equal before/after).
- `src/api/__tests__/completionEngines.test.ts` — extend with the snake→camel mapping case (see Affected Files row).

**Verification**:

- `yarn test --findRelatedTests src/utils/turnDiagnostics.ts src/api/completionEngines.ts` — all pass.
- `yarn lint`, `yarn typecheck`.

**Commit-A boundary**: lint, typecheck, full `yarn test` pass. No native build required (NATIVE_CHANGES=NO; the engine boundary consumes `result.tokens_cached`/`timings.cache_n`/`timings.prompt_n` from the already-exposed `NativeCompletionResult` typings — pure TS consumption). The on-device I6 acceptance gate at the end of the PR is still mandatory because the new field surface is consumed by JS at runtime — see "On-device I6 acceptance gate" section below.

---

### Commit B — Step 2: Prompt-identity stabilization (the core fix)

#### Step 2.1: Extract `toWireArguments` helper (sorted keys)

**Implements**: WHAT §4a.1, §4a.2, §6 S5, §9d, D-canonical-arg-stringification, D-numeric-key-host-independence.

**Files**:

- `src/utils/chat.ts` — add (or co-locate near `toWireToolCall` at line 48):
  ```ts
  export function toWireArguments(args: string | Record<string, unknown> | undefined): string {
    if (typeof args === 'string') return args;
    return canonicalStringify(args ?? {});
  }
  ```
  where `canonicalStringify` recursively sorts object keys at every depth (Object.keys.sort()), preserves array element order, uses `JSON.stringify` with no indent, leaves non-ASCII unescaped, JSON-escapes internal quotes — all enforced by the S5 unit test.

**Approach**: pure helper; ~25 LOC; one place writes the canonical form (single-writer).

**Verification**:

- `yarn lint`, `yarn typecheck`.
- `yarn test --findRelatedTests src/utils/chat.ts` — S5 case in `chat.byteStability.test.ts` (Step 2.4) covers the canonical output.

#### Step 2.2: Use `toWireArguments` at both call sites

**Implements**: WHAT §4a.1, §5 single-writer rule for tool-arg stringification.

**Files**:

- `src/utils/chat.ts` — `toWireToolCall` (line 48-62) calls `toWireArguments(call.function?.arguments)` instead of inline ternary.
- `src/services/agent/AgentRunner.ts` — `buildNextTurnMessages` (line 211-214) calls `toWireArguments(tc.function.arguments)`.

**Approach**: 2 small replacements, ~6 LOC delta total.

**Verification**:

- `yarn lint`, `yarn typecheck`.
- Existing `chat.test.ts` and `AgentRunner.test.ts` pass unchanged (the new helper produces byte-identical output for previously-handled cases — the only behavioural difference is that previously-stringified `{z:1,a:2}` in insertion order now becomes `{"a":2,"z":1}`; this is *the* point — S5 verifies sorted-key output is byte-identical regardless of input key order).

#### Step 2.3: Promote I7 with regression test

**Implements**: WHAT §4a.4, I7, §6 S6.

**Files**:

- `src/services/agent/AgentRunner.ts` — no code change (line 459-465 already uses `finishedResult.content`). Add a one-line code comment promoting it from "documented behaviour" to "I7 — see chat-flow.md §4c".
- `src/services/agent/__tests__/AgentRunner.test.ts` — add a regression case: feed a step where `finishedResult = {text: '<think>...</think>...<tool_call>{"a":1}</tool_call>', content: '', reasoning_content: '...'}` and assert that `buildNextTurnMessages` emits `{role:'assistant', content:''}` (NOT the raw `text`). Test fails today if any future change swaps `.content` for `.text`.

**Approach**: ~30 LOC test; production code unchanged.

**Verification**:

- `yarn test --findRelatedTests src/services/agent/AgentRunner.ts` passes.

#### Step 2.4: Tests — `chat.byteStability.test.ts` covers S1–S6

**Implements**: WHAT §6 S1, S2, S3, S4, S5, S6, I1.

**Files**:

- `src/utils/__tests__/chat.byteStability.test.ts` (NEW). Six describe blocks, one per scenario:
  - **S1 — text only**: build `convertToChatMessages([assistantTurn with single content step])`, hash output; call again with same input; assert byte-identical. Covers the simplest case.
  - **S2 — retry of tool turn**: build the wire array for a persisted tool-using turn; replicate the call (simulating retry); assert byte-identical (modulo the user-msg id, which is exterior to `convertToChatMessages` for this group).
  - **S3 — reload**: persist a turn with `function.arguments` as a parsed object; reload (deep-clone via `JSON.parse(JSON.stringify(...))`); assert wire output bytes match the originally-persisted-as-string form (because `toWireArguments` always canonicalizes).
  - **S4 — orphan-pair**: step has `toolCalls=[A,B]` but `toolOutcomes=[A_outcome]` only; assert `stepToApiMessages` emits the assistant + A_outcome + synthesized `{role:'tool', tool_call_id:B.id, content:'aborted'}`; assert persisted state is NOT mutated (call from a deep-frozen input).
  - **S5 — tool-arg stringification**: WHAT §6 S5's exact input `{z:1, a:'héllo "world"', nested:{y:2,x:1}}` → exact output `'{"a":"héllo \\"world\\"","nested":{"x":1,"y":2},"z":1}'`; also numeric-key case `{"10":x,"2":y}` → `{"10":x,"2":y}` (S5 + §9d D-numeric-key-host-independence).
  - **S6 — reasoning + content projection**: WHAT §6 S6 input → `assistant.content = 'The answer is 42.'` (NOT `.text` — I7) + `reasoning_content` retained when present, omitted when empty; `include_thinking_in_context=false` branch removes `reasoning_content` (referenced from `removeThinkingParts` semantics in `chat.ts:398-423`).

**Approach**: ~250 LOC test file; one file, six describes. Uses fixture data inline (small enough not to need a fixtures file).

**Verification**:

- `yarn test --findRelatedTests src/utils/chat.ts src/services/agent/AgentRunner.ts` — all six scenarios pass.
- `yarn lint`, `yarn typecheck`.

**Commit-B boundary**: full `yarn test` pass; no native change; this is the load-bearing serialization fix.

---

### Commit C — Step 3: Lazy grammar mode

#### Step 3.1: `probeOnce(modelHash, toolsetHash)` capability probe

**Implements**: WHAT §1d, §5 (`templateGrammarSupportCache` single writer), I8, D-capability-probe-once.

**Files**:

- `src/services/agent/triggerMarkers.ts` — extend `TriggerMarkerCache`:
  - Add `interface TemplateGrammarSupport { supportsTriggers: boolean; triggerMarkers: string[] }`.
  - Add `probeOnce(modelHash: string, toolsetHash: string, getFormattedChat: (msgs: ChatMessage[]) => Promise<JinjaFormattedChatResult>): Promise<TemplateGrammarSupport>`. Internal: cache key `${modelHash}::${toolsetHash}`. On miss, call `getFormattedChat([{role:'system',content:' '},{role:'user',content:' '}])` (single-space content per planner decision above to dodge empty-content-rejecting Jinja templates). Extract `triggerMarkers` via existing `extractTextMarkers`. `supportsTriggers = triggerMarkers.length > 0`. Cache and return.
  - Existing `getMarkers` becomes: `const support = await probeOnce(...); return support.triggerMarkers;` — backwards-compatible.
  - On `getFormattedChat` throw: cache `{supportsTriggers:false, triggerMarkers:[]}` (eager fallback) and `console.warn` once per `(modelHash, toolsetHash)`.

**Approach**: ~50 LOC delta. Single-writer cache as before.

**Verification**:

- `yarn lint`, `yarn typecheck`.
- `triggerMarkers.test.ts` extended (or new `lazyGrammar.test.ts` — chosen path: new file for cleanliness): I8 — same `(modelHash, toolsetHash)` probed with two different message bodies → equal `supportsTriggers`. Covered in Step 3.3.

#### Step 3.2: LAZY-default + EAGER fallback selector + `eagerGrammarCache`

**Implements**: WHAT §1b.ii, §1b.iii, §3 (selector when `flag=false`), §5, I2, §9e.

**Files**:

- `src/utils/eagerGrammar.ts` (NEW) — `EagerGrammarCache` factory with `getOrCompute(modelHash, toolsetHash, tools)` single writer; reset on context swap (called from `useChatSession` on model swap). Returns the permissive `JSON_GBNF` constant from `TestCompletionScreen.tsx:511` (extract to shared module, do NOT duplicate). For now (per WHAT §1b.iii (?) note), tools list does NOT yet generate per-tool GBNF — permissive whole-turn JSON is the seed; tightening is deferred.
- `src/services/agent/AgentRunner.ts` — wrap the existing `engine.completion(turnParams, ...)` call (line 326-359). Compute `mode: 'LAZY' | 'EAGER' | 'TWO_STAGE'` once per turn from `(templateGrammarSupport, twoStageFallbackEnabled, recentDiagnostics)`. For Step 3, only LAZY/EAGER paths are wired; TWO_STAGE branch falls back to LAZY/EAGER (Step 4 fills it in). EAGER injects `grammar: eagerGrammarCache.getOrCompute(...)` into `turnParams`. LAZY leaves `turnParams` unchanged (today's behaviour).
- `src/hooks/useChatSession.ts` — pass `templateGrammarSupport` snapshot, `eagerGrammarCache`, and (for Step 4 prep) `twoStageFallbackEnabled: cleanCompletionParams.enable_two_stage_fallback ?? false` to `runAgent({...})`.

**Approach**: ~80 LOC across three files. The selector is a pure function: given inputs, return mode. No store reads.

**Verification**:

- `yarn lint`, `yarn typecheck`.
- New `lazyGrammar.test.ts` (Step 3.3) covers selector branches.

#### Step 3.3: Tests — `lazyGrammar.test.ts`

**Implements**: WHAT §1d, §1b.iii, I2, I8, §9e.

**Files**:

- `src/services/agent/__tests__/lazyGrammar.test.ts` (NEW). Cases:
  - **I8 stability**: probe `(model_X, toolset_Y)` with `messages=[]` → mock `getFormattedChat` returns `{prompt:'...', grammar_triggers:[{value:'<tool_call>'}]}`; probe again with messages of ~2k tokens → mock returns the *same* `grammar_triggers` (because, in this story, the cache holds). Assert `supportsTriggers===true` from both probes; second probe MUST NOT call `getFormattedChat` again (the cache short-circuits).
  - **EAGER fallback when triggers empty**: probe returns `grammar_triggers:[]` → `supportsTriggers===false` → runner injects `grammar: <JSON_GBNF>` from `eagerGrammarCache`.
  - **Capability-probe synthetic body**: probe is called with `[{role:'system',content:' '},{role:'user',content:' '}]` — assert exact body (not the live messages array).
  - **`eagerGrammarCache` single-writer**: two concurrent `getOrCompute` calls for the same key share a single computation (in-flight de-dup).
  - **§9e gracefully**: when `getFormattedChat` throws, fallback to `{supportsTriggers:false, triggerMarkers:[]}`; `console.warn` called once.

**Verification**:

- `yarn test --findRelatedTests src/services/agent/triggerMarkers.ts src/utils/eagerGrammar.ts` — all pass.
- `yarn lint`, `yarn typecheck`.

**Commit-C boundary**: full `yarn test` pass. No native change.

---

### Commit D — Step 4: Two-stage fallback (flag-gated, off-by-default)

> **Step 4.0 — Decision gate (split-out check)**: per intent brief, Step 4 must NOT block PR #709 merging. The **default is split-out** — Step 4 ships as a follow-up PR (the safer path per intent brief). This PR ships commits A–C plus the architecture-doc absorption plus the `enable_two_stage_fallback` flag *defined* in the v5 migration (so the persistence migration path is consistent and forward-compatible) and `APP_ONLY_KEYS` (so the flag is stripped from API params), but the runner branch is unimplemented — when the flag is true, runner returns LAZY/EAGER unchanged.
>
> **Opt-in criterion to land Step 4 in this PR (must be evaluated *before* starting commit-D implementation; all three must hold)**:
>
> 1. **PR #709 is not in the human-review queue at the start of commit-D work.** Concretely: `gh pr view 709 --json reviewRequests,reviewDecision` shows no outstanding review requests AND `reviewDecision != "REVIEW_REQUESTED"`. (Pre-checkable: yes/no observation against PR state.)
> 2. **No commit A–C verification has failed or required >1 day of rework.** Concretely: every Verification block in Steps 1.0–3.3 (lint / typecheck / unit / `chat.byteStability.test.ts` / `lazyGrammar.test.ts`) passed on first or second attempt; if any required a third-pass fix or external clarification, this criterion fails. (Pre-checkable from the implementer's commit/test log.)
> 3. **The planner-given LOC budget for commits A–C has not been exceeded by >50%.** The budgeted total per the per-step Approach lines is ~12 + ~150 + ~30 + ~250 (test) + ~25 + ~6 + ~30 + ~250 (test) + ~50 + ~80 + ~250 (test) ≈ **1133 LOC** across commits A–C (production + test). 50% margin = 1700 LOC. Concretely: `git diff pr-709..HEAD -- src/ __mocks__/ | wc -l` ≤ 1700 at the start of commit-D. (Pre-checkable from the diff.)
>
> If **all three opt-in conditions** hold → land Step 4 in this PR (commit D). Otherwise → split-out (the default). The implementer MUST record the outcome (which criterion failed, with the observation) in the PR description and the follow-up task brief — this is the implementer's evidence, not a re-decision. The architect has already approved the split-out path; this gate exists only to record evidence, not to add discretion.

#### Step 4.1: Flag + completionSettings v5 migration

**Implements**: WHAT §1e.

**Files**:

- `src/utils/completionSettingsVersions.ts` — add a `< 5` block that sets `enable_two_stage_fallback = false`. Bump default version constant.
- `src/utils/completionTypes.ts` — extend `AppOnlyCompletionParams` with `enable_two_stage_fallback?: boolean`; add to `APP_ONLY_KEYS` (so it's stripped from API params before sending to llama.rn).

**Verification**: `yarn test --findRelatedTests src/utils/completionSettingsVersions.ts` passes; new test asserts default-false on fresh install and migrate.

#### Step 4.2: TWO_STAGE selector with hysteresis

**Implements**: WHAT §3.

**Files**:

- `src/utils/twoStageFallback.ts` (NEW): pure selector function `pickMode(prevMode, recentDiagnostics, supportsTriggers, flag): 'LAZY'|'EAGER'|'TWO_STAGE'` implementing §3's window-of-3, 0.80/0.85 hysteresis, append-only-turn detection, `canonicalReuseRatio = tokensCached/promptTokenLength ?? lcpRatio`. Append-only detection compares current turn's messages to prior turn's by token-prefix (delegated to recorder via diagnostic state).
- `src/services/agent/AgentRunner.ts` — selector consumed at the point Step 3.2 prepared. Recorder injects `recentDiagnostics` into the runner via the existing `diagnostics` option (extend recorder with `getRecentDiagnostics(messageId)` getter).

**Verification**: `twoStageFallback.test.ts` covers hysteresis edges (0.79, 0.81, 0.85, 0.86), edit-or-delete resets the window (per §3 "edits/deletes/retries reset the window").

#### Step 4.3: Stage-A unconstrained run + hard-stop on marker

**Implements**: WHAT §1b.iv stage A, D-stage-a-hard-stop.

**Files**:

- `src/services/agent/AgentRunner.ts` — when `mode === 'TWO_STAGE'` AND a tool-call intent is expected, call `engine.completion` first with `{messages, jinja:true, /* no tools, no grammar */}`; trigger markers still scanned in-stream (existing path); on first marker seen, call `engine.stopCompletion()`. Then run the existing post-completion path that produces `finishedResult.content` from the partial accumulated text (the same `removeThinkingParts` / parsed-preamble normalization that I7 pins) and store it.

**Verification**: `twoStageFallback.test.ts` Stage-A case uses the mock `llama.rn` to feed a stream containing the trigger marker mid-way; assert `engine.stopCompletion` called exactly once; assert `finishedResult.content` is the cleaned preamble.

#### Step 4.4: Stage-B args-only constrained + forced-opener prefix continuity

**Implements**: WHAT §1b.iv stage B, D-two-stage-prefix-continuity, §6 S8 (c).

**Files**:

- `src/utils/twoStageFallback.ts` — forced-opener table:
  ```ts
  const FORCED_OPENERS: Record<TemplateFamily, string> = {
    chatml: '<tool_call>',
    llama3: '<|start_header_id|>function',
  };
  ```
  with a small `detectTemplateFamily(modelHash, getFormattedChat)` helper (heuristic on the rendered prompt; if no family detected → return `null` and TWO_STAGE falls through to LAZY/EAGER for that turn — per WHAT §1b.iv).
- `src/services/agent/AgentRunner.ts` — Stage-B prompt construction: `messages + [{role:'assistant', content: finishedResult.content}] + <forced-opener-as-prefix-only>`. Stage-B `engine.completion` params: `{tools, grammar: <args-only GBNF>}`. The **args-only GBNF constrains only the tool's `arguments` payload — i.e. the matched tool's `parameters` JSON-schema wrapped in GBNF — NOT the whole turn**, even though the shape is permissive in this story. Per-tool means: one GBNF per tool advertised; the runner picks the one matched by the trigger marker text (or the assistant's stage-A preamble that triggered Stage B). Per WHAT §1b.iii's "start permissive, tighten if Step-1 logs justify" stance, the permissive shape ships now; tightening is deferred. Crucially the GBNF source is **per-tool args**, not the whole-turn `JSON_GBNF` constant used in EAGER fallback (which constrains the entire turn body).

**Verification**: `twoStageFallback.test.ts` D-two-stage-prefix-continuity: build the next-turn prompt via `buildNextTurnMessages(state-after-stage-B)`, render via mock `getFormattedChat`, slice the first `|stage-A-prompt + finishedResult.content + opener|` bytes; assert the slice (modulo opener, sliced off before persistence) equals the corresponding stage-B prefix.

#### Step 4.5: Tests — `twoStageFallback.test.ts`

**Implements**: WHAT §6 S8, I3, §1b.iv, §9h.

**Files**:

- `src/services/agent/__tests__/twoStageFallback.test.ts` (NEW). Cases:
  - **S8 stage-A hard-stop**: marker seen → `stopCompletion` called.
  - **S8 stage-B args-only**: stage-B completion is called with `grammar` + `tools` (not stage-A's bare params).
  - **I3 positive direction — args-only constrained, not whole-turn**: when TWO_STAGE is triggered, assert that stage-B `engine.completion` params carry `tools` AND a `grammar` field whose source is the **per-tool args GBNF** (the matched tool's `parameters` JSON-schema wrapped in GBNF — assert by identity / fixture comparison against the per-tool GBNF the runner constructs), NOT the whole-turn `JSON_GBNF` constant used by EAGER. Companion negative assertion: `grammar !== JSON_GBNF` in the stage-B call.
  - **S8 (c) prefix-equality**: rebuild next-turn prompt via `buildNextTurnMessages(...)`, slice first `|stageA + finishedResult.content + opener|` bytes; assert equality with stage-B's first same-length prefix (modulo opener slicing).
  - **Selector hysteresis** (3 / 0.80 / 0.85 band): build a 3-turn diagnostic window, assert mode transitions match §3.
  - **Flag off**: with `enable_two_stage_fallback=false`, mode never selects TWO_STAGE regardless of diagnostics.
  - **Missing opener falls through**: when `detectTemplateFamily` returns `null`, runner uses LAZY/EAGER for that turn (no error).
  - **§9h stage-A no-marker**: runs to natural completion; no stage B; result treated as a normal text turn.

**Verification**: `yarn test --findRelatedTests src/services/agent/AgentRunner.ts src/utils/twoStageFallback.ts` passes.

**Commit-D boundary**: full `yarn test` pass. Architecture-doc absorption commit follows. Then the on-device I6 acceptance gate (see "On-device I6 acceptance gate" section).

---

### Architecture doc absorption (in this PR, per AGENTS.md "doc updates land in the same PR")

**Implements**: WHAT §10 closing — "On merge, the following collapse from `(P)` to `(C)`/`(D)`".

**Files**:

- `context/architecture/chat-flow.md` — apply WHAT deltas:
  - §1 — note new in-memory diagnostic record (no schema change).
  - §1b — append the new `CompletionResult` camelCase fields (§1b.iii from WHAT) with rationale comment. Note that `nPast` is **NOT** added to `CompletionResult` (runtime exposes no separate `n_past`); it stays as a `null` slot on `TurnDiagnostic` only, for forward-compatibility.
  - §1c — record `D-naming-snake-on-wire-camel-in-app` and the `prompt_ms`→`promptMs` rename as the boundary precedent. **Amend the renamed row** in `chat-flow.md` from `prompt_token_count → promptTokenLength` to `cache_n + prompt_n → promptTokenLength`, with one sentence on the derivation: *"the runtime does not expose a single `prompt_token_count` field; `promptTokenLength` is derived as the sum `timings.cache_n + timings.prompt_n` (cache-hit prompt tokens + this-turn-processed prompt tokens) at the engine boundary."* Also drop any `n_past → nPast` row if present (runtime exposes no separate `n_past`).
  - §1d, §1e — capability-probe-once and two-stage flag. **Reflect the synthetic minimal-message body's actual choice**: WHAT §1d uses `''` (empty string) but the planner chose single-space `' '` (Step 3.1, to dodge empty-content-rejecting Jinja templates). The chat-flow.md text MUST say `' '` (single space), not `''`, after merge.
  - §2 — diagnostic emission points (no event-stream changes).
  - §3 — runner-internal selector (LAZY/EAGER/TWO_STAGE) — explicitly note it does NOT touch the reducer.
  - §4 — promote `toWireArguments` byte-stable rules; promote I7 (no longer "documented", now invariant); add I8 (capability-probe stability).
  - §5 — single-writer additions (recorder, capability cache, eager grammar cache, flag).
  - §6 — add S7 (LAZY long-context append-only) and S8 (TWO_STAGE) descriptions.
  - §8 — record D-grammar-vs-prefix-layer, D-fallback-default-off, D-canonical-arg-stringification, D-numeric-key-host-independence, D-capability-probe-once, D-prompt-token-length-piggyback, D-naming-snake-on-wire-camel-in-app, D-stage-a-hard-stop, D-two-stage-prefix-continuity, D-canonical-reuse-metric.
  - §9 — orphan-pair, retry, reload, missing TalentUI (already there), engine-without-tokensCached, recorder-failure-degrades, stage-A-no-marker.
  - §10 — add cleanup reminders 1, 2, 3 from WHAT §10.

**Approach**: this is a documentation-merge commit, not a code change. It belongs at the tail of commit-D (or as the very last commit before native verification). Drift policy mandates the same PR (per AGENTS.md "Drift prevention").

**Verification**: human review; no test gate. Architect/CTO sign-off captured in PR review.

---

### Cleanup-reminders pass

**Files**: `context/architecture/chat-flow.md` §10 — append reminders from WHAT §10:

1. `TurnDiagnosticRecorder` ring + console emission is dev-mode instrumentation; remove on GOOA-19 sign-off (or promote to a dedicated store if surfaced in-app).
2. `enable_two_stage_fallback` is a temporary feature gate; retire in a follow-up once bench data justifies default-on or default-off-forever — do not let it ossify.
3. Orphan-pair literal `'aborted'` is provisional; promote to tested constant or reason enum once model-behavior data exists.

---

## Testable-Contract Coverage

WHAT §6 canonical scenarios S1–S8 plus invariants I1–I8.

| Contract item | Verified by |
| --- | --- |
| **S1 — text only** | `src/utils/__tests__/chat.byteStability.test.ts` — describe('S1') |
| **S2 — retry of tool turn** | `src/utils/__tests__/chat.byteStability.test.ts` — describe('S2') |
| **S3 — reload** | `src/utils/__tests__/chat.byteStability.test.ts` — describe('S3') |
| **S4 — orphan-pair synthesis** | `src/utils/__tests__/chat.byteStability.test.ts` — describe('S4') |
| **S5 — tool-arg stringification** | `src/utils/__tests__/chat.byteStability.test.ts` — describe('S5') (incl. §9d numeric-key) |
| **S6 — reasoning + content projection** | `src/utils/__tests__/chat.byteStability.test.ts` — describe('S6') + `src/services/agent/__tests__/AgentRunner.test.ts` regression case from Step 2.3 |
| **S7 — LAZY long-context append-only** | manual scenario — captured by the **On-device I6 acceptance gate** section below (canonical 3-turn S7 scenario); ≥80% `tokensCached/promptTokenLength` is the acceptance gate (D-canonical-reuse-metric). Recorder logs to dev console; test plan operationalizes the 5x repetition + median + per-turn-3..10 window from WHAT §4c-supplement. |
| **S8 — TWO_STAGE fallback** | `src/services/agent/__tests__/twoStageFallback.test.ts` (Step 4.5) — all sub-cases (a)/(b)/(c) |
| **I1 — byte-stable serialization** | `chat.byteStability.test.ts` (S1–S6) |
| **I2 — grammar selection independent of cache-prefix layer** | `lazyGrammar.test.ts` — assert that swapping LAZY↔EAGER produces identical `messages` array (only `grammar` field differs in `turnParams`) |
| **I3 — TWO_STAGE only when triggered, args-only constrained** | `twoStageFallback.test.ts` — negative direction: flag-off + selector-not-firing sub-cases. Positive direction: "I3 positive direction — args-only constrained, not whole-turn" sub-case asserting stage-B `engine.completion` params carry `tools` AND a `grammar` whose source is the per-tool args GBNF (matched tool's `parameters` schema wrapped in GBNF), NOT the whole-turn `JSON_GBNF`. |
| **I4 — instrumentation must never alter runtime bytes** | `turnDiagnostics.test.ts` — recorder methods deep-equal the input event before/after |
| **I5 — native bridge surfaces tokenized prompt length** | `completionEngines.test.ts` — snake→camel mapping case |
| **I6 — mobile-budget guardrail** | On-device I6 acceptance gate (S7 baseline-vs-feature `prompt_ms` + RSS + `tokensCached/promptTokenLength` ≥ 0.80, per WHAT §4c-supplement); plus `turnDiagnostics.test.ts` __DEV__-tree-shake assertion |
| **I7 — assistant follow-up uses `finishedResult.content`** | `AgentRunner.test.ts` regression case (Step 2.3) + `chat.byteStability.test.ts` describe('S6') |
| **I8 — capability-probe stability** | `lazyGrammar.test.ts` — same `(modelHash, toolsetHash)`, two different message bodies |

---

## On-device I6 acceptance gate (NATIVE_CHANGES=NO — perf/canary device baseline; MANDATORY before "ready")

This PR contains no native code changes (no edits to `package.json`, `ios/`, `android/`, `Podfile`, or `build.gradle`), so the iOS+Android Release-build gate from AGENTS.md does **not** apply. What still applies is the on-device I6 acceptance gate referenced from the WHAT §4c-supplement metric table — `prompt_ms` / RSS / `tokensCached/promptTokenLength`. This is a perf/canary device baseline, not a native build gate.

Run the **canonical 3-turn S7 scenario** (per WHAT §4c-supplement, "Baseline-capture protocol") on installed app builds (debug or release as the tester prefers — only the same build mode pre vs post matters for delta comparability):

1. Check out `pr-709` branch tip (pre-merge of this story); install + run; on a nominated Android mid-tier device with **qwen25 1.5B** loaded, run a fixed 3-turn tool-loop scenario (datetime + render_html + datetime). Repeat 5x. Capture `prompt_ms` per turn (turns 3..10 if scenario extends — for canonical 3-turn, capture turns 2..3 and report). Capture RSS via `adb shell dumpsys meminfo com.pocketpalai` after the last turn.
2. Check out `feature/TASK-20260509-1733` (this PR); install + run on the **same device + same model file + same build mode**; rerun the same scenario 5x.
3. Acceptance gate (per WHAT §4c-supplement table):
   - `prompt_ms` post ≤ 1.05 × pre baseline (median across reps, per turn).
   - RSS post ≤ pre + 10 MB.
   - `tokensCached / promptTokenLength` ≥ 0.80 on append-only turns 2 and 3.
   - Recorder-disabled production-build size delta ≤ +10 KB gz.
4. Capture results as a comment on PR #709 successor (or this PR) with the raw numbers; if any margin is exceeded, the merge is blocked pending a recorder-overhead investigation.

Note: skipping this step is a blocking review issue.

---

## Deferred Items

- **Step 4 split-out (Step 4.0 decision gate above)** — if commit-D scope exceeds the criterion, the implementation lands as a follow-up PR. The flag definition + v5 migration still ship in this PR; only the runner-branch implementation defers.
- **WHAT Q4 (forced-opener template-family seed list expansion beyond ChatML + Llama3)** — bench-driven; expand based on Step-1 logs surfacing other families. Out of scope here.
- **WHAT Q5 (window-size + threshold-band tuning, 3 / 0.80 / 0.85)** — bench-driven; revisit in the post-Step-1-data retro. Out of scope here.
- **WHAT §1b.iii GBNF tightening (per-tool args GBNF beyond permissive `JSON_GBNF`)** — open question with `(P)` "start permissive, tighten if logs justify". Out of scope; permissive shape ships.
- **WHAT §5 deferred cleanups** —
  1. Move `tools` shape into a dedicated typed module (today an `as ToolDefinition[]` cast in `useChatSession.ts:427`). Out of scope.
  2. Unify `toWireToolCall` (chat.ts) and inline tool-call stringification — *partially landed in this PR* via the shared `toWireArguments` helper (Step 2.1–2.2); the full §5 promotion to a single `toWireToolCall` site is deferred.
- **`function: {name, arguments}` string-or-object ambiguity drift** (architect-critic note from WHAT review) — `toWireArguments` resolves the wire-time ambiguity (always emits canonical string). The persisted-shape ambiguity (`AgentToolCall.function.arguments: string | Record<string, unknown>`) is NOT changed in this PR — promoting persistence to one canonical form is a separate cleanup story.
- **chat-flow.md drift items the architect-critic noted beyond the above** — flagged for a separate doc-cleanup pass; this PR's chat-flow.md update is scoped to absorbing WHAT deltas, not refactoring pre-existing drift.
- **WHAT §10 cleanup-reminder #1** (recorder removal post-sign-off) — by definition deferred; reminder is added to chat-flow.md §10 in this PR.
- **WHAT §10 cleanup-reminder #2** (flag retire) — deferred to bench-data follow-up.
- **WHAT §10 cleanup-reminder #3** (`'aborted'` literal → enum) — deferred until model-behaviour data exists.
- **Q1 bench matrix** (per-architecture run on qwen25, llama3, llama32, gemma3, mistral-7B-v0.3, zamba2, granite-1B-MoE, rwkv-7, mamba-2) — `how.md`'s job per WHAT §8(?) Q1 (P), but covered by the Native Verification's nominated-device-and-model rule. Full matrix execution is a separate test-execution task post-merge — NOT a code item.
- **Q2 raw-`llama.rn` harness** — only run if Step-1 logs show <80% reuse on PocketPal's path AND Step-2 byte-stability tests don't lift it. By construction, this PR cannot determine that gate before its own merge; defer to post-merge bench.

---

## What this plan is NOT

- not a design doc — design lives in `what.md`
- not a justification — `intent-brief.md` is where the request lives
- not exhaustive — only steps the implementer needs; if a step would just be "obey WHAT §N", reference WHAT instead of restating
- not a bench plan — Native Verification spells out the canonical scenario; the broader Q1 matrix is a deferred follow-up
- not a guarantee that Step 4 ships in this PR — Step 4.0 is the explicit split-out gate
