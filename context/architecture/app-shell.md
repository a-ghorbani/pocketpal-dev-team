# App Shell (bottom-tab navigation) + Home screen

Cumulative architecture truth for PocketPal's top-level navigation shell and
the Home screen (the Chats-tab root). Promoted from
`workflows/stories/TASK-20260619-1332/what.md` (POC-30, redesign foundation).

Conventions: **(C)** current behaviour from code · **(D)** decision with rationale.

---

## 1. Data model

No persisted model. One navigation-topology shape and one DS-component axis.

```
RootStackParamList  (src/utils/types.ts)   (C)
  MainTabs: undefined          // the tab navigator (NOT a leaf screen)
  Chat: undefined              // full-bleed, pushed above tabs (POC-7 owns UI)
  Models: undefined            // pushed above tabs
  'Pals (experimental)': undefined   // pushed above tabs
  Benchmark: undefined         // pushed above tabs
  Settings: undefined          // served by SettingsTab (not registered as a pushed screen)
  'App Info': undefined        // pushed above tabs
  'Dev Tools': undefined       // debug-only, pushed above tabs
  BenchmarkRunner: undefined   // E2E-only, pushed above tabs (deep-link target)

MainTabParamList   (C)
  ChatsTab: undefined          // root = Home screen
  ExploreTab: undefined        // root = Explore placeholder (POC-11 scaffold)
  SettingsTab: undefined       // root = existing Settings screen (POC-10 owns reskin)
```

Persisted: none. Derived: the focused tab `selectedValue` is read from the
navigator's state, never stored.

**Glossary:**
- **App shell** — the root navigation container: `NavigationContainer →
  BottomSheetModalProvider → SwitchPoint → RootStack → MainTabs`.
- **Tab root** — the screen at the base of a tab (Home / Explore-placeholder /
  Settings).
- **Pushed route** — a sibling route on the root Stack rendered full-bleed above
  the tab bar (Chat, Models, etc.).
- **Home** — the Chats-tab root screen (`src/screens/HomeScreen`): serif title,
  pal carousel, composer, model chip, chat-history list.
- **Floating BottomNavBar** — the canonical peach-pill tab bar; the
  `variant='floating'` value on the DS `BottomNavBar` (see theming.md).
- **start-chat handoff** — the nav contract from Home's composer / history row
  INTO the Chat flow (POC-7), reusing the pending-message + active-pal mechanism.

### 1b. External shape

No wire-format change. Deep-link URLs (`pocketpal://chat?…`,
`pocketpal://hub/run?…`, `pocketpal://e2e/benchmark`) are unchanged; only the
navigator that resolves the target route name changed (Drawer → root Stack).
All targets are flat route names on the root Stack, so the existing
`navigate(ROUTES.*)` calls resolve unchanged.

---

## 2. Event flow

```
App launch (post-onboarding, hydrated)
  SwitchPoint mounts RootStack
    RootStack initial route = MainTabs → Tab.Navigator (initial tab = ChatsTab → Home)
  tab tap
    BottomNavBar.onSelect(value) → navigation.navigate(<value tab route>)   [single nav writer]
  Home composer "start chat" / history row tap
    → start-chat handoff (§4a) → navigation.navigate(ROUTES.CHAT)
  Home model chip tap
    → ChatPalModelPickerSheet opens (sheet above shell); no navigation
  deep link pocketpal://chat?palId=…&message=…
    → useDeepLinking.handleChatDeepLink: setPendingMessage + setActivePal → navigate(ROUTES.CHAT)
  deep link pocketpal://hub/run?…
    → deepLinkStore.setPendingHubRun → HubRunSheetHost (above the shell)
```

---

## 3. State machine

No new lifecycle. Tab focus is owned by `@react-navigation/bottom-tabs`.

| State | User-visible feedback |
| --- | --- |
| ChatsTab focused, no pushed route | Home screen + floating tab bar; Chats item = peach pill |
| pushed route on top (e.g. Chat) | full-bleed screen with its own header/back; tab bar NOT shown |
| return from pushed route | lands back on the previously-focused tab (Stack pop) |

