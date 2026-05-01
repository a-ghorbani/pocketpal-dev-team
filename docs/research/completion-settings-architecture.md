# Completion Settings Architecture

## Data Stores

```
┌─────────────────────────────────────────────────────────────┐
│                     WHERE SETTINGS LIVE                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. SYSTEM DEFAULTS (code constant)                         │
│     completionSettingsVersions.ts                           │
│     defaultCompletionParams = {                             │
│       temperature: 0.7, enable_thinking: true, ...          │
│     }                                                       │
│     defaultCompletionSettings = same minus prompt/stop      │
│                                                             │
│  2. GLOBAL/PRESET (DB: global_settings table)               │
│     ChatSessionStore.newChatCompletionSettings               │
│     Loaded on init, saved via setNewChatCompletionSettings   │
│     UI: ChatGenerationSettingsSheet (when no active session) │
│                                                             │
│  3. PAL (DB: local_pals.generation_settings column)         │
│     Pal.completionSettings (merged with defaults on read)   │
│     UI: PalGenerationSettingsSheet (from PalSheet form)     │
│     Note: enable_thinking NOT shown in settings UI          │
│                                                             │
│  4. SESSION (DB: completion_settings table)                 │
│     SessionMetaData.completionSettings                      │
│     UI: ChatGenerationSettingsSheet (when active session)   │
│                                                             │
│  5. settingsSource (IN-MEMORY ONLY - NOT in DB!)            │
│     SessionMetaData.settingsSource: 'pal' | 'custom'       │
│     Controls whether pal layer is used or bypassed          │
│     Defaults to 'pal' on every app restart                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Resolution Hierarchy

```
resolveCompletionSettings(sessionId?, palId?)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌──────────────────┐
  │ System Defaults   │  defaultCompletionSettings
  │ enable_thinking:  │  (always true)
  │ temperature: 0.7  │
  └────────┬─────────┘
           │ {...defaults, ...global}
           ▼
  ┌──────────────────┐
  │ Global Settings   │  newChatCompletionSettings
  │ (user presets)    │  (from DB global_settings table)
  └────────┬─────────┘
           │ {...merged, ...palSettings}  (if palId provided)
           ▼
  ┌──────────────────┐
  │ Pal Settings      │  pal.completionSettings
  │ e.g. temp: 0.9   │  (from DB local_pals.generation_settings)
  │ thinking: false   │  (merged with defaults via getter)
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────────────────────────────┐
  │ settingsSource === 'custom' ?            │
  │                                          │
  │   YES → REPLACE all with                 │
  │          session.completionSettings       │
  │          (total override, not merge!)     │
  │                                          │
  │   NO  → Keep merged result from above    │
  └──────────────────────────────────────────┘
```

## First Message Flow (New Chat with Pal)

```
User selects pal (e.g. enable_thinking=false, temperature=0.9)
  │
  │  chatSessionStore.newChatPalId = palId
  │  chatSessionStore.newChatSettingsSource = 'pal'
  │
  ▼
User types message and hits send
  │
  ▼
handleSendPress()
  │
  ├──1── addMessage(textMessage)
  │        │
  │        ▼
  │      addMessageToCurrentSession()
  │        │
  │        │  activeSessionId is null → create new session
  │        │
  │        ▼
  │      const settings = {...this.newChatCompletionSettings}  ← GLOBAL ONLY!
  │      createNewSession(title, [message], settings)
  │        │
  │        │  Session stored in DB with:
  │        │    completionSettings = GLOBAL settings (not pal!)
  │        │    activePalId = newChatPalId
  │        │    settingsSource = 'pal' (in-memory only)
  │        │
  │        ▼
  │      Session NOW EXISTS with activeSessionId set
  │
  ├──2── prepareCompletion()
  │        │
  │        ▼
  │      getCurrentCompletionSettings()
  │        │
  │        ▼
  │      resolveCompletionSettings(sessionId, palId)
  │        │
  │        │  1. System defaults (enable_thinking: true)
  │        │  2. + Global settings
  │        │  3. + Pal settings (enable_thinking: false, temp: 0.9)
  │        │  4. settingsSource === 'pal' → keep merged result
  │        │
  │        ▼
  │      Returns: { enable_thinking: false, temperature: 0.9 }  ← CORRECT!
  │
  ▼
Completion runs with enable_thinking=false  ← CORRECT for model
```

**But the session.completionSettings in DB still has the GLOBAL values (enable_thinking: true, temperature: 0.7) — this matters later!**

## Thinking Toggle Display vs Reality

```
┌─────────────────────────────────────────────────────────────┐
│              THINKING TOGGLE (ChatScreen.tsx)                │
│                                                             │
│  READS FROM:                                                │
│    currentSession?.completionSettings                       │
│      ?? chatSessionStore.newChatCompletionSettings           │
│                                                             │
│  For new chat:  newChatCompletionSettings.enable_thinking   │
│  For session:   session.completionSettings.enable_thinking  │
│                                                             │
│  DOES NOT read from:                                        │
│    - resolveCompletionSettings()                            │
│    - pal.completionSettings                                 │
│    - the merged/resolved value                              │
│                                                             │
│  COMPLETION USES:                                           │
│    resolveCompletionSettings() → merged value               │
│                                                             │
│  ═══════════════════════════════════════════                 │
│  INCONSISTENCY:                                             │
│  Toggle shows global/session value (e.g. true)              │
│  Model receives resolved value (e.g. false from pal)        │
│  ═══════════════════════════════════════════                 │
└─────────────────────────────────────────────────────────────┘
```

## What Happens When User Toggles Thinking

```
User toggles thinking (e.g. OFF → ON) during active session
  │
  ▼
