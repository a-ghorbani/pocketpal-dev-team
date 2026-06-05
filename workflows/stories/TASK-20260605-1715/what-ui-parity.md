# Chat context-limit banner — UI-parity slice — WHAT

Story-scoped delta on `context/architecture/chat-flow.md` (§9f) and on the
already-approved data-layer contract `what.md` (this story). Continuation slice
on the SAME branch (`feature/TASK-20260605-1715`, PR #763). On promotion the
delta absorbs into §9f in the same PR.

**Conventions**: `(C)` current (verified from code on the PR branch), `(P)` proposal,
`(D)` decision (≤ 12-word rationale). Zero `(?)`.

**What this slice is**: a port-and-rewire of the prototype's richer visual design
onto OUR already-landed, disciplined data layer. It does NOT introduce a new flow,
does NOT change the resolver's trigger, and does NOT regress `what.md`.

---

## Drift check

minor drift in chat-flow §9f, repaired in this delta: §9f line 1047 asserts "There
is no n_ctx slider" and lines 1044-1046 say the **resolver** supplies the increase
target via `computeNextFitNCtx`. This slice ADDS a slider in the sheet and moves
target selection FROM resolver TO sheet; §9f's two sentences are corrected here. No
silently-violated invariant in live code — the landed code matches §9f today. (C)

---

## Design exploration

`DESIGN_EXPLORATION=NO` — design is fixed by the prototype
(`_context-warning-lab/index.html`) and the reference RN implementation
(worktree `TASK-20260526-2259`). This is a port, not a fresh design.

### Alternatives considered

- selected: port reference sheet/meter onto OUR data layer + OUR confirm path.
- rejected: adopt reference resolver wholesale — double-counts `used`, drops re-init.

---

## 1. Data model — delta on `what.md` §1

OUR `CompletionResultSnapshot` (C, `completionTypes.ts:115`) is UNCHANGED. `used`
stays `tokens_evaluated + tokens_predicted` (C, `completionTypes.ts:118`). The
reference's `tokensCached + tokensEvaluated + tokensPredicted` summation is NOT
ported (DOUBLE-counts ~2×; see Invariant U1). (C, D)

`BannerResolution` (C, `bannerVariantResolver.ts:24`) GAINS one field:

```
BannerResolution (existing)
  variant         : BannerVariant          (C)
  nextNCtx?       : number                 (C) — RETIRED (see §4a/§5); resolver no longer emits it
  heavyTalentName?: string                 (C)
  ratio?          : number   (P) used/effectiveNCtx clamped [0,1]; ONLY on context-full/context-warning
```

**`ratio` precision contract (P):**

- Computed and emitted ONLY on the two nCtx-reading branches (`context-full`,
  `context-warning`), the exact branches where `effectiveNCtx` is already guaranteed
  defined (`bannerVariantResolver.ts:76` gate) — so there is no divide-by-zero. (C/P)
- Value is `snapshot.used / effectiveNCtx`, clamped `[0,1]`. (P)
- NEVER computed or emitted on `context-remote-hedged`, `html-soft-cap`, or `none`
  (those branches don't read `effectiveNCtx`). `ratio` is `undefined` there. (P)
- The fullness **meter** (§4d) is the SOLE reader of `ratio`. Nothing else consumes it. (D)

The remote-no-meter behaviour (UE-e) follows directly from this: `ratio` is absent on
the remote-hedged branch, so the meter cannot render — reinforcing I7, not just relying
on it. (P)

**Discriminated-union decision (D-U1):** the resolver return stays the **minimal**
flat shape (`variant` string + optional `ratio`/`heavyTalentName`), NOT
the reference's rich per-variant union. `BannerRow` already computes presentation
(copy selection, tints) from `variant` + store reads; adding `ratio` is the only
new datum the meter needs. (D)

**Test migration (D-U1, load-bearing):** retiring `computeNextFitNCtx` /
`BannerResolution.nextNCtx` (§4a/§5) changes the resolver's test surface, NOT its
correctness contract:

- The resolver's variant-**precedence** tests (`bannerVariantResolver.test.ts`:
  full > warning > remote-hedged > html-soft-cap > none, the 0.80 edge, dismiss,
  no-model/undefined-nCtx suppression, remote-undefined-nCtx) stay intact — they
  don't assert on `nextNCtx`. (C)
- The two `nextNCtx` fit-gate tests (`:54` "offers nextNCtx when a larger fits",
  `:63` "hides the CTA when nothing larger fits") MOVE out of the resolver suite into
  the sheet's fit-classifier (§4c) / CTA-visibility (§4a.2) tests. These two encode the
  OOM-safety contract (D7/9g): no actionable increase target the device cannot fit. (C/P)
- CRITICAL: the OOM-safety assertion — "when no ladder tier the device can fit is
  larger than `currentNCtx`, the banner exposes NO actionable increase target" — is
  RELOCATED, not deleted. It now lives on the sheet's "fits"-zone CTA-visibility gate
  (§4a.2). Scenario UI-7 (§6) asserts this relocation explicitly. (P, load-bearing)

No new persisted fields. No new MobX-ephemeral store fields. No migration. (D)

### 1b. External shape

No new engine/wire fields. The sheet reads existing surfaces only:
`model.ggufMetadata.context_length` (C, `types.ts:479`),
`getModelMemoryRequirement(model, projModel, {...contextInitParams, n_ctx})`
(C, `memoryEstimator.ts:105`), `modelStore.availableMemoryCeiling` /
`largestSuccessfulLoad` (C, `ModelStore.ts:192,194`),
`DeviceInfo.getTotalMemory()` (C, lib present), `formatBytes` (C,
`formatters.ts:18`). All READS — no ModelStore refactor. (C)

---

## 2. Event flow — delta

Snapshot write boundaries UNCHANGED (`what.md` §2). New presentational events:

```
banner increase CTA tapped  → open IncreaseContextSheet (no precomputed target)   (P)
pal-load hint "More room"   → dismiss hint + open IncreaseContextSheet            (P)
slider moved (local state)  → recompute fit zone + capacity copy + warn line      (P)
sheet confirm               → OUR existing restore-on-failure reload path (UNCHANGED) (C)
```

---

## 3. State machine — delta

Banner state machine UNCHANGED (`what.md` §3). Sheet adds LOCAL UI state only:

```
sheet closed ─CTA→ sheet open (pickIdx = recommended fitting tier) ─slide→ pickIdx changes
sheet open ─confirm→ reloading (OUR confirm path) ─result→ closed + reload snackbar
```

`pickIdx` / `advancedOpen` / fetched `totalMemory` are **local component state**
(React `useState`), NOT MobX. The chosen tier is ephemeral UI state and dies with
the sheet. (D)

---

## 4. Contract

### 4a. Increase target ownership moves to the sheet

Today (C) the resolver computes a single doubling `nextNCtx` via
`computeNextFitNCtx`, the banner passes it to `onIncreaseContext(target)`, and the
sheet confirms that fixed target. **After this slice (P):**

1. The banner CTA opens the sheet with `(model, currentNCtx=effectiveNCtx)` — it no
   longer passes a precomputed target. `computeNextFitNCtx` / `nextNCtx` are RETIRED
   from the increase path. (P)
2. The CTA's **visibility** still gates on "does anything larger fit": the banner
   shows the increase CTA iff at least one ladder tier `> currentNCtx` is `fits`
   (the "fits" zone, §4c) — same OOM-safe intent as today's `nextNCtx !== undefined`.
   When nothing fits, the banner shows ONLY [New chat]. (P, preserves D7/9g)
3. The sheet owns tier selection via a slider over a context ladder. The user picks
   any tier; confirm passes the chosen tier to OUR existing reload path. (P)
4. **No-fit sheet is never a dead-end (P, resolves UE-b).** The sheet is reachable
   independently of the banner CTA — the pal-load hint's "More room" action (UI-5)
   opens it even when the banner CTA is hidden. When NO ladder tier `> currentNCtx`
   is `fits` (every stop is `won't_fit`/`tight`), the sheet does NOT show a permanently
   disabled confirm. Instead it shows an explanatory state — "this device can't fit a
   larger context; start a new chat instead" — with the confirm button **hidden** (not
   merely disabled) and a reachable **New chat** affordance in the sheet that routes to
   `chatSessionStore.resetActiveSession()` and closes the sheet. (P, chosen over
   suppressing the hint action so the sheet is self-consistent from every entry point.)