---

## 4. Contract

### 4a. Navigation topology & start-chat handoff

1. **Root is a Stack, first screen is Tabs (D1).** `SwitchPoint`'s
   post-onboarding branch mounts `RootStack.Navigator` whose `initialRouteName`
   is `MainTabs`. `MainTabs` is the `@react-navigation/bottom-tabs` navigator
   with three screens: `ChatsTab` (Home), `ExploreTab` (placeholder),
   `SettingsTab` (existing Settings screen).
2. **Drawer is removed outright (D2).** `@react-navigation/drawer` is not
   mounted; `SidebarContent` is not rendered as drawer content. (Dead-code file
   removal → POC-13.)
3. **Tab bar is the DS `BottomNavBar`, floating variant (D3).** `MainTabs`
   passes a custom `tabBar` rendering `<BottomNavBar variant="floating"
   items=[Chats,Explore,Settings] selectedValue={focusedTab} onSelect={navigate}
   />`. The native tab bar is off. Items left→right: Chats (chat-bubble),
   Explore (compass), Settings (gear). The floating bar reads
   `theme.colors.accent.peach` for the active-item pill (see theming.md).
4. **Non-tab destinations are pushed routes on the root Stack (D4).** `Chat`,
   `Models`, `Pals (experimental)`, `Benchmark`, `App Info`, `Dev Tools`
   (debug-only), `BenchmarkRunner` (E2E-only) are sibling Stack routes above
   `MainTabs`, rendered full-bleed with their own header/back, no tab bar. Their
   route-name strings are unchanged. `BenchmarkRunner` is injected by `App.tsx`
   (the only module allowed to import from `src/__automation__/`) via the
   `renderAutomationScreens` prop.
5. **Start-chat handoff reuses the existing prefill contract (D5).** Home's
   start-chat entry points (composer send, history-row tap) do NOT implement
   chat UI. Composer send: optionally `deepLinkStore.setPendingMessage(text)`,
   then `await chatSessionStore.setActivePal(palId)`, then
   `navigation.navigate(ROUTES.CHAT)`. History row:
   `await chatSessionStore.setActiveSession(id)` then `navigate(ROUTES.CHAT)`.
   `ChatScreen` consumes `pendingMessage → initialInputText`. POC-7 owns
   everything inside `ChatScreen`.
6. **Model chip picker (D6).** The Home model chip opens the existing
   `ChatPalModelPickerSheet` (conditionally mounted, like ChatView). Selecting a
   model sets the active model via the sheet's existing `modelStore.selectModel`
   path; it does NOT navigate.
7. **`openDrawer()` call sites are replaced; only the HeaderLeft hamburger loses
   `menu-button` (D7).** `HeaderLeft` (rendered in `ChatHeader`) converts
   `openDrawer()` → `goBack()` with a back icon and a `back-button` testID;
   `DevToolsScreen`'s home-screen menu button converts to `goBack()`. The chat
   `HeaderRight` overflow keeps `testID="menu-button"`; `ModelsHeaderRight` keeps
   `models-menu-button`. The collision that previously had two `menu-button`
   elements is gone, so the e2e generation-settings helper taps `menu-button`
   directly.
8. **Home data wiring (D8).** Home wires only existing data: pal carousel ←
   `palStore.pals`; chat-history list ← `chatSessionStore.sessions`; model chip
   ← `modelStore.activeModel`. Sibling-slice areas render placeholders. No new
   store, no new persistence.

### 4b. Hard invariants

- **I1 — Drawer fully replaced.** No `@react-navigation/drawer` navigator is
  mounted and no `openDrawer()`/`DrawerActions` executes at runtime. Top-level
  switching is the bottom-tab bar only.
- **I2 — No orphaned screens.** Every prior destination (Chat, Models, Pals,
  Benchmark, Settings, App Info, Dev Tools, BenchmarkRunner) is still reachable
  — as a tab root or a pushed route.
- **I3 — Single nav writer for tab selection.** Tab selection navigates
  exclusively through `BottomNavBar.onSelect → navigation.navigate(tabRoute)`.
  `selectedValue` is a pure read of the focused route; never stored elsewhere.
