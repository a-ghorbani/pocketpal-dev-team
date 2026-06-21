# Explore Tab

**Purpose**: cumulative architecture truth for the **Explore** bottom-tab root
(`ExploreScreen`) — the PalsHub **discovery** surface and its segmented
`[Pals | Models]` sub-tab container. This doc owns the discovery/browse UI only.
The **purchase** flow lives in `palshub-checkout.md`; pal **configuration**
(PACT/talents/greeting) lives in `pals-and-talents.md`; the bottom-tab shell and
nav topology live in `app-shell.md`. Tokens resolve via `theming.md`.

Status: **Pals discovery shipped; Models sub-tab is a disabled stub.** The
detail surface is the existing `PalDetailSheet`, reskinned in place — no nav
topology change.

Convention:
- **(C)** = current behaviour, documented from code
- **(D)** = decision (was open, now resolved)

---

## 1. Surface

`ExploreScreen` (C) is mounted by `MainTabs` as the `ExploreTab` root
(`MainTabs.tsx`), unchanged. It renders, top to bottom:

- a header ("Explore");
- a sign-in promo card ("Get your pals" → "Log in to Palshub"), shown only when
  `!authService.isAuthenticated`;
- the DS `Tabs` (`variant='pill'`) segmented `[Pals | Models]` container;
- the active sub-tab panel.

The promo card's CTA and any gated discovery action route to the existing
`AuthSheet` (no new auth behaviour).

**Glossary:**
- **Sub-tab** — the segmented `[Pals | Models]` container (DS `Tabs`).
- **Pals sub-tab** — the PalsHub discovery surface (browse/filter/search public
  pals); a single-column **Card-List** layout, distinct from PalsScreen's
  2-column `SquarePalCard` grid.
- **Models sub-tab** — a present-but-disabled segment with a "coming soon"
  placeholder; content is owned by a separate Models slice.
- **Pal-details** — the existing `PalDetailSheet` bottom-sheet, reskinned in
  place (tokens only; behaviour byte-preserved).

---

## 2. Data model

**No new persisted model, no new store, no data-model change.** The discovery
surface is built from existing `palStore` discovery state + existing wire types.

```
ExploreScreen local UI state (C, React state — not persisted, not a store)
  subTab        : 'pals' | 'models'   // 'models' is disabled (never selected)
  activeFilters : category ids + price range (local)
  searchQuery   : string
  searchExpanded: boolean
  openSheet     : 'none' | 'categories' | 'price'
  selectedPal   : PalsHubPal | null   // for the detail sheet
  hasMore       : boolean             // reached-the-end signal

Read from palStore (C, all existing):
  cachedPalsHubPals : PalsHubPal[]        // discovery results
  isLoadingPalsHub  : boolean
  searchPalsHubPals(query)                // → PalsResponse (has_more on response)
  getCategories() / getTags()             // filter-sheet options
  isPalsHubPalDownloaded(id)
  isUSRegion                              // buy-button region gate (in the sheet)
```

Filter/sort/search compose a `PalsQuery` (`category_ids` / `tag_names` /
`price_min` / `price_max` / `query`) passed to `searchPalsHubPals`. The
**reached-the-end** signal reads `has_more` off the **resolved response** —
`PalStore.searchPalsHubPals` persists only `cachedPalsHubPals`, not `has_more`.

---

## 3. State machine

The discovery surface has a small load lifecycle (read off `isLoadingPalsHub` +
result count + `has_more`); no new persisted lifecycle. Checkout lifecycle is
owned by `palshub-checkout.md` (unchanged).

| State | User-visible feedback |
| --- | --- |
| loading | spinner in the Pals panel (`isLoadingPalsHub`) |
| results | Card-List rows; "Available Pals" header + sort + search |
| empty | "No Pals found" empty state |
| reached-the-end | check-circle + "You've reached the end" + "Browse Pals on Palshub" (when `!has_more`) |
| login-required | "Create an Account" modal on a gated action while unauthenticated |
| models sub-tab | disabled segment; tap is a no-op; panel shows a "coming soon" placeholder |

---

## 4. Contract

1. **Sub-tab container = DS `Tabs` pill variant (D).** `items=[{value:'pals'},
   {value:'models', disabled:true}]`, `selectedValue=subTab`, `onChange` sets
   `subTab` (only 'pals' is reachable; the disabled item never fires
   `onChange`). Reuses DS `Tabs` frozen testIDs (`ui-tabs`, `ui-tab-item-*`).
2. **Models sub-tab is a deferred stub (D).** Present-but-disabled segment;
   selecting is a no-op; the panel renders a minimal "coming soon" placeholder.
   The standalone Models screens + HF search do NOT reach into Explore.
3. **Pals sub-tab is built from hub-discovery logic, NOT PalsScreen's local
   path (D).** It owns its own discovery state and reads
   `palStore.searchPalsHubPals` / `cachedPalsHubPals` / `getCategories` /
   `getTags`. PalsScreen's local "my-pals" path is left intact and reachable.
4. **Card tap opens the reskinned `PalDetailSheet` (D).** `setSelectedPal(pal)`
   + open the sheet — the same handler shape PalsScreen uses. No navigation.
5. **Gated actions while unauthenticated show the login-required modal (C).** A
   buy/get attempt by a signed-out user opens the "Create an Account" modal,
   routing to the existing auth surface (`AuthSheet`).
