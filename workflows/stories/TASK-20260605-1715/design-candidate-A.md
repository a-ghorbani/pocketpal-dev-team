# Design Candidate: A — Snapshot-on-store + pure resolver (matches doc's optimistic shape)

## Metadata

- **Task ID**: TASK-20260605-1715
- **Candidate**: A
- **Intent Brief**: `./workflows/stories/TASK-20260605-1715/intent-brief.md`
- **Architecture doc(s)**: `./context/architecture/chat-flow.md`, `./context/architecture/pals-and-talents.md`

---

## Approach

Implement what the architecture doc already (falsely) marks `(C)`: at every turn boundary, write a normalised `CompletionResultSnapshot` to both the newest assistant message's `metadata.completionResult` AND a new `chatSessionStore.lastCompletionResult` observable, in one MobX action. A pure `resolveBannerVariant(snapshot, effectiveNCtx, isRemote, htmlPreviewCount, dismissed, palMeta)` returns exactly one of five variants. ChatView renders the single banner slot from the resolver. Increase-context CTA opens a confirm sheet that calls `setNContext` + reload.

## Contract Shape

- Data / ownership boundary: snapshot owned by `ChatSessionStore` (`lastCompletionResult`) + mirrored on `metadata.completionResult`; runtime n_ctx read from existing `modelStore.activeContextSettings.n_ctx` (NOT a new `runtimeNCtx`).
- Event or state shape: arithmetic done once at write time (`used`, `contextFull`); resolver is pure read.
- Single-writer implications: `lastCompletionResult` written only by `useChatSession` at `run_finished` + abort-catch. `dismissedBannerVariants` written only by the banner on dismiss. `contextInitParams.n_ctx` keeps its two existing writers (Settings + new CTA).
- User-visible scenarios covered: all six (near-limit, full-sticky, recovery, remote-hedged, suppression, talent copy/snackbar).

## Why This Might Win

- The architecture doc is already written in this shape; absorbing the delta is mechanical and keeps the doc honest.
- Snapshot-at-write means readers never redo arithmetic; freshness gate (`used >= nCtx - runway`) lets the banner self-clear after an increase without a new inference.
- Pure resolver is trivially unit-testable; one banner per render is structural.

## Known Risks

- Persisting `metadata.completionResult` widens its meaning — today it carries only `{content, reasoning_content}` for TTS/PlayButton. Must extend, not break, those readers.
- Snapshot must be written even on abort-with-partial (the truncation smoking gun lives there).
- Remote `tokens_predicted` / `finish_reason` availability varies by server.

## Rejected If

- Persisting a richer `completionResult` proves to collide with TTS readers in a way that can't be made additive.

## Verification Focus

- Code paths: `useChatSession` `run_finished` (line ~323) + abort-catch (~670); `PlayButton.tsx` completionResult reader; `ChatView` soft-cap JSX (~1047).
- Easy: resolver precedence unit tests; freshness-gate self-clear.
- Hard: end-to-end remote-hedged heuristic without a real server.
