# <Flow name> — Architecture & Flow Board

**Purpose**: design board for one flow within PocketPal. Captures **what the system must obey** — contracts, invariants, single-writer rules, canonical scenarios — independent of any individual implementation.

When this is a **story-scoped delta**, it lives at `workflows/stories/<TASK-ID>/what.md` and proposes additions / changes on top of `context/architecture/<flow>.md`. On PR merge, the relevant sections get absorbed into the architecture file in the same PR.

When this is a **promoted architecture doc**, it lives at `context/architecture/<flow>.md` and is the cumulative truth for that flow.

---

## Conventions

- **(C)** = current behaviour, documented from code
- **(P)** = proposal, open for challenge
- **(?)** = open question, decision needed
- **(D)** = decision (was an open question, now resolved)

A story WHAT is mostly **(P)** + **(?)**. On promotion, those become **(C)** and **(D)**. A promoted architecture doc shouldn't have any **(?)** left.

---

## 1. Data model

The on-disk and in-memory shape used by this flow.

```
<top-level type>
  <field>: <type>           // <one-line meaning>
  <field>: <type>
  <nested type>
    <field>: <type>
  ...
```

Stored on disk: <which fields are persisted, and where>. Computed at render / runtime only: <which fields are derived>.

**Glossary** — terms used elsewhere in this doc:

- **<Term>** — <one-line gloss>
- **<Term>** — <one-line gloss>

---

## 1b. External shape

If this flow exposes or consumes a wire format / API / protocol, document the shape here and how it maps to ours. Skip if the flow is purely internal.

---

## 2. Event flow

If the flow is event-driven (runner emits events, hook applies them, store mutates), document the event order and what each event carries.

```
<event-1>
  <event-2>+
  [<event-3>]
<event-4> | <event-5>
```

---

## 3. State machine

If the flow has a finite-state lifecycle (reducer, status enum, etc.), document the states and transitions.

```
<state-A>
  ─<event>→ <state-B>
              ─<event>→ <state-C>
              ─<event>→ <state-D>
  ─<event>→ <state-E>
```

What the user should see in each state:

| State       | User-visible feedback |
| ----------- | --------------------- |
| `<state-A>` | <one line>            |
| `<state-B>` | <one line>            |

---

## 4. Contract

For each component participating in this flow, what it renders / produces / writes — and what it does NOT.

### 4a. <Sub-rule, e.g. "Per-step blocks">

Numbered rules. Order matters where applicable.

1. <rule>
2. <rule>

### 4b. <Sub-rule, e.g. "Turn footer">

<rules>

### 4c. Hard invariants

Non-negotiable rules. Any commit violating one is wrong.

- **I1**: <invariant>
- **I2**: <invariant>
- **I3**: <invariant>

### 4d. What each component renders

| Component     | Renders | Does NOT render |
| ------------- | ------- | --------------- |
| `<Component>` | <what>  | <what not>      |
| `<Component>` | <what>  | <what not>      |

---

## 5. Layer ownership (single-writer rule)

For each mutable field, the **single** code path allowed to write it. Reading is unrestricted.

| Field     | Single writer        |
| --------- | -------------------- |
| `<field>` | `<function or path>` |
| `<field>` | `<function or path>` |

Recent bugs / past pain related to multi-writer races: <one-line history>.

**Deferred cleanups** (to do during refactor, not now): <numbered list of cleanups noted but explicitly out of current scope>

---

## 6. Canonical scenarios

Concrete shapes the design must produce. Each scenario is manually testable and corresponds to a test that should exist.

### A. <Scenario name>

```
<input or initial state>
─────────────────────────────────────────
<rendered or observable output>
```

### B. <Scenario name>

...

---

## 7. State signals (if applicable)

Who sets each signal, who reads, when it's true. Keep this table small — overlap between signals is a smell.

| Signal     | Set by   | Read by   | True when   |
| ---------- | -------- | --------- | ----------- |
| `<signal>` | <writer> | <readers> | <predicate> |

---

## 8. Decisions

Resolved trade-offs. Each gets a (D) marker so a future reader knows the question was deliberately settled.

- **D1**: <decision>. <one-line rationale>.
- **D2**: <decision>. <one-line rationale>.

---

## 9. Edge cases

Behaviours implied by the decisions but not shown in the canonical scenarios.

### 9a. <Edge case>

<short description, what happens, which decisions / invariants apply>

### 9b. <Edge case>

...

---

## 10. What this doc is NOT

- not a TODO list
- not an implementation plan (those live in `how.md`)
- not a record of recent fixes (those live in commits)

When this doc and a commit disagree, the commit wins — but the same PR must update this doc. Drift is the failure mode that brings back the ping-pong.

**Cleanup reminders**: <any temporary diagnostic code that must be removed once the refactor lands; e.g. debug overlays, instrumentation, feature flags>.
