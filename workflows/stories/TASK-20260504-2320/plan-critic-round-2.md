# HOW Critique — Round 2

**Reviewer**: pocketpal-plan-critic
**Date**: 2026-05-05
**Verdict**: LGTM

---

## Summary

Round-1 BLOCKER (Step 14 §10 retention) is fully resolved per `templates/what-template.md` lines 182–190. CONCERN 2 (hook buffer vs runner-attached payload) resolved by extending `step_finished` event payload — verified non-breaking against the reducer's exhaustive switch. CONCERN 3 (Step 12 title) resolved with a clear structural-change body. The two SUGGESTIONs (per-frame id-match assertion, `modelStore.isStreaming` Deferred bullet) are absorbed.

Three new SUGGESTIONs surface — all cosmetic line-citation imprecisions; none affect plan correctness, scope, or the design contract.

## Coverage verification

- **Step → WHAT trace**: every step references a §-section. All 14 steps traced cleanly.
- **AC coverage**: each user-visible problem in intent-brief maps to ≥1 HOW step + canonical-scenario test.
- **Canonical scenario coverage**: A–I (all 9) covered by Message/ChatView tests + Visual #A–I.
- **Pattern compliance**: 9 file targets spot-checked against the worktree at `f3b750e`. No false claims.
- **Native gate**: NATIVE_CHANGES=NO; no native block expected and none included. Compliant.
- **Visual gate**: Visual Confirmation=YES; VISUAL_CAPTURES JSON has 9 entries (A–I) each with `look_for` checklists tied to the WHAT. Compliant.

## Findings

### SUGGESTION 1: Step 9's TalentSurface `renderPending` line range

Step 9 cites "renderPending per call at lines 71–77" — actual location is 79–87 (the per-call pending push). Lines 71–77 are the `renderResult` branch. Cosmetic; the structural rewrite prose ("New shape: four-priority dispatch") makes the implementation intent unmistakable.

**Fix**: When implementing, the line range to delete is roughly 79–87 (per-call pending) + 96–130 (post-toolCalls fallback paths). No plan change required.

### SUGGESTION 2: Step 4's runner-side reorder is slightly underspecified

Step 4 says "Move `const rawToolCalls = ...` and `const calls = ... normalizeToolCallIds(...)` lines up so they execute before the `step_finished` yield." That requires also moving `const finishedResult = lastResult;` (line 358) and the `if (!finishedResult) break;` guard, since `rawToolCalls` depends on `finishedResult`.

**Fix**: When implementing, hoist the entire 358–369 block above the `yield {type: 'step_finished', ...}` statement. No plan change required.

### SUGGESTION 3: Step 7's footer-attachment site

Step 7 says "Inside `renderMessage()` for `case 'text'`: after the bubble container call, append `<AssistantTurnFooter>`." The bubble container is rendered by `renderBubbleContainer()` outside `renderMessage()` (line 354 in the component's JSX return). The footer attaches in the outer return.

**Fix**: When implementing, attach the footer in the JSX return adjacent to the `renderBubbleContainer()` call at line 354. No plan change required.

## Routing

LGTM → HOW advances to implementer. SUGGESTIONs are cosmetic; an implementer following the structural rewrites will hit the right files at the right scope. No revision round needed.
