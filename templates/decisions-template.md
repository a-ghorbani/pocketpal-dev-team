# Decisions: <TASK_ID>

Product calls, prior decisions, operator and PM rulings, and review dismissals (`docs/workflows/pipeline.md`, Decisions and product calls). Append only; reverse a row with a new row that names it.

| ID | Kind | Decision | By | Source | Status |
| --- | --- | --- | --- | --- | --- |
| P1 | product call | <the call> — default: <recommended answer> | default (operator may override) / operator / PM | intake / architect / review R<n> | active / reversed by <ID> |
| H1 | prior decision | <what the code does on purpose> — <why, from its PR> | #<PR> | repro | active |
| O1 | ruling | <verbatim> | operator / PM, <date> | <where it was given> | active |
| X1 | review dismissal | <finding, one line> — <reason it is not acted on> | review round <n> refutation | `workflows/reviews/.../final.md` | active |
