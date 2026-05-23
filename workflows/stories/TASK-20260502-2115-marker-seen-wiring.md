# Amendment: Wire `marker_seen` runner-side detection

**Amends**: TASK-20260502-2115 (v6 → v7)
**Date**: 2026-05-03
**Origin**: Implementer surfaced an underspecified seam during Step 7/8 — the cache module and reducer were built and tested per spec, but no field carries trigger markers into `runAgent`, so the runner has nothing to scan and `marker_seen` never fires. Reducer falls back to transitioning on `tool_call_started` instead of marker time.
**Status**: LANDED via PR #709 (squash `2f4d772`, 2026-05-23). Implementation commits on the branch: a896e64, 4ac9727, f3b750e — verified by typecheck + 2098-test jest run pre-merge.

---

## Summary

The parent story specifies `createTriggerMarkerCache()`, the `marker_seen` event, and the reducer transition `marker_seen → generating_tool_call`. It does NOT pin three things the runner needs in order to actually emit the event:

1. A field in `AgentRunOptions` carrying the resolved markers.
2. Where the markers come from (the cache uses a zero-arg `getFormattedChat: () => Promise<JinjaFormattedChatResult>` closure, which the hook constructs from `modelStore.context.getFormattedChat(messages, undefined, {tools, jinja: true})` — the runner has no access by design).
3. The streaming-bridge mechanics: where to scan, when to scan, ordering relative to `token` events, and per-step lifecycle.

The cache module and reducer mapping are correct and stay as-is. This amendment closes the runner ↔ hook seam so `marker_seen` actually fires.

**Scope**: ~30 min implementation, additive. No architecture change.
**Behavior delta**: UX state `streaming_text → generating_tool_call` happens at marker-detect time (one beat earlier) instead of at `tool_call_started` time. No correctness change in the absence of this amendment — only a one-beat UX latency.

---

## What changes in TASK-20260502-2115.md

### Edit 1 — `Target State > Agent runner` — extend canonical `AgentRunOptions`

**Target**: the inline `AgentRunOptions` block in **`Target State > Agent runner`** (parent story line ~449). This is the canonical shape — the matching `allowedTalentNames: string[]` field already lives in the implementation at `src/services/agent/AgentRunner.types.ts:83-95`.

**Action**: Add `triggerMarkers: string[]` to `AgentRunOptions` in BOTH places — the implementation (`src/services/agent/AgentRunner.types.ts`, after `talentLookup`) and the parent story's canonical block. In the implementation file the change is purely additive (one field). In the parent story doc the change is reconciliation: replace the block wholesale with the Resulting shape below, which simultaneously drops the stale `buildFollowUpMessages` field. Preserve all other existing fields including `messageId: string`, `allowedTalentNames: string[]`, `maxTurns?`, `signal?`.

**Parent-doc reconciliation**: the parent's line 449 block may also still contain a stale `buildFollowUpMessages` field that the implementation has dropped (see `AgentRunner.types.ts:83-95`). If present, drop it as part of this edit — replace the parent's entire block with the Resulting shape below, which is the authoritative as-implemented shape plus the new `triggerMarkers` field.

Resulting shape:

```typescript
export interface AgentRunOptions {
  engine: CompletionEngine;
  initialParams: ApiCompletionParams;
  allowedTalentNames: string[];
  talentLookup: (name: string) => TalentEngine | undefined;
  triggerMarkers: string[];   // NEW — precomputed by the hook before each call
  messageId: string;
  maxTurns?: number;
  signal?: AbortSignal;
}
```

Add this paragraph directly under the interface:

> `triggerMarkers` is **precomputed by the hook**, not derived inside the runner. This keeps the runner free of llama.rn-context coupling — the chat-template formatter (`getFormattedChat`) lives on `modelStore.context`, not on `engine`. The hook computes the array once before each `runAgent` invocation and passes it in. Cache hits make follow-up sends in the same session effectively free.

