# Story: UX Amendment — Model-Centric Remote Model Management

## Metadata
- **Task ID**: TASK-20260219-1727-ux-amendment
- **Amends**: TASK-20260219-1727
- **Source**: UX design review
- **Complexity**: standard
- **Native Changes**: NO
- **Visual Confirmation**: YES
- **Created**: 2026-02-24
- **Status**: draft

## Environment
- **Worktree**: `./worktrees/TASK-20260219-1727`
- **Branch**: `feature/TASK-20260219-1727`
- **Base**: `main`

---

## Progress Tracking

### Current Phase
`[x] Planning → [x] Approved → [x] Implementing → [ ] Testing → [ ] Reviewing → [ ] PR Created`

### Checkpoints (Updated by Agents)

| Checkpoint | Status | Agent | Commit | Notes |
|------------|--------|-------|--------|-------|
| Story approved | DONE | human | - | |
| Step 1 complete | DONE | implementer | fd45f25 | ServerStore: add userSelectedModels, remove isActive |
| Step 2 complete | DONE | implementer | 7adfc00 | ModelStore: remoteModels filters to user-selected only |
| Step 3 complete | DONE | implementer | a9af5a6 | RemoteModelSheet component |
| Step 4 complete | DONE | implementer | c2a68d8 | ServerDetailsSheet component |
| Step 5 complete | DONE | implementer | 4c329eb | FAB extension on Models screen |
| Step 6 complete | DONE | implementer | 4ac045c | ModelCard: server link + delete flow |
| Step 7 complete | DONE | implementer | 43e3180 | Settings: Connected Servers read-only |
| Step 8 complete | DONE | implementer | 768af0c | Remove ServerConfigSheet, update components |
| Step 9 complete | PENDING | tester | - | Mock store updates + tests |
| Tests written | PENDING | tester | - | |
| Review passed | PENDING | reviewer | - | |
| PR created | PENDING | reviewer | - | |

### Last Agent Handoff
```yaml
from_agent: implementer
to_agent: tester
timestamp: 2026-02-24T22:00:00Z
status: "Implementation complete (Steps 1-8), ready for test fixes"
completed:
  - Step 1: Types, L10n, ServerStore foundation (commit fd45f25)
  - Step 2: ModelStore remoteModels filter (commit 7adfc00)
  - Step 3: RemoteModelSheet component (commit a9af5a6)
  - Step 4: ServerDetailsSheet component (commit c2a68d8)
  - Step 5: FAB extension + wire sheets (commit 4c329eb)
  - Step 6: ModelCard server link + delete (commit 4ac045c)
  - Step 7: Settings Connected Servers (commit 43e3180)
  - Step 8: Remove ServerConfigSheet (commit 768af0c)
  - Lint/prettier formatting fix (commit 67a76bd)
next_steps:
  - Fix ServerStore.test.ts (5 failing tests from isActive removal)
  - Write new tests for userSelectedModels, RemoteModelSheet, etc.
  - Run full test suite
blockers: []
context_for_next_agent: |
  Steps 1-8 are complete. TypeScript compiles clean (non-test files).
  ESLint passes. 5 tests fail in ServerStore.test.ts due to isActive
  removal. 1617/1622 tests pass. Mock store already updated.
  Test file needs: remove isActive refs, delete activeServers tests,
  add userSelectedModels/removeServerIfOrphaned/getModelsNotYetAdded tests.
```

---

## Context (For Recovery After Context Reset)

> **If you're an agent resuming work on this story:**
> 1. Read the "Progress Tracking" section above
> 2. Check `git log` in the worktree for commits
> 3. Read the "Last Agent Handoff" section
> 4. Continue from the next incomplete checkpoint

### Background

The original TASK-20260219-1727 implemented an OpenAI-compatible API client with
server-centric UX: full server CRUD in Settings, all models auto-populated.
A UX design review (Norman/Wroblewski/Rams analysis) identified this as backwards --
users think in terms of models, not servers. This amendment redesigns the UI layer:

- Users add **individual remote models** from the Models screen FAB
- Servers are hidden plumbing (created/removed automatically)
- Server maintenance (URL/key changes) is accessible but not prominent

### Current State (What exists NOW in the worktree)

The following are ALREADY IMPLEMENTED and committed:

1. **`src/api/openai.ts`** — `fetchModels()`, `testConnection()`, `streamChatCompletion()` (XHR-based)
2. **`src/api/sseParser.ts`** — SSE parser
3. **`src/utils/completionTypes.ts`** — `CompletionResult`, `CompletionStreamData`, `CompletionEngine` interface
4. **`src/api/completionEngines.ts`** — `LocalCompletionEngine`, `OpenAICompletionEngine`
5. **`src/hooks/useChatSession.ts`** — engine-based completion integration
6. **`src/store/ServerStore.ts`** — Server CRUD with Keychain, `isActive` toggle, auto-fetch on foreground
7. **`src/store/ModelStore.ts`** — `remoteModels` computed (loops all active servers), `selectModel()` wrapper, `setRemoteModel()`, `engine` field
8. **`src/components/ServerConfigSheet/`** — Bottom sheet with name/URL/key/test-connection (in Settings)
9. **`src/screens/SettingsScreen/SettingsScreen.tsx`** — Full "Remote Servers" CRUD section (add/edit/delete/toggle)
10. **`src/screens/ModelsScreen/ModelCard/ModelCard.tsx`** — Remote model support (cloud icon, server badge, load/offload only)
11. **`__mocks__/stores/serverStore.ts`** — Mock store for tests
12. **L10n keys** — All current server-centric keys in `en.json` settings section

### Target State

1. **Models screen FAB** has "Add Remote Model" as third speed-dial option
2. **RemoteModelSheet** (new): URL -> connect -> pick ONE model -> Add Model
3. **ServerDetailsSheet** (new): Edit URL/key, see models using server, Remove Server
4. **Settings** has lightweight "Connected Servers" read-only list (not CRUD)
5. **ModelCard** has tappable "Server: name" link opening ServerDetailsSheet
6. **ServerStore** adds `userSelectedModels`, `removeServerIfOrphaned()`, `getModelsNotYetAdded()`; removes `isActive`
7. **ModelStore.remoteModels** filters to user-selected models only
8. **ServerConfigSheet** removed (replaced by RemoteModelSheet + ServerDetailsSheet)
9. Old server-centric l10n keys replaced with model-centric keys

---

## Requirements

### Functional
1. [MUST] Add `userSelectedModels` to ServerStore — `Array<{serverId, remoteModelId}>` persisted
2. [MUST] Remove `isActive` from ServerConfig and all usages
3. [MUST] `ModelStore.remoteModels` filters to only user-selected models
4. [MUST] RemoteModelSheet: URL auto-probe (debounced 800ms), server name auto-fill from hostname, model selection, API key input
5. [MUST] RemoteModelSheet: known server chips when servers exist
6. [MUST] RemoteModelSheet: privacy notice inline (first time only)
7. [MUST] RemoteModelSheet: ATS warning for non-local http:// URLs
8. [MUST] ServerDetailsSheet: edit URL/key, list models using server, Remove Server (destructive)
9. [MUST] FAB on Models screen has "Add Remote Model" third option
10. [MUST] ModelCard shows tappable "Server: name" link for remote models
11. [MUST] Settings shows read-only "Connected Servers" (name + count + chevron)
12. [MUST] Deleting last model from server cleans up server config + API key
13. [MUST] Remove ServerConfigSheet component entirely
14. [MUST] Update l10n keys in en.json
15. [SHOULD] If server has one model, auto-select (no picker shown)
16. [SHOULD] Already-added models shown as disabled in model picker

