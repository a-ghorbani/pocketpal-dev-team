# FOU-112 designer asks from FOU-114 token extraction

Sourced by HOW Step 0 of TASK-20260519-2110. Canonical file: `RZxDJea4t6jnBZrV4YBacF` (Pocket Pal — Copy — Khatia), page `0:1`. Dark extraction nodes used: `3011:25220, 3011:25472, 3011:25554, 3011:25896, 3011:26529, 3011:26813, 3011:28061, 3011:28506` (the `3011:*` dark band — originally suggested `989:*` IDs returned "invalid node" from `get_variable_defs`; the `3011:*` mirror covers the same screens with their dark-mode binding).

Per WHAT D6, on each disagreement the **current dark Theme value wins** (preserves I1) and the canonical value is logged here for designer review. Per §9a, tokens with no extractable canonical dark binding are also logged so the designer can supply one in a future iteration.

---

## A. D6 disagreements — canonical dark binding exists but differs from current dark Theme

Format: token name — canonical (Figma var) → kept current (theme value).

- `background` — `#0e0d0c` (`Color/Background/Muted`) → kept `#000000`. Canonical canvas is near-black with warm tint; today is pure black.
- `onBackground` — `#fafafa` (`Color/Foreground/Primary`) → kept `#ffffff`. Canonical near-white vs current pure white. Small but visible on solid surfaces.
- `surface` — `#181715` (`Color/Background/Card`) → kept `#0E0E0E`. Different surface lift level; canonical reads as a darker warm card, today is a flatter cold near-black.
- `onSurface` — `#fafafa` (`Color/Foreground/Primary`) → kept `#E2E2E2`. Canonical pushes text closer to pure white than current.
- `surfaceVariant` — `#2a2928` (`Color/Background/Subtle`) → kept `#646466`. Major value gap: canonical is a dark warm tint; today is a mid-grey. Largest visual delta in this list.
- `onSurfaceVariant` — `#c4c2c0` (`Color/Foreground/Secondary`) → kept `#e3e4e6`. Canonical is warmer mid-grey; today is cooler light grey.
- `primary` — `#ffffff` (`Color/Primary/Default`) → kept `#DADDE6`. Canonical is pure white; current is a cool grey. Different semantic — affects FAB tint / accent contrast.
- `onPrimary` — `#0e0d0c` (`Color/Primary/Foreground`, Settings/Onboarding/Homepage) → kept `#44464C`. Canonical near-black on white primary; current is a mid-grey on cool-grey primary. (Note: `Color/Primary/Foreground` resolves to `#fafafa` in the Chat dark frame `3011:25554` — internal inconsistency in canonical file, also worth a designer pass.)
- `secondary` — `#2a2928` (`Color/Secondary/Default`) → kept `#95ABE6`. Semantic mismatch: canonical secondary is a surface-tint role; current secondary is a blue accent role. Reconciling requires deciding which role "secondary" means in the new system.
- `onSecondary` — `#f5eee6` (`Color/Secondary/Foreground`) → kept `#11214C`. Follow-on of the secondary role disagreement above.
- `outline` — `#81807e` (`Color/Border/Strong`) → kept `#444444`. Canonical pushes borders higher contrast. Note: Explore section resolves `Color/Border/Strong` to `#666666` — internal canonical disagreement; both differ from current.
- `outlineVariant` — `#2a2928` (`Color/Border/Light Grey`) → kept `#a1a1a1`. Largest borderline value gap: canonical is a dark warm tint; current is light grey. Likely the canonical token is meant for a different consumer role.
- `text` / `menuText` — `#fafafa` (`Color/Foreground/Primary`) → kept `#ffffff` / `#E2E2E2`. Follow-ons of the foreground-primary disagreement.
- `border` — `#2a2928` (`Color/Border/Light Grey`) → kept `withOpacity(onSurface, 0.05)` (`rgba(226,226,226,0.05)`). Current is `withOpacity` math; canonical has a direct literal binding. Migrating from math to literal is §5 deferred cleanup #4; until then, current math wins.
- `textSecondary` — `#c4c2c0` (`Color/Foreground/Secondary`) → kept `withOpacity(onSurface, 0.5)`. Same pattern: current is `withOpacity` math; canonical offers a literal. Belongs to §5 deferred #4.
- `scrim` — `#00000080` (`Color/Overlay/Overlay`) → kept `rgba(0,0,0,0.25)`. Different alpha (50% vs 25%). Visible on any modal scrim.