**Also**: the parent story has a second, slightly stale inline `AgentRunOptions` block in `Step 1: Types` (parent line ~870) using `allowedTalents: TalentEngine[]`. That block is a documentation duplicate of the canonical shape and disagrees with the implementation. Update it to match the canonical shape (with `allowedTalentNames`, `messageId`, and the new `triggerMarkers`), or replace its body with `// see canonical shape in Target State > Agent runner`.

### Edit 2 — `Target State > Trigger marker cache` — clarify ownership

Replace the section's body with:

> The cache is held in the hook (`triggerCacheRef = useRef(createTriggerMarkerCache())`). **Before each `runAgent` call**, the hook resolves the marker array. The cache contract takes a zero-arg `getFormattedChat: () => Promise<JinjaFormattedChatResult>`; the hook constructs it as a closure that supplies the current messages, template (none — let llama.rn pick), and `params: {tools, jinja: true}` (the `tools`+`jinja:true` combination is what causes llama.rn to populate `grammar_triggers`):
>
> ```typescript
> const tools = (cleanCompletionParams.tools as ToolDefinition[] | undefined) ?? [];
> let triggerMarkers: string[] = [];
> try {
>   triggerMarkers = await triggerCacheRef.current.getMarkers(
>     modelStore.context!.id,
>     tools,
>     () =>
>       modelStore.context!.getFormattedChat(
>         cleanCompletionParams.messages ?? [],
>         undefined,
>         {tools: cleanCompletionParams.tools, jinja: true},
>       ) as Promise<JinjaFormattedChatResult>,
>   );
> } catch (e) {
>   console.warn('[chat] trigger marker compute failed; falling back', e);
> }
> ```
>
> The resolved `string[]` is then passed into `AgentRunOptions.triggerMarkers`. The runner never imports the cache, the modelStore, or `getFormattedChat`.
>
> **Why the closure shape matters**: llama.rn's `getFormattedChat` is multi-arg `(messages, template?, params?)`. `params: {tools, jinja: true}` is the trigger that causes the chat template to emit `grammar_triggers` in the result. A zero-arg `getFormattedChat.bind(...)` call would invoke the method with no arguments, producing either an exception or an empty `grammar_triggers` array — silently defeating marker detection. Always use the closure form above.
>
> **Graceful degradation**: if `getMarkers` rejects (template formatter throws, network engine, no `grammar_triggers` in template, etc.), the hook logs and falls back to `triggerMarkers: []`. The runner still emits `tool_call_started` correctly when the engine yields parsed tool_calls; the only loss is one beat of UX latency. Failure is non-fatal.
>
> No module-level mutable state. The `useRef` lifetime is the hook's lifetime; cache contents reset when the hook unmounts.

### Edit 3 — `Step 7: Agent runner` — pin the streaming-bridge scan

Add to Step 7's checklist (after the "Move `executeTalentCalls` and `normalizeToolCallIds`" task):

- [ ] **Per-iteration locals**: at the top of each `while (turn < maxTurns)` body — after the `step_started` event is yielded — declare two fresh locals:
  ```typescript
  let accumulatedText = '';
  let markerSeenThisStep = false;
  ```
  Their lifetime is the iteration; no explicit reset is needed because the next iteration redeclares them. This is simpler than function-scope state with manual reset.