### Non-Functional
- No native changes required
- All existing backend/engine tests must continue to pass
- New UI components should follow existing Sheet and component patterns

### Migration Considerations
- [x] Does this change affect stored user data/settings? YES
- `ServerConfig.isActive` field removed — existing persisted servers no longer have this field
- `userSelectedModels` is a new persisted field (starts empty)
- Migration strategy: `backwards compatible` — removing `isActive` is safe (TypeScript ignores extra fields in deserialized JSON). Existing users who already added servers will see them but won't have any models selected. They would need to re-add models via the new flow. This is acceptable since this feature is unreleased (draft PR).
- Notes: Since PR #597 is still a draft and unreleased, migration is not needed for end users.

---

## Acceptance Criteria

- [ ] Models screen FAB has "Add Remote Model" option alongside existing options
- [ ] Can add a remote model via URL entry with auto-probe connection
- [ ] Server name auto-fills from hostname after successful connection
- [ ] If server has multiple models, user picks one from inline list
- [ ] If server has one model, it is auto-selected (no picker shown)
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
- [ ] Known server chip shows Retry + "Enter URL manually" when server is offline
- [ ] Local-only usage (no servers configured) works exactly as before
- [ ] All new UI strings have l10n keys in en.json
- [ ] All tests pass, coverage >= 60%
- [ ] TypeScript compiles without errors, ESLint passes

---

## Affected Files

| File | Action | Reason | Status |
|------|--------|--------|--------|
| `src/store/ServerStore.ts` | MODIFY | Add `userSelectedModels`, `removeServerIfOrphaned`, `getModelsNotYetAdded`; remove `isActive` | PENDING |
| `src/utils/types.ts` | MODIFY | Remove `isActive` from `ServerConfig` | PENDING |
| `src/store/ModelStore.ts` | MODIFY | `remoteModels` computed filters to user-selected only | PENDING |
| `src/components/RemoteModelSheet/RemoteModelSheet.tsx` | CREATE | Add remote model bottom sheet | PENDING |
| `src/components/RemoteModelSheet/styles.ts` | CREATE | Styles | PENDING |
| `src/components/RemoteModelSheet/index.ts` | CREATE | Re-export | PENDING |
| `src/components/ServerDetailsSheet/ServerDetailsSheet.tsx` | CREATE | Server maintenance bottom sheet | PENDING |
| `src/components/ServerDetailsSheet/styles.ts` | CREATE | Styles | PENDING |
| `src/components/ServerDetailsSheet/index.ts` | CREATE | Re-export | PENDING |
| `src/screens/ModelsScreen/FABGroup/FABGroup.tsx` | MODIFY | Add "Add Remote Model" third FAB action | PENDING |
| `src/screens/ModelsScreen/ModelsScreen.tsx` | MODIFY | Wire RemoteModelSheet + ServerDetailsSheet | PENDING |
| `src/screens/ModelsScreen/ModelCard/ModelCard.tsx` | MODIFY | Add tappable server link + remote delete flow | PENDING |
| `src/screens/ModelsScreen/ModelCard/styles.ts` | MODIFY | Add server link styles | PENDING |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | MODIFY | Replace full CRUD with read-only "Connected Servers" | PENDING |
| `src/screens/SettingsScreen/styles.ts` | MODIFY | Remove server CRUD styles, add Connected Servers styles | PENDING |
| `src/components/ServerConfigSheet/` | DELETE | Replaced by RemoteModelSheet + ServerDetailsSheet | PENDING |
| `src/components/index.ts` | MODIFY | Replace ServerConfigSheet export with RemoteModelSheet + ServerDetailsSheet | PENDING |
| `src/locales/en.json` | MODIFY | Replace server-centric keys with model-centric keys | PENDING |
| `__mocks__/stores/serverStore.ts` | MODIFY | Add `userSelectedModels`, new methods, remove `isActive`-related | PENDING |

---

## Implementation Plan

### Step 1: Types, L10n Keys, ServerStore — Foundation Changes

**Files**: `src/utils/types.ts`, `src/locales/en.json`, `src/store/ServerStore.ts`
**Status**: PENDING

**Change**:

**1a. `src/utils/types.ts` (line 334-340)**
- [ ] Remove `isActive: boolean` from `ServerConfig` interface

Current:
```typescript
export interface ServerConfig {
  id: string;
  name: string;
  url: string;
  isActive: boolean;
  lastConnected?: number;
}
```

New:
```typescript
export interface ServerConfig {
  id: string;
  name: string;
  url: string;
  lastConnected?: number;
}
```

**1b. `src/locales/en.json`** — Add ALL new l10n keys and remove old server-centric keys NOW (not in Step 8). This unblocks all subsequent steps that reference l10n keys.
- [ ] Remove old keys: `remoteServers`, `remoteServersDescription`, `addServer`, `editServer`, `testConnection`, `testConnectionSuccess`, `testConnectionFailed`, `testing`, `serverActive`, `deleteServerTitle`, `deleteServerMessage`, `noServersConfigured`, `serverNamePlaceholder`, `serverNameRequired`
- [ ] Keep reused keys: `serverName`, `serverUrl`, `serverUrlPlaceholder`, `apiKey`, `apiKeyPlaceholder`, `apiKeyDescription`, `remoteModel`, `remotePrivacyNotice`, `remoteIndicator`, `serverUrlRequired`, `serverUrlInvalid`, `serverUrlHttpWarning`
- [ ] Add new model-centric keys to `settings` section:
```json
"addRemoteModel": "Add Remote Model",
"yourServers": "Your Servers",
"orConnectNewServer": "or connect new server",
"selectModel": "Select Model",
"addModel": "Add Model",
"connected": "Connected",
"connectionFailed": "Connection failed: {{error}}",
"connecting": "Connecting...",
"noModelsAvailable": "No models available on this server.",
"alreadyAdded": "Already added",
"connectedServers": "Connected Servers",
"modelsCount": "{{count}} models",
"serverDetails": "Server Details",
"modelsUsingServer": "Models using this server:",
"saveChanges": "Save Changes",
"removeServer": "Remove Server",
"removeServerMessage": "Remove {{serverName}} and its {{count}} models?",
"removeRemoteModel": "Remove {{modelName}} ({{serverName}})?",
"retryConnection": "Retry",
"enterUrlManually": "Enter URL manually"
```

