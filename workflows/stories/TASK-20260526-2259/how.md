# Implementation Plan: Context-full warning UX in chat

**Purpose**: land the design in `what.md` — one snapshot observable on `ChatSessionStore`, a banner-variant resolver that subsumes the existing HTML soft-cap, a session-only "increase context" override, a weak-signal remote variant, and (α + β amendment) a declarative `recommendedContextTokens` hint on `TalentEngine` with a pal-load snackbar and a heavy-talent post-fail sub-copy.

This HOW front-loads UX analysis (§A) before the plumbing worklist (§B). All design content is anchored in WHAT §X references — no new contracts are invented here.

---

## Metadata

- **Task ID**: TASK-20260526-2259
- **Worktree**: `./worktrees/TASK-20260526-2259`
- **Branch**: `feature/TASK-20260526-2259`
- **Native Changes**: NO
- **Visual Confirmation**: YES
- **Intent Brief**: `./workflows/stories/TASK-20260526-2259/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260526-2259/what.md`
- **Architecture docs being updated**: `./context/architecture/chat-flow.md`, `./context/architecture/pals-and-talents.md`
- **Status**: draft
- **Review log**: see `./deliberation-log.md` (R1 plan-critic, R2 plan-critic, R3 amendments absorbed)

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — verify finish_reason → CompletionResult adapter | DONE | - | verified `src/api/openai.ts` mapping + existing tests (line 503-540) |
| Step 2 — `run_finished` writer extension (snapshot + persisted metadata) | DONE | 49d0f99 | §1a, §1b, §5, I7 |
| Step 3 — `ChatSessionStore` state additions + hydration | DONE | 5ad6751 | committed alongside resolver scaffold |
| Step 4 — resolver module (pure) + β heavy-talent sub-copy | DONE | 55fafb1 | added TalentEngine.recommendedContextTokens here |
| Step 5 — `getEffectiveContextInitParams` cross-store read | DONE | f50b8de | §5, I5 |
| Step 6 — `ChatView` banner shell replacement | DONE | a83d28d | committed with Step 8 |
| Step 7 — l10n keys (`chat.contextWarning.*`) | DONE | 2fcbbeb | en.json only; Weblate handles other languages |
| Step 8 — Increase context CTA + sheet + reload UX | DONE | a83d28d | committed with Step 6 |
| Step 9 — α pal-load hint snackbar + `TalentEngine.recommendedContextTokens` | DONE | 79e3dea | recommendedContextTokens landed in Step 4 |
| Step 10 — Tests | deferred | - | tester (next pipeline stage) writes tests; implementer covered only typecheck + lint |
| Architecture docs updated | DONE | 9feb8c2 (dev-team repo) | absorbed WHAT delta into chat-flow.md + pals-and-talents.md |

---

# §A. UX Analysis

## A.1 Copy register and l10n pressure-test

**Pinned register**: friendly-only in the banner. No raw token numbers, no parenthetical time hedges. Raw n_ctx values surface only inside `IncreaseContextSheet` under an "Advanced" disclosure. Matches existing `chat.softCapWarning` register; survives translation across all 8 integrated languages on iPhone SE.

### A.1.1 L10n pressure-test (one line per language)

iPhone SE budget: ~38 CJK chars / ~60 Latin chars per line; the banner uses two-line title+message, so the budget is *per line*, not total. Worst-case message is `full` (3 lines on SE — acceptable; the banner is meant to capture attention).

| lang     | `warning.message` chars | `full.message` chars | iPhone SE wrap risk             | RTL note            |
|----------|-------------------------|----------------------|---------------------------------|---------------------|
| en       | 36                      | 78                   | none / 2-line title+msg         | n/a                 |
| he       | ~40                     | ~80                  | none; mirrors cleanly           | RTL primary, verified by `softCapBanner` reuse (D9) |
| id       | ~70                     | ~120                 | full → 3 lines, acceptable      | n/a                 |
| ja       | ~25 (CJK denser)        | ~50                  | 2 lines max                     | n/a                 |
| ko       | ~28                     | ~55                  | 2 lines max                     | n/a                 |
| ms       | ~65                     | ~115                 | full → 3 lines, acceptable      | n/a                 |
| ru       | ~50                     | ~95                  | tight; 2-line OK                | n/a                 |
| zh       | ~18                     | ~38                  | 1–2 lines                       | n/a                 |
| fa (futures) | ~45                 | ~85                  | RTL like he                     | RTL                 |

Action button labels are short across all languages (worst: id `"Tambah konteks"` 14 + `"Tutup"` 5 — fits inline). RTL correctness is by construction: the existing `softCapBanner` uses only symmetric `paddingHorizontal` and `textAlign:'center'`; no `marginLeft`/`marginRight` literals to mirror (D9).

### A.1.2 Copy decisions (pinned strings — source of truth for Weblate)

