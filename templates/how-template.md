# Sequencing plan: <one-line summary>

`PLAN=YES` only. Reference WHAT by section; don't re-derive design.

---

## Metadata

- **Task ID**: TASK-YYYYMMDD-HHMM
- **WHAT**: `./workflows/stories/<TASK-ID>/what.md`
- **Evidence**: `./workflows/stories/<TASK-ID>/evidence.md`
- **Why sequencing is a risk**: <one line>

---

## Units

### U1: <one-line>

- **Implements**: WHAT §<N>
- **Lands as**: PR / stacked commit
- **Leaves the app in**: <the shippable state after this unit>
- **Must not break**: <what an existing install or a half-migrated state still needs>
- **Evidence**: E<ids> from `evidence.md`
- **Native verification**: yes / no

---

## Rollback

<What reverting each unit leaves behind, and which later units depend on it.>

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | <one-line> | BLOCKER / CONCERN / SUGGESTION | FIXED <ref> / REJECTED <evidence file:line> / DEFERRED <ref> |