## B. Missing canonical dark binding (§9a) — no Figma dark variable extracted for these keys

Carry the current dark Theme value as the dark token; flag for designer to supply a canonical dark binding (or confirm "use the current value").

- `primaryContainer`, `onPrimaryContainer`
- `secondaryContainer`, `onSecondaryContainer`
- `tertiary`, `onTertiary`, `tertiaryContainer`, `onTertiaryContainer` — no `Color/Tertiary/*` variable hit during dark extraction
- `error`, `onError`, `errorContainer`, `onErrorContainer` — no dedicated error variable; the canonical `Color/Red/*` family (Accent/Strong/Subtle/Mute/Highest Contrast) is used for destructive accents and is not 1:1 with error semantics
- `surfaceContainerHighest`, `surfaceContainerHigh`, `surfaceContainer`, `surfaceContainerLow`, `surfaceContainerLowest`, `surfaceDim`, `surfaceBright` — all are `withOpacity`-derived in current theme (§5 deferred cleanup #4); no explicit canonical dark bindings extracted
- `placeholder`, `inverseText`, `inverseTextSecondary` — `withOpacity`-derived; no canonical analogue
- `menuBackground`, `menuBackgroundDimmed`, `menuBackgroundActive`, `menuSeparator`, `menuGroupSeparator`, `menuDangerText` — menu surfaces not exposed as named canonical variables in the dark frames sampled
- `authorBubbleBackground`, `receivedMessageDocumentIcon`, `sentMessageDocumentIcon`, `userAvatarImageBackground`, `userAvatarNameColors`, `searchBarBackground` — message/chat-specific colors; no canonical bindings extracted
- `thinkingBubbleBackground`, `thinkingBubbleText`, `thinkingBubbleBorder`, `thinkingBubbleShadow`, `thinkingBubbleChevronBackground`, `thinkingBubbleChevronBorder` — thinking-bubble palette; no canonical bindings
- `bgStatusActive`, `bgStatusIdle` — status indicators; no canonical bindings
- `btnPrimaryBg/Border/Text`, `btnReadyBg/Border/Text`, `btnDownloadBg/Border/Text` — button accent palette (download/ready/primary states); no canonical bindings
- `iconModelTypeText`, `iconModelTypeVision`, `iconModelTypeAudio` — model-type icon tint palette; no canonical bindings
- `stateLayerOpacity`, `hoverStateOpacity`, `pressedStateOpacity`, `draggedStateOpacity`, `focusStateOpacity` — interaction-layer opacity scalars; canonical doesn't expose these as variables
- `surfaceDisabled`, `onSurfaceDisabled`, `inverseSurface`, `inverseOnSurface`, `inversePrimary`, `inverseSecondary`, `shadow`, `backdrop` — MD3 required keys with no direct canonical mapping in the dark frames sampled

---

## C. Notes for FOU-112 designer

1. The dark side of the canonical file leans warm-near-black (`#0e0d0c` / `#181715` / `#2a2928`), the current production app leans cool-pure-black (`#000000` / `#0E0E0E` / mid-greys). When FOU-115 onwards starts applying the canonical palette, expect a broad mood shift even before per-screen restyle work. FOU-114 explicitly avoids this shift (I1).
2. The `secondary` role meaning is the single biggest semantic decision pending: canonical uses it as a surface-tint slot, current uses it as a blue accent slot. This blocks `secondary` / `onSecondary` / `secondaryContainer` token names from being unambiguous and should be locked before FOU-115 lands.
3. `Color/Border/Strong` resolves to two different values across canonical dark frames (`#81807e` in most, `#666666` in Explore). Internal canonical inconsistency — designer should pick one.
4. `Color/Primary/Foreground` resolves to `#0e0d0c` in most dark frames but `#fafafa` in Chat (`3011:25554`). Same kind of internal inconsistency.
5. The full Tertiary / Error / Container token families have no canonical dark bindings in the screens we sampled. Either (a) the canonical collection doesn't define them and PocketPal should propose its own, or (b) they live in screens not sampled — designer can confirm.
6. The seven `withOpacity`-derived semantic surfaces (`surfaceContainer*`, `surfaceDim`, `surfaceBright`, `border`, `placeholder`, `textSecondary`, `inverseTextSecondary`) are kept as math at the builder layer per WHAT §5 deferred cleanup #4. Migrating them to canonical literals is FOU-115+ work — please supply explicit dark literals for those slots when ready.