### 4b. Sheet content (ported from prototype + reference)

| Element | Source | Behaviour |
| --- | --- | --- |
| context ladder | `CONTEXT_LADDER` `[2048..131072]` (P, port) | filtered to tiers `> currentNCtx` AND `<= modelMaxCtx`; `modelMaxCtx` appended as rightmost stop |
| `modelMaxCtx` | `model.ggufMetadata.context_length` (C) | hard cap; fallback to ladder top when absent |
| slider | `@react-native-community/slider` (C, dep present) | index over filtered ladder; `disabled` while reloading or ladder length ≤ 1 |
| capacity readout | `formatBytes(memBytes,1)` (C) + `approxWords` (P) | "~N words · ≈X GB RAM"; words = `round(tokens*0.75/100)*100` |
| fit chip | 3-zone classifier §4c (P) | Fits / Tight / Won't-fit, semantic tint |
| device-limit status copy | furthest "fits" tier (P) | rendered as the status-line text (no track-overlay tick — see §4b note); shown when memory-constrained |
| warn line | adaptive copy §4c (P) | fixed min-height slot so slider never reflows mid-drag |
| Advanced disclosure | local `advancedOpen` (P) | raw `from→to` tokens + model max; collapsed by default |
| confirm | `t(confirm,{size})` "Set to NK" (P) | DISABLED when chosen tier is `won't-fit` OR reloading |

