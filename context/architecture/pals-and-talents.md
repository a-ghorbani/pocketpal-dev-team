# Pals & Talents

**Purpose**: cumulative architecture truth for **what a Pal is**, **what a Talent
is**, and how a Pal opts into tool use. The wire-format / agent-loop / rendering
side lives in `chat-flow.md`; this doc owns the configuration surface and the
execution boundary.

Convention:

- **(C)** = current behaviour, documented from code
- **(D)** = decision (was an open question, now resolved)

---

## 1. Data model

### 1a. Pal — talent-relevant fields

The `Pal` type (`src/types/pal.ts:43`) carries the usual identity / prompt /
model / parameter fields that this doc does not own. The two fields that exist
*because of* the talent system:

```
Pal
  pact?     : { talents: TalentRef[] }            // (C) declares tool use
  greeting? : { text, suggestedPrompts? }         // (C) UI scaffolding only

TalentRef (src/types/pal.ts:5)
  name      : string                              // matches a TalentEngine.name
  necessity : 'required' | 'optional'             // see D1
```

### 1b. Talent

```
TalentEngine (src/services/talents/types.ts:26)   // execute side
  name : string                                   // also used as tool name
  execute(args)        → Promise<TalentResult>    // tool body — pure, no
                                                  //   React/MobX/store (I4)
  toToolDefinition()   → ToolDefinition           // OpenAI function schema
  recommendedContextTokens? : number              // declarative hint, see I6

TalentUI    (src/services/talents/TalentUIRegistry.ts:5)  // render side
  name           : string
  renderResult?(result)  → ReactNode              // visual block per outcome
  renderPending?()       → ReactNode              // (C) deprecated, see D5

TalentResult                                      // discriminated union
  { type: 'html',   html, title?, summary }
  { type: 'text',   summary }
  { type: 'search', query, results[], summary }   // results: {title,url,snippet}[]
  { type: 'audio',  audioUri, summary }
  { type: 'error',  summary, errorMessage }

AgentToolCall  (src/utils/types.ts:35)            // one call in a step
  id, type:'function', function:{ name, arguments },
  metrics? : { tokens, durationMs }               // generation cost,
                                                  //   attached by the runner
                                                  //   when tool-call tokens
                                                  //   were observed; rendered
                                                  //   post-hoc by the talent
                                                  //   surface (§5b)
```

