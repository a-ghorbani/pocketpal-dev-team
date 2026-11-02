# Evidence plan: <one-line summary>

What must be shown for this change to count as done (`docs/workflows/pipeline.md`, Evidence plan).

## Claim

- **Bug**: repro steps on `main` → observed result (red); the same steps on the branch → expected result (green).
- **Feature**: the done check(s), each able to pass or fail.
- **Repro on `main`** (bugs; tester, repro mode): <receipt>
- **Cause** (bugs): <mechanism, file:line>; regression: introduced by #<PR> (<what it intended>)

## Where

- **Platforms**: iOS | Android | both, and why.
- **Real vs fake**: the real systems the claim depends on (store, server, model backend, device hardware).
- **Risk rows**: <matching rows from the pipeline's table, or "none">.

## Items

| ID | Proves | Source | How | Platform | When | Status | Receipt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | <the claim, or one consequence of it> | claim / risk: <row> / WHAT §6x / fix R<n> | <command, spec, or device run> | iOS / Android / both / n/a | pre-PR / CI APK | planned / PASS / FAIL / BLOCKED: <why> / dropped: <reason> | <path, PR comment link, or output excerpt> |
