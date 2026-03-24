# UX Amendment: Model-Centric Remote Model Management

**Amends**: TASK-20260219-1727
**Date**: 2026-02-24
**Origin**: UX design review with Norman/Wroblewski/Rams analysis
**Status**: Approved by human

---

## Summary of Changes

The original story placed server management in Settings with all models auto-populating.
This amendment redesigns the UX around a **model-centric** approach: users add individual
remote models from the Models screen, servers are hidden plumbing, and server maintenance
is accessible when needed but not prominent.

**What changes**: Steps 5, 6, and parts of Step 3 (ServerStore), plus affected files list
and acceptance criteria.

**What does NOT change**: Steps 1, 2, 4a, 4b, 4c (engine layer, types, SSE, completion
integration) are unaffected. The entire backend/engine architecture remains as planned.

---

## Design Principles

1. **The user manages models, not servers.** Adding a remote model feels identical to
   downloading a local model — it's just another way to get a model into your list.
2. **Servers exist but are secondary.** ServerStore is internal plumbing. Server config
   surfaces only for maintenance (URL/key changes), not as a primary management concept.
3. **One model = one entry.** Each remote model the user adds becomes one card in the
   model list. A server with 15 models does NOT create 15 entries — only the ones the
   user explicitly picks.
4. **Immutable model identity.** You don't "change" a remote model entry to point to a
   different model. You delete it and add a new one. This preserves conversation history
   integrity.
5. **Server changes propagate.** When a server's URL or API key changes, ALL models from
   that server update. The UI makes this relationship visible.

---

## User Flows

### Flow 1: Add First Remote Model

```
Models Screen
  → FAB tap
    → "Add Remote Model" (new third option)
      → RemoteModelSheet opens

┌───────────────────────────────────┐
│  Add Remote Model                 │
│                                   │
│  ┌─────────────────────────────┐  │
│  │ ⓘ Messages sent to remote  │  │  ← privacy notice, first time only
│  │   servers leave your device.│  │    inline banner, not a modal alert
│  │   Only connect to servers   │  │    dismissed globally once
│  │   you trust.                │  │
│  └─────────────────────────────┘  │
│                                   │
│  Server URL                       │
│  ┌─────────────────────────────┐  │
│  │ http://                     │  │  ← keyboardType="url"
│  └─────────────────────────────┘  │
│                                   │
│  (remaining fields appear after   │
│   successful connection probe)    │
│                                   │
└───────────────────────────────────┘
```

After user enters a valid URL, auto-probe fires (debounced ~800ms):

```
┌───────────────────────────────────┐
│  Add Remote Model                 │
│                                   │
│  Server URL                       │
│  ┌─────────────────────────────┐  │
│  │ http://192.168.1.100:1234   │  │
│  └─────────────────────────────┘  │
│  ✓ Connected                      │
│                                   │
│  Server Name                      │
│  ┌─────────────────────────────┐  │
│  │ My LM Studio               │  │  ← auto-filled from hostname,
│  └─────────────────────────────┘  │    user can edit
│                                   │
│  API Key (optional)               │
│  ┌─────────────────────────────┐  │
│  │                          👁 │  │  ← secure entry with toggle
│  └─────────────────────────────┘  │
│  Stored securely on device.       │
│                                   │
│  ⚠ iOS requires HTTPS for        │  ← only for non-local http://
│    non-local servers.             │
│                                   │
│  Select Model                     │  ← appears after connection
│  ● llama-3.1-8b                  │    succeeds and models fetched
│  ○ mistral-7b-v0.3               │
│  ○ codestral-22b                 │
│                                   │
│           [Add Model]             │
└───────────────────────────────────┘
```

**Key behaviors:**
- URL auto-probes on valid input (debounced). No separate "Test Connection" button.
- If probe fails: show inline error below URL field ("Connection failed: timeout" etc.)
- Server name auto-fills from hostname (e.g., `192.168.1.100` or domain). Editable.
- If **one model** on server: auto-selected, model list section does NOT appear.
- If **multiple models**: user picks exactly one. No "server default" option.
- If **zero models** (server connected but empty): show "No models available on this
  server." with disabled Add button.
- API key field always visible but marked optional.
- "Add Model" saves server config internally + creates the model entry.

