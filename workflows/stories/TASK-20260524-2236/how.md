# Implementation Plan: Wire Palshub `pact.talents` + `greeting` into PocketPal pal download

**Purpose**: land the download-boundary delta specified in `what.md`. Two production touch-points (`PalsHubApiService.transformApiPal` and `PalStore.createLocalPalFromPalsHub`), one wire-type extension, plus targeted Jest coverage and the architecture-doc absorption.

---

## Metadata

- **Task ID**: TASK-20260524-2236
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260524-2236`
- **Branch**: `feature/TASK-20260524-2236`
- **Native Changes**: NO
- **Visual Confirmation**: NO
- **Intent Brief**: `/Users/aghorbani/codes/pocketpal-dev-team/workflows/stories/TASK-20260524-2236/intent-brief.md`
- **WHAT**: `/Users/aghorbani/codes/pocketpal-dev-team/workflows/stories/TASK-20260524-2236/what.md`
- **Architecture doc(s) being updated**: `/Users/aghorbani/codes/pocketpal-dev-team/context/architecture/pals-and-talents.md`
- **Status**: draft

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — Extend `PalsHubPal` + `ApiPalResponse` with optional `pact`/`greeting`/`images`/`models` | DONE | 023d528 | WHAT §1b, §1c |
| Step 2 — Forward new fields in `transformApiPal` | DONE | 5919f52 | WHAT §4b |
| Step 3 — Map `pact` + `greeting` in `createLocalPalFromPalsHub` | DONE | adf29ff | WHAT §4a |
| Step 4 — Tests: `transformApiPal` forwards new fields | pending (tester) | - | WHAT §6.A, §6.B |
| Step 5 — Tests: `createLocalPalFromPalsHub` conversion rules + edge cases | pending (tester) | - | WHAT §6.A, §6.B, §6.E, §6.G, §9a, §9b, §9e |
| Step 6 — Architecture doc updated (absorb WHAT delta + critic cosmetic fix) | DONE | (this commit) | WHAT §11 |
| Cleanup reminders applied | DONE | - | none required — WHAT has no diagnostic code to remove |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/types/palshub.ts` | edit (extend `PalsHubPal`) | §1b |
| `src/services/palshub/PalsHubApiService.ts` | edit (extend `ApiPalResponse`, forward in `transformApiPal`) | §1c, §4b |
| `src/store/PalStore.ts` | edit (`createLocalPalFromPalsHub`) | §4a |
| `src/services/palshub/__tests__/PalsHubApiService.test.ts` | edit (add cases to existing `describe('transformApiPal')`) | §6 |
| `src/store/__tests__/PalStore.test.ts` | edit (new `describe('createLocalPalFromPalsHub')` block) | §6, §9 |
| `context/architecture/pals-and-talents.md` | edit (drift fix + WHAT absorption) | §11 |

No new files. No native, no schema, no migration — DB v7 already has `local_pals.pact` / `local_pals.greeting`, and `PalRepository` already JSON-stringifies both fields (`src/repositories/PalRepository.ts:186-187`, `:292-296`).

---

## Implementation Steps

### Step 1: Extend `PalsHubPal` (wire type) and `ApiPalResponse` with the four optional fields

**Implements**: WHAT §1b, §1c.

**Files**:

- `src/types/palshub.ts` — append four optional fields to `PalsHubPal` (the public wire-shape interface around line 82-168): `pact`, `greeting`, `images`, `models`.
- `src/services/palshub/PalsHubApiService.ts` — append the same four optional fields to the file-local `ApiPalResponse` interface (around line 26-75).

**Approach**: Add exactly the shapes from WHAT §1b:

```ts
pact?: { version: number; talents: Array<{name: string; required?: boolean}> };
greeting?: { text?: string; suggested_prompts?: string[] };
images?: unknown[];
models?: unknown[];
```

Snake_case on both interfaces — this is the wire boundary. `images`/`models` stay `unknown[]` per WHAT D3. Do not import or re-use `Pal['pact']` / `Pal['greeting']` here: the wire shape is intentionally distinct (snake_case, optional `required: boolean` not `necessity: 'required' | 'optional'`).

