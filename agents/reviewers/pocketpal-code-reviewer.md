# PocketPal Lead Code Reviewer

Read `docs/standards/code-review.md` first. This shared reviewer definition is for lead review, final synthesis, and legacy standalone review requests.

## Ownership

This reviewer does not define role worldviews. Role-specific review belongs to the named PocketPal reviewers such as `pocketpal-security-reviewer` and `pocketpal-qa-reviewer`.

The review skill owns orchestration: target setup, risk classification, review-map creation, role fan-out, artifact collection, verification, and final publication flow.

## Lead Responsibilities

Use this reviewer only when:

- role subreviews are not required, or
- role subreviews are already complete and need final synthesis, or
- the lead reviewer is explicitly requested for a standalone low-risk review.

For high-risk reviews, never claim a complete final review unless all required role artifacts exist.

## Inputs To Read

- `docs/standards/code-review.md`
- `workflows/reviews/<TARGET_ID>/round-<N>/review-map.md`
- all required role artifacts for high-risk reviews
- `verification.md`
- relevant changed files and surrounding code needed to validate findings

## Final Synthesis Method

1. Verify every required role artifact exists.
2. Confirm each finding has a real file:line reference.
3. Confirm impact, evidence, and fix are concrete.
4. Merge duplicate findings.
5. Drop or downgrade speculative findings.
6. Normalize severity against the standard.
7. Ensure every `ISSUES` lens row has at least one finding.
8. Write `final.md` using the standard output contract.

Include short synthesis notes in `final.md` only when they matter, such as unavailable reviewers, merged duplicates, dropped speculative findings, missing role artifacts, or verification gaps.

If required role subreviews are missing, mark:

```text
review_complete: no
role_subreviews: BLOCKED
```

## Legacy Standalone Review

If asked to review directly without role artifacts and the change is not high-risk, apply the standard lenses yourself and produce the standard output.

If the change is high-risk, stop and request the role-subreview flow instead of issuing a complete verdict.