`metrics` measures **generation** (how much work the model did to produce
the call's arguments JSON), NOT **execution** (how long the engine took).
Engines stay pure — they neither produce nor read metrics.

**Built-in engine specifics**:

- `CalculateEngine` pins its `expr-eval` parser to
  `{allowMemberAccess: false}` (`CalculateEngine.ts:7`). This blocks the
  `(0).constructor.constructor("…")()` sandbox-escape on RN runtimes where
  Hermes is disabled and a JIT is reachable through the Function constructor.
  Math operators and the standard library still resolve without member
  access. Engine purity (I4) is necessary for sandbox safety but not
  sufficient on its own — engines that wrap untrusted input parsers MUST
  pick the locked-down configuration explicitly.

- `WebSearchEngine` (`web_search`) and `ReadUrlEngine` (`read_url`) are the
  internet-search talents (BYOK, provider-agnostic). The model writes
  the query / URL; result count comes from settings (not a tool parameter, so
  the model cannot inflate the injected tokens). `read_url` is text-only
  (no `TalentUI` — falls through I3 to `ToolUsedChip`) and resolves to a
  `{type:'text'}` page on success. `web_search` resolves to a `{type:'search'}`
  result carrying structured `results[]` for `WebSearchTalentUI` AND the wrapped
  menu as `summary` (the model-facing payload — `summary` behaves exactly like a
  `{type:'text'}` result for the runner). The `summary` menu is markdown: a
  `## Web search results for "…" (retrieved YYYY-MM-DD)` header, then one bullet
  per hit — `- **title**` with an italic `*(publishedAt)*` suffix when present,
  the snippet indented on the next line (omitted when empty), and the
  angle-bracketed `<url>` last; bullets are not blank-line separated. Title falls
  back to the URL when the provider gives none. Both return
  `{type:'error'}` on not-enabled / no-results / timeout / transport — never a
  silent no-op; the no-results summary appends "Try a shorter or less
  restrictive query." as the model's in-band retry steer.
  - **Task-shaped descriptions + grounding system line**: both tool descriptions
    state when to reach for the tool, not just what it does — `web_search` names
    the change-prone domains (news, prices, releases, sports, weather) and steers
    the model to short keyword queries (2–6 words) rather than full sentences;
    `read_url` says to use it when a snippet mentions but does not contain the
    answer, and to pass an exact URL copied from a result rather than invent one.
    The rest of the behavioural steering (today's date,
    search-first policy, tool-call budget = agent turn cap − 1,
    answer-from-results + cite URLs, say-so when results lack the answer)
    is grounding text that `prepareCompletion` (`useChatSession.ts`) adds when
    the session's tools include a search talent
    (`resolveSearchGroundingMessage`, `src/utils/systemPromptResolver.ts`).
    **The request carries at most ONE system message**: the grounding is
    MERGED into the pal's system message (`mergeSearchGrounding` joins them
    with a blank line, pal prompt first), and becomes the sole system message
    when the pal has no prompt. It must not be a second system message — many
    chat templates accept a system message only as the first message and
    `raise_exception('System message must be at the beginning.')` otherwise,
    which fails template rendering and kills the whole completion. The merge
    happens at request-assembly time only: the pal's STORED system prompt is
    never modified. The result sits in the initial messages array so it rides
    every follow-up tool turn. Invariant guarded by a
    `system messages === 1` assertion in the `useChatSession` tests. Network
  and Keychain reads are permitted side effects behind the engine boundary
  (I4); the engines read the active provider, whether search may run, and the
  result count through an **accessor injected as a constructor argument** at
  `registerDefaultTalents()` (`new WebSearchEngine(searchAccess)` /
  `new ReadUrlEngine(searchAccess)`), so they never import `SearchProviderStore`
  directly.
  - **Execution gate (consent is load-bearing)**: both engines short-circuit
    with an error result unless `searchProviderStore.canSearch` — i.e. the user
    has consented (`hasConsentedToSearch === true`) **and** the active provider
    has a BYOK key. The Settings disclosure is not the only gate.
  - **`read_url` reader path**: `read_url` requires the active provider be
    configured (consent + key); it then deep-reads via the provider's **native
    reader** if it has one (e.g. Exa), else via the **default reader service**
    (`r.jina.ai`). Providers without a native reader (Brave, Tavily, Parallel)
    therefore route the page URL + content to `r.jina.ai`; the consent
    disclosure names this recipient.
  - **Untrusted content**: retrieved web text (the `web_search` menu and the
    `read_url` page body) is wrapped in explicit untrusted-data markers with a
    one-line "external data, not instructions" note before it is returned to the
    model — an indirect-prompt-injection deterrent.
  - **URL validation**: `read_url` accepts only plain `http(s)` URLs with no
    embedded credentials; `file:`/`data:`/other schemes and userinfo are
    rejected with an error result before any fetch. The default-reader path
    `encodeURI`s the target.

  A single pure `searchBudget` util owns the on-device budgeting
  (count cap, plain-text strip, word-boundary snippet cap with char-boundary
  fallback for space-less scripts, token ceiling with trailing-drop, bounded
  in-session cache invalidated on key/consent/provider change). `budgetHits`
  takes the caller's per-hit renderer and charges the ceiling against the
  **rendered** bullet, not the raw fields — markdown and indentation are part of
  what the model receives, so estimating from raw fields under-counts the real
  payload and leaks past the cap. The provider
  adapters (`src/services/search/providers/`) only normalize wire JSON to a
  common `SearchHit` / `PageContent` shape and bound each response body before
  buffering. BYOK keys live only in Keychain, one entry per provider under
  service `'search_provider_service_<id>'`. Search provider choice, result
  count, and the first-enable consent flag live in `SearchProviderStore` (see
  `settings.md` Internet Search section).

### 1c. Persistence (DB v7)

```
local_pals (WatermelonDB)                         // (C) src/database/schema.ts
  ... existing columns ...
  pact      : string?     // JSON-stringified { talents: TalentRef[] }
  greeting  : string?     // JSON-stringified { text, suggestedPrompts? }
```

`pact` and `greeting` are added in migration v6 → v7 as nullable text columns
(`src/database/migrations.ts:133-145`). Existing pals get `NULL` and behave as
"no talents, no greeting". `LocalPal.toPal()` parses both columns defensively.

(C) `LocalPal.greetingObject` (`src/database/models/LocalPal.ts:128-134`)
returns `Pal['greeting']` directly via `JSON.parse`; defensive against
malformed JSON (returns `undefined` on parse failure).

