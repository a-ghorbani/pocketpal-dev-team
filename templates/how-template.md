# Implementation Plan: <one-line summary>

**Purpose**: an executable worklist that lands the design specified in `what.md`. Reference WHAT sections by number; do not re-derive design content here. If a step requires a design decision that isn't already in WHAT, stop and route back to the architect.

This file lives at `workflows/stories/<TASK-ID>/how.md`.

---

## Metadata

- **Task ID**: TASK-YYYYMMDD-HHMM
- **Worktree**: `./worktrees/TASK-YYYYMMDD-HHMM`
- **Branch**: `feature/TASK-YYYYMMDD-HHMM`
- **Native Changes**: YES | NO
- **Visual Confirmation**: YES | NO
- **Intent Brief**: `./workflows/stories/<TASK-ID>/intent-brief.md`
- **WHAT**: `./workflows/stories/<TASK-ID>/what.md`
- **Architecture doc(s) being updated**: `./context/architecture/<flow>.md` (and any others)
- **Status**: draft | in-review | approved | implementing | done

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 | pending | - |  |
| Step 2 | pending | - |  |
| Step N | pending | - |  |
| Architecture doc updated | pending | - | absorb WHAT delta into `context/architecture/<flow>.md` |
| Cleanup reminders applied | pending | - | remove diagnostic code listed in WHAT §10 |

---

## Affected Files

| Path     | Change kind                  | WHAT reference |
| -------- | ---------------------------- | -------------- |
| `<path>` | <add / edit / delete / move> | `<§N>`         |
| `<path>` | <add / edit / delete / move> | `<§N>`         |

---

## Implementation Steps

Each step:

- references the WHAT section(s) it's executing (`§4a`, `§5`, etc.)
- is atomic (one logical change, one commit)
- specifies the file paths it touches
- states the acceptance check (lint, typecheck, targeted test, manual scenario)

### Step 1: <one-line>

**Implements**: WHAT §<N>.

**Files**:

- `<path>` — <what changes>

**Approach**: <short — what to do, in 3–5 lines max. Refer to WHAT for the contract.>

**Verification**:

- `yarn lint` passes
- `yarn typecheck` passes
- `yarn test --findRelatedTests <path>` passes
- (if applicable) Scenario `<§6.X>` from WHAT renders as expected

### Step 2: <one-line>

...

---

## Testable-Contract Coverage

The testable contract — the list of items the implementation must deliver — comes from:

- **standard / complex**: canonical scenarios in WHAT §6.
- **quick** (no WHAT): the user-visible outcomes implied by the request in `intent-brief.md`. Enumerate them here, briefly, before mapping to tests.

Map every contract item to a test (or manual scenario):

| Contract item | Verified by                                |
| ------------- | ------------------------------------------ |
| §6.A          | `<test file or manual scenario reference>` |
| §6.B          | `<test file or manual scenario reference>` |

---

## Native Verification (if NATIVE_CHANGES=YES)

```bash
cd "${WORKTREE_PATH}"
cd ios && pod install && cd ..
yarn ios --configuration Release
yarn android --variant=release
```

Note: skipping this step is a blocking review issue.

---

## Visual Confirmation (if Visual Confirmation=YES)

VISUAL_CAPTURES JSON specifying the prompts the reviewer will use to capture screenshots. Each entry names what to look for in the screenshot.

```json
[
  {
    "label": "<scenario>",
    "prompt": "<what to enter in the chat>",
    "look_for": "<what should be visible in the screenshot>"
  }
]
```

---

## Deferred Items

Anything WHAT explicitly defers (cleanups #1, #2 in WHAT §5). These do NOT land in this PR. They stay listed in WHAT for the next story to pick up.

- <ref to WHAT deferred cleanup, with brief reason it's out of scope here>

---

## What this plan is NOT

- not a design doc — design lives in `what.md`
- not a justification — `intent-brief.md` is where the request lives
- not exhaustive — only steps the implementer needs; if a step would just be "obey WHAT §N", reference WHAT instead of restating
