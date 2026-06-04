# Implementation Plan: <one-line summary>

Executable worklist for the design source (`what.md` for standard/complex, `context/architecture/<flow>.md` for quick). Reference design-source sections by number; do not re-derive design here. If a step needs a decision not in the source, STOP and route back.

---

## Metadata

- **Task ID**: TASK-YYYYMMDD-HHMM
- **Worktree**: `./worktrees/TASK-YYYYMMDD-HHMM`
- **Branch**: `feature/TASK-YYYYMMDD-HHMM`
- **Native Changes**: YES | NO
- **Visual Confirmation**: YES | NO
- **Intent Brief**: `./workflows/stories/<TASK-ID>/intent-brief.md`
- **WHAT**: `./workflows/stories/<TASK-ID>/what.md` (omit for quick)
- **Architecture doc(s)**: `./context/architecture/<flow>.md`
- **Status**: draft | in-review | approved | implementing | done

---

## Progress

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 | pending | - | |
| Architecture doc updated | pending | - | absorbs WHAT delta (standard/complex only) |
| Cleanup reminders applied | pending | - | per WHAT §10 |

---

## Affected files

| Path | Change | Design ref |
| --- | --- | --- |
| `<path>` | add / edit / delete / move | `<§N>` |

---

## Plan exploration

Required for complex stories; optional for standard stories when execution sequencing is risky.

Candidate artifacts, if used:
- `workflows/stories/<TASK-ID>/plan-candidate-A.md`
- `workflows/stories/<TASK-ID>/plan-candidate-B.md`
- `workflows/stories/<TASK-ID>/plan-candidate-C.md`

This HOW is the synthesized executable plan. Do not paste full candidate docs here.

### Sequencing note

One line only. Explain the chosen order only if non-obvious; otherwise write `standard order`.

---

## Steps

Each step is atomic — one logical change, one commit.

### Step 1: <one-line>

**Implements**: §<N>.

**Files**: `<path>` — <what changes>

**Approach** (≤ 5 lines): <what to do; reference design source for the contract>

**Verification**: lint / typecheck / `yarn test --findRelatedTests <path>` / scenario `§6.X`.

---

## Testable-contract coverage

Standard/complex: one row per WHAT §6 scenario. Quick: enumerate user-visible outcomes from the intent brief, one row each.

| Contract item | Verified by |
| --- | --- |
| §6.A | `<test file or manual scenario>` |

---

## Review / debug strategy

Use this to make downstream debugging and independent review deterministic.

- **Riskiest files**: `<path>` — <why>; max 3
- **Expected failure modes**: <max 3 short phrases>
- **Tests that should fail if wrong**: `<test file or command>`; max 3
- **Manual verification required**: <scenario or N/A>
- **Independent reviewer focus**: <max 2 code paths, invariants, or evidence checks>

---

## Native verification (if NATIVE_CHANGES=YES)

```bash
cd "${WORKTREE_PATH}"
cd ios && pod install && cd ..
yarn ios --configuration Release
yarn android --variant=release
```

Skipping is a blocking review issue.

---

## Visual confirmation (if Visual Confirmation=YES)

```json
[
  {"label": "<scenario>", "prompt": "<chat input>", "look_for": "<what should be visible>"}
]
```

---

## Deferred items

- <ref to WHAT deferred item, ≤ 1 line>

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | <one-line> | BLOCKER / CONCERN / SUGGESTION | FIXED <ref> / REJECTED <evidence file:line> / DEFERRED <ref> |
