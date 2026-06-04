# Plan Candidate: <short strategy name>

Exploration artifact for high-risk implementation sequencing. This is not the executable worklist; the synthesizer uses candidates to produce the single final `how.md`.

---

## Metadata

- **Task ID**: TASK-YYYYMMDD-HHMM
- **Candidate**: A | B | C
- **Design source**: `./workflows/stories/<TASK-ID>/what.md` or `./context/architecture/<flow>.md`

---

## Strategy

One paragraph describing the implementation sequencing.

## Step Shape

1. <logical step>
2. <logical step>
3. <logical step>

## Commit Boundaries

- <commit scope and why>

## Verification

- Lint/typecheck:
- Focused tests:
- Manual / visual / native checks:

## Risks

- <risk in this sequence>

## Rejected If

- <condition that makes this sequence unsafe or too broad>
