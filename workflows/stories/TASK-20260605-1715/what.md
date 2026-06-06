# Chat context-limit banner — WHAT

Story-scoped delta on `context/architecture/chat-flow.md` (§9f, §1, §5, Invariants)
and `context/architecture/pals-and-talents.md` (§5a I8). On promotion, the delta
absorbs into both docs in the same PR.

**Conventions**: `(C)` current (verified from code), `(P)` proposal, `(D)` decision (≤ 12-word rationale). Zero `(?)`.

---

## Drift check

STOP-level drift was found and is reconciled in this delta (not a separate fix-up, because
the drift is *aspirational-ahead* — docs describe unbuilt behaviour as `(C)`; there is no
silently-violated invariant in live code to repair). Both flow docs describe this entire
feature as shipped `(C)`. Verified at `origin/main` worktree: **zero** code matches for
`bannerVariantResolver`, `resolveBannerVariant`, `IncreaseContextSheet`, `runtimeNCtx`,
`lastCompletionResult`, `dismissedBannerVariants`, `consecutiveFullFailures`, `palLoadHintSeen`,
`usePalLoadHint`, `useContextBanner`, `recommendedContextTokens`, `runtimeContextSettings`,
`pendingReloadRequired`, `context-remote-hedged`, `BannerRow`, `CompletionResultSnapshot`,
`deriveSnapshotFromResult`, `applyStickyFull`. This WHAT re-marks all of that as `(P)` and is
the real contract; the implementer rewrites the doc prose from `(C)` to match what actually lands.
Two doc-invented names are corrected to real fields: `runtimeNCtx`/`runtimeContextSettings` →
existing `modelStore.activeContextSettings.n_ctx`. The public store method is
`ChatSessionStore.bulkDeleteSessions()` (no args; operates on `selectedSessionIds`); the doc name was correct.

---

## Design exploration

Candidates: `design-candidate-A.md`, `design-candidate-B.md`, `design-candidate-C.md`.
This WHAT synthesizes candidate A.

### Alternatives considered

- selected: snapshot-on-store + pure resolver — matches doc shape, no reader-side arithmetic.
- rejected: recompute-on-render, component-local dismiss — duplicates arithmetic, loses dismiss on refocus.
- rejected: footer-only escalation — cannot be sticky or near-input for the ~80% warning.

---

## 1. Data model

Only fields changing or at risk.

```
ChatSessionStore (MobX, ephemeral — NOT persisted to DB)
  lastCompletionResult? : CompletionResultSnapshot   (P) newest finished turn's snapshot
  dismissedBannerVariants : Set<BannerVariant>       (P) variants the user dismissed this draft
  consecutiveFullFailures : number                   (P) run of contextFull turns; drives escalation copy
  palLoadHintSeen : Set<string>                       (P) signatures already shown the pal-load snackbar

AssistantTurn.metadata (Record<string,any> — (C) untyped)
  completionResult? : CompletionResultSnapshot        (P) per-turn mirror of the snapshot
                                                      //   DANGLING-READER CONTRACT today: PlayButton (C)
                                                      //   READS metadata.completionResult{,.reasoning_content}
                                                      //   on the legacy `text` branch; NO writer exists in src.
                                                      //   This WHAT is the FIRST writer. Write must preserve
                                                      //   those two read paths (I9).

CompletionResultSnapshot                              (P) normalised at write time
  content?           : string
  reasoning_content? : string
  used               : number    // local: tokensEvaluated + tokensPredicted (see §1b — tokens_cached
                                  //   is NOT available at the engine boundary; redefined accordingly)
  contextFull        : boolean    // OR-predicate result, frozen at write (see I2)
  tokensPredicted?   : number
  finishReason?      : string     // remote: derived from stopped_limit (see §1b); 'length' iff stopped_limit===1
  isRemote           : boolean
```

Persisted: `metadata.completionResult` (on disk via `ChatSessionRepository`, same as other metadata).
Ephemeral (MobX-only, no DB column, no migration): all four `ChatSessionStore` fields above. (D)