- [ ] On every chunk with `content` (within the iteration's streaming bridge):
  1. Append `data.content` to `accumulatedText`.
  2. Enqueue the `token` event FIRST.
  3. Then, if `!markerSeenThisStep && triggerMarkers.length > 0`, scan: `const matched = triggerMarkers.find(m => accumulatedText.includes(m))`. If matched, enqueue `{type: 'marker_seen', marker: matched}` and set `markerSeenThisStep = true`.
- [ ] **Ordering invariant**: `marker_seen` is always enqueued AFTER the `token` event whose content completed the substring — never before, never instead-of. Consumer sees the token arrive normally, then transitions on `marker_seen`. Verified by Test #19.
- [ ] **At-most-once-per-step invariant**: `markerSeenThisStep` blocks any further `marker_seen` emissions in the same iteration. A multi-step run (e.g., model emits a marker in step 0, executes the tool, then emits another marker in step 1) yields TWO `marker_seen` events total — one per step — because each iteration has its own fresh `markerSeenThisStep`. Verified by Test #21.
- [ ] Per-iteration variables live in the runner's local scope. Runner does NOT import `triggerMarkers.ts` (the cache module). Runner only consumes `options.triggerMarkers`.
- [ ] **Performance note**: use built-in `String.includes`. Markers are short (typically <30 chars) and `accumulatedText` is bounded by typical assistant response length. No need for Aho-Corasick or KMP; V8's optimization is sufficient.

### Edit 4 — `Step 8: Hook integration` — pin the precompute call

Add to Step 8's checklist (before the `for await` task):

- [ ] Before each `runAgent({...})` invocation, compute the marker array using the closure shape pinned in Edit 2:

  ```typescript
  const tools = (cleanCompletionParams.tools as ToolDefinition[] | undefined) ?? [];
  let triggerMarkers: string[] = [];
  try {
    triggerMarkers = await triggerCacheRef.current.getMarkers(
      modelStore.context!.id,
      tools,
      () =>
        modelStore.context!.getFormattedChat(
          cleanCompletionParams.messages ?? [],
          undefined,
          {tools: cleanCompletionParams.tools, jinja: true},
        ) as Promise<JinjaFormattedChatResult>,
    );
  } catch (e) {
    console.warn('[chat] trigger marker compute failed; falling back', e);
  }
  ```

  Pass `triggerMarkers` into `AgentRunOptions`. Cache is keyed on `(contextId, sorted(toolNames))`; successive sends in the same session hit the cache.

- [ ] **Do NOT use `getFormattedChat.bind(...)`**. The cache contract is zero-arg, but `getFormattedChat` is multi-arg and requires `params: {tools, jinja: true}` to produce `grammar_triggers`. A bare `bind` would call the method with no arguments and silently return empty markers. Use the closure form above.

### Edit 5 — `Test Requirements > Unit Tests — AgentRunner` — append three tests

| # | Test Case | Priority |
|---|---|---|
| 19 | Marker straddles two stream chunks. Chunk 1 content: `'foo<tool_'`. Chunk 2 content: `'call>bar'`. With `triggerMarkers: ['<tool_call>']`. Asserted event sequence (in order): `token('foo<tool_')`, `token('call>bar')`, `marker_seen('<tool_call>')`. Exactly one `marker_seen` for the step. No `marker_seen` interleaved before either `token`. | MUST |
| 20 | `triggerMarkers: []` passed in options → no `marker_seen` events ever; tool flow still correct via `tool_call_started`. | MUST |
| 21 | Multi-step run: model emits the marker in step 0, the runner executes a tool, then the model emits the marker again in step 1. With `triggerMarkers: ['<tool_call>']`. Assertion: exactly TWO `marker_seen` events across the run, each AFTER the relevant `token` in its own step. Regression guard for the per-iteration reset semantics. | MUST |

Update existing Test #11 to be explicit about wiring:

> *"With `triggerMarkers: ['<tool_call>']` passed in `AgentRunOptions`: `accumulated_text` contains marker, no parsed `tool_calls` arrive → `marker_seen` exactly once."*

**Test #12 (parent story line 1149) is closed as fulfilled by Test #19**, which asserts a stricter explicit event sequence (`token('foo<tool_')`, `token('call>bar')`, `marker_seen('<tool_call>')`) — fully covering #12's intent ("preamble before marker → token events in order, marker_seen still fires once"). Do NOT implement #12 separately.

### Edit 6 — `Affected Files` — tighten two rows

| File | Action |
| --- | --- |
| `src/services/agent/AgentRunner.ts` | CREATE — owns the loop; **streaming bridge declares per-iteration `accumulatedText` / `markerSeenThisStep` at the top of each `while (turn < maxTurns)` body; consumes `triggerMarkers: string[]` from options; never imports `triggerMarkers.ts`** |
| `src/hooks/useChatSession.ts` | MODIFY — becomes thin event consumer; `applyEventToStore` mapper; `triggerCacheRef` wraps factory; **before each `runAgent` call, resolve markers via `triggerCacheRef.current.getMarkers(modelStore.context.id, tools, () => modelStore.context.getFormattedChat(messages, undefined, {tools, jinja: true}))`; fall back to `[]` on rejection** |

### Edit 7 — `Test #15` — extend module-graph guard

The parent story's Test #15 asserts `AgentRunner.ts`'s reachable module graph contains no `react`, `mobx`, `mobx-react-lite`, or store imports. Extend the deny-list to also include `triggerMarkers` (the cache module):

> *"Module graph for `AgentRunner.ts` does not contain `react`, `mobx`, `mobx-react-lite`, store imports, OR a path to `services/agent/triggerMarkers`. The runner consumes `triggerMarkers` only as a `string[]` value injected through `AgentRunOptions`."*

Rationale: locks the architectural invariant in CI rather than relying on a one-time grep. One-line test change.

---

## Acceptance Criteria (additions)

Append to `Acceptance Criteria > Runner + state`:

- [ ] `AgentRunOptions.triggerMarkers: string[]` is the runner's only source of marker data; module graph for `AgentRunner.ts` does NOT import `triggerMarkers.ts` (the cache module). Verified by extended Test #15.
- [ ] Hook resolves markers via `triggerCacheRef.current.getMarkers(modelStore.context.id, tools, getFormattedChatClosure)` before each `runAgent` call; the closure passes `params: {tools, jinja: true}` (NOT a bare `.bind(...)`); rejection logs and falls back to `[]`.
- [ ] Streaming bridge enqueues `marker_seen` AFTER the `token` event whose content completed the marker substring (verified by Test #19's explicit event-sequence assertion).
- [ ] `marker_seen` fires at most once **per step**, not once per run. A multi-step run with markers in step 0 and step 1 yields two `marker_seen` events total (verified by Test #21).

---

## Implementation Plan

| Step | Task | Est | Status | Commit |
|---|---|---|---|---|
| A1 | Add `triggerMarkers: string[]` to `AgentRunOptions` in `AgentRunner.types.ts` (after `talentLookup`, before `messageId`); preserve all other fields | 1 min | DONE | a896e64 |
| A2 | Add per-iteration locals + scan logic in `AgentRunner.ts` streaming bridge (declared at top of `while` body) | 10 min | DONE | a896e64 |
| A3 | Wire hook precompute call before `runAgent` using closure form (NOT `.bind(...)`); try/catch with fallback to `[]` | 5 min | DONE | 4ac9727 |
| A4 | Write Tests #11, #19, #20, #21; extend Test #15's deny-list with `triggerMarkers` | 12 min | DONE | f3b750e |
| A5 | Run `yarn test src/services/agent/ src/hooks/__tests__/useChatSession.test.ts` | 5 min | DONE | - |

Total: ~33 min. Implementation: ~30 min actual.

### Implementation Notes

- Parent canonical `AgentRunOptions` block reconciled in the same edit
  pass: dropped stale `buildFollowUpMessages` field and aligned with
  the as-implemented shape (`messageId: string`, `initialParams:
  ApiCompletionParams`). The Step 1 stale duplicate was replaced with
  a `// see canonical shape` reference.
- Existing AgentRunner tests #1–#10, #13–#18 were updated to pass
  `triggerMarkers: []` (the disabled case); behavior unchanged.
- All four new tests (#11, #19, #20, #21) pass on first run; no
  flakiness observed across repeat runs.
- Verification greps:
  - `grep -n "from.*triggerMarkers" src/services/agent/AgentRunner.ts`
    → zero matches (runner does NOT import the cache module).
  - `grep -n "getFormattedChat" src/hooks/useChatSession.ts` → three
    matches (one comment, one comment, one closure call) and zero
    `.bind(` matches.
- Full jest suite: 2098 passed / 2 skipped / 0 failed (was 2094
  passed before; +4 new tests, no regressions).

---

## Verification

Before calling this done:

```bash
# Tests pass
yarn test src/services/agent/

# Module graph still clean — no triggerMarkers.ts imports in runner
grep -n "from.*triggerMarkers" src/services/agent/AgentRunner.ts
# Expect: zero matches

# Sanity: hook uses the closure form, not bare bind
grep -n "getFormattedChat" src/hooks/useChatSession.ts
# Expect: at least one match calling .getFormattedChat(messages, undefined, {tools, jinja: true})
# Expect: zero matches of getFormattedChat.bind(
```

Manual smoke (in the worktree):
- Send a calculate query with a Pal that has the `calculate` talent enabled.
- Watch the UI: status indicator should flip to "preparing tool" before the tool call result lands, not at the moment of dispatch.
- Inspect the AssistantTurn after completion: `step.content` should contain the preamble, NOT any trigger marker substring.

---

## Why this lands in the same PR (not a follow-up issue)

The implementer's "deferred to follow-up" framing was reasonable given the underspecified seam — they correctly avoided improvising. With the seam now pinned in this amendment:

- Work is small (~33 min) and additive.
- Test scaffolding (#11, #12) was already enumerated in the parent story; #19, #20, #21 are routine extensions.
- Shipping with `marker_seen` orphaned creates a known one-beat UX latency that we'd have to re-enter context to fix later.
- The follow-up issue route requires re-reading the spec, re-grepping the runner, and re-running the test suite — strictly more total effort than closing it now.

---

## What does NOT change

- The `triggerMarkers.ts` cache module — already correct (zero-arg `getFormattedChat` contract is preserved; the hook supplies the closure).
- `agentStateReducer.ts` `marker_seen` handler — already correct and tested.
- The `AgentEvent` union — `marker_seen` is already a member.
- All existing fields of `AgentRunOptions` (`engine`, `initialParams`, `allowedTalentNames`, `talentLookup`, `messageId`, `maxTurns?`, `signal?`) — preserved verbatim. Only one field is added.
- All other steps (1–6, 9–10), all other ACs, all other tests, all other files.
- The branching plan, the `1c1ecec` base ref, the closure obligations.

---

## Changelog

| Date | Agent/Human | Change |
| --- | --- | --- |
| 2026-05-03 | human | Amendment drafted to close the runner ↔ hook seam for `marker_seen`. Six precise edits to the parent story; two new tests; one AC group extended. |
| 2026-05-03 | human (post critic R1) | Revision after critic blockers + concerns. Fixed `getFormattedChat` closure shape (multi-arg with `{tools, jinja: true}`, NOT `.bind(...)`); changed Edit 1 from "Replace" to "Add field" preserving `messageId`/`allowedTalentNames`; specified canonical block location (Target State, not Step 1's stale duplicate); reframed per-step locals as loop-iteration declaration; tightened Test #19 with explicit event sequence; added Test #21 for per-step reset; added Edit 7 extending Test #15's deny-list to include the cache module. |
| 2026-05-03 | human (post critic R2) | LGTM round. Applied the one optional SUGGESTION: Edit 1 now explicitly handles the parent doc's stale `buildFollowUpMessages` field, instructing the implementer to drop it as part of this edit (replace the parent's block wholesale with the Resulting shape). |
| 2026-05-03 | human (post critic R3) | Independent fresh-eyes review: LGTM with 2 non-blocking CONCERNs. Applied both fixes: (1) Edit 1 framing now explicit that the change spans both `.types.ts` (additive) and the parent story doc (wholesale replacement dropping `buildFollowUpMessages`); (2) Edit 5 explicitly closes parent Test #12 as fulfilled by stricter Test #19, no separate implementation. SUGG-1/SUGG-2 deferred (chunk-fully-contains-marker test redundant with #19; first-match-wins for overlapping markers is best-effort, not a contract). Critic verified `getFormattedChat` multi-arg requirement against `node_modules/llama.rn/lib/typescript/index.d.ts:190-202` and `types.d.ts:476-496` — closure form is necessary, not paranoia. |
