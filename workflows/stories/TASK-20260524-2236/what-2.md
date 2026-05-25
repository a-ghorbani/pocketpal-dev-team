# WHAT (slice 2) — Editable greeting + suggested prompts in PalSheet

**Scope of this delta**: amends `context/architecture/pals-and-talents.md` (§5b, §6, §7, §8a). Adds a second writer for `Pal.greeting` (the in-app editor in `PalSheet`) so users can author/edit greeting bubble text and tappable suggested-prompt chips on locally-created and downloaded pals. Layers on top of slice 1's `what.md` (PalsHub download writer already merged in PR #741); the chat-side render gates and the `SuggestedPromptsRow` chip component are unchanged and consume the editor output verbatim.

This delta does **not** touch the PACT flow (§3), the talent execution lifecycle (§4), or the wire-boundary type changes from slice 1.

---

## Conventions

- **(C)** = current behaviour, verified by reading code
- **(P)** = proposal, open for challenge
- **(D)** = decision (was an open question, now resolved)

No **(?)** markers; all open questions are resolved below.

---

## 1. Data model

### 1a. Local `Pal` — no change

`Pal.greeting?: { text: string, suggestedPrompts?: string[] }` (`src/types/pal.ts:122-136`) is the target shape. **(C)** This slice does not introduce new fields; it only adds a new writer.

Persistence (`local_pals.greeting`) is unchanged. `PalRepository.createPal` already JSON-stringifies `palData.greeting` (`src/repositories/PalRepository.ts:187`). `PalRepository.updatePal` gates on `updates.greeting !== undefined` and stringifies (`PalRepository.ts:295-297`). `LocalPal.greetingObject` parses on read (`src/database/models/LocalPal.ts:128-134`). `LocalPal.safeStringify(null) === undefined` AND `safeStringify(undefined) === undefined` (`LocalPal.ts:213-216` — "Preserve null/undefined as undefined in database"). **(C, load-bearing for §4a rule 2.)**

### 1b. Form data — additive

`PalFormData` (`src/components/PalsSheets/types.ts:4-19`) is React Hook Form's working shape inside `PalSheet`. Add two optional fields:

```
PalFormData
  greetingText?            : string            // (P) backs the single-line greeting input
  suggestedPrompts?        : string[]          // (P) ordered list of chip prompts, editor-owned
```

Notes:

- Fields are **flat on `PalFormData`** (not nested under a `greeting` object). RHF's `Controller` + `useFieldArray` both prefer flat top-level keys, and slice 1's wire-boundary code already proves the shape collapse happens at save time (PalStore composes the nested `greeting` object from these two pieces). **(D6)**
- `greetingText` is named to avoid collision with `name` already in `PalFormData`. **(P)**
- `suggestedPrompts` is the **same camelCase identifier** the local `Pal.greeting.suggestedPrompts` uses (I2 in slice 1). No rename inside the editor. **(P)**
- Defaults in `INITIAL_STATE` and the form `reset` paths: `greetingText: ''`, `suggestedPrompts: []`. Matches the "empty fields → save as no-greeting" predicate in §4a rule 1. **(P)**

### 1c. No new persistence

No DB column, no migration, no new repository method. The existing `palRepository.createPal` / `updatePal` paths persist `palData.greeting` verbatim already.

---

## 1b. External shape

Not applicable. This slice has no wire-format effect. The PalsHub mobile endpoint shape is owned by slice 1 (§1c of `what.md`).

---

## 2. Event flow

Not applicable. Form input → submit handler → store → repository is synchronous from the editor's perspective (one async call to `createPal` / `updatePal`).

---

## 3. State machine

No state machine changes. The chat-side `agentUiState` lifecycle (architecture doc §4) is untouched. The editor itself is plain RHF state; React Hook Form's internal touched/dirty/error states are not new contracts.

---

## 4. Contract

### 4a. Save-path rules in `PalSheet.onSubmit`

`PalSheet.onSubmit` (`src/components/PalsSheets/PalSheet.tsx:222-294`) is the **single** code path that translates editor state into `palData: Partial<Pal>` and calls `palStore.createPal` / `palStore.updatePal`. After this story it must additionally:

1. **Greeting emit predicate (parity with slice 1 §4a rule 2)**: emit `palData.greeting` iff `text.length > 0` OR `cleanedPrompts.length > 0`, where:
   - `text = data.greetingText ?? ''` — **un-trimmed** raw user input. The length check is against the raw string, identical to slice 1's wire-side predicate `(palsHubPal.greeting?.text?.length ?? 0) > 0`. **(D8, S4 alignment)**
   - `cleanedPrompts = (data.suggestedPrompts ?? []).map(p => p.trim()).filter(p => p.length > 0)` — per-row trim + drop empty rows. Per-prompt trim stays because chips render trimmed-content visually; an empty row is almost certainly user error. **(D7)**
   - When the predicate is true:
     - `palData.greeting.text = text` — pass through verbatim, including whitespace-only strings (preserves intentional leading spaces or trailing line breaks the author typed). The chat-side render gate handles display-time visibility (architecture doc §8a). **(D8, I10)**
     - `palData.greeting.suggestedPrompts = cleanedPrompts` is set only when `cleanedPrompts.length > 0`. Otherwise the key is omitted. (Matches the camelCase shape and the slice-1 wire-mapping table.)
   - When the predicate is false (both pieces empty / missing — note: `text` is **not** trimmed in the predicate, so `'   '` with no prompts emits greeting; see §9a row 2 and I12), `palData.greeting = SENTINEL_NO_GREETING` (see rule 2).

