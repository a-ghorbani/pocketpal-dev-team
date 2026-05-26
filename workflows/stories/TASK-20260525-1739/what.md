# Thinking toggle in no-session chat — Architecture delta

**Status**: MERGED — PR #745 (merge commit `8a097df`, merged 2026-05-26). Architecture truth has been absorbed into `context/architecture/{pals-and-talents,chat-flow}.md`; this file is retained as a historical design record.

**Story-scoped delta** on `context/architecture/pals-and-talents.md` (§3, §6 single-writer) and `context/architecture/chat-flow.md` (§5 single-writer, §7 state signals).

**Scope**: the user's manual flip of the chat-input thinking toggle must persist in the **no active session** path. The bug is that pal's `enable_thinking` re-overlays user input every render. Two existing layers are sound (defaults, global) and pal layering is sound for session-bound chats; the gap is **no user-override surface for the new-chat path** and an **asymmetric resolver read** for the same path.

---

## Conventions

- **(C)** = current behaviour, documented from code
- **(P)** = proposal, open for challenge
- **(?)** = open question — none should remain on promotion
- **(D)** = decision (was an open question, now resolved)

---

## 1. Data model (delta)

`ChatSessionStore` already carries the three new-chat-path fields. The change adds **one MobX-only field** (no DB column, no migration).

```
ChatSessionStore  (src/store/ChatSessionStore.ts)
  newChatPalId                : string | undefined            // (C) pal selected for the next session
  newChatCompletionSettings   : CompletionParams              // (C) GLOBAL user settings (persisted via repo)
  newChatSettingsSource       : 'pal' | 'custom'              // (C) which layer "wins" at session creation
  newChatThinkingOverride     : boolean | undefined           // (C) user's last manual toggle for the new-chat path
                                                              //     undefined = no override (resolver runs as today)
                                                              //     true / false = user-explicit, applied AFTER pal
                                                              //     cleared (back to undefined) on session creation
                                                              //     and on any explicit reset of new-chat state
                                                              //     (§5 single-writer table)
```

Stored on disk: **nothing new.** `newChatThinkingOverride` is ephemeral in-memory state — same lifetime as `newChatPalId` / `newChatSettingsSource`. (D1)

No change to `Pal.completionSettings.enable_thinking`, no change to migrations, no change to DB schema, no change to defaults. (D2)

---

## 1b. External shape

No wire-format changes. The model still receives `enable_thinking: boolean` inside the resolved `CompletionParams`. Only the resolution function on the JS side changes.

---

## 2. Event flow

No new events. The change is in (a) one resolver read path, (b) one toggle handler write path, and (c) one session-creation handoff that decides whether the new session is born `'pal'` or `'custom'`.

---

## 3. State machine

No state-machine changes. `agentUiState` and `agentStateReducer` are untouched.

The relevant "states" here are the four `(session?, settingsSource)` combinations for the toggle handler:

| Path | `activeSessionId` | `settingsSource` | (was) toggle behaviour | (C) toggle behaviour |
| --- | --- | --- | --- | --- |
| A | set | `'pal'` | writes session.completionSettings, flips source → `'custom'`. **Persists.** | unchanged |
| B | set | `'custom'` | writes session.completionSettings (source stays `'custom'`). **Persists.** | unchanged |
| C | undefined | `'pal'`  (default for new chat) | writes `newChatCompletionSettings` only; resolver overlays pal on top → **snaps back to pal's value.** | writes `newChatThinkingOverride`; resolver applies it last → **persists in the no-session view AND in the resulting session** (see §4c handoff). |
| D | undefined | `'custom'` (user opened ChatGenerationSettingsSheet first) | writes `newChatCompletionSettings`; resolver bypasses pal entirely → **persists today** (but drops pal's other completion settings). | writes `newChatThinkingOverride` (same as C); pal's other settings now NOT dropped just for a thinking flip. |

Paths A, B are correct today. Path C is the reported bug. Path D works for the user but at the cost of stripping pal-specific completion params — a silent side-effect the fix removes.

---

## 4. Contract

### 4a. Resolver (`ChatSessionStore.resolveCompletionSettings` and `getCurrentCompletionSettings`)

The resolver gains **one additional layer at the very end**, applied only on the no-session path.

```
no-session resolution (resolveCompletionSettings(sessionId=undefined, palId)):
  resolvedSettings = defaults
                   ⊕ newChatCompletionSettings                 (global)
                   ⊕ palCompletionSettings        if palId     (pal)        ← (C)
                   ⊕ { tools: PACT-derived }      if palId     (tools)      ← (C)
                   ⊕ { enable_thinking: override }
                       if newChatThinkingOverride !== undefined            ← (C)

session resolution (resolveCompletionSettings(sessionId, palId)):
                   ⊕ defaults
                   ⊕ newChatCompletionSettings                 (C)
                   ⊕ palCompletionSettings        if palId     (C)
                   ⊕ { tools: PACT-derived }      if palId     (C)
                   ⊕ session.completionSettings
                       if session.settingsSource === 'custom'  (C — snapshot wins; pact tools preserved)
                   ── NO override layer here ──                            (D4, I3)
```

The override is a **single-key overlay**, not a settings replacement. Only `enable_thinking` is touched.

Session-bound resolution (`sessionId !== undefined`) is **unchanged**. The override does NOT leak into sessions — but this leaves a question: how does the no-session override survive into the **first inference**, which runs AFTER the session is born? See 4c.

### 4b. Toggle handler (`ChatScreen.handleThinkingToggle`)

Two branches, both observable end-to-end:

1. `currentSession` exists → unchanged. Writes `session.completionSettings` via `updateSessionCompletionSettings`, which flips `settingsSource → 'custom'` (existing behaviour).
2. `currentSession` is undefined → **(C)** writes `newChatThinkingOverride` instead of `newChatCompletionSettings`. Does NOT touch `newChatSettingsSource`. Does NOT touch `newChatCompletionSettings`. Does NOT touch pal `completionSettings`.

### 4c. Session creation handoff (`addMessageToCurrentSession` → `createNewSession`)

This is the load-bearing handoff. `prepareCompletion` (in `useChatSession.ts`) calls `addMessageToCurrentSession` FIRST (which creates the session for the no-session path), THEN calls `getCurrentCompletionSettings` SECOND. Concretely (verified against `src/hooks/useChatSession.ts`):

- line 439: `await addMessage(textMessage)` → `addMessageToCurrentSession` → `createNewSession` → `activeSessionId` is now set.
- line 462: `await prepareCompletion(…)` → line 64: `getCurrentCompletionSettings()` reads the **session** branch of the resolver.

Therefore: by the time the model sees `enable_thinking`, the no-session override layer has already gone out of scope. The override MUST be captured into session state at creation time, or it is dropped before the first inference.

Handoff rules at `createNewSession` (no-session path; `addMessageToCurrentSession` already gates `palIdForSettings` on `newChatSettingsSource === 'pal'`):

1. `resolveCompletionSettings(undefined, palIdForSettings)` is called (existing). With (C) §4a, the no-session resolver includes the override layer, so the resolved snapshot baked into `session.completionSettings` carries the user's thinking choice on top of pal's other params.
2. **(C)** If `newChatThinkingOverride !== undefined` at the moment of `createNewSession`, the new session is born with `session.settingsSource = 'custom'` (not `newChatSettingsSource`). Otherwise `session.settingsSource = newChatSettingsSource` (existing).
3. **(C)** `newChatThinkingOverride` is cleared (set to `undefined`) inside `createNewSession` in the same code block that already clears `newChatPalId`. One-shot semantics: an override applies to the next session it shapes, then resets.

Why `'custom'`-at-birth works (and why nothing else does):

- The session-branch of the resolver returns `session.completionSettings` verbatim ONLY when `settingsSource === 'custom'` (preserving PACT tools, line 1389-1399). If the override-bearing session is born `'pal'`, the resolver re-derives from pal at inference time and **drops the override** — same bug.
- The snapshot baked in step 1 already contains pal's other completion settings (temperature, top_p, …) PLUS the user's thinking choice. Treating that snapshot as "custom" is the literal truth: it is the user's explicit composite for this session, with pal applied first and one user override applied last.
- `activePalId` is still recorded on the session metadata (`metaData.activePalId = this.newChatPalId`, line 514), so pal-derived behaviour outside `completionSettings` (system prompt, PACT tools — re-injected at line 1372-1382) is unaffected. The `'custom'` flag only controls whether the resolver re-derives or trusts the snapshot for completion params.

### 4d. Hard invariants

- **I1 (override is per-key, not per-bag)**: `newChatThinkingOverride` controls **only** `enable_thinking`. The resolver MUST NOT use it to shadow any other key. Adding a second user-overridable key in the future means adding a second override field, not generalising this one (D3).
- **I2 (override does not affect tool availability)**: PACT-derived `tools` are still injected from `pal.pact.talents` (`pals-and-talents.md` §3, I2). The override layer runs AFTER tools injection; it does not touch `tools`. Tool availability stays a function of `pal.pact` only.
- **I3 (override is no-session-only at the resolver)**: the override layer is consulted ONLY when `sessionId === undefined`. Once a session exists, the source-of-truth is `session.completionSettings` (per `settingsSource`) — the override field is not re-applied at the resolver. The override's survival into the first inference is achieved by 4c (snapshot + `'custom'`-at-birth), NOT by re-reading the override later.
- **I4 (override clears on session creation, override "becomes" session state)**: when `createNewSession` resolves, `newChatThinkingOverride` is set back to `undefined` in the same runInAction that clears `newChatPalId`. If the override was non-`undefined` at that moment, the new session is born with `settingsSource = 'custom'` so the baked snapshot (which already includes the override) is the resolver's answer for the first and every subsequent inference until the user toggles again.
- **I5 (override clears on full new-chat reset and on switching to a different existing session)**: `resetActiveSession` (line 308) already resets `newChatPalId` + `newChatSettingsSource`; the override MUST be reset there too. `setActiveSession` (line 344) also clears `newChatPalId` + `newChatSettingsSource`; the override MUST clear there too. Same for the second reset site at line 354-357 (inside `setActiveSession`'s `runInAction`).
- **I6 (pal completionSettings remain pal-owned)**: nothing in this story writes to `pal.completionSettings`. The pal editor (`PalSheet`) still owns that field; the toggle in chat-input does NOT modify pals.
- **I7 (initial toggle state reflects current resolution)**: the existing `useEffect` in `ChatScreen` that calls `getCurrentCompletionSettings()` and seeds `thinkingEnabled` continues to work — once the resolver honours the override (4a), `getCurrentCompletionSettings()` returns the post-override value in the no-session view. Once the session is born (4c), the session-branch returns the baked snapshot with the override already inside it. Either way, no snap-back.

### 4e. What each component does

| Component | Owns | Does NOT |
| --- | --- | --- |
| `ChatScreen.handleThinkingToggle` | route the toggle to `session.completionSettings` (session) or `newChatThinkingOverride` (no session) | write `newChatCompletionSettings`. Touch `newChatSettingsSource`. Mutate pal. |
| `ChatSessionStore.resolveCompletionSettings` | apply defaults → global → pal → (session if custom) → no-session-override; preserve PACT tools across custom replacement (existing) | persist anything. Mutate the override. Re-apply the override on the session branch (I3). |
| `ChatSessionStore.getCurrentCompletionSettings` | dispatch to `resolveCompletionSettings` with the right `(sessionId, palId)` based on whether a session exists | own the override. (Reads it indirectly via `resolveCompletionSettings`.) |
| `ChatSessionStore.createNewSession` (and `addMessageToCurrentSession`) | bake the resolved snapshot into `session.completionSettings`; decide `session.settingsSource` per 4c rule; clear `newChatThinkingOverride` (and `newChatPalId`, existing) — all in one `runInAction` | persist the override. Re-read pal after session is born for completion params. |
| `ChatSessionStore.resetActiveSession` / `ChatSessionStore.setActiveSession` | clear `newChatPalId`, `newChatSettingsSource`, **and** `newChatThinkingOverride` | persist anything. |
| `ChatGenerationSettingsSheet` | unchanged — already writes `newChatCompletionSettings` + `newChatSettingsSource` for the no-session "Custom" branch (path D above) | touch the override. (The sheet is the "deep settings" surface; the chat-input toggle is the "quick override" surface — they don't compete because the resolver applies the override AFTER both.) |

The ChatGenerationSettingsSheet path is intentionally untouched: if a user opens that sheet, picks `'custom'`, and tweaks values, the per-session handover happens at session creation via `newChatCompletionSettings`. The override layer is orthogonal — both can be set, override still wins for `enable_thinking` only, and at session creation the `'custom'`-at-birth rule still applies if the override is set.

---

## 5. Layer ownership (single-writer rule)

Only one field is added; the table below shows where it's written and reset.

| Field | Single writer |
| --- | --- |
| `newChatThinkingOverride` (set) | `ChatScreen.handleThinkingToggle` (no-session branch) |
| `newChatThinkingOverride` (clear / reset) | `ChatSessionStore.createNewSession` (session-creation handoff, same `runInAction` as `newChatPalId` clear) — clears as part of I4 **and** `ChatSessionStore.resetActiveSession` (new-chat reset, same place that clears `newChatPalId` / `newChatSettingsSource`) **and** `ChatSessionStore.setActiveSession` (switching to a different existing session, same `runInAction` at line 352-358 that clears `newChatPalId` / `newChatSettingsSource`) |

Also writes-by-implication at session-creation: `session.settingsSource` is decided by `createNewSession` per the 4c rule (override-present → `'custom'`, else `newChatSettingsSource` as today). This row already exists in `chat-flow.md` §5; the delta is the rule it follows at creation, not a new writer.

Reading: unrestricted (resolver only).

Existing single-writer rows untouched: `newChatCompletionSettings` (still `setNewChatCompletionSettings` only), `newChatPalId` (still `setActivePal` / `resetActiveSession` / `setActiveSession` / `createNewSession`), `newChatSettingsSource` (still `setNewChatSettingsSource` / `resetActiveSession` / `setActiveSession`), `session.completionSettings` (still `updateSessionCompletionSettings`), `session.settingsSource` (still set by toggle paths A/B and by `createNewSession` at birth).

**Recent bugs / past pain**: the bug this story fixes is the canonical example of "user input swallowed by a deterministic re-overlay." Adding a separate, narrowly-scoped override field — instead of widening any of the existing four signals — keeps the multi-writer surface flat.

**Deferred cleanups** (out of scope):
1. The intent's option 1 (don't store `enable_thinking` on pals by default + migration to strip backfilled `true`). Cleaner long-term but adds a DB migration risk for negligible user-visible win once (P) is in place.
2. The intent's option 2 (general per-chat user-override layer). The override field here is the minimum viable shape of that layer. If a second user-overridable key arrives, revisit and possibly generalise (see D3).
3. **Path-D preview-vs-inference asymmetry** between `getCurrentCompletionSettings` (line 1408-1417, passes `newChatPalId` unconditionally) and `addMessageToCurrentSession` (line 427-432, gates palId on `newChatSettingsSource === 'pal'`). For path D (source=`'custom'`), the no-session **preview** read of the resolver includes pal's params on top of `newChatCompletionSettings`, while the **session-creation** read excludes pal entirely. This is **pre-existing behaviour, untouched by this story.** For the `enable_thinking` key specifically there is no observable disagreement: `newChatCompletionSettings.enable_thinking` is the same value the preview and the session-creation paths both end up writing for that key once the override is applied last (both reads end at the same override branch). The asymmetry remains for *other* pal-defined keys in the preview view only; cleaning it up is a separate change.

---

## 6. Canonical scenarios

All scenarios target the no-session path (`activeSessionId === undefined`). Each is manually testable.

**QA priority**: scenarios **A** and **C** are the **blocker-level** repros from issue #744 (no-session toggle + survival across session-birth into first inference). **B, D, E, F** are consistency checks — they must not regress, but they are not the primary user complaint.

### A. Default pal, user flips thinking OFF in fresh chat (the bug) — BLOCKER

```
pre-conditions:
  newChatPalId            = palX            // has completionSettings.enable_thinking = true
  newChatSettingsSource   = 'pal'
  newChatCompletionSettings.enable_thinking = true     // global default
  newChatThinkingOverride = undefined
  no active session

user action: taps thinking toggle (currently ON) → off
─────────────────────────────────────────────────────────
handler writes: newChatThinkingOverride = false        // (C)
resolver returns (no-session branch, sessionId=undefined):
  defaults.enable_thinking     = true
  ⊕ global.enable_thinking     = true
  ⊕ palX.enable_thinking       = true
  ⊕ override.enable_thinking   = false                  ← wins
  → resolved.enable_thinking   = false
useEffect re-reads → setThinkingEnabled(false)         // toggle stays off
```

Tapping the toggle on again writes `newChatThinkingOverride = true`; resolution returns `true`; toggle stays on. The user can flip freely.

### B. Authored pal with `enable_thinking: false` stored, user flips ON

```
pre-conditions:
  palX.completionSettings.enable_thinking = false       // user-authored in PalSheet
  newChatPalId            = palX
  newChatSettingsSource   = 'pal'
  newChatThinkingOverride = undefined
  no active session

initial render: resolver returns enable_thinking = false → toggle is OFF (matches pal). (C, correct.)

user action: taps toggle → on
─────────────────────────────────────────────────────────
handler writes: newChatThinkingOverride = true
resolver returns:
  ⊕ palX.enable_thinking       = false
  ⊕ override.enable_thinking   = true                   ← wins
  → resolved.enable_thinking   = true
toggle stays on.
```

Pal's initial preference is honoured (B's initial state matches pal); the user retains the ability to override.

### C. Override carries into the new session born from this turn, and into the FIRST inference — BLOCKER

This is the load-bearing scenario; it covers the bug the critic caught in round 1.

```
pre-conditions: (same as A, but user is about to send their first message)
  newChatThinkingOverride = false
  newChatSettingsSource   = 'pal'
  newChatPalId            = palX                        // has enable_thinking = true

user action: types and sends "hello"
─────────────────────────────────────────────────────────
useChatSession.handleSendPress (src/hooks/useChatSession.ts):
  line 439: await addMessage(textMessage)
    → addMessageToCurrentSession (no active session):
        palIdForSettings = newChatPalId = palX           // source === 'pal'
        settings = await resolveCompletionSettings(undefined, palX)
                 = { ...palX.completionSettings,
                     enable_thinking: false }            // override applied last (4a)
        await createNewSession(NEW_SESSION_TITLE, [msg], settings)
          baked: session.completionSettings = settings  // enable_thinking=false inside
          baked: session.settingsSource     = 'custom'  // (C) per 4c, because override was set
          baked: session.activePalId        = palX      // pal metadata preserved
          runInAction (line 513-): newChatPalId            = undefined
                                   newChatThinkingOverride = undefined  // (C) I4 clear
        activeSessionId is now set.

  line 462: await prepareCompletion(…)
    → getCurrentCompletionSettings():
        activeSessionId is set → activePalId = session.activePalId = palX
        → resolveCompletionSettings(activeSessionId, palX)
          session branch: session.settingsSource === 'custom'
            → resolvedSettings = session.completionSettings   // baked snapshot wins
              (pactTools preserved if palX has any)
          → resolved.enable_thinking = false              ← user's choice honoured

  model sees: enable_thinking = false on the first turn.

post-session toggle path:
  if user taps thinking again → path A / B (session branch, unchanged)
                                writes session.completionSettings,
                                source already 'custom' so nothing else to flip
```

The user's choice survives into the session and into the first inference; pal's other completion settings (temperature, top_p, etc.) survive because they were merged in before the override; the override field resets so the next new-chat doesn't inherit it.

### D. User opens ChatGenerationSettingsSheet, picks Custom, tweaks temperature, then flips thinking

```
pre-conditions:
  newChatSettingsSource   = 'custom'                    // user picked Custom in sheet
  newChatCompletionSettings.temperature = 0.3           // tweaked
  newChatCompletionSettings.enable_thinking = true      // sheet's value
  newChatPalId            = palX
  newChatThinkingOverride = undefined
  no active session

user action: taps thinking toggle → off
─────────────────────────────────────────────────────────
handler writes: newChatThinkingOverride = false
resolver returns (no-session, getCurrentCompletionSettings preview reads palId=newChatPalId
                  unconditionally — pre-existing asymmetry, §5 deferred cleanup #3):
  ⊕ defaults
  ⊕ newChatCompletionSettings { temperature: 0.3, enable_thinking: true }
  ⊕ palX.completionSettings (preview path only)
  ⊕ override.enable_thinking = false                    ← wins
  → resolved.enable_thinking = false

For the enable_thinking key specifically: preview and session-creation agree, because both end with
the override applied last. The asymmetry doesn't bite this key.
```

When the first message is sent, `addMessageToCurrentSession` passes `palId=undefined` (source is `'custom'`), so the baked snapshot is `{ ...newChatCompletionSettings, enable_thinking: false }` — custom temperature kept, user's thinking choice kept. The new session is born with `settingsSource = 'custom'` per 4c (because the override is set; this happens to coincide with the existing `'custom'` source, so behaviour is identical to today's path-D semantics plus the thinking key).