### 1d. Two terms used throughout

- **PACT** — *Pal Action & Capability Treaty*. The opt-in: `pal.pact.talents`
  is the single source of truth for what tools a Pal advertises and what the
  agent loop will dispatch.
- **Talent** — a named capability with an executor (`TalentEngine`) and an
  optional renderer (`TalentUI`). A talent is **visual** when both are
  registered (only `render_html` today) and **text-only** when only an engine
  is (`calculate`, `datetime`).

> UI-surface note: PalsHub **discovery** lives in the **Explore** tab
> (`explore-tab.md`). `PalsScreen` is now the local-only **My Pals** surface —
> a serif header (back + "+ Create Pal"), **Downloaded | Created-by-me** tabs
> (`source==='palshub'` vs `source==='local'`), and single-column cards with a
> per-card overflow menu (edit / share / delete). The former unified
> local+library+hub grid, filter chips, search, auth bars, and bottom action
> bar were dropped; Explore owns hub discovery. The create/modify form
> (`PalSheet`) is a full-height Sheet with **General | Generation** tabs — the
> former standalone `PalGenerationSettingsSheet` is folded into the Generation
> tab. Pal config/talent dispatch (this doc) is unaffected: the write path
> (`PalSheet.onSubmit → PalStore.create/updatePal`) and PACT/greeting editors
> are unchanged.

---

## 2. Registries

Two registries, one per concern, both populated at app boot via
`registerDefaultTalents()` (`src/services/talents/index.ts:24`). Idempotent —
called from `PalStore.initialize` and `deriveToolSchemas` for safety.

```
                              ┌──────────────────────────────────┐
                              │ registerDefaultTalents()         │
                              │   (idempotent boot)              │
                              └────────────────┬─────────────────┘
                                               │
                ┌──────────────────────────────┴──────────────────────────────┐
                ▼                                                             ▼
   talentRegistry                                                   talentUIRegistry
   Map<name, TalentEngine>                                          Map<name, TalentUI>
   ───────────────────────                                          ─────────────────────
   render_html → RenderHtmlEngine                                   render_html → RenderHtmlTalentUI
   calculate   → CalculateEngine                                    web_search  → WebSearchTalentUI
   datetime    → DatetimeEngine                                     (calculate, datetime, read_url:
   web_search  → WebSearchEngine                                     no UI — text-only)
   read_url    → ReadUrlEngine
```

**Why two registries.** A talent can have an engine without a UI (text-only
talents) but not a UI without an engine (you can't render outcomes for a tool
that never ran). Splitting keeps the executor pure and lets visual surfaces
fail-safe to a generic chip when no UI is registered (see I3 in §5).

---

## 3. PACT → tools derivation

A Pal advertises tools to the model only when its `pact.talents` is non-empty.
`ChatSessionStore.resolveCompletionSettings()` is the single derivation site.

```
Pal.pact.talents = [{name: 'calculate', necessity: 'required'},
                    {name: 'render_html', necessity: 'optional'}]
                                  │
                                  ▼
   talentNames = pal.pact.talents.map(t => t.name)
                                  │
                                  ▼
   deriveToolSchemas(talentNames)   ← src/services/talents/index.ts:47
                                  │   filters talentRegistry by name
                                  │   calls engine.toToolDefinition()
                                  ▼
   resolvedSettings.tools = [
     { type: 'function', function: { name: 'calculate',   parameters: {…} } },
     { type: 'function', function: { name: 'render_html', parameters: {…} } },
   ]
```

When `settingsSource === 'custom'` (per-session override), generation params
come from the session but `tools` is preserved from PACT — see D2 and §7D.

In the no-session chat path the resolver also applies a single-key user
override for `enable_thinking` AFTER PACT tools are injected (see
`chat-flow.md` §5). The override never touches `tools`, so PACT remains the
sole source of truth for tool availability (I2).

---

## 4. Talent execution lifecycle (state machine)

The **runner** (`AgentRunner.ts`) emits the `AgentEvent` stream; the **reducer**
(`agentStateReducer.ts`) maps it to `AgentUiState.status`; **TalentSurface**
renders outcomes once they land. Two views below: a per-tool-call lifecycle and
the literal event → status table from the reducer.

### 4a. Per-tool-call lifecycle

A single tool call moves through three observable phases within one agent step:

```
   STREAMING ──► GENERATING ──► EXECUTING ──► SETTLED
   (text)        (tool args)    (engine)      (outcome on step.toolOutcomes)

   UX status:    UX status:     UX status:    (status carries through to
   streaming_    generating_    executing_     next event — step_started
   text          tool_call      tool           or run_finished)

   trigger:      trigger:       trigger:      trigger:
   first         step_finished  engine        engine resolves OR throws
   `token` w/    + tool_call_   resolves OR    OR name unknown → error
   delta.        started        throws         result; runner emits
   toolCalls     event           (caught)      tool_call_finished either
   OR                                          way
   marker_seen
```

Notes:

- `tool_call_started` *is* the dispatch — runner emits it just before calling
  `engine.execute`. There is no separate "now executing" event.
- Unknown / disallowed tool names short-circuit before `execute`
  (`AgentRunner.ts:132`) and still flow through `tool_call_finished` with
  `result.type === 'error'`. SETTLED is reached either way.
- TalentSurface renders the outcome at SETTLED; `outcome.responseContent` is
  fed back to the model on the next turn.

### 4b. Event → reducer status (from `AgentRunner.types.ts:41-64` + `agentStateReducer.ts`)

| `AgentEvent.type`                          | Reducer status after            |
| ------------------------------------------ | ------------------------------- |
| `run_started`                              | `prefill`                       |
| `step_started`                             | `prefill`                       |
| `token` w/ `delta.toolCalls`               | `generating_tool_call`          |
| `token` w/ visible `content` from `prefill`| `streaming_text`                |
| `marker_seen`                              | `generating_tool_call`          |
| `tool_call_started`                        | `executing_tool`                |
| `tool_call_finished`                       | unchanged (stays `executing_tool`) |
| `step_finished`                            | unchanged                       |
| `run_finished`                             | `done`                          |
| `run_failed`                               | `failed`                        |

Status set: `idle | prefill | streaming_text | generating_tool_call | executing_tool | done | failed`.

User abort is **not** a runner event. The hook calls `signal.abort()`; the
runner's loop sees `signal.aborted`, breaks out, and ends in either
`run_finished` (graceful) or `run_failed` (engine surfaced an error during
shutdown). Aborted runs therefore land in `done`, not a dedicated status.

---

## 5. Contract

### 5a. Hard invariants

- **I1 (registry boundary)**: `talentRegistry` is keyed by `TalentEngine.name`;
  the same name keys `talentUIRegistry`. PACT references this name. Drift
  between the three (engine name, UI name, PACT TalentRef.name) is a bug.
- **I2 (PACT is the source of truth for tool availability)**: a Pal's
  advertised tools are `deriveToolSchemas(pact.talents.map(t=>t.name))` and
  nothing else. The agent runner accepts only tool calls whose name matches an
  entry in the same set; unknown names produce an `error` outcome
  (`AgentRunner.ts:132`).
- **I3 (no-UI fallback)**: when a tool's outcome has no registered `TalentUI`
  (or `renderResult` returns null), `TalentSurface` renders nothing for that
  outcome and the `ToolUsedChip` covers the affordance. Visual talents must
  not assume a UI is registered for any *other* talent.
- **I4 (engine purity)**: `TalentEngine.execute(args)` is a pure
  `args → Promise<TalentResult>`. It must NOT touch React, MobX, or any store.
  Side-effecting talents (file write, network, audio) can live behind the
  engine boundary but must surface their output via `TalentResult` only.
- **I5 (idempotent registration)**: `registerDefaultTalents()` is called from
  multiple boot paths and from `deriveToolSchemas()`. It must be idempotent;
  the module-level `registered` flag enforces this.
- **I6 (text-only talents render nothing)**: `calculate` and `datetime` have
  no `TalentUI`. Their `responseContent` reaches the model on the next turn;
  the user sees only the chip and any subsequent assistant prose. This is by
  design — these tools' value is in the model's follow-up.
- **I7 (engine-name uniqueness)**: registries are `Map<name, …>`; calling
  `register(...)` twice with the same `TalentEngine.name` (or `TalentUI.name`)
  silently replaces the prior entry. Boot-time registration order therefore
  matters: built-ins go first, any future plugin layer registers after and may
  not shadow built-ins by accident. There is no diagnostic for collisions —
  treat unique names as an authoring contract.
