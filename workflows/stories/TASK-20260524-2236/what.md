# WHAT — Wire Palshub `pact.talents` + `greeting` into PocketPal pal download

**Scope of this delta**: amends `context/architecture/pals-and-talents.md`. Touches only the **download conversion site** (PalsHub wire → local `Pal`) and the wire-boundary type that precedes it. No new flow, no new contract, no new component. The chat-time PACT → tools path (§3 of the architecture doc) is unchanged and consumes the populated fields verbatim.

---

## Conventions

- **(C)** = current behaviour, documented from code
- **(P)** = proposal, open for challenge
- **(?)** = open question, decision needed (must be zero before critic routing)
- **(D)** = decision (was an open question, now resolved)

---

## 1. Data model

### 1a. Local `Pal` — no change

The `Pal` type (`src/types/pal.ts:117-136`) already carries the target fields:

```
Pal.pact?     : { talents: TalentRef[] }
Pal.greeting? : { text, suggestedPrompts? }
```

Persistence layer (`local_pals.pact`, `local_pals.greeting`) is also unchanged — both are nullable JSON text columns since DB v7 (`src/database/migrations.ts:133-145`). `LocalPal.toPal()` already parses both via `pactObject` / `greetingObject` and includes them in the returned `Pal` (`src/database/models/LocalPal.ts:175-209`). **(C)**

### 1b. PalsHub wire type — additive

Add three optional fields to `PalsHubPal` (`src/types/palshub.ts:82-168`) so the wire shape can carry what PalsHub PR #66/#68 added:

```
PalsHubPal
  pact?     : { version: number, talents: Array<{name: string, required?: boolean}> }   // (P) PR #68
  greeting? : { text?: string, suggested_prompts?: string[] }                            // (P) PR #66
  images?   : unknown[]                                                                  // (P) PR #66 — loose pass-through
  models?   : unknown[]                                                                  // (P) PR #66 — loose pass-through
```

Notes:

- `pact` and `greeting` mirror the Palshub server shape exactly — **snake_case**, top-level optional. The wire-side `pact.version` is carried in the type but ignored at conversion time; the local `Pal.pact` shape has no `version` field today and adding one is out of scope (see §10). **(D2)**
- `images` and `models` are typed as `unknown[]` because this story does not consume them. Defining concrete shapes for not-yet-consumed fields is forbidden by YAGNI; future stories will tighten when there's a real consumer. **(D3)**
- All four fields are optional. Older Palshub responses (before PR #66/#68) omit them entirely and must continue to deserialize without error. **(I3)**

### 1c. API-response interface — additive at the wire boundary

`ApiPalResponse` (`src/services/palshub/PalsHubApiService.ts:26-75`) is the raw HTTP-response shape that `transformApiPal` (`PalsHubApiService.ts:209-260`) converts into `PalsHubPal`. The same three optional fields (`pact`, `greeting`, `images`, `models`) must be added there so the transformer can forward them. The transformer is the **only** writer that produces `PalsHubPal` from a network response — no other site is allowed to fabricate one. **(C)** / **(P)**

---

## 1b. External shape

PalsHub mobile endpoint `GET /api/mobile/pals/[id]` (and the list endpoints) now return JSONB columns `pact` and `greeting` on each pal (PalsHub PRs #66, #68). Server-derived legacy fields (`thumbnail_url`, `model_reference`, `model_settings`) keep working — the server derives them from `images[].is_primary` / `models[].is_recommended` respectively. We do not consume `images[]` or `models[]` arrays in this story; they are passed through `PalsHubPal` as `unknown[]` only to keep round-trip fidelity for future stories.

Wire → local mapping (the only mapping this delta adds):

| Wire (`PalsHubPal`, snake_case)       | Local (`Pal`, camelCase)                      |
| ------------------------------------- | --------------------------------------------- |
| `pact.talents[].name`                 | `pact.talents[].name`                         |
| `pact.talents[].required: true`       | `pact.talents[].necessity = 'required'`       |
| `pact.talents[].required: false`/absent | `pact.talents[].necessity = 'optional'`     |
| `pact.version`                        | (dropped — see D2)                            |
| `greeting.text`                       | `greeting.text`                               |
| `greeting.suggested_prompts`          | `greeting.suggestedPrompts`                   |
| `thumbnail_url` (server-derived)      | `thumbnail_url` (unchanged path — see §6.C)   |
| `model_reference` (server-derived)    | `defaultModel` (unchanged path — see §6.D)    |

---

## 2. Event flow

Not applicable — this is a synchronous data transform on a one-shot user action (tap "Download" / tap "Start Chat" on an undownloaded PalsHub pal). No new events.

---

## 3. State machine

Not applicable — no state changes. The chat-time `executing_tool` lifecycle (architecture doc §4) is unchanged; it consumes whatever `pact.talents` arrives in the local `Pal`.

---

## 4. Contract

### 4a. Conversion rules at the download boundary

`createLocalPalFromPalsHub` (`src/store/PalStore.ts:432-491`) is the **single** code path that produces a local `Pal` from a `PalsHubPal`. After this story, it must additionally:

1. **Pact pass-through**: when `palsHubPal.pact?.talents` is a non-empty array, populate `pal.pact = { talents: [...] }` with each entry mapped per §1b. When `palsHubPal.pact` is absent, `null`, or has an empty `talents` array, `pal.pact` is `undefined`. **(P)**
2. **Greeting pass-through**: emit `pal.greeting` iff `(palsHubPal.greeting?.text?.length ?? 0) > 0` OR `(palsHubPal.greeting?.suggested_prompts?.length ?? 0) > 0`. When emitted:
   - `pal.greeting.text` is `palsHubPal.greeting.text` passed through as-is (including the empty string `''` when only `suggested_prompts` is non-empty — see §9a). The conversion site does **not** trim, validate, or filter `text`.
   - `pal.greeting.suggestedPrompts` is set only when `palsHubPal.greeting.suggested_prompts` is a non-empty array (camelCase rename; see I2). Otherwise the key is omitted.
   - When the predicate is false (both subfields empty/absent, or `greeting` itself absent / `null`), `pal.greeting` is `undefined`. This is the single source of truth for the "emit greeting?" decision; §9a is a worked example, not an additional rule. **(P)**
3. **Necessity defaulting**: `pact.talents[].required` is **optional** on the wire. The mapping defaults absent `required` to `necessity: 'optional'`. This matches D1 in the architecture doc — `'required'` is a marker that an enforcement gate may use later; until then both values are equivalent at runtime. **(D1)**
4. **Required boolean coercion**: `pact.talents[].required` MUST be checked as a strict boolean: only the literal `true` maps to `'required'`. Anything else (including `false`, `0`, `null`, `undefined`, missing key) maps to `'optional'`. This protects against truthy-but-not-true Palshub payload drift. **(D4)**
5. **Empty-pact policy**: `pal.pact = { talents: [] }` is forbidden — the architecture doc's PACT → tools derivation (§3) treats an empty array as the "advertises tools" path, which is wasted work. Emit `undefined` instead. (The analogous greeting rule is folded into rule 2 above as a single predicate.) **(P)**
6. **Forward-compat with unknown talent names**: the conversion site does **not** validate that named talents exist in `talentRegistry`. Unknown names are preserved on the local `Pal` so a future build with new engines can use them. This is the existing architectural contract (architecture doc §7 scenario C). **(C)**

### 4b. Wire boundary (`transformApiPal`)

`transformApiPal` (`PalsHubApiService.ts:209`) forwards `apiPal.pact` and `apiPal.greeting` onto the returned `PalsHubPal` verbatim (no shape conversion at this boundary; the snake_case wire shape lives on `PalsHubPal` per §1b). Same for the loose `images`/`models` arrays. **(P)**

### 4c. Re-download semantics

(C) Today there is **no re-download UI path**. `PalDetailSheet.handleAction` (`src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx:91-114`) and `SquarePalCard.handleStartChat` (`src/screens/PalsScreen/components/SquarePalCard/SquarePalCard.tsx:264-302`) both gate on `palStore.isPalsHubPalDownloaded(pal.id)` / `palStore.pals.find(p => p.palshub_id === pal.id)` and short-circuit before calling `downloadPalsHubPal`. The download button does not appear once a pal is downloaded.

(D5) **No new "refresh" path is introduced in this story.** The intent's "re-download refreshes pact/greeting without dropping them" acceptance criterion is satisfied **trivially** today: re-download is not possible from the UI, so `pact`/`greeting` cannot be dropped by a re-download. If a future story adds an explicit refresh / re-sync of downloaded pals, that story owns the contract for which fields are refreshed and which are preserved (e.g., user-edited greeting text). Designing that contract here would be speculative.

### 4d. Hard invariants

- **I1** (single conversion site): `createLocalPalFromPalsHub` is the only path that fabricates a `Pal.pact` or `Pal.greeting` from a `PalsHubPal`. No other module may read PalsHub wire fields and produce a local `Pal`. Preserves the architecture doc's §6 single-writer table for `pal.pact` / `pal.greeting` (PalStore create/update flows).
- **I2** (snake_case at wire / camelCase locally): `PalsHubPal.greeting.suggested_prompts` (snake_case) and `Pal.greeting.suggestedPrompts` (camelCase) MUST stay distinct. The rename happens exactly once, inside `createLocalPalFromPalsHub`. The conversion site is syntactic only — it does not trim, validate, or filter `text` content (see §9c). For `text`, which keeps the same identifier on both sides, this means pass-through verbatim including the empty string `''`. Persistence (`PalRepository`, `LocalPal`) speaks camelCase only.
- **I3** (older payloads survive): when `palsHubPal.pact`, `palsHubPal.greeting`, `palsHubPal.images`, `palsHubPal.models` are all absent, the conversion produces a `Pal` with `pact: undefined`, `greeting: undefined`, behaving identically to today's pre-PR-#66/#68 path.
- **I4** (no regression on existing legacy paths): server-derived `thumbnail_url` and `model_reference` continue to flow through their existing branches in `createLocalPalFromPalsHub` (see §6.C, §6.D scenarios). The conversion site does **not** read `images[]` / `models[]` to re-derive these locally — that is the server's job per PalsHub PR #66.

### 4e. What each component does (delta only)

| Component                         | Owns (new in this story)                                                          | Does NOT                                                                                |
| --------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `PalsHubApiService.transformApiPal` | Forward `pact`, `greeting`, `images`, `models` from `ApiPalResponse` to `PalsHubPal`. | Convert snake_case → camelCase. Validate. Default values.                               |
| `PalStore.createLocalPalFromPalsHub` | Map wire `pact` + `greeting` to local shape (per §1b table). Apply §4a rules.   | Validate talent names against registry. Persist (PalRepository does it). Trigger UI.    |
| `PalRepository.createPal` / `updatePal` | **No change** — already JSON-stringifies `palData.pact` / `palData.greeting`. | —                                                                                       |
| `LocalPal.pactObject` / `greetingObject` | **No change** — already returns the parsed JSON typed as `Pal['pact']` / `Pal['greeting']`. | — |

---

## 5. Layer ownership (single-writer rule)

The architecture doc's §6 table is unchanged. This delta only re-affirms the writers for the two fields the story touches:

| Field                  | Single writer                                                                                                  |
| ---------------------- | -------------------------------------------------------------------------------------------------------------- |
| `Pal.pact` (in-memory) | (C) `PalStore.createPal` / `updatePal` (via `addPal`). Source of values: `createLocalPalFromPalsHub` for downloaded pals; `PalSheet → TalentSection` for in-app edits. |
| `Pal.greeting` (in-memory) | (C) `PalStore.createPal` / `updatePal`. Source: `createLocalPalFromPalsHub` or `PalSheet`.                  |
| `local_pals.pact` (DB) | (C) `PalRepository` — `LocalPal.safeStringify(palData.pact)`.                                                  |
| `local_pals.greeting` (DB) | (C) `PalRepository` — `LocalPal.safeStringify(palData.greeting)`.                                          |

No multi-writer race risk introduced: download is a single async action that runs `createLocalPalFromPalsHub` → `addPal` → `PalRepository.createPal` serially.

**Deferred cleanups** (not in this story):

1. Architecture doc §1c (?) about `LocalPal.greetingObject` under-typing is **stale** — code at `LocalPal.ts:128-134` already returns `Pal['greeting']`. Architecture doc must be reconciled when this story's WHAT is absorbed (see §11 Drift).
2. `transformApiPal` returns synthetic `creator`, `categories[].sort_order = 0`, `tags[].usage_count = 0` defaults. Out of scope.

---

## 6. Canonical scenarios

### A. Download a PalsHub pal with full pact + greeting (the happy path)

```
Wire (PalsHubPal):
  pact: { version: 1, talents: [
    { name: 'render_html', required: true  },
    { name: 'calculate',   required: false },
  ]}
  greeting: { text: 'Hi! Want me to sketch something?',
              suggested_prompts: ['Draw a sunset', 'Make a chart'] }

  ↓ createLocalPalFromPalsHub

Local (Pal):
  pact: { talents: [
    { name: 'render_html', necessity: 'required' },
    { name: 'calculate',   necessity: 'optional' },
  ]}
  greeting: { text: 'Hi! Want me to sketch something?',
              suggestedPrompts: ['Draw a sunset', 'Make a chart'] }

  ↓ PalRepository.createPal (existing)

local_pals row:
  pact:     '{"talents":[{"name":"render_html","necessity":"required"},...]}'
  greeting: '{"text":"Hi! Want me to sketch something?","suggestedPrompts":[...]}'

  ↓ user opens chat with this pal

ChatSessionStore.resolveCompletionSettings:
  talentNames        = ['render_html', 'calculate']
  resolvedSettings.tools = [
    { type:'function', function:{ name:'render_html', parameters:{...} } },
    { type:'function', function:{ name:'calculate',   parameters:{...} } },
  ]

  ↓ ChatView (empty session)

  • greeting bubble: "Hi! Want me to sketch something?"
  • suggested-prompt chips: [Draw a sunset] [Make a chart]
```

### B. Download a PalsHub pal with neither pact nor greeting (legacy / older Palshub)

```
Wire (PalsHubPal):
  pact:     undefined   // older Palshub backend / pal author opted out
  greeting: undefined

  ↓ createLocalPalFromPalsHub

Local (Pal):
  pact:     undefined
  greeting: undefined

  ↓ ChatSessionStore.resolveCompletionSettings (chat opens later)

resolvedSettings.tools = undefined   // architecture doc §3 — no PACT → no tools
                                     // agent loop runs as plain chat (architecture §7 scenario C)
```

### C. Download a PalsHub pal — recommended-model path still works (PR #66 regression check)

PalsHub PR #66 moved the model from a single `model_reference` to `models[].is_recommended`, then server-derives the legacy `model_reference` field for older clients. PocketPal continues to read `palsHubPal.model_reference` — no client-side change.

```
Wire (PalsHubPal):
  model_reference: { repo_id: '…', filename: '…', author: '…',
                     downloadUrl: '…', size: 1234567 }
  models:          [...]              // present but unread by client

  ↓ createLocalPalFromPalsHub  (existing branch at PalStore.ts:456-458)

Local (Pal):
  defaultModel: Model { id: '…', name: '…', author: '…', ... }
```

### D. Download a PalsHub pal — primary-image path still works (PR #66 regression check)

Same shape: `images[].is_primary` is the new source of truth; server derives `thumbnail_url`; client reads `thumbnail_url`.

```
Wire:  thumbnail_url: 'https://…/abc.png'
       images:        [...]            // present but unread

  ↓ existing thumbnail download branch (PalStore.ts:252-275)

Local (Pal): thumbnail_url: 'pal_thumbnails/{palId}.png'   // relative local path
```

### E. Pact with an unknown talent name (forward compat)

```
Wire:  pact: { talents: [{ name: 'web_search', required: true }] }
       // talentRegistry has no 'web_search' engine in this build

  ↓ createLocalPalFromPalsHub  (does NOT validate name)

Local (Pal): pact: { talents: [{ name: 'web_search', necessity: 'required' }] }

  ↓ chat opens

deriveToolSchemas(['web_search']) = []     // architecture §3 filter
resolvedSettings.tools             = undefined
                                   → plain chat
                                   → no error, no crash
```

### F. App restart preserves pact + greeting

```
1. Download Pal X (per Scenario A) → local_pals row written.
2. Kill + relaunch app.
3. PalStore.initialize() → PalRepository.getAllPals() → LocalPal.toPal() per row.
4. Pal X in memory has the same pact + greeting as before restart.
5. Open chat with Pal X → tools advertised; greeting + chips render on empty session.
```

(Trivially covered today by the existing round-trip through `LocalPal.pactObject` / `greetingObject` — Scenario F is in the list to make the regression check explicit and testable.)

### G. Pact with stringly-typed `required` (D4 — strict-boolean check)

```
Wire:  pact: { talents: [
         { name: 'calculate',   required: 'true' },   // string, not bool
         { name: 'render_html', required: 1 },        // number, not bool
         { name: 'web_search',  required: true },     // the only literal-true entry
       ]}

  ↓ createLocalPalFromPalsHub  (D4: strict `=== true` check)

Local (Pal):
  pact: { talents: [
    { name: 'calculate',   necessity: 'optional' },  // 'true' string → optional
    { name: 'render_html', necessity: 'optional' },  // 1 → optional
    { name: 'web_search',  necessity: 'required' },  // true → required
  ]}
```

Rationale: a Palshub-side accident (stringly-typed payload) MUST NOT silently flip a Pal's enforcement semantics. Until a future enforcement gate ships (architecture D1), `'optional'` is the safe default.

---

## 7. State signals

Not applicable.

---

## 8. Decisions

- **D1** (referenced) — `necessity: 'optional'` is the default when wire `required` is missing or non-true. Matches the architecture doc's existing D1 — both `'required'` and `'optional'` are runtime-equivalent until a future enforcement gate lands; defaulting to `'optional'` is the conservative choice and avoids accidentally flagging a Pal as enforcing tools it tolerates.
- **D2** — Drop `pact.version` at the conversion boundary. The local `Pal.pact` shape has no `version` field; adding one purely to round-trip a constant `1` is YAGNI. A future schema-versioned PACT story can introduce it on the local type and a real migration path at the same time.
- **D3** — Type `images` and `models` as `unknown[]` on `PalsHubPal`, not as fully-typed arrays. The fields are explicitly non-goals; concrete shapes invite shape-drift between this story and the actual consumer story. `unknown[]` documents that the data flows through without being structurally inspected.
- **D4** — `pact.talents[].required` is mapped via strict-boolean check (`=== true`), not truthy. Defends against Palshub-side stringly-typed accidents (`required: 'true'`, `required: 1`) that would otherwise silently flip a Pal's enforcement semantics.
- **D5** — No "re-download / refresh" path is added in this story. Today's UI prevents re-download, so the intent's "re-download refreshes pact/greeting without dropping them" criterion is satisfied trivially. A refresh path is a separate design — it must decide which fields are refreshed and which are user-protected (e.g., a user-edited greeting).

---

## 9. Edge cases

### 9a. Partial greeting from wire

Worked examples of the single predicate in §4a rule 2 (`emit iff text.length > 0 OR suggested_prompts.length > 0`):

| Wire `greeting`                                | Predicate | Local `pal.greeting`                                       |
| ---------------------------------------------- | --------- | ---------------------------------------------------------- |
| absent / `null`                                | false     | `undefined`                                                |
| `{ text: 'Hi', suggested_prompts: ['a','b'] }` | true      | `{ text: 'Hi', suggestedPrompts: ['a','b'] }`              |
| `{ text: 'Hi' }`                               | true      | `{ text: 'Hi' }` (no `suggestedPrompts` key)               |
| `{ text: 'Hi', suggested_prompts: [] }`        | true      | `{ text: 'Hi' }` (empty array → key omitted)               |
| `{ suggested_prompts: ['a'] }`                 | true      | `{ text: '', suggestedPrompts: ['a'] }`                    |
| `{ text: '', suggested_prompts: ['a'] }`       | true      | `{ text: '', suggestedPrompts: ['a'] }`                    |
| `{ text: '' }`                                 | false     | `undefined` (no chips, no text → nothing to emit)          |
| `{ text: '', suggested_prompts: [] }`          | false     | `undefined`                                                |
| `{}`                                           | false     | `undefined`                                                |

When `text` is emitted as `''` (text absent / empty but chips present), the chat-side visibility gate at `ChatView.tsx:853` (`activePal?.greeting?.text && modelStore.activeModelId`) treats the empty string as falsy and hides the empty bubble; chips still render. This matches today's behaviour for in-app pals that have only suggested prompts.

### 9b. Empty talents array

`pact: { talents: [] }` on the wire → local `pal.pact = undefined` (§4a rule 5). Avoids walking an empty array through the PACT → tools derivation on every chat turn. Same outcome for `pact: { version: 1 }` (no `talents` key), `pact: { talents: null }`, and `pact: null` — all four shapes produce `pal.pact = undefined`. The conversion check uses `palsHubPal.pact?.talents` plus a `length > 0` test, so each variant short-circuits naturally.

### 9c. Whitespace-only greeting text

`greeting.text` is whitespace-only (`'   '`) → emit `text` as-is to `Pal.greeting.text`. The chat-side render gate is responsible for the visibility decision; the download path does not trim or filter. This keeps the conversion site syntactic, not semantic.

### 9d. Duplicate talent names in `pact.talents[]`

Out of scope; the local `Pal` accepts duplicates today and the architecture doc does not forbid them. If duplicates appear, `deriveToolSchemas` will return duplicate entries; the model will see duplicate tool definitions. Not a regression — the wire just makes it more likely. A future de-dup decision belongs on the conversion site, not on this story.

### 9e. PalsHub returns `pact: null` (vs absent)

JSON `null` and absent key both must produce `pact: undefined` locally. The conversion check uses `palsHubPal.pact?.talents` so null short-circuits naturally.

### 9f. App ships before Palshub server starts returning the new fields

Older Palshub servers return `PalsHubPal` without `pact`/`greeting`. The new optional fields stay absent; conversion takes the §6.B branch; everything works as before.

### 9g. Export / import after download

(C) The export DTO already round-trips `pact` and `greeting` from migration v7+ (architecture doc §8b). After this story, a Pal downloaded from PalsHub and then exported retains its PACT + greeting on re-import. No change required at the export/import layer.

---

## 10. What this doc is NOT

- Not a "refresh existing palshub pal" design — that's deferred (D5, intent §"deferred").
- Not a per-user consent UX for talents — explicit non-goal in the intent.
- Not a model-picker for `models[]` beyond `is_recommended` — explicit non-goal.
- Not a disclaimers UI / data path — explicit non-goal.
- Not a multi-image gallery — explicit non-goal.
- Not a tightening of `images[]` / `models[]` types — those stay `unknown[]` until a consumer story arrives (D3).
- Not an enforcement gate for `necessity: 'required'` — that's architecture doc D1's future work.

---

## 11. Drift findings (architecture doc → code)

Drift check against `context/architecture/pals-and-talents.md`:

- **Minor drift**: §1c says `LocalPal.greetingObject` is under-typed as `{text: string} | undefined`. Reality (`src/database/models/LocalPal.ts:128-134`): returns `Pal['greeting']`, which already includes `suggestedPrompts`. The (?) marker is stale and should be removed when this story's WHAT is absorbed into the architecture file.
  - **Fix-up**: when the implementer absorbs this WHAT, also delete the (?) in §1c of the architecture doc (4 lines) and tighten the description to "(C) `LocalPal.greetingObject` returns `Pal['greeting']` directly via `JSON.parse`; defensive against malformed JSON."

No major drift. The single-writer rules in §6, the I1–I7 invariants, the PACT → tools derivation, and the lifecycle in §4 all match code.

---

## Review History — Round 1

| # | Severity   | Critic finding (short)                                                                 | Resolution | Where |
| - | ---------- | -------------------------------------------------------------------------------------- | ---------- | ----- |
| 1 | CONCERN    | §9a partial-greeting rule contradicts §4a rule 5; empty-string is an unaddressed third state | FIXED | §4a rule 2 rewritten as single predicate `emit iff text.length > 0 OR suggested_prompts.length > 0`; §4a rule 5 narrowed to pact-only; §9a converted to a worked-examples table over the predicate (including `text: ''`, `text: ''` + chips, `text: ''` + empty chips). The predicate is now the single source of truth. |
| 2 | CONCERN    | I2 under-specifies that `text` rename is a no-op AND the policy site for empty/whitespace | FIXED | I2 extended to call out that `text` is pass-through verbatim (including `''`) and that the conversion site is syntactic only (cross-ref §9c). |
| 3 | SUGGESTION | Make §6 forward-compat scenario explicit about D4 strict-boolean                         | FIXED | Added §6.G covering `required: 'true'` (string), `required: 1` (number), `required: true` (bool) — only literal `true` maps to `'required'`. |
| 4 | SUGGESTION | §9b should cover `pact: { version: 1 }` (no `talents` key) and `pact: { talents: null }` | FIXED | §9b extended to enumerate all four variants (`talents: []`, `{version:1}` no key, `talents: null`, `pact: null`) and note the `?.talents` + `length > 0` short-circuit. |

All four findings addressed; no REJECTED or DEFERRED. Re-ran the Quality Checklist: zero `(?)` markers, all `(D)` rationaled, single-writer table unchanged, scenarios still cover happy + legacy + forward-compat + restart + strict-boolean coercion, doc length within ceiling.

