# WHAT — Context-full warning UX in chat (TASK-20260526-2259)

Contract delta on `context/architecture/chat-flow.md` for the context-full warning banner. Adds one turn-derived snapshot observable on `ChatSessionStore`, a banner-variant resolver that subsumes the existing HTML soft-cap, a session-only "increase context" override with an explicit cross-store read seam, a weak-signal remote variant, and (α + β additive amendment) a declarative `TalentEngine.recommendedContextTokens?` field surfaced via a one-shot pal-load snackbar and a heavy-talent post-fail copy swap.

Conventions: **(C)** current behaviour; **(P)** proposal; **(D)** decision; **(?)** open question — none must remain before LGTM.

---

## Drift check

Read against code on 2026-05-26.

| Area | Status | Detail |
|---|---|---|
| chat-flow.md §4d / §5 agent-state surfaces | OK (C) | Hold in `ChatView.tsx`, `useChatSession.ts`, `ChatSessionStore.ts`. |
| HTML soft-cap banner (not in chat-flow.md) | Minor drift | `htmlPreviewCount >= 4` at `ChatView.tsx:1023-1047`, shell `:1073-1079`, styles `styles.ts:85-97`, copy `en.json:1104`. This delta adds a banner component row + variant signal table to chat-flow.md. |
| chat-flow.md §5 line 415 `metadata.completionResult` writer at `run_finished` | Real local drift, repaired in this delta | No production writer exists; `useChatSession.ts:323-338` writes only `timings`, `copyable`, `multimodal`, `hitMaxTurns`. Field is read as sentinel by `PlayButton.tsx:56` only. This story adds the real writer per §1b + §5 (I7). |
| `CompletionResult` shape | OK (C) | `src/utils/completionTypes.ts:80-101`. Local maps in `LocalCompletionEngine.completion` (`completionEngines.ts:36-51`); remote (`openai.ts:436-628`) sets `stopped_limit=1` on `finish_reason==='length'`, `interrupted=true` on `'content_filter'`; remote does NOT set `context_full` or `truncated`. |
| `ModelStore.initContext(model, mmProjPath?)` | OK (C) | No context-params argument (`ModelStore.ts:1492`). Effective n_ctx resolved in `getEffectiveContextInitParams` (`ModelStore.ts:419-478`). No existing seam for per-session n_ctx override — this story adds one. |
| Hook reads of `tokens_evaluated`, `tokens_predicted`, `context_full` | Greenfield | Zero hits in `useChatSession.ts`. |

Outcome: minor + local drift, both repaired in this delta. No separate reconciliation PR required.

---

## 1. Data model

### 1a. `lastCompletionResult` snapshot observable on `ChatSessionStore` (P)

One top-level observable, parallel to `isGenerating` / `isStopping` / `toolCallTokenCount`:

```ts
ChatSessionStore.lastCompletionResult: CompletionResultSnapshot | null

type CompletionResultSnapshot = {
  tokensCached:    number  // result.tokens_cached ?? 0    (KV-prefix reused, not re-evaluated)
  tokensEvaluated: number  // result.tokens_evaluated ?? 0 (freshly evaluated prompt tokens this turn)
  tokensPredicted: number  // result.tokens_predicted ?? 0 (tokens generated this turn)
  contextFull:     boolean // §4a match on this turn OR sticky carry-over if I3 didn't clear
  finishReason:    FinishReason  // 'length' | 'stop' | 'eos' | 'content_filter' | 'unknown'
}
// null = no completed turn yet for the active session
```

`finishReason` derivation (single helper at the writer):

| Source | finishReason |
|---|---|
| `result.stopped_limit === 1` | `'length'` |
| `result.stopped_eos === true` | `'eos'` |
| `result.interrupted === true` (remote) | `'content_filter'` |
| `result.stopped_word === true` | `'stop'` |
| otherwise | `'unknown'` |

Per-active-session: on session switch, reloads from disk (see §1b, §5). Persisted on last assistant turn's `metadata.completionResult`; recovered on session entry by reading that field from the most recent assistant message.

### 1b. Persisted snapshot on `metadata.completionResult` (P)

Shape on message metadata is tightened from "raw final result from llama.rn" to:

```ts
metadata.completionResult?: {
  // existing readers (PlayButton, TTS) — preserved, additive on same key
  content?:           string
  reasoning_content?: string
  // new in this story
  tokensCached:    number
  tokensEvaluated: number
  tokensPredicted: number
  contextFull:     boolean
  finishReason:    FinishReason
}
```

Existing readers (`PlayButton.tsx:56`, `:78`) check field presence as a "streaming finished" sentinel and read `reasoning_content` — continue to work.

### 1c. `sessionContextOverrides` on `ChatSessionStore` (P)

```ts
ChatSessionStore.sessionContextOverrides: Map<sessionId, number>
```

Session-keyed n_ctx override that survives `LlamaContext` destruction within app lifetime. Not persisted — survives `releaseContext → initContext` cycles in one app run, gone after process death (D2; §7c).

### 1d. `CompletionResult` fields consumed (C, recap)

See `repos/pocketpal-ai/node_modules/llama.rn/src/types.ts:380-409` for the wire shape. Fields read by this story: `tokens_cached?`, `tokens_evaluated?`, `tokens_predicted?`, `context_full?`, `truncated?`, `stopped_limit?`, `stopped_eos?`, `stopped_word?`, `interrupted?`, `text?` / `content?`. This story is the first reader.

### 1e. Optional `recommendedContextTokens?` on `TalentEngine` (P, α + β)

```ts
TalentEngine.recommendedContextTokens?: number  // src/services/talents/types.ts
// Soft hint: minimum n_ctx under which this engine tends to overflow on first invocation.
```

Optional. `RenderHtmlEngine` declares `4096`; `DatetimeEngine` and `CalculateEngine` omit. Declarative-only, not predictive (D15). Consumed at exactly two pure read sites:

- §4i pal-load hint trigger: `palNeedsMoreRoom(sessionId) = activePal.pact.talents.some(name => talentRegistry.get(name)?.recommendedContextTokens > effectiveNCtx(sessionId))`.
- §4d heavy-talent sub-copy lookup: scan `messages[0].steps[].tool_calls[].function.name` (when `messages[0]` is `assistant_turn`); if any matched engine declares `recommendedContextTokens`, switch copy key for the `context-full` variant. Variant itself unchanged (I4 preserved).

### 1f. `palLoadHintSeen` on `ChatSessionStore` (P, α)

```ts
ChatSessionStore.palLoadHintSeen: Set<string>  // key: `${palId}:${n_ctx}`
```

In-memory, session-scoped. Records (palId, n_ctx_at_load) pairs for which §4i snackbar already fired in active session. Not persisted (process restart re-fires once). Not keyed by sessionId — the hint is "this pal at this n_ctx wants more room." Cleared on `resetActiveSession`; never trimmed otherwise (cardinality bounded by |loaded pals| × |tier table|).