### E. Second new-chat after override has been applied to a session

```
pre-conditions:
  active session exists (born from scenario C with enable_thinking=false)
  newChatThinkingOverride = undefined                   // cleared in C

user action: opens drawer → "New chat"
─────────────────────────────────────────────────────────
resetActiveSession:
  newChatPalId            = activePalId                 // existing (carries forward)
  newChatSettingsSource   = 'pal'                       // existing (reset)
  newChatThinkingOverride = undefined                   // (C) idempotent (already undefined)

no-session resolver returns palX's saved enable_thinking; toggle reflects pal again.
```

Override does not leak across "new chat" boundaries. (I4 / I5)

### F. Override + tool-capable pal (PACT preserved)

```
pre-conditions:
  palX.pact.talents = [{name:'render_html', necessity:'required'}]
  palX.completionSettings.enable_thinking = true
  newChatPalId = palX, source = 'pal'

user action: taps thinking toggle → off; then sends first message
─────────────────────────────────────────────────────────
resolver (no-session, in toggle preview):
  ⊕ palX (enable_thinking: true, …)
  ⊕ PACT tools injected (pals-and-talents §3)
  ⊕ override → enable_thinking = false

session creation:
  settings = above snapshot (includes tools[render_html] AND enable_thinking=false)
  session.completionSettings = settings
  session.settingsSource     = 'custom'      // (C) per 4c
  session.activePalId        = palX

first-inference resolver (session branch, source='custom'):
  pactTools  = resolveCompletionSettings's pal-pass tools[render_html]
  resolvedSettings = session.completionSettings        // baked snapshot
  resolvedSettings = {...resolvedSettings, tools: pactTools}   // line 1394-1398
  → enable_thinking = false, tools preserved
```

