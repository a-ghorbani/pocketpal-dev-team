# Pals Screen Grid

## Purpose

Covers how the Pals screen lays out pal cards: the column count derived from the live window width, the row chunking both render paths share, and the card's content sizing. What a Pal is and how it reaches a chat belongs to `pals-and-talents.md`; buying a paid pal to `in-app-purchase.md`; the redesign branch's replacement surface to `explore-tab.md`.

## Code map

| Path | Role |
| --- | --- |
| `src/screens/PalsScreen/PalsScreen.tsx` | The screen: filters, search, sheets. Computes the layout once per render and picks the sectioned or flat path. Holds the module-scope `SectionGrid` |
| `src/screens/PalsScreen/palGridLayout.ts` | Pure layout module. `H_PADDING` / `GAP` / `MIN_CARD_WIDTH` / `MIN_COLUMNS` / `MAX_COLUMNS`, `computePalGridLayout(width)`, `chunkIntoRows(items, columns)` |
| `src/screens/PalsScreen/components/PalGridRow/` | One row: fixed-width cells with `GAP` between them, one card per cell |
| `src/screens/PalsScreen/components/SquarePalCard/` | The card. Fills its cell, sizes to its content, keeps its footer at the bottom |
| `src/screens/PalsScreen/styles.ts` | Screen and list-container styles. Holds no row style |
| `src/screens/PalsScreen/myPals.ts` | `myPals()`: the owned sections' union, one card per PalsHub id |
| `e2e/pages/PalBuyPage.ts` | e2e consumer of the card testID |

## How it works

`PalsScreen` reads the window width with `useWindowDimensions()` and passes it to `computePalGridLayout`, which returns `columns` and `cardWidth`. `getFilteredData` and `getSectionedData` produce the items; `shouldUseSections` (filter `all` or `my-pals`, and more than one section) picks between a `ScrollView` of `SectionGrid`s and a `FlatList`.

Both paths pass their items through `chunkIntoRows` and render each chunk with `PalGridRow`, which is what makes the two paths agree by construction. The `FlatList`'s `data` is the rows, not the pals, so it needs no `numColumns`. `PalGridRow` wraps each item in a cell `View` carrying `width: cardWidth` and renders one `SquarePalCard` inside it.

## Contracts and invariants

- **Single writers.** `computePalGridLayout` is the only source of `columns` and `cardWidth`; `chunkIntoRows` is the only code that decides row membership; the cell `View` in `PalGridRow` is the only element that sets a card's width. `SquarePalCard` takes no width prop and reads no window or screen dimensions. The list's horizontal inset is `H_PADDING` from `palGridLayout`, the same constant the width identity uses.
- **The grid fills the window exactly.** `2·H_PADDING + columns·cardWidth + (columns−1)·GAP` equals the window width within float tolerance, and `cardWidth` may be fractional. Rows never wrap, so sub-pixel rounding cannot push a cell onto a new line.
- **Columns stay in `[MIN_COLUMNS, MAX_COLUMNS]`**, derived from `MIN_CARD_WIDTH`.
- **Both paths render the same rows** at the same width, because both call the same layout function, chunker and row component.
- **A width change reflows without a remount.** Neither the screen nor the `FlatList` is re-keyed on `columns`, so rotation, split-screen and fold keep the list mounted and its scroll offset. The offset is kept in pixels, so the visible item can shift when row heights change.
- **The height chain.** A row stretches its cells through the default `alignItems: 'stretch'`; the cell itself carries no `flex`. The `flex: 1` chain starts one level down and must stay unbroken: the card's outer `View` → `TouchableOpacity` → Paper `Card` → the `Card`'s `contentStyle` → `cardContent` → `content`. Paper's `Card` is a `Surface`, and on iOS a `Surface` splits the style across two layers, sending `flex` and `height` to the outer layer and the **border and shadow** to the inner one, so the JS chain alone does not survive the platform; `height: '100%'` on the card style is what keeps the inner layer growing.
- **The footer sits on the card's bottom edge because of `marginTop: 'auto'`.** `content`'s `justifyContent: 'space-between'` pins it only while the card is content-height; once the card stretches, that rule spreads the slack across `header`, `middleContent` and `footer`, floating a short description away from the title. The auto margin holds the outcome at any card height.
- **Row keys are positional and id-derived.** The row's start index prefixes the joined item ids, so uniqueness is structural and does not rest on ids being unique. Rows below an insert or delete are re-indexed and remount: inherent to positional keys, not a defect.
- **Text is limited by `numberOfLines` only** — two lines, one when the model warning shows. No character count determines what the user sees, and nothing is ever appended to signal a cut; no display branch carries a character bound at all, non-visible ones included, since `MAX_COLUMNS` clamps the column count and not the card width, so no constant can be shown to sit outside what the card can render. And no fixed height on a container that holds text.
- **testIDs are frozen**: `local-pal-card-<id>` and `palshub-pal-card-<id>` on the card's pressable, `pals-flat-list` on the `FlatList`. e2e resolves `palshub-pal-card-<id>`. Additive: `pal-badge-pending` / `pal-badge-unlocking` on the card, `restore-purchases-row` as the list footer (both render paths) while billing is `ready`.
- **Owned sections are one card per PalsHub id.** `myPals()` unions installed local Pals, purchase-ledger records (except `unfulfillable` and `removed`) and, when signed in, the library and created Pals. The installed card wins, then a listing card, then a card built from the record's snapshot; both the sectioned and the flat `all` / `my-pals` paths use it.
- **Purchase badges sit in the card's footer row**, so they add no height and leave the height chain intact. They show only for `pending_payment` and `unlocking` / `granted` records.