**Verification**:

- `yarn typecheck` passes (no consumer breakage — all four fields are optional).
- `yarn lint src/types/palshub.ts src/services/palshub/PalsHubApiService.ts` clean.

### Step 2: Forward the new fields in `transformApiPal`

**Implements**: WHAT §4b, I1 (single conversion site preserved at the wire boundary).

**Files**:

- `src/services/palshub/PalsHubApiService.ts` — inside `transformApiPal` (around line 209-260), forward `apiPal.pact`, `apiPal.greeting`, `apiPal.images`, `apiPal.models` verbatim onto the returned object. No coercion, no defaulting, no snake_case→camelCase here — that happens at the next boundary (Step 3).

**Approach**: Append four lines to the object literal returned by `transformApiPal`:

```ts
pact: apiPal.pact,
greeting: apiPal.greeting,
images: apiPal.images,
models: apiPal.models,
```

When the API omits any of these, the property lands as `undefined`, which is the WHAT §9f / §9e behaviour (older Palshub servers + JSON `null` both short-circuit downstream).

**Verification**:

- `yarn typecheck` passes.
- `yarn test --findRelatedTests src/services/palshub/PalsHubApiService.ts` — existing cases continue to pass (no change in defaults for missing fields).

### Step 3: Map `pact` + `greeting` in `createLocalPalFromPalsHub`

**Implements**: WHAT §4a (rules 1–6), I2 (single rename site), I3 (older payloads survive), I4 (no regression on `thumbnail_url`/`model_reference`), §9a–§9e (edge cases).

**Files**:

- `src/store/PalStore.ts` — inside `createLocalPalFromPalsHub` (around line 432-491), add a `pact` mapping and a `greeting` mapping, and include them on the returned `Pal` object.

**Approach**:

1. **PACT**: read `palsHubPal.pact?.talents` (handles both absent `pact` and absent `talents` keys naturally — WHAT §9b/§9e). If the array is non-empty, map each entry to `{name, necessity: entry.required === true ? 'required' : 'optional'}` (strict-boolean per WHAT D4 / §6.G). Drop `pact.version` (WHAT D2). Emit `pact: { talents: [...] }`. If empty / absent / null → emit nothing (i.e., omit the `pact` key) so the returned `Pal` has `pact: undefined` (WHAT rule 5).
2. **Greeting**: compute `hasText = (palsHubPal.greeting?.text?.length ?? 0) > 0` and `hasPrompts = (palsHubPal.greeting?.suggested_prompts?.length ?? 0) > 0` (WHAT §4a rule 2's single predicate). If neither is true, omit the key. If at least one is true, emit `greeting: { text: palsHubPal.greeting!.text ?? '', ...(hasPrompts ? { suggestedPrompts: palsHubPal.greeting!.suggested_prompts } : {}) }`. Pass `text` through verbatim — no `trim`, no validation (WHAT I2, §9c).
3. Untouched: the entire `thumbnail_url` branch in `downloadPalsHubPal` (lines 252-275) and the `defaultModel = palsHubPal.model_reference ? createLocalModelFromPHModel(...) : undefined` branch (lines 456-458) — WHAT I4 / §6.C / §6.D.

Implementation must construct `pact` / `greeting` outside the object literal and conditionally spread them in (`...(pact ? {pact} : {})`, `...(greeting ? {greeting} : {})`) so omitted keys land as `undefined` on the returned `Pal`, matching the §6.B scenario.

**Verification**:

- `yarn typecheck` passes (the `Pal` type already has `pact?` / `greeting?`).
- `yarn lint src/store/PalStore.ts` clean.
- Step 5 tests cover the contract.

### Step 4: Tests for `transformApiPal` forwarding

**Implements**: WHAT §4b. Extends the existing `describe('transformApiPal', ...)` block.

**Files**:

- `src/services/palshub/__tests__/PalsHubApiService.test.ts` — add three `it(...)` cases inside the existing `describe('transformApiPal')` block (around line 97). Mirror the existing pattern (build a literal `apiPal`, call `service.transformApiPal(apiPal)`, assert).

**Approach**:

1. `it('forwards pact, greeting, images, models when present')` — populate all four on the input, assert they round-trip verbatim onto the returned `PalsHubPal` (no shape conversion at this boundary).
2. `it('leaves new fields undefined when absent')` — minimal apiPal (existing "missing optional fields" shape), assert `result.pact`, `result.greeting`, `result.images`, `result.models` are all `undefined`.
3. `it('forwards pact with version field intact')` — input `pact: { version: 1, talents: [...] }`, assert the returned shape still carries `version: 1`. Dropping `version` is the job of `createLocalPalFromPalsHub` (WHAT D2), not this transformer.

**Verification**:

- `yarn test src/services/palshub/__tests__/PalsHubApiService.test.ts` — all transformApiPal cases (existing + new) pass.

### Step 5: Tests for `createLocalPalFromPalsHub` conversion rules

**Implements**: WHAT §6.A, §6.B, §6.E, §6.G, §9a (worked examples), §9b, §9e.

**Files**:

- `src/store/__tests__/PalStore.test.ts` — add a new `describe('createLocalPalFromPalsHub')` block alongside the existing `describe('downloadPalsHubPal')` (after line 549). The block tests the conversion by driving it through the public `downloadPalsHubPal` entry point and asserting on the object passed to `palRepository.createPal` — same pattern as the existing `downloadPalsHubPal` cases (lines 440-549). This keeps the private method private and exercises the real I1 single-writer path.

**Approach**: Each case builds a `PalsHubPal` with the relevant `pact` / `greeting` shape, calls `palStore.downloadPalsHubPal(palsHubPal)`, then asserts on the first argument of the `palRepository.createPal` mock (`expect.objectContaining({pact: ..., greeting: ...})` or the asymmetric `expect.not.objectContaining(['pact'])` shape where the key must be absent).

Cases (each is a contract-coverage row in §Testable-Contract Coverage below):

| Case | Wire input | Expected on local `Pal` |
| --- | --- | --- |
| `happy path (§6.A)` | `pact: {version:1, talents:[{name:'render_html',required:true},{name:'calculate',required:false}]}` + `greeting: {text:'Hi',suggested_prompts:['a','b']}` | `pact: {talents:[{name:'render_html',necessity:'required'},{name:'calculate',necessity:'optional'}]}`, `greeting: {text:'Hi',suggestedPrompts:['a','b']}` |
| `legacy / both absent (§6.B)` | no `pact`, no `greeting` | `pact: undefined`, `greeting: undefined` |
| `unknown talent name preserved (§6.E)` | `pact: {talents:[{name:'web_search',required:true}]}` | `pact: {talents:[{name:'web_search',necessity:'required'}]}` (conversion does NOT validate against registry) |
| `strict-boolean coercion (§6.G)` | `pact: {talents:[{name:'a',required:'true' as any},{name:'b',required:1 as any},{name:'c',required:true}]}` | only `c` → `'required'`; `a`, `b` → `'optional'` |
| `pact.version dropped (D2)` | `pact: {version:1, talents:[{name:'calculate'}]}` | returned `pal.pact` has no `version` key |
| `empty talents array (§9b)` | `pact: {talents: []}` | `pact: undefined` |
| `pact: {version:1}` no talents key (§9b) | `pact: {version: 1}` | `pact: undefined` |
| `pact: null` (§9e) | `pact: null as any` | `pact: undefined` |
| `greeting with only text (§9a)` | `greeting: {text: 'Hi'}` | `greeting: {text: 'Hi'}` (no `suggestedPrompts` key) |
| `greeting with only prompts (§9a)` | `greeting: {suggested_prompts: ['a']}` | `greeting: {text: '', suggestedPrompts: ['a']}` |
| `greeting with text + empty prompts (§9a)` | `greeting: {text: 'Hi', suggested_prompts: []}` | `greeting: {text: 'Hi'}` (key omitted because empty array) |
| `greeting all empty (§9a)` | `greeting: {text: '', suggested_prompts: []}` | `greeting: undefined` |
| `greeting: null` | `greeting: null as any` | `greeting: undefined` |
| `whitespace-only text passes through (§9c)` | `greeting: {text: '   '}` | `greeting: {text: '   '}` (no trim) |

Use the existing `mockPalsHubPal` base and spread overrides, matching the local style. Reuse the existing `(palRepository.createPal as jest.Mock).mockResolvedValue(...)` mocking.

**Verification**:

- `yarn test src/store/__tests__/PalStore.test.ts` — all new + existing cases pass.
- `yarn test --findRelatedTests src/store/PalStore.ts` — full related-test fan-out passes.

### Step 6: Absorb WHAT delta into `context/architecture/pals-and-talents.md` (+ critic cosmetic fix)

**Implements**: WHAT §11 (drift fix-up), plus the round-2 critic SUGGESTION on §9a wording.

**Files**:

- `context/architecture/pals-and-talents.md` — two surgical edits, no other content changes.
- `workflows/stories/TASK-20260524-2236/what.md` — one cosmetic line edit (critic SUGGESTION absorption).

**Approach**:

1. **Architecture §1c drift fix** (WHAT §11). Replace the existing `(?)` block at `context/architecture/pals-and-talents.md:91-96` with a single `(C)` line:

   ```
   (C) `LocalPal.greetingObject` returns `Pal['greeting']` directly via
   `JSON.parse`; defensive against malformed JSON.
   ```

   Verify before editing that `src/database/models/LocalPal.ts:128-134` still returns `Pal['greeting']` (it does today — confirmed at HOW research time). If the code has since changed, surface and STOP rather than silently editing.

2. **Critic SUGGESTION absorption** in `workflows/stories/TASK-20260524-2236/what.md`, §9a final paragraph (currently reading "the chat-side visibility gate at `ChatView.tsx` (`text.trim().length > 0`)"). The actual gate at `src/components/ChatView/ChatView.tsx:853` is the plain truthy check `activePal?.greeting?.text && modelStore.activeModelId`. Per the critic note (and architect's review-history table allowing only cosmetic correction), rewrite the sentence to quote the real check:

   > When `text` is emitted as `''` (text absent / empty but chips present), the chat-side visibility gate at `ChatView.tsx:853` (`activePal?.greeting?.text && modelStore.activeModelId`) treats the empty string as falsy and hides the empty bubble; chips still render. This matches today's behaviour for in-app pals that have only suggested prompts.

   Do NOT change the behaviour described elsewhere in WHAT — the conversion contract (emit `text: ''` when only chips are present) is unchanged. Only the chat-side gate description changes.

3. The architecture doc has no other drift the WHAT identified. The `what.md` story file itself remains in `workflows/stories/` for archival and is not folded into the architecture doc per repo conventions.

**Verification**:

- `git diff context/architecture/pals-and-talents.md` shows only the §1c block change (≤ ~6 lines).
- `git diff workflows/stories/TASK-20260524-2236/what.md` shows only the §9a sentence rewrite.
- `grep -c '(?)' context/architecture/pals-and-talents.md` — count must not increase vs. baseline (the §1c `(?)` line is removed, the §8a `(?)` line about the PR-709 model-load gate is unchanged and out of scope for this story).
- A final `yarn typecheck && yarn lint && yarn test src/store/__tests__/PalStore.test.ts src/services/palshub/__tests__/PalsHubApiService.test.ts src/database/models/__tests__/LocalPal.test.ts` passes.

---

## Testable-Contract Coverage

The testable contract is WHAT §6 (canonical scenarios) plus the §9 edge cases that the WHAT explicitly enumerates as worked examples of the §4a predicate. Every row below maps to a test added in Step 4 or Step 5; the two "trivially today" scenarios (§6.C, §6.D, §6.F) are verified by virtue of leaving the existing code paths untouched — explicit regression assertions confirm they remain untouched.

| Contract item | Verified by |
| --- | --- |
| §6.A — Full pact + greeting (happy path) | Step 5 `happy path (§6.A)` case + Step 4 `forwards pact, greeting, images, models when present` |
| §6.B — Neither pact nor greeting (legacy) | Step 5 `legacy / both absent (§6.B)` case + Step 4 `leaves new fields undefined when absent` |
| §6.C — Recommended-model path unchanged | Step 3 leaves `defaultModel = palsHubPal.model_reference ? ... : undefined` (PalStore.ts:456-458) untouched; existing `downloadPalsHubPal` test (PalStore.test.ts:441-501) already asserts on `rawPalshubGenerationSettings` and `palshub_id` round-trip — runs unchanged and acts as the regression guard |
| §6.D — Primary-image / `thumbnail_url` path unchanged | Step 3 leaves the entire `downloadPalsHubPal` thumbnail branch (PalStore.ts:252-275) untouched; the existing `downloadPalsHubPal` test mocks `imageUtils.downloadPalThumbnail` and asserts the call — regression guard |
| §6.E — Unknown talent name preserved | Step 5 `unknown talent name preserved (§6.E)` case |
| §6.F — App restart preserves pact + greeting | Implicit — `PalRepository.createPal` already stringifies `palData.pact` / `palData.greeting` (PalRepository.ts:186-187) and `LocalPal.toPal()` already parses via `pactObject` / `greetingObject`. Existing test `LocalPal.toPal - pact / greeting round-trip` (LocalPal.test.ts:35-95) asserts the round-trip and continues to pass unchanged. Step 5 asserts the value is forwarded into `palRepository.createPal`; the round-trip itself is owned by the existing LocalPal test |
| §6.G — Strict-boolean `required` coercion | Step 5 `strict-boolean coercion (§6.G)` case |
| §9a — Partial greeting worked examples | Step 5 cases `greeting with only text`, `greeting with only prompts`, `greeting with text + empty prompts`, `greeting all empty`, `greeting: null`, `whitespace-only text passes through` |
| §9b — Empty/missing talents variants | Step 5 cases `empty talents array`, `pact: {version:1}` no talents key, `pact: null` |
| §9c — Whitespace-only text passes through | Step 5 `whitespace-only text passes through` case |
| §9d — Duplicate talent names | Out of scope per WHAT §9d (explicit non-goal); no test added |
| §9e — `pact: null` vs absent | Step 5 `pact: null` case |
| §9f — Older Palshub server (all four fields absent) | Same as §6.B coverage above |
| §9g — Export / import round-trip | Implicit — `exportUtils` / `importUtils` already round-trip both fields (architecture §8b); this story does not touch those modules. Existing tests in those modules (if present) continue to pass unchanged |

---

## Native Verification

Not required — `NATIVE_CHANGES=NO`. No changes to `package.json`, `ios/`, `android/`, Podfile, build.gradle, or any native module surface.

---

## Visual Confirmation

Not required — `Visual Confirmation=NO`. The story makes no UI change; the consumer surfaces (`GreetingBubble`, `SuggestedPrompts`, `TalentSurface`) already exist and are unchanged.

---

## Deferred Items

These remain in WHAT §10 / §5 and are NOT touched by this PR:

- Disclaimers data path / UI (intent non-goal).
- Multi-image gallery / carousel (intent non-goal).
- Alternative model picker beyond `is_recommended` (intent non-goal).
- Per-user consent UX for talents (intent non-goal).
- Re-download / refresh path for downloaded pals (WHAT D5).
- Tightening `images[]` / `models[]` types beyond `unknown[]` (WHAT D3).
- Enforcement gate for `necessity: 'required'` (architecture D1).
- Tightening of `transformApiPal` synthetic `creator` / `categories[].sort_order = 0` / `tags[].usage_count = 0` defaults (WHAT §5 deferred cleanup #2).
- Future-cleanup: removing `TalentUI.renderPending` (architecture D5).

---

## What this plan is NOT

- not a design doc — design lives in `what.md`.
- not a justification — `intent-brief.md` is where the request lives.
- not a UI plan — `ChatView.tsx` is not edited by this story; the §6 critic cosmetic fix is to WHAT §9a text only, not to the code.
- not a refactor of the existing `downloadPalsHubPal` thumbnail / model-reference branches — those are explicitly preserved as regression guards (§6.C, §6.D).
