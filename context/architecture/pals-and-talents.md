# Pals & Talents

## Purpose

What a Pal carries for tool use (`pact`, `greeting`), what a Talent is (engine plus optional UI), how a Pal opts into tools, and the execution boundary engines respect, including the search talents' trust rules. Elsewhere: the agent loop (`agent-runner.md`), rendering and persistence of tool outcomes (`chat-flow.md`), search settings and consent UI (`settings.md`).

## Code map

| Path | Role |
| --- | --- |
| `src/types/pal.ts` | `Pal`, `TalentRef {name, necessity}`, `pact`, `greeting` |
| `src/services/talents/types.ts` | `TalentEngine`, `TalentResult` union, `ToolDefinition`, `SystemPromptContext` |
| `src/services/talents/index.ts` | `registerDefaultTalents`, `deriveToolSchemas`, `collectSystemPromptFragments`, `createSearchAccess`, `createCustomToolAccess`; attaches the custom source; narrow barrel |
| `src/services/talents/talentSource.ts` | `attachTalentSource`: the MobX bridge from a `TalentSource` to the registry, returning a disposer |
| `src/services/talents/builtinTalentNames.ts` | leaf list of built-in names, imported by the custom-tool validator (`custom-tools.md`) |
| `src/services/talents/TalentRegistry.ts`, `TalentUIRegistry.ts`, `registerTalentUIs.ts` | name-keyed engine and UI registries; UI registration is kept out of the engine module graph |
| `src/services/talents/*Engine.ts` | built-ins: `render_html`, `calculate`, `datetime`, `web_search`, `read_url` |
| `src/services/talents/readUrlAllowlist.ts` | run-scoped `read_url` exfiltration allowlist (`seedReadUrlAllowlist`) |
| `src/services/talents/untrustedContent.ts` | `wrapUntrusted`, which puts web text in nonce-delimited markers |
| `src/services/talents/searchAccess.ts` | `SearchAccess` interface injected into search engines |
| `src/services/search/` | provider adapters (`providers/`), `searchBudget.ts`, `readWithDefaultReader` (`r.jina.ai`) |
| `src/store/SearchProviderStore.ts` | provider, result count, consent, Keychain keys (`search_provider_service_<id>`) |
| `src/store/ChatSessionStore.ts` | `resolveCompletionSettings`, the PACT to `tools` derivation |
| `src/utils/systemPromptResolver.ts` | `assembleMessages`: one leading system message |
| `src/components/TalentSurface/TalentSurface.tsx` | per-call render dispatch |
| `src/components/PalsSheets/PalSheet.tsx`, `TalentSection.tsx`, `GreetingSection/` | in-app Pal editor |
| `src/database/models/LocalPal.ts`, `src/repositories/PalRepository.ts` | `local_pals.pact` / `greeting` JSON columns; `getPalByPalshubId` |
| `src/store/PalStore.ts` | the PalsHub install path: `insertPalsHubPalOnce`, `downloadPalsHubPal`, `installOwnedPal`, `applyOwnedPalContent` |
| `src/utils/exportUtils.ts`, `importUtils.ts` | Pal export/import round-trip of `pact` and `greeting` |

## How it works

`registerDefaultTalents()` fills `talentRegistry` at `PalStore` init and lazily from `deriveToolSchemas` / `collectSystemPromptFragments`. `TalentSurface` calls `registerDefaultTalentUIs()` at module load.

`ChatSessionStore.resolveCompletionSettings` layers defaults, then global settings, then Pal `completionSettings`. It then sets `tools = deriveToolSchemas(pact.talents names)` when that list is non-empty. When the session uses `settingsSource === 'custom'`, the session's params replace the result but the PACT `tools` are re-applied.

`useChatSession.prepareCompletion` then:
- collects talent `systemPromptFragment`s for the session's tool names;
- folds them into one system message with `assembleMessages`;
- reseeds the `read_url` allowlist with `seedReadUrlAllowlist`.

The run dispatches through `talentLookup` with `allowedTalentNames` from `pact.talents` (see `agent-runner.md`). `TalentSurface` renders each settled call: `ToolErrorBlock` for an error, else a registered `TalentUI.renderResult` (plus `ToolMetricsFooter` when `call.metrics` is set), else `ToolUsedChip` with metrics inline. `PendingIndicator` covers calls with no outcome yet.

## Contracts and invariants