## Traps and decisions

- **Never put `flex` on the cell.** Its parent is a `flexDirection: 'row'`, so flex grows the cell *horizontally* and silently overrides `width: cardWidth`. It shows up only on a partial last row, where the lone card stretches across the row. The cell's height comes from the row's stretch alone. The trap is enforced by a `PalGridRow` test on the flattened cell style, which must fail for a deleted width and for any of `flex`, `flexGrow` or `flexBasis` — the trap covers the whole flex family, not the `flex` shorthand alone.
- **A property that is inert today can wake up when an ancestor starts stretching.** `cardContent`'s `justifyContent` was correctly called inert and stayed inert; `content`'s identical property did not. The difference is which container has slack, and only a device run tells you which.
- **Paper's `Card` does not pass height down.** Its inner container is `flexShrink: 1` with no grow, so without a growing `contentStyle` the stretch stops there and the footer sits at the bottom of the content instead of the card.
- **Don't reintroduce `numColumns` for this grid.** `FlatList` throws on a `numColumns` change at runtime, and re-keying the list to work around that resets the scroll position on every rotation. Rendering rows as items sidesteps both.
- **Fixed heights are what broke the card.** A square `aspectRatio` with fixed inner heights pushed description and warning text outside the card border on phones and left large empty areas on tablets; a fixed chip height clipped the tag label to nothing. The thumbnail band keeps its fixed height deliberately, to line the images up across a row.
- **No clipping safety net.** `overflow: 'hidden'` on the card would hide exactly the regressions this layout is meant to prevent, and would cut the card's shadow.
- **`observer()` memoises the screen.** A parent re-render cannot simulate a rotation, so a test that changes the width must drive it through the dimensions hook itself, the way the real subscription does.
- **Jest cannot prove this layout.** It has no layout engine, so "every glyph sits inside its card's border" and the partial-last-row width are device-capture claims, not test claims.

## Verification

- Tests: `src/screens/PalsScreen/__tests__/palGridLayout.test.ts` (column counts, the width identity, the chunker), `src/screens/PalsScreen/__tests__/PalsScreen.test.tsx` (reflow without remount, both paths agreeing), `src/screens/PalsScreen/components/SquarePalCard/__tests__/SquarePalCard.test.tsx` (full description, warning, tags), `src/screens/PalsScreen/components/PalGridRow/__tests__/PalGridRow.test.tsx` (the cell's width, and the absence of flex on it).
- Gates: `yarn lint`, `yarn typecheck`, `yarn test`.
- By hand: on a phone and on a tablet-width device (`adb shell wm density 240`), open Pals with both sections populated and with a filter active, and rotate portrait → landscape → portrait without relaunching. Check that no text, warning, chip or badge leaves its card, that a partial last row keeps its card at the normal width, and that the tag chip's label is readable. The short-content card is the case to look at — description directly under the title, footer on the card's bottom edge, footers aligned across the row — on **both** platforms, since Android has never been observed with a correctly stretching card. iPad portrait lays out 5 columns and landscape 6, the first device confirmation of the >4-column path.