handleThinkingToggle(true)
  │
  ├── Spreads: { ...currentSession.completionSettings }
  │   These are the SESSION's stored settings (global values from creation!)
  │   NOT the resolved/merged values that include pal settings
  │
  │   Result: { ...globalValues, enable_thinking: true }
  │           temperature: 0.7 (global, NOT pal's 0.9!)
  │
  ├── Calls: updateSessionCompletionSettings(updatedSettings)
  │     │
  │     ├── Saves to DB
  │     └── Sets settingsSource = 'custom'  ← AUTO-SWITCH!
  │
  ▼
Next completion: resolveCompletionSettings()
  │
  │  settingsSource === 'custom'
  │  → REPLACES entire result with session.completionSettings
  │  → Returns: { enable_thinking: true, temperature: 0.7 }
  │
  │  Pal's temperature: 0.9 is LOST
  │  Pal layer completely bypassed
  │
  ▼
```

## All UI Components That Touch Settings

```
┌─────────────────────────────────────────────────────────────┐
│                    UI COMPONENTS                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ChatInput (thinking toggle button)                         │
│  ├── Shows: thinkingEnabled (from ChatScreen)               │
│  ├── Calls: onThinkingToggle(enabled)                       │
│  └── Only for enable_thinking, no other settings            │
│                                                             │
│  ChatGenerationSettingsSheet (from HeaderRight menu)        │
│  ├── No session: edits global/preset settings               │
│  ├── With session: edits session settings                   │
│  ├── Pal/Custom segmented toggle (if pal active)            │
│  ├── Uses CompletionSettings component                      │
│  └── Does NOT show enable_thinking (not in metadata)        │
│                                                             │
│  PalGenerationSettingsSheet (from PalSheet form)            │
│  ├── Edits pal.completionSettings                           │
│  ├── Reset options: Global / System / Clear                 │
│  ├── Uses CompletionSettings component                      │
│  └── Does NOT show enable_thinking (not in metadata)        │
│                                                             │
│  CompletionSettings (shared component)                      │
│  ├── Renders fields from COMPLETION_PARAMS_METADATA         │
│  ├── Shows: temperature, top_k, top_p, penalties, etc.      │
│  ├── Shows: include_thinking_in_context (switch)            │
│  └── Does NOT show: enable_thinking                         │
│                                                             │
│  PalsHub (web/remote)                                       │
│  ├── Pal creator sets model_settings                        │
│  ├── Downloaded as rawPalshubGenerationSettings             │
│  ├── Stored in same DB column as completionSettings         │
│  └── Merged with defaults via completionSettingsObject      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Bugs Found (Triple-Verified)

```
┌─────────────────────────────────────────────────────────────┐
│  BUG 1: Toggle shows wrong state                           │
│  ─────────────────────────────────                          │
│  WHERE:   ChatScreen.tsx lines 110-118                      │
│  WHAT:    Toggle reads session/global settings directly     │
│  SHOULD:  Read from resolved settings (including pal)       │
│  EFFECT:  Toggle shows ON when pal sets thinking=false      │
│                                                             │
│  BUG 2: Toggle nukes pal settings                          │
│  ─────────────────────────────────                          │
│  WHERE:   ChatScreen.tsx lines 128-134                      │
│  WHAT:    Spreads session.completionSettings (global vals)  │
│           + sets settingsSource='custom' automatically      │
│  SHOULD:  Either resolve first, or not switch settingsSource│
│  EFFECT:  Pal's temperature lost after toggling thinking    │
│                                                             │
│  BUG 3: Session created with wrong settings                │
│  ──────────────────────────────────────────                  │
│  WHERE:   ChatSessionStore.ts line 347                      │
│  WHAT:    New session gets newChatCompletionSettings only    │
│  SHOULD:  Get resolved settings (including pal)             │
│  EFFECT:  session.completionSettings ≠ what model receives  │
│           (works at completion time via resolve, but         │
│            session snapshot is wrong for later use)          │
│                                                             │
│  BUG 4: settingsSource not persisted                       │
│  ────────────────────────────────────                        │
│  WHERE:   ChatSessionStore.ts updateSessionSettingsSource   │
│  WHAT:    Only updates in-memory MobX, not DB               │
│  ALSO:    No settingsSource column in DB schema at all      │
│  EFFECT:  User choice lost on app restart                   │
│           All sessions default to 'pal' on reload           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Settings Consistency Matrix

```
┌──────────────────────┬──────────────┬──────────────┬────────────┐
│ Scenario             │ Toggle Shows │ Model Gets   │ Consistent │
├──────────────────────┼──────────────┼──────────────┼────────────┤
│ New chat, no pal     │ global       │ global       │ ✅ YES     │
│ New chat, pal        │ global       │ global+pal   │ ❌ NO      │
│ Session, source=pal  │ session(=gl) │ global+pal   │ ❌ NO      │
│ Session, source=cust │ session      │ session      │ ✅ YES     │
│ After toggle         │ session(mod) │ session(mod) │ ✅ YES     │
│ After app restart    │ session(=gl) │ global+pal   │ ❌ NO      │
└──────────────────────┴──────────────┴──────────────┴────────────┘

gl = global defaults stored at session creation
pal = pal.completionSettings overlay
mod = modified by user toggle
```