### Flow 2: Add Another Model from Same Server

```
Models Screen
  → FAB tap
    → "Add Remote Model"
      → RemoteModelSheet opens (now with known servers)

┌───────────────────────────────────┐
│  Add Remote Model                 │
│                                   │
│  Your Servers                     │
│  ┌───────────┐  ┌─────────────┐  │
│  │ LM Studio │  │ OpenAI      │  │  ← tappable chips
│  └───────────┘  └─────────────┘  │
│                                   │
│  ─── or connect new server ───   │
│                                   │
│  Server URL                       │
│  ┌─────────────────────────────┐  │
│  │ http://                     │  │
│  └─────────────────────────────┘  │
│                                   │
└───────────────────────────────────┘
```

Tapping a known server chip skips URL/name/key entry entirely and goes straight
to model selection:

```
┌───────────────────────────────────┐
│  Add Remote Model                 │
│                                   │
│  From: LM Studio                  │
│  (192.168.1.100:1234)             │
│                                   │
│  Select Model                     │
│  ○ mistral-7b-v0.3               │  ← models already added are
│  ○ codestral-22b                 │    excluded or shown as
│  ✓ llama-3.1-8b  (already added) │    disabled with checkmark
│                                   │
│           [Add Model]             │
└───────────────────────────────────┘
```

**Key behaviors:**
- Known servers derived from ServerStore.servers internally.
- Chips shown only when known servers exist.
- Models already added from this server shown as disabled/checked (not selectable again).
- If ALL models from a server are already added, the chip could show "(all added)" or
  the model list shows all checked with disabled Add button.

### Flow 3: Delete a Remote Model

Same as deleting a local model — delete action on the model card.

Confirmation: "Remove llama-3.1-8b (My LM Studio)?"

If this was the **last model** from that server:
- ServerStore removes the server config internally
- API key removed from Keychain
- Server disappears from "Your Servers" chips on next add

### Flow 4: Server Maintenance (URL/Key Change)

Accessible from two places:

**A) From the model card:**
Remote model card shows "Server: My LM Studio" as a tappable link below the model name.
Tapping opens the Server Details sheet.

**B) From Settings:**
Settings screen has a lightweight "Connected Servers" section (read-only list, not for
adding/removing). Each server row is tappable.

```
Settings
├─ ...existing sections...
├─ Connected Servers
│  ├─ My LM Studio (3 models)   ▸
│  └─ OpenAI (1 model)          ▸
├─ ...rest of settings...
```

Both paths open the same **Server Details sheet**:

```
┌───────────────────────────────────┐
│  My LM Studio                     │
│                                   │
│  Server URL                       │
│  ┌─────────────────────────────┐  │
│  │ http://192.168.1.100:1234   │  │
│  └─────────────────────────────┘  │
│                                   │
│  API Key                          │
│  ┌─────────────────────────────┐  │
│  │ ••••••••              👁    │  │
│  └─────────────────────────────┘  │
│                                   │
│  Models using this server:        │
│  · llama-3.1-8b                   │
│  · mistral-7b                     │  ← read-only list, makes shared
│  · codestral-22b                  │    nature of the change explicit
│                                   │
│        [Save Changes]             │
│                                   │
│  Remove Server                    │  ← destructive, removes server
│  Removes all 3 models above.     │    AND all its models
└───────────────────────────────────┘
```

**Key behaviors:**
- URL change triggers auto-probe (same as add flow). Shows ✓/✗ inline.
- "Models using this server" makes it clear the change affects all listed models.
- "Remove Server" is a destructive action with confirmation alert:
  "Remove My LM Studio and its 3 models?"
- API key update: save immediately to Keychain on Save.

### Flow 5: Auth Failure Recovery

When a remote completion fails with 401:
- Show inline error in chat: "Authentication failed for My LM Studio."
- Offer a tappable "Update API Key" link that opens the Server Details sheet
  directly to the API key field.

This avoids the user needing to navigate to Settings or find the model card.

---

## Component Changes (vs. Original Story)

### Removed

