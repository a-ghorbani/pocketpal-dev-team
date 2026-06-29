# Screen → Figma node → device capture map (canonical file RZxDJea4t6jnBZrV4YBacF, page 0:1)

Figma LIGHT band = 1xx/2xx/4xx/7xx/8xx/9xx ; Figma DARK band = 3011:* (mode-aware dup).

| key | Screen | Fig light | Fig dark | device cap | capture status |
|---|---|---|---|---|---|
| home | Home (first-time empty, w/ pals) | 888:33856 | 3011:25505 | home-empty-with-pals | OK (tab-chats-active = byte-dup) |
| chat-conversation | Chat — conversation | 139:3792 | 3011:25555 | chat-conversation | OK |
| chat-empty-no-model | Chat — no model loaded | (none; analog greeting 3011:25858) | 3011:25858 | chat-empty-no-model | OK; NO-FIGMA-SOURCE (no-model state) |
| chat-model-picker | Chat — model picker sheet | 454:25590 | 3011:25873 | chat-model-picker | OK |
| chat-gen-menu | Chat — header overflow menu | (none clean; dropdown 3011:25760) | 3011:25760 | chat-generation-settings-menu | OK; weak figma source |
| models-ready | Models — Ready-to-Use tab | 477:13944 | 3011:26004 | models-screen-ready-tab | OK |
| models-explore | Models — Explore tab | 477:20848 | 3011:26085 | models-screen-explore-tab | UNRELIABLE (byte-dup of ready in iOS-light/Android) |
| model-settings | Model Settings sheet | 771:29912 | 3011:26309 | model-settings-sheet | OK |
| explore-pals | Explore — Pals tab (free/empty) | 788:18186 | 3011:28062 | explore-pals-tab | OK (our side empty; figma shows promo+cards) |
| explore-models-stub | Explore — Models sub-tab stub | (none; deferred) | (none) | explore-models-stub | UNRELIABLE (byte-dup of pals) + NO-FIGMA-SOURCE |
| my-pals-downloaded | My Pals — Downloaded tab | 787:17312 | 3011:26198 | my-pals-downloaded | OK (empty, 3010) |
| my-pals-created | My Pals — Created-by-me tab | 787:17312 | 3011:26198 | my-pals-created-tab | OK iOS-light; byte-dup elsewhere |
| create-pal-general | Create/modify pal — General tab | 772:34754 | 3011:28571 | create-pal-form-general | OK |
| create-pal-generation | Create/modify pal — Generation tab | 772:36034 | 3011:28733 | create-pal-form-generation | BLOCKED (byte-dup of general) |
| settings-launcher | Settings root (registered) | 787:19024 | 3011:25948 | settings-launcher | OK |
| settings-preferences | Settings — Preferences | 771:36287 | 3011:26233 | settings-preferences | OK |
| settings-app | Settings — App Settings | 771:36876 | 3011:26211 | settings-app-settings | OK |
| settings-about | Settings — About App | 771:36058 | 3011:26106 | settings-about | OK |
| search-prompt | Search — default/prompt | 989:234988 | 3011:28870 | search-prompt | OK |
| search-0-results | Search — 0 results | 989:235063 | 3011:28943 | search-0-results | OK |

## DEFERRED (PalsHub 3010 down — Figma side only if cheap, no montage)
- Explore populated discovery (788:18914 reg / cards), pal-details (225:19393 / 788:17247 / 3011:26813), filter/sort sheets (989:230881 cat / 989:230920 price), search-results (989:235099 / 3011:28978)

## Capture-quality issues (device side)
- tab-switch captures FAILED → byte-identical dups: models explore==ready (iOS-light, Android both), explore models==pals (all 4), my-pals created==downloaded (iOS-dark, Android both), create-pal generation==general (Android both).
- chat-model-loaded.png actually shows the Home screen (mislabel) — excluded.
- chat-thinking-bubble == chat-conversation (expected; no thinking model).
