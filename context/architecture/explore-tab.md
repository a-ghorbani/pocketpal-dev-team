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

### Search overlay body (C)

When `searchExpanded`, `ExplorePalsPanel` renders a Portal-mounted search
overlay over the dimmed discovery grid. The overlay body is selected from
existing signals (`debouncedQuery`, `isLoadingPalsHub`, `items.length`);
`items` is shared with the grid behind the scrim, so the prompt body is keyed on
`debouncedQuery === ''`, not on `items.length`.

| Overlay body | Selected when | User-visible feedback |
| --- | --- | --- |
| prompt | `debouncedQuery === ''` | centered "Start typing" + "Enter pal name and view available options" |
| loading | query set, `isLoadingPalsHub` | in-overlay spinner |
| 0-results | query set, `items.length === 0`, not loading | "No Results for **{query}**" (query in accent) + helper + "Explore Pals" CTA |
| results | query set, `items.length > 0` | "Search results" header + result rows (avatar + name + `pal.description` subtitle + chevron) |
| closed | `!searchExpanded` | overlay unmounted; discovery grid visible |

A result-row tap **closes the overlay before opening `PalDetailSheet`**: it runs
the shared close-and-clear (`setSearchExpanded(false)` + clear `searchInput`),
then `handleCardPress`. The overlay is a paper `Portal` painted above the
`@gorhom/bottom-sheet` host, so opening the sheet while the overlay is still
mounted would render it under the scrim and the scrim would swallow its touches.

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

### 4c. Search overlay (C)

- **Overlay owned by `ExplorePalsPanel`, gated on `searchExpanded`.** A
  Portal-mounted card sheet (`explore-search-overlay`) over a tap-to-dismiss
  scrim; the panel's filter row, "Available Pals" header, discovery list, and
  footer states stay mounted behind it. The header `ExploreSearchToggle`
  (`explore-search-toggle`) opens it.
- **Inline search input removed from the panel body.** The overlay owns the
  focused input (`explore-search-input`) — a DS `Input` (leading `SearchIcon`,
  trailing clear `explore-search-clear` shown when non-empty) inside a
  token-styled wrapper: rounded accent border (`primary` on focus, `outline`
  otherwise), mode-aware `secondaryDefault` fill, the DS Input bottom divider
  tucked so there is no double divider. No raw hex; no shared DS-Input edit.
- **Behaviour byte-preserved.** `searchInput`/`debouncedQuery`, the 300ms
  debounce, `buildQuery`, `searchPalsHubPals`, and the `seqRef`/`pageRef`
  last-query-wins guard are unchanged; the overlay only re-presents that state.
- **Result-row tap closes the overlay, then reuses `handleCardPress`** — it
  first runs the shared close-and-clear (so the paper `Portal` overlay/scrim is
  gone), then opens `PalDetailSheet` via the same premium/unauth gate as a
  discovery card. Close-before-open is required because the overlay Portal paints
  above the `@gorhom/bottom-sheet` host. Subtitle binds `pal.description`
  (`numberOfLines={1}`, dropped when empty); no static literal, no l10n key.
- **Accessibility labels are distinct per control** — the backdrop dismiss
  Pressable (`explore-search-scrim`) is labelled `common.close`, the trailing
  clear control (`explore-search-clear`) `common.clear`, and the focused input
  (`explore-search-input`) `explore.searchLabel`; the clear control carries a
  `hitSlop` to reach a ~44px touch target.
- **"Explore Pals" CTA** (`explore-search-explore-cta`, 0-results) =
  `setSearchExpanded(false)` + clear `searchInput` → overlay closes onto the
  discovery grid. A real action, not a dead control; same dismiss-and-clear as
  the scrim/close path.
- New overlay testIDs are additive and screen-scoped:
  `explore-search-overlay`, `explore-search-scrim`, `explore-search-clear`,
  `explore-search-prompt`, `explore-search-no-results`,
  `explore-search-explore-cta`, `explore-search-results-header`,
  `explore-search-result-row-<pal.id>`. `explore-search-toggle` /
  `explore-search-input` are preserved verbatim.

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
| PalsHub not configured / search fails | `searchPalsHubPals` swallows the failure and returns empty (sets `syncState: success`), so a failed fetch is indistinguishable from a genuine zero-results in the overlay 0-results body. Copy stays neutral rather than asserting "no matches"; an honest error/retry state needs a store-level error signal (follow-up) |
| Non-US region, premium pal | detail sheet shows info text, no Buy button (preserved) |
| Android premium buy | existing `Linking.openURL(getPalBuyUrl)` web path fires unchanged (drift note) |
| Empty results after filter | "No Pals found" empty state; filters remain adjustable |
| Tap disabled Models segment | no-op; `selectedValue` stays 'pals' |
| Non-Latin pal title (CJK/he/fa) | Fraunces→Inter fallback via theme builder |