| Original Component | Reason |
|-------------------|--------|
| `ServerConfigSheet` in Settings | Replaced by `RemoteModelSheet` on Models screen |
| Settings "Remote Servers" section (add/edit/delete/toggle) | Replaced by lightweight "Connected Servers" read-only list |
| Server active/inactive toggle | Not needed — if you don't want a model, delete it |
| Separate "Test Connection" button | Auto-probe replaces it |
| Auto-populate ALL models from server | User explicitly picks models |

### Added/Changed

| New Component | Purpose |
|--------------|---------|
| `RemoteModelSheet` | Bottom sheet for adding a remote model (URL → connect → pick model) |
| `ServerDetailsSheet` | Bottom sheet for editing server URL/key (shared across models) |
| Models screen FAB extension | Third option: "Add Remote Model" |
| Settings "Connected Servers" | Lightweight read-only list linking to ServerDetailsSheet |
| Model card "Server: name" link | Tappable link opening ServerDetailsSheet |

### Renamed

| Original | New | Reason |
|----------|-----|--------|
| `ServerConfigSheet/` | `RemoteModelSheet/` | Model-centric framing |
| — | `ServerDetailsSheet/` | New component for server maintenance |

---

## Changes to Story Steps

### Step 3: ServerStore — Modifications

ServerStore still exists as internal plumbing but with these adjustments:

- **Add `userSelectedModels`** field: `Array<{serverId: string, remoteModelId: string}>`
  persisted via `makePersistable`. This tracks which models the user explicitly added
  (vs. all models available on the server).
- **Remove** `isActive` from `ServerConfig`. Servers don't have an active/inactive toggle.
  A server exists as long as at least one of its models is in the user's list.
- **Keep** `privacyNoticeAcknowledged`.
- **Keep** all API methods: `fetchModelsForServer`, `testConnection`, Keychain ops.
- **Add** `removeServerIfOrphaned(serverId)`: called when a model is deleted. If no more
  `userSelectedModels` reference this server, remove the server config and its API key.
- **Add** `getModelsNotYetAdded(serverId)`: returns models from `serverModels` that are
  NOT in `userSelectedModels` (for the "already added" UI in Flow 2).

### Step 5: Replaces "Server Configuration UI" entirely

**Was**: ServerConfigSheet in Settings with server CRUD.
**Now**: Two components:

#### Step 5a: RemoteModelSheet (Add Remote Model)

**Files**: `src/components/RemoteModelSheet/RemoteModelSheet.tsx`, `styles.ts`, `index.ts`

- Triggered from Models screen FAB
- Single sheet with progressive disclosure:
  1. Known server chips (if any) + URL input
  2. After connection: server name (auto-filled), API key, model selection
  3. "Add Model" button