All new keys under `chat.contextWarning.*`. Existing `chat.softCapWarning` is **kept** (resolver's `'html-soft-cap'` variant maps to it — avoids Weblate churn for unchanged semantics).

| Variant / surface                         | English copy                                                                                                                           | l10n key                                  | Notes                                            |
|-------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------|--------------------------------------------------|
| `context-warning` title                   | "This chat is filling up."                                                                                                             | `chat.contextWarning.warning.title`       |                                                  |
| `context-warning` message                 | "Replies may start getting cut off."                                                                                                   | `chat.contextWarning.warning.message`     |                                                  |
| `context-warning` CTA primary             | "Increase context"                                                                                                                     | `chat.contextWarning.warning.increase`    |                                                  |
| `context-warning` CTA secondary           | "Dismiss"                                                                                                                              | `chat.contextWarning.warning.dismiss`     | per-draft (WHAT §4d)                             |
| `context-full` title                      | "Chat reached its memory limit."                                                                                                       | `chat.contextWarning.full.title`          | sticky (D6) — no Dismiss button rendered         |
| `context-full` message                    | "The model can't fit any more of this conversation. Increase context or start a new chat."                                             | `chat.contextWarning.full.message`        |                                                  |
| `context-full` CTAs                       | "Increase context" / "New chat"                                                                                                        | `chat.contextWarning.full.increase` / `newChat` |                                            |
| `context-full` escalated title            | "Still at the memory limit."                                                                                                           | `chat.contextWarning.fullEscalated.title` | counter ≥ 2 (WHAT §4d, D7)                       |
| `context-full` escalated message          | "Recent replies have been truncated. Try a larger context or start a new chat with a shorter prompt."                                  | `chat.contextWarning.fullEscalated.message` |                                                |
| `context-full` heavy-talent title (β)     | "Chat reached its memory limit."                                                                                                       | `chat.contextWarning.fullHeavyTalent.title` | same shell as `full` (D16); copy key only swap |
| `context-full` heavy-talent message (β)   | "{talentName} needs more room than this chat has. Increase context or start a new chat."                                               | `chat.contextWarning.fullHeavyTalent.message` | `{talentName}` placeholder; resolver passes the matched talent name |
| `context-remote-hedged` title             | "Reply may be cut off."                                                                                                                | `chat.contextWarning.remoteHedged.title`  |                                                  |
| `context-remote-hedged` message           | "You may be near the model's context limit on the server."                                                                             | `chat.contextWarning.remoteHedged.message` | "on the server" preserves causal hedge          |
| `context-remote-hedged` CTA               | "Dismiss"                                                                                                                              | `chat.contextWarning.remoteHedged.dismiss` | per-draft, also reactively cleared (WHAT §4d)   |
| Sheet title                               | "Increase context size"                                                                                                                | `chat.contextWarning.sheet.title`         |                                                  |
| Sheet body                                | "We'll reload the model with a larger context so this chat has more room."                                                             | `chat.contextWarning.sheet.body`          |                                                  |
| Sheet current/new labels                  | "Current context" / "New context"                                                                                                      | `chat.contextWarning.sheet.currentLabel` / `nextLabel` | only place raw n_ctx surfaces to the user |
| Sheet reload hint                         | "Reloading the model takes a few seconds."                                                                                             | `chat.contextWarning.sheet.reloadHint`    | duration-agnostic (empirical 1.5–12s)            |
| Sheet success snackbar                    | "Context increased."                                                                                                                   | `chat.contextWarning.sheet.successSnackbar` |                                                |
| Sheet failure snackbar                    | "Couldn't increase context. Reverted."                                                                                                 | `chat.contextWarning.sheet.failureSnackbar` |                                                |
| Reload-in-flight snackbar                 | "Reloading with a larger context…"                                                                                                     | `chat.contextWarning.reloadingSubcopy`    | `Snackbar.DURATION_INDEFINITE`, dismissed on success/fail |
| `palLoadHint` snackbar message (α)        | "This pal works better with more context."                                                                                             | `chat.contextWarning.palLoadHint.message` | one-shot per (palId, n_ctx) per session          |
| `palLoadHint` action (fits memory)        | "Increase context"                                                                                                                     | `chat.contextWarning.palLoadHint.increase` | reuses §4h `IncreaseContextSheet`                |
| `palLoadHint` action (no tier fits)       | "Start new chat"                                                                                                                       | `chat.contextWarning.palLoadHint.newChat` | reuses §4h memory-aware fallback                 |

`chat.softCapWarning` ("Start a new chat for best performance.") stays at `src/locales/en.json:1104` — the resolver's `html-soft-cap` variant maps to it (§A.1.4 below).

### A.1.3 `softCapWarning` fate

Kept verbatim. Resolver's `'html-soft-cap'` branch returns this existing key. Rationale: avoids a Weblate churn of all 8 integrated languages for a string whose semantics haven't changed (still "5+ HTML previews — memory hint").

## A.2 Worked-example traces (dismiss / recovery / precedence)

### Trace 1 — warning → dismiss → return → full → recovery → clear

Pre-condition: default `n_ctx=2048`, local engine, `render_html` enabled. WHAT §4d governs every clear.

1. turn 1: `used = 0 + 100 + 20 = 120`, ratio 0.06 → `none`.
2. turn 2: `used = 50 + 700 + 200 = 950`, ratio 0.46 → `none`.
3. turn 3 (paste ~1200 tok doc): `used = 100 + 1500 + 200 = 1800`, ratio 0.88 → `context-warning` shows.
4. user taps Dismiss → `dismissedBannerVariants.add('<sid>:context-warning')` → resolver → `none`.
5. turn 4: `run_finished` writer clears `dismissedBannerVariants` for `<sid>` (WHAT §5); turn returns `context_full=true` → `snap.contextFull=true`, `consecutiveFullFailures=1` → `context-full` (sticky, no Dismiss button).
6. user taps Increase context → tier picker → 4096 fits memory → `IncreaseContextSheet` → confirm → `sessionContextOverrides.set(sid, 4096)` → `releaseContext → initContext` → success snackbar.
7. turn 5: `used = 100 + 1500 + 200 = 1800 < 4096 − 32 = 4064` AND no §4a match → I3 atomic swap to `contextFull=false`, `consecutiveFullFailures=0` → ratio 0.44 → `none`.

### Trace 2 — escalation (2 consecutive failures)

1. turn N: §4a matches → `consecutiveFullFailures=1`, copy `chat.contextWarning.full.*`.
2. turn N+1: user ignores banner, §4a matches again → counter=2 → copy switches to `chat.contextWarning.fullEscalated.*`. Same shell, same CTAs, same precedence (WHAT §4d, D7).
3. turn N+2: user taps Increase context → 8192 → next turn satisfies §4a no-match + I3 → counter resets to 0, variant → `none`.

### Trace 3 — precedence vs HTML soft-cap (WHAT §4c, Scenario I)

State: `htmlPreviewCount=5`, `snap={tokensCached:0, tokensEvaluated:1500, tokensPredicted:200, contextFull:false, finishReason:'eos'}`, `effectiveNCtx=2048`, ratio 0.83, local session.

1. resolver order: `context-full` no → `context-warning` YES (short-circuits) → variant = `context-warning`. Soft-cap silenced.
2. user dismisses `context-warning` → resolver re-runs: `context-warning` gated by Set → `context-remote-hedged` no (local) → `html-soft-cap` YES → banner SWITCHES copy.
3. soft-cap also dismissible (per-draft, same gate keyed by `<sid>:html-soft-cap`).
4. on next `run_finished` → Set cleared → resolver picks whichever still matches.

**I4 visual confirmation**: only one banner ever renders. The resolver short-circuits.

### Trace 4 (β heavy-talent post-fail sub-copy)

Pre-condition: `n_ctx=4096`, local engine, `render_html` declares `recommendedContextTokens=4096`.

1. assistant_turn produces `steps[0].tool_calls[0].function.name='render_html'`; result `context_full=true` → `snap.contextFull=true` → variant = `context-full`.
2. resolver scans `messages[0].steps[].tool_calls[].function.name` against `talentRegistry`; finds `render_html` declaring `recommendedContextTokens` → copy key swaps to `chat.contextWarning.fullHeavyTalent.*` with `{talentName: 'render_html'}` placeholder.
3. variant identity unchanged (still `'context-full'`, I4 preserved, D16). Shell, dismissibility (sticky, no Dismiss), CTAs (Increase context / New chat) all unchanged.

## A.3 Reload UX timeline

`releaseContext → initContext` on a warm-loaded model is empirically 1.5–4s on iPhone 13 Pro / Pixel 9 / iPhone SE 2; worst case ~8–12s on large 7B at big n_ctx jumps. Reload subcopy stays duration-agnostic.

Subcopy is delivered as a **snackbar** at CTA tap, not as text on the loading-model screen (WHAT §3 forbids new states; the existing loading-model screen is shared with multiple paths and is not safe to mutate).

- t0: user taps "Increase context" → confirm sheet appears.
- t1: user taps "Increase" → sheet dismisses; `sessionContextOverrides.set(sid, target)`; snackbar fires `reloadingSubcopy` with `Snackbar.DURATION_INDEFINITE`.
- t2: `modelStore.releaseContext()` runs → existing `loadingModel` overlay covers chat surface (WHAT §3, no new state).
- t3: `modelStore.initContext(model)` runs → `getEffectiveContextInitParams` reads `sessionContextOverrides[sid]=target` (I5) → native context inits at `target`.
- t4 success: `isContextLoading=false` → reload snackbar dismissed → success snackbar (`sheet.successSnackbar`) fires (default duration). `snap` unchanged from before reload; if previous variant was `context-full`, banner MAY STILL SHOW until the next finished turn proves headroom (Scenario J, intended UX).
- t4 failure: `initContext` rejects → revert `sessionContextOverrides` to prior (delete if absent before) → reload snackbar dismissed → failure snackbar (`sheet.failureSnackbar`) fires. PRIOR context was released; chat surface falls back to `ModelNotLoadedMessage` (existing path) until the user reloads.

## A.4 Hedged remote variant — dismissibility refinement

WHAT §4d codifies the variant as **per-draft dismissible AND reactively cleared on the next non-§4e remote turn**. Rationale: the §4e heuristic is a weak signal (all-four heuristic) and forcing non-dismissibility on uncertain signals is the wrong posture — per-draft dismiss costs nothing because the variant re-derives every render and would clear on the next remote turn anyway. Action set: **Dismiss only** — no Increase context CTA (we don't own the remote n_ctx), no New chat CTA (the next remote chat has the same n_ctx).

## A.5 Three pinned decisions

| Decision                 | Value                                       | One-line rationale                                                                                                                                          |
|--------------------------|---------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `WARNING_THRESHOLD`      | **0.80** (named export, resolver module)    | At `n_ctx=2048` gives ~410 token runway = one average follow-up turn; 0.75 fires too early on short chats, 0.85 fires too late to be actionable. Pinned per WHAT D11. |
| Snapshot vs live tracking | **snapshot-at-turn-boundary** (WHAT D13)    | Live tracking would defeat MobX memoization (re-derive per token), contradict §7h ("banner reflects PRIOR turn's state"), and require a fourth observable. Brief asked to verify — verified.    |
| First-time `render_html` warn | **reactive after firing** (WHAT D14) + **α pal-load hint mitigant** | Predictive talent-aware thresholds were rejected (3-round deliberation). α amendment mitigates the reactive-first-tool gap with a one-shot pal-load snackbar — declarative-only (`recommendedContextTokens`), no per-turn talent inspection.     |

---

# §B. Plumbing worklist

Tight by design — design is settled in WHAT. Each step references the WHAT section it executes.

## Affected files

| Path | Change kind | WHAT reference |
|---|---|---|
| `src/store/ChatSessionStore.ts` | edit | §1a, §1c, §1f, §5, I7 |
| `src/hooks/useChatSession.ts` | edit (writer extension on `run_finished` + abort-catch) | §1a, §1b, §5, I7 |
| `src/store/ModelStore.ts` | edit (`getEffectiveContextInitParams` cross-store read) | §5, I5 |
| `src/components/ChatView/ChatView.tsx` | edit (resolver-driven banner + CTA + tier picker memo) | §4c, §4g, §4h, D9 |
| `src/components/ChatView/styles.ts` | edit (additive variant tokens; shell unchanged) | §4g, D9 |
| `src/utils/bannerVariantResolver.ts` | add (resolver + helpers + types + β scan) | §4a–§4e, §1a, §1e |
| `src/utils/__tests__/bannerVariantResolver.test.ts` | add | §6 A–I, P |
| `src/components/IncreaseContextSheet/{IncreaseContextSheet.tsx,styles.ts,index.ts}` | add | §4h |
| `src/components/IncreaseContextSheet/__tests__/IncreaseContextSheet.test.tsx` | add | §6 J/K |
| `src/store/__tests__/ChatSessionStore.test.ts` | edit (snapshot, dismiss, override, hint set tests) | §1a, §1c, §1f, §4d, §5 |
| `src/hooks/useMemoryCheck.ts` | edit (add `hasEnoughMemoryWithNCtx(model, nCtx)` wrapper) | §4h step 1 |
| `src/hooks/usePalLoadHint.ts` | add (α pal-load detector, snackbar trigger, suppression gate) | §1e, §1f, §4i, I8 |
| `src/services/talents/types.ts` | edit (add `recommendedContextTokens?` on `TalentEngine`) | §1e |
| `src/services/talents/RenderHtmlEngine.ts` | edit (declare `recommendedContextTokens: 4096`) | §1e |
| `src/locales/en.json` | edit (new `chat.contextWarning.*` keys; keep `chat.softCapWarning`) | §A.1 |
| `context/architecture/chat-flow.md` | edit (absorb delta; repair §5 line 415; add §4i row) | §5 |
| `context/architecture/pals-and-talents.md` | edit (one line for `recommendedContextTokens?`) | §1e |

`CompletionResultSnapshot` type is co-located in `src/utils/bannerVariantResolver.ts` — the single domain owner of the snapshot shape.

## Implementation steps

### Step 1: Verify `finish_reason → CompletionResult` adapter

| Field | Value |
|---|---|
| Implements | WHAT §4a #4, §4e gating |
| Files | none (verification only) |
| Approach | Confirm `src/api/openai.ts:611-628` maps: `'length'` → `stopped_limit=1`; `'content_filter'` → `interrupted=true`; `'stop' \| 'tool_calls'` → `stopped_eos=true`. Any future divergence becomes a contract violation that Step 4's resolver will catch. |
| Risk | none — read-only |
| Verification | `yarn test --findRelatedTests src/api/openai.ts` green (existing tests at lines 503-540 already cover the mapping) |

### Step 2: `run_finished` writer extension (snapshot + persisted metadata)

| Field | Value |
|---|---|
| Implements | WHAT §1a, §1b, §5, I7 |
| Files | `src/hooks/useChatSession.ts` (`run_finished` ≈line 323; abort-catch ≈line 670); `src/utils/bannerVariantResolver.ts` (export `deriveSnapshotFromResult` helper) |
| Approach | (a) Helper `deriveSnapshotFromResult(result, truncationLikely): CompletionResultSnapshot` co-located in `bannerVariantResolver.ts`; implements §4a OR predicate + §1a derivation table; `tokensCached = result.tokens_cached ?? 0`. (b) In `run_finished` after existing `updateMessage`, call helper with `truncationLikely=false`; extend the same `metadata` payload to additionally carry `completionResult: snapshot` (additive to existing `content`/`reasoning_content`). (c) In same MobX action, write to `chatSessionStore.lastCompletionResult` and increment / reset `consecutiveFullFailures` per §4d. (d) Abort-catch path: when `hasPartialContent=true`, compute snapshot from partial data (force `contextFull=true` when `isToolArgsParseError`, per §4a #3); when `hasPartialContent=false`, do NOT touch `lastCompletionResult` (§7a). |
| Risk | metadata shape change touched by PlayButton/TTS readers — additive only; preserved fields (`content`, `reasoning_content`) untouched |
| Verification | `yarn lint`, `yarn typecheck` pass; `yarn test --findRelatedTests src/hooks/useChatSession.ts` passes |
| Tests | Scenarios A, C, D, E, F, P (resolver side via snapshot input); abort-catch path covered in Step 10 store tests |

### Step 3: `ChatSessionStore` state additions + hydration

| Field | Value |
|---|---|
| Implements | WHAT §1a, §1c, §1f, §2, §5, I7 |
| Files | `src/store/ChatSessionStore.ts` |
| Approach | Add observables: `lastCompletionResult: CompletionResultSnapshot \| null = null`, `sessionContextOverrides: Map<string, number> = new Map()`, `dismissedBannerVariants: Set<string> = new Set()`, `consecutiveFullFailures: number = 0`, `palLoadHintSeen: Set<string> = new Set()`. Setters (single writers per §5): `setLastCompletionResult`, `setBannerDismissed(sid, variant)`, `clearBannerDismissalsForSession(sid)`, `setSessionContextOverride(sid, nCtx)`, `clearSessionContextOverride(sid)`, `incrementConsecutiveFullFailures` / `resetConsecutiveFullFailures`, `markPalLoadHintSeen(palId, nCtx)`. Hydration: (a) `setActiveSession(sid)` after lazy-load reads most recent assistant message; if `metadata.completionResult` has snapshot fields, seed `lastCompletionResult`, else `null`; reset counter and clear dismiss set. (b) `resetActiveSession()` clears `lastCompletionResult`, counter, dismiss set, AND `palLoadHintSeen` (§1f). (c) `deleteSession(id)` also calls `clearSessionContextOverride(id)`. |
| Risk | MobX Map mutations trigger reactions in MobX 6 — confirmed via `makeAutoObservable` |
| Verification | `yarn test --findRelatedTests src/store/ChatSessionStore.ts` passes |
| Tests | scenarios L, M, N, O, plus single-writer assertions per §5 |

### Step 4: Resolver module (pure) + β heavy-talent scan

| Field | Value |
|---|---|
| Implements | WHAT §4a–§4e, §4f, §1a, §1e (β branch), D11 |
| Files | `src/utils/bannerVariantResolver.ts` (new) |
| Approach | Single pure module. Type + predicate code below. **Text extraction**: `lastAssistantText` is derived at the call site via `derivedText(message)` from `src/utils/chat.ts:32` — the codebase's single domain-owner of "final visible content" for assistant messages (concatenates step contents with `\n\n`; trailing char is the last non-empty step's last char, exactly what §4e #4 asks about). **β scan** lives inside the resolver: when variant resolves to `context-full`, scan `messages[0].steps[].tool_calls[].function.name` (only if `messages[0]` is an `assistant_turn`) against `talentRegistry.get(name)?.recommendedContextTokens`; if any matched engine declares the field, return `{ kind: 'context-full', escalated, nextTierTokens, heavyTalent: { name } }`. Caller maps `heavyTalent.name !== undefined` to `chat.contextWarning.fullHeavyTalent.*` copy key with `{talentName}` placeholder. **Async memory check stays at caller** — resolver receives pre-computed `nextTierTokens` from `useEffect`-driven `pickNextTier`. |
| Risk | resolver purity must be preserved — no MobX writes, no async, no JSX |
| Verification | `yarn typecheck` passes; resolver tests in Step 10 |
| Tests | Scenarios A, B, C, D, E, F, G, H, I, P |

Type and predicate code:

```ts
export const WARNING_THRESHOLD = 0.80;   // D11, §A.5
export const AUTOCLEAR_RUNWAY  = 32;     // D4

export type FinishReason = 'length' | 'stop' | 'eos' | 'content_filter' | 'unknown';

export type CompletionResultSnapshot = {
  tokensCached:    number;   // result.tokens_cached ?? 0
  tokensEvaluated: number;   // result.tokens_evaluated ?? 0
  tokensPredicted: number;   // result.tokens_predicted ?? 0
  contextFull:     boolean;
  finishReason:    FinishReason;
};

export type BannerVariant =
  | { kind: 'context-full'; escalated: boolean; nextTierTokens: number | null; heavyTalent: { name: string } | null }
  | { kind: 'context-warning'; nextTierTokens: number | null }
  | { kind: 'context-remote-hedged' }
  | { kind: 'html-soft-cap' }
  | { kind: 'none' };

// §4b used-budget predicate (β amendment threads tokensCached):
const used = snap.tokensCached + snap.tokensEvaluated + snap.tokensPredicted;
const ratio = used / nCtx;
const warning = !snap.contextFull && ratio >= WARNING_THRESHOLD;
const autoClear = used < nCtx - AUTOCLEAR_RUNWAY;
```

`effectiveNCtx(sessionId)` is a co-located helper exported from the same module — used by both the resolver AND `getEffectiveContextInitParams` (Step 5), keeping the precedence rule (override > base) in one place.

### Step 5: `getEffectiveContextInitParams` cross-store read

| Field | Value |
|---|---|
| Implements | WHAT §5, I5 |
| Files | `src/store/ModelStore.ts` (~line 419-478) |
| Approach | Replace line 423 `const effectiveContext = this.contextInitParams.n_ctx;` with `effectiveNCtx(chatSessionStore.activeSessionId)` from the resolver module. The helper reads `sessionContextOverrides.get(sid)` first, falls back to `this.contextInitParams.n_ctx`. Import direction is one-way `ModelStore → ChatSessionStore` (no cycle: `ChatSessionStore` does not import `ModelStore`). |
| Risk | circular-import — confirmed not introduced; `ChatSessionStore` already independent of `ModelStore` |
| Verification | `yarn typecheck`; targeted test asserting override flows through |
| Tests | Scenario J (success path uses I5 silently); §7c (background eviction) |

### Step 6: Replace `htmlPreviewCount`-only banner with resolver-driven variant render

| Field | Value |
|---|---|
| Implements | WHAT §4c, §4g, §4h, I4, D9 |
| Files | `src/components/ChatView/ChatView.tsx` (~lines 1023-1079); `src/components/ChatView/styles.ts` (~lines 85-97, additive only) |
| Approach | (a) Keep `htmlPreviewCount` `useMemo` (feeds resolver). (b) Delete `showSoftCapWarning` boolean (line 1047). (c) Destructure from `chatSessionStore`: `lastCompletionResult` (as `snap`), `dismissedBannerVariants`, `consecutiveFullFailures`, `activeSessionId`. (d) Compute `effectiveNCtxForSession = effectiveNCtx(activeSessionId)`. (e) `isRemoteSession = modelStore.activeModel?.origin === ModelOrigin.REMOTE`. (f) `lastAssistantMsg = messages.find(m => m.type === 'assistant_turn' \|\| m.type === 'text')` (newest-first per `ChatView.tsx:740`); `lastAssistantText = lastAssistantMsg ? derivedText(lastAssistantMsg) : ''`. (g) `nextTierTokens` via `useEffect` calling `pickNextTier(effectiveNCtxForSession, modelStore.activeModel)` (Step 8). (h) Call `resolveBannerVariant({...})`. (i) Replace JSX at 1073-1079 with a single `<BannerRow variant={variant} l10n={l10n} onIncrease={...} onDismiss={...} onNewChat={...} />` (inline component, ~30 lines, proximity preferred). Five renders: `'none'` → null; `'html-soft-cap'` → existing `l10n.chat.softCapWarning` + Dismiss; `'context-warning'` → title + msg + Increase + Dismiss; `'context-full'` (+ `escalated` / `heavyTalent` flags) → title + msg + Increase + New chat, NO Dismiss (D6); `'context-remote-hedged'` → title + msg + Dismiss only (§A.4). |
| Risk | I4 (one banner) — guaranteed by resolver short-circuit |
| Verification | `yarn lint`, `yarn typecheck`, `yarn test --findRelatedTests src/components/ChatView/ChatView.tsx`; VISUAL_CAPTURES |
| Tests | Scenarios A–I, P (via resolver tests); J/K via sheet tests; visual via VISUAL_CAPTURES |

Style additions (additive only — shell unchanged, D9):

```ts
bannerTitle: { fontSize: 12, fontWeight: '600', color: theme.colors.onSurfaceVariant },
bannerActions: { flexDirection: 'row', gap: 8, justifyContent: 'flex-end' },
bannerButton: { /* RNP Button compact */ },
// backgroundColor stays theme.colors.surfaceVariant — variant identity from copy, not chrome
```

### Step 7: l10n keys

| Field | Value |
|---|---|
| Implements | §A.1.2 |
| Files | `src/locales/en.json` (~line 1104, after `softCapWarning`) |
| Approach | Add the `chat.contextWarning.*` tree per §A.1.2 (all keys including `palLoadHint.*` and `fullHeavyTalent.*`). Keep `chat.softCapWarning` unchanged. Do NOT edit other-language locale files — l10n CI uploads `en.json` to Weblate; missing keys fall back via `_.merge` overlay. |
| Risk | placeholder consistency — `{talentName}` in `fullHeavyTalent.message` validated by `validate-l10n.js` |
| Verification | `yarn validate-l10n`; `yarn typecheck` (TS derives keys from `typeof en`); manual: set language to each of 8 integrated languages, confirm friendly copy renders on iPhone SE without truncation |
| Tests | n/a (string file; coverage via banner visual tests) |

### Step 8: Increase context CTA + sheet + reload UX

| Field | Value |
|---|---|
| Implements | WHAT §4h, §A.3 |
| Files | `src/components/IncreaseContextSheet/{IncreaseContextSheet.tsx,styles.ts,index.ts}` (new); `src/hooks/useMemoryCheck.ts` (add `hasEnoughMemoryWithNCtx(model, nCtx)` wrapper); `src/components/ChatView/ChatView.tsx` (CTA handler + snackbar) |
| Approach | (a) Sheet built on existing `Sheet` primitive (`src/components/Sheet/Sheet.tsx`); shape mirrors `ChatGenerationSettingsSheet` — `BottomSheetModalMethods` ref, `forwardRef`, `present()` / `dismiss()`. Content: title, body, Current/New context row (only place raw n_ctx surfaces), reload hint, Confirm / Cancel. (b) `pickNextTier(currentNCtx, model)`: iterate `TIERS = [2048, 4096, 8192, 16384, 32768]`, skip ≤ current, return first `t` where `hasEnoughMemoryWithNCtx(model, t) === true`; null if none fit. (c) `hasEnoughMemoryWithNCtx` is a new wrapper around `useMemoryCheck.hasEnoughMemory` that accepts an explicit n_ctx (no store mutation — cleaner than swap/restore). (d) CTA handler in `ChatView`: snapshot prior override, write new, fire indefinite reloading snackbar, await `releaseContext` then `initContext`; on success dismiss reloading + show `successSnackbar`; on failure revert override + show `failureSnackbar`. (e) I6 guard: Increase context button `disabled` when `isGenerating \|\| isStopping`. (f) "New chat" CTA on `context-full` calls existing `chatSessionStore.resetActiveSession()`. (g) Snackbar pattern: local `Portal + Snackbar` in `ChatView` matching `ModelsScreen` style. |
| Risk | initContext rejection path leaves PRIOR context released → chat surface falls back to existing `ModelNotLoadedMessage` (existing recovery path; no new UI) |
| Verification | `yarn lint`, `yarn typecheck`, `yarn test --findRelatedTests src/components/IncreaseContextSheet`; manual J / K via VISUAL_CAPTURES |
| Tests | Scenarios J, K; I6 guard test; `nextTierTokens=null` → confirm disabled |

### Step 9: α pal-load hint snackbar + `TalentEngine.recommendedContextTokens`

| Field | Value |
|---|---|
| Implements | WHAT §1e, §1f, §4i, I8 |
| Files | `src/services/talents/types.ts` (add `recommendedContextTokens?: number` on `TalentEngine`); `src/services/talents/RenderHtmlEngine.ts` (declare `recommendedContextTokens: 4096`); `src/hooks/usePalLoadHint.ts` (new — detector + snackbar trigger); `src/components/ChatView/ChatView.tsx` (mount the hook); `src/store/ChatSessionStore.ts` (already adds `palLoadHintSeen` Set in Step 3) |
| Approach | (a) `TalentEngine` gains one optional field; `CalculateEngine` and `DatetimeEngine` omit. (b) `usePalLoadHint()` is a hook that observes `(activePal, modelStore.context, pal.pact.talents, effectiveNCtxForSession)`. Pure predicate: `palNeedsMoreRoom = activePal.pact.talents.some(t => talentRegistry.get(t.name)?.recommendedContextTokens > effectiveNCtx(sid))`. Edge moments: pal load (active pal change), model load (`modelStore.context` becomes available), talent-set change. (c) On flip `false→true` AT one of those edges AND `palLoadHintSeen` does NOT contain `${pal.id}:${effectiveNCtx(sid)}` → emit ONE snackbar. Insert key at emit time regardless of user action (one-shot). (d) Snackbar action label: `await pickNextTier(currentNCtx, model)`; if a tier fits → "Increase context" → tapping opens the **same** `IncreaseContextSheet` from §4h with the SAME confirm action; if no tier fits → "Start new chat" → tapping calls `chatSessionStore.resetActiveSession()` (SAME memory-aware fallback as §4h J/K). (e) I8: hint is a snackbar (transient), NOT a banner — does not enter §4c precedence; banner singleton preserved. (f) `palLoadHintSeen` cleared on `resetActiveSession` (Step 3). |
| Risk | edge-trigger reliability — `useEffect` on the four deps catches each edge; key is `${palId}:${n_ctx}` so user lowering n_ctx later re-opens a fresh fire opportunity (correct semantically). |
| Verification | `yarn lint`, `yarn typecheck`, `yarn test --findRelatedTests src/hooks/usePalLoadHint.ts src/services/talents/RenderHtmlEngine.ts`; manual: load render_html pal at `n_ctx=2048` → snackbar fires; tap CTA → §4h sheet opens; reload pal at 2048 → suppressed (Scenario O) |
| Tests | Scenarios N, O (suppression), §7j (no-fit → "Start new chat") |

### Step 10: Tests

| Field | Value |
|---|---|
| Implements | WHAT §6 scenarios A–P |
| Files | `src/utils/__tests__/bannerVariantResolver.test.ts` (new); `src/store/__tests__/ChatSessionStore.test.ts` (edit); `src/components/IncreaseContextSheet/__tests__/IncreaseContextSheet.test.tsx` (new); `src/hooks/__tests__/usePalLoadHint.test.ts` (new) |
| Approach | One test file per layer; each maps to a WHAT scenario. `deriveSnapshotFromResult` block: one test per §1a derivation row plus one per §4a OR-arm. Resolver block uses fixture builders for `CompletionResultSnapshot` and `AssistantTurn`. |
| Risk | tokensCached threading — every resolver test must include `tokensCached` in snap fixtures, otherwise `used` math is wrong |
| Verification | `yarn test --findRelatedTests src/utils/bannerVariantResolver.ts src/store/ChatSessionStore.ts src/components/IncreaseContextSheet src/hooks/usePalLoadHint.ts` all pass |
| Tests | full scenario coverage table below |

### Step 11: Architecture docs absorption (chat-flow + pals-and-talents)

| Field | Value |
|---|---|
| Implements | absorbs WHAT delta in same PR |
| Files | `context/architecture/chat-flow.md`; `context/architecture/pals-and-talents.md` |
| Approach | (a) `chat-flow.md` §1 metadata block (lines 24-29): tighten `completionResult?` to the §1b shape including `tokensCached`. (b) §4d component table: add row for banner shell ("ONE of five variants from `bannerVariantResolver`"). (c) §5 single-writer table: REPLACE line 415 with the §5 rows from WHAT including the new `lastCompletionResult` / `dismissedBannerVariants` / `consecutiveFullFailures` / `sessionContextOverrides` / `palLoadHintSeen` rows. (d) Add cross-store-read paragraph documenting one-way `ModelStore → ChatSessionStore` read with I5 named. (e) Add §4i pal-load hint row (snackbar, I8 layering note). (f) Cleanup-LANDED entry at §5 bottom: "`metadata.completionResult` shape + writer (was drift from TASK-20260504-2320). Resolved in TASK-20260526-2259." (g) `pals-and-talents.md`: one line on `TalentEngine` schema gaining `recommendedContextTokens?: number` (optional; `RenderHtmlEngine` declares `4096`; declarative-only — does NOT drive per-turn behaviour). Convert all (P) markers from WHAT to (C); leave (D) as (D); confirm zero (?). |
| Risk | drift between WHAT and architecture doc — addressed by absorbing in same PR (Non-Negotiable) |
| Verification | architect re-reads docs; zero (?) markers; cross-link from `chat-flow.md` §5 → `pals-and-talents.md` for `TalentEngine` extension |
| Tests | n/a (doc) |

---

## Testable-contract coverage

Every WHAT §6 scenario (A–P) maps to a test or manual verification:

| Scenario | Verified by |
|---|---|
| §6.A — fresh local chat | `bannerVariantResolver.test`: "no snapshot → variant none" |
| §6.B — local 80% | `bannerVariantResolver.test`: "tokensCached+evaluated+predicted ratio ≥ 0.80 local !contextFull → context-warning" |
| §6.C — context_full local | `bannerVariantResolver.test`: "snap.contextFull → context-full" |
| §6.D — tool-args parse failure | `bannerVariantResolver.test`: "truncationLikely → contextFull=true → context-full" + `ChatSessionStore.test`: abort-catch writer |
| §6.E — auto-clear | `bannerVariantResolver.test`: "used < nCtx-32 && !§4a → contextFull cleared (I3)" — fixture threads `tokensCached` |
| §6.F — remote length-finish | `bannerVariantResolver.test`: "remote stopped_limit → context-full" |
| §6.G — remote weak-signal | `bannerVariantResolver.test`: "remote all-4 → context-remote-hedged" |
| §6.G § 4e #4 extraction | `bannerVariantResolver.test`: "AssistantTurn last step ends mid-sentence → hedge fires" + "concatenated steps preserve trailing char" |
| §6.H — remote short answer | `bannerVariantResolver.test`: "remote tokens_predicted<500 → none" |
| §6.I — collision with HTML soft-cap | `bannerVariantResolver.test`: "context-warning beats html-soft-cap"; "dismissed warning falls through to soft-cap" |
| §6.J — Increase context success | `IncreaseContextSheet.test`: "confirm → releaseContext + initContext + success snackbar" + VISUAL_CAPTURE `increase-context-success` |
| §6.K — Increase context failure | `IncreaseContextSheet.test`: "initContext rejection reverts override + failure snackbar" + VISUAL_CAPTURE `increase-context-failure` |
| §6.L — session-switch hydration | `ChatSessionStore.test`: "setActiveSession hydrates lastCompletionResult from metadata.completionResult" |
| §6.M — cold app launch | `ChatSessionStore.test`: "process restart: sessionContextOverrides empty Map, lastCompletionResult hydrates from disk" |
| §6.N — pal-load hint fires at 2048 (α) | `usePalLoadHint.test`: "render_html pal at n_ctx=2048 → snackbar"; "render_html pal at n_ctx=8192 → no snackbar" |
| §6.O — pal-load hint suppression (α) | `usePalLoadHint.test`: "second pal-load at same (palId, n_ctx) → palLoadHintSeen gate → no snackbar" |
| §6.P — heavy-talent post-fail copy (β) | `bannerVariantResolver.test`: "context-full + assistant_turn called render_html → heavyTalent={name:'render_html'} on variant → caller uses `fullHeavyTalent` copy key" |
| §4d escalation | `bannerVariantResolver.test`: "consecutiveFullFailures ≥ 2 → escalated flag" |
| §7j — no-fit memory fallback (α) | `usePalLoadHint.test`: "no tier fits → snackbar action label 'Start new chat'" |
| §7a — abort with no partial content | `ChatSessionStore.test`: "abort-catch hasPartialContent=false → lastCompletionResult unchanged" |
| §7c — background eviction | `ModelStore.test`: "getEffectiveContextInitParams reads sessionContextOverrides silently after release+init" |

---

## Visual Confirmation (Visual Confirmation=YES)

```json
[
  {
    "label": "context-warning-local",
    "prompt": "(paste a ~1200-token document) Summarize the key points.",
    "look_for": "Banner above the chat input: title 'This chat is filling up.' message 'Replies may start getting cut off.' with buttons 'Increase context' and 'Dismiss'. Same chrome as the existing soft-cap banner."
  },
  {
    "label": "context-warning-dismiss",
    "prompt": "(dismiss the warning banner from the previous step, then send 'okay, continue')",
    "look_for": "Banner disappears on dismiss; reappears (or NOT, if the new turn cleared the ratio) after run_finished. Confirms per-draft dismiss."
  },
  {
    "label": "context-full-local-render-html",
    "prompt": "(default 2048 n_ctx) Make me an HTML page showing a CSS grid of 20 colors with names.",
    "look_for": "Banner: 'Chat reached its memory limit.' 'The model can't fit any more of this conversation. Increase context or start a new chat.' Buttons 'Increase context' and 'New chat'. NO Dismiss button."
  },
  {
    "label": "context-full-heavy-talent-subcopy",
    "prompt": "(same context as above; default 2048 n_ctx; render_html declared recommendedContextTokens=4096)",
    "look_for": "Banner message switches to the heavy-talent sub-copy: '{talentName} needs more room than this chat has. Increase context or start a new chat.' with talentName resolved to 'render_html'. Same shell, same CTAs."
  },
  {
    "label": "context-full-escalated",
    "prompt": "(after the context-full banner shows, send another message:) try again.",
    "look_for": "Banner title escalates to 'Still at the memory limit.' with the more directive message. Same CTAs."
  },
  {
    "label": "increase-context-success",
    "prompt": "(tap 'Increase context' on the banner; confirm the sheet)",
    "look_for": "Sheet shows current/new context (e.g. 2048 → 4096). After Increase: brief loading-model overlay, then chat returns. Snackbar 'Context increased.' Chat history preserved."
  },
  {
    "label": "increase-context-failure",
    "prompt": "(force-fail initContext via a model too large; tap Increase context)",
    "look_for": "Snackbar 'Couldn't increase context. Reverted.' PRIOR context released → ModelNotLoadedMessage; after reload, banner unchanged."
  },
  {
    "label": "pal-load-hint-fires",
    "prompt": "(load a pal whose pact.talents includes render_html, with default 2048 n_ctx)",
    "look_for": "On pal load (or model load completing), a snackbar appears: 'This pal works better with more context.' with action 'Increase context'. Tapping opens the same IncreaseContextSheet as the banner CTA."
  },
  {
    "label": "pal-load-hint-no-fit",
    "prompt": "(on a low-RAM device where no tier > current n_ctx fits, load the same pal)",
    "look_for": "Snackbar action label is 'Start new chat' (memory-aware fallback). Tapping starts a new session."
  },
  {
    "label": "pal-load-hint-suppressed",
    "prompt": "(after dismissing the hint, re-open the same pal at the same n_ctx)",
    "look_for": "Snackbar does NOT re-fire (palLoadHintSeen gate). Process restart clears the gate."
  },
  {
    "label": "remote-hedged",
    "prompt": "(remote OpenAI-compatible session) Write me a 1000-word essay on the history of typewriters.",
    "look_for": "If response is long (>500 tokens) AND not terminal-punctuated AND finish_reason != 'length': banner 'Reply may be cut off.' 'You may be near the model's context limit on the server.' with Dismiss only. NO Increase context CTA."
  },
  {
    "label": "softcap-still-works",
    "prompt": "(generate 5 HTML previews by repeatedly asking 'make me another HTML page')",
    "look_for": "Once htmlPreviewCount ≥ 4 AND no context-warning/full active, banner shows legacy 'Start a new chat for best performance.' (chat.softCapWarning preserved)."
  },
  {
    "label": "rtl-hebrew",
    "prompt": "(set app language to Hebrew; trigger context-warning)",
    "look_for": "Banner renders RTL with Hebrew copy. Button order mirrored. Text not clipped at iPhone SE width."
  },
  {
    "label": "ja-zh-narrow-width",
    "prompt": "(set app language to Japanese, then Chinese, iPhone SE simulator; trigger each variant)",
    "look_for": "Title/message wrap to 2-3 lines max; no horizontal overflow; CTAs on a single bottom row."
  }
]
```

---

## Deferred items

Anything WHAT defers stays deferred:

- Per-pal `contextSizeOverride` field on the Pal record (intent-brief caveat #2; follow-up once telemetry shows repeat-override patterns).
- Known-provider context-window registry for pre-emptive remote warnings.
- Live during-stream tracking (WHAT D13 pins snapshot).
- Heads-up vs critical two-tier banner variants (persistence-as-state IS the "critical" tier).
- Talent-aware predictive thresholds at the variant resolver level (declarative-only via α + β; predictive deliberation-rejected).
- Pal-edit chip / discoverability surfaces outside the banner.
- Backfill of legacy sessions without `metadata.completionResult` (WHAT D12).
- Chat-flow.md state-signal consolidation (`inferencing` / `isStreaming` / `isGenerating` / `isGeneratingToolCall`).

---

## What this plan is NOT

- not the design doc — design is in `what.md`
- not a re-litigation of the 3-round deliberation
- not exhaustive on plumbing — steps reference WHAT rather than re-derive it

---

## Review history

See `./deliberation-log.md` for R1 plan-critic CONCERNS (resolved), R2 plan-critic LGTM, R3 amendment absorption (α + β + tokens_cached correction).
