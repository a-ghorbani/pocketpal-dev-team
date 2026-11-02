# Fix brief: <PR or task> Round <N>

Actionable findings from `workflows/reviews/<TARGET_ID>/round-<N>/final.md`, without reviewer reasoning the fix doesn't need.

---

## Metadata

- **Source review**: `workflows/reviews/<TARGET_ID>/round-<N>/final.md`
- **Target PR**: #<number>
- **Target branch**: `<branch>`
- **Worktree**: `./worktrees/PR-<number>`
- **Status**: draft | approved-for-fix | fixed | superseded

---

## Verdict

- **Review verdict**: APPROVE | REQUEST_CHANGES | ESCALATE
- **Review complete**: yes | no
- **Role subreviews**: COMPLETED | BLOCKED | NOT_REQUIRED

---

## Fix Scope

`BLOCKER` and `CONCERN` findings only; `SUGGESTION`s go to the PR's follow-ups (the `Follow-ups` list of the published review). A finding that contradicts `decisions.md` or WHAT, that an earlier round already fixed, or whose fix needs a contract, state, owner, or persisted field WHAT doesn't record (on trivial or quick work, any new contract) is `DESIGN_INVALIDATED`, not a row.

| ID | Severity | Path:line | State touched | Owned at | Writers / callers checked | Required fix |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | BLOCKER | `src/...:123` | <field, file, or lifecycle> | <where that state is decided> | <each writer and caller, file:line> | <one sentence, applied at the owner> |

---

## Evidence to re-run

Each finding's own check, plus the `evidence.md` rows covering every surface a fix touches.

- <E-id or new row>

---

## Out Of Scope

- <suggestions or deferred items>
