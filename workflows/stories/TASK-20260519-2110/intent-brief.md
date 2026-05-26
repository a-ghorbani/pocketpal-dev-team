# Intent: Redesign Phase 1 — design-token foundation, font additions, theme decoupling, RTL/non-Latin fallback (FOU-114)

---

## Metadata

- **Task ID**: TASK-20260519-2110
- **Source**: Linear FOU-114 (Phase 1 of parent initiative FOU-112, "PocketPal redesign — Figma UX rollout"). Rollout plan: `context/redesign/FOU-112-rollout.md` in the dev-team control-plane repo (not committed; not present in the worktree).
- **Worktree**: `./worktrees/TASK-20260519-2110` (removed 2026-05-26)
- **Branch**: `feature/TASK-20260519-2110`
- **Complexity**: standard (touches a contract: theme/token model + native build; multi-file; full pipeline)
- **Native Changes**: YES (adds fonts; updates `react-native.config.js`; requires native font linking, `pod install`, iOS build, Android build)
- **Visual Confirmation**: YES (this slice must produce NO visible change — visual capture is needed to prove the no-regression claim)
- **Created**: 2026-05-19
- **Status**: merged (main body in PR #732); token-rename leftover folded into FOU-115 / PR #742
- **PR**: https://github.com/a-ghorbani/pocketpal-ai/pull/732 (main body, merged separately); the 5-file token-rename leftover ride-along merged via https://github.com/a-ghorbani/pocketpal-ai/pull/742 (squash `6187c4c`, 2026-05-26).

---

## Request

FOU-114 — Redesign Phase 1: Design-token foundation + fonts + theme decoupling + RTL/non-Latin fallback.

This is **Phase 1** of the long-running PocketPal redesign (parent FOU-112), the first implementation slice. It is an **invisible foundation slice**: no user-visible change. The app must build and render exactly as it does today, just sourced from a new token layer. Visual/UX changes happen in later slices (FOU-116…122).

### Program context

Parent initiative FOU-112 ("PocketPal redesign — Figma UX rollout") is long-running and implemented in slices. The full rollout plan lives in the dev-team control-plane repo at `context/redesign/FOU-112-rollout.md` and is the source of truth for the rollout. Phase 0 decisions (FOU-113) are locked.

### Canonical design source (LOCKED)

- Figma file `RZxDJea4t6jnBZrV4YBacF` ("Pocket Pal - Copy - Khatia"), page `0:1` "App design". Design-system section: node `789:19792` ("Components"); nested icons `746:26281`. Other Figma files are non-canonical and must not be used.
- Light/dark structure: `789/888:*` frames are the light render; `989:*` frames are the dark-mode render of the same screens. Dark derives from a mode-aware token collection (every token has a light and a dark binding).

### Locked decisions (do not re-litigate)

- Keep `react-native-paper` (v5.14.5) thin — Text/Button/IconButton/Portal/Provider only. Introduce a token layer **decoupled from MD3**. Do not rip Paper out; do not deepen Paper usage.
- Remove the `x1Theme` variant — light + dark only. Removal can be staged in this slice or in cleanup FOU-123; at minimum the new token layer must not depend on x1.
- RTL (`he`, `fa`) + non-Latin/CJK is engineering's responsibility — the design system does not encode it. The token/typography layer must implement the fallback rule: the serif accent (Fraunces) is Latin/Cyrillic only; non-Latin locales (`he ja ko zh fa`) render headlines in Inter/system. RTL mirroring must be respected.
- Architecture today (preserve it): `src/utils/theme.ts` MD3-based with 3 variants (light/dark/x1), `createStyles(theme)` factory + `useTheme()` hook, MobX `uiStore.colorScheme` drives mode, fonts bundled via `react-native.config.js`. Inter (7 weights) already bundled. ~109 files import react-native-paper; 65 components; drawer nav.

### Verified canonical-file token state (from `get_variable_defs` on `789:19792`, light render)

- Spacing is effectively one scale `Spacing/*` = 0 / 2 / 4 / 8 / 12 / 16 / 20 / 24 (None/XXS/XS/S/SM/M/ML/L). One `Radius/*` = 0 / 2 / 4 / 8 / 12 / 16 / 20 / 32 / 40. One `Stroke/*` = 0.5 / 1 / 1.5 / 3. Sizing `height/*`, `width/*` separate.
- Residual name-drift to alias in the token module (not new scales): `Gap/*` (S=8, SM=12) mirrors `Spacing/*`; lowercase `radius/radius-xs` = 4 mirrors `Radius/XS` = 4.
- Typography families: Inter (body / UI / title / caption), Fraunces (Headline/H1, Styled/xs), JetBrains Mono (Code). Weights are concrete 400 / 500 (statically mappable: 400 → Regular, 500 → Medium).
- Implementation-side typography normalization required: (a) Fraunces-Italic is not a named style in tokens — ship Fraunces-Italic as its own RN font family for the accent word; (b) two type styles use non-absolute line-height (`Headline/H1` = 1.4 multiplier, `Styled/xs` = 100) — convert to absolute px; (c) encode the non-Latin fallback rule above.
- The dark token values have not yet been extracted — the architect/planner must pull the dark-mode binding of the same variables from the canonical file (Figma MCP `get_variable_defs` / design-context on the `989:*` render or the variable collection's dark mode) so the token module ships both light and dark.

### Scope (what FOU-114 must deliver)

1. A token module for the new design system: color tokens (light + dark, mode-aware), typography tokens (Inter / Fraunces / Fraunces-Italic / JetBrains Mono with static weight mappings, absolute px line-heights, non-Latin fallback rule), one consolidated Spacing / Radius / Stroke scale with `Gap/*` → `Spacing/*` and `radius/radius-xs` → `Radius/XS` aliasing. Decoupled from MD3.
2. Add fonts: Fraunces (including a separately-named Fraunces-Italic family) and JetBrains Mono — static weight cuts only (no variable fonts; RN can't use them). Both are OFL / Google Fonts. Wire iOS + Android via `react-native.config.js` and native linking, alongside existing Inter.
3. Refactor `src/utils/theme.ts` / `useTheme()` so token consumption no longer depends on MD3 internals where the new system diverges, while keeping `PaperProvider` / `Portal` and the `createStyles(theme)` + `useTheme()` + MobX `colorScheme` architecture intact.
4. Map current component visuals onto the new tokens so the app builds and renders unchanged (no visual regression). No screen restyle in this slice.

### Constraints / acceptance criteria

- `NATIVE_CHANGES=YES` (fonts + `react-native.config.js` + native font linking). Required before "ready": `pod install`, an iOS build, an Android build — all in the worktree, never in the submodule.
- No visual or behavioral regression vs current app (this is an invisible slice).
- E2E quick-smoke (`e2e/specs/quick-smoke.spec.ts`) must pass.
- TypeScript compiles; existing Jest suites green; lint / hooks pass (never bypass git hooks — no `LEFTHOOK=0` / `--no-verify`).
- Worktree isolation enforced; submodule read-only; stop and report if `pwd` is in the submodule or branch is `main`.
- This is standard / complex (touches a contract: the theme / token model + native build). Run the full pipeline (Intent → WHAT → HOW → Implementation).

---

## Clarifications

none — the request is self-contained and unambiguous. The architect/planner will resolve the remaining open implementation questions (dark-token extraction, x1Theme removal staging, exact set of Fraunces / JetBrains Mono weight cuts, MD3-decoupling shape) in WHAT and HOW.
