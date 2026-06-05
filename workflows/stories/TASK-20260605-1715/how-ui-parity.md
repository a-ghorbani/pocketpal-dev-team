# Implementation Plan: Chat context-limit banner — UI-parity port (meter + slider sheet)

Executable worklist for `what-ui-parity.md`. Port the prototype's richer banner
meter + slider sheet onto OUR landed data layer (PR #763), rewiring reference RN
JSX/styles to OUR resolver/snapshot. Section refs are to `what-ui-parity.md` unless
prefixed `what.md`/`§9f`. Do NOT re-derive design here.

---

## Metadata

- **Task ID**: TASK-20260605-1715 (UI-parity slice)
- **Worktree**: `worktrees/TASK-20260605-1715`
- **Branch**: `feature/TASK-20260605-1715` (= PR #763)
- **Native Changes**: NO (`@react-native-community/slider ^5.0.1`, `react-native-device-info ^14.1.1` already in `package.json`; no native edit)
- **Visual Evidence Required**: YES
- **Intent Brief**: `./workflows/stories/TASK-20260605-1715/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260605-1715/what-ui-parity.md` (+ data-layer `what.md`, do not regress)
- **Architecture doc(s)**: `./context/architecture/chat-flow.md` (§9f), `./context/architecture/pals-and-talents.md`
- **Status**: draft

---

## Progress

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 (resolver) | DONE | 8f5fc4b | ratio + CONTEXT_LADDER; nextNCtx/computeNextFitNCtx/canFitNCtx retired |
| Step 2 (fit classifier helper) | DONE | 8f5fc4b | `makeFitStatusFor` pure caller-injected 3-zone helper |
| Step 3 (BannerRow meter/pills) | DONE | 1d80121 | meter + percent + More room/or/New chat; host `canIncrease` gate |
| Step 4 (sheet) | DONE | 99b0427 | slider/ladder/capacity/fit chip/ticks/warn/Advanced + no-fit state; OUR re-init confirm preserved |
| Step 5 (ChatView rewire) | DONE | 99b0427 | sheetOpen state; canIncrease at call site; sheet props |
| Step 6 (pal-hint action) | DONE | 99b0427 | snackbar "More room" action opens sheet |
| Step 7 (l10n) | DONE | 99b0427 | en.json only; validate-l10n green |
| Step 8 (tests) | DONE | 8f5fc4b/1d80121/99b0427 | migrated nextNCtx tests to sheet; added ratio + slider/no-fit; 61/61 affected pass |
| Architecture doc updated (§9f) | DONE | (control-plane) | §9f rewritten: slider + sheet-owned target + fits-gate + meter; restore-on-failure prose kept |
| Cleanup reminders applied | DONE | 8f5fc4b | computeNextFitNCtx/nextNCtx removed |

---

## Affected files

| Path | Change | Design ref |
| --- | --- | --- |
| `src/utils/bannerVariantResolver.ts` | edit — add `ratio`, `CONTEXT_LADDER`; retire `computeNextFitNCtx`/`nextNCtx` | §1, §4a |
| `src/components/IncreaseContextSheet/fitStatus.ts` | add — pure `fitStatusFor` 3-zone classifier + `FitStatus` type | §4c |
| `src/components/ChatView/BannerRow.tsx` | edit — meter, pill CTAs + "or", icons/tints, sheet-side CTA gate | §4d, §4a.2 |
| `src/components/ChatView/styles.ts` | edit — meter/header/percent/pill/or styles (lift from reference) | §4d |
| `src/components/IncreaseContextSheet/IncreaseContextSheet.tsx` | edit — slider/ladder/capacity/fit chip/ticks/warn line/Advanced/no-fit state; keep OUR confirm path | §4a, §4b, §4c |
| `src/components/IncreaseContextSheet/styles.ts` | edit — slider/chip/ticks/status/advanced (lift from reference) | §4b |
| `src/components/ChatView/ChatView.tsx` | edit — pass `(model, currentNCtx)` to sheet; sheet `New chat`; pal-hint `action` | §4a.1, §4a.4, §6 UI-5 |
| `src/locales/en.json` | edit — new chat.* strings (en only) | §5 |
| `src/utils/__tests__/bannerVariantResolver.test.ts` | edit — drop `:54`/`:63` `nextNCtx` tests; add `ratio` tests | §1 D-U1, §6 UI-1 |
| `src/components/IncreaseContextSheet/__tests__/IncreaseContextSheet.test.tsx` | edit — slider/fit-chip/no-fit/CTA-visibility (relocated OOM gate) | §6 UI-2/3/7 |
| `context/architecture/chat-flow.md` | edit — repair §9f (~1043-1052) | §9f drift |

---

## Plan exploration

`PLAN_EXPLORATION=NO`.

### Sequencing note

Resolver + pure classifier first (no UI dep), then presentational layers (BannerRow,
sheet), then ChatView rewire that connects them — so each commit typechecks and the
retired `nextNCtx` callers all flip in one wiring step (Step 5), not stranded mid-series.

---

## Steps

### Step 1: Resolver — add `ratio`, `CONTEXT_LADDER`; retire `nextNCtx`/`computeNextFitNCtx`

**Implements**: §1 (ratio precision contract, D-U1), §4a.1, §5 (deferred cleanup).

**Files**: `src/utils/bannerVariantResolver.ts`

**Approach** (≤5 lines):
- Add `ratio?: number` to `BannerResolution`; remove `nextNCtx` field. Delete
  `computeNextFitNCtx` and drop `canFitNCtx` from `BannerResolverInput` (banner CTA
  gate moves to the sheet, §4a.2).
- On BOTH nCtx-reading branches (`context-full` `:80`, `context-warning` `:95`) set
  `ratio = Math.min(1, Math.max(0, snapshot.used / nCtx))` — emit ONLY here (§1: these
  are the branches the `:76` `effectiveNCtx!==undefined` gate guarantees, no /0). Never
  set on remote-hedged/html/none.
- Keep OUR `snapshot.used` as-is — do NOT introduce reference `tokensCached+…` (U1).
- Add `export const CONTEXT_LADDER = [2048,4096,6144,8192,12288,16384,24576,32768,49152,65536,98304,131072] as const;` (lift value from reference resolver).

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/utils/bannerVariantResolver.ts` (after Step 8 migration).

---

### Step 2: Pure 3-zone fit classifier helper

**Implements**: §4c, §1b (external reads), DU3.

**Files**: add `src/components/IncreaseContextSheet/fitStatus.ts`

**Approach** (≤5 lines):
- Export `type FitStatus = 'fits' | 'tight' | 'wont_fit'` and a pure factory that
  takes injected `{memBytesFor, ceiling, totalMemory}` and returns `fitStatusFor(nCtx)`
  per §4c: `req<=ceiling → fits`; else `totalMemory>0 && req<=totalMemory → tight`;
  else `wont_fit`. Store-free, caller-injected like OUR existing `canFitNCtx` (`BannerRow.tsx:63`).
- The sheet (Step 4) builds `memBytesFor` from `getModelMemoryRequirement` and
  `ceiling = max(largestSuccessfulLoad ?? 0, availableMemoryCeiling ?? 0)` (§4c).

**Verification**: `yarn tsc --noEmit`; unit-tested via Step 8 (CTA-visibility / no-fit).

---

### Step 3: BannerRow — meter, pill CTAs + "or" connector, per-variant icons/tints

**Implements**: §4d, §4a.2, §4g, UI-1.

**Files**: `src/components/ChatView/BannerRow.tsx`, `src/components/ChatView/styles.ts`

**Approach** (≤5 lines):
- Lift the reference's `Meter` subcomponent + `bannerMeter`/`bannerMeterFill`/
  `bannerHeader`/`bannerPercent` styles. Width = `Math.max(0,Math.min(1,ratio))*100%`.
  Render the meter ONLY on `context-warning` + `context-full` (where resolver now emits
  `ratio`); guard `ratio != null` (remote/none have none — reinforces I7/UE-e).
- Add increase CTA to the WARNING banner (§4d) plus the FULL banner; present them as
  primary "More room" + secondary "New chat" with an "or" connector (lift prototype
  `.ctx-or`/`.ctx-cta` look into `styles.ts`). Keep dismiss on warning/hedged.
- CTA visibility gate (§4a.2): replace `nextNCtx !== undefined` with a `canIncrease`
  boolean prop from the host (true iff ≥1 ladder tier `> currentNCtx` is `fits`); when
  false show ONLY [New chat]. Keep OUR `deriveHeavyTalentName` + l10n copy selection (`:147`).
- `onIncreaseContext` prop changes signature to `() => void` (no precomputed target).

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/components/ChatView/BannerRow.tsx`; scenario UI-1.

---

### Step 4: IncreaseContextSheet — slider sheet (capacity, fit chip, ticks, warn line, Advanced, no-fit state)

**Implements**: §4a.3, §4a.4, §4b, §4c, U2, U5, U6, U7, UE-a/b/c/f, UI-2/3/4/6/7.

**Files**: `src/components/IncreaseContextSheet/IncreaseContextSheet.tsx`, `.../styles.ts`

**Approach** (≤5 lines):
- Change props to `{model, projectionModel?, currentNCtx, isVisible, onClose,
  onReloadStart, onReloadResult, onNewChat}`. Lift reference JSX/state for: `totalMemory`
  via `DeviceInfo.getTotalMemory()` (catch→0, UE-c); `ladder` filtered `>currentNCtx`
  && `<=modelMaxCtx` with `modelMaxCtx` appended (UE-a fallback `CONTEXT_LADDER[last]`);
  `pickIdx`/`advancedOpen` `useState` reset on open (U6); slider, fit chip, capacity
  readout (`formatBytes`+`approxWords`), now-tick at `currentNCtx`, device-limit tick at
  furthest "fits" idx, fixed-min-height warn line, Advanced disclosure.
- Wire fit via Step 2 `fitStatusFor`; confirm DISABLED when chosen is `wont_fit`/reloading.
- PRESERVE OUR confirm path verbatim (U2): `setNContext(chosen)` → `releaseContext` →
  `initContext`; on failure `setNContext(prior)` + re-`initContext`; call
  `onReloadStart`/`onReloadResult(success, chosen)`. Do NOT port reference's setting-only restore.
- No-fit state (§4a.4, UE-b): when NO ladder tier is `fits`, HIDE confirm (not disable),
  show explanatory copy + a New-chat button calling `onNewChat` (host wires to
  `resetActiveSession()` + close). Use RTL-correct tick/label positions + fixed warn slot (U7).
- Grow `snapPoints` from `['35%']` to a tall point (`['85%']`, matching reference, for the
  nested-ScrollView intrinsic-height-zero issue noted in the reference).

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/components/IncreaseContextSheet/IncreaseContextSheet.tsx`; scenarios UI-2/3/4/6/7.

---

### Step 5: ChatView — rewire banner CTA → sheet, sheet props, no-fit New-chat

**Implements**: §2, §4a.1, §4a.4, §4g, §6 UI-2/UI-5.

**Files**: `src/components/ChatView/ChatView.tsx`

**Approach** (≤5 lines):
- Replace `increaseContextTarget:number|null` state with a boolean `sheetOpen` (the
  sheet owns the target now). `BannerRow.onIncreaseContext={() => setSheetOpen(true)}`.
- Compute `canIncrease` for BannerRow at the call site: ≥1 ladder tier `>currentNCtx`
  classifies `fits` (reuse Step 2 helper built from `getModelMemoryRequirement` +
  `ceiling`); pass as prop. This is the relocated OOM gate (§4a.2, replaces `nextNCtx`).
- Render `IncreaseContextSheet` with `isVisible={sheetOpen}`, `model`,
  `projectionModel`, `currentNCtx={activeContextSettings.n_ctx}`,
  `onClose={()=>setSheetOpen(false)}`, OUR existing `onReloadStart`/`onReloadResult`,
  and `onNewChat={() => { chatSessionStore.resetActiveSession(); setSheetOpen(false); }}`.

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/components/ChatView/ChatView.tsx`.

---

### Step 6: Pal-load hint snackbar — "More room" action

**Implements**: §4 (item 4), §4g, A4, UI-5, UE-b.

**Files**: `src/components/ChatView/ChatView.tsx`

**Approach** (≤5 lines):
- Add `action={{label: l10n.chat.palLoadHintAction, onPress: () => { palLoadHint.dismiss(); setSheetOpen(true); }}}` to the existing `pal-load-hint-snackbar` (`ChatView.tsx:1224`).
- No-fit handling per C3/§4a.4: the action still opens the sheet (sheet is never a
  dead-end — it self-resolves to its no-fit New-chat state). Do NOT suppress the hint.

**Verification**: `yarn tsc --noEmit`; covered by ChatView/sheet tests (no-fit reachability, Step 8).

---

### Step 7: l10n — new en-only strings

**Implements**: §5 (l10n).

**Files**: `src/locales/en.json` (chat section, after existing `palLoadHint` at `:1120`)

**Approach** (≤5 lines):
- Add en-only keys for: banner "More room"/"or"/percent are reused or literal; sheet
  body, `wordsRamReadout` ("~{{words}} words · ≈{{ram}} RAM"), `fitsChip`/`tightChip`/
  `wontFitChip`, `fitsStatus`/`fitsUnconstrainedStatus`/`tightStatus`/`wontFitStatus`,
  `hedge`, `advanced`/`advancedBody`, `confirm` ("Set to {{size}}"), `modelMaxLabel`,
  no-fit title/body + New-chat label, `palLoadHintAction` ("More room"), and reload copy
  if new. Mirror reference key shapes but keep OUR flat `l10n.chat.*` namespace (NOT the
  reference's nested `chat.contextWarning.sheet`).
- en.json ONLY; other locales land via Weblate (do not touch). Run validate.

**Verification**: `yarn l10n:validate`; `yarn tsc --noEmit` (typed via `typeof en`).

---

### Step 8: Tests — migrate retired `nextNCtx` tests, add `ratio`/slider/no-fit

**Implements**: §1 D-U1 (load-bearing), §6 UI-1/2/3/7, U2/U5.

**Files**: `src/utils/__tests__/bannerVariantResolver.test.ts`, `src/components/IncreaseContextSheet/__tests__/IncreaseContextSheet.test.tsx`

**Approach** (≤5 lines):
- Resolver test: DELETE the two `nextNCtx` fit-gate tests (`:54` "offers nextNCtx",
  `:63` "hides the CTA") and drop `canFitNCtx` from `baseInput`. KEEP all precedence /
  freshness / dismiss / suppression tests. ADD `ratio` tests (UI-1): `used=3300,nCtx=4096`
  warning → `ratio≈0.806`; full → clamped `1`; remote/none → `ratio` undefined.
- Sheet tests: KEEP OUR 3 confirm-path tests (U2 — adapt to new props: `model`,
  `currentNCtx`, `onReloadResult(success, chosen)`). ADD: slider changes chosen + capacity
  (UI-2); fit chip zones + confirm disabled on `wont_fit` (UI-3); RELOCATED OOM gate —
  when no tier `fits`, confirm HIDDEN + New-chat present (UI-7/§4a.4, the assertion that
  replaces resolver `:54`/`:63`). Mock `DeviceInfo.getTotalMemory` + `getModelMemoryRequirement`.
- Keep existing usePalLoadHint + BannerRow suites green.

**Verification**: `yarn test src/utils/__tests__/bannerVariantResolver.test.ts src/components/IncreaseContextSheet src/components/ChatView/BannerRow src/hooks/__tests__/usePalLoadHint.test.ts`.

---

### Step 9: Architecture doc — repair §9f (same-PR drift)

**Implements**: §9f drift check (lines 1043-1054).

**Files**: `context/architecture/chat-flow.md`

**Approach** (≤5 lines):
- Rewrite §9f's increase-CTA paragraph (~1043-1054): "there is no n_ctx slider" →
  there now IS one in the sheet; the increase target is chosen by the user via the
  sheet slider (over `CONTEXT_LADDER`, capped at `ggufMetadata.context_length`), NOT
  precomputed by the resolver. CTA visibility gates on the sheet-side "fits" classifier
  (≥1 tier fits) — same OOM-safe intent as the retired `nextNCtx`. Note the meter
  (driven by resolver `ratio`) on warning/full. Keep the confirm/restore-on-failure prose
  (U2 unchanged). No internal refs (FOU/TASK/§-anchors) in doc prose that ships.

**Verification**: doc reads consistently with landed code; zero `(?)`; manual review.

---

## Testable-contract coverage

| Contract item | Verified by |
| --- | --- |
| §6 UI-1 (meter = OUR `used`, not double-count) | `bannerVariantResolver.test.ts` ratio test (≈0.806, clamp 1) |
| §6 UI-2 (slider over ladder capped at model max) | `IncreaseContextSheet.test.tsx` slider/capacity test |
| §6 UI-3 (3-zone fit + confirm disabled on won't-fit) | `IncreaseContextSheet.test.tsx` fit-chip/zone test |
| §6 UI-4 (confirm failure restores running model, U2) | `IncreaseContextSheet.test.tsx` existing re-init tests (adapted) |
| §6 UI-5 (pal-hint "More room" opens sheet) | ChatView/snackbar action test + no-fit reachability assertion |
| §6 UI-6 (arbitrary current n_ctx, ladder filtered) | `IncreaseContextSheet.test.tsx` `currentNCtx=250` now-tick test |
| §6 UI-7 (OOM-safety relocated: no tier fits → no actionable target) | `IncreaseContextSheet.test.tsx` no-fit: confirm HIDDEN + New-chat present |

---

## Review / debug strategy

- **Riskiest files**: `IncreaseContextSheet.tsx` (largest port, owns OOM-safety + U2 confirm path + no-fit state); `bannerVariantResolver.ts` (retiring `nextNCtx` strands callers if Step 5 lags); `BannerRow.tsx` (CTA gate now host-supplied).
- **Expected failure modes**: stranded `nextNCtx` import after retire; meter rendering on remote (ratio leak); confirm enabled on `wont_fit`; ladder not filtered vs arbitrary `currentNCtx`.
- **Tests that should fail if wrong**: `IncreaseContextSheet.test.tsx` no-fit (confirm visibility); `bannerVariantResolver.test.ts` ratio + precedence; sheet U2 re-init tests.
- **Manual verification required**: visual evidence (below) — meter widths, slider tick/RTL positions (U7), fit-chip zone colors, no-fit state.
- **Independent reviewer focus**: U1 (OUR `used` not reference summation) + U2 (OUR restore-on-failure re-init, not setting-only); the relocated OOM-safety gate (§4a.2/UI-7) — confirm it is RELOCATED, not lost.

---

## Visual evidence (Visual Evidence Required = YES)

8 integrated locales (incl. RTL `he`) + iPhone SE, per the WHAT U7 gate. Capture: meter
banner variants (warning + full), slider sheet (fit-chip zones fits/tight/won't-fit),
and the no-fit sheet state.

```json
[
  {"label": "warning banner + meter (en)", "prompt": "long chat near ~80% n_ctx", "look_for": "fullness meter ~80%, percent text, More room CTA"},
  {"label": "full banner + meter + pills (en)", "prompt": "overflow the context", "look_for": "meter ~100%, More room / or / New chat pills, error tint"},
  {"label": "slider sheet zones (en)", "prompt": "open sheet from full banner", "look_for": "slider, Fits/Tight/Won't-fit chip + tint, capacity ~words·GB, now + device-limit ticks, warn line"},
  {"label": "no-fit sheet (en)", "prompt": "device where no larger tier fits", "look_for": "confirm HIDDEN, explanatory copy, reachable New chat"},
  {"label": "RTL banner + sheet (he)", "prompt": "near-limit chat", "look_for": "ticks/labels mirrored to thumb travel (U7), no clipped warn line"},
  {"label": "iPhone SE sheet (en)", "prompt": "open sheet", "look_for": "no overflow/clipping at small width; fixed warn slot stable on drag"},
  {"label": "8-locale meter+sheet sweep", "prompt": "warning + sheet per locale (en, he, id, ja, ko, ms, ru, zh)", "look_for": "no truncation; warn line min-height holds across locale string lengths"}
]
```

---

## Deferred items

- Disclaimers / multi-image / alternative-model picker — out of scope (carried from prior slice).
- Cleanup-DEFERRED (`inferencing`/`isStreaming`/`isGenerating` derive from `agentUiState.status`) — untouched (`what.md` §5).

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| — | (initial draft) | — | — |
