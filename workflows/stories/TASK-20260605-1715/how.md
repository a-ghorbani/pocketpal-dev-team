# Implementation Plan: Chat context-limit banner + recovery + pal-load hint

Executable worklist for `what.md`. Section refs (§1, §4a, I2…) point at WHAT; do
not re-derive design. If a step needs a decision not in WHAT, STOP → architect.

---

## Metadata

- **Task ID**: TASK-20260605-1715
- **Worktree**: `./worktrees/TASK-20260605-1715`
- **Branch**: `feature/TASK-20260605-1715`
- **Native Changes**: NO
- **Visual Evidence Required**: YES
- **Intent Brief**: `./workflows/stories/TASK-20260605-1715/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260605-1715/what.md`
- **Architecture doc(s)**: `./context/architecture/chat-flow.md`, `./context/architecture/pals-and-talents.md`
- **Status**: implemented

---

## Progress

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| 1 types | DONE | b4ed32a | CompletionResultSnapshot, BannerVariant, recommendedContextTokens |
| 2 store fields + clears | DONE | 87ba0dd | 4 ephemeral fields + setters + clear/hydrate triggers + mock |
| 3 paired writer | DONE | dbec744 | deriveSnapshotFromResult + recordCompletionSnapshot at both boundaries |
| 4 resolver + memory gate | DONE | 62932f6 | resolveBannerVariant + computeNextFitNCtx via canFitNCtx; 20 unit tests |
| 5 BannerRow + I10 | DONE | c749137, 91fdf3f | footer suppression + BannerRow in soft-cap slot |
| 6 IncreaseContextSheet | DONE | 91fdf3f | confirm + reload + restore-on-failure; reload snackbar in ChatView |
| 7 usePalLoadHint | DONE | 91fdf3f | one-shot focus-gated snackbar; single-surface dismiss |
| 8 l10n en.json | DONE | f612259 | en-only; validate-l10n passes |
| Architecture doc updated | DONE | (dev-team repo) | chat-flow.md + pals-and-talents.md drift repaired to real symbols |
| Cleanup reminders applied | DONE | - | none; §5 deferred items untouched |

---

## Affected files

| Path | Change | Ref |
| --- | --- | --- |
| `src/utils/completionTypes.ts` | add `CompletionResultSnapshot`, `BannerVariant` | §1 |
| `src/services/talents/types.ts` | add `recommendedContextTokens?: number` to `TalentEngine` | §1, I8 |
| `src/services/talents/RenderHtmlEngine.ts` | declare `recommendedContextTokens = 4096` | I8 |
| `src/store/ChatSessionStore.ts` | 4 ephemeral fields + clears | §1, §5 |
| `src/hooks/useChatSession.ts` | paired snapshot write (2 boundaries); remote deriver; counter | §2, §1b, I3 |
| `src/utils/bannerVariantResolver.ts` (new) | pure resolver + memory-gated `nextNCtx` | §4a |
| `src/components/ChatView/ChatView.tsx` | BannerRow in soft-cap slot; snackbar hosts; focus gate | §4c, I1, I6 |
| `src/components/AssistantTurnFooter/AssistantTurnFooter.tsx` | suppress truncated text under context-full | I10 |
| `src/components/IncreaseContextSheet/*` (new) | confirm sheet + reload feedback | §4c, 9e |
| `src/hooks/usePalLoadHint.ts` (new) | one-shot snackbar trigger | §4c, I6, I8 |
| `src/locales/en.json` | new strings (en only; rest via Weblate) | intent §7 |
| `context/architecture/chat-flow.md` | rewrite Invariants/§4/§5/§9f `(C)`→reality | Drift |
| `context/architecture/pals-and-talents.md` | rewrite §5a I8 to real fields | Drift |

---

## Plan exploration

Candidates: `plan-candidate-{A,B,C}.md`. This HOW synthesizes A.

### Sequencing note

Data-up; the pure resolver lands once in Step 4 (avoids B's per-slice precedence churn) and docs absorb last in Step 9 once the real code shape is known (avoids C's stale-doc window).

---

## Steps

### Step 1: Snapshot + variant types; talent recommended-context field

**Implements**: §1, §1b, I8.

**Files**: `completionTypes.ts` — `CompletionResultSnapshot` (fields per §1) +
`BannerVariant` union (§1 glossary). `talents/types.ts` — add
`recommendedContextTokens?: number` to `TalentEngine` (currently types.ts:26, no
field). `RenderHtmlEngine.ts` — set `4096`; `Calculate`/`Datetime` stay absent.