PACT is untouched by the override (I2). Tool availability and the user's thinking choice coexist across the snapshot handoff because the resolver's session branch already re-injects PACT tools when source is `'custom'`.

---

## 7. State signals

`thinkingEnabled` is local React state in `ChatScreen` (`useState(true)`), seeded from `getCurrentCompletionSettings()` in an existing `useEffect`. The effect already re-runs on changes to `newChatCompletionSettings`, `activeSessionId`, `activePalId`, `settingsSource`, and `completionSettings`. (C) `newChatThinkingOverride` is in its dependency array so a toggle-tap propagates without waiting for an unrelated re-render.

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `newChatThinkingOverride` | `ChatScreen.handleThinkingToggle` (no-session) / cleared by `createNewSession` + `resetActiveSession` + `setActiveSession` | `ChatSessionStore.resolveCompletionSettings` (no-session branch only); `ChatSessionStore.createNewSession` (to decide `session.settingsSource` at birth, per 4c) | user has explicitly flipped the toggle in no-session path since the last session creation / reset / switch |
| `thinkingEnabled` (existing local) | `ChatScreen` useEffect (reads resolver) | `MessageInput` (toggle UI) | resolver's `enable_thinking ?? true` |

No new MobX `@computed`. The override is a plain observable field; the resolver reads it directly, and `createNewSession` reads it once to set `session.settingsSource`.