The slider supports an arbitrary `currentNCtx` (e.g. 250 — scenario B1 baseline),
since the ladder is filtered relative to it, not assumed to be a ladder member. (P)

**§4b note — track ticks dropped (reconciled):** the now / device-limit slider
TRACK ticks were over-specified. `@react-native-community/slider` exposes no
track-overlay API; positioning ticks would require RTL-fragile `onLayout` math, and
the OOM-safety they implied is already carried by the per-stop confirm gate (§4e U5)
and the no-fit state (§4a.4). The device-limit information is conveyed by the
status-line copy that already renders (`increaseContextTightStatus` etc.); the now
value is the slider's announced/displayed value. No track ticks are drawn. (D)

### 4c. Three-zone fit classifier

A pure, store-free helper, caller-injected exactly like OUR existing `canFitNCtx`
(C, `BannerRow.tsx:63`). Lives as a function in `IncreaseContextSheet` (or a colocated
helper module); it is a READ, not a ModelStore refactor. (P, D)

```
fitStatusFor(nCtx):
  req = getModelMemoryRequirement(model, projModel, {...contextInitParams, n_ctx})
  ceiling = max(largestSuccessfulLoad ?? 0, availableMemoryCeiling ?? 0)
  req <= ceiling                         → 'fits'      (P)
  totalMemory>0 && req <= totalMemory    → 'tight'     (P)
  otherwise                              → 'wont_fit'  (P)
```

This 3-zone classifier REPLACES/EXTENDS OUR binary `canFitNCtx` **for the sheet
only**. The banner CTA's visibility (§4a.2) uses the "fits" zone — semantically
identical to today's `canFitNCtx` (`req <= availableMemoryCeiling`), now expressed
through the same classifier's "fits" boundary. (P, D)

Warn-line copy by zone: `fits` → "Comfortable" / "Plenty of RAM" (memory-constrained
vs not); `tight` → "Past ~NK this device may run low… It can still try"; `wont_fit`
→ "~NK likely won't fit… Pick a smaller size". (P)

### 4d. Banner presentation (ported from prototype)

`BannerRow` GAINS, per the prototype, without changing the resolver trigger:

- A fullness **meter** (thin bar) on `context-warning` and `context-full`, width =
  `ratio * 100%`. Driven by OUR correct `ratio` (§1). (P)
- The **warning** banner gains an increase CTA (today it has dismiss only) when the
  fit gate (§4a.2) allows — resolves the warning/full CTA parity in the prototype. (P)
