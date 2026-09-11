# App Shell

## Purpose

The root of the running app, covering five parts:

- the hydration hold;
- the provider tree;
- the switch between onboarding and the main navigator;
- the Drawer navigator with its custom sidebar (navigation items and the chat-session list);
- the global hosts mounted above the navigator.

Neighbouring docs own the rest:

- the onboarding stack and its gate: `onboarding.md`;
- the Chat screen and `chatSessionStore`: `chat-flow.md`;
- deep-link handlers: `deep-linking.md`;
- Settings: `settings.md`;
- `TTSSetupSheet`: `tts.md`;
- themes: `theming.md`.

This doc describes `main`. The bottom-tab shell and Home screen exist only on the unmerged `redesign/phase-3` branch. The previous version of this doc described the branch's version (`git show 1ad6ce1:context/architecture/app-shell.md`); distill it back in when the branch lands.

## Code map

| Path | Role |
| --- | --- |
| `App.tsx` | `AppWithMigrationWrapper` (hydration gate + `HydrationHold`), `App` (providers, `DeepLinkHandler`, `SwitchPoint`, Drawer screens, global hosts) |
| `src/utils/navigationConstants.ts` | `ROUTES`: every route-name string |
| `src/components/SidebarContent/` | Custom drawer content: nav items, session `SectionList`, per-session menu, bulk selection |
| `src/components/HeaderLeft/` | Hamburger that calls `openDrawer()` |
| `src/components/ChatHeader/` | Chat's own header (Chat sets `headerShown: false`); renders `HeaderLeft` + `HeaderRight` |
| `src/components/HeaderRight/`, `ModelsHeaderRight/`, `PalHeaderRight/` | Per-screen header-right menus |
| `src/components/DatabaseMigration/AppWithMigration.tsx` | Wraps `App`, runs the settings migration, overlays `DatabaseMigration` |
| `src/components/DownloadOverlay/`, `HubRunSheetHost/`, `TTSSetupSheet/` | Global hosts above the switch |
| `src/__automation__/AutomationBridge.tsx` | E2E-only root child (hosts `OnboardingBypass`) |
| `src/screens/DevToolsScreen/DevToolsScreen.tsx` | Debug-only; nested stack with its own drawer button |
| `src/utils/types.ts` (`RootDrawerParamList`) | Partial route typing |

## How it works

1. `AppWithMigrationWrapper` renders `HydrationHold` until `isHydrated(uiStore)`, then renders `<AppWithMigration><App/></AppWithMigration>`.
2. `App` builds its providers in this order:
   - `GestureHandlerRootView`, plus `AutomationBridge` when `__E2E__`
   - `SafeAreaProvider`
   - `KeyboardProvider`
   - `PaperProvider`
   - `L10nContext`
   - `MarkdownProvider`
   - `NavigationContainer`, containing `DeepLinkHandler` and a `BottomSheetModalProvider`

   Inside `BottomSheetModalProvider` are `SwitchPoint`, `TTSSetupSheet`, `DownloadOverlay` and `HubRunSheetHost`.
3. `SwitchPoint` re-checks hydration, then renders `OnboardingStack` (see `onboarding.md`) or the Drawer.
4. The Drawer's screens are Chat, Pals, Models, Benchmark, Settings, App Info, Dev Tools (only when `__DEV__`) and `BenchmarkRunner` (only when `__E2E__`). The first screen, Chat, is the initial route. Every non-Chat header uses `HeaderLeft` from `screenOptions`.
5. `SidebarContent` covers navigation and the session list:
   - Nav items call `navigate(ROUTES.X)`.
   - Sessions are sectioned from `chatSessionStore.groupedSessions` (pinned group + date groups).
   - Tapping a session awaits `setActiveSession`, then navigates to Chat.
   - Long-press opens a menu: pin/unpin, rename (`RenameModal`), export, delete, select….
   - Select mode enables bulk export and bulk delete.

## Contracts and invariants

