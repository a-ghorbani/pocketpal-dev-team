# Intent: Warn when a chat is near or at the context limit, with recovery

> **Outcome — DONE.** Shipped as PR #763 (pocketpal-ai), merged 2026-06-06 (`07d1937`).
> Full pipeline: intent → WHAT (+UI-parity delta) → HOW → implement → test →
> 5 independent-review rounds → merge. Unit suite green (221 suites / 3247);
> feature E2E sweep green incl. the new `context-banner` spec (5/5 on iOS sim).
> Architecture absorbed into `context/architecture/chat-flow.md` §9f +
> `pals-and-talents.md` §5a. Other-locale copy follows via Weblate; visual
> capture (8 locales + RTL + iPhone SE, light/dark) was the noted residual.

**Purpose**: confirm **what** the requester wants built, before any design or implementation begins.

---

## Metadata

- **Task ID**: TASK-20260605-1715
- **Source**: prompt (dev-team intake)
- **Worktree**: `./worktrees/TASK-20260605-1715`
- **Branch**: `feature/TASK-20260605-1715`
- **Complexity**: standard
- **Native Changes**: NO
- **Visual Evidence Required**: YES
- **Design Exploration**: YES
- **Plan Exploration**: YES
- **Created**: 2026-06-05
- **Status**: approved

---

## Request

Users have no warning when a chat is about to run out of context. Long conversations and tool-heavy talents (especially render_html) silently overflow n_ctx, producing truncated replies or "tool call cut off" errors that the user can't diagnose. This task adds a visible warning when the chat is near or at the context limit, with a way to recover.

### What it must deliver

1. **Warn when nearing the limit.** When recent turns have used a high fraction of n_ctx (~80%+), the user sees a banner in the chat surface telling them the conversation is getting tight. The trigger is talent-agnostic — based purely on the used/n_ctx ratio.
2. **Surface a clear "full" state.** When a turn was actually truncated or hit the context limit, the user sees a stronger, sticky banner that doesn't clear until the situation improves.
3. **Offer recovery from the banner.** The user can either start a new chat, or increase the context size if the device can fit a larger one (memory-aware).
4. **Handle remote models gracefully.** For PalsHub remote models (we don't own their n_ctx), surface a hedged advisory when a response looks truncated. No "increase context" option.
5. **Stay quiet when there's nothing to act on.** No banner when no model is loaded, no banner when dismissed for the turn, no banner duplication with the existing HTML soft-cap.
6. **Talent-aware copy and pre-load hint (NOT talent-aware thresholds).** Talents may declare a `recommendedContextTokens` field. This is used for:
   - A one-shot snackbar when a pal with a heavy talent loads into a chat smaller than its recommendation ("this pal tends to need more room").
   - A more specific copy variant on the full banner when the last turn called a heavy-talent tool.
   The banner trigger stays purely ratio-based; only the copy and the pre-load hint consult talent metadata.
7. **Work across the supported languages.** 8 integrated locales (en/he/id/ja/ko/ms/ru/zh) including RTL, on iPhone SE narrow widths.

### Not in scope

Per-pal context overrides; predictive talent-aware thresholds (using talent metadata to move the warning trigger itself); live during-stream tracking; known-provider context registries for remote pre-warning. Reactive-only on remote.

### Acceptance criteria

- A near-limit (~80%+ used/n_ctx) banner appears in the chat surface, ratio-based and talent-agnostic.
- A stronger sticky "full" banner appears when a turn was truncated / hit the context limit, and persists until the situation improves.
- Banner offers recovery: start new chat, and (local models only) increase context size when the device can fit a larger n_ctx (memory-aware).
- Remote (PalsHub) models get a hedged truncation advisory with no "increase context" option.
- No banner when: no model loaded, dismissed for the turn, or where it would duplicate the existing HTML soft-cap.
- `recommendedContextTokens` talent metadata drives only (a) a one-shot pal-load snackbar when loaded chat n_ctx < recommendation, and (b) a copy variant on the full banner after a heavy-talent tool call — NOT the trigger threshold.
- Works across all 8 integrated locales incl. RTL, on iPhone SE narrow widths.

### Known baseline / context to verify in codebase

- This is the dev-team control plane; app source is in repos/pocketpal-ai (read-only submodule; all work in a worktree).
- Relevant existing areas to confirm during design: how n_ctx / runtime context is read and configured, the chat completion flow and where truncation / stop reason is surfaced, the existing HTML render soft-cap, PACT/talent metadata shape, memory-aware context sizing used elsewhere (model load), and the l10n flow (8 integrated locales).

---

## Clarifications

none — the request is unambiguous: scope, acceptance criteria, and explicit non-goals were all supplied.
