# FOU-112 — PocketPal Redesign Rollout Plan

**Status:** planning · **Parent:** [FOU-112](https://linear.app/pocketpal/issue/FOU-112) · **Last updated:** 2026-05-19

Long-running parent, implemented in slices. This doc is the source of truth for the
rollout; Linear sub-issues FOU-113…FOU-123 track execution.

---

## 1. Canonical inputs (LOCKED)

| Item | Decision |
|---|---|
| **Canonical Figma file** | `RZxDJea4t6jnBZrV4YBacF` — "Pocket Pal - Copy - Khatia", page `0:1` "App design". `fyC1zC0eq0nJjG5SFDexbY` and `szXSjMGisopPpjgmVjovoB` are **non-canonical**; do not implement from them. |
| **Light/dark structure** | The duplicated sections are **not iterations**. `789/888:*` = the **light** render; the dark-mode render of the *same* screens lives under the `3011:*` band (e.g. Homepage dark = `3011:25472`, Chat dark = `3011:25554`, Settings dark = `3011:25896`, Log in dark = `3011:26529`, Pal details dark = `3011:26813`, Explore dark = `3011:28061`, Create/modify pal dark = `3011:28506`, Onboarding dark = `3011:25220`). The `989:*` band was the earlier file structure and has been restructured — those IDs no longer resolve. Dark derives from the mode-aware token collection; no per-flow "pick a set" decision exists. |
| **Onboarding screens** | `884:28223` screens **1–6** are canonical. The dark render lives at `3011:25220` — ignore as a separate flow. |
| **RN Paper** | Keep **thin**: Text/Button/IconButton/Portal/Provider. Add a token layer decoupled from MD3, build new components against tokens, migrate screens incrementally. Not a rewrite, not a full removal. |
| **Theme variants** | Remove `x1Theme`. Light + dark only. |
| **Per-slice scope** | **Both** reskin + UX change, handled per slice. Greenfield areas (e.g. onboarding — none exists today) carry no migration risk. |
| **RTL + non-Latin** | The DS does **not** account for it. Engineering owns it: RTL (`he`, `fa`) mirroring + non-Latin/CJK font fallback (serif accent is Latin/Cyrillic only; non-Latin → Inter/system). Locked requirement, all phases. |
| **Sheet/Modal/Dialog** | Designer may deliver later; if not, we generate our own. For now **pick one representative bespoke sheet from the design and work from it**. Do not block Phase 2. |

---

## 2. Canonical-file token state (verified 2026-05-19)

Pulled from `get_variable_defs` on the Components section (`789:19792`). The canonical
file is **cleaner than the older audited file** — no remaining designer blockers.

**Spacing / radius — effectively collapsed:**
- One scale `Spacing/*` = `0 / 2 / 4 / 8 / 12 / 16 / 20 / 24` (None/XXS/XS/S/SM/M/ML/L).
- One scale `Radius/*` = `0 / 2 / 4 / 8 / 12 / 16 / 20 / 32 / 40`.
- One scale `Stroke/*` = `0.5 / 1 / 1.5 / 3`; sizing `height|width/*` separate (fine).
- **Residual name-drift only** (not 3 conflicting scales): a parallel `Gap/*` (S=8, SM=12)
  mirroring `Spacing/*`, and lowercase `radius/radius-xs`=4 mirroring `Radius/XS`=4.
- **Action:** in our token module treat `Spacing/*` + `Radius/*` as canonical and alias
  `Gap/*`→`Spacing/*`, `radius/radius-xs`→`Radius/XS`. Implementation-side, no designer ask.

**Typography:**
- Families correct: **Inter** (body/UI/title/caption), **Fraunces** (Headline/H1,
  Styled/xs), **JetBrains Mono** (Code).
- Weights are concrete **400/500** — static-mappable (400→Regular, 500→Medium). No 450
  variable-axis problem in this file.
- **Our-side gaps (all implementation, none blocking):**
  1. Fraunces-Italic is not a named style in tokens — ship Fraunces-Italic as its own
     RN family and apply to the accent word per the locked typography rule.
  2. 2 of ~12 type styles use non-absolute line-height: `Headline/H1`=1.4 (multiplier),
     `Styled/xs`=100 — convert to absolute px (e.g. H1 36×1.4≈50).
  3. No non-Latin fallback encoded — handle per the locked RTL/non-Latin requirement.
- Component variant duplication (Chips×3 / Tabs×3 / nav×2, no canonical marker) is a
  component-structure concern — pick canonical per slice on the implementation side.

---

## 3. Current app foundation (for reference)

- `react-native-paper` v5.14.5 — 109 files, used lightly (Text/Button/IconButton/Portal/Card).
- `src/utils/theme.ts`: MD3-based, 3 variants (light/dark/**x1**, x1 to be removed), 50+
  semantic tokens, `createStyles(theme)` + `useTheme()`, MobX `uiStore.colorScheme`.
- Inter fonts bundled via `react-native.config.js`. 65 custom components. Drawer nav
  (`@react-navigation/drawer` v7), 6 screens.
- Architecture is a good fit for a mode-aware token collection — the migration is a
  token re-map + new components + restyle, not an architecture change.

---

## 4. Phased plan & sub-issues

| Phase | Sub-issue | Scope |
|---|---|---|
| 0 — Decisions | **FOU-113** | Inputs locked (this doc). Remaining: confirm component-variant canon per slice as encountered. |
| 1 — Foundation (invisible) | **FOU-114** | Token module (single Spacing/Radius scale + aliases); add Fraunces + Fraunces-Italic + JetBrains Mono (static cuts, iOS+Android); decouple theme from MD3; **RTL + non-Latin fallback rule**; map current visuals onto tokens so app is unchanged. `NATIVE_CHANGES=YES`. |
| 2 — Component library (parallel) | **FOU-115** | New components against tokens, same API where possible. Pick **one representative bespoke sheet** as the working sheet/modal pattern — do not block on a delivered Modal component. |
| 3a — Onboarding | **FOU-116** (TASK-20260526-1731, app PR #747 — Round-3 Figma-faithful retrofit in flight) | Screens 1–6 (`884:28223`). Greenfield (no onboarding today). relatedTo FOU-98. Promoted flow doc: `context/architecture/onboarding.md` (Round-3 corrections absorbed in-place). |
| 3b — Home + Chat | **FOU-117** | Homepage + Chat (advanced details/reasoning, multiple answers, audio, temp chat). Preserve markdown/table/thinking rendering. |
| 3c — Models + recovery | **FOU-118** | Model screens + load/error/recovery states. UX improvement, not pure reskin. |
| 3d — Pals | **FOU-119** | My Pals + Create/modify pal (General/Generation, assistant/Roleplay/video). |
| 3e — Settings + Auth | **FOU-120** | Settings (~20 screens) + Log in/sign up/account. |
| 3f — PalsHub | **FOU-121** | Explore + Pal-details + Create-pal. Screens are in the canonical file (no separate file dependency). |
| 3g — Search | **FOU-122** | 4 search states. |
| 4 — Cleanup | **FOU-123** | Remove `x1Theme`, dead components, legacy Paper; final a11y/RTL/l10n pass; update `context/architecture/*.md`. |

Blocked-chain: 113→114→115; 115 blocks 116–122; 116–122 block 123.
Each Phase 1+ slice runs the dev-team pipeline (standard/complex) when picked up.

---

## 5. Cross-cutting (every slice)

- **testID freeze.** Restyling restructures the component tree, which changes the
  accessibility tree Appium queries (selectors that match by text/hierarchy/position
  break even when behavior is identical — see the documented iOS
  `TouchableWithoutFeedback` / `byText` vs `byStaticText` gotchas). Keep `testID`s and
  accessibility labels stable as a migration contract so the E2E pipeline survives.
- **RTL + non-Latin** verified per slice, not deferred entirely to Phase 4.
- **Light + dark** parity checked per slice (dark = the `3011:*` render).
- Update the relevant `context/architecture/*.md` flow doc in the same PR as any
  behavior change (repo non-negotiable).