- Privacy notice inline (first time only)
- ATS warning inline (non-local http://)
- Auto-probe URL (debounced, using `testConnection` from openai.ts)
- On save: creates/reuses ServerConfig, adds to `userSelectedModels`, model appears in list
- Follow `HFTokenSheet` pattern for sheet + secure input

#### Step 5b: ServerDetailsSheet (Server Maintenance)

**Files**: `src/components/ServerDetailsSheet/ServerDetailsSheet.tsx`, `styles.ts`, `index.ts`

- Opened from model card "Server: name" link OR Settings "Connected Servers" row
- Shows: URL (editable), API key (editable), "Models using this server" (read-only list)
- Auto-probe on URL change
- "Save Changes" button
- "Remove Server" destructive action at bottom
- Follow same sheet patterns

#### Step 5c: Models Screen FAB Extension

**Files**: `src/screens/ModelsScreen/ModelsScreen.tsx`

- Add "Add Remote Model" as third FAB option
- Follow existing FAB speed-dial pattern (review current implementation for exact pattern)
- Opens `RemoteModelSheet`

#### Step 5d: Settings "Connected Servers" Section

**Files**: `src/screens/SettingsScreen/SettingsScreen.tsx`

- Lightweight read-only section (NOT the original full CRUD)
- Shows only when servers exist (no empty state needed — the add flow is on Models screen)
- Each row: server name + model count + chevron
- Tapping opens `ServerDetailsSheet`
- Placement: after "API Settings" card, before "Export Options"

### Step 6: Remote Models in Unified List — Modifications

Key change: `ModelStore.remoteModels` computed filters to **only user-selected models**:

```typescript
get remoteModels(): Model[] {
  const models: Model[] = [];
  for (const selected of serverStore.userSelectedModels) {
    const serverModelList = serverStore.serverModels.get(selected.serverId);
    const server = serverStore.servers.find(s => s.id === selected.serverId);
    if (!server) continue;
    const rm = serverModelList?.find(m => m.id === selected.remoteModelId);
    if (!rm) continue; // Model no longer on server — show offline state?
    models.push(createRemoteModel({
      serverId: selected.serverId,
      serverName: server.name,
      remoteModelId: rm.id,
      modelName: rm.id,
    }));
  }
  return models;
}
```

Model card changes for remote models:
- Show `cloud-outline` icon + server name where local models show file size
- Actions: **Load/Offload** and **Delete** only (no expand, no settings, no download)
- **New**: tappable "Server: My LM Studio" link that opens ServerDetailsSheet
- Delete action: removes from `userSelectedModels`, calls `removeServerIfOrphaned`

Everything else in Step 6 (HeaderRight indicators, ChatPalModelPickerSheet routing,
selectModel wrapper, cloud icon in chat header) remains as originally planned.

---

## Updated Acceptance Criteria

Replace the original acceptance criteria with:

- [ ] Models screen FAB has "Add Remote Model" option alongside existing options
- [ ] Can add a remote model via URL entry with auto-probe connection
- [ ] Server name auto-fills from hostname after successful connection
- [ ] If server has multiple models, user picks one from inline list
- [ ] If server has one model, it's auto-selected (no picker shown)
- [ ] Privacy notice shows inline on first remote model add, dismissed globally
- [ ] ATS warning shows for non-local http:// URLs
- [ ] Remote model appears in model list with cloud icon and server name
- [ ] Adding another model from same server shows "Your Servers" chip shortcut
- [ ] Already-added models shown as disabled in model picker
- [ ] Can delete remote models (same as local model delete pattern)
- [ ] Deleting last model from a server cleans up server config and API key
- [ ] Can edit server URL/API key from model card "Server: name" link
- [ ] Can edit server URL/API key from Settings "Connected Servers" section
- [ ] Server changes affect all models from that server (shown in UI)
- [ ] "Remove Server" deletes server and all its models
- [ ] 401 auth failure shows inline recovery prompt in chat
- [ ] Selecting a remote model creates an OpenAI completion engine and enables chat
- [ ] Streaming works: tokens appear incrementally in the chat UI
- [ ] Stop button aborts remote completion
- [ ] Switching between local and remote models works without issues
- [ ] Local-only usage (no servers configured) works exactly as before
- [ ] API keys stored in Keychain, not plain AsyncStorage
- [ ] All new UI strings have l10n keys in en.json
- [ ] All tests pass, coverage >= 60%
- [ ] TypeScript compiles without errors, ESLint passes

---

## Updated Affected Files

### Removed from original

| File | Reason |
|------|--------|
| `src/components/ServerConfigSheet/*` | Replaced by RemoteModelSheet + ServerDetailsSheet |
| `src/screens/SettingsScreen/SettingsScreen.tsx` (heavy modification) | Now lightweight "Connected Servers" only |

### Added

| File | Action | Reason |
|------|--------|--------|
| `src/components/RemoteModelSheet/RemoteModelSheet.tsx` | CREATE | Add remote model flow |
| `src/components/RemoteModelSheet/styles.ts` | CREATE | Styles |
| `src/components/RemoteModelSheet/index.ts` | CREATE | Re-export |
| `src/components/ServerDetailsSheet/ServerDetailsSheet.tsx` | CREATE | Server maintenance |
| `src/components/ServerDetailsSheet/styles.ts` | CREATE | Styles |
| `src/components/ServerDetailsSheet/index.ts` | CREATE | Re-export |

### Modified (changed scope)

| File | Original Scope | New Scope |
|------|---------------|-----------|
| `src/screens/ModelsScreen/ModelsScreen.tsx` | Not in original | FAB extension with "Add Remote Model" |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | Full server CRUD section | Lightweight "Connected Servers" read-only list |
| `src/store/ServerStore.ts` | Server CRUD + auto-fetch all | + `userSelectedModels`, `removeServerIfOrphaned`, `getModelsNotYetAdded` |
| `src/store/ModelStore.ts` | `remoteModels` = all from active servers | `remoteModels` = only user-selected models |
| `src/screens/ModelsScreen/ModelCard/ModelCard.tsx` | Cloud icon + server badge | + tappable "Server: name" link |

### Unchanged from original

All other files (types, completionTypes, openai.ts, sseParser.ts, completionEngines.ts,
useChatSession.ts, ChatScreen.tsx, HeaderRight.tsx, ChatPalModelPickerSheet.tsx,
ChatView.tsx, useMessageActions.ts, BenchmarkScreen.tsx, test files, mock files)
remain as planned in the original story.

---

## Updated L10n Keys

Replace original server management keys with:

```json
{
  "addRemoteModel": "Add Remote Model",
  "yourServers": "Your Servers",
  "orConnectNewServer": "or connect new server",
  "serverUrl": "Server URL",
  "serverUrlPlaceholder": "e.g., http://192.168.1.100:1234",
  "serverName": "Server Name",
  "apiKey": "API Key",
  "apiKeyPlaceholder": "Optional - required for OpenAI/Groq",
  "apiKeyDescription": "Stored securely on device.",
  "selectModel": "Select Model",
  "addModel": "Add Model",
  "connected": "Connected",
  "connectionFailed": "Connection failed: {{error}}",
  "connecting": "Connecting...",
  "noModelsAvailable": "No models available on this server.",
  "alreadyAdded": "Already added",
  "remotePrivacyNotice": "Messages sent to remote servers leave your device. Only connect to servers you trust.",
  "serverUrlHttpWarning": "iOS requires HTTPS for non-local servers. Use https:// or a local network address.",
  "serverUrlRequired": "Server URL is required",
  "serverUrlInvalid": "Invalid URL format",
  "connectedServers": "Connected Servers",
  "modelsCount": "{{count}} models",
  "serverDetails": "Server Details",
  "modelsUsingServer": "Models using this server:",
  "saveChanges": "Save Changes",
  "removeServer": "Remove Server",
  "removeServerMessage": "Remove {{serverName}} and its {{count}} models?",
  "removeRemoteModel": "Remove {{modelName}} ({{serverName}})?",
  "authFailed": "Authentication failed for {{serverName}}.",
  "updateApiKey": "Update API Key",
  "remoteModel": "Remote",
  "remoteIndicator": "Remote"
}
```

Keys removed (no longer needed): `remoteServers`, `remoteServersDescription`, `addServer`,
`editServer`, `testConnection`, `testConnectionSuccess`, `testConnectionFailed`, `testing`,
`serverActive`, `deleteServerTitle`, `deleteServerMessage`, `noServersConfigured`,
`serverNamePlaceholder`, `serverNameRequired`.

---

## Updated Checkpoints

Replace Steps 5-6 checkpoints with:

| Checkpoint | Status | Agent | Notes |
|------------|--------|-------|-------|
| Step 5a complete | PENDING | implementer | RemoteModelSheet |
| Step 5b complete | PENDING | implementer | ServerDetailsSheet |
| Step 5c complete | PENDING | implementer | Models screen FAB extension |
| Step 5d complete | PENDING | implementer | Settings "Connected Servers" section |
| Step 6 complete | PENDING | implementer | Remote models in list (user-selected only) |

---

## Visual Confirmation Updates

```json
[
  {"prompt": "Go to Models screen, tap FAB", "name": "models-fab-remote-option", "description": "FAB should show 'Add Remote Model' as a third option"},
  {"prompt": "Open Add Remote Model sheet", "name": "remote-model-sheet-empty", "description": "Sheet should show URL field, privacy notice on first use"},
  {"prompt": "Go to Settings screen", "name": "settings-connected-servers", "description": "Settings should show 'Connected Servers' section if servers exist"}
]
```

---

## Changelog Entry

| Date | Agent/Human | Change |
|------|-------------|--------|
| 2026-02-24 | human + design review | UX amendment: model-centric redesign. Move add flow to Models screen FAB. Server becomes hidden plumbing. User picks individual models. Server maintenance via model card link + Settings shortcut. Informed by Norman/Wroblewski/Rams analysis. |
