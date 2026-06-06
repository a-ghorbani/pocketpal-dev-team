# Review Feedback Intake: PR #763 Round 1

Normalized input for the PR-fix pipeline. Mandatory findings imported from `workflows/reviews/PR-763/round-1/final.md`.

---

## Metadata

- **Source review**: `workflows/reviews/PR-763/round-1/final.md`
- **Target PR**: #763
- **Target branch**: `feature/TASK-20260605-1715`
- **Worktree**: `./worktrees/TASK-20260605-1715` (PR head `8f26c02`; this is the implementation worktree and the PR branch — fixes land here)
- **Status**: approved-for-fix

---

## Verdict

- **Review verdict**: REQUEST_CHANGES
- **Review complete**: yes
- **Role subreviews**: COMPLETED

---

## Fix Scope

Only `BLOCKER` and `CONCERN` findings are mandatory. `SUGGESTION` findings are out of scope unless needed to fix a mandatory item.

| ID | Severity | Lens | Path | Line | Required fix |
| --- | --- | --- | --- | --- | --- |
| R1 | BLOCKER | Correctness | `src/utils/bannerVariantResolver.ts` | 70-104 | Remote hedged advisory (AC D) never renders: the branch is gated by `contextActionable` which requires `effectiveNCtx !== undefined`, but `activeContextSettings.n_ctx` is never set for remote models. Gate the remote-hedged branch on `activeModelId !== undefined` only (it never reads `nCtx`); add a resolver test with `effectiveNCtx: undefined` and a `BannerRow` remote-model render test. |
| R2 | CONCERN | Platform/Native | `src/components/IncreaseContextSheet/IncreaseContextSheet.tsx` | 45-59 | On reload failure (incl. user-cancelled memory Alert) `releaseContext()` has already run but the catch only restores the setting via `setNContext`, never re-inits → model left unloaded while copy says "previous setting was restored". Re-init at the prior `n_ctx` in the catch (preferred), or correct the copy to state the model unloaded and keep the New-chat CTA reachable. |
| R3 | CONCERN | UX/Localization | `src/components/ChatView/BannerRow.tsx` | 28-43, 147-148 | Raw engine key `render_html` is interpolated into the full-banner copy instead of its localized display name. Map the engine key to the existing localized name (`l10n.components.palSheet.talentNames.<key>`, e.g. "HTML preview") at the render site before interpolation. |
| R4 | CONCERN | UX/Accessibility | `src/components/ChatView/styles.ts` | 93-108 | Warning + remote-hedged row banners use `flexDirection:'row'` + `justifyContent:'space-between'` with a non-flexed centered text next to Dismiss → clipping / Dismiss pushed off-screen at 320pt (iPhone SE) and in RTL with longer translations. Add `flex:1`/`flexShrink:1` to the row text and drop center alignment for the row variants (match the safer vertical stack used by the full banner). |
| R5 | CONCERN | Maintainability | `src/components/ChatView/__tests__/BannerRow.test.tsx` | 132 | Internal-ref hygiene Non-Negotiable: test name leaks the `(I5)` story/architecture anchor into read-only submodule source. Drop the `(I5)` parenthetical (the name is self-describing). Scan the rest of the diff to confirm no other internal anchors leaked. |

---

## Verification Required

- `yarn tsc --noEmit` clean.
- Full Jest suite green (`yarn test --watchAll=false`), including the new remote-model resolver/BannerRow tests from R1.
- `scripts/validate-l10n.js` clean (R3 touches no new keys but confirm).
- Manual: confirm R2 reload-failure path re-loads the model (or the corrected copy + reachable New-chat), and that R1 remote-hedged advisory actually renders for a remote (PalsHub) model.
- Visual capture (tracked pre-merge item) — after R4, the iPhone SE + `he` RTL captures must confirm the row banners no longer clip.

---

## Out Of Scope (SUGGESTION — do not implement unless pulled in by a mandatory fix)

- S1: doc "same MobX action" wording vs two-actions-with-await (cosmetic). NOTE: if R2/R1 edits touch the write site, optionally tighten to one `runInAction`; otherwise leave — the §4 writer table is already accurate.
- S2: explicit 0.80 lower-edge + Scenario-C freshness-clear tests. NOTE: naturally folded in while adding R1's remote tests — include if convenient.
- S3: lazy projection-model lookup / `useMemo` omission (performance, non-mandatory).
- S4: live-region a11y (`accessibilityRole="alert"`) on the sticky banner.