- **One navigator, flat route names.** Every destination is a sibling in the Drawer. `navigate(ROUTES.X)` therefore resolves from any screen, and also from the hosts above the switch (`DownloadBanner` → Models, deep links → Chat / `BenchmarkRunner`). The `ROUTES` strings are the contract, e.g. `'Pals (experimental)'`. Change them only in `navigationConstants.ts`, never inline.
- **Hosts above the switch.** The global hosts are siblings of `SwitchPoint` inside `BottomSheetModalProvider`. They survive navigation and are mounted during onboarding too (`App.tsx:216-218`).
- **Automation boundary.** Only `App.tsx` imports from `src/__automation__/`. `no-restricted-imports` bans it across `src/` (`.eslintrc.js:46-86`); the override at `.eslintrc.js:105-110` exempts only `App.tsx` and `src/hooks/useDeepLinking.ts`. `AutomationBridge` and `BenchmarkRunner` render only when `__E2E__`.
- **Delete order.** Session delete calls `resetActiveSession()` before `deleteSession()` (`SidebarContent.tsx:381-382`), so Chat never resolves a session mid-deletion.
- **testIDs e2e relies on:**
  - `menu-button` is on both the hamburger (`HeaderLeft.tsx:17`) and the chat overflow (`HeaderRight.tsx:178`).
  - `drawer-item-pals` is e2e's drawer-open indicator.
  - The other drawer selectors in `e2e/helpers/selectors.ts` match English labels.

## Traps and decisions

- **Duplicate `menu-button`.** `ChatPage.openDrawer` taps the first match (the hamburger), and `openGenerationSettings` takes the last (the overflow). Renaming either one, or reordering `ChatHeader`, breaks most e2e specs.
- **Why `drawer-item-pals` is the open indicator.** It matches a testID rather than a label, so it survives a language switch. Don't remove it. `drawer-item-{chat,models,benchmark,settings}` also exist. App Info and Dev Tools items have none.
- **`BenchmarkRunner`'s `drawerItemStyle: {display: 'none'}` does nothing.** `SidebarContent` renders only its explicit items, and that is what keeps the runner out of the sidebar. The runner is reachable only through the `pocketpal://e2e/benchmark` deep link.
- **Loose typing.** `RootDrawerParamList` lists only Chat, Models and Settings, and call sites cast (`as any`, `as never`), so the type checker won't catch a bad route name.
- **`HydrationHold` is deliberately neutral.** It is a flat view coloured from `Appearance`, with no branding or text. `App` calls `useTheme()` before `PaperProvider`, so the gate has to wrap `App`, and a plain colour can't clash with either platform's native launch surface. The branded splash belongs to onboarding.
- **`SwitchPoint` re-checks `isHydrated`** even though the outer wrapper already gates on it. The re-check keeps the onboarding decision correct if the outer gate is refactored.
- **`AppWithMigration` delays `migrateAllSettings()` by 2 s** so it doesn't compete with startup.
- **Dev Tools has its own nested stack,** whose menu `IconButton` calls `openDrawer()` directly.
- **Deep links during onboarding.** `DeepLinkHandler` sits above `SwitchPoint`, so a deep link that arrives during onboarding runs its handler, but its `navigate` finds no Drawer route.

## Verification

- **Unit tests:**
  - `__tests__/App.test.tsx`: hydration hold (`hydration-splash`) and mount after hydration.
  - `src/components/SidebarContent/__tests__/`: `SidebarContent.test.tsx` and `SidebarContent.pinned.test.tsx`.
  - `src/components/ChatHeader/__tests__/`.
  - `src/components/HubRunSheetHost/__tests__/`.
- **E2E:**
  - `e2e/pages/DrawerPage.ts` and `ChatPage.openDrawer()`, which nearly every feature spec uses.
  - `e2e/specs/quick-smoke.spec.ts` is the fastest shell check.
  - E2E builds bypass onboarding by default (see `onboarding.md`, Traps and decisions).
- **By hand:**
  - A debug build shows Dev Tools in the sidebar and a release build doesn't.
  - Pin, rename, export and delete a session from the sidebar, and delete the active session while Chat is open.
