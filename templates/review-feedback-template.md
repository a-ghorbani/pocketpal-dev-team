# Review Feedback Intake: <PR or task> Round <N>

Normalized input for a PR-fix pipeline. Import actionable findings from `workflows/reviews/<TARGET_ID>/round-<N>/final.md`; do not paste reviewer reasoning that is not needed to implement the fix.

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

Only `BLOCKER` and `CONCERN` findings are mandatory. `SUGGESTION` findings are out of scope unless needed to fix a mandatory item.

| ID | Severity | Lens | Path | Line | Required fix |
| --- | --- | --- | --- | --- | --- |
| R1 | BLOCKER | Correctness | `src/...` | 123 | <one-sentence fix> |

---

## Verification Required

- <command or manual check from review final.md>

---

## Out Of Scope

- <suggestions or deferred items not required for this fix round>