---

## 2. Signals

| Signal | Type | Writer | Reader | Initial | Notes |
|---|---|---|---|---|---|
| `lastCompletionResult` | `CompletionResultSnapshot \| null` | `useChatSession` at `run_finished` + abort-catch; `setActiveSession` seeds from disk; `resetActiveSession` clears | resolver | `null` | atomic snapshot; `null` before any finished turn |
| `dismissedBannerVariants` | `Set<string>` keyed `${sessionId}:${variant}` | `ChatView` banner shell on user dismiss; cleared on `run_finished` (same writer as `lastCompletionResult`) | resolver (gate) | empty | per-draft dismiss |
| `consecutiveFullFailures` | `number` | same writer as `lastCompletionResult` | resolver (copy escalation) | `0` | resets to 0 on any non-full turn |
| `sessionContextOverrides` | `Map<sessionId, number>` | `IncreaseContextSheet` confirm action | `getEffectiveContextInitParams`, resolver (via `effectiveNCtx`) | empty | cleared on session deletion only |
| `palLoadHintSeen` | `Set<string>` keyed `${palId}:${n_ctx}` | §4i trigger (gate-before-write, one site) | §4i trigger (gate) | empty | cleared on `resetActiveSession` (α) |
| `bannerVariant` (derived) | `'context-full' \| 'context-warning' \| 'context-remote-hedged' \| 'html-soft-cap' \| 'none'` | resolver (computed) | `ChatView` shell | `'none'` | not stored; computed from `(lastCompletionResult, htmlPreviewCount, effectiveNCtx(sessionId), isRemoteSession)`. Replaces `showSoftCapWarning` (`ChatView.tsx:1047`) |

---

## 3. State machine

No new state machine. `agentUiState` (chat-flow §3) unchanged. Banner variant is a pure function of the signals above; no internal lifecycle.

Session-override CTA, when activated, performs `releaseContext → initContext` on `modelStore` (existing path; model lifecycle is `ModelStore`'s concern, not `agentUiState`'s). During the cycle existing `modelStore.loadingModel` is true; this story does NOT introduce a new state.

---

## 4. Contract

### 4a. "Full" predicate (P)

`snap.contextFull = true` when any of the following hold on the just-finished `CompletionResult`:

| # | Condition | Engine |
|---|---|---|
| 1 | `result.context_full === true` (strict) | local |
| 2 | `result.truncated === true` (strict) | local |
| 3 | Catch path wrote `metadata.truncationLikely === true` (`useChatSession.ts:642-680` — tool-args JSON parse failure, the n_ctx-exhaustion smoking gun) | local |
| 4 | `finish_reason === 'length'` (→ `stopped_limit === 1`); only authoritative full-context signal in the OpenAI wire shape (D3) | remote |

A turn that matches none of the above sets `contextFull = false` on the auto-clear path (§4b, I3) — only when it also matches the low-ratio predicate.

Heavy-talent sub-copy (β, see §4d): when this predicate fires AND the just-finished turn's `assistant_turn` invoked a tool whose talent name resolves to an engine declaring `recommendedContextTokens` (§1e), the `context-full` variant emits a heavy-talent sub-copy. The variant stays `context-full` — shell, dismissibility, CTA actions, I4 all preserved. Only the copy key changes.

### 4b. "Warning" / auto-clear predicates (P)

```ts
// resolver module-level
WARNING_THRESHOLD = 0.80   // named export (D11; threshold value pinned by planner)
AUTOCLEAR_RUNWAY  = 32     // named export, tokens (D4)

snap      = lastCompletionResult                              // null → no predicate fires
used      = snap.tokensCached + snap.tokensEvaluated
          + snap.tokensPredicted                              // total KV occupancy at end of last finished turn
nCtx      = effectiveNCtx(sessionId)
ratio     = used / nCtx

warning   = snap !== null && ratio >= WARNING_THRESHOLD && !snap.contextFull
autoClear = snap !== null && used < nCtx - AUTOCLEAR_RUNWAY   // gates clearing contextFull
```

### 4c. Banner variant precedence (P)

Resolver returns exactly ONE variant per render. Short-circuits on first match.

