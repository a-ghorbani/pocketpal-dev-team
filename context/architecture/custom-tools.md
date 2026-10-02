# Custom HTTP Tools

## Purpose

User-authored HTTP tools: the persisted definition, how a request is built and a response trimmed, where secrets live, and the manager and editor UI. The runner gates that make them safe to call belong to `agent-runner.md`; how they reach the registry and a Pal belongs to `pals-and-talents.md`; the confirmation sheet and the expandable chip belong to `chat-flow.md`; the Settings entry point belongs to `settings.md`.

## Code map

| Path | Role |
| --- | --- |
| `src/services/customTools/types.ts` | `CustomToolDefinition`, `CustomToolDraft`, `CUSTOM_TOOL_ERROR_CODES`, timeout and response-cap bounds |
| `src/services/customTools/validator.ts` | the single zod-backed validator; placeholder helpers (`placeholdersIn`, `templateSlots`) |
| `src/services/customTools/toolStatus.ts` | `secretNames`, `toolStatus`, `isNonLoopback` |
| `src/services/customTools/requestBuilder.ts` | pure `(def, args, secrets) → request | failure`; positional encoding |
| `src/services/customTools/responsePipeline.ts`, `jsonPath.ts`, `redact.ts` | the fixed response pipeline, the JSONPath subset, secret redaction |
| `src/services/customTools/HttpToolEngine.ts` | the `TalentEngine` implementation; the whole trust boundary |
| `src/services/customTools/access.ts` | `CustomToolAccess`, interface only, so the engine reaches no store |
| `src/services/talents/builtinTalentNames.ts` | leaf list of built-in names, equality-tested against `registerDefaultTalents` |
| `src/store/CustomToolStore.ts` | persisted definitions, CRUD, import/export, Keychain secrets |
| `src/screens/CustomToolsScreen/`, `src/components/CustomToolSheet/` | manager list and editor sheet |
| `docs/custom-tools/` | stdlib-only Termux demo server, importable tool JSON, setup guide |

## How it works

`CustomToolStore` persists `{tools}` through `makePersistable` on AsyncStorage, set up only after the constructor has read the existing blob and copied it aside if it was unreadable. The store carries no schema version: nothing read one, so an old blob's `schemaVersion` is ignored and dropped on the next write. `talents/index.ts` maps every definition whose `toolStatus` is `ok` to an `HttpToolEngine` and registers it through the source bridge, so the runner and chat UI never learn a tool's origin.

One call runs: read secrets for this call → `buildRequest` → `fetch` → redirect-origin check → size check → status check → `runResponsePipeline` (`extract` → `fields` → `maxItems` → `template` → redact → `maxChars` → `wrapUntrusted`) → `{type:'text', summary}`. Every failure becomes a `type:'error'` result; nothing throws.

The editor writes the definition through `addTool` / `updateTool`, then calls `setSecrets` once. The manager lists every stored tool, badging the ones the bridge will not register.

## Contracts and invariants