---

## 8. Decisions

- **D1**: The override is **in-memory only** — no DB column, no persistence across app restarts. Rationale: the override is bound to a specific "next session" intent; persisting it would mean a user who flips the toggle, force-quits the app, and starts a new chat sees an unexpected thinking state on a pal they may not even reactivate. Lifetime matches `newChatPalId` (also ephemeral). (?) was: "persist across restarts?" — resolved **no**.
- **D2**: **Do not change pal storage.** Option 1 in the intent (strip `enable_thinking` from pals by default + migration) is rejected for this story. Rationale: every pal already carries the field due to v3 migration; ripping it out is a destructive, hard-to-roll-back DB change for negligible additional user value once the override layer exists. The override is the minimum surface that makes the user's intent stick without touching pal data. (?) was: "should we drop the field from pals?" — resolved **no, not now**.
- **D3**: **Single-key override**, not a generic per-chat override layer. Rationale: today the only user-visible chat-input "quick toggle" is thinking. A generic override bag would invite scope creep (which keys are user-overridable? do we expose all of them?) and a new wire surface to define. Adding a second narrow field if/when a second quick toggle ships is the cheap path; reaching for a generic layer when no second toggle exists is YAGNI. (?) was: "narrow override vs. generic per-chat layer?" — resolved **narrow**.
- **D4**: Apply the override layer **only on the no-session resolver path**, not on the session path. Rationale: once a session exists, `session.completionSettings + settingsSource` is the source-of-truth. The override's survival into the first inference (which happens after session-birth) is handled by `'custom'`-at-birth in 4c — bake the override into `session.completionSettings`, mark the session `'custom'`, and the resolver returns the baked snapshot verbatim. Adding the override as a separate layer on the session-branch would either double the surface or fight the snapshot. (?) was: "how does no-session override survive into first inference, given `prepareCompletion` reads the resolver AFTER session-birth?" — resolved by **`'custom'`-at-birth**.
- **D5**: Override is applied **after PACT tools injection** in the resolver. Rationale: keeps `pact.talents` as the sole tool source (`pals-and-talents.md` I2). The session-branch's existing PACT-tools preservation (line 1394-1398) already re-injects tools when source is `'custom'`, so the `'custom'`-at-birth handoff in 4c does NOT lose tools (I1, I2, F scenario).
- **D6**: When the override is set at the moment of session creation, the new session is born `'custom'` even if `newChatSettingsSource === 'pal'`. Rationale: the baked `session.completionSettings` snapshot is the literal composite "pal first, user override last." Calling that `'pal'` would be a lie — the snapshot is no longer just pal-derived. Calling it `'custom'` is the existing semantic for "user-explicit composite stored on the session" (paths A/B already use `'custom'` after a toggle). Resolver behaviour follows automatically: session branch trusts the snapshot.

