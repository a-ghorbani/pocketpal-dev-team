# Explore Tab

## Purpose

This doc covers the Explore bottom-tab root (`ExploreScreen`): PalsHub pal discovery (browse, filter, sort, search, paginate), the segmented `[Pals | Models]` container, and the pal-details sheet that Explore opens.

Other flow docs own the neighbouring pieces:

- purchase and ownership: `palshub-checkout.md`
- pal configuration: `pals-and-talents.md`
- the tab shell: `app-shell.md`
- tokens and DS components: `theming.md`

**Branch:** the code exists only on the `redesign/phase-3` integration branch. `main` (v1.17.3) has no `ExploreScreen` and no bottom tabs. Every path below is relative to `src/` on that branch.

## Code map

| Path | Role |
| --- | --- |
| `navigation/MainTabs.tsx` | Mounts `ExploreScreen` as the `ExploreTab` root |
| `screens/ExploreScreen/ExploreScreen.tsx` | Header, sign-in promo card (signed-out only), DS `Tabs` `variant="pill"`, the `AuthSheet` host, and the Models "coming soon" placeholder |
| `screens/ExploreScreen/components/ExplorePalsPanel.tsx` | Owns all discovery state: filters, sort, debounced search, pagination, the detail and login gates, and the overlay |
| `…/components/ExploreFilterRow.tsx` | Filter openers (`categories`, `price`, `tags`) |
| `…/components/ExploreSortControl.tsx` | Opens the sort sheet |
| `…/components/CategoryFilterSheet.tsx`, `TagsFilterSheet.tsx` | Options from `palStore.getCategories()` and `getTags()`, shown in the legacy `components/Sheet` |
| `…/components/PriceFilterSheet.tsx`, `SortFilterSheet.tsx` | Price range; `SortOption` is any `PalsQuery['sort_by']` value except `rating`, which the API orders like `popular` |
| `…/components/PalCardList.tsx` | Single-column discovery row |
| `…/components/ExploreSearch.tsx` | `ExploreSearchToggle` (`explore-search-toggle`) |
| `…/components/ExploreSearchOverlay.tsx` | Search overlay in a Paper `Portal`: scrim, DS `Input`, and four body states |
| `…/components/ExploreSearchResultRow.tsx` | Overlay result row |
| `…/components/LoginRequiredModal.tsx` | DS `Dialog` shown when a signed-out user taps a premium pal |
| `components/PalsHub/PalDetailSheet/PalDetailSheet.tsx` | Pal details plus the download, buy and owned actions. Explore is its only mount |
| `store/PalStore.ts` | `searchPalsHubPals`, `isLoadingPalsHub`, `getCategories`, `getTags`, `isCheckoutEligible`, `downloadPalsHubPal` |

## How it works

`ExploreScreen` holds only `subTab` and `showAuth`. The Models item is `disabled`, so the DS `Tabs` never fires `onChange` for it, and `subTab` stays `'pals'`.

`ExplorePalsPanel` works as follows:

- **Query.** `buildQuery(page)` composes a `PalsQuery` from `sort` (default `'newest'`), `categoryIds`, `tagNames`, `priceRange` and `debouncedQuery` (the input trimmed after a 300 ms debounce).
- **Page 1.** Any change to `buildQuery` bumps `seqRef`, resets `pageRef` to 1, and calls `palStore.searchPalsHubPals(buildQuery(1))`. The response replaces `items` and sets `hasMore` from `response.has_more`, but only if the token is still current.
- **Paging.** `FlatList` `onEndReached` calls `loadMore`, which fetches the next page and appends to `items` under the same token check.
- **Footer.** It shows a spinner while loading more. When `items` is non-empty, nothing is loading and `!hasMore`, it shows the reached-the-end check-circle with a title and subtitle. `ListEmptyComponent` shows a spinner while `isLoadingPalsHub`, otherwise "No Pals found".
- **Card tap.** `handleCardPress` checks for a premium, unowned pal (`price_cents > 0 && !is_owned`). If the user is signed out it opens `LoginRequiredModal`, whose action calls `onSignInPress`, which leads to `AuthSheet`. Otherwise it sets `selectedPal` and opens `PalDetailSheet`.
- **Search.** `searchExpanded` mounts `ExploreSearchOverlay`, which re-presents the same `searchInput`, `debouncedQuery` and `items`. The body is chosen in this order:
  1. prompt, when `debouncedQuery === ''`
  2. loading, when `isLoadingPalsHub`
  3. no results, when `items.length === 0`
  4. results
- **Closing search.** The scrim, the "Explore Pals" call to action and a result-row tap all run `closeSearch()` (collapse the overlay and clear the input). A result tap then calls `handleCardPress`.

## Contracts and invariants