6. **Tokens-only.** Every new surface reads `theme.colors/typography/spacing/
   radius/stroke` only — no raw hex/px. Built on Phase-2 DS components; RN Paper
   stays thin.

### 4a. Pal-details reskin (existing sheet, in place)

- `PalDetailSheet` is reskinned in place (D): it stays a `@gorhom/bottom-sheet`
  (`Sheet`); tokens-only restyle of hero, rating summary (display-only),
  categories/tags chips, gated system-prompt, and the download/buy/owned action
  bar + checkout feedback.
- **Behaviour byte-preserved**: `handleAction` (download), `handleBuyPress`
  (incl. the existing `Platform.OS !== 'ios'` web-buy branch — see
  `palshub-checkout.md` drift note), `checkoutFlowStore.start/reset`,
  `shouldShowPalContent` gating, `getPalActionText`, and the
  `checkoutStatus === 'owned'` ownership re-read are all unchanged.
- **Rating summary is display-only (D)**: renders `average_rating` +
  `review_count` + the existing created-date stat. No comments-count (no backing
  aggregate). The Figma reviews-list / discussions / Q&A / add-review blocks are
  NOT rendered (no data backing; separate ticket).

### 4b. Hard invariants

- **testID freeze**: every existing testID on a reskinned pal-details element is
  preserved — `buy-button`, `download-button`, `downloaded-button`,
  `checkout-signin-button`, `pal-label-<type>`, plus the `Sheet` chrome
  `sheet-close-button` and `sheet-handle`. New Explore-surface testIDs are
  additive; they do not replace any frozen id. PalsScreen's discovery testIDs
  stay on PalsScreen — they are NOT migrated (Explore is a distinct layout).
- **light + dark**: all surfaces resolve mode-aware tokens; dark follows
  automatically (verified on device).
- **RTL (he/fa)**: any animated/absolute positioning animates physical `left`
  and mirrors `onLayout` x; verified with a real tab/segment switch under
  forceRTL.
- **no nav-topology change**: no new root-Stack route, no `RootStackParamList`
  delta; the detail surface stays a sheet.
- **no local-path dismantling**: PalsScreen's local my-pals path and its
  `PalDetailSheet` call remain intact and reachable.

---

## 5. Single-writer rule

No new writers. All mutable shared state keeps its existing single writer.

| Field | Single writer |
| --- | --- |
| `CheckoutFlowState` | (C) `CheckoutFlowStore` (palshub-checkout.md) |
| ownership (`is_owned`) | (C) **server** — `getPal()`; never written client-side |
| `cachedPalsHubPals` / discovery results | (C) `PalStore.searchPalsHubPals` |
| pal download → `local_pals` row | (C) `PalStore.downloadPalsHubPal` / `PalRepository` |
| Explore sub-tab / filter / sort / search UI state | (C) `ExploreScreen` local React state (read-only over `palStore`) |
| focused bottom-tab | (C) `@react-navigation` (app-shell.md) — unchanged |

`ExploreScreen` reads `palStore` (discovery + region + downloaded) and
`authService.isAuthenticated`; it writes none of them.

**Deferred (out of scope, tracked elsewhere):**
1. Explore Models sub-tab content → standalone Models slice.
2. Pal-details reviews / discussions / Q&A / add-review → separate PalsHub
   backend ticket.
3. Reconcile the `handleBuyPress` Android web-buy branch with
   `palshub-checkout.md` → checkout-flow owner (preserved verbatim here).
4. Optionally retire PalsScreen's hub-discovery surface once Explore>Pals
   subsumes it → Pals-slice coordination.

---

## 6. Canonical scenarios

| # | Scenario | Outcome |
| --- | --- | --- |
| A | Tap Explore → mounts | header + (signed-out: promo card) + pill Tabs `[Pals* \| Models(disabled)]` + filter row + "Available Pals" + Card-List (or empty / reached-the-end) |
| B | Filter by category | category sheet (chips from `getCategories`) → apply → `searchPalsHubPals({category_ids})` → list re-renders |
| C | Reached the end | response `has_more === false` → check-circle + "You've reached the end" + "Browse Pals on Palshub" |
| D | Card tap → free download | free Card-List row → `PalDetailSheet` → "Get Pal" → `downloadPalsHubPal` → success (behaviour identical to today) |
| E | Buy premium (US, signed-in) | premium card → sheet → buy-button → `checkoutFlowStore.start`; owned → button flips to download (unchanged) |
| F | Gated action signed-out | login-required modal ("Create an Account") → `AuthSheet` |
| G | Models segment inert | tap Models → no-op (disabled); Pals panel stays active; Models shows "coming soon" |
| H | Dark + RTL | all surfaces resolve dark tokens; segment/filter positioning mirrored (physical left); verified on device |

---

## 7. Edge cases

| Edge case | Behaviour |
| --- | --- |
| PalsHub not configured / search fails | `searchPalsHubPals` returns empty; empty state, no error UI |
| Non-US region, premium pal | detail sheet shows info text, no Buy button (preserved) |
| Android premium buy | existing `Linking.openURL(getPalBuyUrl)` web path fires unchanged (drift note) |
| Empty results after filter | "No Pals found" empty state; filters remain adjustable |
| Tap disabled Models segment | no-op; `selectedValue` stays 'pals' |
| Non-Latin pal title (CJK/he/fa) | Fraunces→Inter fallback via theme builder |