**Glossary**:
- **runtime n_ctx** — `modelStore.activeContextSettings?.n_ctx` (C): the n_ctx the running LlamaContext was loaded with. The doc's `runtimeNCtx` name does not exist; this is the real field.
- **configured n_ctx** — `modelStore.contextInitParams.n_ctx` (C): the next-init intent, written by Settings slider and by the increase-context CTA.
- **BannerVariant** — `'context-full' | 'context-warning' | 'context-remote-hedged' | 'html-soft-cap' | 'none'`.
- **isRemote** — `modelStore.activeModel?.origin === ModelOrigin.REMOTE` (C).

### 1b. External shape — what the snapshot boundary actually exposes

`CompletionResult` (C, `src/utils/completionTypes.ts:84`) carries `context_full`, `truncated`,
`tokens_predicted`, `tokens_evaluated`, `stopped_limit`, `interrupted`. `LocalCompletionEngine.completion`
maps native fields 1:1 (C, `src/api/completionEngines.ts:36-51`). The local `finalResult` at
`run_finished` (C, `useChatSession.ts:327`) is the snapshot source; today these are read for timings
only and the rest discarded.

**`used` (BLOCKER 3, option b):** `tokens_cached` is dropped at the engine boundary — documented as
EXCLUDED (C, `completionTypes.ts` comment) and absent from `src/`; surfacing it is an out-of-scope native
change. So `used = tokens_evaluated + tokens_predicted` (D8). On prompt-cache-reuse turns `tokens_evaluated`
is smaller, so `used` UNDER-counts KV occupancy → the ~80% warning fires late, never early. The sticky
`context-full` path reads `contextFull` directly (I2), not the ratio, so the hard-limit path is unaffected. (D)

**Remote `finishReason` (CONCERN 1):** `OpenAICompletionEngine` returns no `finishReason`; it collapses
`finish_reason === 'length'` into `stopped_limit = 1` (C, `src/api/openai.ts:611-628`). The deriver maps
`isRemote && finalResult.stopped_limit === 1 → finishReason = 'length'` at write. No new engine field. (P)

---

## 2. Event flow

Snapshot is written at exactly two boundaries (same MobX action each time):

```
run_finished              → deriveSnapshot(finalResult, activeContextSettings.n_ctx) → write metadata.completionResult
                            + chatSessionStore.lastCompletionResult; update consecutiveFullFailures
abort-catch w/ partial    → same snapshot write (contextFull may be true via truncationLikely)
```

No live during-stream tracking (out of scope).

---

## 3. State machine

Banner is stateless per render — resolved fresh. Sticky/dismiss is the only stateful axis:

```
none ─turn finishes contextFull→ context-full (sticky)
context-full ─next turn used < nCtx-RUNWAY (freshness gate) → falls through to warning/none
context-warning ─user dismiss→ suppressed-this-draft ─next triggered turn→ context-warning again
```

| State | User-visible feedback |
| --- | --- |
| `context-full` | strong sticky banner; recovery CTAs; no dismiss |
| `context-warning` | softer "getting tight" banner; dismissable for the draft |
| `context-remote-hedged` | hedged "reply may be cut off" advisory; no increase CTA; dismissable |
| `html-soft-cap` | existing soft-cap text (C); unchanged |
| `none` | banner slot hidden |

---

## 4. Contract

### 4a. Banner-variant resolver precedence (pure)

`resolveBannerVariant` returns exactly ONE variant in this order; first match wins:

1. `context-full` (P) — `snap.contextFull === true` AND reader-freshness gate holds
   (`snap.used >= effectiveNCtx - AUTOCLEAR_RUNWAY`). Sticky; not dismissable.
2. `context-warning` (P) — local session, `snap.used / effectiveNCtx >= WARNING_THRESHOLD`
   (0.80), not contextFull, not dismissed-this-draft.
3. `context-remote-hedged` (P) — remote session, weak-signal heuristic, not dismissed-this-draft.
4. `html-soft-cap` (C) — `htmlPreviewCount >= 4`. Existing rule preserved; context variants
   take precedence so the real bug beats the preventative hint.
5. `none` (P) — slot hidden.

`effectiveNCtx` = runtime n_ctx (`activeContextSettings.n_ctx`).