**1c. `src/store/ServerStore.ts`**
- [ ] Add `userSelectedModels` observable array: `Array<{serverId: string, remoteModelId: string}>`
- [ ] Add `userSelectedModels` to `makePersistable` properties list (line 31)
- [ ] Remove `activeServers` computed (line 43-45) — no longer needed
- [ ] Modify `addServer()` (line 48): Remove `isActive` from the created config. Do NOT auto-fetch models on add (the add flow in RemoteModelSheet handles fetching separately)
- [ ] Modify `updateServer()` (line 64): Remove `isActive` logic branches (lines 69-76)
- [ ] Modify `fetchModelsForServer()` (line 124): Remove the `!server.isActive` guard (line 126-128) — servers are always "active" if they exist
- [ ] Modify `fetchAllRemoteModels()` (line 157): Fetch for ALL servers, not just `activeServers`
- [ ] Add `addUserSelectedModel(serverId: string, remoteModelId: string)` action: pushes to `userSelectedModels`
- [ ] Add `removeUserSelectedModel(serverId: string, remoteModelId: string)` action: filters out the entry
- [ ] Add `removeServerIfOrphaned(serverId: string)` action: if no `userSelectedModels` reference this `serverId`, call `removeServer(serverId)`
- [ ] Add `getModelsNotYetAdded(serverId: string): RemoteModelInfo[]` computed/method: returns models from `serverModels.get(serverId)` that do NOT have a matching entry in `userSelectedModels`
- [ ] Add `getUserSelectedModelsForServer(serverId: string): Array<{serverId, remoteModelId}>` method: returns filtered `userSelectedModels` for a given server
- [ ] Modify `removeServer()` (line 80): also remove all `userSelectedModels` entries for this server

**Pattern Reference**: Existing `ServerStore.ts` for MobX patterns; `makePersistable` at line 30-34

**Code Guidance** for new methods:
```typescript
// New observable
userSelectedModels: Array<{serverId: string; remoteModelId: string}> = [];

// In constructor, add to makePersistable:
properties: ['servers', 'privacyNoticeAcknowledged', 'userSelectedModels'],

// New actions
addUserSelectedModel(serverId: string, remoteModelId: string): void {
  // Prevent duplicates
  const exists = this.userSelectedModels.some(
    m => m.serverId === serverId && m.remoteModelId === remoteModelId,
  );
  if (!exists) {
    this.userSelectedModels.push({serverId, remoteModelId});
  }
}

removeUserSelectedModel(serverId: string, remoteModelId: string): void {
  this.userSelectedModels = this.userSelectedModels.filter(
    m => !(m.serverId === serverId && m.remoteModelId === remoteModelId),
  );
}

removeServerIfOrphaned(serverId: string): void {
  const hasModels = this.userSelectedModels.some(
    m => m.serverId === serverId,
  );
  if (!hasModels) {
    this.removeServer(serverId);
  }
}

getModelsNotYetAdded(serverId: string): RemoteModelInfo[] {
  const allModels = this.serverModels.get(serverId) || [];
  return allModels.filter(
    m => !this.userSelectedModels.some(
      sel => sel.serverId === serverId && sel.remoteModelId === m.id,
    ),
  );
}

getUserSelectedModelsForServer(serverId: string): Array<{serverId: string; remoteModelId: string}> {
  return this.userSelectedModels.filter(m => m.serverId === serverId);
}
```

Also update `removeServer`:
```typescript
removeServer(id: string): void {
  this.servers = this.servers.filter(s => s.id !== id);
  this.serverModels.delete(id);
  // Remove all user-selected models for this server
  this.userSelectedModels = this.userSelectedModels.filter(
    m => m.serverId !== id,
  );
  // Clean up API key from keychain
  this.removeApiKey(id);
}
```

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
npx tsc --noEmit 2>&1 | head -30
```

---

### Step 2: ModelStore — `remoteModels` Filters to User-Selected Only

**Files**: `src/store/ModelStore.ts`
**Status**: PENDING

**Change**:
- [ ] Replace `remoteModels` computed (lines 1829-1848) to iterate `serverStore.userSelectedModels` instead of `serverStore.serverModels`

Current (line 1829-1848):
```typescript
get remoteModels(): Model[] {
  const remoteList: Model[] = [];
  for (const [serverId, serverModelList] of serverStore.serverModels) {
    const server = serverStore.servers.find(s => s.id === serverId);
    if (!server?.isActive) {
      continue;
    }
    for (const rm of serverModelList) {
      remoteList.push(
        createRemoteModel({
          serverId,
          serverName: server.name,
          remoteModelId: rm.id,
          modelName: rm.id,
        }),
      );
    }
  }
  return remoteList;
}
```

New:
```typescript
get remoteModels(): Model[] {
  const models: Model[] = [];
  for (const selected of serverStore.userSelectedModels) {
    const server = serverStore.servers.find(s => s.id === selected.serverId);
    if (!server) {
      continue;
    }
    // Use the remote model ID as the display name
    models.push(
      createRemoteModel({
        serverId: selected.serverId,
        serverName: server.name,
        remoteModelId: selected.remoteModelId,
        modelName: selected.remoteModelId,
      }),
    );
  }
  return models;
}
```

**Key Design Decision**: We do NOT check if the model still exists on the server (`serverModels`). The model entry persists even if the server is temporarily offline. The model will show as "available" in the list and a connection error will surface when the user tries to chat.

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
npx tsc --noEmit 2>&1 | head -30
```

---

### Step 3: RemoteModelSheet — Add Remote Model Flow

**Files**: `src/components/RemoteModelSheet/RemoteModelSheet.tsx`, `styles.ts`, `index.ts`
**Status**: PENDING

**Change**:
- [ ] Create `src/components/RemoteModelSheet/index.ts` — re-export
- [ ] Create `src/components/RemoteModelSheet/styles.ts` — styles following `ServerConfigSheet/styles.ts` pattern
- [ ] Create `src/components/RemoteModelSheet/RemoteModelSheet.tsx` — main component

**Pattern Reference**: 
- `src/components/HFTokenSheet/HFTokenSheet.tsx` (Sheet + secure input pattern)
- `src/components/ServerConfigSheet/ServerConfigSheet.tsx` (URL validation, API key, test connection — we will take from this then delete it)
- `src/components/Sheet/Sheet.tsx` (Sheet component API: `isVisible`, `onClose`, `title`, `snapPoints`)

**Props**:
```typescript
interface RemoteModelSheetProps {
  isVisible: boolean;
  onDismiss: () => void;
  onModelAdded?: () => void; // callback after successful add
}
```

**Internal State** (NO `phase` variable — probeResult drives progressive disclosure):
```typescript
// Connection
const [url, setUrl] = useState('');
const [serverName, setServerName] = useState('');
const [apiKey, setApiKey] = useState('');
const [secureTextEntry, setSecureTextEntry] = useState(true);

// Auto-probe — probeResult is THE state machine:
//   null → show URL field only
//   probeResult.ok === true → show name, key, model list
//   probeResult.ok === false → show error below URL
const [isProbing, setIsProbing] = useState(false);
const [probeResult, setProbeResult] = useState<{ok: boolean; error?: string} | null>(null);

// Available models from server
const [availableModels, setAvailableModels] = useState<RemoteModelInfo[]>([]);
const [selectedModelId, setSelectedModelId] = useState<string | null>(null);

// Known server selection
const [selectedServerId, setSelectedServerId] = useState<string | null>(null);

// Saving
const [isSaving, setIsSaving] = useState(false);

// Errors
const [urlError, setUrlError] = useState('');
```

**CRITICAL: Reset all state when sheet reopens** (same pattern as ServerConfigSheet lines 63-83):
```typescript
useEffect(() => {
  if (isVisible) {
    setUrl('');
    setServerName('');
    setApiKey('');
    setSecureTextEntry(true);
    setIsProbing(false);
    setProbeResult(null);
    setAvailableModels([]);
    setSelectedModelId(null);
    setSelectedServerId(null);
    setIsSaving(false);
    setUrlError('');
  }
}, [isVisible]);
```

**UI Structure (progressive disclosure)**:

1. **Known Server Chips** (only when `serverStore.servers.length > 0`):
   - Row of tappable Chip components from react-native-paper
   - Each chip = server name
   - Tapping a chip: set `selectedServerId`, fetch models for that server, go straight to model selection phase
   - Section label: "Your Servers" with divider "or connect new server"

2. **URL Input**:
   - `TextInput` with `keyboardType="url"`, `autoCapitalize="none"`
   - Debounced auto-probe on URL change (800ms) using `lodash/debounce`
   - URL validation: try `new URL(url)` — inline error if invalid
   - On successful probe: auto-fill `serverName` from hostname, fetch models, transition to showing more fields

3. **Post-Connection Fields** (visible after successful probe OR chip selection):
   - Server Name input (editable, auto-filled from hostname)
   - API Key input (secure entry with toggle, following HFTokenSheet eye icon pattern)
   - `apiKeyDescription`: "Stored securely on device."
   - ATS warning for non-local `http://` (reuse `isLocalHost()` from ServerConfigSheet)
   - Model selection radio list

4. **Model Selection**:
   - List of available models (radio buttons using react-native-paper `RadioButton`)
   - Already-added models shown disabled with checkmark and "(Already added)" text
   - If only one model: auto-select, skip showing the list
   - If zero models: "No models available on this server." with disabled Add button

5. **Privacy Notice**:
   - Shown inline at top when `!serverStore.privacyNoticeAcknowledged`
   - Styled banner (reuse `privacyContainer`/`privacyText` styles from ServerConfigSheet)
   - Dismissed when user proceeds (acknowledged flag set on first add)

6. **Add Model Button** (in `Sheet.Actions`):
   - Disabled until model selected
   - On press: creates/reuses server config, saves API key, adds to `userSelectedModels`, calls `onModelAdded`, dismisses

**Auto-Probe Logic** (key behaviors — treats (url, apiKey) as a pair):

CRITICAL DESIGN DECISIONS:
1. Use static imports for `testConnection`/`fetchModels` — no dynamic `import()` (no bundle reason for lazy-load here)
2. Probe fires when EITHER url OR apiKey changes (debounced). Fixes the race condition where user enters URL → 401 → enters key → nothing happens.
3. Store apiKey in a ref so the debounced function always reads the current value.
4. Smart server name: detect common ports (1234→LM Studio, 11434→Ollama, 8080→llama.cpp), then hostname.

```typescript
import {testConnection, fetchModels} from '../../api/openai';
import debounce from 'lodash/debounce';

// Smart server name from URL
function guessServerName(urlStr: string): string {
  try {
    const parsed = new URL(urlStr);
    const port = parsed.port;
    if (port === '1234') return 'LM Studio';
    if (port === '11434') return 'Ollama';
    if (port === '8080') return 'llama.cpp';
    return parsed.hostname;
  } catch {
    return '';
  }
}

// Inside component:
const apiKeyRef = useRef(apiKey);
useEffect(() => { apiKeyRef.current = apiKey; }, [apiKey]);

const probeServer = useCallback(async (probeUrl: string) => {
  const trimmedUrl = probeUrl.trim();
  if (!trimmedUrl) return;
  try {
    new URL(trimmedUrl);
  } catch {
    setUrlError(l10n.settings.serverUrlInvalid);
    return;
  }
  setUrlError('');
  setIsProbing(true);
  setProbeResult(null);
  try {
    const key = apiKeyRef.current.trim() || undefined;
    const result = await testConnection(trimmedUrl, key);
    setProbeResult({ok: result.ok, error: result.error});
    if (result.ok) {
      setServerName(prev => prev || guessServerName(trimmedUrl));
      const models = await fetchModels(trimmedUrl, key);
      setAvailableModels(models);
      if (models.length === 1) {
        setSelectedModelId(models[0].id);
      }
    }
  } catch (error: any) {
    setProbeResult({ok: false, error: error.message});
  } finally {
    setIsProbing(false);
  }
}, [l10n]);

const debouncedProbe = useMemo(
  () => debounce(probeServer, 800),
  [probeServer],
);

// Trigger on url change
useEffect(() => { debouncedProbe(url); }, [url, debouncedProbe]);

// Re-probe on apiKey blur (not every keystroke — reduces noise)
// The apiKey onBlur handler calls: debouncedProbe(url);
// This re-probes with the current (url, apiKey) pair.
```

**Save Logic**:
```typescript
const handleAddModel = async () => {
  if (!selectedModelId) return;
  setIsSaving(true);
  try {
    let serverId = selectedServerId;
    if (!serverId) {
      // Create new server
      serverId = serverStore.addServer({
        name: serverName.trim(),
        url: url.trim(),
      });
      if (apiKey.trim()) {
        await serverStore.setApiKey(serverId, apiKey.trim());
      }
    }
    // Acknowledge privacy notice
    if (!serverStore.privacyNoticeAcknowledged) {
      serverStore.acknowledgePrivacyNotice();
    }
    // Add model to user selections
    serverStore.addUserSelectedModel(serverId, selectedModelId);
    // Fetch models for this server so serverModels is populated
    await serverStore.fetchModelsForServer(serverId);
    onModelAdded?.();
    onDismiss();
  } finally {
    setIsSaving(false);
  }
};
```

**Known Server Chip Selection** (handles offline with Retry + manual URL fallback):
```typescript
const handleServerChipPress = async (server: ServerConfig) => {
  setSelectedServerId(server.id);
  setServerName(server.name);
  setUrl(server.url);
  setIsProbing(true);
  setProbeResult(null);
  try {
    const key = await serverStore.getApiKey(server.id);
    apiKeyRef.current = key || '';
    setApiKey(key || '');
    const models = await fetchModels(server.url, key || undefined);
    runInAction(() => {
      serverStore.serverModels.set(server.id, models);
    });
    const notYetAdded = serverStore.getModelsNotYetAdded(server.id);
    setAvailableModels(models); // Show all (already-added shown as disabled)
    if (notYetAdded.length === 1) {
      setSelectedModelId(notYetAdded[0].id);
    }
    setProbeResult({ok: true});
  } catch (error: any) {
    setProbeResult({ok: false, error: error.message});
    // UI shows: "Could not connect to {name}. Check if the server is running."
    // with [Retry] button (calls handleServerChipPress again)
    // and "Enter URL manually" link (calls handleDeselectChip: clears selectedServerId,
    // resets url/name/key, shows fresh URL input)
  } finally {
    setIsProbing(false);
  }
};

const handleDeselectChip = () => {
  setSelectedServerId(null);
  setUrl('');
  setServerName('');
  setApiKey('');
  setProbeResult(null);
  setAvailableModels([]);
  setSelectedModelId(null);
};
```

