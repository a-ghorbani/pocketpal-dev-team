# Design Candidate: B — Derive-on-read from existing message metadata (no new store field)

## Metadata

- **Task ID**: TASK-20260605-1715
- **Candidate**: B
- **Intent Brief**: `./workflows/stories/TASK-20260605-1715/intent-brief.md`
- **Architecture doc(s)**: `./context/architecture/chat-flow.md`, `./context/architecture/pals-and-talents.md`

## Approach

No new `lastCompletionResult` store field. The resolver/hook reads the newest assistant turn's existing `metadata` (`truncationLikely`, `interrupted`, `timings`) plus a minimal new `metadata.completionResult` snapshot, and recomputes `used`/`ratio` on every render from the message list + `activeContextSettings.n_ctx`. Banner state (dismiss) lives in component-local `useState` keyed by draft id, not in the store.

## Contract Shape

- Data / ownership boundary: snapshot lives ONLY on the message (`metadata.completionResult`); no store mirror. Dismiss is ChatView-local React state.
- Event or state shape: ratio recomputed each render (resolver not pure over a frozen snapshot — re-reads message list).
- Single-writer implications: only `useChatSession` writes `metadata.completionResult`; no cross-store store field to own.
- User-visible scenarios covered: all six, but talent snackbar one-shot needs SOME persistence to survive remount.

## Why This Might Win

- Smaller surface: no new MobX observable, no clear-trigger wiring across `resetActiveSession`/`setActiveSession`/`deleteSession`.
- Dismiss-for-turn maps naturally to component state that dies on navigation/new-chat.

## Known Risks

- Recompute-on-render duplicates arithmetic and risks reader/writer divergence (the exact thing the doc's "snapshot truth" invariant exists to prevent).
- Component-local dismiss state is lost on unmount/refocus — "dismissed for the turn" may resurface when returning to chat.
- One-shot pal-load snackbar still needs persisted "seen" marker, so "no new store field" is only partly true.
- `consecutiveFullFailures` (escalation copy) has nowhere to live without a store field.

## Rejected If

- The "dismissed for the turn" requirement must survive backgrounding/refocus (it should — focus-gate is in scope), which kills pure component-local state.

## Verification Focus

- Code paths: `ChatView` render, `useChatSession` metadata writes.
- Easy: fewer store-clear edge cases.
- Hard: stable dismiss across focus changes; one-shot snackbar idempotency.
