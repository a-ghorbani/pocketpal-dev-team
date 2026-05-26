# Completion Settings Architecture

> **Doc status (2026-05-25):** original snapshot identified four bugs; all four are now closed. Bugs 1/2/3 were fixed when the toggle moved to an async resolver-backed read and `addMessageToCurrentSession` started resolving pal before `createNewSession`. Bug 4 was fixed by DB migration v6 (`settings_source` column). The latest delta is the **`newChatThinkingOverride`** layer added for issue #744 — see new "No-session override layer" section below.

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
│  5. settingsSource (DB: chat_sessions.settings_source)      │
│     SessionMetaData.settingsSource: 'pal' | 'custom'       │
│     Controls whether pal layer is used or bypassed          │
│     Persisted across restarts (migration v6 added column;   │
│     legacy rows without a value fall back to 'pal')         │
│                                                             │
│  6. newChatThinkingOverride (IN-MEMORY ONLY, ephemeral)     │
│     ChatSessionStore.newChatThinkingOverride: bool | undef  │
│     Per-chat user override for the thinking toggle in chat  │
│     input, ONLY consulted when no session exists yet.       │
│     Carrier between toggle-tap and session-birth; cleared   │
│     on createNewSession / resetActiveSession /              │
│     setActiveSession. Forces session.settingsSource to      │
│     'custom' at birth so the baked snapshot survives into   │
│     the first inference.                                    │
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
           │ if palId provided AND pal.pact.talents present:
           │   {...merged, tools: deriveToolSchemas(talents)}
           ▼
  ┌──────────────────┐
  │ PACT tools        │  resolvedSettings.tools
  │ (when applicable) │  (single-writer for tools key)
  └────────┬─────────┘
           │ if !sessionId AND newChatThinkingOverride !== undefined:
           │   {...merged, enable_thinking: newChatThinkingOverride}
           ▼
  ┌──────────────────────┐
  │ No-session override   │  newChatThinkingOverride
  │ (no-session path only)│  per-chat user override
  └────────┬─────────────┘
           │
           ▼
  ┌──────────────────────────────────────────┐
  │ settingsSource === 'custom' ?            │
  │                                          │
  │   YES → REPLACE all with                 │
  │          session.completionSettings,      │
  │          THEN re-inject PACT tools        │
  │          (preserves talent-derived tools) │
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
  │      const palIdForSettings =
  │        newChatSettingsSource === 'pal' ? newChatPalId : undefined;
  │      const settings = await resolveCompletionSettings(
  │        undefined, palIdForSettings);
  │      // (settings includes pal overlay + override if set)
  │      const birthSource =
  │        newChatThinkingOverride !== undefined
  │          ? 'custom'              // force custom so snapshot wins
  │          : newChatSettingsSource;
  │      createNewSession(title, [message], settings, palId, birthSource)
  │        │
  │        │  Session stored in DB with:
  │        │    completionSettings = resolved snapshot (pal + override)
  │        │    activePalId = newChatPalId
  │        │    settings_source = birthSource (PERSISTED in DB v6+)
  │        │  Override + newChatPalId cleared in same code block.
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
  │        │  4. + PACT tools (if pal has talents)
  │        │  5. No-session override skipped (sessionId is set now)
  │        │  6. settingsSource branch:
  │        │     - 'pal' → keep merged result
  │        │     - 'custom' (e.g. user tapped thinking before send)
  │        │       → REPLACE with session.completionSettings
  │        │         which IS the resolved snapshot baked at birth
  │        │       → re-inject PACT tools
  │        │
  │        ▼
  │      Returns: { enable_thinking: false, temperature: 0.9 }  ← CORRECT!
  │
  ▼
