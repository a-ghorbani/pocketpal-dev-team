# <Flow name> — WHAT

Story-scoped delta on `context/architecture/<flow>.md`. On promotion, the delta absorbs into that doc in the same PR.

**Conventions**: `(C)` current (verified from code), `(P)` proposal, `(?)` open question (zero allowed at LGTM), `(D)` decision with ≤ 12-word rationale.

---

## Drift check

One line: `no drift` | `minor drift in <area>, repaired in this delta` | `STOP — major drift in <area>; reconcile first`.

---

## 1. Data model

Only fields changing or at risk.

```
<top-level type>
  <field>: <type>           // <one-line meaning>
  ...
```

Persisted: <fields, where>. Derived: <fields>.

**Glossary** (terms used below):
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

```
<state-A> ─<event>→ <state-B>
```

| State | User-visible feedback |
| --- | --- |
| `<state>` | <one line> |

---

## 4. Contract

### 4a. <Sub-rule>

Numbered rules; order matters where stated.

1. <rule>

### 4b. Hard invariants

- **I1**: <invariant>
- **I2**: <invariant>

### 4c. Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| `<Component>` | <what> | <what not> |

---

## 5. Single-writer rule

| Field | Single writer |
| --- | --- |
| `<field>` | `<function or path>` |

Cross-store reads (if any): one line per direction.

Past pain related to multi-writer races: <one line, or "none">.

**Deferred cleanups** (out of current scope): <numbered, one line each>

---

## 6. Canonical scenarios

Input → output, ≤ 4 lines per scenario. Each maps to a test.

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

One row each. Rationale ≤ 12 words. Do not defend alternatives the critic might raise — wait for the critic to ask.

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | <decision> | <≤ 12 words> |

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | <case> | <one line; cite invariant / decision> |

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | <one-line summary> | BLOCKER / CONCERN / SUGGESTION | FIXED <ref> / REJECTED <evidence file:line> / DEFERRED <ref> |