**Chip offline error UI** (rendered when selectedServerId exists and probeResult?.ok === false):
```tsx
<View style={styles.chipErrorContainer}>
  <Text style={styles.errorText}>
    {t(l10n.settings.connectionFailed, {error: probeResult.error || 'Unknown'})}
  </Text>
  <View style={styles.chipErrorActions}>
    <Button compact mode="text" onPress={() => handleServerChipPress(selectedServer)}>
      {l10n.settings.retryConnection}
    </Button>
    <Button compact mode="text" onPress={handleDeselectChip}>
      {l10n.settings.enterUrlManually}
    </Button>
  </View>
</View>
```

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
npx tsc --noEmit 2>&1 | head -30
```

---

### Step 4: ServerDetailsSheet — Server Maintenance

**Files**: `src/components/ServerDetailsSheet/ServerDetailsSheet.tsx`, `styles.ts`, `index.ts`
**Status**: PENDING

**Change**:
- [ ] Create `src/components/ServerDetailsSheet/index.ts`
- [ ] Create `src/components/ServerDetailsSheet/styles.ts`
- [ ] Create `src/components/ServerDetailsSheet/ServerDetailsSheet.tsx`

**Props**:
```typescript
interface ServerDetailsSheetProps {
  isVisible: boolean;
  onDismiss: () => void;
  serverId: string | null; // null = nothing to show
}
```

**Internal State**:
```typescript
const [url, setUrl] = useState('');
const [apiKey, setApiKey] = useState('');
const [secureTextEntry, setSecureTextEntry] = useState(true);
const [isProbing, setIsProbing] = useState(false);
const [probeResult, setProbeResult] = useState<{ok: boolean; error?: string} | null>(null);
const [isSaving, setIsSaving] = useState(false);
```

**UI Structure**:

1. **Title**: Server name (from `serverStore.servers.find(s => s.id === serverId)`)

2. **URL Input** (editable):
   - Pre-filled with current URL
   - Auto-probe on change (debounced, same pattern as RemoteModelSheet)
   - Shows connected/failed status inline

3. **API Key Input** (editable):
   - Pre-filled from Keychain (loaded via `serverStore.getApiKey()` on mount)
   - Secure entry with toggle (same pattern as HFTokenSheet)
   - "Stored securely on device."

4. **Models Using This Server** (read-only list):
   - Derived from `serverStore.getUserSelectedModelsForServer(serverId)`
   - Each item: model name (text only, not tappable)
   - Header: "Models using this server:"

5. **Save Changes Button** (in `Sheet.Actions`):
   - Updates server URL/name via `serverStore.updateServer()`
   - Saves API key via `serverStore.setApiKey()`

6. **Remove Server** (destructive, at bottom):
   - Text button with destructive color
   - "Removes all N models above."
   - On press: `Alert.alert` confirmation
   - On confirm: `serverStore.removeServer(serverId)` (which also cleans up `userSelectedModels`)
   - Dismisses sheet

**Effect on mount/visibility change**:
```typescript
useEffect(() => {
  if (isVisible && serverId) {
    const server = serverStore.servers.find(s => s.id === serverId);
    if (server) {
      setUrl(server.url);
    }
    serverStore.getApiKey(serverId).then(key => {
      setApiKey(key || '');
    });
    setProbeResult(null);
  }
}, [isVisible, serverId]);
```

**Pattern Reference**: `src/components/ServerConfigSheet/ServerConfigSheet.tsx` (field layout, validation, Sheet.Actions pattern)

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
npx tsc --noEmit 2>&1 | head -30
```

---

### Step 5: Models Screen — FAB Extension + Wire Sheets

**Files**: `src/screens/ModelsScreen/FABGroup/FABGroup.tsx`, `src/screens/ModelsScreen/ModelsScreen.tsx`
**Status**: PENDING

**Change**:

**5a. `src/screens/ModelsScreen/FABGroup/FABGroup.tsx`**
- [ ] Add `onAddRemoteModel` prop to `FABGroupProps`
- [ ] Add third action to the `actions` useMemo array

Current props (line 10-13):
```typescript
interface FABGroupProps {
  onAddHFModel: () => void;
  onAddLocalModel: () => void;
}
```

New:
```typescript
interface FABGroupProps {
  onAddHFModel: () => void;
  onAddLocalModel: () => void;
  onAddRemoteModel: () => void;
}
```

Add to `actions` array (after the `local-fab` entry):
```typescript
{
  testID: 'remote-fab',
  icon: 'cloud-plus-outline',
  label: l10n.settings.addRemoteModel, // l10n key added in Step 8
  accessibilityLabel: l10n.settings.addRemoteModel,
  style: styles.actionButton,
  onPress: () => {
    onAddRemoteModel();
  },
},
```

Note: The `l10n.settings.addRemoteModel` key must exist in en.json. We will add it in Step 8. The implementer should add the l10n key before or alongside this step to avoid TypeScript errors.

**5b. `src/screens/ModelsScreen/ModelsScreen.tsx`**
- [ ] Add imports for `RemoteModelSheet` and `ServerDetailsSheet`
- [ ] Add state: `remoteModelSheetVisible`, `serverDetailsSheetVisible`, `selectedServerId`
- [ ] Add handler: `handleAddRemoteModel`, `handleOpenServerDetails`
- [ ] Pass `onAddRemoteModel` to FABGroup
- [ ] Render `RemoteModelSheet` and `ServerDetailsSheet` components
- [ ] Pass `handleOpenServerDetails` down to ModelCard via a new prop

Add state variables (after existing state declarations around line 37-45):
```typescript
const [remoteModelSheetVisible, setRemoteModelSheetVisible] = useState(false);
const [serverDetailsSheetVisible, setServerDetailsSheetVisible] = useState(false);
const [selectedServerId, setSelectedServerId] = useState<string | null>(null);
```

Add handlers:
```typescript
const handleAddRemoteModel = () => {
  setRemoteModelSheetVisible(true);
};

const handleOpenServerDetails = (serverId: string) => {
  setSelectedServerId(serverId);
  setServerDetailsSheetVisible(true);
};
```

Update FABGroup usage (line 392-395):
```tsx
<FABGroup
  onAddHFModel={() => setHFSearchVisible(true)}
  onAddLocalModel={handleAddLocalModel}
  onAddRemoteModel={handleAddRemoteModel}
/>
```

Add sheet components in the render (before closing `</View>`):
```tsx
<RemoteModelSheet
  isVisible={remoteModelSheetVisible}
  onDismiss={() => setRemoteModelSheetVisible(false)}
/>
<ServerDetailsSheet
  isVisible={serverDetailsSheetVisible}
  onDismiss={() => {
    setServerDetailsSheetVisible(false);
    setSelectedServerId(null);
  }}
  serverId={selectedServerId}
/>
```