Completion runs with enable_thinking=false  ← CORRECT for model
```

The `session.completionSettings` in DB now matches what the model received (the resolved snapshot was baked at session creation, not the raw global settings). Previously this snapshot was the global-only values, which caused divergence — closed by the `addMessageToCurrentSession` resolve-before-create change.

## Thinking Toggle Display vs Reality (current — Bug 1 closed)

```
┌─────────────────────────────────────────────────────────────┐
│              THINKING TOGGLE (ChatScreen.tsx)                │
│                                                             │
│  READS FROM (useEffect re-runs on deps):                    │
│    await chatSessionStore.getCurrentCompletionSettings()    │
│    → resolveCompletionSettings(activeSessionId, palId)      │
│    → includes pal overlay AND newChatThinkingOverride       │
│                                                             │
│  Deps: activeSessionId, settingsSource, completionSettings, │
│        newChatCompletionSettings, activePalId,              │
│        newChatThinkingOverride                              │
│                                                             │
│  COMPLETION USES:                                           │
│    same resolveCompletionSettings()                         │
│                                                             │
│  Toggle and model see the SAME value (consistent).          │
│                                                             │
│  The override exists so the user can flip the displayed     │
│  value without (a) tainting their global preset or          │
│  (b) being silently overwritten by the pal layer on the     │
│  next re-resolve.                                           │
└─────────────────────────────────────────────────────────────┘
```

## What Happens When User Toggles Thinking (current — Bug 2 closed)

```
Branch A: active session (was the only fix path the doc originally covered)
  │
  ▼
