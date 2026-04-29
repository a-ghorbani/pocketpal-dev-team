# Story: Talent Picker UI in PalSheet + E2E Test for Talent Flow

## Metadata
- **Task ID**: TASK-20260415-1030-talents-ui
- **Issue**: Builds on PR #705 (PACT talent system)
- **Source**: prompt
- **Complexity**: standard
- **Native Changes**: NO
- **Visual Confirmation**: YES
- **Created**: 2026-04-26
- **Status**: draft

## Environment
- **Worktree**: `./worktrees/TASK-20260415-1030`
- **Branch**: `feature/TASK-20260415-1030`
- **Base**: `main`

---

## Progress Tracking

### Current Phase
`[x] Planning → [x] In Review → [x] Approved → [x] Implementing → [ ] Testing → [ ] Reviewing → [ ] PR Created`

### Checkpoints (Updated by Agents)

| Checkpoint | Status | Agent | Commit | Notes |
|------------|--------|-------|--------|-------|
| Worktree created | DONE | orchestrator | - | Existing worktree with PACT work |
| Story approved | PENDING | critic/human | - | |
| Step 1 complete | DONE | implementer | 02bd9f1 | Added talents to PalFormData + l10n strings |
| Step 2 complete | DONE | implementer | 3977d2e | Created TalentSection component |
| Step 3 complete | DONE | implementer | 4c36dfd | Integrated into PalSheet with pact wiring |
| Step 4 complete | PENDING | implementer | - | |
| Tests written | PENDING | tester | - | |
| Review passed | PENDING | reviewer | - | |
| PR created | PENDING | reviewer | - | |

### Last Agent Handoff
```yaml
from_agent: implementer
to_agent: tester
timestamp: 2026-04-26
status: "Steps 1-3 implementation complete, ready for tests"
completed:
  - "Step 1: Added talents field to PalFormData + l10n strings (commit 02bd9f1)"
  - "Step 2: Created TalentSection component following ColorSection pattern (commit 3977d2e)"
  - "Step 3: Integrated TalentSection into PalSheet, wired pact to onSubmit (commit 4c36dfd)"
next_steps:
  - Write unit tests for TalentSection
  - Write/update PalSheet tests for talent integration
  - Write E2E test for talent pipeline
blockers: []
context_for_next_agent: |
  Steps 1-3 are complete. TalentSection follows ColorSection pattern exactly
  (observer, useFormContext, Controller). Pact is always passed explicitly
  (empty array when no talents, not undefined) to ensure PalRepository clears
  old pact data. All 69 existing tests pass. Typecheck and lint clean.
```

---

## Context (For Recovery After Context Reset)

> **If you're an agent resuming work on this story:**
> 1. Read the "Progress Tracking" section above
> 2. Check `git log` in the worktree for commits
> 3. Read the "Last Agent Handoff" section
> 4. Continue from the next incomplete checkpoint