- **No new persisted state.** All Explore UI state is React state in `ExploreScreen` and `ExplorePalsPanel`. `ExploreScreen` reads `authService.isAuthenticated` and passes it to the panel as a prop; the panel reads `palStore`. Neither writes either.
- **Single writers.**
  - `PalStore.searchPalsHubPals` owns `isLoadingPalsHub` and `cachedPalsHubPals`.
  - `PalStore.downloadPalsHubPal` owns local pal rows.
  - `CheckoutFlowStore` owns checkout state (`palshub-checkout.md`).
  - Only the server sets ownership (`is_owned`); the sheet re-reads the pal when `checkoutFlowStore.status === 'owned'`.
- **Last query wins.** Every response, including page fetches, is applied only if `seqRef` is unchanged, so a slow earlier response cannot overwrite a newer query (`ExplorePalsPanel.tsx`).
- **Two separate gates.**
  - *Sheet access:* `handleCardPress` blocks a signed-out user from opening a premium, unowned pal.
  - *Buy action:* inside `PalDetailSheet`, `handleBuyPress` sends a signed-out user to `onSignInPress`. `buy-button` renders only when `palStore.isCheckoutEligible`; otherwise the sheet shows informational text.
  - Keep both gates; the predicates are commented as a pair.
- **Buying.** Both platforms call `checkoutFlowStore.start(pal.id)` directly. There is no web-buy link-out in the sheet.
- **No navigation-topology change.** The detail surface is a sheet, with no route and no `RootStackParamList` entry.
- **Frozen testIDs on `PalDetailSheet`:** `buy-button`, `download-button`, `downloaded-button`, `checkout-signin-button` and `pal-label-<type>`, plus the legacy `Sheet` chrome `sheet-close-button` / `sheet-handle`. Explore's own `explore-*` testIDs are additive. The consumers are `e2e/pages/PalPurchasePage.ts` and `e2e/helpers/selectors.ts`.
- **Accessibility labels in the overlay.** The scrim is labelled `common.close`, the clear control `common.clear` (with `hitSlop` to reach a 44 px target), and the input and toggle `explore.searchLabel`.
- **Styling.** Colours, type, spacing, radius and stroke come from tokens. The literal sizes are the 56 px avatar and the 44 px minimum touch target. `screens/ExploreScreen` and `components/PalsHub/PalDetailSheet` are on the token-consumer allow-list (`theming.md`, "Contracts and invariants").

## Traps and decisions

- **Close the overlay before opening the sheet.** The overlay is a Paper `Portal` that paints above the `@gorhom/bottom-sheet` host. If the sheet opened under a mounted scrim, the scrim would swallow the sheet's touches, so the result-row handler calls `closeSearch()` first.
- **The overlay's prompt body depends on `debouncedQuery`, not `items.length`.** The overlay shares `items` with the list behind the scrim, so `items` is non-empty before the user types anything.
- **Don't read `cachedPalsHubPals` for the list.** `searchPalsHubPals` overwrites it with each response, so it holds only the last page from the last caller. The panel accumulates its own `items`.
- **The loading flag is store-wide.** `isLoadingPalsHub` is not scoped to the panel's query, so any other PalsHub fetch flips the overlay into its loading body.
- **Failures look like zero results.** `searchPalsHubPals` catches errors and returns `{pals: [], has_more: false}` with `syncState: success`, so a failed fetch is indistinguishable from zero results. The no-results copy is therefore neutral; a real error state would need a store-level error signal.
- **The purchase e2e can't reach a card on this branch.** `purchase-flow.spec.ts` still goes drawer → Pals and `PalPurchasePage` taps `palshub-pal-card-<id>` (only the unmounted `SquarePalCard` renders it); Explore rows are `explore-pal-card-<id>`. Retarget both when this branch lands.
- **The Models sub-tab is a stub.** It is disabled, and the standalone Models screens do not render inside Explore.
- **Only part of the rating block is shown.** The sheet shows `average_rating`, `review_count` and the created date. The Figma reviews list, discussions and Q&A are not rendered because no backend supports them.

## Verification

- Unit tests (on `redesign/phase-3`):
  - `screens/ExploreScreen/__tests__/ExploreScreen.test.tsx`
  - `components/PalsHub/PalDetailSheet/__tests__/PalDetailSheet.test.tsx`, which includes Android `Platform.OS` buy cases
  - `navigation/__tests__/MainTabs.test.tsx`
- e2e: `e2e/helpers/selectors.ts` has only the tab item (`tabs.explore` → `ui-bottom-nav-item-ExploreTab`); there are no Explore-surface selectors yet.
- By hand:
  1. Signed out: the promo card shows, and tapping a premium card opens the "Create an Account" dialog.
  2. Signed in: apply category, tag, price and sort filters and confirm the list refetches; scroll to the end-of-list footer.
  3. Open search: the prompt shows first. Type a query with no results; the "Explore Pals" button clears it. Tap a result and confirm the sheet opens and responds to touches.
  4. Repeat in dark mode and in `he` or `fa`.