- **PACT is the single opt-in.** Advertised tools are `deriveToolSchemas(pact.talents.map(t => t.name))`. The runner dispatches only names in that same list. Engines are global, and there is no Pal-id coupling (`TalentRegistry`).
- **One name, three places.** `TalentEngine.name` is the tool name, the `talentUIRegistry` key, and the `TalentRef.name`. `register()` silently replaces a same-name entry, and nothing warns about collisions. That is why a non-builtin source never registers a name it does not already own: built-ins claim theirs first, and the bridge skips any name already taken, so a user tool can never shadow `calculate`.
- **A source owns the names it registers.** `attachTalentSource` runs one fire-immediately MobX reaction over `source.engines()`; each run unregisters the owned names no longer produced, then registers the current ones. It returns a disposer that stops the reaction and gives up every owned name, and `resetRegisteredFlag()` calls it — without that, a test reset stacks a second reaction and leaves a stale owned-name set. `TalentRegistry.unregister(name)` exists for this.
- **Import direction is one-way:** `talents/index.ts` → `CustomToolStore` → the custom-tool validator → `builtinTalentNames.ts`, a leaf with no imports. The store and the validator never import `services/talents/index` or `store/index`, which keeps the graph acyclic under Babel's CommonJS interop.
- **`TalentSection` lists whatever is registered,** re-read each time the sheet mounts, so a custom tool appears beside the built-ins with no edit: `title` falls back to the engine name and the description to `toToolDefinition().function.description` when l10n has no entry.
- **Unknown PACT names are dropped silently.** `deriveToolSchemas` filters by what is registered, so a Pal naming a talent this build lacks runs as plain chat (forward-compat for PalsHub Pals).
- **Custom session settings never strip PACT tools.** `resolveCompletionSettings` re-applies them after the `custom` layer. Generation params and tool availability are separate concerns.
- **Engine boundary.** `execute(args) → Promise<TalentResult>` never touches React, MobX or stores. Network and Keychain access are allowed behind the boundary, but store state reaches search engines only through the `SearchAccess` passed to their constructors, built in `createSearchAccess`. `talents/index.ts` is the only talents file importing a store, and it now imports `CustomToolStore` there too, behind `createCustomToolAccess`. Output leaves only as a `TalentResult`, and `summary` is what the model sees. `execute` takes an optional second argument, a `{signal}` context, passed only to engines that declare `timeoutMs` (`agent-runner.md`).
- **At most one system message, and it comes first.** Talent fragments are folded into the Pal prompt by `assembleMessages`, joined with a blank line, Pal prompt first. A talent never emits its own system message, and strict chat templates `raise_exception` on a second one. The stored Pal prompt is never modified. `__DEV__` logs a violation, and `useChatSession` / `systemPromptResolver` tests assert exactly one.
- **Search consent is load-bearing at execution.** Both search engines return an error result unless `canSearch()`, which requires `hasConsentedToSearch` and a configured key. The Settings disclosure is not the only gate.
- **`read_url` order of checks.** First, a plain `http(s)` URL with no userinfo. Second, `canSearch`. Third, the allowlist. Then fetch the fragment-stripped canonical URL through the provider's native `read` (Exa only) or else `readWithDefaultReader` (`r.jina.ai`, which the consent disclosure names).
- **Allowlist trust sources.** URLs count only from user-written message text, `{type:'search'}` hit URLs from persisted `step.toolOutcomes` (seeded at run start), and live hits (`WebSearchEngine` calls `allowReadUrls`). Assistant text and tool-message text never count. Matching is exact on the canonical URL, so query or path mutation fails. Only `seedReadUrlAllowlist` / `isReadUrlAllowed` are exported.
- **All retrieved web text is wrapped by `wrapUntrusted`** before it reaches the model: the search menu and the page body. Literal marker strings in the page are neutralised.
- **The search token ceiling is charged against the rendered bullet.** `budgetHits` takes the model-facing renderer, because counting raw fields under-counts markdown and indentation and leaks past the cap. Engines read their own `recommendedContextTokens` as that ceiling.
- **Outside engines, `recommendedContextTokens` is read only by `usePalLoadHint` and `BannerRow.deriveHeavyTalentName`;** it never moves a banner threshold.
- **`web_search` returns `{type:'search'}`,** with structured `results[]` for `WebSearchTalentUI` and the wrapped menu as `summary`. The UI never parses model-facing text.
- **PalsHub install path.** Every PalsHub Pal enters `local_pals` through `PalStore.insertPalsHubPalOnce`: a per-`palshub_id` promise chain that checks the DB (not the in-memory `pals`) and returns an existing row instead of inserting a second one. `downloadPalsHubPal` (library, with its ownership check) and `installOwnedPal` (store purchases, no ownership check, `in-app-purchase.md`) both use it; `PalStore.ready` is the `initialize()` promise that installs wait on.
- **A store purchase never writes an empty prompt.** `installOwnedPal` throws without `system_prompt`, and `applyOwnedPalContent` skips the prompt fields when the new content has none.
- **A creator update never overwrites the user's prompt edit.** `applyOwnedPalContent` rewrites name, description, thumbnail, pact, greeting, default model and generation settings, but `systemPrompt` / `originalSystemPrompt` / `parameterSchema` only when the local prompt's hash (`promptHash`: `hashCode:length`) equals the last applied hash (or already equals the new prompt). User `parameters` survive for keys the new schema keeps.
- **The editor always writes `necessity: 'required'`** (`PalSheet.onSubmit`). `'optional'` arrives only through import or PalsHub (wire `required` maps strictly, `=== true`, in `PalStore.createLocalPalFromPalsHub`). Nothing enforces `necessity`, so a future gate must default to not blocking. `onSubmit` always passes `pact` (possibly `{talents: []}`) because `PalRepository` skips `undefined` updates.