Update ModelCard rendering to pass server details handler (line 321-325):
```tsx
<ModelCard
  model={subItem}
  activeModelId={activeModelId}
  onOpenSettings={() => handleOpenSettings(subItem)}
  onOpenServerDetails={handleOpenServerDetails}
/>
```

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
npx tsc --noEmit 2>&1 | head -30
```

---

### Step 6: ModelCard — Server Link + Remote Delete Flow

**Files**: `src/screens/ModelsScreen/ModelCard/ModelCard.tsx`, `src/screens/ModelsScreen/ModelCard/styles.ts`
**Status**: PENDING

**Change**:

**6a. `ModelCard.tsx`**
- [ ] Add `onOpenServerDetails?: (serverId: string) => void` prop to `ModelCardProps` interface
- [ ] Add tappable "Server: name" link in the remote model card (below the model name, in `headerRight` area)
- [ ] Modify remote model delete flow to use `serverStore.removeUserSelectedModel()` then `serverStore.removeServerIfOrphaned()`

Add prop:
```typescript
interface ModelCardProps {
  model: Model;
  activeModelId?: string;
  onFocus?: () => void;
  onOpenSettings?: () => void;
  onOpenServerDetails?: (serverId: string) => void; // NEW
}
```

**Server link in header** — Replace the current remote model `sizeInfo` section (lines 600-609) to be tappable:

Current (line 600-609):
```tsx
{isRemoteModel ? (
  <View style={styles.sizeInfo}>
    <Icon source="cloud-outline" size={12} color={theme.colors.secondary} />
    <Text style={styles.sizeInfoText}>
      {model.serverName || 'Remote'}
    </Text>
  </View>
) : ( ... )}
```

New:
```tsx
{isRemoteModel ? (
  <TouchableOpacity
    testID="server-link"
    onPress={() => {
      if (model.serverId && onOpenServerDetails) {
        onOpenServerDetails(model.serverId);
      }
    }}
    style={styles.serverLink}>
    <Icon source="cloud-outline" size={12} color={theme.colors.primary} />
    <Text style={styles.serverLinkText}>
      {model.serverName || 'Remote'}
    </Text>
  </TouchableOpacity>
) : ( ... )}
```

**Remote model delete flow** — Modify `handleDelete` to handle remote models.
Currently remote models don't have a delete button (the `renderActionButtons` for remote models only shows load/offload at line 336-339).

Add a delete button for remote models in `renderActionButtons`:
```tsx
if (isRemoteModel) {
  return (
    <View style={styles.actionButtonsRow}>
      {renderModelLoadButton()}
      <TouchableOpacity
        testID="delete-button"
        onPress={handleRemoteDelete}
        style={styles.iconButton}
        accessibilityRole="button"
        accessibilityLabel={l10n.common.delete}>
        <TrashIcon width={16} height={16} stroke={theme.colors.error} />
      </TouchableOpacity>
    </View>
  );
}
```

Add `handleRemoteDelete`:
```typescript
const handleRemoteDelete = useCallback(() => {
  if (!model.serverId || !model.remoteModelId) return;
  const serverName = model.serverName || 'Remote';
  Alert.alert(
    l10n.common.delete,
    t(l10n.settings.removeRemoteModel, {
      modelName: model.name,
      serverName: serverName,
    }),
    [
      {text: l10n.common.cancel, style: 'cancel'},
      {
        text: l10n.common.delete,
        style: 'destructive',
        onPress: () => {
          // If this is the active model, release it first
          if (isActiveModel) {
            modelStore.manualReleaseContext();
          }
          serverStore.removeUserSelectedModel(model.serverId!, model.remoteModelId!);
          serverStore.removeServerIfOrphaned(model.serverId!);
        },
      },
    ],
  );
}, [model, l10n, isActiveModel]);
```

Note: Import `serverStore` from `'../../../store'` and `t` from `'../../../locales'`. Verify ModelCard is wrapped in `observer()` since it now reads store state reactively via the delete handler.

**6b. `ModelCard/styles.ts`**
- [ ] Add `serverLink` and `serverLinkText` styles

```typescript
serverLink: {
  flexDirection: 'row',
  alignItems: 'center',
  marginRight: 8,
},
serverLinkText: {
  fontSize: 12,
  color: theme.colors.primary,
  marginLeft: 4,
  textDecorationLine: 'underline',
},
```

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
npx tsc --noEmit 2>&1 | head -30
```

---

### Step 7: Settings — Replace CRUD with Read-Only "Connected Servers"

**Files**: `src/screens/SettingsScreen/SettingsScreen.tsx`, `src/screens/SettingsScreen/styles.ts`
**Status**: PENDING

**Change**:

**7a. `SettingsScreen.tsx`**
- [ ] Remove import of `ServerConfigSheet` (line 43)
- [ ] Remove `showServerConfigSheet` and `editingServer` state (lines 88-91)
- [ ] Add `serverDetailsSheetVisible` and `selectedServerId` state
- [ ] Add import of `ServerDetailsSheet`
- [ ] Replace the entire "Remote Servers" Card (lines 1056-1189) with a lightweight "Connected Servers" section
- [ ] Remove `<ServerConfigSheet>` from bottom of render (lines 1337-1344)
- [ ] Add `<ServerDetailsSheet>` component at bottom of render
- [ ] Only show the "Connected Servers" card when `serverStore.servers.length > 0`

New state (replacing lines 88-91):
```typescript
const [serverDetailsSheetVisible, setServerDetailsSheetVisible] = useState(false);
const [selectedServerId, setSelectedServerId] = useState<string | null>(null);
```

New "Connected Servers" section (replacing lines 1056-1189):
```tsx
{/* Connected Servers — only shown when servers exist */}
{serverStore.servers.length > 0 && (
  <Card elevation={0} style={styles.card}>
    <Card.Title title={l10n.settings.connectedServers} />
    <Card.Content>
      <View style={styles.settingItemContainer}>
        {serverStore.servers.map((server, index) => {
          const modelCount = serverStore.getUserSelectedModelsForServer(server.id).length;
          return (
            <React.Fragment key={server.id}>
              {index > 0 && <Divider style={styles.divider} />}
              <TouchableOpacity
                testID={`server-row-${server.id}`}
                onPress={() => {
                  setSelectedServerId(server.id);
                  setServerDetailsSheetVisible(true);
                }}
                style={styles.connectedServerRow}>
                <View style={styles.textContainer}>
                  <Text variant="titleMedium" style={styles.textLabel}>
                    {server.name}
                  </Text>
                  <Text variant="labelSmall" style={styles.textDescription}>
                    {t(l10n.settings.modelsCount, {count: String(modelCount)})}
                  </Text>
                </View>
                <Icon
                  source="chevron-right"
                  size={20}
                  color={theme.colors.onSurfaceVariant}
                />
              </TouchableOpacity>
            </React.Fragment>
          );
        })}
      </View>
    </Card.Content>
  </Card>
)}
```

Replace `<ServerConfigSheet>` at bottom with:
```tsx
<ServerDetailsSheet
  isVisible={serverDetailsSheetVisible}
  onDismiss={() => {
    setServerDetailsSheetVisible(false);
    setSelectedServerId(null);
  }}
  serverId={selectedServerId}
/>
```

**Placement**: The "Connected Servers" card should appear after the "API Settings" card (after line 1054) and before "Cache & Storage Settings" / "Export Options".

**7b. `SettingsScreen/styles.ts`**
- [ ] Remove `emptyServerContainer`, `emptyServerDescription`, `serverActionsRow`, `serverActionButton` styles (no longer needed)
- [ ] Add `connectedServerRow` style