| Order | Variant | Match condition |
|---|---|---|
| 1 | `context-full` | `snap.contextFull === true` |
| 2 | `context-warning` | warning predicate (§4b) holds AND session is local (LlamaContext present) |
| 3 | `context-remote-hedged` | session is remote AND §4e holds AND `snap.finishReason !== 'length'` (length would already be variant 1 via §4a #4) |
| 4 | `html-soft-cap` | `htmlPreviewCount >= 4` (existing rule, preserved; `ChatView.tsx:1023-1047`) |
| 5 | `none` | — |

Context beats HTML soft-cap because context-full produces visible bugs (truncated replies, tool-call parse errors) while HTML soft-cap is preventative (D5).

### 4d. Dismiss / recovery semantics (P)

| Variant | Dismiss affordance | Behaviour |
|---|---|---|
| `context-warning` | per-draft | Keyed `(sessionId, variant)` in `dismissedBannerVariants`; cleared on next `run_finished`. |
| `html-soft-cap` | per-draft | Same set, same clear cycle. |
| `context-full` | NONE | Sticky via `snap.contextFull` + auto-clear (§4b, I3, D6). Clears only when next finished turn satisfies auto-clear AND §4a does not match. |
| `context-remote-hedged` | per-draft | Same dismiss set as warning/soft-cap. Also re-derives every render from §4e; when next remote turn lands without all four §4e conditions, variant drops naturally regardless of dismiss set. Rationale: weak signal; non-dismissibility reserved for authoritative §4a strong signals (D6). |

Escalation: when a `context-full` state is followed by another turn that also matches §4a, increment `consecutiveFullFailures`. When counter reaches **2**, copy escalates (planner picks the string; contract is the counter + threshold). Reset to 0 on any turn that does NOT match §4a (D7).

### 4e. Remote weak-signal heuristic (P)

A remote turn is hedged only when ALL of the following hold (two-of-four is NOT enough):

1. Active session uses a remote engine (`activeContext` is `OpenAICompletionEngine`).
2. `snap.finishReason !== 'length'` (otherwise variant 1 wins).
3. `snap.tokensPredicted >= 500` (response was long, not a short-answer legitimate finish).
4. Trailing character of `result.content.trimEnd()` is NOT one of `.`, `!`, `?`, `。`, `！`, `？` (terminal sentence punctuation across the 8 integrated languages — D8). "Looks like it was cut mid-sentence" cheap heuristic.

Resolver reads message text from `lastMessage.text`; the snapshot does not need to carry it (`messages[0]` is already a MobX dependency of any chat-screen render). The four punctuation marks are codified at the resolver; adding to the set is a one-line change.

### 4f. Hard invariants

| ID | Rule |
|---|---|
| I1 | `snap.contextFull === true` iff the most recent finished completion in the active session matched §4a. No other code path writes `contextFull = true`. |
| I2 | `snap.tokensCached`, `snap.tokensEvaluated`, `snap.tokensPredicted` are values from the most recent finished `CompletionResult` (success, hit-max-turns, or abort-with-partial-content) for the active session. Never written from streaming token events. Together = total KV occupancy at end of that turn. |
| I3 | (auto-clear) when a turn completes with `used < nCtx - AUTOCLEAR_RUNWAY` AND none of §4a holds, the new snapshot is written with `contextFull = false` (clearing any prior sticky `true`). All four fields written together as one atomic swap. |
| I4 | Exactly ONE banner is visible at any time. Resolver returns one variant; existing single-conditional in `ChatView.tsx` is the single render site. |
| I5 | `getEffectiveContextInitParams` consults `sessionContextOverrides.get(activeSessionId)` and prefers it over `this.contextInitParams.n_ctx` when present. Resolver consults the same Map via a shared `effectiveNCtx(sessionId)` helper. Both reads agree by construction. |
| I6 | Pressing "Increase context" while runner is active (`isGenerating === true` or `isStopping === true`) is a no-op — CTA disabled until current run finishes. Reloading `LlamaContext` mid-stream would race the abort path. |
| I7 | (persistence) writer that updates `lastCompletionResult` ALSO writes the same snapshot fields onto `message.metadata.completionResult` in the same `updateMessage` call. On `setActiveSession`, snapshot rehydrates from the most recent assistant message's `metadata.completionResult` (else `null`). |
| I8 | (α layering) §4i pal-load hint is a **snackbar**, not a banner. Not part of §4c precedence; cannot displace a banner variant. Banner shell and snackbar live on different surfaces and lifecycle edges (pal/model load vs `run_finished`). I4 unchanged. |

### 4g. Component contract

| Component | Renders | Does NOT render |
|---|---|---|
| `ChatView` banner shell (existing wrapper at `ChatView.tsx:1073-1079`) | ONE of five variants from `bannerVariant` (or nothing) | per-variant logic (lives in resolver) |
| `bannerVariantResolver` (new pure module) | computed variant name + payload (e.g. `nextTierTokens` for CTA) | no JSX, no MobX writes |
| `IncreaseContextSheet` (new) | confirm sheet, tokens-primary copy with parenthetical time hedge, advanced disclosure for raw token count | n_ctx selection logic (lives in resolver / tier helper) |

Banner shell reuses existing `softCapBanner` View + styles (D9). Variant changes inner content; shell invariant. Styles file becomes variant-aware (planner picks tokens). No new component at chat surface beyond optional CTA buttons inside the same View.

### 4h. "Increase context" CTA (P)

For variants `context-full` and `context-warning`:

- Resolver computes `nextTierTokens` from tier table `[2048, 4096, 8192, 16384, 32768]`: smallest entry strictly greater than current `effectiveNCtx(sessionId)` that passes `hasEnoughMemory(activeModel, undefined)` from `src/hooks/useMemoryCheck.ts` with a temporarily-substituted `contextInitParams.n_ctx`.
- If no tier fits: CTA hidden; banner still renders with copy that does NOT offer to increase (copy is planner's; contract is "CTA hidden, banner remains visible").
- Tapping CTA opens `IncreaseContextSheet`. Confirming:
  - `sessionContextOverrides.set(sessionId, nextTierTokens)`,
  - `modelStore.releaseContext()`,
  - `modelStore.initContext(activeModel)` — override read silently by `getEffectiveContextInitParams` via the Map (I5); call signature unchanged.
- Existing feedback (`loadingModel` UI, success snackbar, error snackbar + revert) reused; no new state.

Variants `context-remote-hedged` and `html-soft-cap` do NOT render the CTA (remote n_ctx is server-controlled; HTML soft-cap recommends "start a new chat").

### 4i. Pal-load hint (P, α)

One-time, snackbar-only hint that fires at pal/model-load boundaries when active pal declares a talent recommending more context than current `effectiveNCtx(activeSessionId)`. Reuses §4h CTA path — no new confirm sheet, no new tier-pick logic, no new memory fallback.

Trigger predicate (pure, derived):

```ts
palNeedsMoreRoom(sessionId) =
  activePal.pact.talents.some(name =>
    talentRegistry.get(name)?.recommendedContextTokens > effectiveNCtx(sessionId)
  )
```

Edge moments where predicate is evaluated:
- pal load (active pal change),
- model load (`modelStore.context` becomes available after init),
- talent-set change (active pal's `pact.talents` array mutates).

Snackbar lifecycle:
1. When predicate flips `false → true` AT one of the edges AND `palLoadHintSeen` does NOT contain `${activePal.id}:${effectiveNCtx(sessionId)}`, emit ONE snackbar.
2. Insert that key into `palLoadHintSeen` at emit time, regardless of user action — one-shot per (palId, n_ctx) per session.
3. Snackbar action label:
   - Higher tier fits (`hasEnoughMemoryWithNCtx` true for some entry > current): label = "Increase context"; tapping opens the SAME `IncreaseContextSheet` from §4h with the same confirm action.
   - No tier fits: label = "Start new chat"; reuses §4h's no-fit fallback (see §7j).

Single-fire semantics: `palLoadHintSeen` is the single suppressor. Re-entering same pal at same n_ctx in same session does NOT re-fire. Changing n_ctx via the CTA yields a new key — and a new fire opportunity only if predicate still holds (typically won't, because CTA just raised n_ctx past the recommendation). Process restart clears the Set.

No banner-stack overlap with §4a–§4h (I8): snackbar is transient/system-managed; §4c precedence untouched. §4i fires at pal/model load (before user sends a message); §4a–§4h fire at `run_finished` (after). They cannot co-occur. If a §4i snackbar is still visible when a `run_finished` banner appears, both are allowed (snackbar transient, banner persistent) — snackbar's own dismissal timer governs it.

Does NOT pollute per-turn flow: §4i fires only at pal/model load edges, never at `run_finished`. §4a / §4b / §4c paths unchanged. No talent-aware logic runs on each completed turn.

---

## 5. Single-writer rule

Additions/replacements to chat-flow.md §5. The existing line 415 (`metadata.timings`, `metadata.completionResult`) is REPLACED by two rows that reflect the new persisted shape.

| Field | Single writer | Clear-trigger |
|---|---|---|
| `metadata.timings` (C, unchanged) | `updateMessage` at `run_finished` (`useChatSession.ts`) | — |
| `metadata.completionResult` (tightened shape, §1b) | `updateMessage` at `run_finished` — new in this story; same action also writes snapshot to `ChatSessionStore.lastCompletionResult` | — |
| `lastCompletionResult` (`ChatSessionStore`) | `useChatSession` at `run_finished` + abort-catch (same action that writes `metadata.completionResult`). Also `setActiveSession` (seed from disk) and `resetActiveSession` (clear to `null`) | on `resetActiveSession` |
| `dismissedBannerVariants` (`ChatSessionStore`) | `ChatView` banner shell on user dismiss | on `run_finished` (same action as `lastCompletionResult`) |
| `consecutiveFullFailures` (`ChatSessionStore`) | same writer as `lastCompletionResult`; increment/reset per §4d | resets to 0 on any non-full turn |
| `sessionContextOverrides[sessionId]` (`ChatSessionStore`) | `IncreaseContextSheet` confirm action only | on `deleteSession`; on `bulkDeleteSessions` (per-id) |
| `pendingContextOverride` (`ChatSessionStore`, A3.1) | `IncreaseContextSheet` confirm action (no-session branch, `activeSessionId === null`) | on `createNewSession` (after copy into `sessionContextOverrides.set(newSessionId, pendingContextOverride)`); on `resetActiveSession`; on `setActiveSession` (drawer-switch leak guard); on `IncreaseContextSheet` confirm failure (no-session branch) |
| `palLoadHintSeen` (`ChatSessionStore`, α) | §4i pal-load hint trigger (one site, gate-before-write) | on `resetActiveSession` |

Cross-store read direction (new, single direction): `ModelStore.getEffectiveContextInitParams` performs ONE read of `chatSessionStore.activeSessionId` and ONE read of `chatSessionStore.sessionContextOverrides.get(activeSessionId)` to compute effective n_ctx (I5). `ChatSessionStore` does not read `ModelStore`. The resolver's `effectiveNCtx(sessionId)` helper performs the same two reads and is the single co-located helper that BOTH the resolver AND `getEffectiveContextInitParams` consult — precedence rule lives in one place. The override does NOT mutate `modelStore.contextInitParams` (D10).

`TalentEngine.recommendedContextTokens` (α + β): resolver and §4i trigger read the field via `talentRegistry.get(name)`. Active pal's `pact.talents` is already a MobX dependency through `PalStore.activePalId` → `pal.pact.talents`. No new cross-store read introduced — same source the existing tool-call dispatch already reads.

Reading is unrestricted.

Cleanup absorbed by implementer on chat-flow.md update:
- Replace `showSoftCapWarning` boolean at `ChatView.tsx:1047` with resolver call. Old computation moves into resolver as one of five branches.
- `l10n.chat.softCapWarning` becomes one of five strings under `l10n.chat.contextWarning.*` (or sibling). String itself preserved for `html-soft-cap` variant.
- chat-flow.md §5 line 415 tightened: `metadata.completionResult` now has a defined shape and a real writer (§1b).

---

## 6. Canonical scenarios

| ID | Name | Preconditions | Trigger / observation | Expected variant | Dismiss | CTA | Auto-clear |
|---|---|---|---|---|---|---|---|
| A | Fresh local chat, no turns | `nCtx=2048`, `lastCompletionResult=null`, `htmlPreviewCount=0` | render | `none` | n/a | n/a | n/a |
| B | Local, 80% usage | `nCtx=2048`, snap={cached:0, eval:1500, pred:200, full:false, fr:eos}; `used=0+1500+200=1700`, `ratio=0.83` | render | `context-warning` | visible (per-draft, clears on next `run_finished`) | visible if 4096 fits memory, else hidden | n/a |
| C | Local, `context_full=true` | `nCtx=2048`, `result.context_full=true` → snap.contextFull=true | run_finished | `context-full` | NOT rendered (sticky) | visible iff higher tier fits memory | via §4b autoClear + §4a non-match |
| D | Tool-args parse failure (smoking gun) | catch path wrote `metadata.truncationLikely=true` → snap.contextFull=true (§4a #3) | abort-catch | `context-full` | same as C | same as C | same as C |
| E | Auto-clear after low-ratio turn | prior: snap.contextFull=true (from C); next: `context_full=false`, cached+eval+pred=1000, nCtx-32=2016, 1000<2016 | run_finished | `none` (assuming ratio<0.80) | n/a | n/a | I3 atomic swap; new snap = {..., contextFull:false} |
| F | Remote length-finish | remote session; `stopped_limit=1` (mapped from `finish_reason='length'`) → snap.contextFull=true, finishReason='length' (§4a #4) | run_finished | `context-full` | NOT rendered | hidden (remote, no increase path) | n/a |
| G | Remote weak-signal | remote; `stopped_eos=true`, `tokens_predicted=850`, finishReason='eos'; `content` trimmed end="...to"; snap.contextFull=false; all four §4e conditions hold | run_finished | `context-remote-hedged` | visible (per-draft, clears on next `run_finished`); also reactively clears when next remote turn lacks all four §4e conditions | hidden | reactive (§4d) |
| H | Remote short answer | remote; `tokens_predicted=120`, content ends with "." | run_finished | `none` (§4e #3 fails) | n/a | n/a | n/a |
| I | HTML soft-cap collides with context warning | `nCtx=8192`, ratio=0.82, `htmlPreviewCount=5` | render | `context-warning` (context wins, D5); HTML soft-cap silenced; resurfaces after warning dismissed/cleared | per-draft | per §4h | n/a |
| J | CTA success | `bannerVariant=context-full`, model loaded, `isGenerating=false`; next-fit tier 4096 | tap CTA, confirm | banner re-evaluates on next render; snap.contextFull unchanged by reload (changes only on next finished turn — intended UX) | n/a | — | n/a |
| K | CTA failure | `initContext` rejects (OOM, missing file, etc.) | confirm → reject | unchanged | n/a | — | n/a; `sessionContextOverrides[sessionId]` reverted (or deleted if absent before); error snackbar (existing) |
| L | Session switch with persisted recovery | A's last assistant turn: contextFull=true on disk; B's last: contextFull=false, ratio=0.85 | `setActiveSession(B)`, then back to A | B: `context-warning`; back on A: `context-full` (sticky, recovered from disk per I7); if either has no assistant message or no metadata.completionResult, `lastCompletionResult=null`, variant=`none` until next finished turn | per-variant | per-variant | per-variant |
| M | Cold app launch | `sessionContextOverrides` empty (not persisted, D2); active session restored from disk by existing boot path; `lastCompletionResult` seeded from last assistant message's `metadata.completionResult` (I7) | app boot | session that ended at `contextFull=true` still shows banner on launch before user sends anything | per-variant | per-variant | per-variant |
| N | Pal-load hint fires on default n_ctx + render_html (α) | activePal.pact.talents includes `render_html`; `effectiveNCtx=2048`; `talentRegistry.get('render_html').recommendedContextTokens=4096`; `palLoadHintSeen` does NOT contain `${pal.id}:2048` | pal load (or model load) edge | snackbar (NOT banner; I8); action "Increase context" (4096 fits memory); `palLoadHintSeen.add(${pal.id}:2048)`; tap opens same `IncreaseContextSheet` as §4h → override → release+reinit | n/a (snackbar) | reuses §4h | n/a |
| O | Pal-load hint suppressed on second load at same n_ctx (α) | same as N; user did NOT take CTA; `palLoadHintSeen` contains `${pal.id}:2048` | next pal-load edge | snackbar NOT emitted; predicate true but gate fails | n/a | n/a | n/a |
| P | Heavy-talent post-fail copy (β) | `nCtx=4096`; last turn: `assistant_turn` with `steps[0].tool_calls[0].function.name='render_html'`; `result.context_full=true` → snap.contextFull=true; `talentRegistry.get('render_html').recommendedContextTokens=4096` | run_finished | `context-full` (unchanged, I4); copy key swaps to `chat.contextWarning.fullHeavyTalent` | NOT rendered (sticky) | per §4h | per §4b/§4a |

---

## 7. Edge cases

| ID | Situation | Rule |
|---|---|---|
| 7a | Streaming abort mid-tool-call, no partial content | Catch path at `useChatSession.ts:642-700` deletes empty turn. No `CompletionResult` observed. `lastCompletionResult` unchanged from before the run. Last finished turn's state survives. Matches chat-flow §9a (empty-turn deletion leaves no trace). |
| 7b | Hit-max-turns | `event.result.hitMaxTurns===true` at `run_finished`. `finalResult` is still a real `CompletionResult` — snapshot written normally. `snap.contextFull` per §4a; if agent ran out of turns but last completion had headroom, `contextFull` stays `false`. Hit-max-turns is a separate problem (chat-flow `metadata.hitMaxTurns`); banner does not address it. |
| 7c | App background → OS evicts native context → foreground | `LlamaContext` destroyed; `sessionContextOverrides[sessionId]` survives (in-memory on `ChatSessionStore`). Next user message triggers existing auto-load. Override honoured silently by `getEffectiveContextInitParams` reading `sessionContextOverrides.get(activeSessionId)` (I5). No toast; D2-chosen silent survival. |
| 7d | Pal switch within a session | Override is session-keyed, not pal-keyed. Pal switch does NOT clear it. If new pal declares heavy talents and override is already set from prior CTA — fine. If not, banner reactively fires on first overflowing turn (the explicitly-accepted reactive-first-tool trade-off from the brief). |
| 7e | Pal-driven n_ctx override (resolver) | Out of scope. Pals can declare `defaultCompletionSettings.n_ctx`; resolved at completion time, not at context-init time — no interaction with `effectiveNCtx`. Per intent-brief explicit scope ("no per-pal contextSizeOverride field"), this WHAT does not change that. If a future story makes pals influence init-time n_ctx, the resolver helper + `getEffectiveContextInitParams` cross-store read is the seam to extend. |
| 7f | Two banners trying to show in the same render | Cannot happen (I4). Resolver returns exactly one variant. |
| 7g | Race: `run_finished` writes snapshot mid-render | MobX batches the write inside `updateMessage` action (atomic swap of snapshot reference). Next render observes a consistent value. Same pattern `metadata.timings` / `copyable` already follow on the same write site. |
| 7h | Resolver runs while `isGenerating === true` | Resolver depends only on `lastCompletionResult` from the last finished turn, not on in-flight token events. A banner shown during a run reflects the PRIOR turn's state. Deliberate: warning is for the next message the user is about to send. Not a live progress bar. If §4a fires on the CURRENT in-flight turn (e.g. `truncated` on the prompt), signal lands on `run_finished` and banner appears afterwards. |
| 7i | Session has assistant messages but none has `metadata.completionResult` | Legacy sessions pre-this-story. On entry, `lastCompletionResult=null`. Banner stays `none` until next user message produces fresh snapshot. No backfill (D12). |
| 7j | Pal-load hint when device can't fit the next tier (α) | activePal declares heavy talent, `effectiveNCtx=2048`, `hasEnoughMemoryWithNCtx(activeModel, 4096)=false`, no other tier in `[4096, 8192, 16384, 32768]` fits → snackbar action label = "Start new chat" (same fallback as §4h J/K). Tap invokes existing new-session path. Hint is one-shot either way: `palLoadHintSeen` records `${pal.id}:2048`; no re-fire for this pal at this n_ctx. §4i does not add a new fallback path — same logic the §4h banner-CTA uses when its tier search comes up empty. |

---

## 8. Decisions

| ID | Decision | Rationale |
|---|---|---|
| D1 | `lastCompletionResult` is a SINGLE snapshot observable on `ChatSessionStore`, not four scalars and not derived from `messages[0].metadata`. | One writer, one read, one persisted field, one atomic swap. Matches existing scalar pattern (`isStopping`, `isGenerating`) with slightly richer payload; kills inconsistent-intermediate-state risk. |
| D2 | Session override survival across `LlamaContext` destruction uses option (a) from intent-brief caveat 1: session-keyed in-memory `Map` on `ChatSessionStore`, honoured silently by `getEffectiveContextInitParams` reading `sessionContextOverrides.get(activeSessionId)` (the named seam, I5). **No toast on silent reload.** | Option (b) (one-time toast) notifies on a path the user did not trigger (background recovery); silence is the kinder default. Override is documented in banner copy when it activates; user knows they set it. |
| D3 | Remote `finish_reason==='length'` is mapped to "full," not "hedged." Hedged reserved for the all-four-conditions weak signal. | `'length'` is authoritative; OpenAI wire contract guarantees the model hit its output budget. |
| D4 | Auto-clear runway = **32 tokens absolute**, not a ratio. | Reads cleanly across `n_ctx ∈ {2048..32768}`. Ratio-based would be ~1.6% at 2048 (32 tokens) vs ~12% at 32k (4096 tokens) — second too lax. |
| D5 | Context warnings beat the HTML soft-cap. | Context-full produces visible bugs (truncated answers, parse errors); HTML soft-cap is preventative. |
| D6 | `context-full` has no dismiss affordance; exit is "send a smaller next message" or "increase context." `context-remote-hedged` is per-draft dismissible AND reactively cleared. | §4a matches are authoritative (strict `context_full` / `truncated` / `truncationLikely` / remote `length`). §4e is a weak signal — softer posture; per-draft dismiss costs nothing (re-derives on next remote turn). |
| D7 | Escalation threshold = **2 consecutive `context-full` turns** triggers escalated copy. | One failure can be a fluke; two is a pattern. |
| D8 | Terminal-punctuation set hardcoded to `.`, `!`, `?`, `。`, `！`, `？`. | Covers the 8 integrated languages' primary sentence enders without per-language branching. |
| D9 | Reuse existing `softCapBanner` View + styles in `ChatView.tsx:1073-1079` / `styles.ts:85-97`. Do not introduce a new banner component. | Variant changes inner content; shell invariant. |
| D10 | Session override does NOT mutate `modelStore.contextInitParams`. Applied at the `getEffectiveContextInitParams` read site only (I5). | Keeps user's Settings → Context Size global default untouched; override is per-session and ephemeral. |
| D11 | `WARNING_THRESHOLD` and `AUTOCLEAR_RUNWAY` pinned as named exports of the resolver module (one file). | No runtime tunable; no settings UI; future tuning is a single-line PR. |
| D12 | No backfill for legacy sessions without `metadata.completionResult`. They start with `lastCompletionResult=null` and rebuild on next finished turn. | Backfilling would require reading raw `CompletionResult` shapes never persisted; cost outweighs benefit for a one-time-only blip. |
| D13 | Snapshot-at-turn-boundary, not live during-stream tracking. | Brief asks planner to verify streaming-path complexity; the **contract** here is snapshot. If planner finds streaming cheap, revisit in follow-up. v1 pins snapshot to keep the writer set small (`run_finished` + abort-catch, two sites). |
| D14 | First-time `render_html` on a fresh chat warns **reactively**. | Model fires the tool, result inflates context, banner appears after `run_finished`. Accepted trade-off vs rejected talent-aware-predictive design. |
| D15 | (α+β) `TalentEngine.recommendedContextTokens` is declarative, not predictive. Two pure read sites: §4i pal-load hint trigger and §4d heavy-talent sub-copy lookup. | No per-turn talent inspection drives banner state; §4a / §4b / §4c resolver path unchanged. 3-round deliberation rejected predictive thresholds (complexity, false-positive risk); this amendment adds zero per-turn branching and zero new banner variants. |
| D16 | (β) Heavy-talent post-fail UX is a **sub-copy of `context-full`**, not a new variant. | Same banner shell, same dismissibility, same CTA actions. Resolver returns the same `'context-full'` value; only the copy key changes. Preserves I4, avoids inflating §4c, keeps dismiss/recovery semantics in one place. New variant would multiply (variant × dismiss × CTA-target × auto-clear) matrix without giving user a materially different action — they still need to increase context or start a new chat. |

---

## Amendment 3 — Post-implementation iOS bug-bash (4 BLOCKERs, 2 CONCERNs)

Critic re-review against shipped code surfaced four real bugs observed on iOS. Amendments are additive contract tightenings — no resolver redesign, no new variants, no new banner surface. Implementer diff is small (sheet-confirm no-session branch; resolver freshness arithmetic; snackbar surface scoping; cross-snackbar dismiss).

Each BLOCKER lists the architectural option chosen and a one-line rationale. Decisions added: D17–D20. Hard invariants added: I9 (snackbar single-surface). Three existing invariants (I3, I5, I8) are tightened in place.

### A3.1 — No-session confirm path (BLOCKER 1, §1c + §4h + I5 + Scenario Q)

**Bug**: §4i pal-load hint can fire pre-first-turn with `activeSessionId === null`. User taps "Increase context" on the snackbar → confirm sheet → `sessionContextOverrides.set(null, target)` no-ops (Map key is `null`), resolver reads `effectiveNCtx` and sees the original `baseNCtx`. Silent no-op on the reactive-first-tool path the brief explicitly accepts.

**Decision**: pending-override slot consumed at session creation. Picked over (b) materialise-first because creating a session as a side-effect of "I tapped Increase context" couples chat-session lifecycle to a UX affordance that explicitly fires BEFORE the user starts chatting; picked over (c) global `modelStore.contextInitParams` mutation because D10 forbids it and the override must remain session-scoped to honour §7d (pal-switch in same session preserves override) and Scenario K (failure reverts only the session's override, not the global default).

**§1c amendment** — pending slot added alongside the session-keyed Map:

```ts
ChatSessionStore.sessionContextOverrides: Map<sessionId, number>
ChatSessionStore.pendingContextOverride: number | undefined   // NEW (A3)
```

`pendingContextOverride` holds an override consented to by the user BEFORE any session exists (no-session pal-load-hint path). Cleared on `createNewSession` (after being copied into `sessionContextOverrides` at the new session's id) and on `resetActiveSession`. Not persisted (D2 unchanged).

**§4h amendment** — confirm sequence branches on `activeSessionId`:

| `activeSessionId` at confirm | Sequence |
|---|---|
| non-null (existing behaviour) | `sessionContextOverrides.set(activeSessionId, target)` → `releaseContext` → `initContext(activeModel)` |
| `null` (no session yet) | `pendingContextOverride = target` → `releaseContext` → `initContext(activeModel)` → on next `createNewSession(id)`: `sessionContextOverrides.set(id, pendingContextOverride)` and clear the slot |

Reload feedback (reload snackbar, success/failure copy) identical. Failure path on the no-session branch clears `pendingContextOverride` (not `sessionContextOverrides`, which has no entry to revert).

**§4f I5 amendment** — `getEffectiveContextInitParams` consults `sessionContextOverrides.get(activeSessionId)` when `activeSessionId !== null`; otherwise consults `pendingContextOverride`. Resolver's `effectiveNCtx(sessionId)` helper applies the same precedence. Both reads agree by construction (single helper).

```ts
// resolver/ModelStore co-located helper
effectiveNCtx(overrides, activeSessionId, baseNCtx, pendingOverride) =
  activeSessionId && overrides.has(activeSessionId)
    ? overrides.get(activeSessionId)
    : (pendingOverride ?? baseNCtx)
```

**Scenario Q (NEW)**: No-session confirm.

| Step | State | Observation |
|---|---|---|
| 1 | `activeSessionId=null`, activePal declares `render_html`, `baseNCtx=2048`, `pendingContextOverride=undefined` | §4i fires snackbar (Scenario N) |
| 2 | User taps "Increase context", confirms 4096 | `pendingContextOverride=4096`; `releaseContext` + `initContext(activeModel)`; `effectiveNCtx(*,null,2048,4096)=4096` |
| 3 | User sends first message → `createNewSession('s1')` | `sessionContextOverrides.set('s1', 4096)`; `pendingContextOverride=undefined`; resolver reads `effectiveNCtx(map,'s1',2048,undefined)=4096` ✓ |
| 4 | First inference runs at `n_ctx=4096` | Pal's `render_html` tool fits; no context-full banner |

### A3.2 — Reader-side freshness for `snap.contextFull` (BLOCKER 2, §4c + I3 + §4d + Scenario Q′)

**Bug**: I3 auto-clear is writer-side only (clears `contextFull` on next `run_finished` that satisfies §4b). External n_ctx changes (Settings → Context Size, model reload from another surface, app restart with persisted `snap.contextFull=true`) leave the sticky full banner up indefinitely even though `used << newNCtx − AUTOCLEAR_RUNWAY`.

**Decision**: resolver-side freshness check. Picked over (b) writer-side invalidation subscribed to n_ctx changes because no single seam emits "n_ctx changed" — Settings writes `contextInitParams.n_ctx` directly, `releaseContext+initContext` from other surfaces touches the same field, app boot loads it from disk. Subscribing in N writers is fragile. Resolver-side downgrade is a one-line arithmetic check, idempotent, runs every render, and matches the existing "resolver is a pure function of state" architecture (§4c).

**§4c amendment** — precedence table row 1 gains a freshness gate:

| Order | Variant | Match condition |
|---|---|---|
| 1 | `context-full` | `snap.contextFull === true` AND `used >= effectiveNCtx(sessionId) - AUTOCLEAR_RUNWAY` (NEW gate, A3) |
| 2..5 | unchanged | — |

When the gate fails (n_ctx changed externally OR override raised it above the stuck snapshot's `used`), resolver falls through to the warning/none path on the same render — no writer involvement.

**§4f I3 amendment** — restated for clarity:

> **I3 (auto-clear, two paths)**: (writer-side, unchanged) when a turn completes with `used < nCtx - AUTOCLEAR_RUNWAY` AND none of §4a holds, the new snapshot is written with `contextFull = false`. (reader-side, NEW) when the resolver evaluates a snapshot whose `contextFull === true` but `used < effectiveNCtx(sessionId) - AUTOCLEAR_RUNWAY` at read time, it downgrades the variant from `context-full` to the next applicable in §4c (typically `none`, or `context-warning` if §4b ratio threshold holds against the new n_ctx). The snapshot itself is NOT rewritten — next `run_finished` writer will refresh it through the normal path. Two paths agree by construction: both consult the same `(used, effectiveNCtx, AUTOCLEAR_RUNWAY)` triple.

**§4d amendment** — sticky semantics for `context-full` now mean "sticky across renders within the same n_ctx envelope." If n_ctx grows past the snapshot's `used + AUTOCLEAR_RUNWAY`, the banner clears at read time (no new render is needed beyond the next MobX-triggered one — the `effectiveNCtx` change IS a MobX dependency through `sessionContextOverrides` or `contextInitParams.n_ctx`).

**Scenario Q′ (NEW)**: External n_ctx change downgrades stale sticky full.

| Step | State | Observation |
|---|---|---|
| 1 | `nCtx=2048`, `snap.contextFull=true`, `used=2020` (Scenario C aftermath) | resolver returns `context-full`, sticky banner visible |
| 2 | User opens Settings → Context Size = 8192; reload completes | `contextInitParams.n_ctx=8192`; `effectiveNCtx=8192`; `used=2020 < 8192 - 32 = 8160` ✓ |
| 3 | Next render (same `snap`, no `run_finished` yet) | resolver freshness gate fails; downgrade to `context-warning` (ratio=0.25 < 0.80) → `none`. Banner clears. |
| 4 | Next user message + `run_finished` | normal writer-side path (I3 writer branch); snapshot refreshed. |

**Scenarios L, M updated**: both now assert freshness post-restore. Scenario L: on returning to session A with disk-restored `contextFull=true`, if user has since raised `contextInitParams.n_ctx` via Settings such that `used < newNCtx - AUTOCLEAR_RUNWAY`, banner does NOT render. Scenario M (cold launch): same rule — `contextFull=true` recovered from disk is downgraded at read time if current `effectiveNCtx` provides headroom.

### A3.3 — Snackbar surface scoping (BLOCKER 3, I8 + §4i + Scenarios R/S)

**Bug**: Both snackbars (reload status + pal-load hint) render in RNP `<Portal>` which hoists above the navigator. Chat-screen snackbars appear over Settings, Models, Pals screens. I8 says snackbars "live on different surface" but doesn't pin which surface or lifecycle. Cross-screen visual bleed.

**Decision**: snackbars scoped to chat screen; predicate evaluation and snackbar render both gated on chat-screen focus. Picked over "always-render but suppress when blurred" because the `usePalLoadHint` effect would still fire (and mark `palLoadHintSeen`) while the user is on Settings — burning the one-shot opportunity off-screen.

**I8 amendment** — codify the surface and lifecycle:

> **I8 (snackbar surface scoping)**: Both context-related snackbars (reload status, pal-load hint) render inside the chat screen's React tree only. While chat screen is not focused (`useIsFocused()` from `@react-navigation/native` returns false), (a) snackbar renders are suppressed (no JSX emits) and (b) `usePalLoadHint` predicate evaluation is paused (effect early-returns; the suppressor key is NOT marked). On refocus, the effect re-runs against the current signature and fires the snackbar if conditions still hold. I4 (one banner) is independent of this rule.
>
> Snackbar visibility state lives on `useContextBanner`'s `useState` and persists across the conditional render — gating suppresses JSX only, not state. If the RNP auto-dismiss timer fires while the snackbar's JSX is gated out (chat unfocused), the `onDismiss` callback still sets `visible=false`; on refocus the snackbar stays hidden because its `visible` is now `false`. If the timer has NOT yet fired when the user returns, the snackbar reappears with whatever time RNP has remaining on its internal timer — PocketPal does not pause or resume the duration timer; the underlying RNP `Snackbar` owns it. Lightest possible semantics: re-entry behaviour is whatever `visible` says at the moment chat refocuses.

**§4i amendment** — lifecycle step 0 prepended:

> 0. (NEW, A3) Predicate evaluation is gated on `useIsFocused()`. While chat screen is not focused, the effect early-returns before the predicate is checked — no marker, no snackbar, no signature update. Refocus triggers a normal evaluation against the current signature.

**Scenario R (NEW)**: Pal-load hint suppressed off-chat-screen.

| Step | State | Observation |
|---|---|---|
| 1 | User opens Settings; activePal change happens via deep-link / programmatic | `usePalLoadHint` effect fires but `isFocused=false` → early return; `palLoadHintSeen` unchanged; no snackbar |
| 2 | User navigates back to chat | `useIsFocused()` → true; effect re-runs; predicate still holds; snackbar emits exactly once |

**Scenario S (NEW)**: Reload snackbar does not bleed across screens.

| Step | State | Observation |
|---|---|---|
| 1 | User taps "Increase context" on banner; `reloadSnackbar.phase='reloading'`, `isFocused=true` | snackbar visible on chat |
| 2 | User navigates to Settings mid-reload | `isFocused=false`; reload snackbar JSX gated out; reload itself continues (lives on `useContextBanner` state, not on the JSX) |
| 3 | Reload completes (`phase='success'`); user navigates back | `isFocused=true`; snackbar JSX gates back in; success message visible (state survives navigation; only render is gated) |

### A3.4 — Snackbar single-surface invariant + dismiss-on-action (BLOCKER 4, new I9 + §4i + §4h + Scenario T)

**Bug 1**: Pal-load hint snackbar (8s duration) survives the sheet/reload flow it advertised. User taps "Increase context" on the hint → sheet opens → confirm → reload snackbar appears → pal-load hint snackbar is STILL visible behind/above the reload snackbar until its 8s timer runs out. Stale UX, contradicts I4's spirit.

**Bug 2**: Tapping the snackbar action label dismisses asynchronously via `setState` round-trip while the action callback (open sheet, reset session) fires; UI looks laggy.

**Decision**: I9 (new) — at most ONE snackbar visible at any time across the chat-snackbar set (reload status + pal-load hint). Reload status takes precedence over pal-load hint (it's user-initiated, currently in progress, and confirms an explicit recent intent). Pal-load hint is preempted (dismissed synchronously) when the reload snackbar appears. Plus: tapping a snackbar action label dismisses synchronously regardless of remaining duration.

**§4f I9 (NEW)**:

> **I9 (chat-snackbar single-surface)**: At most ONE snackbar from the chat-snackbar set (`reloadSnackbar` from §4h, pal-load hint from §4i) is visible at any time. Precedence: reload status > pal-load hint. When a higher-precedence snackbar enters the visible state, the same event handler that sets the higher-precedence snackbar visible MUST also set any currently-visible lower-precedence snackbar in the set to `visible=false` — both `useState` setters fire in the one handler, React 18 batches them into a single commit, and no intermediate frame is rendered with both visible. Tapping a snackbar action label follows the same rule: the action-label handler sets that snackbar's `visible=false` AND invokes the action callback in the one handler; React 18 batches the state updates from both into one commit, so the action callback never paints a frame where the snackbar is still visible. `flushSync` is NOT required and MUST NOT be used. I4 (banner singleton) is independent.

**§4h amendment** — confirm step prepends a pal-load-hint dismiss:

> When the user confirms the sheet AND the pal-load hint snackbar is currently visible (the same UX flow that opened the sheet from the hint), the same confirm handler MUST call both setters: pal-load hint `visible=false` AND `reloadSnackbar` → `reloading` phase. React 18 batches the two `useState` updates from the one handler into a single commit; one render shows the hide-and-show together. No explicit cross-commit ordering is required and `flushSync` MUST NOT be used.

**§4i lifecycle amendment** — step 3 (snackbar action handler):

> 3. (TIGHTENED, A3) The snackbar action handler runs both effects in one handler call: sets `visible=false` on the hint's local `useState` AND invokes the action callback (open sheet for `increase`; `resetActiveSession` for `newChat`). React 18 batches the state updates triggered by both into a single commit, so the action's downstream UI is never rendered alongside a still-visible hint snackbar. No `flushSync`, no explicit ordering between commits. Suppressor key (`palLoadHintSeen`) is inserted at emit time per §4i.2, so the dismiss does not affect one-shot semantics.

**Scenario T (NEW)**: Hint → sheet → reload — single-surface invariant.

| Step | State | Observation |
|---|---|---|
| 1 | Pal-load hint snackbar visible (Scenario N) | one snackbar visible (hint) |
| 2 | User taps "Increase context" action label | hint snackbar dismissed synchronously (I9 dismiss-on-action); sheet opens; still one (or zero) visible |
| 3 | User confirms sheet | (defensive, §4h amendment) hint already dismissed in step 2; reload snackbar enters `reloading` phase; still one visible (reload) |
| 4 | Reload completes | reload snackbar transitions to `success` phase (existing remount-on-`key` flow); still one visible |
| 5 | Reload snackbar 4s timer expires OR user taps dismiss | no snackbars visible |

### A3.5 — `palLoadHintSeen` clear-trigger audit (CONCERN 1, §1f / §5)

`palLoadHintSeen` is currently cleared on `resetActiveSession` only (verified at `ChatSessionStore.ts:431` and `:478`). Post-A3.1 (no-session confirm), the suppressor key still uses `(palId, effectiveNCtxForSession)`. When the no-session confirm completes and a session is later created at the lifted n_ctx, the new key `${palId}:${liftedNCtx}` is different from the previously-marked `${palId}:${baseNCtx}` — no extra clear needed. The Set is bounded by |loaded pals| × |tier table|, unchanged.

**§5 amendment** — clear-trigger column for `palLoadHintSeen` row stays as `on resetActiveSession`; no addition required. CONCERN 1 closed without contract change. Audit recorded here for traceability.

### A3.6 — Scenarios L, M freshness assertions (CONCERN 2)

Folded into A3.2 above. Both scenarios now assert resolver-side freshness post-restore/post-launch when current `effectiveNCtx` provides headroom.

### A3.7 — Decisions added

| ID | Decision | Rationale |
|---|---|---|
| D17 | (A3.1) No-session override uses a single-slot `pendingContextOverride` consumed at `createNewSession`, not premature session materialization or global-default mutation. | Keeps D10 invariant (no `modelStore.contextInitParams` mutation), keeps override session-scoped (honours §7d / Scenario K), avoids coupling chat-session lifecycle to a pre-chat UX affordance. |
| D18 | (A3.2) Auto-clear has TWO paths: writer-side at `run_finished` (existing) and reader-side at resolve time (new). Both consult the same `(used, effectiveNCtx, AUTOCLEAR_RUNWAY)` triple. | Reader-side handles external n_ctx changes (Settings, app restart with persisted full + higher current n_ctx) that no single writer seam catches. Idempotent, runs every render, no new subscribers. |
| D19 | (A3.3) Snackbars render inside chat-screen React tree only; `usePalLoadHint` predicate paused while chat unfocused. | RNP `<Portal>` hoists above the navigator → cross-screen visual bleed without the focus gate. Pausing predicate evaluation (not just suppressing render) preserves the one-shot opportunity for when the user returns. Re-entry to chat does NOT re-emit a snackbar whose RNP duration elapsed off-screen: `visible` was already set to `false` by `onDismiss` before refocus. No pause/resume of the duration timer; lightest possible semantics. |
| D20 | (A3.4) Chat snackbars form a single-surface set with reload > pal-load-hint precedence; tap-action dismisses synchronously. | Two snackbars on screen at once contradicts I4's spirit. Synchronous dismiss-on-action removes a perceived-lag bug that surfaced on iOS. |

### A3.8 — Out of scope (defer)

- Persisting `pendingContextOverride` across app restarts. Same rationale as D2 — silent survival is the kind default within app lifetime; restart is a deliberate boundary.
- Cross-screen snackbar relocation (e.g. showing reload-status on Settings when user navigates away mid-reload). State survives navigation; only render is gated. If telemetry shows users routinely navigating away mid-reload and missing the success confirmation, revisit in a follow-up.
- Predicting external n_ctx changes from Settings UI (e.g. closing the banner instantly on slider release). Reader-side freshness already handles it at the next render, which fires immediately when `contextInitParams.n_ctx` mutates (MobX dependency).

---

Review history: [./deliberation-log.md](./deliberation-log.md)