- CTA presentation: primary "More room" + secondary "New chat" with an "or"
  connector reading as alternatives (full variant); "More room" only (warning). (P)
- Escalated / heavy-talent / plain copy selection UNCHANGED (C, `BannerRow.tsx:147`). (P)

### 4e. Hard invariants (this slice)

- **U1 (used formula preserved)**: the meter `ratio` derives from OUR
  `snapshot.used = tokens_evaluated + tokens_predicted`. The reference's
  `tokensCached + …` summation is never introduced — it double-counts KV
  occupancy ~2×. (C/P, load-bearing)
- **U2 (restore-on-failure preserved)**: sheet confirm uses OUR landed path
  (`setNContext(target)` → `releaseContext` → `initContext`; on failure
  `setNContext(prior)` + re-`initContext`) (C, `IncreaseContextSheet.tsx:45-67`).
  The reference's confirm — which restores only the setting and leaves the model
  unloaded — is NOT ported. (C, load-bearing)
- **U3 (chat-surface scope only)**: no ModelStore `runtimeNCtx`/`runtimeContextSettings`
  rename, no `pendingReloadDiff`/`pendingReloadRequired`, no Settings reload indicator,
  no ModelCard "Loaded Context" badge, no Benchmark rewiring. Runtime n_ctx is read via
  `modelStore.activeContextSettings.n_ctx` exactly as today. (P, load-bearing)
- **U4 (trigger stays ratio-only)**: the ~0.80 `WARNING_THRESHOLD` and the
  `contextFull` freshness gate are untouched. Talent metadata still only drives copy
  + the pal-load hint (`what.md` I8). The new meter/slider/classifier are presentation
  and memory-fit READS — never the threshold. (C, preserves D4/I8)
- **U5 (sheet target ≠ OOM)**: per-stop, confirm is disabled when the chosen tier is
  `won't_fit`; when NO tier fits at all the sheet hides confirm entirely and offers New
  chat (§4a.4); the banner CTA is hidden when no tier fits (§4a.2). The device can never
  be asked to load a tier the classifier rejected. (P, preserves D7/9g)
- **U6 (sheet state is local)**: `pickIdx`/`advancedOpen`/`totalMemory` are component
  `useState`, never MobX/persisted. (D)
- **U7 (slider layout is stable + direction-correct)**: no track-overlay ticks are
  drawn (reconciled — see §4b note), so there is no LTR-coordinate hazard to mirror.
  The slider's end labels and the "from→to" advanced reading rely on the component's
  own RTL-aware rendering. The warn/status line occupies a fixed min-height slot (§4b)
  so the track never reflows mid-drag as zone copy changes length across locales. The
  8-locale + RTL + iPhone-SE visual-evidence gate verifies against this assertion.
  (P, load-bearing)

### 4f. Preserved invariants (from `what.md` / §9f — explicitly re-asserted)

Single-banner-slot precedence (I1), the I10 footer-suppression of the "cut off" text
under the sticky banner, all suppression rules (I5 no-model, per-draft dismiss), the
reader-side freshness gate, the snackbar focus gate + single-surface dismiss, and the
remote-no-increase rule (I7) are ALL preserved unchanged by this slice. (C)

### 4g. Component renders (delta)

| Component | Renders (new/changed) | Does NOT render |
| --- | --- | --- |
| `BannerRow` | meter on warning/full; "More room"/"New chat" pill CTAs with "or"; warning-banner increase CTA | the increase target (sheet owns it); fit arithmetic |
| `resolveBannerVariant` | + `ratio` on warning/full | JSX; the slider ladder; fit zones |
| `IncreaseContextSheet` | slider + ladder + capacity + fit chip + status/warn line + Advanced; OUR confirm path; no-fit explanatory state with New-chat + hidden confirm (§4a.4) | the variant; MobX writes; `canFitNCtx` for the banner CTA; track-overlay ticks (§4b note) |
| pal-load hint snackbar | gains a "More room" action → opens the sheet | becoming a banner (I6) |

---

## 5. Single-writer rule — delta