```typescript
connectedServerRow: {
  flexDirection: 'row',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingVertical: 8,
},
```

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
npx tsc --noEmit 2>&1 | head -30
```

---

### Step 8: Remove ServerConfigSheet, Extract Utils, Update Components Index

**Files**: `src/components/ServerConfigSheet/` (DELETE), `src/components/index.ts`
**Status**: PENDING

**Note**: L10n key changes were already done in Step 1b to unblock all other steps.

**Change**:

**8a. Delete `src/components/ServerConfigSheet/`**
- [ ] Delete `src/components/ServerConfigSheet/ServerConfigSheet.tsx`
- [ ] Delete `src/components/ServerConfigSheet/styles.ts`
- [ ] Delete `src/components/ServerConfigSheet/index.ts`
- [ ] Delete `src/components/ServerConfigSheet/__tests__/ServerConfigSheet.test.tsx` (and __tests__ dir)

Note: Extract `isLocalHost()` utility from `ServerConfigSheet.tsx` to a shared location BEFORE deleting. Options:
  - Move to `src/utils/index.ts` or `src/utils/network.ts`
  - Or duplicate inline in `RemoteModelSheet.tsx` (it is only 10 lines)
  
  **Recommendation**: Since `isLocalHost()` is used by both RemoteModelSheet and ServerDetailsSheet, extract to `src/utils/network.ts` and export from `src/utils/index.ts`.

**8b. `src/components/index.ts`**
- [ ] Remove `export * from './ServerConfigSheet';` (line 58)
- [ ] Add `export * from './RemoteModelSheet';`
- [ ] Add `export * from './ServerDetailsSheet';`

**8c. L10n keys** — Already done in Step 1b. Verify no stale references remain after deleting ServerConfigSheet.

**8d. Extract `isLocalHost` utility**
- [ ] Create or add to `src/utils/network.ts`:
```typescript
/**
 * Returns true if the host is a local/LAN address.
 */
export function isLocalHost(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return (
      host === 'localhost' ||
      host.startsWith('127.') ||
      host.startsWith('10.') ||
      host.startsWith('192.168.') ||
      /^172\.(1[6-9]|2\d|3[01])\./.test(host)
    );
  } catch {
    return false;
  }
}
```
- [ ] Export from `src/utils/index.ts`: `export {isLocalHost} from './network';`
- [ ] Import in RemoteModelSheet and ServerDetailsSheet from `../../utils`

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
npx tsc --noEmit 2>&1 | head -30
yarn lint 2>&1 | tail -20
```

---

### Step 9: Mock Store Updates + Unit Tests

**Files**: `__mocks__/stores/serverStore.ts`, existing test files
**Status**: PENDING

**Change**:

**9a. `__mocks__/stores/serverStore.ts`**
- [ ] Add `userSelectedModels` observable array (starts empty)
- [ ] Add mock methods: `addUserSelectedModel`, `removeUserSelectedModel`, `removeServerIfOrphaned`, `getModelsNotYetAdded`, `getUserSelectedModelsForServer`
- [ ] Remove `activeServers` computed
- [ ] Exclude new mock methods from `makeAutoObservable`

```typescript
class MockServerStore {
  servers: ServerConfig[] = [];
  serverModels: Map<string, RemoteModelInfo[]> = observable.map();
  userSelectedModels: Array<{serverId: string; remoteModelId: string}> = [];
  isLoading = false;
  error: string | null = null;
  privacyNoticeAcknowledged = false;

  addServer: jest.Mock;
  updateServer: jest.Mock;
  removeServer: jest.Mock;
  setApiKey: jest.Mock;
  getApiKey: jest.Mock;
  removeApiKey: jest.Mock;
  fetchModelsForServer: jest.Mock;
  fetchAllRemoteModels: jest.Mock;
  testServerConnection: jest.Mock;
  acknowledgePrivacyNotice: jest.Mock;
  addUserSelectedModel: jest.Mock;
  removeUserSelectedModel: jest.Mock;
  removeServerIfOrphaned: jest.Mock;
  getModelsNotYetAdded: jest.Mock;
  getUserSelectedModelsForServer: jest.Mock;

  constructor() {
    makeAutoObservable(this, {
      addServer: false,
      updateServer: false,
      removeServer: false,
      setApiKey: false,
      getApiKey: false,
      removeApiKey: false,
      fetchModelsForServer: false,
      fetchAllRemoteModels: false,
      testServerConnection: false,
      acknowledgePrivacyNotice: false,
      addUserSelectedModel: false,
      removeUserSelectedModel: false,
      removeServerIfOrphaned: false,
      getModelsNotYetAdded: false,
      getUserSelectedModelsForServer: false,
    });
    this.addServer = jest.fn().mockReturnValue('mock-server-id');
    this.updateServer = jest.fn();
    this.removeServer = jest.fn();
    this.setApiKey = jest.fn().mockResolvedValue(undefined);
    this.getApiKey = jest.fn().mockResolvedValue(undefined);
    this.removeApiKey = jest.fn().mockResolvedValue(undefined);
    this.fetchModelsForServer = jest.fn().mockResolvedValue(undefined);
    this.fetchAllRemoteModels = jest.fn().mockResolvedValue(undefined);
    this.testServerConnection = jest.fn().mockResolvedValue({ok: true, modelCount: 3});
    this.acknowledgePrivacyNotice = jest.fn();
    this.addUserSelectedModel = jest.fn();
    this.removeUserSelectedModel = jest.fn();
    this.removeServerIfOrphaned = jest.fn();
    this.getModelsNotYetAdded = jest.fn().mockReturnValue([]);
    this.getUserSelectedModelsForServer = jest.fn().mockReturnValue([]);
  }
}
```

**9b. Update Existing Tests — SUBSTANTIAL REWRITE needed for ServerStore tests**

The ServerStore test file (`src/store/__tests__/ServerStore.test.ts`) has ~35 references to `isActive` across 498 lines. This is NOT a quick find-and-replace:
- [ ] Remove `isActive` from ALL `addServer()` calls throughout the file
- [ ] Delete the entire `activeServers` computed test block
- [ ] Update `fetchModelsForServer` tests to remove the `isActive` guard check
- [ ] Update `fetchAllRemoteModels` test — it should fetch for ALL servers (not just active)
- [ ] Add new test blocks for: `userSelectedModels`, `addUserSelectedModel`, `removeUserSelectedModel`, `removeServerIfOrphaned`, `getModelsNotYetAdded`, `getUserSelectedModelsForServer`
- [ ] Add test: `removeServer` also cleans up `userSelectedModels` entries
- [ ] Run full test suite and fix any other failures from `isActive` removal

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727
yarn test 2>&1 | tail -30
```

---

## Test Requirements

### Unit Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| ServerStore: addUserSelectedModel prevents duplicates | `src/store/__tests__/ServerStore.test.ts` | MUST | PENDING |
| ServerStore: removeUserSelectedModel removes entry | `src/store/__tests__/ServerStore.test.ts` | MUST | PENDING |
| ServerStore: removeServerIfOrphaned removes server with no models | `src/store/__tests__/ServerStore.test.ts` | MUST | PENDING |
| ServerStore: removeServerIfOrphaned keeps server with models | `src/store/__tests__/ServerStore.test.ts` | MUST | PENDING |
| ServerStore: getModelsNotYetAdded filters correctly | `src/store/__tests__/ServerStore.test.ts` | MUST | PENDING |
| ServerStore: removeServer also removes userSelectedModels | `src/store/__tests__/ServerStore.test.ts` | MUST | PENDING |
| ModelStore: remoteModels returns only user-selected | `src/store/__tests__/ModelStore.test.ts` | MUST | PENDING |
| RemoteModelSheet: renders URL input | `src/components/RemoteModelSheet/__tests__/RemoteModelSheet.test.tsx` | SHOULD | PENDING |
| ServerDetailsSheet: renders server info | `src/components/ServerDetailsSheet/__tests__/ServerDetailsSheet.test.tsx` | SHOULD | PENDING |
| FABGroup: shows three options | `src/screens/ModelsScreen/FABGroup/__tests__/FABGroup.test.tsx` | SHOULD | PENDING |
| ModelCard: tappable server link for remote models | `src/screens/ModelsScreen/ModelCard/__tests__/ModelCard.test.tsx` | SHOULD | PENDING |

### Manual Testing
- [ ] Open Models screen, tap FAB, verify "Add Remote Model" option appears
- [ ] Tap "Add Remote Model", enter a valid LM Studio URL, verify auto-probe and model list
- [ ] Add a model, verify it appears in the model list with cloud icon and server name
- [ ] Tap server name on model card, verify ServerDetailsSheet opens
- [ ] Go to Settings, verify "Connected Servers" section shows (if servers exist)
- [ ] Tap server in Settings, verify ServerDetailsSheet opens
- [ ] Delete a remote model, verify it disappears from the list
- [ ] Delete last model from a server, verify server is cleaned up
- [ ] Load a remote model, verify chat works with streaming
- [ ] Verify local models still work perfectly

### Visual Confirmation (Visual Confirmation = YES)

```json
[
  {"prompt": "Go to Models screen, tap FAB", "name": "models-fab-remote-option", "description": "FAB should show 'Add Remote Model' as a third option"},
  {"prompt": "Open Add Remote Model sheet", "name": "remote-model-sheet-empty", "description": "Sheet should show URL field, privacy notice on first use"},
  {"prompt": "Go to Settings screen", "name": "settings-connected-servers", "description": "Settings should show 'Connected Servers' section if servers exist"}
]
```

---

## Coding Standards

### Testing Infrastructure (CRITICAL)
```
# Read these BEFORE writing tests:
/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727/jest/setup.ts
/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727/jest/test-utils.tsx
/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260219-1727/__mocks__/stores/