**Approach**: Additive types only, no behaviour. Snapshot semantics (esp. `used`,
`finishReason`) are pinned in §1b — do not redefine.

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/services/talents/types.ts`.

---

### Step 2: ChatSessionStore ephemeral fields + all clear triggers

**Implements**: §1, §5, scenario E.

**Files**: `ChatSessionStore.ts` — observable `lastCompletionResult?`,
`dismissedBannerVariants:Set`, `consecutiveFullFailures:number`,
`palLoadHintSeen:Set<string>` + setter actions. Clear all four in
`resetActiveSession()` (:313 runInAction); whole-op clear `dismissedBannerVariants`
in `bulkDeleteSessions()` (:1281); per-id clear in `deleteSession(id)` (:285);
hydrate `lastCompletionResult` from disk in `setActiveSession()` (:350). Register
in the observability annotations block.

**Approach**: MobX-only, no DB/migration (D1). `bulkDeleteSessions()` calls
`resetActiveSession()` ONLY when the active session is among deleted ids (:1293),
so the `dismissedBannerVariants` clear must be unconditional in `bulkDeleteSessions`
to cover the active-not-deleted path. No ModelStore import (no cycle, §5).

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/store/ChatSessionStore.ts` + new test asserting each clear trigger.

---

### Step 3: Paired snapshot writer at both completion boundaries

**Implements**: §2, §1b, I2, I3, I9, 9a.

**Files**: `useChatSession.ts` — at `run_finished` (~:323-356 `updateMessage`) and
abort-catch-with-partial (~:670-685): a local `deriveSnapshotFromResult(finalResult,
modelStore.activeContextSettings?.n_ctx)`, then write `metadata.completionResult`
AND `chatSessionStore.lastCompletionResult` in ONE MobX action, plus
`consecutiveFullFailures` (++ on contextFull, reset otherwise).