### Background
The PACT talent system (PR #705) is fully functional at the data layer: three talent engines (render_html, calculate, datetime) are registered, `Pal.pact.talents` is persisted by PalRepository, `deriveToolSchemas()` filters tool schemas, and the dispatch loop in `useChatSession.ts` gates tool calls by `pal.pact.talents`. However, there is NO UI for users to add talents to a Pal, meaning users have zero path to create a tool-calling Pal.

### Current State
- `src/components/PalsSheets/PalSheet.tsx` — Full form with name, description, model, system prompt, colors, parameters, generation settings. No talent/pact UI.
- `src/components/PalsSheets/types.ts` — `PalFormData` interface has no `talents` field.
- `src/services/talents/index.ts` — `talentRegistry.getAll()` returns all registered `TalentEngine[]`. Each engine has `.name` and `.toToolDefinition()` (which contains a `function.description`).
- `src/types/pal.ts` — `Pal.pact?: { talents: TalentRef[] }` where `TalentRef: { name: string; necessity: 'required' | 'optional' }`.
- `src/repositories/PalRepository.ts:186,292-293` — Already persists `pact` field on create and update.
- No E2E test exists for the talent pipeline.

### Target State
- PalSheet includes a "Talents" section with toggleable chips/switches for each registered talent.
- Users can create/edit Pals with talents enabled, which persists `pact.talents` to the database.
- An E2E test validates the full talent pipeline: create Pal with talent, chat, verify talent result.

---

## Requirements

### Functional
1. [MUST] Add `talents?: string[]` field to `PalFormData` in `src/components/PalsSheets/types.ts`
2. [MUST] Create `TalentSection` component that displays available talents as toggleable controls
3. [MUST] Place TalentSection between ColorSection and Generation Settings in `PalSheet.tsx`
4. [MUST] Initialize talent form data from `pal.pact?.talents?.map(t => t.name) ?? []` when editing
5. [MUST] On submit, convert selected talents to `pact: { talents: selectedTalents.map(name => ({ name, necessity: 'required' as const })) }` — when none selected, pass `pact: { talents: [] }` (NOT `undefined`, because `PalRepository.updatePal` treats `undefined` as "don't update this field" — the old pact would persist)
6. [MUST] Include `pact` in the `palData` object passed to `palStore.createPal()`/`updatePal()` in `onSubmit`
7. [MUST] Add l10n strings for "Talents" section header and talent descriptions
8. [MUST] Create E2E spec `e2e/specs/features/talent-tool-use.spec.ts` that validates the full pipeline
9. [SHOULD] Each talent toggle shows engine name and short description
10. [SHOULD] Talent section is visible for both create and edit modes

### Non-Functional
- Performance: No impact — talent list is static (3 items currently)
- Compatibility: iOS and Android (no native changes)

### Migration Considerations
- [ ] Does this change affect stored user data/settings? **No** — adding an optional pact field to existing pals; existing pals without pact continue to work as before.
- [ ] Is backwards compatibility needed for existing users? **No** — this is additive only.
- Migration strategy: `none needed`

---

## Acceptance Criteria

- [ ] TalentSection renders in PalSheet with all 3 registered talents
- [ ] Toggling a talent on/off updates the form state correctly
- [ ] Creating a new Pal with talents sets `pact.talents` correctly
- [ ] Editing an existing Pal with talents pre-selects them
- [ ] Editing an existing Pal and removing all talents sets `pact: { talents: [] }` (clears pact in DB)
- [ ] E2E test creates a Pal with render_html talent, sends a prompt, and verifies HtmlPreviewBubble appears
- [ ] All existing tests pass
- [ ] Coverage >= 60%

---

## Affected Files

| File | Action | Reason | Status |
|------|--------|--------|--------|
| `src/components/PalsSheets/types.ts` | MODIFY | Add `talents?: string[]` to PalFormData | PENDING |
| `src/components/PalsSheets/TalentSection.tsx` | CREATE | New talent picker section component | PENDING |
| `src/components/PalsSheets/PalSheet.tsx` | MODIFY | Add TalentSection, wire talents to form, include pact in onSubmit | PENDING |
| `src/components/PalsSheets/styles.ts` | MODIFY | Add styles for talent section | PENDING |
| `src/locales/en.json` | MODIFY | Add l10n strings for talent names/descriptions | PENDING |
| `src/components/PalsSheets/__tests__/TalentSection.test.tsx` | CREATE | Unit tests for TalentSection | PENDING |
| `src/components/PalsSheets/__tests__/PalSheet.test.tsx` | MODIFY | Add tests for talent form integration | PENDING |
| `e2e/specs/features/talent-tool-use.spec.ts` | CREATE | E2E test for full talent pipeline | PENDING |
| `e2e/pages/PalSheetPage.ts` | CREATE | Page object for PalSheet E2E interactions | PENDING |
| `e2e/pages/index.ts` | MODIFY | Export new page object | PENDING |
| `e2e/pages/DrawerPage.ts` | MODIFY | Add `navigateToPals()` method (follows `navigateToModels()` pattern) | PENDING |
| `e2e/helpers/selectors.ts` | MODIFY | Add selectors for talent testIDs and PalSheet fields | PENDING |

---

## Implementation Plan

### Step 1: Add `talents` to PalFormData and l10n strings
**Files**: `src/components/PalsSheets/types.ts`, `src/locales/en.json`
**Status**: `DONE`

**Change**:
- [ ] Add `talents?: string[]` to `PalFormData` interface
- [ ] Add l10n strings under `components.palSheet`:
  ```json
  "talents": "Talents",
  "talentDescriptions": {
    "render_html": "HTML preview — render HTML documents inline in chat",
    "calculate": "Math expressions — evaluate mathematical expressions",
    "datetime": "Date & time — get current time, format dates, compute differences"
  }
  ```

**Pattern Reference**: See `src/components/PalsSheets/types.ts:4-18` for existing PalFormData; see `src/locales/en.json:731-747` for palSheet l10n structure.

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn typecheck
```

### Step 2: Create TalentSection component
**Files**: `src/components/PalsSheets/TalentSection.tsx`, `src/components/PalsSheets/styles.ts`
**Status**: `DONE`

**Change**:
- [ ] Create `TalentSection.tsx` following `ColorSection.tsx` pattern (see below)
- [ ] Use `useFormContext<PalFormData>()` + `Controller` for `talents` field
- [ ] Call `talentRegistry.getAll()` to get available engines (`registerDefaultTalents()` is already called in `PalStore.initialize()` at app startup — no need to call it in the component)
- [ ] For each engine, show a `Switch` (react-native-paper) with the engine name and l10n description
- [ ] Use `SectionDivider` with l10n label "Talents"
- [ ] Add `testID="talent-switch-{name}"` on each Switch for E2E targeting
- [ ] Add `testID="talent-section"` on the container View
- [ ] Add styles: `talentItem` (row with switch), `talentDescription` (subtitle text)

**Pattern Reference**: `src/components/PalsSheets/ColorSection/ColorSection.tsx:64-99` — self-contained section using `useFormContext`, `Controller`, `SectionDivider`, and `createStyles`.

**Code Guidance**:
```typescript
// TalentSection.tsx — key structure
import React, {useContext, useMemo} from 'react';
import {View} from 'react-native';
import {Switch, Text} from 'react-native-paper';
import {observer} from 'mobx-react-lite';
import {useFormContext, Controller} from 'react-hook-form';

import {useTheme} from '../../hooks';
import {L10nContext} from '../../utils';
import {createStyles} from './styles';
import {SectionDivider} from './SectionDivider';
import type {PalFormData} from './types';
import {talentRegistry} from '../../services/talents';

export const TalentSection = observer(() => {
  const {control} = useFormContext<PalFormData>();
  const theme = useTheme();
  const styles = createStyles(theme);
  const l10n = useContext(L10nContext);

  // registerDefaultTalents() is already called in PalStore.initialize()
  // at app startup — no need to call here.
  const availableTalents = useMemo(() => {
    return talentRegistry.getAll();
  }, []);

  return (
    <View testID="talent-section">
      <SectionDivider label={l10n.components.palSheet.talents} />
      <Controller
        control={control}
        name="talents"
        render={({field: {onChange, value}}) => (
          <View>
            {availableTalents.map(engine => {
              const isEnabled = (value ?? []).includes(engine.name);
              const description =
                l10n.components.palSheet.talentDescriptions?.[engine.name] ??
                engine.toToolDefinition().function.description;
              return (
                <View key={engine.name} style={styles.talentItem} testID={`talent-item-${engine.name}`}>
                  <View style={styles.talentInfo}>
                    <Text variant="bodyMedium">{engine.name}</Text>
                    <Text variant="bodySmall" style={styles.talentDescription}>
                      {description}
                    </Text>
                  </View>
                  <Switch
                    testID={`talent-switch-${engine.name}`}
                    value={isEnabled}
                    onValueChange={checked => {
                      const current = value ?? [];
                      onChange(
                        checked
                          ? [...current, engine.name]
                          : current.filter(n => n !== engine.name),
                      );
                    }}
                  />
                </View>
              );
            })}
          </View>
        )}
      />
    </View>
  );
});
```

**Styles to add in `styles.ts`**:
```typescript
talentItem: {
  flexDirection: 'row',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingVertical: 8,
  paddingHorizontal: theme.spacing.default,
},
talentInfo: {
  flex: 1,
  marginRight: 12,
},
talentDescription: {
  color: theme.colors.onSurfaceVariant,
},
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn typecheck
yarn lint
```

### Step 3: Integrate TalentSection into PalSheet and wire pact to onSubmit
**Files**: `src/components/PalsSheets/PalSheet.tsx`
**Status**: `DONE`

**Change**:
- [ ] Import `TalentSection` component
- [ ] Add `talents: []` to `INITIAL_STATE`
- [ ] Add `talents: z.array(z.string()).optional()` to `validationSchema`
- [ ] In the `useEffect` that initializes form data, set `talents: pal.pact?.talents?.map(t => t.name) ?? []`
- [ ] Same in `resetForm`
- [ ] Place `<TalentSection />` after `<ColorSection />` and before the Generation Settings section (line ~378)
- [ ] In `onSubmit`, build `pact` from form data and include it in `palData`:
  ```typescript
  const selectedTalents = data.talents ?? [];
  // Always pass pact explicitly — using `undefined` would skip the
  // update in PalRepository (it checks `if (updates.pact !== undefined)`)
  const pact = selectedTalents.length > 0
    ? { talents: selectedTalents.map(name => ({ name, necessity: 'required' as const })) }
    : { talents: [] as TalentRef[] };
  // Add to palData:
  const palData: Partial<Pal> = {
    ...existingFields,
    pact,
  };
  ```

**Pattern Reference**: See `PalSheet.tsx:144-161` for form initialization pattern; see `PalSheet.tsx:217-274` for `onSubmit` pattern.

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn typecheck
yarn lint
yarn test --findRelatedTests src/components/PalsSheets/PalSheet.tsx
```

### Step 4: Write Unit Tests
**Files**: `src/components/PalsSheets/__tests__/TalentSection.test.tsx`, `src/components/PalsSheets/__tests__/PalSheet.test.tsx`
**Status**: `PENDING`

**Change**:
- [ ] Create `TalentSection.test.tsx`:
  - Renders all 3 talent switches
  - Toggling a switch updates form value
  - Pre-selected talents show as enabled
- [ ] Add to `PalSheet.test.tsx`:
  - Test that talent section is visible
  - Test creating a pal with talents selected → verify `palStore.createPal` called with correct pact
  - Test editing a pal with existing pact.talents → switches pre-selected
  - Test removing all talents → pact is undefined

**Test Infrastructure Notes**:
- Import `render` from `jest/test-utils` (NOT @testing-library/react-native)
- `palStore` is globally mocked in `jest/setup.ts` — import and verify mock calls
- For TalentSection tests, wrap in `FormProvider` from react-hook-form (same pattern as ColorSection would need)
- Mock `registerDefaultTalents` and `talentRegistry.getAll()` — or use the real registry since it's pure TypeScript
- Use `jest.clearAllMocks()` in `beforeEach`
- Use `runInAction` for any MobX state changes

**Pattern Reference**: See `src/components/PalsSheets/__tests__/PalSheet.test.tsx:1-80` for test setup pattern (Sheet mock, useStructuredOutput mock, palStore import).

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn test --findRelatedTests src/components/PalsSheets/TalentSection.tsx src/components/PalsSheets/PalSheet.tsx
```

### Step 5: Create E2E Page Objects and Selectors
**Files**: `e2e/pages/PalSheetPage.ts`, `e2e/pages/DrawerPage.ts`, `e2e/pages/index.ts`, `e2e/helpers/selectors.ts`
**Status**: `PENDING`

**Change**:
- [ ] Add `navigateToPals()` to `DrawerPage.ts` (follows `navigateToModels()` at line 66-72):
  ```typescript
  async navigateToPals(): Promise<void> {
    await this.waitForOpen();
    await this.tap(Selectors.drawer.palsTab);
    await browser.pause(300);
    await this.waitForClose();
  }
  ```
- [ ] Add selectors to `Selectors` object in `selectors.ts`:
  ```typescript
  palSheet: {
    get nameInput(): string { return byTestId('pal-name-input'); },
    // Note: The FormField component may not have this testID. Check if
    // PalSheet name field uses a custom testID or if we need to find it
    // by the input within a form. May need to use the existing field refs.
    get submitButton(): string { return byTestId('submit-button'); },
    talentSwitch: (name: string): string => byTestId(`talent-switch-${name}`),
    get talentSection(): string { return byTestId('talent-section'); },
  },
  ```
- [ ] Create `PalSheetPage.ts` page object:
  ```typescript
  // Methods needed:
  // - setName(name: string)
  // - setSystemPrompt(prompt: string)
  // - enableTalent(talentName: string) — tap the switch for a talent
  // - disableTalent(talentName: string)
  // - submit()
  // - scrollToTalents() — scroll down to reach talent section
  ```
- [ ] Export from `e2e/pages/index.ts`

**Pattern Reference**: See `e2e/pages/ChatPage.ts` for page object pattern; see `e2e/helpers/selectors.ts:111-503` for selector organization.

**Important**: The PalSheet form fields use `FormField` component with `name` prop for react-hook-form. The name input at `PalSheet.tsx:307` does NOT have a `testID` — it uses `ref` and `name="name"`. The E2E test will need to find the input by accessibility label or by using the placeholder text. Check at implementation time whether adding `testID` props to the FormField calls is needed (it likely is — add `testID="pal-name-input"` to the name FormField, `testID="pal-system-prompt-input"` to the system prompt, etc.).

### Step 6: Create E2E Test Spec
**Files**: `e2e/specs/features/talent-tool-use.spec.ts`
**Status**: `PENDING`

**Change**:
- [ ] Create E2E spec following `thinking.spec.ts` pattern:
  1. Download and load Qwen3-1.7B (already in `TEST_MODELS` fixtures as `qwen3-1.7b`)
  2. Navigate to Pals screen:
     - `chatPage.openDrawer()` → `drawerPage.navigateToPals()`
     - This uses `Selectors.drawer.palsTab` (testID: `drawer-item-pals`)
  3. Create new Assistant Pal:
     - Tap add button: testID `bottom-action-add` → menu appears
     - Tap "Assistant" menu item (text match, no testID on Menu.Item)
     - PalSheet opens as full-screen bottom sheet
  4. Fill in PalSheet:
     - Name: "E2E Code Companion" (FormField name input — may need testID added)
     - System prompt: tool-use prompt instructing the model to use render_html
     - Scroll to Talents section and toggle `render_html` on (testID: `talent-switch-render_html`)
  5. Submit the pal (testID: `submit-button`)
  6. Navigate back to Chat:
     - `chatPage.openDrawer()` → `drawerPage.navigateToChat()`
  7. Select the new pal:
     - `chatPage.openPalPicker()` → `chatPage.selectPal('E2E Code Companion')`
  8. Send prompt: "Create a simple hello world webpage with a blue heading"
  9. Wait for inference to complete
  10. Verify: `html-preview-bubble` testID element appears
  11. Take screenshot for visual confirmation

  **Note on TalentSection placement**: In create mode, TalentSection is the last visible section (Generation Settings is hidden for new pals, only shown when `pal.id` exists). This means scrolling to it is straightforward.

**Test Infrastructure Notes**:
- Use `downloadAndLoadModel()` from `e2e/helpers/model-actions.ts` for model setup
- Use `ChatPage.openPalPicker()` and `ChatPage.selectPal('E2E Code Companion')` for pal selection
- Navigate to Pals screen via `DrawerPage.navigateToPals()` (added in Step 5, follows `navigateToModels()` pattern)
- The Qwen3-1.7B model is already defined in `e2e/fixtures/models.ts:86-90`
- Timeout for download: 600000 (10 min, already set in fixture)
- Use `waitForInferenceComplete()` from model-actions helper
- Verify html-preview-bubble via `byTestId('html-preview-bubble')`

**Risks for E2E**: Tool calling with a 1.7B model is non-deterministic. The model may not always produce a valid tool call. Mitigations:
- Set temperature=0 and seed=1 for determinism
- Use a very explicit system prompt that instructs tool use
- Allow retries (2-3 attempts) before failing
- If the model doesn't produce HTML, log a warning but don't hard-fail (the UI integration is still validated by unit tests)

**Pattern Reference**: See `e2e/specs/features/thinking.spec.ts` for full test structure including before/afterEach, screenshot capture, and model setup.

**Verification**:
```bash
cd "${WORKTREE_PATH}"
# Lint E2E files
cd e2e && npx tsc --noEmit && cd ..
```

---

## Test Requirements

### Unit Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| TalentSection renders all registered talents | `TalentSection.test.tsx` | MUST | PENDING |
| Toggling talent switch updates form state | `TalentSection.test.tsx` | MUST | PENDING |
| Pre-selected talents render as enabled | `TalentSection.test.tsx` | MUST | PENDING |
| PalSheet includes talent section | `PalSheet.test.tsx` | MUST | PENDING |
| Creating pal with talents → correct pact in createPal call | `PalSheet.test.tsx` | MUST | PENDING |
| Editing pal with existing pact → talents pre-selected | `PalSheet.test.tsx` | MUST | PENDING |
| Removing all talents → pact is `{talents: []}` (clears in DB) | `PalSheet.test.tsx` | SHOULD | PENDING |

### Integration Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| Full talent pipeline E2E (create pal → chat → verify HTML bubble) | `talent-tool-use.spec.ts` | SHOULD | PENDING |

### Manual Testing
- [ ] Open PalSheet for new pal → verify Talents section visible with 3 toggles
- [ ] Toggle render_html on → create pal → verify pact persists (check via edit)
- [ ] Edit existing pal with talents → verify switches are pre-selected
- [ ] Chat with talent-enabled pal → verify tool calling works

### Visual Confirmation (if Visual Confirmation = YES)

Screenshots captured automatically via `visual-capture` E2E spec during review.
The reviewer runs this spec and attaches screenshots to the PR for human assessment.

```json
[
  {"prompt": "Create a simple hello world webpage with a blue heading that says Welcome", "name": "talent-html-preview", "description": "Verify HtmlPreviewBubble appears in chat with rendered HTML content after talent tool call completes"}
]
```

**Note**: Visual capture requires a Pal with render_html talent to be selected. The reviewer should first create such a Pal manually or use the E2E talent-tool-use spec which creates one.

---

## Coding Standards

### Testing Infrastructure (CRITICAL)
```
# Read these BEFORE writing tests:
${WORKTREE_PATH}/jest/setup.ts      # Global mocks
${WORKTREE_PATH}/jest/test-utils.tsx # Custom render
${WORKTREE_PATH}/__mocks__/stores/  # Mock stores

# DO NOT mock stores inline - they're globally mocked
# Use runInAction() for MobX state changes
# Import render from jest/test-utils, NOT @testing-library/react-native
```

### Patterns to Follow
- **State**: Use MobX `@observable`, `@action`, `@computed`
- **Components**: Functional + `observer()` HOC
- **Hooks**: Follow existing hooks in `/src/hooks/`
- **Types**: Strict TypeScript, avoid `any`

### Commit Format (enforced by commitlint)
```
type(scope): subject
```

**Rules**:
- Header max: 100 chars total
- Types allowed: `feat`, `fix`, `docs`, `chore` (only these 4)
- No Co-Authored-By needed
- Keep it short and clear

**Suggested commits**:
1. `feat(pals): add talent picker section to PalSheet`
2. `feat(e2e): add talent tool-use E2E test`

---

## Reference Code

### Pattern Example: ColorSection (self-contained form section)
**File**: `src/components/PalsSheets/ColorSection/ColorSection.tsx`
**Lines**: 64-99
```typescript
export const ColorSection = observer(() => {
  const {control} = useFormContext<PalFormData>();
  const theme = useTheme();
  const styles = createStyles(theme);

  return (
    <View>
      <SectionDivider label="Color" />
      <Controller
        control={control}
        name="color"
        render={({field: {onChange, value}}) => (
          // ... render color pickers
        )}
      />
    </View>
  );
});
```

### Pattern Example: PalSheet onSubmit (building palData)
**File**: `src/components/PalsSheets/PalSheet.tsx`
**Lines**: 217-274
```typescript
const onSubmit = async (data: PalFormData) => {
  // ... extract parameters, build palData
  const palData: Partial<Pal> = {
    type: pal.type || 'local',
    name: data.name,
    // ... other fields
    completionSettings: data.completionSettings,
  };
  // Add pact here based on data.talents
  if (isEditing) {
    await palStore.updatePal(pal.id!, palData);
  } else {
    await palStore.createPal(palData as Omit<Pal, 'id'>);
  }
};
```

### Pattern Example: TalentEngine interface
**File**: `src/services/talents/types.ts`
```typescript
export interface TalentEngine {
  readonly name: string;
  execute(args: Record<string, any>): Promise<TalentResult>;
  toToolDefinition(): ToolDefinition;
}
```

### Pattern Example: E2E thinking test structure
**File**: `e2e/specs/features/thinking.spec.ts`
**Lines**: 40-56
```typescript
describe('Thinking Model Features', () => {
  let chatPage: ChatPage;
  before(async () => {
    chatPage = new ChatPage();
    await chatPage.waitForReady(TIMEOUTS.appReady);
    await chatPage.openGenerationSettings();
    await chatPage.setTemperature('0');
    await chatPage.setSeed('1');
    await chatPage.saveGenerationSettings();
    await downloadAndLoadModel(THINKING_MODEL);
  });
  // ... tests
});
```

---

## Dependencies

### Blocked By
- [ ] PR #705 (PACT talent system) must be in the worktree — **already present on branch**

### Blocks
- [ ] Future: greeting/suggestedPrompts UI (out of scope for this story)
- [ ] Future: Talent-specific configuration per talent (out of scope)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| E2E test flaky due to model non-determinism | High | Low | Set temp=0, seed=1; allow retries; don't hard-fail on model output |
| FormField lacks testID for E2E | Medium | Low | Add testID props to FormField calls in PalSheet; minimal change |
| PalSheet vertical scroll may hide TalentSection | Low | Low | Place between ColorSection and GenSettings; user already scrolls |
| `talentRegistry.getAll()` returns empty if `registerDefaultTalents()` not called | Low | Medium | Already called in `PalStore.initialize()` at app startup; no defensive call needed in UI component |

---

## Open Questions

### For Human
- [ ] Should talent descriptions be shorter (just "HTML preview", "Math", "Date & time") or include full descriptions as proposed?
- [ ] For E2E: Qwen3-1.7B is specified as good at tool calling. Should we also test with a smaller model as fallback?

### Resolved
- Q: Should talents have "required" vs "optional" necessity in UI? → A: No, keep simple — all toggled talents are "required". Users don't need this distinction yet (YAGNI).
- Q: Where to place TalentSection? → A: After ColorSection, before Generation Settings — logical grouping of "what this pal can do" before "how it generates".

---

## Review History

> Updated by the planner during revision. Shows what the critic found and how it was addressed.

| # | Severity | Finding | Resolution | Notes |
|---|----------|---------|------------|-------|
| 1 | CONCERN | Missing `DrawerPage.ts` in affected files — needs `navigateToPals()` | FIXED | Added to affected files table and Step 5 with full code guidance |
| 2 | CONCERN | E2E Pal creation flow under-specified (no testIDs, no navigation path) | FIXED | Step 6 now specifies exact testIDs: `drawer-item-pals`, `bottom-action-add`, `submit-button`, `talent-switch-render_html` and full navigation sequence |
| 3 | CONCERN | `pact: undefined` won't clear talents on edit (`PalRepository.updatePal` skips undefined fields) | FIXED | Changed to `pact: {talents: []}` when no talents selected — explicitly clears the field |
| 4 | SUGGESTION | `registerDefaultTalents()` in component useMemo is app-init logic | FIXED | Removed from component — already called in `PalStore.initialize()` at app startup |
| 5 | SUGGESTION | Note TalentSection is last section in create mode | FIXED | Added note in Step 6 about section placement in create mode |

---

## Agent Reports

### Planner Report
```
Researched: PalSheet form structure (react-hook-form + zod + Controller pattern),
ColorSection as section pattern, TalentEngine/TalentRegistry API, PalRepository
pact handling, E2E infrastructure (Appium + page objects + model fixtures).

Key findings:
- PalSheet uses react-hook-form with zod validation — talents fits cleanly as
  an optional array field
- ColorSection is the exact pattern to follow for a self-contained section
- PalRepository already handles pact persistence (lines 186, 292-293)
- talentRegistry.getAll() returns TalentEngine[] with name and toToolDefinition()
- HtmlPreviewBubble has testID="html-preview-bubble" for E2E verification
- Qwen3-1.7B already exists in E2E fixtures
- No PalSheet page object exists yet — needs creation
- FormField in PalSheet lacks testIDs — may need to add for E2E
```

### Implementation Report
```
Steps 1-3 complete. 3 atomic commits on feature/TASK-20260415-1030.

Changes:
- src/components/PalsSheets/types.ts — added talents?: string[] to PalFormData
- src/locales/en.json — added talents + talentDescriptions l10n strings
- src/components/PalsSheets/TalentSection.tsx — new component (observer, Controller, Switch per talent)
- src/components/PalsSheets/styles.ts — added talentItem, talentInfo, talentDescription styles
- src/components/PalsSheets/PalSheet.tsx — imported TalentSection, added talents to INITIAL_STATE/schema/form init/resetForm, placed after ColorSection, wired pact in onSubmit

Verification:
- TypeCheck: PASS
- Lint: PASS (0 errors, 4 pre-existing warnings)
- Related Tests: PASS (69/69)
- Pod Install: N/A (no native changes)
- iOS Build: N/A
- Android Build: N/A

No deviations from plan. Used keyof typeof for talentDescriptions lookup
instead of `as any` cast for type safety.
```

### Test Report
```
[Filled by tester after tests written]
```

### Review Report
```
[Filled by reviewer after review]
```

---

## Changelog

| Date | Agent/Human | Change |
|------|-------------|--------|
| 2026-04-26 | planner | Initial story draft |
| 2026-04-27 | planner | Revision: addressed 3 concerns + 2 suggestions from critic R1 |
