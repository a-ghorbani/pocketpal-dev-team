# Architecture Library

This directory holds the **cumulative architecture truth** for PocketPal AI, organised per flow.

The library exists to stop the team from rebuilding the same design over and over inside each story. It captures **what the system must obey** — contracts, invariants, single-writer rules, canonical scenarios — independent of the implementation steps that get the code there.

---

## What lives here

One file per **flow**. A flow is bounded by a single user-facing concept:

- `chat-flow.md` — chat rendering, streaming, tool calls, agent loop
- `model-loading.md` — model download, init, unload, errors
- `pals-and-talents.md` — pal config, talent dispatch, registry
- `persistence.md` — DB schema, migrations, exports, MMKV keys
- `vision.md` — multimodal pipeline (when it lands)
- `release.md` — CI / build / TestFlight / Play Store

Per-flow is the right granularity. Per-component is too narrow (components churn). Per-system is too broad (becomes a book nobody reads).

A flow file does NOT live here until at least one story has produced a vetted WHAT for it. The library accrues lazily — the moment a flow has needed a WHAT, it has a doc here. Other flows stay undocumented until someone touches them.

---

## Lifecycle

```
Story-scoped WHAT (delta)            Cumulative architecture (this dir)
─────────────────────────            ──────────────────────────────────
workflows/stories/<TASK-ID>/         context/architecture/<flow>.md
  what.md                            (current truth)

  proposes additions, changes,       (read by next story's architect
  decisions, edge cases on top       to draft its delta against this)
  of context/architecture/<flow>.md
                                                ▲
            on PR merge ──────────────────────  │
                                                │
              architect updates the architecture
              file with the approved delta in
              the SAME PR that lands the code
```

The story-scoped `what.md` is born **as a delta** on the architecture file and dies **merged into it** when the work ships.

---

## Conventions used in architecture files

Mark every claim with one of:

- **(C)** — current behaviour, documented from code
- **(P)** — proposal, open for challenge
- **(?)** — open question, decision needed
- **(D)** — decision (was an open question, now resolved)

Architecture files should mostly be **(C)** — they're current truth. Story WHATs are mostly **(P)** and **(?)** — they're deltas being proposed. On merge, the architect resolves the markers (anything (P) becomes (C); any remaining (?) is a bug — the WHAT shouldn't have shipped).

---

## Required sections (template)

Every architecture file should have:

1. **Data model** — the on-disk and in-memory shape. Glossary for any term used elsewhere in the doc.
2. **External shape** — wire format / API / protocol the flow exposes (if any).
3. **State machine** — lifecycle states, transitions, what the user sees in each (if any).
4. **Contract** — for each component participating in the flow: what it renders / produces / writes; what it does NOT.
5. **Single-writer rule** — for each mutable field, the canonical writer. Reading is unrestricted.
6. **Canonical scenarios** — the rendered or observable shapes the design must produce. Manually testable.
7. **Edge cases** — what happens at the boundaries (cancel, empty, race, missing dependency).
8. **Decisions** — resolved trade-offs. Each has a short rationale.

Use `templates/what-template.md` as a starting point.

---

## Drift prevention

Architecture docs and code drift unless the pipeline enforces alignment:

- **PR-time check** — every PR's diff review verifies: "does this PR change any behaviour described in `context/architecture/*.md`? If yes, the same PR must update the doc."
- **Story-time check** — the architect reads the relevant architecture doc at the start of every story. If the doc no longer matches code, the architect produces a small fix-up commit BEFORE drafting the story's `what.md`. The story doesn't get to add a delta on top of stale truth.

Architecture drift is the failure mode that brings back the ping-pong this library was created to prevent.

---

## What this library is NOT

- **Not a TODO list** — it describes the system as it should be, not work to be done.
- **Not an implementation plan** — those live in story-scoped `how.md` files.
- **Not historical** — old behaviour gets overwritten on merge, not appended. Git history preserves the past.
- **Not exhaustive** — only the flows currently under active design or that have hit pain points need a doc. Don't back-document the rest of the app speculatively.
- **Not a substitute for code** — when the doc and the code disagree, the code wins, then the doc gets fixed. Drift is fought, not ignored.

---

## Bootstrap

The library starts empty. The first entry will be `chat-flow.md`, promoted from the AssistantTurn refactor's WHAT (`workflows/stories/TASK-20260502-2115-flow-analysis.md`) once that work lands and its canonical scenarios verify cleanly.

After that, every standard/complex story either:

- adds a new flow file (when the work is in an undocumented area), or
- proposes a delta on an existing flow file (when the work touches an already-documented area).