# DO NOT mock stores inline - they're globally mocked
# Use runInAction() for MobX state changes
# Import render from jest/test-utils, NOT @testing-library/react-native
```

### Patterns to Follow
- **State**: MobX `makeAutoObservable`, `runInAction`
- **Components**: Functional + `observer()` HOC
- **Sheets**: Use `Sheet` component with `Sheet.ScrollView`, `Sheet.Actions` (see HFTokenSheet)
- **Secure Input**: `PaperTextInput.Icon` with `EyeIcon`/`EyeOffIcon` toggle (see HFTokenSheet lines 152-164)
- **Styles**: Separate `styles.ts` with `createStyles(theme: Theme)` factory

### Commit Format
```
type(scope): subject
```

Types: `feat`, `fix`, `docs`, `chore`

---

## Reference Code

### Pattern Example: Sheet with Secure Input (HFTokenSheet)
**File**: `src/components/HFTokenSheet/HFTokenSheet.tsx`
**Lines**: 109-166
```typescript
// Sheet structure:
<Sheet isVisible={isVisible} onClose={onDismiss} title={...} snapPoints={['60%']}>
  <Sheet.ScrollView contentContainerStyle={styles.container}>
    {/* Content */}
    <TextInput
      secureTextEntry={secureTextEntry}
      right={
        <PaperTextInput.Icon
          icon={({color}) =>
            secureTextEntry ? (
              <EyeIcon width={24} height={24} stroke={color} />
            ) : (
              <EyeOffIcon width={24} height={24} stroke={color} />
            )
          }
          onPress={toggleSecureEntry}
        />
      }
    />
  </Sheet.ScrollView>
  <Sheet.Actions>
    <View style={styles.buttonsContainer}>
      <Button mode="contained" onPress={handleSave} loading={isSaving}>
        Save
      </Button>
    </View>
  </Sheet.Actions>
</Sheet>
```

### Pattern Example: FAB Speed-Dial Actions
**File**: `src/screens/ModelsScreen/FABGroup/FABGroup.tsx`
**Lines**: 39-63
```typescript
const actions = useMemo(
  () => [
    {
      testID: 'hf-fab',
      icon: HFIcon,
      label: l10n.models.buttons.addFromHuggingFace,
      accessibilityLabel: l10n.models.buttons.addFromHuggingFace,
      style: styles.actionButton,
      onPress: () => { onAddHFModel(); },
    },
    {
      testID: 'local-fab',
      icon: 'folder-plus',
      label: l10n.models.buttons.addLocalModel,
      // ...
    },
    // Add third action here
  ],
  [l10n, onAddHFModel, onAddLocalModel, styles.actionButton],
);
```

### Pattern Example: Remote Model in ModelCard Header
**File**: `src/screens/ModelsScreen/ModelCard/ModelCard.tsx`
**Lines**: 600-609
```typescript
// Current (will be modified):
{isRemoteModel ? (
  <View style={styles.sizeInfo}>
    <Icon source="cloud-outline" size={12} color={theme.colors.secondary} />
    <Text style={styles.sizeInfoText}>
      {model.serverName || 'Remote'}
    </Text>
  </View>
) : ( ... )}
```

### Pattern Example: MobX Store Persistence
**File**: `src/store/ServerStore.ts`
**Lines**: 26-37
```typescript
makeAutoObservable(this, { serverModels: observable });
makePersistable(this, {
  name: 'ServerStore',
  properties: ['servers', 'privacyNoticeAcknowledged'], // Add 'userSelectedModels'
  storage: AsyncStorage,
}).then(() => {
  this.fetchAllRemoteModels();
});
```

---

## Dependencies

### Blocked By
- [x] TASK-20260219-1727 backend/engine layer (DONE — already committed)

### Blocks
- [ ] None

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Debounced auto-probe with apiKey race condition | Medium | Medium | Store apiKey in ref; re-probe on apiKey blur; treat (url, apiKey) as pair |
| Removing `isActive` breaks existing test assertions | Low | Low | This is a draft PR — no user data at risk. Fix tests in Step 9 |
| Sheet stacking issues (RemoteModelSheet opens ServerDetailsSheet) | Low | Medium | These sheets are mutually exclusive — only one opens at a time |
| L10n key changes break other language files | Low | Medium | Only `en.json` is edited — other languages managed by Weblate, not affected by key removals in unreleased feature |
| FAB with 3 actions may be cramped on small screens | Low | Low | React-native-paper FAB.Group handles scrolling/positioning natively |

---

## Open Questions

### For Human
- None — amendment already approved

### Resolved
- Server-centric vs model-centric UX -> Model-centric (decided by UX review)
- Whether to keep `isActive` toggle -> No, remove it (decided by amendment)

---

## Agent Reports

### Planner Report
```
Research completed 2026-02-24. All backend/engine code is already implemented
and committed. This amendment touches only UI layer:
- 2 new components (RemoteModelSheet, ServerDetailsSheet)
- 3 modified screens (ModelsScreen, SettingsScreen, ModelCard)
- 1 modified store (ServerStore: new fields/methods)
- 1 modified computed (ModelStore.remoteModels)
- 1 deleted component (ServerConfigSheet)
- L10n key updates

No native changes. No dependency additions. Follows existing Sheet and
component patterns throughout.
```

---

## Changelog

| Date | Agent/Human | Change |
|------|-------------|--------|
| 2026-02-24 | human | Approved UX amendment (model-centric redesign) |
| 2026-02-24 | planner | Created implementation plan |
| 2026-02-24 | story-critic | Reviewed: HAS_CONCERNS (6 concerns, 3 observations) |
| 2026-02-24 | human + external review | Applied fixes: probe (url,apiKey) pair, drop phase state, static imports, smart server name, chip offline handling, l10n to Step 1, sheet state reset, substantial test rewrite note, scoped out Flow 5 (auth recovery in chat) as follow-up |