- **I4 — Chat UI ownership unchanged.** This shell never renders chat
  conversation UI; it navigates to `ROUTES.CHAT` and prefills via the existing
  store contract (POC-7 owns Chat).
- **I5 — Deep links resolve unchanged.** `pocketpal://chat`,
  `pocketpal://hub/run`, `pocketpal://e2e/benchmark` reach the same
  destinations. Chat/benchmark targets are flat root-Stack routes; hub/run
  remains a sheet host above the shell. No deep-link handler logic changed.
- **I6 — DS default snapshot byte-identical (theming I_UI5).** The floating
  tab-bar styling is an additive `BottomNavBar` variant; the `default` variant
  snapshot is unchanged; floating ships its own snapshot cells.
- **I7 — testID freeze honored / migrated deliberately (theming I_UI6).** The
  tab bar keeps DS testIDs `ui-bottom-nav` / `ui-bottom-nav-item-<value>`. The
  single deliberate migration is the removed HeaderLeft hamburger losing
  `menu-button` (now `back-button`); chat HeaderRight overflow and
  `models-menu-button` keep theirs. Appium specs that relied on the hamburger
  are updated in the same PR.
- **I8 — Tokens-only DS.** The floating variant reads only
  `theme.colors.accent.peach`, `theme.colors.shadow`, `theme.radius.*`,
  `theme.spacing.*`, `theme.stroke.*`; `BottomNavBar` imports no store.

### 4c. Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| `RootStack` | `MainTabs` + full-bleed pushed routes (Chat, Models, Pals, Benchmark, App Info, Dev Tools, BenchmarkRunner) | a drawer; chat conversation UI |
| `MainTabs` | three tab roots (Home, Explore-placeholder, Settings) + floating `BottomNavBar` | native tab bar; pushed-route content |
| `BottomNavBar` floating variant | rounded floating bar; active item on `theme.colors.accent.peach` pill (mode-aware: light `#FCE7CF` / dark `#7A4A1F`); icon + label | change to the `default` variant's snapshot |
| `HomeScreen` | serif title "Chat with your pals", pal carousel (`palStore.pals` + Add affordance), composer entry, model chip, chat-history list (`chatSessionStore.sessions`) or empty hint | chat conversation UI; Explore/Settings content; new persistence |
| `ExploreScreen` (placeholder) | a scaffold placeholder | PalsHub Explore content (POC-11) |
| Pushed routes (reused) | each screen's existing UI with a Stack header/back | the tab bar |

---

## 5. Single-writer rule

| Field | Single writer |
| --- | --- |
| focused tab / nav stack | `@react-navigation` navigators (Stack + Tabs); no app store mirrors it |
| `BottomNavBar.selectedValue` | derived read of the focused tab route (no writer) |
| active pal for start-chat | `chatSessionStore.setActivePal` (existing) |
| active session for history open | `chatSessionStore.setActiveSession` (existing) |
| chat prefill text | `deepLinkStore.setPendingMessage` (existing — reused by Home composer) |
| active model | existing `modelStore` selection path (via `ChatPalModelPickerSheet`) |

Cross-store reads: Home reads `palStore.pals`, `chatSessionStore.sessions`,
`modelStore.activeModel` (read-only observer). No new write coupling.

### Deferred cleanups (out of current scope)

1. Delete dead `SidebarContent` + drawer-only files → POC-13.
2. Re-home Models / Benchmark / Pals / App Info under their conceptual tab →
   POC-10 / POC-11.
3. Explore tab content → POC-11; Settings reskin → POC-10.
4. Migrate the remaining Appium specs and page helpers (DrawerPage,
   `model-actions`, `SettingsPage`, the per-feature specs) off the drawer
   navigation model to the tab/Home model. Only `quick-smoke` was migrated in
   POC-30; `ChatPage.openDrawer` is retained but deprecated.

---

## 6. Canonical scenarios