handleThinkingToggle(true)
  │
  ├── const resolved = await getCurrentCompletionSettings()   ← RESOLVED!
  │   { ...defaults, ...global, ...pal, tools }
  │   (includes pal's temperature: 0.9 — not lost any more)
  │
  ├── const updated = { ...resolved, enable_thinking: true }
  │
  ├── updateSessionCompletionSettings(updated)
  │     ├── Saves snapshot to DB
  │     └── Sets settings_source = 'custom' (DB-persisted, v6+)
  │
  ▼
Next completion: session-branch returns session.completionSettings
verbatim (with PACT tools re-injected). Pal's temp 0.9 preserved.

Branch B: no active session (the path that produced issue #744)
  │
  ▼
handleThinkingToggle(false)
  │
  ├── runInAction(() => {
  │     chatSessionStore.newChatThinkingOverride = false;
  │   })
  │   (NOT written into newChatCompletionSettings — keeps preset clean)
  │
  ▼
Toggle UI re-resolves and sees the override layer → reflects false.
On next createNewSession (from sending the first message):
  ├── settings = resolveCompletionSettings(undefined, palId)
  │   includes override → { ...pal, enable_thinking: false }
  ├── birthSource = 'custom'  (because override !== undefined)
  ├── DB row stores snapshot + settings_source='custom'
  └── Override + newChatPalId cleared in same code block.
First inference: session-branch with source='custom' → snapshot wins
→ enable_thinking=false reaches the model. Override does not leak
into the user's global preset.
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

## Bugs Found (all CLOSED — kept as history)

```
┌─────────────────────────────────────────────────────────────┐
│  BUG 1: Toggle shows wrong state                  [CLOSED] │
│  ─────────────────────────────────                          │
│  ORIGINAL: Toggle read session/global directly, missing pal.│
│  FIX:    ChatScreen.tsx useEffect now calls                 │
│          getCurrentCompletionSettings() (the resolver) so   │
│          the toggle reflects the pal overlay.               │
│          This change introduced the no-session re-overlay   │
│          symptom — fixed by Bug 5 below.                    │
│                                                             │
│  BUG 2: Toggle nukes pal settings                 [CLOSED] │
│  ─────────────────────────────────                          │
│  ORIGINAL: Session-bound toggle spread stored snapshot      │
│          (global vals) and switched source='custom', losing │
│          pal's temperature.                                 │
│  FIX:    handleThinkingToggle session branch now calls      │
│          getCurrentCompletionSettings() first, then spreads │
│          the resolved snapshot with the toggled value, then │
│          updateSessionCompletionSettings (which also sets   │
│          source='custom'). Pal-derived params survive.      │
│                                                             │
│  BUG 3: Session created with wrong settings       [CLOSED] │
│  ──────────────────────────────────────────                  │
│  ORIGINAL: createNewSession received raw                    │
│          newChatCompletionSettings (no pal overlay).        │
│  FIX:    addMessageToCurrentSession now resolves first      │
│          (with palIdForSettings gated on                    │
│          newChatSettingsSource) and passes the resolved     │
│          snapshot to createNewSession. DB snapshot matches  │
│          what the model received.                           │
│                                                             │
│  BUG 4: settingsSource not persisted              [CLOSED] │
│  ────────────────────────────────────                        │
│  ORIGINAL: settingsSource was MobX-only; no DB column.      │
│  FIX:    Migration v6 added chat_sessions.settings_source.  │
│          ChatSessionRepository.createSession and            │
│          setSessionSettingsSource both write it.            │
│          loadSessionList hydrates it back on app start      │
│          (legacy rows fall back to 'pal' for compat).       │
│                                                             │
│  BUG 5: Pal re-overlays user's toggle (issue #744) [CLOSED]│
│  ────────────────────────────────────────────────            │
│  ORIGINAL: After Bug 1 was fixed, the no-session toggle     │
│          handler wrote to newChatCompletionSettings; pal    │
│          still wins on every re-resolve, so the user's flip │
│          snapped back. Writing to global also tainted the   │
│          user's preset across all future no-pal chats.      │
│  FIX:    Added newChatThinkingOverride (in-memory, ephemeral│
│          one-shot, single-key). Resolver applies it as a    │
│          no-session-only last layer. createNewSession bakes │
│          the overlaid snapshot AND forces                   │
│          settings_source='custom' so the snapshot survives  │
│          into the first inference. Cleared at all three     │
│          new-chat reset sites.                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## No-Session Override Layer (current state)

```
┌─────────────────────────────────────────────────────────────┐
│  WHY a dedicated field instead of writing to global?         │
│                                                             │
│  newChatCompletionSettings IS the user's preset baseline    │
│  for any future no-pal chat. The thinking toggle in chat    │
│  input is per-chat ephemeral intent. Conflating the two:    │
│                                                             │
│   1. Pal still wins on re-resolve (pal applied AFTER global).│
│      So writing to global only "works" with no pal active.   │
│   2. Taints the preset — silently leaks the toggle's value   │
│      into the NEXT no-pal new chat. Wrong scope.            │
│                                                             │
│  The session-bound toggle path dodges both: writes to       │
│  session.completionSettings (per-session) and flips         │
│  session.settings_source='custom' (per-session). The        │
│  no-session path has no equivalent per-chat storage         │
│  *before* the session exists — that's the gap               │
│  newChatThinkingOverride fills.                             │
│                                                             │
│  INVARIANTS                                                  │
│  ─ Single key (enable_thinking) — does NOT touch tools or    │
│    any other field.                                         │
│  ─ Applied AFTER pal overlay and AFTER PACT tools injection. │
│  ─ Resolver consults it ONLY when sessionId === undefined.   │
│  ─ Survives across session boundary via 'custom'-at-birth,   │
│    not via cross-session resolver lookup.                   │
│  ─ Cleared at createNewSession / resetActiveSession /        │
│    setActiveSession. No leak across new-chat or session      │
│    switch.                                                  │
│                                                             │
│  GENERALIZATION                                             │
│  If a second per-chat ephemeral toggle ever lands in chat    │
│  input, promote this field to                               │
│  newChatOverrides: Partial<CompletionParams> and apply it   │
│  generically in the same slot. Current shape is sized to     │
│  today's only consumer.                                     │
└─────────────────────────────────────────────────────────────┘
```

## Settings Consistency Matrix (current — all consistent)

```
┌────────────────────────────┬───────────────┬───────────────┬────────────┐
│ Scenario                   │ Toggle Shows  │ Model Gets    │ Consistent │
├────────────────────────────┼───────────────┼───────────────┼────────────┤
│ New chat, no pal           │ global        │ global        │ ✅ YES     │
│ New chat, pal              │ global+pal    │ global+pal    │ ✅ YES     │
│ New chat, pal, user toggled│ resolved+ovr  │ resolved+ovr  │ ✅ YES     │
│ Session, source=pal        │ global+pal    │ global+pal    │ ✅ YES     │
│ Session, source=custom     │ session snap  │ session snap  │ ✅ YES     │
│ After session toggle       │ session+mod   │ session+mod   │ ✅ YES     │
│ After app restart          │ same as above │ same as above │ ✅ YES     │
└────────────────────────────┴───────────────┴───────────────┴────────────┘

gl  = global preset (newChatCompletionSettings)
pal = pal.completionSettings overlay
ovr = newChatThinkingOverride (no-session, ephemeral, single-key)
mod = modified by user toggle
session snap = session.completionSettings (baked at birth, source='custom')

Notes on the restart row:
  - settings_source is persisted in DB (migration v6), so source='custom'
    sessions remain custom after restart.
  - newChatThinkingOverride is in-memory only — but it's already cleared
    by the time createNewSession returns, so there's nothing to persist;
    the user's choice has been baked into the resulting session snapshot.
```