- **I8 (recommendedContextTokens is declarative)**: the optional
  `TalentEngine.recommendedContextTokens` is read at exactly two **external**
  sites — the pal-load hint trigger (`usePalLoadHint`) and the heavy-talent
  sub-copy lookup on the `context-full` banner
  (`BannerRow.deriveHeavyTalentName`, whose result is passed through the
  pure `resolveBannerVariant`). It never drives per-turn behaviour or the
  banner trigger threshold; engines without the field work unchanged.
  An engine reading its **own** declared `recommendedContextTokens` as an
  internal budget ceiling inside `execute()` is a permitted **engine-internal**
  read site and does not count against the "exactly two sites" rule (the
  `web_search` / `read_url` engines do this via the shared `searchBudget` util);
  the two external read sites stay unchanged.
  `RenderHtmlEngine` declares `4096`; `WebSearchEngine` declares `1000` and
  `ReadUrlEngine` `1200` (consumed internally as their result token ceiling);
  `CalculateEngine` and `DatetimeEngine` omit. The pal-load hint predicate is focus-gated via
  `useIsFocused()` so it only evaluates while the chat surface is mounted
  and visible — the per-signature suppressor marker is set only after the
  predicate ran, so the hint can re-fire on the next focus event with the
  same `(palId, n_ctx, talents)` signature. See `chat-flow.md` §4a, §4c,
  and §9f for the full banner / snackbar contract.

### 5b. What each component does

| Component                      | Owns                                                                                          | Does NOT                                                                  |
| ------------------------------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `Pal` (data)                   | `pact`, `greeting` configuration in `local_pals`.                                              | Execute. Reference engines or UIs.                                        |
| `TalentEngine`                 | Pure `execute(args) → TalentResult` + `toToolDefinition()`.                                    | React/MobX/store. Persistence. Knowledge of Pals.                         |
| `TalentUI`                     | `renderResult(result)` for the typed outcome.                                                  | Mutate state. Re-execute the engine. Read PACT.                           |
| Registries                     | Name-keyed maps; populated once via `registerDefaultTalents()`.                                | Pal-scoping (engines are global; opt-in is per-Pal via PACT).             |
| `ChatSessionStore.resolveCompletionSettings` | PACT → `tools` derivation; preserve `tools` when `settingsSource === 'custom'`.  | Modify `pact`. Cache schemas.                                             |
| `useChatSession` (hook)        | Wire `talentLookup` and precomputed `triggerMarkers` into `AgentRunOptions`.                   | Hold tool state. Mutate registries.                                       |
| `AgentRunner`                  | Drive the §4 lifecycle. Emit events. Produce `AgentToolOutcome`.                               | Render. Persist. Touch MobX/React.                                        |
| `TalentSurface` (component)    | Per call dispatch: `ToolErrorBlock` (error) / registered `TalentUI.renderResult` / `ToolUsedChip` (no UI) + sibling `ToolMetricsFooter` when `call.metrics` is set. | Decide whether a tool ran. Re-trigger execution.                          |

---

## 6. Single-writer rule

| Field                        | Single writer                                                                                       |
| ---------------------------- | --------------------------------------------------------------------------------------------------- |
| `talentRegistry` entries     | (C) `registerDefaultTalents()` (and tests via `talentRegistry.reset()`).                            |
| `talentUIRegistry` entries   | (C) `registerDefaultTalents()`.                                                                     |
| `pal.pact`                   | (C) `PalStore` create/update flows, edited via `TalentSection` in `PalSheet`.                       |
| `pal.greeting`               | (C) `PalStore` create/update flows, edited via `PalSheet` → `GreetingSection` (in-app editor); also sourced from `createLocalPalFromPalsHub` on PalsHub download. |
| `pal.completionSettings`     | (C) `PalStore` create/update via the `PalSheet` form field; edited in the **Generation tab** (was the standalone `PalGenerationSettingsSheet`). Reset/Clear mutate in-form state only; persistence still happens on form Save. |
| `local_pals.pact` (DB)       | (C) `PalRepository` (writes JSON-stringified value).                                                |
| `resolvedSettings.tools`     | (C) `ChatSessionStore.resolveCompletionSettings()` only.                                            |

Message-side state (`AssistantTurn`, `step.toolOutcomes`, per-step fields) is
owned by `chat-flow.md` §5.

---

## 7. Canonical scenarios

### A. Tool dispatch — text-only vs visual

Same lifecycle (§4), branching only at render time on whether a `TalentUI` is
registered:

