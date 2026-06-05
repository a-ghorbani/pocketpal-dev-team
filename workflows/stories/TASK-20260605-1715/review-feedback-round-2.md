# Review Feedback Intake: PR #763 Round 2 (UI-parity slice)

Normalized input for the PR-fix pipeline. Mandatory findings imported from `workflows/reviews/PR-763/round-3/final.md`.

---

## Metadata

- **Source review**: `workflows/reviews/PR-763/round-3/final.md`
- **Target PR**: #763
- **Target branch**: `feature/TASK-20260605-1715`
- **Worktree**: `./worktrees/TASK-20260605-1715` (at `b7338d6`)
- **Status**: approved-for-fix

---

## Verdict

- **Review verdict**: REQUEST_CHANGES
- **Review complete**: yes
- **Role subreviews**: COMPLETED (ux, qa, architect, mobile, local-invariants; security/perf/data no-delta)

---

## Fix Scope

Only `BLOCKER` and `CONCERN` findings are mandatory. `SUGGESTION` findings are out of scope unless needed to fix a mandatory item.

| ID | Severity | Lens | Path | Line | Required fix |
| --- | --- | --- | --- | --- | --- |
| R1 | BLOCKER | UX/Correctness | `src/components/ChatView/styles.ts` + `BannerRow.tsx` | styles.ts:98-107; BannerRow:106-145 | The `context-warning` banner stacks header/meter/actions inside `styles.contextBanner` which is `flexDirection:'row'` → blocks render side-by-side and the fullness meter collapses to ~0 width (invisible — the headline feature). Give `context-warning` a COLUMN container (mirror `contextFullBanner`); harden `bannerMeter` with `alignSelf:'stretch'` (+ explicit width) so its `width: ratio*100%` fill measures against a full-width parent. Do NOT regress `context-remote-hedged` (it legitimately uses the row layout). Add a test asserting the meter renders with non-zero width / the warning uses a column layout. |
| R2 | CONCERN | Correctness | `src/components/ChatView/ChatView.tsx` | 289-314 | The banner increase-CTA gate `CONTEXT_LADDER.some(tier > currentNCtx && fits(tier))` omits the `<= modelMaxCtx` cap the sheet applies. When `currentNCtx >= ggufMetadata.context_length`, the CTA appears and opens a sheet whose only stop equals the current size → a no-op "Set to NK" reload. Add the `<= modelMaxCtx` cap to the gate so banner and sheet agree. |
| R3 | CONCERN | Architecture / doc drift | `context/architecture/chat-flow.md` | 441-442 | The §9f component-render TABLE still names the retired `computeNextFitNCtx` / "memory-gated next-fit n_ctx", contradicting the repaired §9f prose (~1043-1067) and the landed code. Update the two table rows to match: sheet owns the target via the 3-zone fit classifier; resolver emits `ratio`. (Control-plane doc edit, same-PR drift repair.) |
| R4 | CONCERN | UX/Architecture (contract reconcile) | `workflows/stories/TASK-20260605-1715/what-ui-parity.md` (§4b, U7) + `src/components/IncreaseContextSheet/IncreaseContextSheet.tsx` | what §4b/U7; sheet:141 | ADJUDICATED (ux + mobile, independently): the now/device-limit slider TRACK TICKS were over-specified — `@react-native-community/slider` has no track-overlay API, ticks would need RTL-fragile onLayout math, and OOM-safety is already carried by the per-stop confirm gate + no-fit state. Do NOT build the ticks. Instead AMEND `what-ui-parity.md` §4b and U7 (and any §9f mention) to drop the now/device-limit track ticks — keep the device-limit info as the status-line copy that already renders. Remove the stale `IncreaseContextSheet.tsx:141` comment claiming a device-limit tick is "drawn". |
| R5 | CONCERN | Accessibility | `src/components/IncreaseContextSheet/IncreaseContextSheet.tsx` | 271-295 | The slider has `testID` but no `accessibilityLabel`/`accessibilityValue` → screen readers announce the raw ladder index ("5"), not the size. Add `accessibilityLabel` + `accessibilityValue={{text: '<NK> tokens'}}` (localized) on the slider; mark the decorative fullness meter `accessibilityElementsHidden` / `importantForAccessibility="no"`. |

---

## Verification Required

- `yarn tsc --noEmit` clean; `yarn lint` clean on changed files.
- Full Jest suite green (`yarn test --watchAll=false`), including NEW assertions for R1 (meter renders with non-zero width on the warning variant) and R2 (CTA gate respects model max).
- `scripts/validate-l10n.js` clean (R5 may add a localized slider-value string).
- Manual/visual (tracked pre-merge): after R1 + R4, the 8-locale + RTL `he` + iPhone SE capture confirms the meter renders on the warning banner and the slider/fit-chip/no-fit layout holds (no ticks).

---

## Out Of Scope (SUGGESTION — do not implement unless pulled in by a mandatory fix)

- S1: delete orphan l10n key `chat.increaseContextConfirm: "Increase"` (`en.json:1130`). NOTE: trivial; fold in while touching en.json for R5 if convenient.
- S2: prototype parity — distinct per-variant icons (octagon-alert vs alert-triangle), CTA pill icons, non-numeric vs numeric meter label — product/design decision, defer.
- S3: `onSlidingComplete` vs per-frame `onValueChange` on low-end Android; `kLabel` rounding of a non-power-of-two model max — defer.