### A. Tab switch
```
On Home (ChatsTab) → tap "Settings" tab item
→ navigate(SettingsTab) → Settings screen shown; Settings item = peach pill
```

### B. Start chat from composer
```
Home composer: type "hi", active pal = Lunabot, tap send
→ setPendingMessage("hi") + setActivePal(Lunabot) → navigate(ROUTES.CHAT)
→ ChatScreen opens full-bleed (no tab bar), input prefilled "hi"  (Chat UI = POC-7)
```

### C. Open chat from history row
```
Home history list → tap a previous-chat row
→ setActiveSession(id) → navigate(ROUTES.CHAT) → ChatScreen full-bleed (POC-7 loads session)
```

### D. Deep link to chat (regression guard)
```
pocketpal://chat?palId=p1&message=hello (app running)
→ handleChatDeepLink → setPendingMessage + setActivePal → navigate(ROUTES.CHAT)
→ Chat opens prefilled; identical to pre-migration
```

### E. First-time-user Home
```
No sessions exist → open Home
→ title + carousel + composer + model chip shown; history area shows empty hint
```

### F. Model chip picker
```
Home → tap model chip
→ ChatPalModelPickerSheet opens (sheet above shell) → pick model → active model set; NO navigation
```

### G. Benchmark E2E deep link (regression guard)
```
pocketpal://e2e/benchmark (e2e build)
→ navigate(ROUTES.BENCHMARK_RUNNER) resolves on the root Stack → runner mounts
```

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| focused tab route | `@react-navigation` Tabs | `BottomNavBar.selectedValue`, Home | that tab is active |
| `deepLinkStore.pendingMessage` | `setPendingMessage` (deep link OR Home composer) | `ChatScreen` via `usePendingMessage` | a chat prefill is awaiting consumption |

---

## 8. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Root Stack hosts the Tab navigator (candidate B) | Keeps flat routes; chat/detail render full-bleed |
| D2 | Remove `@react-navigation/drawer` outright | Locked product decision; not coexistence |
| D3 | Floating peach-pill tab bar via DS `BottomNavBar` `tabBar` | Canonical Figma; DS is presentational, caller wires it |
| D4 | Non-tab destinations = sibling pushed routes, names unchanged | Preserves deep links + existing screen headers |
| D5 | Start-chat reuses `setActivePal`/`setActiveSession` + `setPendingMessage` + `navigate(CHAT)` | Existing prefill contract; no new chat coupling |
| D6 | Model chip opens existing picker sheet, no navigation | Sheet already does pal/model selection; reuse |
| D7 | Remove only the HeaderLeft hamburger's `menu-button`; keep HeaderRight's | Hamburger gone with Drawer; overflow is unrelated |
| D8 | Home wires only existing data; placeholders elsewhere | Foundation slice; sibling slices own their content |
| D9 | Add `@react-navigation/bottom-tabs` (pinned `7.4.9`); reuse existing `stack` | Only the tab lib is new; pinned to match installed `native@7.1.26` peer (≥7.5 needs native ≥7.3.3) |
| D10 | Floating variant is additive; `default` snapshot frozen | Honors theming I_UI5 DS-snapshot invariant |

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | Deep-link chat while a pushed route is already on top | `navigate(ROUTES.CHAT)` resolves on root Stack regardless of focused tab |
| 9b | No active model when composer "start chat" tapped | Existing no-model handling applies; navigation contract unchanged (Chat UX = POC-7) |
| 9c | `Dev Tools` route in release build | Pushed route registered debug-only; absent in release |
| 9d | RTL locale (he/fa) | Tab order and pill follow RN `I18nManager` start/end; tokens carry no directional values |
| 9e | Non-Latin serif title | "Chat with your pals" falls back Fraunces→Inter via the theme builder (no per-screen handling) |
| 9f | Back from a pushed route | Stack pop returns to the previously-focused tab root |
| 9g | Empty `palStore.pals` on Home carousel | Carousel shows only the "Add" affordance; no crash |
| 9h | `BENCHMARK_RUNNER` hidden from any visible nav | Pushed route reached only by the E2E deep link; not a tab, not a menu item |
