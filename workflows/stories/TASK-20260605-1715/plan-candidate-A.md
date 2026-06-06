# Plan Candidate A: data-up (types → store → writer → resolver → UI → l10n → docs)

## Metadata
- **Task ID**: TASK-20260605-1715
- **Candidate**: A
- **Design source**: `./workflows/stories/TASK-20260605-1715/what.md`

## Strategy
Build strictly bottom-up along the data flow. First the snapshot type + talent
field (§1, §1b), then the MobX-ephemeral store fields with their clear-trigger
wiring (§5), then the single paired writer in `useChatSession` (§2/I3), then the
pure resolver + memory-gate (§4a), then the UI surfaces (BannerRow reuse,
IncreaseContextSheet, usePalLoadHint), then l10n, finally docs absorption. Each
layer is unit-testable before the next consumes it; the writer can be tested
against the type before any UI exists.

## Step Shape
1. Snapshot type + `recommendedContextTokens` on TalentEngine + RenderHtml=4096.
2. Store fields + all clear triggers (reset/setActive/delete/bulkDelete).
3. Paired snapshot writer at both useChatSession boundaries; remote deriver.
4. Pure resolver + memory-gated nextNCtx + payload.
5. BannerRow (reuse soft-cap slot) + footer I10 suppression.
6. IncreaseContextSheet confirm/restore + reload snackbar.
7. usePalLoadHint one-shot snackbar (I6/focus gate).
8. en.json strings.
9. Docs absorption (drift repair) + visual evidence.

## Commit Boundaries
- One commit per layer (9 commits). Clean blame; each compiles + has its own test.

## Verification
- Lint/typecheck: `yarn tsc --noEmit`, `yarn lint` per commit.
- Focused tests: resolver unit (`__tests__/resolveBannerVariant.test.ts`), writer
  test via useChatSession, PlayButton regression (I9), store-clear tests.
- Manual / visual: 8-locale + RTL + iPhone SE capture of warning/full/hedged/snackbar.

## Risks
- Snapshot type churns if resolver later needs a field not anticipated — but §1
  pins the shape, low risk.
- Long lead time before any visible behaviour; integration bugs surface late.

## Rejected If
- The resolver contract were unsettled (it is fully pinned in §4a), making
  bottom-up premature. It is settled, so this stays viable.