**Increase-context tier gate (CONCERN 3 / AC3):** the resolver computes a single `nextNCtx` = the next
larger candidate n_ctx (doubling steps, clamped to the model's slider max) whose
`getModelMemoryRequirement(activeModel, projModel, {...contextInitParams, n_ctx: candidate})`
(C, `memoryEstimator.ts:105`) is ≤ `modelStore.availableMemoryCeiling` (C, `ModelStore.ts:192`) — the
same estimator the load path uses. If no larger candidate fits, `nextNCtx = undefined` and the banner
offers ONLY [New chat] (increase CTA hidden) — never offer an n_ctx the device can't fit (OOM safety). (P, D)

### 4b. Hard invariants

- **I1 (one banner per render)**: resolver short-circuits; the chat-input slot renders at most one variant. (P)
- **I2 (snapshot truth)**: `contextFull` is frozen at write time as the OR of
  `finalResult.context_full` / `finalResult.truncated` / `metadata.truncationLikely` (C, abort path,
  `useChatSession.ts:678`) / (remote) `finishReason === 'length'` (derived per §1b from `stopped_limit`).
  Readers never recompute it. (P)
- **I3 (paired write)**: `lastCompletionResult` and `metadata.completionResult` are written in the
  same MobX action by the same writer. (P)
- **I4 (single global n_ctx, two named views)**: banner readers use `activeContextSettings.n_ctx`
  (runtime) and `contextInitParams.n_ctx` (configured); no per-session or pending override layer. (C/P)
- **I5 (suppress when inactionable)**: `context-*` variants are suppressed when no LlamaContext is
  loaded (`modelStore.activeModelId === undefined`); `html-soft-cap` is independent of model state. (P)
- **I6 (snackbar is not a banner)**: the pal-load hint is a snackbar on a separate surface; it cannot
  displace or be displaced by a banner variant. At most one snackbar per frame. (P)
- **I7 (increase-context = local only)**: `context-remote-hedged` never offers increase-context;
  PocketPal does not own a remote server's n_ctx. (P)
- **I8 (recommendedContextTokens is declarative)**: read at exactly two pure sites — pal-load hint
  trigger and the heavy-talent sub-copy lookup on `context-full`. It NEVER moves the banner trigger
  threshold (which stays purely ratio-based). Engines without the field work unchanged;
  `RenderHtmlEngine` declares it, `calculate`/`datetime` omit. (P)
- **I9 (dangling-reader contract preserved)**: `metadata.completionResult` is read-only today —
  `PlayButton` (C, `PlayButton.tsx:56,78`) reads `completionResult` / `.reasoning_content` on the legacy
  `text` branch; NO writer exists in `src/`. This WHAT is the first writer; the snapshot MUST carry
  `content` + `reasoning_content` so those reads keep working. New fields additive. (P)
- **I10 (no double "cut off")**: the footer "Cut off — likely context full" text (C,
  `AssistantTurnFooter.tsx:111-112`, key `components.bubble.truncated`) fires on the SAME
  `interrupted && truncationLikely` event that raises `context-full` via I2. When the `context-full`
  banner shows for the latest turn, the footer's truncated text on THAT turn is suppressed — the sticky
  banner is the single stronger surface. The footer still shows plain `interrupted` status when
  interrupted-but-not-truncated. Non-duplication is load-bearing (intent §5), so this is an invariant. (P)

### 4c. Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| `BannerRow` (in `ChatView`, the existing soft-cap slot) | ONE variant from the resolver | per-variant logic; arithmetic |
| `resolveBannerVariant` (pure) | resolved variant + payload (next-fit n_ctx target or `undefined`, heavy-talent name) | JSX; MobX writes; async |
| `IncreaseContextSheet` | confirm sheet for the CTA + reload feedback snackbar | computing the target (resolver supplies the memory-gated next-fit n_ctx) |
| `usePalLoadHint` (pure hook) | one-shot snackbar trigger when a heavy-talent pal loads below its recommendation | banner state (snackbar layer is separate, I6) |
| existing soft-cap `View testID="soft-cap-warning"` (C) | now a sub-case of `BannerRow` | — |

---

## 5. Single-writer rule

| Field | Single writer |
| --- | --- |
| `metadata.completionResult` (snapshot) | `useChatSession` at `run_finished` AND abort-catch-with-partial (same action seeds `lastCompletionResult`) (P) |
| `chatSessionStore.lastCompletionResult` | same writer as above; `setActiveSession` hydrates from disk; `resetActiveSession` clears (P) |
| `chatSessionStore.dismissedBannerVariants` | `BannerRow` on user dismiss; cleared per-draft by the `run_finished` writer, on `deleteSession(id)` (C, line 285), as a whole-op clear in `bulkDeleteSessions()` (C, line 1281 — no args; already calls `resetActiveSession()`), and on `resetActiveSession`/`setActiveSession` (P) |
| `chatSessionStore.consecutiveFullFailures` | `useChatSession` at `run_finished`/abort: increment on `contextFull`, reset otherwise (P) |
| `chatSessionStore.palLoadHintSeen` | `usePalLoadHint` at emit; cleared on `resetActiveSession` (P) |
| `modelStore.contextInitParams.n_ctx` | Settings slider (C, `setNContext`) AND `IncreaseContextSheet` confirm (P, calls `setNContext(target)` → `releaseContext`+`initContext`; on failure restores prior via second `setNContext`) — single global, no override layer |
| `modelStore.activeContextSettings` | `initContext` on success, cleared on release (C) — unchanged |

Cross-store reads: `ChatView`/resolver read `modelStore` (`activeContextSettings.n_ctx`,
`contextInitParams.n_ctx`, `activeModelId`, `activeModel.origin`). `ChatSessionStore` does NOT
read `ModelStore` — no cycle. (P)

Past pain related to multi-writer races: the merged thinking-override story showed that an
ephemeral per-chat user signal must not be written into a persisted global; banner state stays
MobX-ephemeral for the same reason. (D)

**Deferred cleanups** (out of current scope):
1. Cleanup-DEFERRED (existing) — `inferencing`/`isStreaming`/`isGenerating` should derive from `agentUiState.status`; untouched here.

---

## 6. Canonical scenarios

### A. Near-limit warning (local)
```
local model n_ctx=4096; turn finishes used=3300 (0.80+), contextFull=false
─────
context-warning banner; dismissable; reappears next still-tight turn
```

### B. Full + sticky (local), incl. escalation
```
turn finishes context_full=true (or truncationLikely on abort)
─────
context-full sticky banner with [New chat] + [Increase context if a larger n_ctx fits];
AssistantTurnFooter "cut off" text on that turn is suppressed (I10);
consecutiveFullFailures=1
─────
user sends again, finishes context_full=true again → consecutiveFullFailures=2
→ banner copy escalates (stronger "still overflowing" wording); same CTAs
─────
persists until a finished turn has used < effectiveNCtx-RUNWAY (freshness gate);
note: escalation distinction is copy-only — out of automated-test scope (manual/visual)
```

### C. Increase-context recovery clears sticky without new inference
```
context-full visible; user confirms increase 4096→8192; reload succeeds
─────
freshness gate: snap.used < 8192-RUNWAY → banner falls through to none; history preserved
```

### D. Remote hedged
```
remote model; reply weak-signal truncated (not finish_reason=length, tokensPredicted>=500, no terminal punctuation)
─────
context-remote-hedged advisory; NO increase CTA (I7); dismissable
```

### E. Suppression
```
no model loaded  → context-* suppressed (I5); html-soft-cap may still show
dismissed-this-draft + still triggered → suppressed until next turn re-triggers (warning/hedged only)
htmlPreviewCount>=4 AND context-full → context-full wins (4a precedence)
```

### F. Talent copy + pal-load snackbar
```
heavy-talent pal (render_html, recommendedContextTokens=4096) loads into chat with n_ctx=2048
─────
one-shot snackbar "this pal tends to need more room" (I8); NOT a banner (I6)
last turn called render_html AND context-full → full banner shows heavy-talent sub-copy variant
```

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `lastCompletionResult.contextFull` | `useChatSession` (snapshot write) | resolver | most recent finished turn matched the OR-predicate (I2) |
| `dismissedBannerVariants` | `BannerRow` dismiss | resolver | user dismissed that variant this draft |
| `consecutiveFullFailures` | `useChatSession` | full-banner copy | run of back-to-back contextFull turns |
| `palLoadHintSeen` | `usePalLoadHint` | pal-load hint | this `(palId,n_ctx,talents)` signature already shown |

---

## 8. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Banner state is MobX-ephemeral, no DB column/migration | Ephemeral per-chat UI signal; persisting global taints other chats |
| D2 | Snapshot mirrored on message AND store, one action | Reader freshness + survives reload; no recompute (I2/I3) |
| D3 | Use existing `activeContextSettings.n_ctx`, not new `runtimeNCtx` | Real field already records loaded n_ctx; doc name was invented |
| D4 | Trigger is ratio-only; talent metadata drives copy + snackbar only | Talent-agnostic trigger per intent; predictive thresholds out of scope |
| D5 | Reuse the single soft-cap banner slot, context variants take precedence | One slot, real bug beats preventative hint |
| D6 | Remote gets advisory only, no increase CTA | PocketPal does not own remote n_ctx (I7) |
| D7 | Increase-context target is the next-fit n_ctx via `getModelMemoryRequirement` vs `availableMemoryCeiling` | Reuse load-path estimator; hide CTA when none fits — OOM-safe |
| D8 | `used` = `tokens_evaluated + tokens_predicted` (drop `tokens_cached`) | Dropped at engine boundary; surfacing it is out-of-scope native change |
| D9 | `context-full` banner suppresses the footer "cut off" on that turn | Same event fires both; banner is the single stronger surface (I10) |

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | Abort mid-stream with partial content | snapshot still written; `truncationLikely` feeds `contextFull` (I2) |
| 9b | Reload an old chat whose snapshot predates this feature | `metadata.completionResult` lacks new fields → treated as not-full; banner none until next turn |
| 9c | User raises n_ctx then sends; still tight | freshness gate re-evaluates against new effectiveNCtx; warning may reappear (4a) |
| 9d | Remote server omits `finish_reason`/`tokens_predicted` | weak-signal heuristic simply doesn't fire; no false advisory (4a.3) |
| 9e | Increase-context reload fails | prior n_ctx restored via second `setNContext`; chat history intact; failure snackbar |
| 9g | `context-full` but no larger n_ctx fits the device | resolver `nextNCtx === undefined`; banner shows [New chat] only, increase CTA hidden (D7) |
| 9h | Latest turn truncated → both footer + banner would fire | footer "cut off" suppressed on that turn; sticky banner is the sole surface (I10) |
| 9f | TTS/PlayButton read `metadata.completionResult` | unchanged — new fields additive (I9) |

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | `bulkDeleteSessions→deleteSessions` rename inverted reality | BLOCKER | FIXED — reverted; `bulkDeleteSessions()` (no args) is the real method (line 1281); §5 + drift note corrected. |
| 1 | New `context-full` banner duplicates footer "cut off" | BLOCKER | FIXED — invariant I10 suppresses footer truncated text under the sticky banner; edge 9h, D9, scenario B. |
| 1 | `used` reads `tokens_cached`, dropped at engine boundary | BLOCKER | FIXED — option (b): `used = tokens_evaluated + tokens_predicted`; §1b states the late-warning consequence; D8. |
| 1 | Remote `finishReason` not preserved at wire boundary | CONCERN | FIXED — §1b deriver maps `isRemote && stopped_limit===1 → 'length'`; no new engine field. |
| 1 | `metadata.completionResult` is a net-new write, not extension | CONCERN | FIXED — re-marked dangling-reader contract; I9 rewritten; this WHAT is first writer. |
| 1 | Memory-aware tier selection undefined | CONCERN | FIXED — §4a gate via `getModelMemoryRequirement` vs `availableMemoryCeiling`; hide CTA if none fits (9g, D7). |
| 1 | No scenario for `consecutiveFullFailures` escalation | SUGGESTION | FIXED — Scenario B extended; escalation copy noted out of automated-test scope. |