---

## 9. Edge cases

### 9a. Toggle tapped, then user picks a different pal before sending

The override is **palId-agnostic** — it stores only `enable_thinking`, not "for which pal." If the user toggles thinking off (with palX active), then switches to palY, then sends a message: the override applies to palY's resolution, and the resulting session is born `'custom'` (per 4c). This is consistent with how `newChatCompletionSettings` (global) already works — global settings don't bind to a pal, and neither does the override.

If we wanted palId-binding, the override would carry `{palId, enable_thinking}` and only apply when the palId still matches. Decided **no** for D3 reasons — narrow surface; user can always re-tap after switching pals.

### 9b. Toggle tapped, then user resets new-chat settings via the sheet

`ChatGenerationSettingsSheet` doesn't touch the override (4e). If the user wants a clean slate they tap "New chat" → `resetActiveSession` clears the override (I5). The sheet's behaviour is independent — it remains the deep-settings surface; the toggle remains the quick-override surface.

### 9c. Pal's `enable_thinking` changes while a new-chat toggle override is held

User taps thinking off (override=false), then opens PalSheet and changes palX's `enable_thinking` to false too. The existing `useEffect` dependency on `activePalId` doesn't catch pal field edits, but the override layer wins anyway, so the resolver still returns `false`. No incorrect UI state. If the user clears the pal's setting later, override still wins until cleared.