| Field | Single writer |
| --- | --- |
| sheet `pickIdx`/`advancedOpen`/`totalMemory` | `IncreaseContextSheet` local state only (P) |
| `modelStore.contextInitParams.n_ctx` | Settings slider AND sheet confirm (chosen tier) — UNCHANGED writer set (C) |

No new store writers. The sheet now passes a user-chosen tier instead of the
resolver's precomputed target; the WRITER (sheet confirm → `setNContext`) is the
same. (C)

Cross-store reads unchanged (`what.md` §5): resolver/`BannerRow`/sheet read
`modelStore`; `ChatSessionStore` does not read `ModelStore`. (C)

**Deferred cleanups**: `computeNextFitNCtx` / `BannerResolution.nextNCtx` become dead
once §4a lands — remove in this slice. (P)

**Note for the planner (not a contract change):** the sheet's current
`snapPoints={['35%']}` (C, `IncreaseContextSheet.tsx:75`) is sized for a single
confirm sentence; the ported slider + ladder + capacity + fit chip + status/warn line
+ Advanced disclosure will overflow it. Sizing is a HOW concern — leave the new value /
strategy to the planner.

---

## 6. Canonical scenarios (delta — new/changed only)

### UI-1. Meter reflects OUR used, not double-count
```
local n_ctx=4096; snapshot.used=3300 (warning)
─────
meter fill ≈ 81%; NOT the reference's ~162% (tokensCached not summed) (U1)
```

### UI-2. Sheet slider over ladder, capped at model max
```
currentNCtx=2048; model.ggufMetadata.context_length=32768; mid device
─────
slider tiers = {4096,6144,8192,…,32768}; fit chip + capacity update per stop;
device-limit conveyed by status-line copy at furthest "fits" tier (no tick);
confirm "Set to NK" (UI-3 zones)
```

### UI-3. Three-zone fit + OOM safety
```
chosen tier req <= ceiling → Fits (green); <= total → Tight (amber); else Won't-fit (red)
─────
Won't-fit → confirm DISABLED; banner CTA hidden when no tier fits (U5)
```

### UI-4. Confirm failure restores running model
```
sheet confirm 4096→8192; initContext throws
─────
setNContext(4096) + re-initContext; model loaded at 4096; failure snackbar (U2)
```

### UI-5. Pal-load hint "More room" opens sheet
```
heavy-talent pal loads below recommendation → hint snackbar with "More room" action
─────
tap → dismiss hint + open IncreaseContextSheet (resolves A4 action mismatch) (I6)
```

### UI-6. Arbitrary current n_ctx (B1 baseline)
```
currentNCtx=250 (not a ladder member)
─────
ladder filtered to tiers >250; slider works; current value announced/displayed (no tick) (4b)
```

### UI-7. OOM-safety assertion relocated, not lost
```
no ladder tier > currentNCtx is "fits" (device memory-constrained)
─────
banner exposes NO actionable increase target (CTA hidden, §4a.2);
the relocated fit-gate test asserts this on the sheet's "fits"-zone gate,
replacing the retired resolver `nextNCtx`-undefined test (D-U1, D7/9g)
```

---

## 7. State signals — delta

No new shared MobX signals. The only new datum crossing a boundary is
`BannerResolution.ratio` (resolver → `BannerRow`), derived from existing
`snapshot.used` + `effectiveNCtx`. (P)

---

## 8. Decisions (delta)

| ID | Decision | Rationale |
| --- | --- | --- |
| DU1 | Resolver stays flat + `ratio`; no rich union | Component maps presentation; precedence tests intact, fit-gate tests relocate |
| DU2 | Sheet owns tier selection via slider; retire `nextNCtx` | Slider needs full ladder; resolver shouldn't pick the value |
| DU3 | 3-zone classifier is a pure caller-injected READ in the sheet | Mirrors existing `canFitNCtx`; no ModelStore refactor |
| DU4 | Keep OUR `used` + restore-on-failure; do not port reference's | Reference double-counts and leaves model unloaded |
| DU5 | Sheet pick/advanced/totalMemory are local React state | Ephemeral per-open UI; never persisted (U6) |
| DU6 | Banner CTA opens sheet; visibility gates on "fits" zone | Same OOM-safe intent as today's `nextNCtx !== undefined` |

---