**Approach**: `used = tokens_evaluated + tokens_predicted` (D8; tokens_cached
dropped, completionTypes.ts:78). `contextFull` = OR(`context_full`,`truncated`,
`truncationLikely`, remote `finishReason==='length'`) frozen at write (I2). Remote
deriver: `isRemote && finalResult.stopped_limit===1 → finishReason='length'`
(openai.ts:623). `isRemote = activeModel?.origin === ModelOrigin.REMOTE`. Snapshot
MUST carry `content` + `reasoning_content` — PlayButton.tsx:56,78 reads them (I9).

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/components/TextMessage/PlayButton.tsx` (I9 must stay green); `... useChatSession.ts`.

---

### Step 4: Pure banner-variant resolver + memory-gated next-fit n_ctx

**Implements**: §4a, §4b (I1,I5,I7,I8 copy-site), 9b, 9d, 9g.

**Files**: `bannerVariantResolver.ts` (new) — `resolveBannerVariant(snap, {effectiveNCtx,
isRemote, htmlPreviewCount, activeModelId, dismissed, heavyTalentName})` →
`{variant, nextNCtx?, heavyTalentName?}`; helper `computeNextFitNCtx` doubling search,
each candidate gated by `getModelMemoryRequirement(...) <= availableMemoryCeiling`
(memoryEstimator.ts:105, ModelStore.ts:192).

**Approach**: Precedence exactly §4a. `effectiveNCtx = activeContextSettings.n_ctx`.
Freshness gate `used >= effectiveNCtx - AUTOCLEAR_RUNWAY`. Suppress context-* when
`activeModelId===undefined` (I5). NO n_ctx slider max exists — sole upper bound is
the memory ceiling; `nextNCtx=undefined` when no candidate fits (9g, D7), CTA hidden.
Module consts `WARNING_THRESHOLD=0.80`, `AUTOCLEAR_RUNWAY`, `MIN_REMOTE_TOKENS=500`.
`recommendedContextTokens` feeds `heavyTalentName` copy only, never trigger (I8).

**Verification**: `yarn tsc --noEmit`; new `__tests__/bannerVariantResolver.test.ts` — all precedence, freshness, memory fit/no-fit, suppression (§6.A–F).

---

### Step 5: BannerRow in soft-cap slot + footer I10 suppression

**Implements**: §4c, I1, I5, I6, I10, 9h, D5, D9.

**Files**: `ChatView.tsx` — replace the `showSoftCapWarning` block (~:1074, testID
`soft-cap-warning`) with a `BannerRow` that calls the resolver from observed
store/modelStore state and renders the single resolved variant; the soft-cap `View`
becomes the `html-soft-cap` sub-case (testID preserved). Dismiss → `setBannerDismissed`.
`AssistantTurnFooter.tsx` (:111-112) — suppress `truncated` text on the latest turn
when its snapshot raises `context-full` (new `suppressTruncated` prop, latest turn only).

**Approach**: One variant per render (I1, resolver short-circuits); one slot (D5).
Footer still shows plain `interrupted` when not truncated (I10). New testID
`context-full-banner`.

**Verification**: `yarn tsc --noEmit`; `yarn lint`; `yarn test --findRelatedTests src/components/ChatView/ChatView.tsx src/components/AssistantTurnFooter/AssistantTurnFooter.tsx` (I10); §6.B/E, 9h.

---

### Step 6: IncreaseContextSheet — confirm, reload, restore-on-failure

**Implements**: §4c, §5, §9f confirm flow, scenario C, 9e.

**Files**: `IncreaseContextSheet/` (new, follow existing sheet pattern) — takes the
resolver-supplied `nextNCtx`, calls `modelStore.setNContext(target)` (:361) →
`releaseContext` → `initContext`; indefinite reload snackbar → success/failure; on
failure restores prior n_ctx via a second `setNContext` (9e). [New chat] CTA wires
to the new-session path. Hosted from BannerRow/ChatView.

**Approach**: Sheet does NOT compute the target (resolver supplies it). History
preserved (messages in ChatSessionStore, not LlamaContext). After success the
freshness gate clears the sticky banner with no new inference (scenario C). Snackbar
focus-gated (I6); single-surface dismiss with the pal-load hint.

**Verification**: `yarn tsc --noEmit`; `yarn lint`; `yarn test --findRelatedTests` on the sheet; §6.C, 9e (manual for live reload).

---

### Step 7: usePalLoadHint one-shot snackbar

**Implements**: §4c, I6, I8, scenario F.

**Files**: `usePalLoadHint.ts` (new) — on pal load, read `pal.pact.talents[].name`
→ `talentRegistry.get(name)?.recommendedContextTokens` (TalentRegistry.ts:16); if any
recommendation > runtime `activeContextSettings.n_ctx` and `(palId,n_ctx,talents)`
signature ∉ `palLoadHintSeen`, raise a one-shot snackbar + `markPalLoadHintSeen`.
Host snackbar in ChatView, focus-gated (I6).

**Approach**: Snackbar layer separate from banner (I6); cannot displace/be displaced.
Single-surface dismiss: reload snackbar dismisses this hint in the same handler
(React 18 auto-batch). Declarative copy/pre-load only — never moves a trigger (I8).

**Verification**: `yarn tsc --noEmit`; `yarn lint`; `yarn test --findRelatedTests src/hooks/usePalLoadHint.ts` (once per signature; no-fire when n_ctx≥rec; field-absent engines); §6.F.

---

### Step 8: l10n strings (en.json)

**Implements**: intent §7, §3 copy.

**Files**: `src/locales/en.json` `chat` block (~:1090) — warning / full / escalation
(consecutiveFullFailures≥2) / heavy-talent sub-copy / remote-hedged banner text;
[New chat] & [Increase context] labels; IncreaseContextSheet confirm/reload/success/
failure; pal-load hint. `{{placeholder}}` for n_ctx targets.

**Approach**: Edit en.json ONLY — other 7 locales via Weblate. Terse keys consistent
with existing `chat.*`. RTL/narrow handled by layout, not copy.

**Verification**: `yarn tsc --noEmit` (typed via `typeof en`); `node scripts/validate-l10n.js`.

---

### Step 9: Architecture-doc drift repair (same PR)

**Implements**: Drift check (WHAT 11-25), §8.

**Files**: `chat-flow.md` — rewrite **Invariants** (:20-55:
`runtimeNCtx`/`runtimeContextSettings` → `activeContextSettings.n_ctx`; drop invented
`deriveSnapshotFromResult`/`applyStickyFull` unless Step 3/4 actually used those
names), **§4 table** (:440-443: `bannerVariantResolver`→`resolveBannerVariant`,
`pickNextTier`→`computeNextFitNCtx`, "next tier tokens"→memory-gated next-fit n_ctx),
**§5 table** (:470-503: runtime* → `activeContextSettings`; `useContextBanner`→real
hook names; `bulkDeleteSessions` row → "whole-op clear; resetActiveSession only when
active deleted"), **§9f** (:997-1064: drop slider-tier language → memory-ceiling-only
gate). `pals-and-talents.md` §5a I8 (:265-277): keep declarative; fix invented
companion names. Convert (C)→reality; leave (D) intact; zero (?).

**Approach**: Drift REPAIR, not new design — docs currently describe the whole
feature as shipped `(C)` with invented names. Match exactly what Steps 1-8 landed.
No internal refs (TASK-IDs/§ anchors) in any code comment.

**Verification**: `grep -nE "runtimeNCtx|runtimeContextSettings|pickNextTier|useContextBanner|bannerVariantResolver|deriveSnapshotFromResult|applyStickyFull" context/architecture/chat-flow.md` returns only names that exist in landed code; manual read of §9f + I8.

---

## Testable-contract coverage

| Contract item | Verified by |
| --- | --- |
| §6.A warning | `bannerVariantResolver.test.ts` (0.80, dismiss/reappear) + visual |
| §6.B full + sticky + escalation | resolver (full + freshness) + AssistantTurnFooter (I10); escalation copy = manual (§6.B) |
| §6.C increase clears sticky | resolver (freshness vs new effectiveNCtx) + manual reload |
| §6.D remote hedged | resolver (weak-signal, no CTA) + useChatSession remote deriver |
| §6.E suppression | resolver (no model; dismissed-draft; soft-cap precedence) |
| §6.F talent copy + snackbar | `usePalLoadHint.test.ts` + resolver heavyTalentName + visual |
| I9 dangling-reader | `PlayButton.test.tsx` stays green |
| I10 no double cut-off | `AssistantTurnFooter.test.tsx` |

---

## Review / debug strategy

- **Riskiest files**: `useChatSession.ts` (paired write × 2 boundaries, I3/I9 — wrong
  shape breaks PlayButton); `bannerVariantResolver.ts` (precedence I1 + memory gate);
  `ChatSessionStore.ts` (conditional `bulkDeleteSessions` clear).
- **Expected failure modes**: snapshot missing content/reasoning_content (I9 break);
  warning fires late on cache-reuse turns (D8 under-count, expected); banner + footer
  both show "cut off" (I10 regression).
- **Tests that should fail if wrong**: `PlayButton.test.tsx`; `bannerVariantResolver.test.ts`; `AssistantTurnFooter.test.tsx`.
- **Manual verification required**: live increase-context reload + restore-on-failure
  (9e/C); 8-locale + RTL + iPhone SE banner/snackbar layout.
- **Independent reviewer focus**: (1) paired write preserves I9 reads; (2) resolver +
  memory gate never offers an OOM n_ctx (9g/D7); (3) docs rewrite uses ONLY names that
  exist in landed code (drift fully repaired).

---

## Visual evidence

```json
[
  {"label": "context-warning en", "prompt": "<long convo to ~80% n_ctx>", "look_for": "softer 'getting tight' banner, dismissable"},
  {"label": "context-full sticky en", "prompt": "<overflow n_ctx>", "look_for": "strong sticky banner + New chat + Increase context; footer 'cut off' suppressed that turn"},
  {"label": "context-full no-fit en", "prompt": "<overflow, no larger fits>", "look_for": "sticky banner, ONLY New chat, no Increase CTA"},
  {"label": "context-remote-hedged en", "prompt": "<remote model truncated>", "look_for": "hedged advisory, NO increase CTA, dismissable"},
  {"label": "pal-load hint en", "prompt": "<load render_html pal into 2048 n_ctx>", "look_for": "one-shot 'needs more room' snackbar, not a banner"},
  {"label": "context-warning RTL he iPhone SE", "prompt": "<~80% n_ctx, he>", "look_for": "RTL-mirrored, no clipping"},
  {"label": "context-full ja iPhone SE", "prompt": "<overflow, ja>", "look_for": "CTAs wrap cleanly"}
]
```

Also capture the full-banner variant in id/ko/ms/ru/zh for the 8-locale requirement.

---

## Deferred items

- §5 Cleanup-DEFERRED (`inferencing`/`isStreaming`/`isGenerating` derive from `agentUiState.status`) — untouched.
- Escalation copy distinction (consecutiveFullFailures≥2) — copy-only, manual/visual (§6.B).

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| - | - | - | - |