2. **Update-path explicit clear (the convergent sentinel)**: `palData.greeting` MUST always be set explicitly on the `Partial<Pal>` object — either to the populated object or to a **sentinel "no-greeting" shape**. The current `PalRepository.updatePal` gate is `if (updates.greeting !== undefined)` (`PalRepository.ts:295`). Two facts about the persistence layer make `undefined` and `null` both unsuitable for the clear case: **(C1 fix; verified against code)**
   - `palData.greeting = undefined` → gate is false → the entire block is skipped → DB column **untouched** (stale greeting preserved). Wrong.
   - `palData.greeting = null` → gate passes (`null !== undefined`) but `LocalPal.safeStringify(null)` returns `undefined` (`LocalPal.ts:213-216`); the column is set to `undefined`, which WatermelonDB stores as NULL. This actually works on the DB side, BUT `Pal` is typed as `Pal.greeting?: {...}` — passing `null` to `Partial<Pal>` is a type lie and the next reader (e.g., MobX `_pals` array shape) sees `null` until the next DB read.
   - The contract: set `palData.greeting = { text: '', suggestedPrompts: [] }` (the **empty-object sentinel**). `safeStringify` writes valid JSON `'{"text":"","suggestedPrompts":[]}'`; `LocalPal.greetingObject` parses it back to that same object. The chat-side gates at `ChatView.tsx:853` (`activePal?.greeting?.text` — `''` falsy) and `ChatView.tsx:1115` (`suggestedPrompts.length > 0` — `0` falsy) both suppress the bubble AND chips. Visually identical to "no greeting", and the editor on re-open seeds `greetingText=''`, `suggestedPrompts=[]` per §4b — round-trip closes. **(D9; verified via §6 scenario C round-trip below.)**

   This is the **convergent** workaround pattern that `pact` already uses at `PalSheet.tsx:244-252` (`{talents: [] as TalentRef[]}` sentinel for the same `!== undefined` gate). The trade-off: the stored shape is `{text:'',suggestedPrompts:[]}` rather than "truly empty" (NULL column). This is acceptable because every read path (chat render, editor re-seed, export DTO) treats the sentinel as equivalent to absent. The unification of `pact` and `greeting` onto a single "drop the preservation gate" repo-side refactor is tracked as a deferred cleanup in §5. **(D9, C2 fix)**

3. **Order preservation**: the order the user enters prompts is the order saved and the order rendered as chips. `SuggestedPromptsRow` (`src/components/SuggestedPromptsRow/SuggestedPromptsRow.tsx:41`) iterates `prompts.map((prompt, idx) => …)` in array order, so editor order = chip order. **(P)**

4. **No duplicate-collapse, no caps**: the editor does not de-duplicate prompts, does not enforce a max count, does not enforce a max length. Per the intent's "no length validation" decision. **(P)**

### 4b. Form initialisation rules in `PalSheet`

`PalSheet`'s `useEffect` initialisation (`PalSheet.tsx:147-165`) and `resetForm` (`:167-184`) hydrate `PalFormData` from the incoming `pal: Partial<Pal>` prop. Both must additionally:

1. Set `greetingText = pal.greeting?.text ?? ''`. **(P)**
2. Set `suggestedPrompts = pal.greeting?.suggestedPrompts ?? []`. **(P)**
3. Apply to both create and edit paths. Brand-new pal (`pal.greeting === undefined`): both fields empty. Edit of a downloaded pal: existing values populate. Edit of a previously-cleared pal (`pal.greeting === SENTINEL_NO_GREETING = {text:'', suggestedPrompts:[]}`): both fields also empty (the `?? ''` / `?? []` only triggers for `undefined`, but `pal.greeting.text` IS already `''` and `pal.greeting.suggestedPrompts` IS already `[]`). Round-trip closes cleanly. **(C1 fix verified.)**

### 4c. UI component contract (new section: `GreetingSection`)

The editor surface for greeting fields lives in a new component file `src/components/PalsSheets/GreetingSection/GreetingSection.tsx` (and its barrel `index.ts`), mirroring `ColorSection/` and `TalentSection.tsx` patterns. It is mounted inside `PalSheet` between `SystemPromptSection` and `ColorSection` (rationale in §6 scenario A). **(P)**

