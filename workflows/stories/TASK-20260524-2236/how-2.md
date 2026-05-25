# Implementation Plan: Editable greeting + suggested prompts in PalSheet

**Purpose**: executable worklist that lands `what-2.md`. Adds the second writer for `Pal.greeting` (in-app editor in `PalSheet`) and the supporting `GreetingSection` form section, l10n keys, schema fields, predicate-driven save composition, and one new E2E spec. The chat-side render path and the wire-boundary conversion (PR #741, slice 1) are untouched and consume the editor output verbatim.

This file lives at `workflows/stories/TASK-20260524-2236/how-2.md`.

---

## Metadata

- **Task ID**: TASK-20260524-2236 (slice 2)
- **Worktree**: `./worktrees/TASK-20260524-2236`
- **Branch**: `feature/TASK-20260524-2236`
- **Native Changes**: NO
- **Visual Confirmation**: YES
- **Intent Brief**: `./workflows/stories/TASK-20260524-2236/intent-brief.md`
- **WHAT (slice 1, merged)**: `./workflows/stories/TASK-20260524-2236/what.md`
- **WHAT (this slice)**: `./workflows/stories/TASK-20260524-2236/what-2.md`
- **Architecture doc updated**: `./context/architecture/pals-and-talents.md`
- **Status**: draft

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1: l10n keys for greeting section | DONE | 64b9456 | en.json only — Weblate owns the rest |
| Step 2: PalFormData fields | DONE | 2e1be7b | additive — `greetingText`, `suggestedPrompts` |
| Step 3: GreetingSection component (+ styles + barrel) | DONE | c3add34 | mirrors ColorSection layout |
| Step 4: PalSheet wiring (schema, init, reset, mount) | DONE | 62dd59d | between SystemPromptSection and ColorSection |
| Step 5: PalSheet.onSubmit predicate + sentinel | DONE | 1f3d379 | mirror of slice 1 wire predicate |
| Step 6: GreetingSection unit tests | DONE | e799d7b | mirror TalentSection.test.tsx |
| Step 7: PalSheet integration tests for save predicate | pending (tester) | - | covers §6 A/C/D/E/F |
| Step 8: E2E spec — greeting round-trip | pending (tester) | - | new file under e2e/specs/features/ |
| Step 9: Selectors + PalSheetPage page-object additions | pending (tester) | - | greetingTextInput, addSuggestedPrompt etc. |
| Step 10: Architecture doc updated | DONE | dev-team repo | tighten §6 entry for `pal.greeting` |

### Post-merge follow-ups (not gated by Progress Tracking)

These are real commitments from WHAT §11 that the implementer of this slice owns, but they happen after the PR merges and so are tracked separately from the in-PR Progress Tracking table above.

| Item | Status | Notes |
| --- | --- | --- |
| File the whitespace-only render-gate follow-up issue | pending | references slice 1 §9c AND slice 2 §6 scenario D |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/locales/en.json` | edit (add `palSheet.greeting` block) | §4c, §4d |
| `src/components/PalsSheets/types.ts` | edit (add 2 optional fields to `PalFormData`) | §1b |
| `src/components/PalsSheets/GreetingSection/GreetingSection.tsx` | add | §4c |
| `src/components/PalsSheets/GreetingSection/styles.ts` | add | §4c |
| `src/components/PalsSheets/GreetingSection/index.ts` | add | §4c |
| `src/components/PalsSheets/PalSheet.tsx` | edit (schema, init/reset, mount, onSubmit composition) | §4a, §4b, §4d |
| `src/components/PalsSheets/__tests__/GreetingSection.test.tsx` | add | §4c, §6 |
| `src/components/PalsSheets/__tests__/PalSheet.test.tsx` | edit (add greeting save-path cases) | §4a, §6.A/C/D/E/F |
| `e2e/helpers/selectors.ts` | edit (add greeting + chip selectors under `palSheet` + `chat`) | §6.G |
| `e2e/pages/PalSheetPage.ts` | edit (add `setGreetingText`, `addSuggestedPrompt`, `removeSuggestedPromptAt`) | §6.G |
| `e2e/specs/features/pal-greeting.spec.ts` | add | §6.G |
| `context/architecture/pals-and-talents.md` | edit (§6 row tightened) | §5 reconciliation, §11 |

---

## Implementation Steps

Each step is atomic, references WHAT sections, and lists verification commands. No step contains design decisions — every contract lives in `what-2.md`.

### Step 1: Add l10n keys for the greeting editor

**Implements**: WHAT §4c (section labels), §4d (no validation copy).

**Files**:

- `src/locales/en.json` — add a `greeting` block inside `components.palSheet`.

**Approach**: Extend the existing `components.palSheet` block with a sibling object:

```jsonc
"greeting": {
  "sectionLabel": "Greeting",
  "textLabel": "Greeting message",
  "textPlaceholder": "What should this pal say on an empty chat?",
  "suggestedPromptsLabel": "Suggested prompts",
  "addPromptButton": "+ Add prompt",
  "promptPlaceholder": "A short prompt for the chip",
  "removePromptLabel": "Remove prompt"
}
```

No placeholders / interpolation, so `validate-l10n.js` passes trivially. Only `en.json` is edited; Weblate manages other locales (see CLAUDE.md memory). All strings are user-facing English with no story IDs, no FOU-, no TASK-, no internal markers.

**Verification**:

- `node scripts/validate-l10n.js` passes
- `yarn typecheck` passes (l10n types regenerated from `typeof en`)

---

### Step 2: Extend `PalFormData` with greeting fields

**Implements**: WHAT §1b.

**Files**:

- `src/components/PalsSheets/types.ts` — add two optional flat fields.

**Approach**: Add `greetingText?: string` and `suggestedPrompts?: string[]` as flat top-level keys on `PalFormData`. Do not nest under `greeting`. Per WHAT D6, RHF flat shape is the load-bearing decision.

**Verification**:

- `yarn typecheck` passes

---

### Step 3: Create `GreetingSection` component

**Implements**: WHAT §4c, §4f.

**Files**:

- `src/components/PalsSheets/GreetingSection/GreetingSection.tsx` (new)
- `src/components/PalsSheets/GreetingSection/styles.ts` (new)
- `src/components/PalsSheets/GreetingSection/index.ts` (new — barrel re-exports `GreetingSection`)

**Approach**: Mirror `ColorSection/` directory layout. Component shape:

- Outer `<View testID="greeting-section">` with a `SectionDivider` labelled from `l10n.components.palSheet.greeting.sectionLabel`.
- A `Controller name="greetingText"` rendering a multiline `TextInput` from `../../TextInput` (same component the existing `FormField` uses) with `testID="form-field-greetingText"`. Use the label from `greeting.textLabel`, placeholder from `greeting.textPlaceholder`.
- A `Controller name="suggestedPrompts"` rendering a vertical list of rows. Each row contains:
  - a single-line `TextInput` with `testID={`suggested-prompt-input-${idx}`}` bound to `value[idx]`, calling `onChange([...value.slice(0,idx), text, ...value.slice(idx+1)])` on change.
  - a remove `Button` (use the same Paper `IconButton` or text-mode Button used elsewhere in the project for consistency) with `testID={`suggested-prompt-remove-${idx}`}` and `accessibilityLabel={l10n…greeting.removePromptLabel}` that calls `onChange(value.filter((_, i) => i !== idx))`.
- An "Add prompt" Paper `Button` mode="text" (icon "+") below the list, `testID="suggested-prompt-add-button"`, calls `onChange([...(value ?? []), ''])`.

Component is a pure form-binding (per §4f) — it does not trim, validate, gate, or compose `pal.greeting`. All save-shape logic lives in `PalSheet.onSubmit`.

**Verification**:

- `yarn typecheck` passes
- `yarn lint src/components/PalsSheets/GreetingSection/` passes

---

### Step 4: Wire `GreetingSection` into `PalSheet`

**Implements**: WHAT §4b (form init / reset), §4d (schema, mount).

**Files**:

- `src/components/PalsSheets/PalSheet.tsx`

**Approach**:

1. Extend `validationSchema` (line 90) with `greetingText: z.string().optional()` and `suggestedPrompts: z.array(z.string()).optional()`. No `.min`, no `.max` (per WHAT D12).
2. Extend `INITIAL_STATE` (line 45) with `greetingText: ''` and `suggestedPrompts: []`.
3. Extend the `useEffect` form init (line 147) and `resetForm` (line 167) `formData` objects with:
   - `greetingText: pal.greeting?.text ?? ''`
   - `suggestedPrompts: pal.greeting?.suggestedPrompts ?? []`
   (Per §4b rule 3, this seeds the editor identically from both `undefined` greeting and the empty-object sentinel.)
4. Import `GreetingSection` from `./GreetingSection` and mount `<GreetingSection />` in the JSX between `<SystemPromptSection …/>` (line 392) and `<ColorSection />` (line 398). No other layout changes (per WHAT D10).

**Verification**:

- `yarn typecheck` passes
- `yarn lint src/components/PalsSheets/PalSheet.tsx` passes

---

### Step 5: Compose `palData.greeting` in `PalSheet.onSubmit`

**Implements**: WHAT §4a (rule 1 predicate, rule 2 sentinel), §4e (I8/I9/I10/I11/I12).

**Files**:

- `src/components/PalsSheets/PalSheet.tsx` (lines 222-294 — `onSubmit`)

**Approach**: After the existing `pact` composition block (around line 240-252), add a parallel `greeting` composition. The predicate and sentinel are non-negotiable:

```ts
const greetingText = data.greetingText ?? '';
const cleanedPrompts = (data.suggestedPrompts ?? [])
  .map(p => p.trim())
  .filter(p => p.length > 0);
const hasGreeting = greetingText.length > 0 || cleanedPrompts.length > 0;
const greeting: Pal['greeting'] = hasGreeting
  ? cleanedPrompts.length > 0
    ? {text: greetingText, suggestedPrompts: cleanedPrompts}
    : {text: greetingText}
  : {text: '', suggestedPrompts: []};
```

Then include `greeting` on the `palData: Partial<Pal>` object (around line 256-275). Notes:

- `greetingText` is **never** trimmed for the predicate or for storage (I10).
- The sentinel `{text: '', suggestedPrompts: []}` is always set when both fields are empty — convergent with the existing `pact` `{talents: []}` workaround at lines 244-252 (I12, D9).
- When prompts exist but text is empty, `text` is still saved as `''` (mirrors slice 1 §9a row "text='', suggested_prompts=['a']").
- When the predicate is true and no prompts exist, the `suggestedPrompts` key is omitted (matches slice 1 §9f "empty array vs missing key").

No new types are needed — `Pal['greeting']` is the target shape from `src/types/pal.ts:122-136`.

**Verification**:

- `yarn typecheck` passes
- `yarn lint src/components/PalsSheets/PalSheet.tsx` passes

---

### Step 6: Unit tests for `GreetingSection`

**Implements**: WHAT §4c, §4f (component-purity boundary).

**Files**:

- `src/components/PalsSheets/__tests__/GreetingSection.test.tsx` (new)

**Approach**: Mirror `TalentSection.test.tsx` shape (already in the codebase). Use the same `FormWrapper` pattern (RHF + `FormProvider` + L10nContext.Provider). Cover:

1. Rendering: section container (`greeting-section`), text input (`form-field-greetingText`), add-prompt button (`suggested-prompt-add-button`).
2. Initial state from `defaultValues`: pre-seeded `greetingText` shows in the input; pre-seeded `suggestedPrompts` render N rows with correct values and testIDs.
3. User interactions:
   - Typing in `form-field-greetingText` updates form state.
   - Tapping `suggested-prompt-add-button` appends an empty row (form state grows by one `''`).
   - Editing `suggested-prompt-input-0` updates `suggestedPrompts[0]`.
   - Tapping `suggested-prompt-remove-1` drops that row (length decreases, remaining items re-indexed in form state).
4. Component does NOT trim or filter on its own — typing `'  '` into a row leaves `'  '` in form state (trim happens in `onSubmit` only).

No mocks beyond what `TalentSection.test.tsx` already does.

**Verification**:

- `yarn test src/components/PalsSheets/__tests__/GreetingSection.test.tsx` passes

---

### Step 7: Integration tests for `PalSheet` save predicate

**Implements**: WHAT §4a, §4b, §6 scenarios A, C, D, E, F.

**Files**:

- `src/components/PalsSheets/__tests__/PalSheet.test.tsx` (edit — add a `describe('Greeting save predicate', …)` block)

**Approach**: Add cases that assert the `palData.greeting` shape passed to `palStore.createPal` / `palStore.updatePal`. Use the existing `renderPalSheet`, `createBasicPal`, `createExistingPal` helpers. The L10nContext provider and palStore mock are already set up. Cases (one test each):

1. §6.A — create new pal, set `greetingText='Hi'` (via `fireEvent.changeText` on `form-field-greetingText`), add two prompts ('a', 'b'), Save → assert `palStore.createPal` called with `greeting: {text: 'Hi', suggestedPrompts: ['a', 'b']}`.
2. §6.C — `createExistingPal({greeting: {text: 'Old', suggestedPrompts: ['p']}})`, clear text input, remove the prompt row, Save → assert `palStore.updatePal` called with `greeting: {text: '', suggestedPrompts: []}` (the sentinel).
3. §6.D — set `greetingText='   '` (three spaces), add one prompt, Save → assert `greeting: {text: '   ', suggestedPrompts: ['<prompt>']}`. Asserts the predicate uses raw `text.length` (I9, I10).
4. §6.E — only prompts, no text → assert `greeting: {text: '', suggestedPrompts: ['Hello']}`.
5. §6.F — `createExistingPal()` with no greeting, change only description, Save → assert `greeting: {text: '', suggestedPrompts: []}` (sentinel write; harmless per I12).
6. Form init round-trip — `createExistingPal({greeting: {text: 'Hello', suggestedPrompts: ['x', 'y']}})` → assert `form-field-greetingText` has value 'Hello' and rows 0/1 have values 'x' and 'y'.
7. Trim + drop-empty (I11) — set `greetingText='Hi'`, add prompts `['  a  ', '', '  ']`, Save → assert `greeting: {text: 'Hi', suggestedPrompts: ['a']}`.

**Verification**:

- `yarn test src/components/PalsSheets/__tests__/PalSheet.test.tsx` passes

---

### Step 8: E2E spec — greeting round-trip

**Implements**: WHAT §6.G.

**Files**:

- `e2e/specs/features/pal-greeting.spec.ts` (new)

**Approach**: Mirror the structure of `talent-tool-use.spec.ts` (download/load model → create pal → restart → re-load → select pal → exercise UI). Diverge from it where:

- Use the smallest viable model — pick `Qwen3-0.6B` (`bartowski Qwen_Qwen3-0.6B`, `Qwen_Qwen3-0.6B-Q4_K_M.gguf`) via `downloadAndLoadModel`. This spec exercises greeting/chip rendering, NOT tool calling, so the tool-use model isn't needed.
- Use a plain English pal name like `'Greeter'`. No story IDs, no FOU-, no TASK-IDs.
- Do not set system prompt (greeting tests don't need it). Just `palSheetPage.setName('Greeter')`.
- Call new page-object methods (Step 9): `palSheetPage.setGreetingText('Hi from a friendly pal')`, `palSheetPage.addSuggestedPrompt('Send a test message')`, then `submit()`.
- After restart + re-load + pal-select + chat reset:
  - Assert `Selectors.chat.greetingBubble` is displayed and its text contains `'Hi from a friendly pal'`.
  - Assert `Selectors.chat.suggestedPromptChip(0)` is displayed.
  - Tap chip 0 and wait for a `user-message` bubble carrying text `'Send a test message'` to appear.
  - Best-effort wait for AI response (model non-determinism — wrap in try/catch like talent-tool-use spec does for `html-preview-bubble`).
  - Assert `greeting-bubble` and `suggested-prompts-row` are NOT displayed after the first user message (post-message gate already exists in `ChatView`).
- Single screenshot on success, failure screenshots in `afterEach` (copy the pattern from talent-tool-use:75-90).

Failure modes (per WHAT §6.G "skip-conditions"): if model download fails, the test fails loudly — no silent skip.

**Verification**:

- `tsc --noEmit -p e2e/tsconfig.json` (or `yarn typecheck` if e2e is included) passes
- Spec runs successfully against at least one device in the e2e pipeline (post-build smoke; not in this PR's automated CI by default — runs in the multi-device matrix per `e2e/scripts/run-e2e.ts`).

---

### Step 9: Selectors + PalSheetPage page-object additions

**Implements**: WHAT §6.G (test-surface contract).

**Files**:

- `e2e/helpers/selectors.ts` — extend `Selectors.palSheet` and `Selectors.chat`.
- `e2e/pages/PalSheetPage.ts` — add three async methods.

**Approach (selectors)**: Add inside the existing `palSheet:` block (lines 375-389) and `chat:` block (lines 133-188):

```ts
// Selectors.palSheet
get greetingSection(): string { return byTestId('greeting-section'); },
get greetingTextInput(): string { return byTestId('form-field-greetingText'); },
get suggestedPromptAddButton(): string { return byTestId('suggested-prompt-add-button'); },
suggestedPromptInput: (idx: number): string => byTestId(`suggested-prompt-input-${idx}`),
suggestedPromptRemove: (idx: number): string => byTestId(`suggested-prompt-remove-${idx}`),

// Selectors.chat
get greetingBubble(): string { return byTestId('greeting-bubble'); },
get suggestedPromptsRow(): string { return byTestId('suggested-prompts-row'); },
suggestedPromptChip: (idx: number): string => byTestId(`suggested-prompt-chip-${idx}`),
```

**Approach (page-object methods)**: In `PalSheetPage.ts`, add three methods mirroring the existing `setName` / `setSystemPrompt` pattern (scroll-then-fill-then-dismiss):

- `setGreetingText(text: string)` — scroll to `greetingTextInput`, `clearValue`, `setValue(text)`, `dismissKeyboard`.
- `addSuggestedPrompt(text: string)` — scroll to `suggestedPromptAddButton`, click, pause 300ms; compute the new row index by counting existing `suggested-prompt-input-N` elements before the click (or track an internal counter starting from 0 on each spec run — simpler: assume the spec adds prompts sequentially and the caller passes the expected index). Simplest contract: the method appends and immediately fills the LAST row (caller doesn't need to know the index). Implementation: after click, find all `suggested-prompt-input-*` elements via the chain selector and target the last one with `setValue(text)`, then `dismissKeyboard`.
- `removeSuggestedPromptAt(idx: number)` — scroll to `suggestedPromptRemove(idx)`, click, pause 300ms.

**Verification**:

- `tsc --noEmit -p e2e/tsconfig.json` (or equivalent) passes

---

### Step 10: Update architecture doc

**Implements**: WHAT §5 reconciliation, §11.

**Files**:

- `context/architecture/pals-and-talents.md` — §6 single-writer table row for `pal.greeting`.

**Approach**: Tighten the existing row from `(C) PalStore create/update flows, edited via PalSheet.` to `(C) PalStore create/update flows, edited via PalSheet → GreetingSection (in-app editor); also sourced from createLocalPalFromPalsHub on PalsHub download.` This brings the doc into alignment with the code that ships in this PR (slice 1 added the PalsHub source; slice 2 makes "edited via PalSheet" code-true for the first time). All other slice-2 contracts are implementation-level and do not warrant doc entries (WHAT §11 confirms no other drift).

No `(?)` markers are touched (the §8a model-load-gate `(?)` is explicitly out of slice 2 scope per WHAT §11).

**Verification**:

- `git diff context/architecture/pals-and-talents.md` shows only the single tightened row.
- Architecture doc still parses as markdown.

---

### Post-merge follow-up: File the whitespace-render-gate follow-up issue

> Tracked under "Post-merge follow-ups" in the Progress Tracking section above, NOT as a numbered in-PR step. Listed here only to keep the prose detail co-located.


**Implements**: WHAT §11 follow-up item 1 + round-2 critic suggestion (cross-reference both reproducers).

**Files**: none (GitHub issue, not source code).

**Approach**: After the PR merges, the implementer opens a follow-up issue in `repos/pocketpal-ai` titled `Greeting bubble renders empty for whitespace-only text` (public-artifact hygiene applies — no internal story / tracker / task markers in the title or body). Body:

- One-paragraph summary: `ChatView.tsx:853` gates the bubble on truthy `pal.greeting.text`, which lets a whitespace-only string render an empty visual bubble. Tighten the gate to `text.trim().length > 0`.
- Reproducer A — PalsHub-download path (already in `main`): download a PalsHub pal whose `greeting.text` is `'   '` (whitespace-only) with at least one suggested prompt. Open chat → bubble renders empty.
- Reproducer B — in-app editor path (this PR): create or edit a pal, type `'   '` into the greeting field, add a suggested prompt, save. Open chat → bubble renders empty.
- Note that both reproducers produce the same end-state (`pal.greeting.text === '   '`); the fix is a single render-gate change in `ChatView.tsx:853`.

Link the new issue from the merged PR's description as a follow-up. Mark the row in the "Post-merge follow-ups" subsection done once the issue exists.

**Verification**:

- Issue URL recorded against this row in the "Post-merge follow-ups" subsection.

---

## Testable-Contract Coverage

The testable contract is the canonical scenarios in WHAT §6 (and the I8–I13 invariants in §4e). Mapping:

| Contract item | Verified by |
| --- | --- |
| §6.A — create with greeting + 2 prompts | Step 7 case 1 (Jest PalSheet.test.tsx) + Step 8 (E2E pal-greeting.spec.ts happy path) |
| §6.B — edit a downloaded pal's greeting (round-trip) | Step 7 case 6 (form init from existing pal) + Step 7 case 1 update path |
| §6.C — clear → sentinel write, observable "no greeting" round-trip | Step 7 case 2 |
| §6.D — whitespace-only text + prompts → emit greeting with raw text (predicate parity, I9/I10) | Step 7 case 3 |
| §6.E — only prompts, no text → emit greeting with empty text | Step 7 case 4 |
| §6.F — no-op edit on greetingless pal → sentinel write, observable no-op (S4 symmetry) | Step 7 case 5 |
| §6.G — E2E happy-path round-trip (create → restart → chat → bubble + chips visible) | Step 8 |
| I8 (single editor save path) | Code-level: only `PalSheet.onSubmit` composes greeting; no other write path added. Reviewer-verifiable via grep. |
| I9 (predicate parity with slice 1) | Step 7 case 3 + slice 1's existing tests for the wire path (already merged in PR #741) |
| I10 (no trimming of saved `text`) | Step 7 case 3 + case 4 (text=`''` and text=`'   '` preserved verbatim) |
| I11 (per-prompt trim is destructive) | Step 7 case 7 |
| I12 (clear-on-save round-trip) | Step 7 case 2 (assert sentinel) + Step 7 case 6 (assert reopen shows blank fields after sentinel write) |
| I13 (PalSheet stays the single in-app editor) | Code-level: no new component added; no new write path. Reviewer-verifiable. |

---

## Native Verification

NATIVE_CHANGES=NO — TS/JS only, no native modules, no schema migration. No `pod install` / iOS build / Android build required for this slice.

---

## Visual Confirmation

VISUAL_CONFIRMATION=YES. The reviewer captures screenshots demonstrating the new editor UI and the chat-side render output. The E2E spec (Step 8) takes one screenshot on success automatically; the captures below are for manual review on a fresh build.

```json
[
  {
    "label": "GreetingSection mounted in PalSheet (create flow)",
    "prompt": "Open the Pals screen, tap +, select Assistant. Scroll the PalSheet until the Greeting section is visible.",
    "look_for": "A 'Greeting' section divider between 'System Prompt' and 'Color'. A multi-line 'Greeting message' text input. A 'Suggested prompts' subsection with a '+ Add prompt' button. No prompt rows yet."
  },
  {
    "label": "GreetingSection with text + 2 prompts filled in",
    "prompt": "In the same sheet, type 'Hi! What can I help with?' into the greeting input. Tap '+ Add prompt' twice. Fill row 0 with 'Summarize a webpage' and row 1 with 'Brainstorm a name'.",
    "look_for": "Greeting text input shows the typed message. Two prompt rows visible, each with a text input on the left and a remove control on the right. The add button still visible below the rows."
  },
  {
    "label": "Greeting bubble + chips on empty chat after save",
    "prompt": "Save the pal (name it 'Greeter'). Return to Chat, load any model, select the Greeter pal via the pal picker, reset the chat.",
    "look_for": "On the empty chat: a greeting bubble showing 'Hi! What can I help with?' near the top, and two suggested-prompt chips ('Summarize a webpage' and 'Brainstorm a name') above the input bar."
  },
  {
    "label": "Editing an existing downloaded PalsHub pal's greeting (round-trip)",
    "prompt": "From the Pals screen, long-press a PalsHub-downloaded pal that has a greeting (e.g. SketchPal) and choose Edit. Scroll to the Greeting section.",
    "look_for": "Greeting text input pre-populated with the pal's existing greeting. Suggested-prompt rows pre-populated with the existing prompts. Editing them and saving updates them — taking screenshots before and after save."
  },
  {
    "label": "Clear-on-save round-trip — greeting fully removed (sentinel write)",
    "prompt": "Re-open the previously-saved Greeter pal in the editor. Clear the greeting message text input completely. Tap the remove control on each suggested-prompt row until none remain. Save the pal. Then reopen the editor for the same pal, and finally open a chat with that pal (model loaded, empty session).",
    "look_for": "After the second reopen of the editor: both the Greeting message input and the Suggested prompts list are empty (no rows, no residual text). In the chat view with the same pal on an empty session: NO greeting bubble is rendered, and NO suggested-prompt chips appear above the input — the screen shows the regular empty-state placeholder, visually identical to a pal that never had a greeting. This confirms the clear-on-save round-trip closes."
  }
]
```

---

## Deferred Items

Strictly out of scope for this PR (kept in WHAT for future stories):

- WHAT §5 / §11 follow-up "(C2 fix)" — drop the `!== undefined` preservation gate in `PalRepository.updatePal` and remove both `pact` and `greeting` sentinels in one repo-side refactor. Not landed here; this PR uses the convergent empty-object sentinel pattern that matches the existing `pact` workaround.
- WHAT §10 / D11 — reorder UI for suggested prompts (drag handles, up/down). Add + remove + edit are sufficient for v1.
- WHAT §10 / D12 — length caps / per-row validation. None enforced.
- WHAT §11 follow-up "(S3 fix)" — tighten `ChatView.tsx:853` greeting-bubble render gate from truthy-text to `text.trim().length > 0`. Tracked as Step 11 (file the issue post-merge, no code change in this PR).
- Architecture doc §8a `(?)` on the model-load gate — explicitly noted in WHAT §11 as out of slice 2 scope.

---

## What this plan is NOT

- Not a design doc — design lives in `what-2.md`.
- Not a refactor of `PalRepository`'s preservation gate — deferred as the convergent C2 cleanup.
- Not a render-gate change in `ChatView` — Step 11 only files the follow-up issue, with NO `ChatView.tsx` edit in this PR.
- Not a re-design of the chat-side greeting / chips path — those components are reused verbatim.
- Not a new l10n strategy — only `en.json` is edited; Weblate owns other locales.

---

## Last Agent Handoff

```yaml
from_agent: implementer
to_agent: tester
timestamp: 2026-05-25T00:00:00Z
status: "Production code + GreetingSection unit tests complete; architecture doc updated. Ready for integration tests + E2E spec + page-object additions."
completed:
  - "Step 1: l10n keys (commit 64b9456)"
  - "Step 2: PalFormData fields (commit 2e1be7b)"
  - "Step 3: GreetingSection component + styles + barrel (commit c3add34)"
  - "Step 4: PalSheet schema/init/reset/mount (commit 62dd59d)"
  - "Step 5: PalSheet.onSubmit greeting composition + sentinel (commit 1f3d379)"
  - "Step 6: GreetingSection unit tests — 12 passing (commit e799d7b)"
  - "Step 10: Architecture doc §6 row tightened (dev-team repo)"
  - "Plan-critic round-2 notes absorbed: Visual Confirmation 5th capture (clear-round-trip §6.C); Post-merge follow-up split out of in-PR Progress Tracking"
next_steps:
  - "Step 7: integration tests in PalSheet.test.tsx covering §6 scenarios A/C/D/E/F + I11 trim-drop"
  - "Step 8: e2e/specs/features/pal-greeting.spec.ts happy-path round-trip"
  - "Step 9: e2e/helpers/selectors.ts + e2e/pages/PalSheetPage.ts additions"
blockers: []
context_for_next_agent: |
  Production code follows WHAT §4a/§4b/§4d strictly:
   - INITIAL_STATE seeds `greetingText: ''`, `suggestedPrompts: []`
   - Form init + resetForm both seed from `pal.greeting?.text ?? ''` / `pal.greeting?.suggestedPrompts ?? []`
   - Validation schema gets `.optional()` for both fields, no min/max
   - GreetingSection mounts between SystemPromptSection and ColorSection
   - onSubmit composes greeting per WHAT §4a rule 1+2 (raw text, per-prompt trim, sentinel `{text:'', suggestedPrompts:[]}` on full clear)
   - Sentinel pattern is convergent with the existing `pact` `{talents: []}` workaround a few lines above
  Testable contract is WHAT §6 scenarios A/C/D/E/F + invariants I8–I13.
  All public artifacts (en.json strings, testIDs, commit messages, source comments) are free of internal tracker / story markers per AGENTS.md.
```