- **The app never writes a secret into anything the model or the screen can read**: not `summary`, `responseContent`, `errorMessage`, `toolCalls`, the confirmation sheet, a log line, MobX state, AsyncStorage, or an export file. Secret values live only in Keychain, service `pocketpal-custom-tool-<id>`, one JSON password per tool.
- **Secrets go only to the definition's literal origin, in a query value or the `Authorization` header.** The validator refuses any other placement and `buildRequest` refuses it again. This is narrower than "headers and query" on purpose: on Android OkHttp strips only `Authorization` when a redirect leaves the origin and re-sends every other custom header, so a secret in a custom header would survive a redirect off-host.
- **Server-echoed text is redacted** against each secret's raw and `encodeURIComponent` form, on the pipeline output and on every error message. Redaction runs before truncation, so a cut cannot expose half a credential. Stored values are at least four characters, which is what makes the rule safe to apply blindly.
- **Server text never reaches the model on an error path.** An error's `summary` is engine-authored (`HTTP 500`, `network error`, `invalid JSON`); a redacted excerpt of at most 200 characters goes to `errorMessage`, which the runner does not copy into `responseContent` and only `ToolErrorBlock` renders.
- **Encoding is decided by position.** Path placeholders are `encodeURIComponent`'d and a segment of `.` or `..` is refused; query values are substituted then encoded whole, and an absent optional whole-value entry drops its key; header values are raw and a resolved CR or LF is refused; a body placeholder must be a whole string value and is substituted as a JSON value, never interpolated. Scheme, userinfo, host and port are literal.
- **Hydration never deletes.** A persisted entry that fails the current validator, or whose name a built-in or an earlier entry already holds, stays in `tools`, unregistered and badged. `removeTool` is the only path that deletes a definition, and it resets the Keychain entry on the same per-id chain *before* dropping the definition, so an interrupted delete leaves a definition without secrets rather than secrets without a definition.
- **A blob that cannot be read as `{tools[]}` is copied verbatim to `custom-tools-unreadable-<timestamp>` before `makePersistable` is called**, and nothing deletes that copy. The ordering is the guarantee, not a hope: persistence setup is itself the write that would overwrite the blob, so the backup is awaited first, at construction, with no user action required. A failed backup write is logged and hydration still proceeds. Deferring setup by one AsyncStorage read is invisible: consumers are `observer` components and none gates on `isHydrated`. Its Keychain entries survive as orphans by design.
- **A value the model can inflate is clamped on every path into the store.** `validateDefinition` clamps `maxItems` (1–100) and `maxChars` (1–20000) exactly as it clamps `timeoutMs`; an absent or non-finite value omits the key so the pipeline default applies. These caps are replayed on every later turn of a session and nothing windows history, so an unclamped value is a permanent per-session context tax. Hydration does not re-validate — the next editor save clamps a stale blob.
- **A secret the user removed is gone from the Keychain.** `updateTool` prunes every stored name the saved definition no longer references, on that tool's per-id chain so it cannot interleave with the same save's `setSecrets`. The editor offers a Clear per referenced secret, enabled only when the name is actually stored, wired to `setSecrets(id, {name: null})` — the store's only delete signal, and unreachable otherwise because empty drafts are filtered out of the save patch.
- **`setSecrets` is the only secret writer**: one whole-patch write per save, serialised per tool id with `removeTool`, so two saves cannot lose an update. It rejects the whole patch, writing nothing, if any value is under four characters or contains CR or LF.
- **Import forces `requiresConfirmation: true`** whatever the file says, assigns fresh ids and carries no secrets. It normalises `response.wrapUntrusted` on the same way, so a shared file cannot ship a tool whose response reaches the model unwrapped. Export carries no id and no value, only the literal placeholders.
- **The engine imports no React, MobX or store.** `access.ts` is interface-only and consumed with `import type`, so nothing from `src/store/` enters its require tree; the factory lives in `services/talents/index.ts`. A require-tree test enforces this.
- **`extract` is a hand-written parser** for `$`, `.key`, `[n]` and `[*]`, with no `eval`, `Function` or library, because it parses an untrusted response.
- **Every success path is wrapped by `wrapUntrusted`** unless the user turned wrapping off for that tool.

## Traps and decisions

- **On Android `Response.url` is the request URL, not the final one.** `NetworkingModule` passes the request `url` straight through, so the off-host redirect check can only ever fire on iOS. An Android redirect body therefore reaches the model, wrapped as untrusted; no secret travels with it. The guard carries a comment saying where it stops working, and `docs/custom-tools/README.md` states the limitation for tool authors. Re-verify on any OkHttp upgrade or if the app ever installs a client factory.
- **zod rejects a MobX observable outright.** Definitions reach the validator straight from store state, so `validateDefinition` parses a plain JSON snapshot of its input. Without that, every live tool validates as malformed and none is ever registered — a failure that looks like "the feature does nothing" rather than an error.
- **A timeout that fires after the request reached the server does not undo it.** A non-idempotent call can have taken effect; the outcome is still reported as timed out.
- **Redaction recognises only the raw and percent-encoded forms.** A server that echoes a credential base64-encoded, or in another encoding, defeats it.
- **Validator failures are codes, never English.** The module is pure and cannot reach `L10nContext`, so the UI resolves each code to copy; a test asserts every declared code has an entry, so an unmapped code fails CI instead of printing a raw code on screen. The editor renders each code on the field that caused it, through the shared `TextInput`'s `error` / `helperText`, and focuses the first offender in a fixed field order so the rejection is never off-screen. A code with no field of its own (`shape_invalid`, `secret_placement`) still renders in the sheet-level list, so nothing is swallowed. The editor validates the draft itself purely to place the messages — the store validates again and remains the only writer.
- **A non-loopback host is allowed but flagged**, in the editor and as a manager badge, because anything the model sends then leaves the device.

## Verification

- Unit: `src/services/customTools/__tests__/` (validator, status helpers, request builder, response pipeline and JSONPath, engine incl. the require-tree purity check, and the shipped example), `src/store/__tests__/CustomToolStore.test.ts`, `src/components/CustomToolSheet/__tests__/`, `src/screens/CustomToolsScreen/__tests__/`.
- `python3 -m py_compile docs/custom-tools/termux-server.py` keeps the demo server runnable.
- By hand: run the demo server, import `docs/custom-tools/example-tools.json`, enable a tool on a Pal, and approve a call. Then point a tool at a redirecting endpoint and confirm no `Authorization` reaches the follow-up.