### 9d. Multiple thinking-capable pals during a session — no relevance

The override is no-session-only (I3). Once a session is active, thinking edits go through the session-branch path (A/B), which has always worked.

### 9e. App restart with an unsent new-chat override

The override is in-memory (D1). On restart, the override is gone; resolver returns pal's value; toggle UI reflects pal. The user re-taps if they still want the override. This is intentional — see D1 rationale.

### 9f. Override + `n_predict` and other future intent fields

Out of scope. If a future story adds, e.g., a temperature quick-control to the chat-input, it gets a `newChatTemperatureOverride` (per D3), not a generalised bag. The current change does not preclude that future field.

### 9g. Path-D preview-vs-inference asymmetry

Pre-existing (see §5 deferred cleanup #3). For the `enable_thinking` key specifically — the only key this story touches — there's no observable disagreement: both the preview path (`getCurrentCompletionSettings` with `newChatPalId` unconditionally) and the inference path (`addMessageToCurrentSession` with palId gated on source) end at the same override-applied-last branch, so `enable_thinking` resolves to the same value in both. The asymmetry remains for *other* pal-defined keys in the path-D preview view only; cleaning it up is a separate change and is not blocked by this delta.

### 9h. Cancel / empty / race

- **Cancel**: user opens chat, taps toggle, opens drawer to switch sessions before sending. `setActiveSession` clears the override (I5). The half-applied override does not leak into the existing session.
- **Empty / no pal**: with `newChatPalId === undefined`, the resolver skips the pal layer; the override layer still runs (single-key overlay). Override controls thinking; defaults+global cover the rest. Session is born `'custom'` if override is set, else `'pal'` (the existing default).
- **Race**: the toggle handler and `createNewSession` both mutate state in MobX `runInAction` blocks; MobX serialises updates per microtask. The toggle handler writes only the override field; `createNewSession` reads-then-clears in a single action. A toggle tap that lands between `addMessageToCurrentSession`'s pal-resolution and `createNewSession`'s clear would be observed by the clear and lost — but `addMessageToCurrentSession` is sync from the React event handler's perspective and awaits in series, so there is no window for a second user tap mid-creation.

---

## 10. What this doc is NOT

- not a fix to pal storage shape (D2)
- not a rewrite of `ChatGenerationSettingsSheet` (4e)
- not a generalisation of the per-chat override layer (D3)
- not a change to `agentUiState`, `agentStateReducer`, the agent runner, or any rendering contract
- not a wire-format change
- not a DB migration (D1)
- not a fix to the path-D preview-vs-inference asymmetry (9g, §5 deferred cleanup #3)

**Cleanup reminders** — none. The override field is intended to live indefinitely as the single mechanism for the thinking quick-toggle; no diagnostic code or feature flag involved.

---

## 11. Review History

### Round 1 — critic verdict: HAS_BLOCKERS

**BLOCKER 1**: *Override is dropped before the first model inference.* `prepareCompletion` (useChatSession.ts:64) calls `getCurrentCompletionSettings` AFTER `addMessageToCurrentSession` has already created the session. At that moment session exists, `settingsSource='pal'`, override was cleared by the runInAction inside `createNewSession`. Resolver's session branch only returns `session.completionSettings` when `settingsSource === 'custom'`, so the baked snapshot (which had the override applied) is ignored and pal's `enable_thinking` is returned. Model gets pal's value, not user's override; toggle snaps back on next render.

**Resolution: FIXED.** Adopted critic's recommended option (a): at session creation, if `newChatThinkingOverride !== undefined`, set `session.settingsSource = 'custom'` regardless of `newChatSettingsSource`. The baked `session.completionSettings` IS the pal-resolved snapshot with the override applied last (resolver §4a unchanged from round 1); the session-branch's `'custom'` path returns that snapshot verbatim (with PACT tools re-injected at line 1394-1398), so pal-derived params AND the user's choice both survive into the first inference.

Changes:
- §3 path C "(P) toggle behaviour" updated to spell out "persists in the no-session view AND in the resulting session."
- §4a clarified: session-branch resolution explicitly notes "NO override layer here," with cross-ref to 4c for the survival mechanism.
- §4c rewritten as a load-bearing handoff section, with line numbers from `useChatSession.ts` to anchor the call order, the new `'custom'`-at-birth rule, and a "why nothing else works" paragraph.
- §4d I3 rewritten: "override is no-session-only **at the resolver**" with explicit "survival via 4c, not via re-reading."
- §4d I4 rewritten: "override 'becomes' session state — born `'custom'` if override was set."
- §4d I5 expanded to include `setActiveSession` as a clear site.
- §4e `createNewSession` row updated to reflect the new birth-source rule.
- §6 Scenario C rewritten to trace the call order with line numbers (439, 462, 64) and show the override surviving into first inference via `'custom'`-at-birth + session-branch snapshot.
- §6 Scenario F session-creation step updated to use `'custom'`-at-birth.
- D4 reframed: rationale now anchors on "survival handled by 4c," not on "override doesn't need to travel."
- D6 added: "session born `'custom'` even when source was `'pal'`" rationale.

**CONCERN 2**: *§5 single-writer table omits `setActiveSession` as a clear site, but I5 explicitly says it should clear there too.*

**Resolution: FIXED.** Added `setActiveSession` to the `newChatThinkingOverride` (clear / reset) row in §5. Verified against `src/store/ChatSessionStore.ts:344-358` — the existing `runInAction` at line 352-358 clears `newChatPalId` and `newChatSettingsSource` for consistency on session-switch; the override joins that clear set. I5 wording also updated to call out `setActiveSession` explicitly.

**CONCERN 3**: *Path-D preview-vs-inference asymmetry — note it explicitly is preexisting and untouched.*

**Resolution: FIXED.** §5 deferred cleanup #3 rewritten to spell out that the asymmetry is preexisting (preview path passes `newChatPalId` unconditionally; session-creation path gates on source), untouched by this story, and that for the `enable_thinking` key specifically there is no observable disagreement because both reads end at the same override-applied-last branch. New §9g added as a dedicated edge-case note. §6 scenario D body explicitly walks through both reads for the `enable_thinking` key to show they agree.

**SUGGESTION 4**: *Mark scenarios A and C as blocker-level for QA.*

**Resolution: FIXED.** §6 preamble now states "QA priority: scenarios A and C are blocker-level repros; B/D/E/F are consistency checks." Scenario headings annotated with "— BLOCKER" where applicable.

---

## Cross-references

- `context/architecture/pals-and-talents.md` §3 (resolver layer order), §6 (single-writer table) — to be amended in the same PR to add `newChatThinkingOverride` as a recognised resolver input.
- `context/architecture/chat-flow.md` §5 (single-writer table) — to be amended in the same PR to add the override row and the `'custom'`-at-birth rule for `session.settingsSource` in `createNewSession`.

When this delta lands, the (P) markers in §1, §3, §4, §5, §7 become (C); the (D) markers above stay as-is.
