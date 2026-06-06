# Design Candidate: C — Footer-only escalation, no chat banner

## Metadata

- **Task ID**: TASK-20260605-1715
- **Candidate**: C
- **Intent Brief**: `./workflows/stories/TASK-20260605-1715/intent-brief.md`
- **Architecture doc(s)**: `./context/architecture/chat-flow.md`, `./context/architecture/pals-and-talents.md`

## Approach

Reuse the EXISTING `AssistantTurnFooter` "Cut off — likely context full" affordance (already driven by `metadata.truncationLikely`) and extend it into the full recovery surface: add a near-limit hint and recovery buttons (new chat / increase context) inline in the turn footer instead of a chat-input banner. No new banner slot, no resolver.

## Contract Shape

- Data / ownership boundary: everything hangs off `metadata` on the turn; footer reads it.
- Event or state shape: per-turn, no cross-turn ratio aggregation.
- Single-writer implications: extend the existing footer metadata writers only.
- User-visible scenarios covered: full-sticky (already partly there) + recovery; weaker on near-limit (~80%) which is a forward-looking, cross-turn signal not tied to one finished turn.

## Why This Might Win

- Smallest footprint; builds directly on shipped `truncationLikely` footer.
- No new banner component, no soft-cap precedence problem.

## Known Risks

- Near-limit (~80%) warning is inherently about the conversation's running total vs n_ctx — it belongs at the input, near the send action, not buried in the last turn's footer that scrolls away.
- Footer is per-turn and ephemeral in the scroll; a "sticky" full state that must persist until improved doesn't fit a footer.
- Recovery CTAs in a scrolled-off footer are poor UX on iPhone SE.
- Diverges hard from the architecture doc's banner contract — would require rewriting §9f rather than implementing it.

## Rejected If

- The intent requires a persistent, action-near-input surface (it does: "banner in the chat surface", "sticky banner") — footer-only cannot satisfy "sticky until improved" + near-input recovery.

## Verification Focus

- Code paths: `AssistantTurnFooter.tsx` (truncationLikely already at line ~111).
- Easy: reuse existing footer test harness.
- Hard: near-limit and sticky semantics; iPhone SE reachability.
