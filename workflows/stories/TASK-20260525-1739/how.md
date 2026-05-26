# Implementation Plan: thinking-toggle user override in no-session chat path

**Purpose**: land the design in `what.md` — add `newChatThinkingOverride` as a MobX-only field, apply it as a last-layer overlay in the no-session resolver, route the chat-input toggle's no-session branch into it, and at session creation bake the override into the session by forcing `settingsSource = 'custom'` when present (clearing the override at the same site).

Design source: `workflows/stories/TASK-20260525-1739/what.md`. Reference WHAT section numbers; do not re-derive design.

---

## Metadata

- **Task ID**: TASK-20260525-1739
- **Worktree**: `./worktrees/TASK-20260525-1739`
- **Branch**: `feature/TASK-20260525-1739`
- **Native Changes**: NO
- **Visual Confirmation**: NO
- **Intent Brief**: `./workflows/stories/TASK-20260525-1739/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260525-1739/what.md`
- **Architecture doc(s) being updated**: `./context/architecture/pals-and-talents.md`, `./context/architecture/chat-flow.md`
- **Status**: MERGED — PR #745 (merge commit `8a097df`, merged 2026-05-26)

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — add `newChatThinkingOverride` field + clears | DONE | 4bb29fb | store-only, no behaviour yet |
| Step 2 — resolver last-layer override (no-session branch) | DONE | 9e0be22 | preview path stops snapping back |
| Step 3 — `'custom'`-at-birth handoff in `createNewSession` | DONE | a01a2b1 | survival into first inference |
| Step 4 — `ChatScreen.handleThinkingToggle` no-session branch + useEffect dep | DONE | 2da72fa | wires UI to the new field |
| Step 5 — store tests (resolver + handoff + clears) | DONE | 1fe00a0 | covers §6.A, C, E, F |
| Step 6 — ChatScreen test (toggle persists in no-session) | DONE | 1fe00a0 | covers §6.A end-to-end (real-render via `getByLabelText`) |
| Post-review S1 — atomic clear inside activation `runInAction` | DONE | 4930afb | review #1 S1: close the flicker window during session birth |
| E2E spec (`thinking-pal-override`) | DONE | 05e405e | 3 tests, verified passing on iPhone 17 Pro sim |
| Architecture doc updated | DONE | (this commit) | absorb WHAT delta into `pals-and-talents.md` §3 and `chat-flow.md` §5 |
| Cleanup reminders applied | DONE | (this commit) | none (WHAT §10 declares "no diagnostic code") |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/store/ChatSessionStore.ts` | edit | §1 (field), §4a (resolver), §4c (handoff), §5 (writers), §4d (I4, I5) |
| `src/screens/ChatScreen/ChatScreen.tsx` | edit | §4b (toggle handler), §7 (useEffect dep) |
| `src/store/__tests__/ChatSessionStore.palSettings.test.ts` | edit | §6.A, §6.B, §6.D |
| `src/store/__tests__/ChatSessionStore.test.ts` | edit | §6.C, §6.E, §6.F (clear sites + birth-source rule) |
| `src/screens/ChatScreen/__tests__/ChatScreen.test.tsx` | edit | §6.A (UI wiring) |
| `context/architecture/pals-and-talents.md` | edit | absorb WHAT §3 / §4a resolver order; add override mention to §3 explainer |
| `context/architecture/chat-flow.md` | edit | absorb WHAT §5 single-writer rows: new `newChatThinkingOverride` row + clarifying `session.settingsSource` / `session.completionSettings` rows that document today's writers (with D6 birth-rule note on `settingsSource`) |

No DB schema, no migration, no native files. (WHAT §1, D1.)

---

## Implementation Steps

Each step is one logical change, one commit. Verification commands assume `cd "${WORKTREE_PATH}"`.

### Step 1: add `newChatThinkingOverride` field and clear it on every reset site

**Implements**: WHAT §1 (data model), §4d I4/I5, §5 (single writer — clear half).

**Files**:

- `src/store/ChatSessionStore.ts` — add `newChatThinkingOverride: boolean | undefined = undefined;` next to `newChatPalId` / `newChatSettingsSource` (around line 88-89). Clear it in:
  - `resetActiveSession` (existing `runInAction` at line 309-316) — set to `undefined` alongside the existing `newChatPalId` / `newChatSettingsSource` resets, inside the same `runInAction`.
  - `setActiveSession` (existing `runInAction` at line 352-358) — set to `undefined` alongside the existing `newChatPalId` / `newChatSettingsSource` resets, inside the same `runInAction`.
  - `createNewSession` — set to `undefined` **in the same code block, immediately after** `this.newChatPalId = undefined;` (the existing `if (this.newChatPalId)` block at line 513-516). That clear is NOT inside a `runInAction` today; the existing pattern is a direct assignment in the async method body. Match it — do NOT wrap in a new `runInAction`. The `if (this.newChatPalId)` guard there is a metadata branch, not a clear gate; perform the override clear unconditionally on the line after that block closes. NOTE: this step does NOT yet read the override to decide birth-source — Step 3 adds that. Keeping clear-before-read here is safe because no writer exists yet.

**Approach**: pure plumbing. `makeAutoObservable` (line 114) auto-observes new public fields, so no decorator changes. No new action method needed — clears happen inline next to the existing peer-field clears, matching whatever pattern that site already uses (inside `runInAction` for `reset/setActiveSession`, plain assignment for `createNewSession`).

**Verification**:

- `yarn typecheck` passes (new field is `boolean | undefined`, matches WHAT §1).
- `yarn lint` passes.
- Existing test `src/store/__tests__/ChatSessionStore.test.ts` "preserves active pal ID when resetting active session" (line 1347) still passes — confirms `resetActiveSession` change is non-disruptive.

### Step 2: extend `resolveCompletionSettings` with the no-session override layer

**Implements**: WHAT §4a (resolver), §4d I1 (single-key), I2 (tools untouched), I3 (no-session-only at resolver).

**Files**:

- `src/store/ChatSessionStore.ts` — in `resolveCompletionSettings` (line 1346-1403), after the pal layer + PACT tools block (ends at line 1383) and BEFORE the `if (sessionId)` session branch (line 1386), add the override overlay:

  ```ts
  // No-session-only: apply user's explicit thinking override last so it
  // wins over pal's `enable_thinking`. Single-key overlay — does NOT
  // touch any other field, and does NOT affect tool availability (I1, I2).
  // See what.md §4a, §4d.
  if (!sessionId && this.newChatThinkingOverride !== undefined) {
    resolvedSettings = {
      ...resolvedSettings,
      enable_thinking: this.newChatThinkingOverride,
    };
  }
  ```

  Placement is critical: AFTER the PACT-tools block at line 1372-1382 (so tools are not stripped), BEFORE the `if (sessionId)` block at line 1386 (so session-branch resolution is unchanged — I3 / D4). Do NOT touch the session branch.

**Approach**: literal translation of the resolver diagram in WHAT §4a. The session branch resolution (line 1386-1400) is untouched — the override survives into sessions via Step 3's handoff, not via re-reading the override later (WHAT D4).

**Verification**:

- `yarn typecheck` / `yarn lint`.
- `yarn test src/store/__tests__/ChatSessionStore.palSettings.test.ts` — existing resolver tests still pass (override default is `undefined`, so no behaviour change for legacy paths).

### Step 3: `'custom'`-at-birth handoff in `createNewSession`

**Implements**: WHAT §4c (handoff), §4d I4 (override becomes session state), D6 (born `'custom'` even when source was `'pal'`).

**Files**:

- `src/store/ChatSessionStore.ts` — in `createNewSession` (line 467-527):
  1. Compute `birthSource` BEFORE the `metaData` object literal (around line 503): if `this.newChatThinkingOverride !== undefined` then `'custom'`, else `this.newChatSettingsSource` (preserves today's default).
  2. Replace `settingsSource: this.newChatSettingsSource,` on line 509 with `settingsSource: birthSource,`.
  3. Clear the override field **in the same code block, immediately after** the existing `this.newChatPalId = undefined;` (line 515). Match the existing pattern — plain assignment, no new `runInAction` wrapper. Reading `birthSource` at step 3.1 happens before the clear at step 3.3, both synchronously in the same method body, so no race (WHAT §9h). (Note: Step 1 already adds that clear line; this step does not duplicate the edit, only confirms placement order is correct.)
  4. The repository write at line 474-480 (`chatSessionRepository.createSession(...)`) passes `this.newChatSettingsSource` for the DB `settingsSource` column. Replace that argument with `birthSource` too — the DB row MUST agree with the in-memory metadata. This is the **DB write** referenced in the brief (the override decision must persist to the row, not only memory). Since `birthSource` is computed in step 3.1, hoist that computation above the repository call.

**Approach**: the resolved `completionSettings` passed in via `addMessageToCurrentSession` (line 429) already has the override applied (via Step 2's resolver change). So the baked `session.completionSettings` includes the user's choice. Forcing `birthSource = 'custom'` makes the resolver's session branch (line 1386-1400) return that baked snapshot verbatim on the first inference — pal's other completion settings preserved because they were merged in before the override (WHAT §4c, Scenario C).

Verify against the brief's claim "force `session.settingsSource = 'custom'` (DB + memory)": both the repo call at line 474-480 and the in-memory `metaData.settingsSource` at line 509 must use `birthSource`.

**Verification**:

- `yarn typecheck` / `yarn lint`.
- A new targeted test (added in Step 5) asserts that with `newChatThinkingOverride = false` and `newChatSettingsSource = 'pal'`, `createNewSession` produces `session.settingsSource === 'custom'` AND the override is cleared AND `chatSessionRepository.createSession` was called with `'custom'` as the `settingsSource` argument.

### Step 4: route the no-session toggle handler into the new field, add useEffect dep

**Implements**: WHAT §4b (toggle handler), §7 (useEffect dep on `newChatThinkingOverride`).

**Files**:

- `src/screens/ChatScreen/ChatScreen.tsx` — in `handleThinkingToggle` (line 178-200), the `else` branch (line 193-198) currently writes `newChatCompletionSettings`. Replace its body with a direct write to `chatSessionStore.newChatThinkingOverride`:

  ```ts
  // No active session: stage the user's choice on the new-chat override
  // field. Resolver applies it as the last layer (what.md §4a) so the
  // toggle persists. Does NOT touch newChatCompletionSettings or
  // newChatSettingsSource (what.md §5 single-writer table).
  runInAction(() => {
    chatSessionStore.newChatThinkingOverride = enabled;
  });
  ```

  Notes:
  - Keep the function `async` (other call sites await it) but the body for this branch is sync; an explicit `runInAction` keeps the write inside an action (consistent with the codebase's MobX style — see e.g. `ChatSessionStore.ts:309`).
  - Do NOT also call `setNewChatCompletionSettings` — the design intentionally leaves global settings untouched (WHAT §5, "single-writer rows untouched"). The previous write to global was the bug.
  - `runInAction` import comes from `mobx`; verify it is already imported at top of `ChatScreen.tsx` and add if missing — keep the import surgical.

- `src/screens/ChatScreen/ChatScreen.tsx` — in the existing `useEffect` that re-seeds `thinkingEnabled` (line 114-131), add `chatSessionStore.newChatThinkingOverride` to the dependency array (between `chatSessionStore.newChatCompletionSettings` and `activePalId`). This makes a toggle tap propagate without waiting for an unrelated re-render (WHAT §7).

**Approach**: smallest possible diff. The session-bound `if (currentSession)` branch (line 183-191) is untouched (WHAT §3 paths A/B unchanged).

**Verification**:

- `yarn typecheck` / `yarn lint`.
- A new ChatScreen test (Step 6) asserts that tapping the toggle in the no-session view writes `newChatThinkingOverride` (and does NOT write `newChatCompletionSettings`).

### Step 5: store tests for resolver, handoff, clears

**Implements**: WHAT §6 canonical scenarios A, C, E, F at the store level.

**Files**:

- `src/store/__tests__/ChatSessionStore.palSettings.test.ts` — add a new `describe('newChatThinkingOverride', …)` block after the existing `getCurrentCompletionSettings` block (line 199). Tests:
  1. **§6.A — override wins over pal in no-session resolver**: set up pal with `completionSettings.enable_thinking = true`; set `newChatPalId = palX`, `newChatThinkingOverride = false`; call `resolveCompletionSettings(undefined, 'palX')`; expect `result.enable_thinking === false` AND pal's other params (e.g. add `temperature: 0.5` to pal) are preserved.
  2. **§6.A — override re-applied: flipping back on**: same setup, override = `true`, expect `true`.
  3. **§4d I3 — override does NOT apply on session branch**: with override set and session `settingsSource = 'pal'`, call `resolveCompletionSettings('sessionId', 'palX')`; expect `result.enable_thinking` to equal pal's value, NOT override. (Confirms I3 / D4 invariant.)
  4. **§4d I2 — override does NOT touch tools**: pal has `pact.talents` with a registered talent; with override set, `resolveCompletionSettings(undefined, palId)` still includes `result.tools` from PACT. (Use existing `deriveToolSchemas` path — pick `calculate` since it's already registered in `services/talents/index.ts`.)

- `src/store/__tests__/ChatSessionStore.test.ts` — add tests near the `pal management` block (line 1300-1374):
  5. **§6.C / §4c handoff — `'custom'`-at-birth when override is set**: set `newChatPalId = 'palX'`, `newChatSettingsSource = 'pal'`, `newChatThinkingOverride = false`; call `createNewSession('title', [...], settings)`; expect `sessions[0].settingsSource === 'custom'`, `newChatThinkingOverride === undefined` after, `newChatPalId === undefined` after. Also assert that `chatSessionRepository.createSession` (mocked) was called with `'custom'` as the `settingsSource` argument — guards the DB-side handoff from Step 3.
  6. **§4c handoff — birth-source default unchanged when no override**: same as 5 but `newChatThinkingOverride = undefined`; expect `sessions[0].settingsSource === 'pal'` (or whatever `newChatSettingsSource` was). Regression guard.
  7. **§6.E / §4d I5 — override clears on `resetActiveSession`**: set override, call `resetActiveSession`, expect `newChatThinkingOverride === undefined`.
  8. **§6.E / §4d I5 — override clears on `setActiveSession`**: set override + a fake session; call `setActiveSession(existingId)`; expect `newChatThinkingOverride === undefined`.

**Approach**: copy the shape of the existing `palSettings.test.ts` and `ChatSessionStore.test.ts` cases verbatim — mock `palStore.pals` for pal-presence tests; rely on the in-memory `sessions` array for session-branch tests (no DB hits needed for resolver assertions). For tests 5/6, mock `chatSessionRepository.createSession` and `chatSessionRepository.getSessionById` consistently with existing tests around line 1366 ("applies newChatPalId when creating a new session").

**Verification**:

- `yarn test src/store/__tests__/ChatSessionStore.palSettings.test.ts` — new tests pass.
- `yarn test src/store/__tests__/ChatSessionStore.test.ts -t "newChatThinkingOverride\|custom-at-birth\|override clears"` — new tests pass.

### Step 6: ChatScreen test — no-session toggle writes the override field

**Implements**: WHAT §6.A end-to-end (UI → store).

**Files**:

- `src/screens/ChatScreen/__tests__/ChatScreen.test.tsx` — add a test in the existing `describe('ChatScreen', …)`. Pattern follows the existing "renders correctly when model is loaded" and "handles sending a message" fixtures (lines 44-101): real-render `ChatScreen`, locate the UI element, `fireEvent.press`, assert observable state.

  **Setup**: load model (copy lines 60-72 of existing tests for the `modelStore` setup); set `chatSessionStore.activeSessionId = null` (no session) inside `runInAction`; install a pal in `palStore.pals` with `completionSettings.enable_thinking = true` and set `chatSessionStore.newChatPalId = palX.id`. The pal must report thinking-capable so the toggle renders (`showThinkingToggle: thinkingSupported` in `ChatScreen.tsx:228`). Verify how the existing `palSettings.test.ts` constructs a thinking-capable pal and mirror that.

  **Locate the toggle**: use `getByLabelText('Enable thinking mode')` — the `<TouchableOpacity>` in `ChatInput.tsx:546-580` already sets `accessibilityLabel` to the localized "Enable thinking mode" / "Disable thinking mode" string (toggled by `isThinkingEnabled`). This is the **same pattern** as `src/components/ChatInput/__tests__/ChatInputThinking.test.tsx:166-176`. No new testID is required.

  **Trigger and assert**:
  ```ts
  const toggleButton = getByLabelText('Enable thinking mode'); // initial: thinking off
  await act(async () => { fireEvent.press(toggleButton); });
  expect(chatSessionStore.newChatThinkingOverride).toBe(true);
  // Negative-side guard: global was NOT touched.
  expect(chatSessionStore.setNewChatCompletionSettings).not.toHaveBeenCalled();
  ```

  The positive assertion (`newChatThinkingOverride === true`) is the primary signal — the test passes only if the toggle is wired into the new field. The negative-side spy assertion is a guard rail, not the sole signal. (The `setNewChatCompletionSettings` mock already exists in the test fixture — confirm by inspecting the jest mock setup for `chatSessionStore`; if it's not auto-mocked, add a `jest.spyOn(chatSessionStore, 'setNewChatCompletionSettings')` in the test's `beforeEach`.)

**Approach**: real-render + accessibility-label lookup matches the existing ChatScreen.test.tsx style (the "handles sending a message" test uses `getByPlaceholderText` + `fireEvent.press` on `send-button`). Production code does NOT change — the toggle's existing `accessibilityLabel` is the test handle.

**Verification**:

- `yarn test src/screens/ChatScreen/__tests__/ChatScreen.test.tsx` — passes.

### Step 7: absorb WHAT delta into architecture docs

**Implements**: AGENTS.md "every PR that changes behaviour described in `context/architecture/*.md` must update the relevant doc in the same PR." WHAT §10 cross-references.

**Files**:

- `context/architecture/pals-and-talents.md`:
  - §3 ("PACT → tools derivation"): no contract change (override is single-key, does not touch `tools` — WHAT I2). Add one sentence at the end of the section noting the no-session override layer applies AFTER PACT tools (`see chat-flow.md §5`).
  - §6 (single-writer rule): no change required — the override field is owned by `ChatSessionStore`, and `pals-and-talents.md` §6 covers pal / PACT writers only. Skip.

- `context/architecture/chat-flow.md` §5 ("Layer ownership — single-writer rule"): the existing table covers in-flight session step/metadata writers only. Add three rows in one edit so the new `newChatThinkingOverride` row is not orphaned. Picking **option (a)** from the plan-critic concern — the two existing-behaviour rows are `(C)` (current, documenting today's behaviour); the new row is `(C)` (current after this PR). Place them as a small group at the top or bottom of the table:

  | Field | Single writer |
  |---|---|
  | `session.completionSettings` (in `sessions[]` metadata) | `createNewSession` at birth (`ChatSessionStore.ts`) — baked from the resolver's no-session output; updated thereafter only by `ChatGenerationSettingsSheet` save flow (`updateSessionCompletionSettings`). `(C)` |
  | `session.settingsSource` (in `sessions[]` metadata) | `createNewSession` at birth (`ChatSessionStore.ts`); updated thereafter only by `ChatGenerationSettingsSheet` save flow. Birth-rule (D6): `'custom'` if `newChatThinkingOverride !== undefined`, else `newChatSettingsSource`. `(C)` |
  | `chatSessionStore.newChatThinkingOverride` | `ChatScreen.handleThinkingToggle` (set, no-session branch only); `createNewSession`, `resetActiveSession`, `setActiveSession` (clear). Read by `resolveCompletionSettings` no-session branch only. `(C)` |

  The D6 birth-rule lives in the `session.settingsSource` row's text (per option (a)) — not in a separate `newChatThinkingOverride` annotation — because it's a writer rule about `settingsSource`.

- Convert WHAT's `(P)` markers to `(C)` in §1, §3, §4, §5, §7 of `workflows/stories/TASK-20260525-1739/what.md` once code has landed. Leave `(D)` markers as `(D)`. The story-scoped `what.md` stays intact for archival; this is a `(P)→(C)` flip in-place, not a deletion.

Verify NO `(?)` markers remain on the architecture docs after this step.

**Approach**: keep the delta tight — one sentence in `pals-and-talents.md`, three table rows in `chat-flow.md` §5 (one for the new field, two documenting today's `session.*` writers so the new row has neighbours), plus the `(P)→(C)` flip in `what.md`. Do not restate the design; reference WHAT for the long form (which will live alongside the story for archival).

**Verification**:

- `git diff context/architecture/` shows only the anchored edits described above.
- `grep -n '(?)' context/architecture/pals-and-talents.md context/architecture/chat-flow.md` returns no NEW open questions (the existing `(?)` for greeting model-load gate in `pals-and-talents.md` §8a is unrelated and stays).
- `grep -n '(P)' workflows/stories/TASK-20260525-1739/what.md` returns nothing (all proposals are now `(C)`).

---

## Testable-Contract Coverage

The testable contract is WHAT §6 (canonical scenarios). Mapping:

| Contract item | Verified by |
| --- | --- |
| §6.A — default pal, user flips OFF → override wins, toggle stays | `ChatSessionStore.palSettings.test.ts` new "override wins over pal" + ChatScreen toggle test (Step 6, accessibility-label path) |
| §6.B — authored pal `enable_thinking=false`, user flips ON | covered by the same "override wins" resolver test with palX setting flipped; no separate assertion required — same code path |
| §6.C — override carries into the new session AND first inference | `ChatSessionStore.test.ts` new "`'custom'`-at-birth when override is set" test (asserts `settingsSource === 'custom'` in memory AND in the repo call, and the resolver's session branch returns the baked snapshot) |
| §6.D — ChatGenerationSettingsSheet `'custom'` + toggle | covered transitively: existing source=`'custom'` path is unchanged; the `'custom'`-at-birth rule coincides with today's behaviour when override is set (WHAT §6.D body). Manual smoke recommended; no dedicated automated test (path is unchanged from today by construction). |
| §6.E — second new-chat after override applied, override does not leak | `ChatSessionStore.test.ts` new "override clears on `resetActiveSession`" + "override clears on `setActiveSession`" tests |
| §6.F — override + tool-capable pal preserves PACT tools | `ChatSessionStore.palSettings.test.ts` new "override does NOT touch tools" test (I2) |

`yarn test` aggregate across the changed files should land green; no pre-existing tests should change behaviour because the override defaults to `undefined` (no-op path).

---

## Native Verification

`NATIVE_CHANGES=NO` — JS/TS only (WHAT §1b "no wire-format changes," §1c "no DB schema, no migration"). No `pod install`, no native build required. (AGENTS.md gate satisfied.)

---

## Visual Confirmation

`Visual Confirmation=NO` — no UI redesign; behavioural fix only. Manual repro per intent-brief is sufficient for human reviewer.

---

## Deferred Items

WHAT §5 explicitly defers:

1. Stripping `enable_thinking` from pals by default + DB migration (intent option 1). Rejected for this story per WHAT D2.
2. Generic per-chat override layer (intent option 2). Rejected per WHAT D3 — narrow single-key override is the minimum viable shape.
3. Path-D preview-vs-inference asymmetry between `getCurrentCompletionSettings` (line 1408-1417) and `addMessageToCurrentSession` (line 427-432). Pre-existing, untouched by this story (WHAT §9g).

These stay listed in WHAT for a future story to pick up.

---

## What this plan is NOT

- not a design doc — design lives in `what.md`
- not a re-derivation of invariants — invariants live in WHAT §4d
- not a refactor — the smallest diff that satisfies WHAT §6 wins
- not a fix to pal storage shape (WHAT D2)
- not a generic override layer (WHAT D3)

---

## §11. Review History

### Round 1 (pocketpal-plan-critic) — HAS_CONCERNS (no BLOCKERs, LGTM with concerns + suggestion)

| # | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| 1 | CONCERN | Step 7 `chat-flow.md` §5 edit would leave `newChatThinkingOverride` as an orphan row; existing §5 has no `session.settingsSource` or `session.completionSettings` rows either. Critic offered (a) add the two missing existing-behaviour rows as `(C)` alongside the new row with D6 birth-rule on `settingsSource`, or (b) move the new row into `pals-and-talents.md` §6. | **FIXED — option (a).** Step 7 now adds three rows in one edit: two `(C)` rows documenting today's `session.completionSettings` / `session.settingsSource` writers, and the new `(C)` row for `newChatThinkingOverride`. The D6 birth-rule for `settingsSource` is in the `session.settingsSource` row's writer text (per option (a)). Affected-files table at the top now also names the row group. Choice rationale: the new field is most naturally read alongside the session-state writers it influences, and the two `(C)` rows are documentation debt the project has had anyway. Avoids cross-doc indirection. |
| 2 | CONCERN | Step 6 ChatScreen test relied on a negative-only spy assertion (`setNewChatCompletionSettings` not called). Critic preferred the existing positive-assertion pattern from this file (real-render + `fireEvent` + observe state). | **FIXED.** Step 6 now uses `getByLabelText('Enable thinking mode')` — the `<TouchableOpacity>` in `ChatInput.tsx:546-580` already exposes that `accessibilityLabel`, and `ChatInput/__tests__/ChatInputThinking.test.tsx:159-176` already uses this exact pattern. Real `fireEvent.press`, positive assertion `expect(chatSessionStore.newChatThinkingOverride).toBe(true)`. The negative spy is kept as a guard rail, not the sole signal. **No production-code testID required** — the design uses the existing accessibility label. |
| 3 | SUGGESTION | Steps 1 and 3 said "same `runInAction` block as `newChatPalId = undefined`", but the actual clear at lines 513-516 of `createNewSession` is NOT inside a `runInAction` — it's a plain assignment in the async method body. The later `runInAction` (520-523) is for `sessions.push`. | **FIXED.** Step 1 (`createNewSession` bullet) and Step 3 (clear bullet) now read "**in the same code block, immediately after** `this.newChatPalId = undefined;`" and explicitly say "Match the existing pattern — plain assignment, no new `runInAction` wrapper." The `reset/setActiveSession` clears DO sit inside an existing `runInAction`; that wording was already correct and is preserved. |

**Status**: all three findings FIXED in this revision. No items REJECTED or DEFERRED. Ready for re-review.
