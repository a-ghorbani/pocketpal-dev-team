# POC-30 — Figma design-context pack (extracted by orchestrator)

Design subagents cannot open Figma; this pack is the injected design context. Canonical
file `RZxDJea4t6jnBZrV4YBacF`, page `0:1` "App design". Non-canonical files
`fyC1zC0eq0nJjG5SFDexbY` / `szXSjMGisopPpjgmVjovoB` — do NOT source from them.

Screenshots in this dir (Read them — they are PNGs):
- `home-light.png` — Home, light, 3 variants side by side
- `home-dark.png` — Home, dark, same 3 variants
- `tabs-component.png` — the bottom-tab bar component in isolation

## Locked product decision

**The bottom-tab navigation REPLACES `@react-navigation/drawer` outright.** Not tabs-over-drawer,
not a temporary coexistence. The Drawer (v7, 6 screens today) is removed; the app's top-level
navigation becomes a bottom-tab navigator.

## Bottom-tab bar (canonical node: Tabs instance `888:33854`, 314×48)

Three tabs, left→right: **Chats** · **Explore** · **Settings**.
- Active tab = filled pill (peach/tan in light) with icon + label; inactive = icon + label, no pill.
- Icons: Chats = chat-bubble, Explore = compass, Settings = gear (see `tabs-component.png`).
- Tab → slice ownership: **Chats → POC-7** (Home content + Chat flow), **Explore → POC-11**
  (PalsHub Explore), **Settings → POC-10** (Settings + Auth). This ticket builds the shell +
  Chats/Home scaffold; Explore/Settings destinations are scaffolds/placeholders until their slices land.

## Home screen (canonical: Home section `888:33821` light / `3011:25472` dark)

This is a NEW dedicated screen (no equivalent exists today). Three variants in the metadata:

1. **Homepage - default** (`888:33822`) — title "Chat with your pals" (large, serif/Fraunces);
   horizontal **pal carousel** ("Chat items" ×5: avatar + label, e.g. Social…, Lunabot, Mixpal,
   Immersi…, + an "Add" affordance at the end); an **inline message composer** ("Start messaging
   with <pal>…", with attach `+`, mic, send); a **model chip** ("Model used: ggml-org/…"); and a
   **"Chat history" / "Previous chats" list** below (rows: title + pal name + age + overflow `…`).
   Bottom = the tab bar.
2. **Homepage - first time user** (`888:33856`) — same top (title + carousel + composer + model chip)
   but the history area shows an empty hint: "Select a pal or model, then start typing. Your
   conversations will appear here."
3. **Scrolled up** (`888:33887`) — history list expanded to full height with a sticky "Main Header".

Light vs dark: dark = the `3011:*` render of the same structure (dark derives from the mode-aware
token collection — no per-flow "pick a set" decision). See `home-dark.png`.

## Scope boundaries (this ticket = POC-30)

IN: bottom-tab navigator replacing Drawer; Home screen (all 3 variants) — layout shell + the parts
whose data already exists (pal carousel from existing pals/models, chat-history from existing
sessions, model chip, composer entry point); light+dark; RTL (he/fa); testID freeze contract;
build on Phase-1 tokens + Phase-2 DS.

OUT (sibling slices): Chat active-conversation reskin + message pipeline → POC-7. Settings screens
content → POC-10. Explore/PalsHub screens content → POC-11. Removal of dead Drawer code is in-scope
only insofar as needed to replace it; broad legacy cleanup → POC-13 (Phase 4).

## Open design questions for the architect (resolve in WHAT)

- Exact mapping of the 6 current Drawer destinations onto 3 tabs (which screens become tab roots,
  which become pushed/nested routes, which move under Settings).
- Where the model chip's picker and the composer's "start chat" action route (into the Chat flow
  owned by POC-7 — define the navigation contract/handoff, not the Chat UI).
- Deep-link / existing-navigation-ref impacts of dropping the Drawer (e.g. `pocketpal://` deep links,
  `openDrawer`/`navigation.dispatch(DrawerActions…)` call sites). Drift-check the codebase.

## Current foundation (for reference)

`@react-navigation/drawer` v7, 6 screens; MobX `uiStore.colorScheme`; Phase-1 token module +
Phase-2 DS component library already landed. Rollout plan: `context/redesign/FOU-112-rollout.md`.