## 9. Edge cases (delta)

| ID | Edge case | Behaviour |
| --- | --- | --- |
| UE-a | `ggufMetadata.context_length` absent | ladder top is the cap; fallback to `CONTEXT_LADDER[last]` (4b) |
| UE-b | every tier > current is "won't fit" | banner CTA hidden (§4a.2). The sheet is still reachable via the pal-load hint's "More room"; it must NOT be a dead-end — see §4a.4. (P, U5) |
| UE-c | `getTotalMemory()` rejects/0 | tight boundary collapses; tiers are fits-or-won't only (4c) |
| UE-d | prompt-cache-reuse turn under-counts `used` | meter reads low; warning fires late not early — accepted (U1, `what.md` §1b) |
| UE-e | remote session | no meter, no slider, no increase CTA (I7); hedged advisory only |
| UE-f | sheet open during reload | slider + confirm disabled until result (4b) |

---

## 10. What we deliberately do NOT port from the reference (and why)

| Not ported | Why |
| --- | --- |
| `tokensCached + tokensEvaluated + tokensPredicted` `used` | double-counts KV ~2×; OUR `used` is correct vs llama.rn 0.12.4 (U1) |
| Reference confirm path (restore setting, leave model unloaded) | OUR path re-inits at prior n_ctx on failure (U2) |
| `runtimeNCtx` / `runtimeContextSettings` rename | out of chat-surface scope; read `activeContextSettings.n_ctx` (U3) |
| `pendingReloadDiff` / Settings reload-to-apply indicator | cross-screen scope creep (U3) |
| ModelCard "Loaded Context" badge / Benchmark rewiring | cross-flow; not this story (U3) |
| Reference rich discriminated-union `BannerVariant` | flat shape + `ratio` suffices; keeps resolver tests intact (DU1) |
| `CONTEXT_TIERS` doubling banner picker | sheet slider replaces it; `nextNCtx` retired (DU2) |
| `applyStickyFull` writer-side sticky carry | OUR reader-side freshness gate already covers it (`what.md` §3) |

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| — | (initial draft) | — | — |
| 1 | C1 — DU1 "tests intact" contradicts retiring `nextNCtx`; OOM-safety fit-gate tests must not be lost | CONCERN | FIXED — §1 D-U1 now splits precedence tests (stay) vs the two `nextNCtx` fit-gate tests (`:54`,`:63`, relocate to sheet §4a.2/§4c); OOM-safety assertion explicitly RELOCATED; new scenario UI-7 asserts the relocation |
| 1 | C2 — `ratio` precision: only on nCtx-reading branches, clamped, sole reader, tie UE-e to `ratio` absence | CONCERN | FIXED — §1 ratio-precision contract: emitted ONLY on context-full/context-warning (effectiveNCtx guaranteed by `:76` gate), clamped `[0,1]`, meter is sole reader, never on remote/html/none; UE-e tied to `ratio` absent on remote branch |
| 1 | C3 — no-tier-fits dead-end: pal-load hint "More room" can open a sheet with confirm permanently disabled | CONCERN | FIXED — chose (a): §4a.4 adds explanatory no-fit state with confirm HIDDEN (not disabled) + reachable New-chat affordance; UE-b + U5 updated |
| 1 | C4 — layout invariant for slider/ticks (RTL-mirrored positions, fixed-height warn slot) | CONCERN | FIXED — added U7; visual-evidence gate (8 locales + RTL + iPhone SE) carries the assertion |
| 1 | S5 — sheet `snapPoints={['35%']}` must grow for new content | SUGGESTION | NOTED for planner — sizing left to HOW (§5 planner note) |
| 2 | R4 — now/device-limit slider TRACK TICKS over-specified (no track-overlay API in `@react-native-community/slider`; RTL-fragile; OOM-safety already carried by per-stop confirm gate + no-fit state) | CONCERN | RECONCILED — dropped track ticks from §4b table, U7, §4g render row, §5 planner note, and scenarios UI-2 / UI-6; device-limit kept as status-line copy; added §4b note; U7 no longer carries tick-position mirroring. Implementation: stale `IncreaseContextSheet.tsx` tick comment removed |