```
                  text-only (e.g. calculate)             visual (e.g. render_html)
                  ─────────────────────────              ────────────────────────
  pact.talents:   [{name:'calculate', …}]                [{name:'render_html', …}]
                                                                                    
  Turn events:    streaming_text → marker_seen → tool_call_started →
                  tool_call_finished        (status flips per §4b along the way)
                                                                                    
  engine.execute returns:
                  {type:'text',   summary:                {type:'html', html:"…",
                   '2^16 = 65536'}                         title:"…", summary:"…"}
                                                                                    
  TalentSurface renders:
                  ToolUsedChip                              HtmlPreviewBubble
                  ("used calculate" — I3 fallback           (RenderHtmlTalentUI.renderResult)
                  because no TalentUI is registered)         + sibling ToolMetricsFooter
                                                             when call.metrics is set

  Both: outcome.responseContent goes back to the model on the next turn so
  it can phrase the final answer. The chip / metrics are pure UI affordances
  — they are NOT sent back to the model.
```

### B. Engine throws

```
Turn:
  Assistant: tool_call_started → calculate, args={"expression":"))(("}
             engine.execute catches expr-eval ParseError →
               {type:'error', summary:'calculate: failed to evaluate "))(("',
                errorMessage:'unexpected token …'}
             tool_call_finished (outcome.result.type === 'error')

Visible: ToolErrorBlock; model sees error summary as tool content next turn.
```

### C. Pal advertises a talent the registry doesn't know

```
Pal.pact.talents = [{name: 'future_talent', necessity: 'required'}]  ← engine unregistered

deriveToolSchemas(['future_talent']) → []   ← filter drops unknowns
resolvedSettings.tools               → undefined
                                     → agent loop runs as plain chat
```

Forward-compat: PACT can name talents not yet implemented in this build (e.g.,
a downloaded PalsHub Pal targeting newer features). The pal still runs as
plain chat. `necessity: 'required'` does NOT block today (see D1).

### D. Settings override preserves PACT tools

```
Session.settingsSource = 'custom'              ← user tweaked temperature/top_p
Pal.pact.talents       = [{name: 'calculate', …}]

resolveCompletionSettings(sessionId, palId):
  resolvedSettings ← session.completionSettings (custom)
  resolvedSettings.tools ← re-injected from PACT (ChatSessionStore.ts:1383-1393)
```

Custom generation params, PACT tools intact.

---

## 8. Edge cases

### 8a. Greeting + suggested prompts when no model is loaded

`pal.greeting.text` and `pal.greeting.suggestedPrompts` are pure UI scaffolding —
NOT persisted as messages and NOT sent to the model. They render in `ChatView`
on the empty session.

(C) Today, `ChatView` gates the greeting bubble render on
`modelStore.activeModelId` (`ChatView.tsx:850`); when no model is loaded the
empty-state placeholder shows instead of the greeting. Suggested prompts are
gated separately at `ChatView.tsx:1113` and only render once a model can
accept them.

(?) PR-709 round-1 review left open whether to drop the model-load gate on
the greeting bubble. The greeting is purely UI scaffolding and does not need a
model to render — but the current code still requires one. Resolve in a
follow-up; if the gate goes away, this section becomes "(C) greeting renders
unconditionally on empty sessions." See `chat-flow.md` §6 for the
empty-session rendering contract.

### 8b. Pal export / import round-trip

(C) Pal exports round-trip `pact` and `greeting`. The DTO sits at
`exportUtils.ts:223-224` (write side, export format v2.0) and
`importUtils.ts:266-267` / `:440-441` (`ImportedPal` interface + the
`transformImportPal` reconstruction). Both fields are written when the Pal
has them and re-read on import, so backup-and-restore and share-and-reimport
preserve a Pal's talent set and greeting.

```
EXPORT                                    IMPORT
──────                                    ──────
Pal { pact, greeting, … }                ImportedPal { pact?, greeting?, … }
        │                                          │
        ▼ (exportUtils:200-240)                    ▼ (importUtils:410-450)
JSON DTO v2.0 = {                        new Pal {
  …                                        …
  pact:     pal.pact,         ─────►       pact:     pal.pact,
  greeting: pal.greeting,     ─────►       greeting: pal.greeting,
  …                                        …
}                                        }
```

Older DTOs (pre-fix) that lack both fields still parse — the absent fields
land as `undefined`, equivalent to "no talents, no greeting." No schema
migration is required on the receiving side.

