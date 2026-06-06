# Plan Candidate B: thin-slice-per-variant (full → warning → remote → hint → docs)

## Metadata
- **Task ID**: TASK-20260605-1715
- **Candidate**: B
- **Design source**: `./workflows/stories/TASK-20260605-1715/what.md`

## Strategy
Deliver one banner variant end-to-end at a time. Land the snapshot type + store
+ writer once (shared foundation), then ship `context-full` (sticky + I10 footer
suppression + IncreaseContextSheet) as a vertical slice, then `context-warning`,
then `context-remote-hedged`, then the pal-load snackbar, then docs. Each slice
is independently demoable and visually capturable.

## Step Shape
1. Foundation: snapshot type + store fields + paired writer (shared).
2. context-full slice: resolver full-branch + memory gate + BannerRow + I10 + sheet.
3. context-warning slice: resolver warning-branch + dismiss wiring.
4. context-remote-hedged slice: remote deriver + resolver hedged-branch.
5. pal-load snackbar slice: TalentEngine field + usePalLoadHint.
6. l10n + docs absorption + visual evidence.

## Commit Boundaries
- One commit per slice (6). Each adds a user-visible variant; demo-friendly.

## Verification
- Lint/typecheck per commit.
- Focused tests: resolver gains cases per slice; writer + store tests in slice 1.
- Visual: capture each variant as its slice lands.

## Risks
- The pure resolver (§4a precedence) gets edited in 4 separate commits — precedence
  short-circuit (I1) easy to regress between slices; resolver test must be
  re-run every slice and cover ALL variants from slice 2 on.
- Memory-gate + sheet land together in slice 2, a heavy commit.

## Rejected If
- Resolver precedence churn across slices risks I1/I4a regressions that A avoids
  by landing the resolver once — this is the main reason to prefer A.
