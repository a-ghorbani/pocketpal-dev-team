# <Flow name> — WHAT

Story-scoped delta on `context/architecture/<flow>.md`.

**Markers**: `(C)` current, from code at `file:line`; `(F)` proven by a spike, with its receipt; `(P)` proposal; `(D)` engineering decision, ≤ 12-word rationale; `(?)` open (zero at LGTM). Premises are `(C)` or `(F)`, never `(P)`.

---

## Drift check

One line: `no drift` | `minor drift in <area>, repaired in this delta` | `STOP — major drift in <area>; reconcile first`.

---

## 0. Premises

Facts the design depends on. Spikes live in `<STORY_DIR>/spikes/`. An unproven premise is marked so, has a must-run row in `evidence.md`, and names what changes if it is false.

| ID | Premise | Marker | Proof |
| --- | --- | --- | --- |
| F1 | <fact> | (C) / (F) / unproven | `<file:line>` / `spikes/<name>` → <output excerpt> |

---

## Design exploration

Only with `DESIGN_EXPLORATION=YES`. Candidates: `<STORY_DIR>/design-candidate-*.md` or `<STORY_DIR>/spikes/`; don't paste them here.

### Alternatives considered

≤ 3 bullets, ≤ 12 words each. Omit if no real alternative.

- selected: <approach> — <why>
- rejected: <approach> — <why>

---

## 1. Data model

Only fields changing or at risk. Each new field, state, or mechanism names its reader in this PR and its scenario.

```
<top-level type>
  <field>: <type>           // <one-line meaning> — read by <function>, scenario <X>
  ...
```

Persisted: <fields, where>. Derived: <fields>.

**Glossary**:
- **<Term>** — <one line>

### 1b. External shape (skip if internal-only)

Wire format / API and how it maps to ours.

---

## 2. Event flow (skip if not event-driven)

```
<event-1>
  <event-2>+
  [<event-3>]
```

---

## 3. State machine (skip if no lifecycle)

States come from the dependency's actual type, enum, or docs; check that one axis isn't really two.

```
<state-A> ─<event>→ <state-B>
```

| State | User-visible feedback |
| --- | --- |
| `<state>` | <one line> |

---

## 4. Contract

### 4a. <Sub-rule>

1. <rule; order matters where stated>

### 4b. Hard invariants

- **I1**: <invariant>

### 4c. Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| `<Component>` | <what> | <what not> |

---

## 5. Single-writer rule

| Field | Single writer |
| --- | --- |
| `<field>` | `<function or path>` |

Cross-store reads: <one line per direction, or none>. Past multi-writer races: <one line, or none>.

**Deferred cleanups** (out of scope): <numbered, one line each>

---

## 6. Canonical scenarios

Input → output, ≤ 4 lines each; each maps to a test and an `evidence.md` row.

### A. <name>

```
<input or initial state>
─────
<observable output>
```

---

## 7. State signals (skip if no shared signals)

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `<signal>` | <writer> | <readers> | <predicate> |

---

## 8. Decisions

Engineering choices only; product calls go to `decisions.md`. Rationale ≤ 12 words; name the alternative it beats only when a real one exists.

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | <decision> | <≤ 12 words> |

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | <case> | <one line; cite invariant / decision; prefer an existing state> |

---

## 10. Required checks

Answer each, or `n/a: <reason>`.

| Check | Answer |
| --- | --- |
| Platform and library failure semantics (iOS and Android: cancel, interrupt, error, background, low memory) | <answer, with premise IDs> |
| Upgrade from the last release (data, files, settings an existing install has) | |
| Trust boundaries and new sinks (untrusted input → file / network / render / logs; new secrets) | |
| Concurrency and resource limits (parallelism caps, single-writer under races, low-RAM memory) | |

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | <one-line summary> | BLOCKER / CONCERN / SUGGESTION | FIXED <ref> / REJECTED <evidence file:line> / DEFERRED <ref> |
