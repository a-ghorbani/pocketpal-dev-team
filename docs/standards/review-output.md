# Review Output Shapes

Output contract for `docs/standards/code-review.md` (Output). Load when writing `final.md` or a headless result.

## Human-Facing Output

Open with review metadata:

```markdown
verdict: APPROVE | REQUEST_CHANGES | ESCALATE
risk_level: low | medium | high
review_complete: yes | no
role_subreviews: COMPLETED | BLOCKED | NOT_REQUIRED
```

Then a per-lens summary table:

```markdown
| Lens                  | Status              | Issues |
| --------------------- | ------------------- | ------ |
| Correctness           | PASS / ISSUES       | n      |
| Architecture          | PASS / ISSUES       | n      |
| Maintainability       | PASS / ISSUES       | n      |
| Tests                 | PASS / ISSUES       | n      |
| Security              | PASS / ISSUES / N/A | n      |
| Data / Migration      | PASS / ISSUES / N/A | n      |
| Performance/Resources | PASS / ISSUES / N/A | n      |
| UX / Accessibility    | PASS / ISSUES / N/A | n      |
| Platform / Native     | PASS / ISSUES / N/A | n      |
```

Then: findings ordered by severity (each with its `confidence` and `refutation` outcome), open questions, verification status, residual risks, decision summary.

If nothing was found, say so and name the remaining verification gaps.

The review is team-shareable: deduplicate role findings, normalize severity, and give each finding enough detail to fix without asking "where?". Every `ISSUES` lens row has at least one matching finding.

## Headless Output

Deterministic, compact, no prose:

```markdown
verdict: APPROVE | REQUEST_CHANGES | ESCALATE
risk_level: low | medium | high
review_complete: yes | no
role_subreviews: COMPLETED|BLOCKED|NOT_REQUIRED

missing_context: [item, ...] # or []

verification:

- { name: lint, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: typecheck, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: tests, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }
- { name: native, status: PASS|FAIL|NOT_RUN|N/A, notes: ... }

lens_summary:
  correctness: PASS|ISSUES
  architecture: PASS|ISSUES
  maintainability: PASS|ISSUES
  tests: PASS|ISSUES
  security: PASS|ISSUES|N/A
  data_migration: PASS|ISSUES|N/A
  performance: PASS|ISSUES|N/A
  ux_accessibility: PASS|ISSUES|N/A
  platform_native: PASS|ISSUES|N/A

counts: { blocker: 0, concern: 0, suggestion: 0 }

findings:

- id: R1
  severity: BLOCKER|CONCERN|SUGGESTION
  lens: correctness|architecture|...|platform_native
  confidence: high|med|low
  refutation: stands|withdrawn
  title: short title
  path: relative/path.ts
  line: 123
  impact: one sentence
  evidence: short quoted code
  fix: one sentence

manual_checks: [step, ...]   # or []
residual_risks: [item, ...]  # or []
```

`risk_level: high` when native, persistence, security, or multi-surface changes ship with incomplete verification.