## Traps and decisions

- **`CalculateEngine` pins `expr-eval` to `{allowMemberAccess: false}`.** This blocks the `(0).constructor.constructor(...)` escape on non-Hermes runtimes. Engine purity is not sandbox safety: an engine that wraps an untrusted-input parser must pick the locked-down configuration itself.
- **Component tests and the registration bridge see two different store instances.** `jest/setup.ts` replaces the `src/store` barrel with mocks, while `services/talents/index.ts` deep-imports `store/CustomToolStore`, so the bridge reads the real store even where a component test has mocked the barrel. The deep import is deliberate — the barrel would close a cycle (`store/index` → `ChatSessionStore` → `services/talents/index`) — and it follows this file's own precedent, which deep-imports `SearchProviderStore` the same way. The consequence is that the mock store's `okTools` must reproduce the real getter's filtering rather than return every tool; a test now pins that, because nothing else read the mock's value and the drift was invisible.
- **Talent-internal mutable state assumes one agent run at a time.** This covers the search-hit cache and the `read_url` allowlist. If concurrent runs ever land, thread a run-scoped context through `execute`.
- **Result count comes from settings, not a tool parameter**, so the model cannot inflate injected tokens. Defaults are `brave` with 5 results (range 1–8, `SearchProviderStore`). Brave with 5 results grounded small on-device models best.
- **Search errors steer the model in-band.** Every failure is an error result; the no-results summary says to shorten the query, a blocked `read_url` says to run `web_search` first.
- **Grounding lives on the engine.** `WebSearchEngine.systemPromptFragment` adds today's date, search-first, a tool budget of `maxToolTurns − 1`, answer-from-results-and-cite-URLs, and "say so rather than guess"; it mentions `read_url` only when that talent is active. `read_url` has no fragment, so a Pal with only `read_url` gets no grounding.
- **The hit cache key excludes the BYOK key** (a secret must never be a map key), so invalidation is explicit: `SearchProviderStore` calls `resetSearchCache` on provider, key and consent changes. A new store setter that affects results must do the same.
- **The greeting is UI-only and gated on a loaded model.** It is never persisted or sent to the model. `ChatView` renders the greeting bubble and suggested prompts only when `modelStore.activeModelId` is set.
- **`TalentUI.renderPending` is deprecated and never called.** `PendingIndicator` owns in-flight UX. New UIs must not implement it.
- **Two registries rather than one map,** so text-only talents (`calculate`, `datetime`, `read_url`) need no UI plumbing and engine consumers never load the UI tree.
- **The prompt hash, not `isSystemPromptChanged`, detects user edits.** No editor path sets that flag, so it cannot tell a user's edit from the creator's text.
- **Edits to `pact` apply on the next `resolveCompletionSettings`.** An in-flight run keeps the `tools` / markers it captured at submit.

## Verification

- Unit: `src/store/__tests__/PalStore.install.test.ts` (one row for concurrent installs, no ownership check, prompt-hash rule), `src/services/talents/__tests__/` (engines, registries, allowlist, untrusted wrapping, fragments), `src/services/search/__tests__/` and `providers/__tests__/`, `src/components/TalentSurface/__tests__/`, `src/components/PalsSheets/__tests__/`, `src/utils/__tests__/systemPromptResolver.test.ts`, `src/hooks/__tests__/useChatSession.test.ts` (single-system-message assertions).
- e2e: `e2e/specs/features/talent-tool-use.spec.ts` (`render_html` end to end) and `e2e/specs/features/pal-greeting.spec.ts`.
- By hand: enable `web_search` on a Pal without consenting in Settings. The call must return an error result, not a fetch.