### 8c. Concurrent talent calls in one step

A model can emit multiple tool calls in one step. The runner dispatches them
serially through `talentLookup` → engine; outcomes accumulate on
`step.toolOutcomes` in emission order. A failure in call N does not abort
call N+1.

### 8d. Talent set changes mid-session

Editing `pal.pact.talents` while a session is active takes effect on the
*next* `resolveCompletionSettings()` call. Any in-flight turn keeps its
precomputed `tools` and `triggerMarkers` (the runner's `AgentRunOptions` is
captured at submit time).

---

## 9. Decisions

Resolved trade-offs that aren't obvious from the code. Mechanism alone
(idempotency, registration order, etc.) belongs in §5 invariants, not here.

- **D1** — Ship `TalentRef.necessity` as `'required' | 'optional'` even though
  nothing enforces it yet. The alternative was to land the field later when
  a UX gate needs it. Decided: pay the bytes now to avoid a forced schema
  migration later. (C) The in-app editor (`PalSheet.tsx:244-252`) writes
  `'required'` for every selected talent unconditionally; `'optional'` only
  enters the system through pal import or hand-crafted JSON. A future
  enforcement gate must default to *not* blocking until the editor learns to
  set this field.
- **D2** — Source of truth for tool availability is `pact.talents`, NOT
  `completionSettings.tools` directly. The alternative is a flat
  `completionSettings.tools` that survives whatever per-session override the
  user applied. Decided: separate "what tools does this Pal advertise" (PACT)
  from "what generation params does this turn use" (settings) — otherwise a
  user tweaking temperature could silently strip tools from a Pal that needs
  them. `resolveCompletionSettings` re-injects PACT tools after a custom
  settings layer is applied (§7D).
- **D3** — Two registries (engine + UI), keyed by the same `name`, instead of
  one `Map<name, {engine, ui?}>`. Decided: split keeps engines pure (I4) and
  lets text-only talents exist without UI plumbing (I6). The cost is the I7
  authoring contract.
- **D5** — `TalentUI.renderPending` is deprecated; new UIs must not ship it.
  The single `PendingIndicator` in `ChatView` covers every in-flight phase;
  a second per-talent pending UI doubles the surface and creates dead zones
  in the dispatch handoff. Existing implementations are tolerated to avoid a
  contract break and will be removed in a follow-up cleanup. See
  `TalentUIRegistry.ts:9-21`.
- **D6** — `web_search` returns a dedicated `{type:'search'}` variant carrying
  structured `results[]` alongside the `summary`, rather than having
  `WebSearchTalentUI` re-parse the wrapped menu out of `summary`. Decided: the
  menu is a model-facing payload (untrusted-wrapped, budget-truncated, format
  free to change); the UI gets the same hits as typed data, so the
  human-facing card never depends on parsing model-facing text. `summary` stays
  the single thing the runner forwards to the model, so `search` behaves like
  `text` everywhere except render time (I3-style branch in `TalentSurface`).

---

## 10. Cross-references

- **`chat-flow.md`** — wire shape, `AssistantTurn` / `AgentStep`, agent-loop
  events, persistence and rendering of `step.toolOutcomes`. Read that for
  "how does a tool outcome become a row on the screen." Specifically:
  - §1b — the orphan-pair guard at the wire boundary (relevant when a
    talent call aborts mid-execution)
  - §3 — full `agentUiState` shape (`status`, `pendingTalentNames`,
    `pendingToolTokens`, `hitMaxTurns`) and the indicator's three modes
  - §7 — signal-derivation table
- **`tts.md`** — TTS availability gate. TTS is not a talent today; if it
  becomes one, the engine boundary (I4) and registry split (D3) are where it
  fits.

Source of truth in code: `src/types/pal.ts`, `src/services/talents/`,
`src/store/ChatSessionStore.ts:1340-1397`, `src/database/models/LocalPal.ts`,
`src/hooks/useChatSession.ts` (`talentLookup` wiring), `src/components/TalentSurface/`,
`src/components/PalsSheets/PalSheet.tsx` (in-app editor — `TalentSection`
nested inside; tabbed General | Generation form, the latter via
`src/components/PalsSheets/GenerationSettings.tsx`),
`src/screens/PalsScreen/PalsScreen.tsx` (local-only My Pals surface).

When this doc and the code disagree, the code wins; the same PR that lands
the change updates this file.