Component shape (no implementation detail beyond what's a contract):

| Responsibility                                           | Who owns it                                                                                  |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Render the section divider with l10n label               | `GreetingSection` (via existing `SectionDivider`)                                            |
| Bind `greetingText` to a `Controller` + multi-line `TextInput` | `GreetingSection` (uses existing `FormField` if signature fits; else a `Controller` inline) |
| Bind `suggestedPrompts` to a `Controller` + `useFieldArray`-style add/remove list | `GreetingSection`                                                            |
| Render the "+ Add prompt" affordance                     | `GreetingSection`                                                                            |
| Render per-row delete affordance                         | `GreetingSection`                                                                            |
| Predicate gating / save shape composition                | `PalSheet.onSubmit` (NOT this component — keep the section pure form binding)                |
| Per-prompt trim on save                                  | `PalSheet.onSubmit` (per §4a rule 1; section passes raw strings through)                     |
| Reorder UI                                               | Out of scope (see §10)                                                                       |

Test surface (required testIDs for the E2E spec, all stable strings — no story IDs / Linear refs / TASK IDs in any visible string):

- `greeting-section` — the outer `View` of the section (mirrors `talent-section`)
- `form-field-greetingText` — the `TextInput` for greeting body (mirrors `form-field-name` / `form-field-systemPrompt` convention)
- `suggested-prompt-input-<idx>` — the editable `TextInput` for each prompt row, `idx` matching array index
- `suggested-prompt-remove-<idx>` — the per-row delete button
- `suggested-prompt-add-button` — the "+ Add prompt" affordance

The testID naming follows the existing convention in slice 1 PR (`talent-switch-<name>`, `form-field-<fieldName>`, `talent-item-<name>`). **(P)**

### 4d. PalSheet wiring contract

`PalSheet.tsx`'s validation schema (`:90-121`) is extended **only minimally**: add `greetingText: z.string().optional()` and `suggestedPrompts: z.array(z.string()).optional()` to the base schema. No `.min`, no `.max`, no per-row validation. **(P)** Rationale: matches "no length validation" intent decision; matches RHF + Zod patterns already used.

The mount point inside `PalSheet`'s JSX layout (`:392-417`) gets a `<GreetingSection />` inserted between `<SystemPromptSection />` and `<ColorSection />`. No other layout reflow. **(P)**

### 4e. Hard invariants

- **I8 (single editor save path)**: `PalSheet.onSubmit` is the only path that turns editor state into a `palData.greeting` payload sent to `palStore`. No other component (e.g., a Palshub detail sheet) gets a write path to `Pal.greeting` in this slice.
- **I9 (predicate parity with slice 1)**: the editor's "emit greeting?" predicate (§4a rule 1) is **identical** to slice 1's wire-side predicate (§4a rule 2 of `what.md`): emit iff `text.length > 0` OR at least one non-empty-after-trim prompt exists. Neither predicate trims `text`. The per-prompt trim happens only on prompts (which become chip labels). Verified by the §9a truth table mirroring slice 1's §9a truth table row-for-row on shared inputs. **(S4 fix.)**
- **I10 (no trimming of saved `text`)**: `pal.greeting.text` saved by the editor is the raw user-typed string when emitted. The chat-side render gate handles display-time visibility (architecture doc §8a). Matches slice 1's "syntactic only" passthrough rule for the wire→local rename.
- **I11 (per-prompt trim is destructive)**: prompts are trimmed on save and empty prompts are dropped. Unlike `text`, prompts are short discrete tokens and any leading/trailing whitespace would render as visible padding inside a chip; we treat that as accidental, not intentional. (See D7.)
- **I12 (clear-on-save round-trip)**: after Save with both editor fields blank, the next read from DB (and the next reopen of `PalSheet` for that pal) MUST observe `greetingText === ''` and `suggestedPrompts.length === 0`. The chat-side render MUST NOT show a greeting bubble or chips. The on-disk stored shape is the sentinel `{text:'', suggestedPrompts:[]}` (see D9); from every consumer's perspective this is indistinguishable from "no greeting". Verified by §6 scenario C.
- **I13 (PalSheet stays the single in-app editor)**: there is no PalsHub-detail edit surface in this slice. Downloaded PalsHub pals are edited through the same `PalSheet` they always have been; the only change is that the sheet now exposes greeting fields.

### 4f. What each component does (delta only)

| Component                         | Owns (new in this story)                                                                              | Does NOT                                                                            |
| --------------------------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `GreetingSection` (new)           | Render the text + prompt-list editor. Bind to RHF via `Controller`. Expose stable testIDs.            | Compose `pal.greeting`. Persist. Trim. Validate length. Reorder.                    |
| `PalSheet.onSubmit`               | Compose `palData.greeting` per §4a rule 1. Always set the key explicitly per §4a rule 2 (sentinel on clear). | Re-render. Validate (Zod does it).                                                  |
| `PalSheet` form init / reset      | Seed `greetingText` and `suggestedPrompts` from `pal.greeting`.                                       | Coerce types beyond the `?? ''` / `?? []` defaults.                                 |
| `PalRepository.createPal` / `updatePal` | **No change** — already JSON-stringifies `palData.greeting` (create) and gates on `!== undefined` then stringifies (update). | —                                                          |
| `palStore.createPal` / `updatePal` | **No change** — already forwards `palData.greeting` verbatim.                                        | —                                                                                   |
| `ChatView` greeting + chips render | **No change** — existing gates (line 853 for bubble, lines 1115-1116 for chips) consume the same `Pal.greeting` shape. | —                                                                |
| `SuggestedPromptsRow`             | **No change** — existing component renders prompts in array order with `suggested-prompt-chip-<idx>` testIDs. | —                                                                            |

---

## 5. Layer ownership (single-writer rule)

Slice 1 added one writer for `Pal.greeting` (the PalsHub download conversion). This slice adds the second:

| Field                       | Single writer(s)                                                                                                                                                       |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Pal.greeting` (in-memory)  | (C) `PalStore.createPal` / `updatePal` (via `addPal`). Sources of values: (1) `createLocalPalFromPalsHub` on download, (2) **NEW (P)** `PalSheet.onSubmit` on user save. |
| `local_pals.greeting` (DB)  | (C) `PalRepository.createPal` / `updatePal` — `LocalPal.safeStringify(palData.greeting)`. Source unchanged.                                                            |
| `PalFormData.greetingText`  | **NEW (P)** `GreetingSection`'s `Controller` for the text field; consumers read via `methods.getValues()` in `PalSheet.onSubmit`.                                       |
| `PalFormData.suggestedPrompts` | **NEW (P)** `GreetingSection`'s `Controller` for the prompt list (add / remove rows); read identically by `PalSheet.onSubmit`.                                       |

No multi-writer race: a Save is a single synchronous form submit; `palStore.updatePal` is awaited before the sheet closes. A concurrent re-download of the same pal from PalsHub is gated by today's "no re-download UI path" (slice 1 §4c, D5) — not introduced here.

**Architecture doc reconciliation**: §6 of `context/architecture/pals-and-talents.md` lists "`pal.greeting` ← edited via `PalSheet`" as a (C). That claim was speculative — the sheet had no UI for greeting before this story. After this slice lands, the (C) becomes true. The architecture doc string is **already correct** as-written; only the underlying code is being brought into alignment with the documented contract. See §11 drift.

**Deferred cleanups** (not in this story):

- **Convergent "drop the preservation gate" refactor (C2 follow-up)**: today both `pact` and `greeting` use empty-object sentinels (`{talents: []}`, `{text:'', suggestedPrompts:[]}`) to defeat the `if (updates.X !== undefined)` preservation gate in `PalRepository.updatePal`. A single repo-side cleanup would: (a) drop the `!== undefined` gates and treat `Partial<Pal>` with the key **present** as "write this value" (including explicit `undefined` → write NULL), and (b) remove both sentinels at the editor side. Both pact and greeting workarounds disappear in one PR. Out of scope here; tracked for a future story so two divergent escape hatches don't accrete. **(C2 fix.)**
- Reorder UI for prompts (drag handles, up/down buttons). Explicit non-goal.

---

## 6. Canonical scenarios

### A. Create a local pal with greeting + 2 prompts (happy path)

```
User actions in PalSheet:
  1. Tap "+" → Assistant
  2. Name = 'My Greeter'
  3. (selects a default model)
  4. System Prompt = '…'
  5. Greeting text input = 'Hi! What can I help with today?'
  6. Tap "+ Add prompt" → row 0 input = 'Summarize a webpage'
  7. Tap "+ Add prompt" → row 1 input = 'Brainstorm a name'
  8. Tap Save

  ↓ PalSheet.onSubmit  (§4a rule 1: predicate true via text.length > 0)

palData.greeting = {
  text:             'Hi! What can I help with today?',
  suggestedPrompts: ['Summarize a webpage', 'Brainstorm a name'],
}

  ↓ palStore.createPal → PalRepository.createPal  (existing — JSON-stringifies)

local_pals row:
  greeting: '{"text":"Hi! What can I help with today?","suggestedPrompts":["Summarize a webpage","Brainstorm a name"]}'

  ↓ user picks 'My Greeter' in chat, with a model loaded, empty session

ChatView renders:
  • GreetingBubble: "Hi! What can I help with today?"
  • SuggestedPromptsRow chips: [Summarize a webpage] [Brainstorm a name]
  • Tap [Summarize a webpage] → wrappedOnSendPress({type:'text', text:'Summarize a webpage'})
                              → user message sent automatically (per existing chip onSelect contract)
```

### B. Edit a downloaded PalsHub pal's greeting (round-trip case)

PR #741 already populated `pal.greeting` on a downloaded pal. After this slice, the user can change it.

```
Before edit:
  pal.greeting = { text: 'Hello from the cloud', suggestedPrompts: ['Try X'] }

User actions:
  1. Long-press pal → Edit
  2. PalSheet opens; form init (§4b) seeds:
       greetingText      = 'Hello from the cloud'
       suggestedPrompts  = ['Try X']
  3. Change text to 'Hello locally edited'
  4. Add a second prompt: 'Try Y'
  5. Tap Save

  ↓ PalSheet.onSubmit

palData.greeting = {
  text:             'Hello locally edited',
  suggestedPrompts: ['Try X', 'Try Y'],
}

  ↓ palStore.updatePal → PalRepository.updatePal  (key set, !== undefined → write)

local_pals row updated. `pal.source` still 'palshub', `pal.palshub_id` preserved
(neither field is touched by greeting editor — see §4f).
```

### C. Save with both fields cleared → sentinel write, observable "no greeting" (C1 round-trip)

```
Before edit:
  pal.greeting = { text: 'Old greeting', suggestedPrompts: ['Old prompt'] }
  (DB row: greeting = '{"text":"Old greeting","suggestedPrompts":["Old prompt"]}')

User actions:
  1. Edit → PalSheet opens with greetingText='Old greeting', suggestedPrompts=['Old prompt']
  2. Clear greetingText to ''
  3. Tap remove on the one prompt row → suggestedPrompts = []
  4. Tap Save

  ↓ PalSheet.onSubmit  (§4a rule 1 predicate: text='' (length 0) AND cleanedPrompts=[] → false)

palData.greeting = { text: '', suggestedPrompts: [] }   // SENTINEL — per §4a rule 2

  ↓ palStore.updatePal → PalRepository.updatePal  (gate: greeting !== undefined → true → safeStringify writes)

local_pals row: greeting = '{"text":"","suggestedPrompts":[]}'

  ↓ Re-read (e.g., app restart, or any subsequent palStore.getAllPals())

LocalPal.greetingObject → { text: '', suggestedPrompts: [] }
Pal.greeting           → { text: '', suggestedPrompts: [] }   // sentinel persists in memory

  ↓ user opens chat with this pal (empty session, model loaded)

ChatView:
  • Line 853 gate: activePal?.greeting?.text → '' (falsy) → NO bubble rendered
  • Line 1115 gate: suggestedPrompts && suggestedPrompts.length > 0 → 0 (falsy) → NO chips
  • Empty-state placeholder shown — visually identical to a never-had-greeting pal.

  ↓ Reopen PalSheet for this pal

§4b init:
  greetingText      = pal.greeting?.text ?? ''               → ''   (raw value already '')
  suggestedPrompts  = pal.greeting?.suggestedPrompts ?? []   → []   (raw value already [])

Editor shows blank fields. The user saw "Save → close → reopen → both fields blank" — round-trip closes. (I12)
```

### D. Save with whitespace-only text + valid prompts → emit greeting with raw text

```
User actions:
  1. greetingText = '   '       (three spaces, intentional or accidental)
  2. suggestedPrompts row 0 = 'Tell me a joke'
  3. Save

  ↓ PalSheet.onSubmit  (§4a rule 1: text='   ' (length 3 > 0) → predicate true)

palData.greeting = {
  text:             '   ',                  // raw, per I10
  suggestedPrompts: ['Tell me a joke'],
}

  ↓ chat opens

ChatView:
  • GreetingBubble: line 853 gate = '   ' && modelLoaded.
    Per existing JS truthiness, '   ' is truthy → bubble renders with empty visual content.
    This matches slice-1's identical behaviour for the same wire input (slice 1 §9a row "text='', suggested_prompts=['a']" rendered with empty text). Predicate parity preserved (I9).
  • Chips render normally.
```

Note: the visible-empty-bubble behaviour for whitespace-only text already exists today for PalsHub-sourced pals carrying the same payload (slice 1 §9c). Tightening the chat-side gate to also reject whitespace-only text is a follow-up; see §11 below.

### E. Save with only prompts, no text → emit greeting with empty text

```
User actions:
  1. greetingText = ''           (never typed anything)
  2. suggestedPrompts row 0 = 'Hello'
  3. Save

  ↓ PalSheet.onSubmit  (text='' length 0, cleanedPrompts=['Hello'] length 1 → predicate true via prompts)

palData.greeting = {
  text:             '',
  suggestedPrompts: ['Hello'],
}

  ↓ chat opens
ChatView:
  • GreetingBubble NOT rendered (line 853 gate: '' is falsy)
  • Chips render
```

### F. Edit a pal that has no greeting today, leave fields blank → no-op save (S4 verified)

```
Before edit:
  pal.greeting = undefined

User actions:
  1. Edit → PalSheet opens with greetingText='', suggestedPrompts=[]
  2. (changes only the description, not the greeting fields)
  3. Save

  ↓ PalSheet.onSubmit  (text='' length 0, cleanedPrompts=[] → predicate false → sentinel write)

palData.greeting = { text: '', suggestedPrompts: [] }   // sentinel
  ↓ palStore.updatePal  (gate passes, safeStringify writes the sentinel)

DB row: greeting = '{"text":"","suggestedPrompts":[]}'

Observable effect for the user: none.
  • Reopen pal in editor → fields still blank (§4b init).
  • Open chat → no bubble, no chips (line 853 / 1115 gates falsy on sentinel).
  • Re-edit the description again → still no spurious greeting.

The sentinel write is an internal artifact, NOT observable as a "greeting now exists" state.
This is the trade-off explicit in D9: simpler than refactoring the repo gate, no user-visible regression.

Equivalence with the slice-1 wire path for the analogous PalsHub-sourced input
(`{text: '   '}` with chips): slice 1's wire predicate emits greeting because text.length > 0;
slice 2's editor predicate on the same input also emits greeting because text.length > 0.
**Predicate symmetry holds.** (I9, S4 fix.)
```

### G. E2E spec contract (happy-path round-trip)

The spec drives a full create-with-greeting → chat → assert flow. Lives at `e2e/specs/features/pal-greeting.spec.ts` (filename suggested — implementer picks; no story IDs in the path or test name). Page-object surface required:

```
PalSheetPage (additions to e2e/pages/PalSheetPage.ts):
  setGreetingText(text: string): Promise<void>     // scrolls to form-field-greetingText, fills, dismisses keyboard
  addSuggestedPrompt(text: string): Promise<void>  // taps suggested-prompt-add-button, fills last row's input
  removeSuggestedPromptAt(idx: number): Promise<void>   // taps suggested-prompt-remove-<idx>
  // Existing setName(), setSystemPrompt(), submit() unchanged.

ChatPage / Selectors  (no new page-object methods required; just selectors):
  Selectors.chat.greetingBubble        = byTestId('greeting-bubble')
  Selectors.chat.suggestedPromptsRow   = byTestId('suggested-prompts-row')
  Selectors.chat.suggestedPromptChip   = (idx) => byTestId(`suggested-prompt-chip-${idx}`)

Selectors.palSheet  (additions):
  greetingTextInput        = byTestId('form-field-greetingText')
  suggestedPromptAddButton = byTestId('suggested-prompt-add-button')
  suggestedPromptInput     = (idx) => byTestId(`suggested-prompt-input-${idx}`)
  suggestedPromptRemove    = (idx) => byTestId(`suggested-prompt-remove-${idx}`)
```

The spec flow:

```
1. Download + load a tiny model (reuse downloadAndLoadModel from helpers/model-actions;
   use the smallest available — Qwen3-0.6B or similar; spec must not pin to the
   tool-use model from talent-tool-use.spec.ts since this spec does not need tool calls).
2. Navigate to Pals → tap + → Assistant.
3. palSheetPage.setName('Greeter')
4. palSheetPage.setGreetingText('Hi from E2E')
5. palSheetPage.addSuggestedPrompt('Send a test message')
6. palSheetPage.submit()
7. Return to Chat (the app-restart trick from talent-tool-use.spec.ts:126-130 is fine).
   Re-load model. Select Greeter via pal picker. Reset chat.
8. ASSERT browser.$(Selectors.chat.greetingBubble) is displayed; its text contains 'Hi from E2E'.
9. ASSERT browser.$(Selectors.chat.suggestedPromptChip(0)) is displayed.
10. Tap chip 0 → wait for a user-message bubble to appear with text 'Send a test message'.
    Optionally wait for AI response (best-effort, like talent-tool-use spec — model
    non-determinism makes hard assertions unsafe).
11. ASSERT chips and greeting bubble are no longer visible (post-message gate).
```

Notes on the spec:

- Use `Selectors.chat.suggestedPromptChip(0)` directly; the chip's `onSelect` already routes through `wrappedOnSendPress` to send the prompt as the user message (`ChatView.tsx:1126-1128`). No new component contract needed.
- No story IDs / FOU- refs / Linear refs in the spec title, the test description, or the page-object method names — only descriptive English. **(P)**
- Skip-conditions: if the device cannot download the model in the budget, fail loudly (don't silently skip); the test runs in the same `e2e/scripts/run-e2e.ts` matrix as other specs.

---

## 7. State signals

Not applicable.

---

## 8. Decisions

- **D6** — Flat fields on `PalFormData` (`greetingText`, `suggestedPrompts`), not a nested `greeting: {…}` object. Rationale: React Hook Form's `Controller` + `useFieldArray` work cleanly on top-level keys, every existing `PalFormData` field is flat, and the nested shape is rebuilt at exactly one place (`PalSheet.onSubmit`). Adding nesting would invite shape-drift between the form and the persisted shape.
- **D7** — Per-prompt `.trim()` + drop-empty on save. Rationale: prompts are short discrete strings that render inside chips; trailing whitespace would render as visible padding and an empty row in the UI is almost certainly user error (they tapped Add but never typed). The chat-side render uses array length, so empty strings would still produce empty chips. Trim + filter is the only contract that makes "add a row and don't fill it" a no-op.
- **D8** — `greetingText` saved raw (no trim on the stored value AND no trim in the predicate). Rationale: greeting body is prose; an author might legitimately want a trailing newline, two paragraphs separated by blank lines, or a leading symbol. Trimming would silently mutate authorial intent. Critically, **the predicate also uses raw `text.length`**, identical to slice 1's wire-side predicate `(text?.length ?? 0) > 0`. This guarantees a PalsHub-sourced pal with `text: '   '` and chips that survived slice 1's import will not be silently dropped if the user no-op-edits and saves through slice 2's editor. (S4 fix; previous draft trimmed in the predicate and broke this symmetry.)
- **D9** — Empty-object sentinel `{text:'', suggestedPrompts:[]}` for the clear case, convergent with the existing `pact` workaround `{talents: []}`. Rationale: `PalRepository.updatePal` uses `if (updates.greeting !== undefined)` as a preservation gate (`PalRepository.ts:295`). Setting `palData.greeting = undefined` SKIPS the block → stale value preserved → bug. Setting `palData.greeting = null` would pass the gate AND `safeStringify(null)` returns `undefined` (line 213-216), which writes NULL — works on disk but `null` is a type lie on `Partial<Pal>`. The sentinel `{text:'', suggestedPrompts:[]}` writes valid JSON that round-trips through `greetingObject`, and every read consumer (chat render at line 853/1115, editor re-seed §4b) treats it as visually equivalent to "no greeting". Trade-off: the on-disk shape diverges from a true NULL column; acceptable per I12. The convergent unification (drop the gate everywhere) is the right long-term fix and is captured as a deferred cleanup in §5 (C2 fix).
- **D10** — Mount `GreetingSection` between `SystemPromptSection` and `ColorSection`. Rationale: greeting is an authorial UI scaffolding concept; it pairs conceptually with the system prompt (both are author voice). Color is a visual identity choice, Talents is a capability declaration — both feel adjacent but downstream of the author-voice fields. The order `Name → Description → Model → Parameters? → System Prompt → Greeting → Color → Talents → Generation Settings?` matches the principle "what the pal says before what it can do."
- **D11** — No reorder UI for prompts in v1. Rationale: explicitly out of scope per intent ("recommend skipping unless trivial"). Add + remove + edit cover the user need; reorder can ship as a follow-up if telemetry / feedback demands it.
- **D12** — No length caps, no per-row validation. Rationale: explicitly out of scope per intent ("no length validation"). Server does not enforce one; the chat-side render handles empty gracefully; chip text auto-wraps to two lines via existing `SuggestedPromptsRow` styling.
- **D13** — Spec lives in `e2e/specs/features/` (new file) rather than augmenting `talent-tool-use.spec.ts`. Rationale: the existing tool-use spec depends on a 1.7B tool-use model and a contrived prompt to provoke a tool call; greeting + chips have nothing to do with tool calls and benefit from a smaller, faster, deterministic spec.

---

## 9. Edge cases

### 9a. Predicate truth table (mirror of slice 1 §9a — S4 alignment)

The predicate is `text.length > 0 OR cleanedPrompts.length > 0` where `cleanedPrompts = prompts.map(trim).filter(nonEmpty)`. Text is **never** trimmed for the predicate or for storage.

| Editor state                                                   | `text.length`  | `cleanedPrompts` | Predicate | Saved `pal.greeting`                                 |
| -------------------------------------------------------------- | -------------- | ---------------- | --------- | ---------------------------------------------------- |
| `text=''`, `prompts=[]`                                        | 0              | `[]`             | false     | sentinel `{text:'', suggestedPrompts:[]}` (D9)       |
| `text='   '`, `prompts=[]`                                     | 3              | `[]`             | true      | `{ text: '   ' }` (I10; mirrors slice 1 §9c)         |
| `text='Hi'`, `prompts=[]`                                      | 2              | `[]`             | true      | `{ text: 'Hi' }`                                     |
| `text='Hi'`, `prompts=['a']`                                   | 2              | `['a']`          | true      | `{ text: 'Hi', suggestedPrompts: ['a'] }`            |
| `text=''`, `prompts=['Tell joke']`                             | 0              | `['Tell joke']`  | true      | `{ text: '', suggestedPrompts: ['Tell joke'] }`      |
| `text='   '`, `prompts=['a']`                                  | 3              | `['a']`          | true      | `{ text: '   ', suggestedPrompts: ['a'] }` (I10)     |
| `text='Hi'`, `prompts=['', '  ']`                              | 2              | `[]`             | true      | `{ text: 'Hi' }` (I11 drops empty rows)              |
| `text=''`, `prompts=['', '  ']`                                | 0              | `[]`             | false     | sentinel (D9)                                        |
| `text='Hi'`, `prompts=['  a  ', 'b']`                          | 2              | `['a', 'b']`     | true      | `{ text: 'Hi', suggestedPrompts: ['a', 'b'] }` (I11) |
| `text='\n\n'`, `prompts=['a']`                                 | 2              | `['a']`          | true      | `{ text: '\n\n', suggestedPrompts: ['a'] }` (I10)    |

Cross-check against slice 1 §9a: same input shapes produce same emit decisions and same `text` values. Per-prompt trim is editor-only (slice 1 has nothing to trim — the wire-side `suggested_prompts` array is passed verbatim).

### 9b. Loading a pal where saved `greeting.suggestedPrompts` contains an empty string

Saved DB rows produced **before this slice** (slice 1's PalsHub conversion is the only writer) cannot contain `''` entries — slice 1's wire-side mapping pulls `suggested_prompts` array verbatim, and the Palshub server has its own validation. After this slice, the editor's I11 trim+filter ensures no empty entries are ever saved. So loading an empty-string entry into the editor is unreachable in practice. If it happens (e.g., hand-edited DB or future writer), the load path `pal.greeting?.suggestedPrompts ?? []` still passes `''` through to the editor row; the user sees an empty `TextInput` for that row and can either fill it or remove it. Save will drop it via I11. No special handling required.

### 9c. Cancel button on the sheet

`PalSheet.handleClose` calls `resetForm()` (`PalSheet.tsx:190-193`), which already re-seeds form values from the original `pal` prop. After this slice, `resetForm` also re-seeds `greetingText` and `suggestedPrompts` per §4b. Cancelling discards in-flight greeting edits identically to how it discards in-flight name / system-prompt edits today. No sentinel write occurs on cancel — only on Save.

### 9d. Sheet re-opened on a different pal mid-edit

The existing `useEffect` deps `[pal, methods]` (`PalSheet.tsx:165`) re-run `methods.reset(formData)` whenever the `pal` prop changes. The new greeting fields are included in `formData` per §4b, so switching from pal A to pal B mid-edit cleanly re-seeds greeting too. No race.

### 9e. PalsHub re-download (deferred from slice 1 D5)

This slice does not change the re-download story. There is still no UI to re-download an already-downloaded pal. If a future story adds one, the design must decide whether re-download overwrites a user-edited greeting or preserves it. That decision belongs to that future story, not this one.

### 9f. Empty `suggestedPrompts` array vs missing key

Slice 1's wire-mapping omits the `suggestedPrompts` key when there are no prompts (`{ text: 'Hi' }`, not `{ text: 'Hi', suggestedPrompts: [] }`). This slice follows the same rule (§4a rule 1: "set only when cleanedPrompts.length > 0"). The chat-side render at `ChatView.tsx:1115` checks `.length > 0`, so both shapes render identically — but consistency on save reduces serialised-row noise. Exception: the **sentinel** `{text:'', suggestedPrompts:[]}` (clear case) intentionally includes `suggestedPrompts: []` as part of the convergent shape with `pact`'s `{talents: []}`; the chat-side gate is permissive of both.

### 9g. Existing pal saved before this slice ever gets re-saved

A pal whose existing DB row has `greeting=NULL` re-opens in the editor with both fields empty (`pal.greeting?.text ?? ''` → `''`). Saving without filling them in writes the sentinel (§4a rule 2). DB row goes from `NULL` to `'{"text":"","suggestedPrompts":[]}'`. No observable user-facing change (chat still shows no bubble/chips, editor still shows blank fields next reopen). The shape-change on disk is benign — the export DTO already round-trips greeting JSON verbatim (slice 1 §9g), and re-imports of the sentinel reproduce the same blank-editor / no-render behaviour.

---

## 10. What this doc is NOT

- Not a "downloaded-pal edit gating" change — downloaded pals were already editable through `PalSheet`; this slice merely exposes greeting fields.
- Not a reorder UI for prompts. Explicit non-goal (D11).
- Not a length-validation policy. Explicit non-goal (D12).
- Not a markdown / rich-text greeting body — the chat-side `GreetingBubble` renders plain text.
- Not a redesign of `ChatView`'s render gates. The whitespace-text empty-bubble behaviour in §6 scenario D is an existing issue (slice 1 §9c); a follow-up is promised in §11.
- Not a new l10n strategy — only `src/locales/en.json` is edited (Weblate handles other locales per CLAUDE.md memory).
- Not a refactor of `PalRepository`'s `!== undefined` preservation gate — that's the convergent cleanup deferred in §5 (S3/C2 follow-up).
- Not a new spec for the existing PalsHub-downloaded greeting path — that round-trip was implicitly covered in slice 1; this spec covers the editor round-trip.

---

## 11. Drift findings (architecture doc → code) + follow-ups

Drift check against `context/architecture/pals-and-talents.md` (post-slice-1 absorbed state):

- **No major drift.**
- **Minor reconciliation** (already correct in the doc; this slice brings code into alignment):
  - §6 single-writer table states `pal.greeting ← edited via PalSheet`. Before this slice, the PalSheet had no UI for greeting; the docstring was aspirational / inherited from when `Pal.greeting` was first added. After this slice, the (C) is finally true in code. The §6 entry can be tightened from `edited via PalSheet` to `edited via PalSheet → GreetingSection` if the implementer wants component-level granularity (mirrors the existing `pal.pact ← edited via TalentSection in PalSheet` granularity).
- Slice 1's WHAT noted that §8a still contains a (?) about removing the model-load gate on the greeting bubble. That (?) is NOT in this slice's scope (intent does not request a gate change). The (?) remains open as a deferred follow-up; this WHAT does not touch the gate either.

**Promised follow-ups (not in this PR):**

1. **(S3 fix)** Tighten `ChatView.tsx:853` greeting-bubble gate from truthy-text to `text.trim().length > 0` so whitespace-only `text` does not render an empty visual bubble (today's behaviour for BOTH the slice-1 wire path and this slice's editor path on `text='   '` + chips). The implementer of this slice MUST open a follow-up issue with reproducer = "scenario D above" and link it from the PR description. No code change in this slice; tracked separately so the chat-side render policy can be revisited holistically (the same gate decision affects export/import round-trips and any future "greeting-only pal" content type).
2. **(C2 fix)** Drop `PalRepository.updatePal`'s `!== undefined` preservation gate (currently at `:292` for pact, `:295` for greeting), let `Partial<Pal>` semantics carry "key present → write this value" (including `undefined` → write NULL). Removes both the `pact` sentinel `{talents: []}` and the `greeting` sentinel `{text:'', suggestedPrompts:[]}`. Single-PR refactor; out of scope here so this story stays focused.

---

## What this is, in one sentence

A new `GreetingSection` form section in `PalSheet`, a flat-shape addition to `PalFormData`, an extended save predicate in `PalSheet.onSubmit` that **mirrors slice 1's wire predicate exactly** (raw `text.length`, per-prompt trim), a **convergent empty-object sentinel** for the clear case, and one new E2E spec — to make `Pal.greeting.text` + `Pal.greeting.suggestedPrompts` author-editable for all pal sources, no new contract beyond what slice 1 + the existing chat-side render gates already define.

---

## Review History — Round 1

| # | Severity | Critic finding (short) | Resolution | Where |
| - | -------- | --------------------- | ---------- | ----- |
| 1 | CONCERN  | C1: D9's "always set greeting explicitly to `undefined`" does not clear the DB row (gate at `PalRepository.ts:295` skips the block; `safeStringify(null)`/`(undefined)` both return `undefined`). Implementer-punt is not a contract. Pin a concrete convergent sentinel and verify the round-trip. | **FIXED** | §4a rule 2 rewritten with **empty-object sentinel** `{text:'', suggestedPrompts:[]}` (matches `pact`'s `{talents:[]}` workaround at `PalSheet.tsx:244-252`). New invariant **I12** ("clear-on-save round-trip") added. **§6 scenario C** rewritten to walk the full round-trip: clear → save → DB row → re-read (memory + reopen) → chat render. D9 rationale extended to document why `undefined` and `null` both fail. §1a now explicitly states the `safeStringify` line-numbered behaviour as load-bearing context. Trade-off (stored shape diverges from true NULL) made explicit in D9 and I12. |
| 2 | CONCERN  | C2: Two divergent workarounds for the same gate (`pact` uses one shape, `greeting` would use another). Pick the convergent pattern; document the one-PR cleanup that unwinds both. | **FIXED** | §4a rule 2 + D9 explicitly call out convergence with `pact`'s `{talents:[]}` pattern (same shape family: empty-object sentinel keyed on the "list-of-items" field). §5 deferred-cleanups section renamed and extended with **(C2 follow-up)** documenting the single-PR cleanup that drops the `!== undefined` gate and removes both sentinels at once. §11 follow-up list calls it out again as "(C2 fix)". |
| 3 | SUGGESTION | S3: Whitespace-only render-gate carve-out has no follow-up owner. Promise a follow-up issue. | **FIXED** | §11 now has a **Promised follow-ups** subsection. Item 1 (S3) commits the implementer of this slice to opening a follow-up issue with the scenario-D reproducer, linked from the PR description. Item 2 (C2) tracks the convergent repo-side cleanup. Both are explicit, owned ("implementer of this slice MUST open"), and out of scope for the in-flight PR. |
| 4 | CONCERN  | S4: Editor predicate trims, wire predicate doesn't — asymmetry breaks no-op-save contract for PalsHub-sourced pals with `text: '   '` + chips. Drop the trim in the editor's text predicate to match slice 1. | **FIXED** | §4a rule 1 now uses `text = data.greetingText ?? ''` (un-trimmed) for the predicate. Predicate becomes `text.length > 0 OR cleanedPrompts.length > 0` — character-identical to slice 1's `(text?.length ?? 0) > 0 OR (suggested_prompts?.length ?? 0) > 0` mapping. Per-prompt trim stays (chip rationale). **I9** rewritten as "identical to slice 1's wire-side predicate". **I12** moved to "clear-on-save round-trip" (was the old predicate-non-symmetry note; that asymmetry no longer exists). **§9a truth table** rebuilt: row for `text='   '`, `prompts=[]` flips from `predicate=false → undefined` to `predicate=true → {text:'   '}` (matches slice 1 §9c). **§6 scenario F** rewritten as the explicit symmetry assertion: same input shape, same predicate result, same emit decision. **D8** rationale extended to call out the S4 fix and the predicate symmetry guarantee. |

All four findings addressed; no REJECTED or DEFERRED. Predicate symmetry with slice 1 is now I9 (load-bearing). Round-trip on the clear case is now I12 (load-bearing). Convergence with `pact` workaround is documented in D9 and §5. Follow-up owners are named in §11. Re-ran the Quality Checklist: zero `(?)` markers, all `(D)` rationaled, single-writer table unchanged, scenarios cover happy + edit + clear-round-trip + whitespace + only-prompts + no-op-symmetry + E2E. Doc length under 600 lines.
