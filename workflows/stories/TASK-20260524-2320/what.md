# FOU-115 — Phase 2 shared component library (delta on `context/architecture/theming.md`)

**Story:** TASK-20260524-2320 · **Parent:** FOU-112 / FOU-115 · **Builds on:** FOU-114 (PR #732, promoted into `theming.md`).

This WHAT is a **delta** on top of `context/architecture/theming.md`. It does **not** restate FOU-114's tokens, theme builder, hydration gate, or invariants — those still hold verbatim. It adds:

1. A foundation key-set rename (the leftover patch at `/tmp/fou-114-token-rename-leftover.patch`), and the corresponding §1a doc update that must land in the same PR.
2. A new namespace `src/components/ui/` for the shared component library, built against the tokens layer.
3. A per-component **wrap-vs-rebuild** matrix (decision per family, recorded as D-markers).
4. The component-API contract (props / variants / sizes / state model / a11y / testID), the canonical-variant choices for duplicated DS entries, and the Sheet/Modal/Dialog working pattern (composed around the `Header` building block — Figma `3011:23955`).
5. The Paper-import discipline mechanism that replaces the retired `verify-paper-surface.js` snapshot guard: an ESLint `no-restricted-imports` `importNames` blocklist that grows entry-by-entry as each DS component ships.
6. The visual-parity snapshot strategy (what to snapshot, per state × mode, so Phase 3 swaps have a comparison baseline).
7. The `testID` + accessibility-label freeze contract for new components (the migration handshake Phase 3 relies on).

Phase 2 ships **library + snapshots only**. No screen is wired (Phase 3a–3g do that). The app must continue to render identically to today after this PR lands — every existing `src/components/*` import path keeps working.

---

## Conventions

- **(C)** = current behaviour, verified from code in this worktree
- **(P)** = proposal — open for the architect-critic to challenge
- **(D)** = decision (resolved, with one-line rationale)
- **(?)** = open question — none should remain at promotion to HOW

Story-promoted entries become **(C)** / **(D)** when this delta is absorbed into `theming.md`.

---

## 0. Scope & non-scope (delta on `theming.md` §0)

In scope this slice (additions to §0 "In scope"):

- **Folded foundation rename** (must be the FIRST commit of this PR): apply `/tmp/fou-114-token-rename-leftover.patch` (236 lines). Adds `spacing.xl=32`, renames `radius` to mirror Figma `Radius/*` keys (`None/XXS/XS/S/M/ML/L/XL/XXL` — drops `sm` step, renumbers `l` 32→20, adds `xxl=40`), renames `stroke.{hairline,s,m,l}` to `{xs,sm,md,lg}`. Touches only `src/theme/tokens/{spacing,radius,stroke,types}.ts` + `__tests__/scales.test.ts`. **Verified (C):** `git apply --check` passes against current `feature/TASK-20260524-2320` HEAD; `grep -rn "radius\.sm\b\|radius\.l\b\|stroke\.\(hairline\|s\|m\|l\)\b" src/` returns zero hits outside `src/theme/tokens/`. (P→D: see D1.)
- **A new namespace `src/components/ui/`** holding the Phase 2 component library, built against the tokens layer in parallel with the existing `src/components/*` (which keeps working unchanged). (P→D: see D2.)
- **Per-component wrap-vs-rebuild matrix** (§4f): rebuild visually-defining components from RN primitives (`Pressable` + token-bound styles); wrap `react-native-paper` for a11y-heavy form controls (`Switch`, `Checkbox`, `RadioButton`). (P→D: see D3.)
- **Sheet / Modal / Dialog working pattern**: a `Header` building block (Figma `3011:23955`) becomes the header primitive shared by `Sheet`, `Modal`, and `Dialog` (existing wrappers stay in place; a new DS-side `Sheet` composes Header + body + actions). One representative bespoke sheet is picked as the working pattern. (P→D: see D7.)
- **Paper-import discipline**: ESLint `no-restricted-imports` `importNames` blocklist (§4g). Seed list = **`['Surface']`** in this PR (proof-of-life — both consumers swap in the same PR; see D31 + §4g.7); the blocklist *contract* and *growth rule* also land in this PR. Subsequent DS components ship their replacement together with an entry in the blocklist (a per-component invariant — §4g.3). Replaces the retired `verify-paper-surface.js`. (P→D: see D4.)
- **Visual-parity snapshot strategy** (§6 + §4h): every DS component ships a `__snapshots__/` set covering `variant × size × {default, disabled} × mode ∈ {light, dark}`. Interactive states (pressed / focused) are NOT snapshotted in Phase 2 because Jest's `render()` cannot trigger them through the `style` callback path — they would produce cells byte-identical to `default`, which is misleading green coverage. Pressed/focused coverage is deferred to Phase 3 when a `fireEvent`-driven test harness lands per-component as call-sites migrate. Phase 3 swaps compare against the Phase 2 baseline snapshots; a per-DS-component snapshot delta must be reviewed when Phase 3 lifts each restyle.
- **Canonical-variant decisions** for the three duplicated families (Chips×3, Tabs×3, nav×2). (P→D: see D8–D10.)
- **`testID` + accessibility-label freeze contract** for new DS components (§4i): each DS component declares a stable `testID` prop with a documented default and a stable `accessibilityLabel` prop. Phase 3 wires these into the existing E2E selectors; the names must survive the swap. (P→D: see D11.)

Explicitly NOT in scope this slice (additions to §0 "Explicitly NOT in scope"):

- Wiring any DS component into a real screen. (Phase 3a–3g.)
- Deleting any `src/components/*` file or its tests. (Phase 3 swaps, then Phase 4 cleanup.)
- Removing existing `react-native-paper` imports outside the **two `Surface` consumers** (`src/components/UsageStats/UsageStats.tsx`, `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`) which swap to `Surface` in this PR as proof-of-life. Beyond `Surface`, the `no-restricted-imports` blocklist grows only as each subsequent DS component lands its replacement (Phase 3).
- New native deps. **NATIVE_CHANGES = NO.** If during HOW/implementation a chosen icon font or asset registration requires native linking, flip to YES and re-route through the orchestrator — but the WHAT does not commit to any new native dep.
- Migrating `MD3Theme`/`MD3Colors`/`MD3Typescale` consumers (carried forward from `theming.md` §5 #5 — still FOU-123).
- Sheet/Modal/Dialog rework of existing call-sites. The existing `src/components/Sheet/Sheet.tsx` and `src/components/Dialog/Dialog.tsx` wrappers stay in place. The DS `Sheet` is built alongside; Phase 3 slices migrate call-sites incrementally.
- Designing for components not in the Linear ticket's component list (e.g. drawer rows, snackbars, FAB).

---

## 1. Data model (delta on `theming.md` §1a — foundation rename)

The folded patch updates the token key set. Once promoted, `theming.md` §1a must read:

```
  spacing: TokenSpacing
    none: 0, xxs: 2, xs: 4, s: 8, sm: 12, m: 16, ml: 20, l: 24, xl: 32   // NEW: xl

  radius: TokenRadius
    none: 0, xxs: 2, xs: 4, s: 8, m: 12, ml: 16, l: 20, xl: 32, xxl: 40
    //  ↑ no `sm` step (Figma jumps S(8)→M(12));
    //    `m` is 12 (was 16), `ml` is 16 (was 20), `l` is 20 (was 32),
    //    `xl` is 32 (was 40), `xxl` is 40 (new).
    //    Mirrors canonical Figma Radius/None|XXS|XS|S|M|ML|L|XL|XXL.

  stroke: TokenStroke
    xs: 0.5, sm: 1, md: 1.5, lg: 3
    // Renamed from {hairline, s, m, l} to mirror canonical Figma Stroke/*.
```

The two key correctness facts that motivate the rename (must appear in the absorbed §1a):

- **Single source of truth = Figma name.** A Phase 3 designer spec saying "Radius/L" maps directly to `theme.radius.l = 20`. Before the rename, that spec would have read `theme.radius.l = 32`, which is the Figma value for `Radius/XL`. The rename closes a silent visual-regression vector.
- **No `radius.sm` exists** — Figma's `Radius/*` collection has no SM step (it jumps S(8) → M(12)). Code that previously typed `theme.radius.sm` had no canonical meaning; the rename surfaces that as a compile error.

The §1a Glossary is otherwise unchanged. The §1c (color migration) and §1d (typography migration) tables are unchanged.

### 1b. Data model — DS component layer (new section)

The DS layer is a sibling of the tokens layer:

```
src/components/ui/
  index.ts                          // public barrel — DS surface for Phase 3
  primitives/
    Pressable/                      // (P) RN Pressable + state-layer overlay; the building block for every interactive DS component
    Stack/                          // optional layout primitive — defer if unused
  Surface/                          // background + radius + optional elevation; Paper-free; **Phase 2 swap**: both Paper-Surface consumers migrate in this PR (see §4g.7)
  Header/                           // new — Figma 3011:23955; the header building block for Sheet/Modal/Dialog
  Button/                           // §4f row
  IconButton/                       // §4f row
  Input/                            // §4f row (multiple variants — single/multi-line, with/without label)
  Chip/                             // §4f row
  Card/                             // §4f row
    CardList/                       // (P) Card sub-namespace for list variant
  Tabs/                             // §4f row
  BottomNavBar/                     // §4f row
  RadioButton/                      // §4f row (Paper-wrap)
  RadioSection/                     // §4f row (composite — built on RadioButton)
  Checkbox/                         // §4f row (Paper-wrap)
  Switch/                           // §4f row (Paper-wrap)
  Label/                            // §4f row — Informational / Status labels
  CategoryBadge/                    // §4f row — Category badges
  Dropdown/                         // §4f row — Category dropdowns
  MessageContent/                   // §4f row — Message content variants
  Sheet/                            // §4f row — new DS sheet composed of Header
  Modal/                            // §4f row — full-screen modal composed of Header
  Dialog/                           // §4f row — confirmation dialog composed of Header
```

Each `<Component>/` folder owns:

```
<Component>.tsx                     // implementation
styles.ts                           // token-bound styles only (no raw hex, no raw px)
index.ts                            // re-export
__tests__/
  <Component>.test.tsx              // behaviour + a11y assertions
  __snapshots__/
    <Component>.test.tsx.snap       // variant × size × state × mode snapshots
```

Public DS surface is `src/components/ui/index.ts`. Phase 3 imports from `'@/components/ui'` (alias TBD by planner; not a WHAT concern). No DS-internal file is imported across components except via `primitives/`.

Stored on disk: nothing new. The DS layer is pure code. Computed at render: every style is a function of the resolved `Theme` from `useTheme()`.

**Glossary — additions:**

- **DS layer** — `src/components/ui/`. The Phase 2 shared component library. Built against `useTheme()`. Distinct from `src/components/*` (the legacy components, which keep working through Phase 3 swaps and are removed in Phase 4 / FOU-123).
- **Header building block** — the DS `Header` component at `src/components/ui/Header/`. Figma node `3011:23955`. Reused as the header primitive by `Sheet`, `Modal`, and `Dialog`.
- **State layer** — the token-defined opacity overlay (`stateLayerOpacity`, `pressedStateOpacity`, etc. from `theme.colors.*`, already in `theming.md` §1a) applied by the `Pressable` primitive on `pressed` / `hovered` / `focused`.
- **Visual-parity snapshot** — a serialized React tree of a DS component for a specific `(variant, size, state, mode)` tuple. Used by Phase 3 swaps to detect unintended visual change.

---

## 1c. External shape

No wire format changes. The DS layer is internal. The only external touchpoints remain those documented in `theming.md` §1e (bundled font binary set). No new font asset, no new icon set, no new native module is added in this slice. (If implementation discovers a need, the orchestrator is re-engaged — see §0.)

---

## 2. Event flow

No event flow changes. DS components are stateless leaves: each reads `useTheme()` synchronously, computes styles, renders. Pressable state (`pressed`, `hovered`, `focused`) is local to each `Pressable` primitive instance and produces a single re-render via `Pressable`'s `style` callback.

Sheet/Modal/Dialog mount/dismiss flow is unchanged from the existing `src/components/Sheet/Sheet.tsx` and `src/components/Dialog/Dialog.tsx` (gorhom + Paper Portal). The DS `Sheet`/`Modal`/`Dialog` wrappers reuse those underlying mechanisms and add only structural composition (Header + body + actions).

---

## 3. State machine

No state-machine changes. DS components are stateless or carry only the trivial interactive states (`default → pressed → released`, `default → focused → blurred`, `default ↔ disabled`) handled by `Pressable` or Paper's wrapped primitives. No new global state, no new persisted field, no new MobX writer.

---

## 4. Contract

### 4a. The folded foundation rename (single commit, FIRST in PR)

1. The patch applies atomically — five files, no other touches. The first commit message must record this as a token-key-set rename motivated by Figma-name parity, citing the §1a delta.
2. The same PR updates `context/architecture/theming.md` §1a to the new key set (see §1 above) AND removes the now-stale comment "(currently withOpacity-derived, FOU-115)" from `theming.md` §1a `colors.surfaceContainer*` — that work is tracked here as a deferred cleanup (§5 below), not done in this slice. The text-only doc update for the §1a tables IS done here.
3. The patch carries its own test (`scales.test.ts`) — 12 assertions pass. No other tests are expected to break (zero consumers outside the token module — verified).

### 4b. The DS component layer (`src/components/ui/`)

1. Every DS component reads tokens through `useTheme()` only — no direct token-module imports, no raw hex, no raw px in `styles.ts`.
2. Every interactive DS component is built on the `Pressable` primitive in `primitives/Pressable/`. The primitive is the single writer of pressed/hovered/focused state-layer overlays — components do not re-implement `Pressable`'s `style` callback, they pass `variant`/`size` and the primitive resolves to a token-bound style.
3. DS components are **observation-free**: they do not import `mobx-react`, `observer`, or any store. Stateful integration is the caller's responsibility in Phase 3.
4. DS components do not import from `src/components/*` (the legacy namespace). The two layers are siblings; the dependency is one-way — `src/components/*` may eventually import from `src/components/ui/` during Phase 3 migration, never the reverse.
5. The `Header` component is the single source of structural truth for all DS overlay headers (Sheet, Modal, Dialog). A DS overlay that needs a header MUST compose `<Header>`; bespoke headers are forbidden inside the DS layer.
6. DS component public APIs follow the `variant` + `size` + `state` axis convention (§4c). New variants are added to the existing axis, not as new components.
7. Every DS component file exports a single named React component (no default exports, matching the rest of `src/`). Same for `index.ts` re-exports.

### 4c. Component API contract (semantic shape)

Every DS component exposes the same shape, varying only in which axes apply:

```ts
type CommonDSProps = {
  testID?: string;                                   // see §4i freeze contract
  accessibilityLabel?: string;                       // see §4i
  accessibilityHint?: string;
  accessibilityRole?: AccessibilityRole;             // sensible default per component
  style?: StyleProp<ViewStyle>;                      // outer style override (additive, not destructive)
  disabled?: boolean;
};

type DSComponentProps<V extends string, S extends string> = CommonDSProps & {
  variant?: V;                                       // visual-family axis; default declared per component
  size?: S;                                          // size axis; default declared per component
  // ...component-specific props (label, onPress, value, etc.)
};
```

Rules:

1. `variant` and `size` are **closed string unions per component**, not free strings. Adding a variant means widening the union in `Component.tsx`.
2. The `variant`/`size` defaults are declared in `Component.tsx` and documented in the JSDoc above the component. (P) The defaults match the most common Figma render in the canonical file.
3. Token-binding pattern: `styles.ts` exposes `createStyles(theme, {variant, size, state, mode})` and is the only place that maps a `(variant, size, state)` triple to token reads. The component file never reads tokens directly.
4. State model: `Pressable` resolves `pressed` (the only interactive state RN's `Pressable` exposes via its `style` callback on mobile) and passes it to `createStyles` via the `state` field. `disabled` is part of the same state model. `hovered` and `focused` are platform-conditional and NOT exposed by `Pressable` on mobile; consumers needing focus on Input drive it via `onFocus`/`onBlur` directly (Input owns its focused render branch). Components that wrap Paper (Switch / Checkbox / RadioButton / Dropdown) delegate `pressed`/`focused` to Paper — they expose only `disabled` + `value` on their public API.
5. Accessibility props:
   - `accessibilityLabel` is **required** for interactive components (`Button`, `IconButton`, `Chip`, `Switch`, `Checkbox`, `RadioButton`, `Tabs` items, nav-bar items). **Primary enforcement = TypeScript prop constraint** (D34): the public props type for each such component is a discriminated union of the shape `Props = (Common & {accessibilityLabel: string}) | (Common & {label: string})`. Either `label` (which doubles as the visible/spoken label) OR an explicit `accessibilityLabel` must be supplied at every call-site; the compiler rejects calls that supply neither. Consumers may pass BOTH (e.g. visible label `'Save'` + override `accessibilityLabel='Save changes to model'`) — both intersect the `Common` half and satisfy the union.
   - **Dev-only `__DEV__` runtime fallback**: components additionally guard against the case where types are bypassed (dynamic prop spreads, generic wrappers, `any`-typed consumers). The runtime check warns (not throws) if both labels are absent at render time. The warning is the fallback, not the primary mechanism.
   - `accessibilityRole` defaults: `Button` → `'button'`, `IconButton` → `'button'`, `Chip` (interactive variant) → `'button'`, `Switch` → `'switch'`, `Checkbox` → `'checkbox'`, `RadioButton` → `'radio'`, `Tabs` item → `'tab'`, nav-bar item → `'tab'`. Labels/Badges → `'text'` or `'none'`. `Header` → `'header'` (see §4i defaults table footnote).
   - Components that wrap Paper inherit Paper's `accessibilityState` plumbing (already correct in v5.14.5 (C)).
6. `testID` policy: see §4i.

### 4d. The Header building block (Figma `3011:23955`)

1. `Header` is a single component with the public shape:

```ts
type HeaderProps = CommonDSProps & {
  title?: string;
  subtitle?: string;
  leading?: ReactNode;                       // typically an IconButton (back/close); component picks slot semantics, not the consumer
  trailing?: ReactNode;                      // typically an IconButton (close / action) or up to N inline actions
  align?: 'leading' | 'center';              // (P) default 'leading' per Figma 3011:23955
};
```

2. `Header` reads exactly two typography tokens: `theme.typography.titleM` for `title`, `theme.typography.captionS` for `subtitle`. No font-family or weight is set inline.
3. `Header` reads `theme.spacing.m` for horizontal padding and `theme.spacing.s` for vertical padding (P — exact values to be confirmed against Figma `3011:23955` during HOW; this WHAT only fixes that the source is a single spacing token, not a raw number).
4. `Header` exposes `testID="ui-header"` as the documented default (§4i). Consumers may override.

### 4e. The DS Sheet / Modal / Dialog composition pattern

All three overlay types share the **same composition shape**:

```
<Sheet | Modal | Dialog>
  <Header title=… subtitle=… leading=… trailing=… />
  <Body>                                  // free-form children
  <Actions primary=… secondary=… />       // optional; standard CTA row
```

Rules:

1. The three overlay types differ ONLY in their underlying presentation mechanics: `Sheet` uses `@gorhom/bottom-sheet` (existing dependency, (C) `src/components/Sheet/Sheet.tsx`); `Modal` uses Paper's `Portal` + a full-screen `View`; `Dialog` uses Paper's `Portal` + a centered surface (existing dependency, (C) `src/components/Dialog/Dialog.tsx`). The presentation mechanism is a DS implementation detail; consumers see the same `Header + body + actions` shape across all three.
2. `Sheet`, `Modal`, `Dialog` do NOT render their own header markup. They MUST compose `<Header>`. Bespoke header markup inside any of the three is forbidden — invariant I_UI3 below.
3. The representative bespoke sheet picked as the working pattern is **the existing `ChatPalModelPickerSheet`** (P → D7) — it has a title row, a body that scrolls, and an action row, exercising the full Header + Body + Actions composition. The DS Sheet must render that pattern unchanged when given the same data shape.
4. `Actions` is a small sub-component of each overlay type, exposing `primary?: ActionConfig` and `secondary?: ActionConfig` where `ActionConfig = {label: string; onPress: () => void; loading?: boolean; disabled?: boolean; destructive?: boolean}`. No more than two actions in the standard slot; bespoke overlays needing more compose their own actions in the body.
5. The existing `src/components/Sheet/Sheet.tsx` and `src/components/Dialog/Dialog.tsx` files **stay in place** throughout Phase 2. The DS variants are **net-new files** at `src/components/ui/Sheet/`, `src/components/ui/Modal/`, `src/components/ui/Dialog/`. Phase 3 migrates call-sites; Phase 4 removes the legacy files.

### 4f. Wrap-vs-rebuild matrix (the central architectural decision of this slice)

Per the brief's hypothesis: rebuild visually-defining components from RN primitives, wrap `react-native-paper` for a11y-heavy form controls. Decision per family below. **(D) markers** anchor the rationale.

| Family | Figma node(s) | Decision | Rationale |
| --- | --- | --- | --- |
| `Button` | `746:26337`, `746:26338` | **Rebuild** (P→D13) | Visually defining (radius, padding, weight, state layer). Paper's `Button` ships MD3-specific ripple + label-uppercase quirks that fight the design. Pressable + token styles is straightforward. |
| `IconButton` | derived from icon set `746:26281` | **Rebuild** (P→D14) | Same as Button. Paper's `IconButton` enforces a circular hit area + MD3 state layer that doesn't match the canonical squarish IconButton in `746:26337`. |
| `Input` | `161:9020` | **Rebuild** (P→D15) | The Figma input has bottom-divider + helper-text + leading/trailing slot variants that don't map to Paper's `TextInput` (which forces flat/outlined modes and pads the label). Build directly on RN `TextInput`. |
| `Chip` | `890:29153`, `768:29722` | **Rebuild** (P→D16) | Chip variants in the canonical file (pill, badge, selectable) differ in radius + leading-icon slot + state in ways that fight Paper's `Chip`. |
| `Card` / `CardList` | `764:27682` | **Rebuild** (P→D17) | Pure visual primitive: surface + radius + padding + optional border. Trivial to build from `View` + tokens. Paper's `Card` ships `Card.Title` / `Card.Content` slots that don't match the DS shape. |
| `Tabs` | `764:27807`, `408:11226` | **Rebuild** (P→D18) | Custom underline / state-layer behaviour. Paper's `SegmentedButtons` doesn't reach the Figma look. |
| `BottomNavBar` | `143:4685`, `764:28530` | **Rebuild** (P→D19) | Custom icon-label stack + state-layer indicator. The current screen uses React Navigation; the DS `BottomNavBar` is a presentational shell — navigation wiring happens in Phase 3. |
| `RadioButton` | `888:30130` | **Wrap Paper** (P→D20) | A11y-heavy form control. Paper's `RadioButton` handles `accessibilityRole="radio"`, group state, and pressed/focused atomically. The visual delta is small (color + size) and absorbed by token-bound style overrides. |
| `RadioSection` (composite) | `888:30157` | **Rebuild on top of wrapped RadioButton** (P→D20) | Composite layout (label + helper + radio + divider). The radio inside is the wrapped Paper one. |
| `Checkbox` | `224:17932` | **Wrap Paper** (P→D21) | A11y-heavy form control. Same rationale as RadioButton. |
| `Switch` | (no node ID in brief — Figma DS section) | **Wrap Paper** (P→D22) | A11y-heavy form control. Paper's `Switch` handles `accessibilityRole="switch"`, value semantics, and platform-specific (iOS/Android) thumb-track behaviour we do not want to re-implement. |
| `Label` (Informational / Status) | `768:27628` | **Rebuild** (P→D23) | Pure visual primitive: small text + colored background + optional icon. Trivial from `View` + `Text` + tokens. |
| `CategoryBadge` | (DS — no specific node ID in brief) | **Rebuild** (P→D24) | Same as Label — visual primitive. |
| `Dropdown` (category dropdown) | (DS — no specific node ID in brief) | **Wrap Paper** (P→D25) | The DS dropdown is a trigger-Pressable opening Paper's `Menu` for the popup positioning ((C) — already in `Selector.tsx`). The trigger styling is rebuilt against tokens, but the Menu popup itself is a thin Paper wrapper (positioning, dismiss, item rendering). Reclassified from Rebuild to Wrap-Paper post-Round-1 to be honest about the Paper dependency (the prior Rebuild classification implicitly assumed the trigger-only delta was enough — the popup branch was still Paper-coupled via the legacy `src/components/Menu` import, breaching the one-way dependency rule §4b.4). Treated as the 4th wrap-Paper family alongside Switch/Checkbox/RadioButton; its folder gets the same per-file ESLint allowance when `Menu` enters the blocklist in Phase 3. |
| `MessageContent` variants | `128:3113` | **Rebuild** (P→D26) | Message bubbles are entirely PocketPal-bespoke (no Paper equivalent). The new DS variant unifies the variants in `128:3113` under a single token-bound API; the existing `src/components/Message/*` continues to render. |
| `Surface` (DS primitive) | (no specific node ID — generic surface) | **Rebuild** (P→D32) | Pure visual primitive: `View` + background color + radius + optional elevation shadow. Both Paper-`Surface` consumers (`UsageStats`, `PalDetailSheet`) only use `elevation={0}` with a `style` override — a trivial token-bound `View` matches. Promoted to Phase 2 scope to seed the Paper-import blocklist with a real entry (see D31). |
| `Sheet` | uses `Header` `3011:23955` | **Compose existing `@gorhom/bottom-sheet`** (P→D27) | Sheet mechanics are non-trivial and well-handled by gorhom (the existing dep). DS adds Header + Body + Actions composition; does not re-implement gorhom. |
| `Modal` | uses `Header` `3011:23955` | **Compose Paper `Portal` + `View`** (P→D28) | Paper Portal is the existing full-screen-overlay primitive ((C) — used by `Dialog`). DS adds Header + Body + Actions composition. |
| `Dialog` | uses `Header` `3011:23955` | **Compose Paper `Portal` + centered `Surface`** (P→D29) | Same rationale as Modal. The existing `src/components/Dialog/Dialog.tsx` is the structural reference. |
| `Header` | `3011:23955` | **Rebuild** (P→D30) | Net-new building block. Pure presentational shell. |

Summary of the wrap-vs-rebuild call: **rebuild 14 families** (including new `Surface` primitive — see D32), **wrap-Paper 4 families** (`Switch`, `Checkbox`, `RadioButton`, `Dropdown`). Compositions of existing libs (gorhom for Sheet, Paper Portal for Modal/Dialog) are not "wrap Paper" in the discipline sense — see §4g.

### 4g. Paper-import discipline (`no-restricted-imports` `importNames` blocklist)

This replaces the retired `scripts/verify-paper-surface.js` snapshot guard. Mechanism:

1. The repo's existing `.eslintrc.js` already configures `no-restricted-imports` (C — currently used for `**/__automation__/**` patterns, lines ~40-65). Extend it with a `paths` entry targeting `'react-native-paper'` and an `importNames` array.
2. The Phase 2 PR **seeds the blocklist empty**. The blocklist is the *contract*; growth is per-component and is the per-component invariant I_UI4 (§4j) — "If a DS component declares it replaces Paper's `X`, the same PR adds `'X'` to the `importNames` blocklist, OR a follow-up Phase 3 swap PR adds `'X'` once all call-sites are migrated."
3. (P→D31) Choice between adding entries **as the DS component lands** vs **as call-sites migrate in Phase 3**: ADD AT PHASE 3, per component. Rationale: in Phase 2 the DS component exists but no screen uses it. Banning the import while 100+ call-sites still need the Paper one would block any incidental fix to those screens. The discipline kicks in slice by slice as Phase 3 swaps each family.
4. The blocklist's "final state" (what must be banned by the time Phase 4 / FOU-123 lands) is the inversion of the locked thin set: `'ActivityIndicator', 'Card', 'Checkbox', 'Chip', 'Dialog', 'Divider', 'DividerProps', 'Drawer', 'FAB', 'List', 'MD3Theme', 'Menu', 'Paragraph', 'ProgressBar', 'RadioButton', 'SegmentedButtons', 'Snackbar', 'Surface', 'Switch', 'TextInput', 'Tooltip', 'useTheme'`. The locked thin set (never banned) is `Text`, `Button`, `IconButton`, `Portal`, `Provider` (matches `theming.md` §4c #3 and `FOU-112-rollout.md` §1).
5. The ESLint rule is the **only** enforcement vector for Paper-import discipline in Phase 2+ (the snapshot guard `verify-paper-surface.js` (C — does not exist in this worktree) is gone).
6. The rule must be configured to allow `import {...} from 'react-native-paper'` **inside `src/components/ui/`** for the three wrap-Paper components (`Switch`, `Checkbox`, `RadioButton`). Mechanism: a per-file ESLint override that re-allows the relevant `importNames` for `src/components/ui/{Switch,Checkbox,RadioButton}/**`. (P — actual ESLint config shape is a planner concern; the contract here is "DS wrap-Paper files are the only legal place those Paper imports live by Phase 4".)
7. **Phase 2 seed = `['Surface']`** (proof-of-life). Both call-sites (`src/components/UsageStats/UsageStats.tsx`, `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`) MUST swap to `Surface` in this PR, in the same commit that adds `'Surface'` to the blocklist. Verified (C): the only two Paper-`Surface` imports in `src/` are those two files; both pass `elevation={0}` with a `style` override, so the DS rebuild covers them. This is the only Paper symbol banned at end of Phase 2; subsequent entries accrue in Phase 3.

### 4h. Visual-parity snapshot strategy

#### 4h.1 Mechanism

1. Each DS component ships a Jest snapshot test at `src/components/ui/<Component>/__tests__/<Component>.test.tsx`. The test uses `@testing-library/react-native`'s `render()` + `toJSON()` + `toMatchSnapshot()` (existing test infra, (C) — already used by `ErrorSnackbar`).

#### 4h.2 Bounded matrix (rebuild families)

For each **rebuilt** DS family (the 14 of §4f matrix marked Rebuild), the snapshot matrix is bounded as follows — not a full cartesian product:

2. **Baseline axis** (always snapshotted): `variant × size × {default, disabled} × mode ∈ {light, dark}`. This is the visual-parity contract — every (variant, size) under both static states under both modes. The `disabled` cell is rendered by passing `disabled` through to the component, not by labelling alone — the snapshot factory MUST consume `cell.state` and forward `disabled={state === 'disabled'}` (or the equivalent component-specific prop).
3. **Pressed / focused axes** — explicitly NOT snapshotted in Phase 2. The matrix helper renders through Jest's `render()` which does not trigger Pressable's pressed state via the style callback path, and Input's focused state cannot be reached without `fireEvent.focus`. Emitting these cells would produce snapshots byte-identical to `default` — misleading green coverage. Pressed/focused signal lands in Phase 3 via a per-component `fireEvent`-driven test harness paired with each call-site swap.
4. **Hover** is not snapshotted (mobile-first; `hoverStateOpacity` token is preserved by I_UI1 and remains a token-level invariant; runtime exercise is web-only and out of Phase 2 scope).

#### 4h.3 Wrap-Paper families (Switch / Checkbox / RadioButton / Dropdown) — restricted axes

For the **wrap-Paper** families (`Switch`, `Checkbox`, `RadioButton`, `Dropdown`), the matrix is restricted further — pressed/focused are Paper internals and are NOT snapshotted (testing them would test Paper, not the DS layer):

6. Matrix = `variant × {default, disabled} × mode ∈ {light, dark}` × value axis where applicable. The `size` axis is dropped for the wrap-Paper trio (Switch/Checkbox/RadioButton): Paper owns sizing and the DS layer does not widen it, so emitting size cells would produce duplicate snapshots. The trio's public `size` prop is dropped accordingly (post-Round-1 finding).
   - `Switch`: also `value ∈ {true, false}` (visual state varies by value).
   - `Checkbox`: also `value ∈ {true, false}`.
   - `RadioButton`: also `value ∈ {true, false}`.
   - `Dropdown`: keeps `size` axis (the rebuilt trigger has a size variant); the Paper-coupled popup is exercised via behavioural tests, not snapshots.
7. **Explicitly NOT snapshotted** for the wrap-Paper families: `pressed`, `focused`, `hovered`. These are Paper-owned interactive states; snapshotting them would couple DS tests to Paper's internal state-layer mechanics, defeating the wrap pattern. This restriction is encoded in the scope boundary of invariant I_UI5 (§4j).

#### 4h.4 Theme construction in tests

8. Each snapshot is rendered against a real `Theme` from `buildTheme({mode, language})` (NOT a mocked one). The token-rename absorption + the new component contract are validated by the same snapshot run. The fixture extension needed to expose `{mode, language}`-parameterized themes to tests is decided in §4h.6 below.

#### 4h.5 Phase 3 swap contract

9. Snapshots are **the Phase 3 comparison baseline**. When a Phase 3 slice swaps a screen from a legacy component to its DS sibling, the relevant DS snapshots MUST NOT change in that PR — any DS-side visual change must be a separate, intentional commit. This is invariant I_UI5 (§4j).
10. Non-Latin font-fallback canary: each component additionally snapshots ONE representative `variant × size=<default> × state=default × mode=light × language='fa'` permutation. This exercises the typography-fallback path through `buildTheme` (Fraunces → Inter for non-Latin). It does **NOT** exercise `I18nManager.isRTL` layout direction — Phase 2's helper does not call `I18nManager.forceRTL(true)` because the global toggle is irreversible across tests in the same process; layout-direction snapshots are deferred to Phase 3 with a proper per-test isolation harness. The canary's contract in Phase 2 is "font metrics + character coverage", not "writing direction". If the canary diverges from the LTR snapshot beyond character/font differences, that's a bug.

#### 4h.6 Theme fixtures for the snapshot matrix

11. **(D33)** Extend `jest/fixtures/theme.ts` with a `themeFixtures.byMode(mode).byLocale(language)` factory that calls `buildTheme({mode, language})` and memoizes by `(mode, language)`. DS snapshot tests import this factory and parameterize their `render()` calls. Rationale: the current fixture only exposes `lightTheme`/`darkTheme` for `language='en'` (C — verified: `jest/fixtures/theme.ts` exports `lightTheme = buildTheme({mode:'light',language:'en'})` and `darkTheme = buildTheme({mode:'dark',language:'en'})`); the DS snapshot matrix needs `language='fa'` too. The factory approach centralizes memoization (each `(mode, language)` theme is built once per test process) and keeps the contract uniform — every DS test reaches the theme through the same fixture surface. The alternative — per-file `buildTheme({mode, language})` calls in each DS test — duplicates the import and forfeits memoization; rejected on DRY grounds. Concrete factory shape and naming live in HOW.

### 4i. `testID` + accessibility-label freeze contract

This is the migration handshake the rollout doc §5 calls "testID freeze". Phase 3 wires DS components into screens; Appium E2E selectors must survive the swap.

1. Every interactive DS component declares a stable `testID` PROP with a documented default. Defaults table:

| Component | Default `testID` | `accessibilityRole` default |
| --- | --- | --- |
| `Button` | `'ui-button'` | `'button'` |
| `IconButton` | `'ui-icon-button'` | `'button'` |
| `Input` | `'ui-input'` | `'none'` (RN TextInput has its own a11y) |
| `Chip` | `'ui-chip'` | `'button'` (interactive) / `'text'` (display) |
| `Tabs` (root) | `'ui-tabs'` | `'tablist'` |
| `Tabs` (item) | `'ui-tab-item-<value>'` (templated by item value) | `'tab'` |
| `BottomNavBar` (root) | `'ui-bottom-nav'` | `'tablist'` |
| `BottomNavBar` (item) | `'ui-bottom-nav-item-<value>'` | `'tab'` |
| `RadioButton` | `'ui-radio-<value>'` | `'radio'` |
| `Checkbox` | `'ui-checkbox'` | `'checkbox'` |
| `Switch` | `'ui-switch'` | `'switch'` |
| `Header` | `'ui-header'` | `'header'` ¹ |
| `Card` | `'ui-card'` | `'none'` |
| `Surface` | `'ui-surface'` | `'none'` |
| `Sheet` | `'ui-sheet'` | n/a (overlay) |
| `Modal` | `'ui-modal'` | n/a |
| `Dialog` | `'ui-dialog'` | n/a |

¹ **D35** — `Header` defaults `accessibilityRole='header'` deliberately matching RN navigation headers. Rationale: assistive tech (VoiceOver, TalkBack) treats both as document landmarks; sharing the role lets users navigate by landmark consistently across native nav headers and DS overlay headers. The alternative — defaulting to `'none'` to avoid landmark collision — would force every consumer to opt in, fragmenting a11y behaviour across overlays. The collision is desirable, not accidental.

2. Defaults are documented in the JSDoc above each component. Consumers override per call-site (this is the Phase 3 freeze hook — Phase 3 passes the SAME `testID` the legacy component used at that call-site, so Appium selectors don't break).
3. Naming policy: `ui-<kebab-component-name>` and `ui-<kebab-component-name>-<discriminator>` for repeated items. This namespace prefix lets Appium selectors disambiguate DS instances from legacy ones during the Phase 3 transition window.
4. `accessibilityLabel` is a required prop on the components flagged in §4c.5. **Primary enforcement = TypeScript discriminated-union constraint** (D34): the public Props type for each interactive DS component forces the consumer to supply `label`, `accessibilityLabel`, or both — calls supplying neither fail to typecheck. The dev-only `__DEV__` warning is the runtime fallback for the case where types are bypassed (dynamic spreads, `any`-typed consumers); it does not block production renders.
5. After a Phase 3 slice swaps a screen, the `testID`s observed by Appium MUST equal the pre-swap ones. The freeze contract is "what Appium queries returns the same node tree shape post-swap as pre-swap". This is invariant I_UI6 (§4j).

### 4j. Hard invariants (additions to `theming.md` §4e — I1…I10 keep)

- **I_UI1 (DS components are tokens-only)**: No DS component reads a raw hex, raw px, MD3 typescale key, or `theme.fonts.*` legacy alias. All visual values flow through `theme.colors.*`, `theme.typography.*`, `theme.spacing.*`, `theme.radius.*`, `theme.stroke.*`.
- **I_UI2 (DS layer is observation-free)**: No file under `src/components/ui/` imports `mobx`, `mobx-react`, or any store. State integration is the consumer's responsibility.
- **I_UI3 (Header is the sole overlay header)**: No DS overlay (`Sheet`, `Modal`, `Dialog`) renders inline header markup. They MUST compose `<Header>`.
- **I_UI4 (Paper-import discipline grows monotonically)**: Once a Paper `importName` is added to the `no-restricted-imports` blocklist, it MUST NOT be removed. Re-allowing a banned name (other than the per-file overrides for the three wrap-Paper DS components) is a regression. Phase 4 (FOU-123) lands the final inversion-of-thin-set blocklist; intermediate Phase 3 PRs add entries as call-sites migrate.
- **I_UI5 (Phase 3 swaps preserve DS snapshots)**: A Phase 3 slice PR may change a screen's snapshot, but MUST NOT change any DS component's snapshot. DS visual changes are separate, intentional commits.
- **I_UI6 (testID freeze)**: The Appium-observable testID tree at any screen MUST be identical pre- and post-Phase-3-swap. New DS testIDs are additive at the leaves (e.g. `ui-icon-button` may appear inside an existing `'menu-icon'` parent), never replacing.
- **I_UI7 (canonical-variant choices are recorded)**: For each duplicated DS family (Chips×3, Tabs×3, nav×2), the canonical variant choice is recorded in this WHAT (§4f decisions D8–D10) and absorbed into `theming.md` on promotion. Phase 3 must implement against the canonical choice; other Figma variants in the duplicated set are NOT shipped as DS variants in Phase 2 (they become explicit dead designs until a designer-sourced reconciliation).
- **I_UI8 (folded rename + architecture doc absorption are cross-linked in the same review cycle)**: The token-rename patch lands as the FIRST commit of the app-repo PR, and `theming.md` §1a is updated in a paired dev-team-repo commit referenced from the PR description. The two commits live in different repos by submodule structure (app code in `repos/pocketpal-ai`, architecture docs in the dev-team meta-repo); same-PR-atomicity is therefore not literally enforceable. The invariant is cross-link visibility: the app PR's description MUST cite the dev-team commit SHA that lands the §1a update, and the dev-team commit MUST cite the app PR URL. Splitting them across review cycles (i.e. landing one without the other in the same review) violates the architecture non-negotiable that drift is forbidden.

### 4k. What each module renders / produces (delta on `theming.md` §4f table)

| Module | Renders / produces | Does NOT render / produce |
| --- | --- | --- |
| `src/components/ui/primitives/Pressable` | A `Pressable` wrapper that resolves `pressed` (mobile-only state RN exposes via the style callback) and applies the token-bound state-layer overlay. | `hovered` / `focused` resolution (RN's `Pressable` does not surface these on mobile — consumers wrap `onFocus`/`onBlur` themselves). Any visual style outside the state layer. No padding, no radius. |
| `src/components/ui/<Component>` (rebuild families) | A token-bound, observation-free presentational component. | Store reads. Raw hex / raw px. MD3 typescale references. |
| `src/components/ui/{Switch,Checkbox,RadioButton}` | A thin Paper wrapper exposing the DS API contract (§4c). Forwards a11y props; applies token-bound color/size overrides. | Custom state machinery. Custom a11y. |
| `src/components/ui/Header` | The shared header building block. | Sheet/Modal/Dialog mechanics. |
| `src/components/ui/{Sheet,Modal,Dialog}` | Composition of `Header + Body + Actions` around an existing presentation primitive (gorhom for Sheet, Paper Portal for Modal/Dialog). | New animation primitives. |
| `src/components/ui/*/styles.ts` | `createStyles(theme, {variant, size, state})` returning a `StyleSheet`. | Direct token-module imports. Raw values. |
| `src/components/ui/index.ts` | The public DS barrel. | Re-exports from `src/components/*` (legacy namespace). |
| `.eslintrc.js` | Extended `no-restricted-imports` entry banning Paper `importNames` (seeded EMPTY, growing per-component per §4g.3). Per-file override re-allowing Paper for wrap-Paper DS files. | Removal of the existing `__automation__` rule (kept). |
| `context/architecture/theming.md` | Updated §1a key set (folded rename absorbed); new sub-section "Component layer (DS)" capturing §4b, §4c, §4d, §4e, §4g.4 (final blocklist), §4j invariants. | A separate flow doc. The DS layer is part of the theming flow. |

---

## 5. Layer ownership (single-writer rule) — delta on `theming.md` §5

| Field | Single writer | Notes |
| --- | --- | --- |
| `theme.spacing.xl`, `theme.radius.{m,ml,l,xl,xxl}` (renumbered), `theme.stroke.{xs,sm,md,lg}` (renamed) | The tokens module under `src/theme/tokens/` (writers = `spacing.ts`, `radius.ts`, `stroke.ts`). | Folded rename — values are `const`, never mutated at runtime. |
| `.eslintrc.js` `no-restricted-imports.paths['react-native-paper'].importNames` | The `.eslintrc.js` file itself. Grows monotonically per Phase 3 slice (I_UI4). | No script generates it; entries are added by humans/agents in PR reviews. |
| `src/components/ui/*/styles.ts` (DS styles) | The component's own `styles.ts`. | No cross-component style sharing except through `primitives/`. |
| `src/components/ui/Header/` JSX shape | The Header component itself. I_UI3 forbids other overlays from re-implementing header markup. | The DS overlays compose, not duplicate. |

**Deferred cleanups** (additions to `theming.md` §5 deferred list, items 1–5):

6. Remove the comment "(currently withOpacity-derived, FOU-115)" from `theming.md` §1a once item §5 #4 (the FOU-115 work to migrate `withOpacity`-computed semantic surfaces) lands. NOT done in this slice — the comment refers to a deferred cleanup, and this slice doesn't migrate those colors either. Re-evaluate at a later FOU-115-suffix slice.
7. Migrate the existing `src/components/Sheet/Sheet.tsx`, `src/components/Dialog/Dialog.tsx` call-sites from the legacy wrappers to the DS `Sheet`/`Dialog`. Per-screen Phase 3 work (FOU-117+); the DS wrappers exist after this slice and the legacy ones do too.
8. Move `stateLayerOpacity`, `hoverStateOpacity`, etc. out of `theme.colors.*` into a dedicated `theme.interaction.*` namespace — already noted in `theming.md` §5 #3. The DS `Pressable` primitive consumes them via `theme.colors.*` for now; when the namespace move lands, the primitive's `styles.ts` is the only DS file that needs to change (single touch point — design invariant of this slice).

---

## 6. Canonical scenarios

Each scenario is manually testable and corresponds to a snapshot or test that must exist.

### A. Token rename absorbed, app renders identically

After the folded patch lands as the first commit and `theming.md` §1a is updated, the app renders pixel-identical to pre-PR (preserves `theming.md` I1). Verified by:
- `yarn jest src/theme/tokens/__tests__/scales.test.ts` passes (12 assertions, patched).
- `yarn jest --testPathPattern='src/theme'` passes (no consumers outside token module broke — drift check pre-verified).
- Manual smoke: launch app on iOS sim, no visual diff vs HEAD~N before the patch.

### B. DS Button renders all variants × sizes × states × modes

```
render(<Button variant='primary' size='m'>Save</Button>, {theme: buildTheme({mode:'light', language:'en'})})
─────────────────────────────────────
matches snapshot ui-button/primary-m-default-light.snap
```

Snapshot exists for every cell in the matrix. Phase 3 swap of a screen reading `<PaperButton mode='contained'>Save</PaperButton>` to `<DSButton variant='primary' size='m'>Save</DSButton>` must produce visually identical output (verified by manual visual diff on a real screen and by the Phase 3 snapshot of that screen).

### C. Paper-import ESLint rule rejects banned `importNames` (seed = `['Surface']`)

In Phase 2, the seed list is `['Surface']` and the two pre-existing Paper-`Surface` imports are swapped in this PR (see §4g.7 + scenario I'). All other lint runs pass unchanged. As Phase 3 swaps add entries, lint catches stray Paper imports:

```
// Phase 2 PR — after Surface swap commits land:
import {Surface} from 'react-native-paper';
// ERROR  no-restricted-imports: 'Surface' import from 'react-native-paper' is restricted — use src/components/ui/Surface instead.

// Hypothetical Phase 3 PR adds 'Chip' to blocklist:
import {Chip} from 'react-native-paper';
// ERROR  no-restricted-imports: 'Chip' import from 'react-native-paper' is restricted — use src/components/ui/Chip instead.
```

### D. Wrap-Paper component (DS Switch) preserves a11y semantics

```
render(<DSSwitch value={true} onValueChange={fn} accessibilityLabel='Enable dark mode' />)
─────────────────────────────────────
Appium queries for:
  - testID = 'ui-switch'                   → finds 1 element
  - accessibilityRole = 'switch'           → finds 1 element
  - accessibilityValue.text = 'on'         → finds 1 element (Paper auto-derives from value=true)
```

### E. Sheet composes Header + Body + Actions

```
<DSSheet isVisible>
  <DSSheet.Body>...</DSSheet.Body>
  <DSSheet.Actions primary={…} secondary={…} />
</DSSheet>

(or — equivalent shape)

<DSSheet isVisible title='Pick a model' subtitle='Loaded models only'>
  <ModelList />
  <DSSheet.Actions primary={{label:'Apply', onPress:…}} />
</DSSheet>
```

In both forms, the DS Sheet renders a `Header` (because `title`/`subtitle` are provided OR a Header is passed as a slot — TBD by planner whether title is a slot or a `Header` child; the WHAT fixes that there is exactly ONE Header in the tree). The snapshot matches.

### F. DS overlay header is reused (Header building block)

A `DSDialog` and a `DSModal` and a `DSSheet` all rendered with `title='Hello'` produce the **same** Header-subtree shape (modulo wrapping by the overlay's surface). Verified by inspecting the rendered tree in tests — same `testID='ui-header'`, same children order, same typography tokens.

### G. RTL canary (one snapshot per component)

```
render(<DSButton>اعتقال</DSButton>, {language: 'fa'})  // I18nManager.isRTL=true
─────────────────────────────────────
matches snapshot ui-button/primary-m-default-light-fa.snap
```

The fa snapshot differs from the en one in label characters and writing direction only; padding/radius/state-layer are identical.

### H. Dark canary (every component, every variant)

```
render(<DSChip variant='selectable'>Pal</DSChip>, {mode: 'dark'})
─────────────────────────────────────
matches snapshot ui-chip/selectable-m-default-dark.snap
```

Distinct from the light snapshot. The pair is the dark-parity verification artefact.

### I. Phase 2 ships zero **screen** changes (one component-layer swap excepted)

After this PR lands, every existing `src/components/*` import path renders identically to today, with the single exception of the two `Surface` consumers (`UsageStats.tsx`, `PalDetailSheet.tsx`) which now import `Surface` from `src/components/ui/Surface`. Verified by:
- The existing `src/components/Sheet/Sheet.tsx`, `src/components/Dialog/Dialog.tsx`, `src/components/Selector/Selector.tsx`, etc. — all untouched.
- No screen file under `src/screens/` is modified by this PR (planner enforces).
- The two `Surface` swap commits change `import {Surface} from 'react-native-paper'` to `import {Surface as Surface} from '@/components/ui'` (or equivalent) and nothing else in those files — visual diff is zero (DS Surface renders the same `View` + background + elevation).
- `yarn jest` passes with the additive DS test files plus updated snapshots for `UsageStats` / `PalDetailSheet`.

### I'. Paper-`Surface` blocklist enforces immediately

```
// In this PR, after the Surface swap commits land:
import {Surface} from 'react-native-paper';   // ANY new file
// produces:
ERROR  no-restricted-imports: 'Surface' import from 'react-native-paper' is restricted — use src/components/ui/Surface instead.
```

The blocklist enforcement is verified by a deliberate failing-then-fixed test commit in HOW (proof the rule fires) and by the absence of any `Surface` import from `'react-native-paper'` in the post-PR `src/` tree (verifiable by `grep -rn`).

### J. Folded rename does not regress §1a documented invariants

After the rename:
- `theming.md` I2 (token-source consistency) still holds — new keys are Figma-canonical.
- `theming.md` I3 (single scale per dimension) still holds — `spacing`/`radius`/`stroke` still each one scale.
- `theming.md` I4 (absolute line-heights) untouched.
- `theming.md` I8 (font family names match) untouched.

---

## 7. State signals (delta on `theming.md` §7 — none changed)

No new state signals. DS components consume the existing signals from `theming.md` §7 (`uiStore.colorScheme`, `uiStore.language`, `I18nManager.isRTL`, `isHydrated(uiStore)`) via `useTheme()` only.

---

## 8. Decisions

- **D1**: Fold the 236-line `/tmp/fou-114-token-rename-leftover.patch` as the FIRST commit of this PR; update `theming.md` §1a in the SAME PR. Rationale: it is foundation-layer for the DS components that consume the renamed keys (e.g. `theme.radius.l` now meaning Figma's `Radius/L = 20`); fixing later would require renaming through DS code we'd already shipped against the wrong names.
- **D2**: New DS components live at `src/components/ui/`, NOT replacing existing files at `src/components/*`. Rationale: Phase 2 ships library-only; Phase 3 swaps incrementally. Co-location would force every Phase 3 PR to be larger and would break the parallel-build property the rollout doc calls "same component API where possible so screens swap in place".
- **D3**: Wrap-vs-rebuild = rebuild 14 families, wrap Paper for 4 families (`Switch`, `Checkbox`, `RadioButton`, `Dropdown`). Rationale: visually-defining families have token-bound styles that fight Paper's MD3 specifics; form controls + dropdown popup are a11y-heavy / positioning-heavy and Paper's implementations are correct. (Dropdown reclassified from Rebuild to Wrap-Paper post-pipeline-review-round-1 — see D25.)
- **D4**: Paper-import discipline = ESLint `no-restricted-imports` with `importNames` blocklist that grows entry-by-entry. Rationale: the retired snapshot guard `verify-paper-surface.js` was binary (whole file blocked or whole file ignored). The blocklist is per-symbol, so the locked thin set (`Text/Button/IconButton/Portal/Provider`) stays trivially available while every other symbol gets banned as its DS replacement ships.
- **D5**: Phase 2 seeds the ESLint blocklist with `['Surface']` only (see D31 + D32 for why Surface is the exception). Rationale for keeping the rest empty: adding entries while Paper consumers remain across the codebase would block any incidental Phase 2 fix to a legacy screen. Beyond `Surface` (2 consumers, both swapped here), the discipline is enforced slice by slice during Phase 3.
- **D6**: The Paper-import blocklist FINAL state is the inversion of the locked thin set (`Text/Button/IconButton/Portal/Provider`). Rationale: same definition `theming.md` §4c #3 and `FOU-112-rollout.md` §1 use. No new policy.
- **D7**: The representative bespoke sheet picked as the working pattern is `ChatPalModelPickerSheet`. Rationale: it has a title row, scrollable body, action row, and a model-selection list — exercising every part of the Header + Body + Actions composition AND a realistic body content density. **Contingency**: if a Phase 3 slice surfaces a header/body/actions shape this sheet does not exercise (e.g. a sticky-footer action row that needs a different slot contract from Sheet), the DS `Sheet` may widen ITS slot contract — the `Header` building block contract is independent and stays fixed. Widening Sheet does not invalidate `ChatPalModelPickerSheet`'s status as the Phase 2 working pattern. (P)
- **D8** (canonical variant: Chips×3): Pick **`Chip` family `890:29153`** as canonical. Rationale: it is the standalone Chip definition in the DS section; `768:29722` is the Chip-as-rendered-in-input-context variant and is a presentation overlay of `890:29153`'s base. Defer the third Chip variant until designer reconciliation (Phase 4 designer ask).
- **D9** (canonical variant: Tabs×3): Pick **`Tabs` `764:27807`** as canonical. Rationale: it is the standalone Tabs definition in the DS section; `408:11226` is an older Tabs render preserved as a legacy reference. Defer the third Tabs variant until designer reconciliation.
- **D10** (canonical variant: BottomNavBar×2): Pick **`143:4685`** as canonical. Rationale: `764:28530` mirrors `143:4685` with cosmetic icon swaps; the structural shape is identical. Build against `143:4685`; the cosmetic variant is a Phase 3 designer-spec call.
- **D11** (testID naming): All DS testIDs prefix with `'ui-'` (matches `src/components/ui/` namespace, shadcn convention). Rationale: lets Appium selectors and human readers disambiguate DS instances from legacy ones during the Phase 3 transition window without requiring full-tree inspection. (Originally drafted as `'ds-'`; renamed in lock-step with the folder rename `ds/` → `ui/` post-architect-critic round 1.)
- **D12**: Wrap-Paper DS components (Switch / Checkbox / RadioButton / Dropdown) are the only DS files allowed to import the corresponding Paper symbol after Phase 4. Mechanism: per-file ESLint override (added in lock-step with each Paper symbol entering the blocklist — Phase 2 only blocklists `Surface`, so no per-file allowance is needed yet). Rationale: the discipline must NOT make those four files impossible to write.
- **D13–D30**: Wrap-vs-rebuild decisions per family (see §4f matrix). Each carries the family-specific rationale in the matrix; not duplicated here.
- **D31**: Blocklist starts with `['Surface']` in this PR (proof-of-life — both consumers swap in the same PR; see §4g.7). All *other* blocklist entries are added in Phase 3 swap PRs, not in this Phase 2 PR. Rationale: discipline mechanism is meaningless if it ships with zero enforced entries; `Surface` is the smallest viable proof (2 simple consumers, verified). Beyond `Surface`, the rationale of D5 still holds — banning families with 100+ Paper consumers in Phase 2 would block incidental fixes.
- **D32**: Add a DS `Surface` primitive (originally listed only under `primitives/` in §4b) to the Phase 2 wrap-vs-rebuild matrix as a 15th rebuilt family. Rationale: needed as the replacement target for the blocklist's seed entry (D31); both consumers are simple enough that the rebuild fits the Phase 2 scope without inflating the matrix shape (1 variant × 1 size × 2 modes — minimal snapshot surface).
- **D33**: Extend `jest/fixtures/theme.ts` with a `themeFixtures.byMode(mode).byLocale(language)` factory (vs leaving the fixture alone and calling `buildTheme` per-file). Rationale: centralizes memoization for the DS snapshot matrix which needs `language='fa'` in addition to `en`; keeps every DS test reaching the theme through the same fixture surface. (Full text under §4h.6.)
- **D34**: `accessibilityLabel` enforcement = TypeScript discriminated-union constraint as the **primary** mechanism (rejected calls fail to typecheck), with `__DEV__` runtime warning as a fallback. Rationale: a soft `__DEV__` warning alone can be missed in jest snapshots and production builds where `__DEV__=false`; types catch every call-site at compile time. Consumers may supply both `label` and `accessibilityLabel` (label visible, accessibilityLabel overrides) — the union supports the intersection. (Full text under §4c.5.)
- **D35**: `Header` default `accessibilityRole='header'` deliberately collides with RN navigation header role. Rationale: assistive tech treats both as document landmarks; sharing the role is the desired UX, not an accident. (Full text in §4i footnote ¹.)

---

## 9. Edge cases

### 9a. A future Phase 3 slice wants to ship a new DS variant not in this matrix

Allowed: widen the closed `variant` union for the relevant family in the relevant Phase 3 PR. The PR must update the snapshot matrix (add cells) AND update `theming.md` (which has absorbed this WHAT's §4f matrix). No DS variant lands without (variant × size × state × mode) snapshot coverage.

### 9b. A Phase 3 swap reveals the DS component has wrong padding/radius for a real screen

Two options, both correct: (a) widen the DS variant union to include the screen's needs (preferred — the screen is canonical); (b) the screen passes `style` override (escape hatch — flagged as a smell, see I_UI1 in spirit). Token-bound style overrides remain legal; raw values in the override would fail review per I_UI1's spirit even though the screen sits outside `src/components/ui/`.

### 9c. A wrap-Paper component needs visual delta beyond Paper's color overrides

If `DSSwitch` color tokens are insufficient to match the Figma Switch (e.g. thumb shape differs), reclassify the family to "Rebuild" in a follow-up PR (delta on this WHAT) — do NOT add bespoke styling layers on top of Paper. The wrap-vs-rebuild call is per-component and reviewable; flipping it requires a recorded decision.

### 9d. The Header building block needs different alignments per overlay

The `align` prop covers `'leading' | 'center'`. A future need for `'trailing'` or per-overlay header layouts goes through I_UI3: the answer is to widen Header's prop surface, NOT to inline header markup inside the overlay.

### 9e. RTL canary snapshot diverges from LTR in a non-direction-mirror way

Likely a missing `start`/`end` directional style in the component's `styles.ts`. RTL canary is the catcher; the fix is in the component's `styles.ts`, not in tokens.

### 9f. Non-Latin canary snapshot diverges from Latin in font metrics

Expected behaviour per `theming.md` §4d.2 — Fraunces falls back to Inter for non-Latin locales. The snapshot diff is the verification, not a bug. The snapshot files for non-Latin canaries are the source of truth.

### 9g. Paper-import ESLint rule fires inside `src/components/ui/{Switch,Checkbox,RadioButton}`

The per-file override (§4g #6) re-allows the relevant `importName`. If it doesn't, the override config is wrong, not the import.

### 9h. A Phase 2 commit modifies a `src/screens/*` file

Reject in review. Phase 2 is library-only. Trivial typo fixes in screens that happen to land alongside Phase 2 work go in a separate PR.

### 9i. The folded patch fails to apply at PR-creation time

If a downstream commit on `feature/TASK-20260524-2320` has touched `src/theme/tokens/{spacing,radius,stroke,types}.ts` between drift check and PR creation, the patch will conflict. Resolution: hand-merge the rename onto the latest token files and update `__tests__/scales.test.ts`. The intent (Figma-name parity) is the contract; the patch is its diff representation.

### 9j. Dark mode snapshot has the wrong color for some DS variant

Inspect: is the source token actually wrong (then it's a `theming.md` §9a "missing dark binding" case, designer ask), OR is the component reading the wrong token (then it's a `styles.ts` bug). The snapshot is the diagnostic — the fix is in the right layer.

### 9k. A DS component testID needs to differ per call-site

Pass the prop. The defaults table (§4i) is for the case where the call-site doesn't care. Phase 3 swap PRs MUST pass the legacy testID at each call-site so Appium selectors continue to resolve (I_UI6).

---

## 10. What this doc is NOT

- Not an implementation plan — file creation order, snapshot tool wiring, ESLint config mechanics, exact test names, and commit order live in `how.md`. The contract is here; the schedule is there.
- Not a designer hand-off — Figma is the design source; this doc reflects the slice engineering owns.
- Not a Paper-removal plan — that's Phase 4 / FOU-123. This doc is the Phase 2 contract that makes the removal possible without breaking screens.
- Not a record of which Paper imports exist today — those are the inversion-of-thin-set targets (§4g.4).
- Not a long-term DS API — the `variant`/`size` unions are expected to grow as Phase 3 slices encounter screen needs. The contract is `variant`/`size` as closed string unions PER FAMILY, not a frozen list.
- Not a per-language a11y / l10n review — covered by `theming.md` §4d (typography fallback) and §9d–9f (RTL / non-Latin edge cases). The DS layer is locale-agnostic by construction.

**Cleanup reminders** (carry forward in `theming.md` once absorbed):

1. The Phase 3 blocklist growth contract (I_UI4) must be re-stated when each Phase 3 slice ships, so every Phase 3 WHAT cites it as a check-off item.
2. The DS layer's existence (`src/components/ui/`) must be added to `theming.md` §4f's "What each component renders" table on promotion.
3. The wrap-vs-rebuild matrix decisions (D13–D30) must be absorbed into `theming.md` §8 on promotion.
4. The testID freeze contract (§4i) must be absorbed into `theming.md` §5 cross-cutting rules section (currently in `FOU-112-rollout.md` §5) so the architecture doc itself records it — the rollout doc is planning, the architecture doc is enforcement.


---

## Review History

### Round 1 — architect-critic verdict: HAS_CONCERNS

| # | Finding | Resolution | Notes |
| --- | --- | --- | --- |
| C1 | D31 + I_UI4 leave Phase 2 with zero enforced blocklist entries | **FIXED** | Picked option (a) proof-of-life. Verified Surface has exactly 2 import sites (`UsageStats.tsx`, `PalDetailSheet.tsx`), both using `<Surface elevation={0} style={...}>` — trivial swap. Added `Surface` as 15th rebuild family (D32); seeded blocklist with `['Surface']` (revised D31, D5); updated matrix summary, NOT-in-scope bullet, §4g.7, testID table, scenario I, new scenario I'. |
| C2 | Snapshot matrix unbounded; wrap-Paper trio needs special rendering plan | **FIXED** | Restructured §4h into six numbered subsections (§4h.1–§4h.6). Baseline = `variant × size × {default,disabled} × mode`; `pressed` = one snapshot per `variant` only (size-invariant by construction); `focused` only for `Input` + `Button`; wrap-Paper trio restricted to `variant × size × {default,disabled} × mode × value` axis — `pressed`/`focused` explicitly excluded as Paper internals. Restriction encoded as part of I_UI5's scope boundary in §4j (existing invariant text reads "DS snapshots", which by §4h.3 scope excludes wrap-Paper internals — no rewording of I_UI5 needed). |
| C3 | Required `accessibilityLabel` enforced only by `__DEV__` warning | **FIXED** | Promoted TypeScript discriminated-union constraint to primary enforcement (D34): `Props = (Common & {accessibilityLabel: string}) \| (Common & {label: string})`. `__DEV__` warning demoted to runtime fallback for type-bypass cases. Updated §4c.5 and §4i.4. |
| C4 | Theme fixtures only export en-locale themes; snapshot matrix needs more | **FIXED** | Picked option (a): extend `jest/fixtures/theme.ts` with `themeFixtures.byMode(mode).byLocale(language)` factory (D33). Rationale recorded in §4h.6: centralized memoization, single fixture surface. Verified current fixture exports `lightTheme`/`darkTheme` for `en` only. |
| S5 | D7's pick of `ChatPalModelPickerSheet` deserves a contingency | **FIXED** | Appended contingency clause to D7: future shape-mismatch widens Sheet's slot contract, not Header's. |
| S6 | `accessibilityRole='header'` default may collide with screen-header roles | **FIXED** | Picked option (a) — keep `'header'` default. Added footnote ¹ + decision D35 explaining the collision is desired (assistive tech treats both as document landmarks). |

No (?) markers introduced. All findings addressed in-place.

### Round 2 — planner doc fixes (no critic re-review needed)

| # | Finding | Resolution |
| --- | --- | --- |
| PD3 | D3 said "rebuild 14 families" while §4f summary + D32 said "rebuild 15 families" — Surface added as 15th via D32 was not propagated to D3. | **FIXED** in same commit as the §1a doc update. D3 now reads "rebuild 15 families". Copy-edit only; no contractual change. |
| PD6 | §4b directory tree listed `Surface/` under `primitives/`, but §4f D32, §4g.7, and §4j I_UI5 treat Surface as a top-level rebuild family. PD1 in HOW resolves the location as `src/components/ui/Surface/` (top-level sibling, not under primitives/). Step F1 absorption of §4b into theming.md would otherwise encode the contradiction. | **FIXED** in same commit as PD3. Surface moved out of primitives/ to top-level sibling. Same class as PD3 doc-only correction; WHAT contract is unchanged (§4f D32 already designates Surface as a family with its own snapshot matrix and consumer swaps). |

### Round 3 — pipeline-reviewer findings (round 1)

| # | Finding | Resolution |
| --- | --- | --- |
| B1 | Modal scrim is a sibling-below-body Pressable; RN's responder system is hierarchical, so taps in the body area never reach the scrim. The "scrim" was misleading dead code given Modal's fullscreen contract (§4e). | **FIXED.** Dropped the Pressable scrim from Modal entirely; Modal is fullscreen by §4e and dismiss is consumer-driven via Header `trailing`/`leading` slot (close button) or platform back. No screen consumers existed in Phase 2; tests + snapshot regenerated. |
| B2 | DS Surface emitted only Android `elevation`; Paper Surface synthesizes iOS `shadow*` props from elevation. UsageStats tooltip lost its iOS drop shadow on swap. (Reviewer's Android double-shadow claim was wrong — RN style flatten last-wins gives UsageStats its `elevation:4` correctly.) | **FIXED.** Surface/styles.ts now synthesizes iOS `shadow*` from `elevation`, mirroring Paper's `iOSShadowOutputRanges` tier. Restores parity for both swap consumers and all future DS Surface usages. |
| B3 | DS Surface default `radius='m'=12` applied implicit corners to consumers that didn't ask for them — including PalDetailSheet stats (12 px corners, invisible only because bg matches parent). API contract bug for any future contrasting-bg consumer. | **FIXED.** Surface default radius changed from `'m'` to `'none'`. Trivial `View` parity restored. Dialog passes `radius="l"` explicitly so its rendering is unaffected. |
| B4 | Snapshot matrix promised `pressed`/`focused` coverage but factories ignored `cell.state` — every pressed/focused/disabled cell rendered byte-identical to default. Wrap-Paper trio's `size` axis produced duplicate cells (Paper owns sizing). | **FIXED.** Per §4h.2 + §4h.3 updates: pressed/focused axes dropped from matrix (deferred to Phase 3 fireEvent harness); factories now consume `cell.state` and pass `disabled` through; wrap-Paper trio drops `size` from public prop type. Snapshots regenerated; baseline now reflects real signal. |
| B5 | DS Dropdown imported `Menu` from `src/components/Menu` (legacy), which itself imports `react-native-paper` — breach of §4b.4 one-way dependency rule. | **FIXED via reclassification.** Dropdown moved from Rebuild to Wrap-Paper in §4f matrix (D25 rewritten). Imports Paper `Menu` directly. D3/D12 updated to reflect 4 wrap-Paper families. Per-file ESLint allowance added when `Menu` enters the blocklist in Phase 3 (Phase 2 only blocklists `Surface`). |
| C1 | ESLint `excludedFiles: [Switch, Checkbox, RadioButton]` disabled the ENTIRE `no-restricted-imports` rule in those folders — including the `__automation__` pattern guard, not just the Paper-symbol ban. | **FIXED.** `excludedFiles` dropped from the main override; the only currently-blocklisted Paper symbol is `Surface`, which the wrap-Paper folders don't import, so no per-folder exception is needed today. Per-folder allowance returns in lock-step with each future blocklist entry (Phase 3 work). |
| C2 | Hardcoded English `accessibilityLabel="Dismiss"` on Modal+Dialog scrim with no consumer override. | **PARTIALLY FIXED.** Modal scrim dropped entirely (B1) so the issue evaporates there. Dialog now accepts a `dismissAccessibilityLabel?: string` prop with no default — consumer (Phase 3 caller) supplies an L10n string. |
| C3 | RTL canary did not actually toggle `I18nManager.forceRTL(true)` — the `fa` axis exercised only typography fallback, not layout direction. | **FIXED via accurate naming.** §4h.5 renamed from "RTL canary" to "non-Latin font-fallback canary". Layout-direction snapshots deferred to Phase 3 (the global `forceRTL` toggle is irreversible across same-process tests and needs a per-test isolation harness). The `fa` snapshot's contract in Phase 2 is now honestly scoped. |
| C4 | D11 still read `'ds-'` after the folder/testID rename to `'ui-'`. | **FIXED.** D11 updated to read `'ui-'` with a parenthetical noting the in-flight rename. |
| C5 | Pressable primitive pinned `focused: undefined` and `hovered: undefined` to the consumer style callback — the contract surface in §4c.4 was structurally unreachable. | **FIXED.** §4c.4 and §4k updated: the primitive only resolves `pressed`. `hovered`/`focused` are platform-conditional and consumer-driven (Input owns its `onFocus`). Dead branches in `createStateLayerStyle` removed. |
| C6 | Sheet `testID='ui-sheet'` lived on an inner View wrapper rather than on `BottomSheetView` (asymmetric with Modal/Dialog whose testID is on the outermost container). | **FIXED.** testID moved to `BottomSheetView`; the inner View wrapper removed. Snapshot regenerated. |
| C7 | Same root cause as C6 — non-Animated `<View>` inside `BottomSheetView` is a latent measurement risk for any future `enableDynamicSizing` consumer. | **FIXED with C6.** Wrapper removal also removes the measurement risk. |
| C8 | I_UI8 said the §1a doc update lands in the same PR as code, but architecture docs live in dev-team meta-repo while code lives in pocketpal-ai submodule — same-PR-atomicity is not literally enforceable. | **FIXED.** I_UI8 reworded to require cross-linked commits in the same review cycle: app-PR description cites dev-team commit SHA; dev-team commit cites app-PR URL. |
| C9 | `<Header` JSX-presence regex didn't count occurrences — a second Header could be inlined without the test catching it. | **FIXED.** invariants.test.ts now asserts exact count `=== 1` via global-flag regex match. |
| C10 | `types.ts:44` warned with stale `[ds/${componentName}]` prefix after the rename. | **FIXED.** One-line change to `[ui/${componentName}]`. |
