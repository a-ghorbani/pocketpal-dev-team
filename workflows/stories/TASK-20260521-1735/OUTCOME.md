# Outcome

**Status:** shipped
**PR:** [pocketpal-ai#733 — \[Feat\]: non-touch autostart deep link for bench E2E matrix](https://github.com/a-ghorbani/pocketpal-ai/pull/733)
**Merge commit:** `084e6c0` (merged 2026-05-24)
**Branch:** `feature/TASK-20260521-1735` (9 commits)

## What landed

Bench E2E matrix can now be started without a touch by passing `?autostart=1` on the deep link (`pocketpal://e2e/benchmark?autostart=1`). The screen reads `route.params.autostart` and invokes the existing `onRun` once per mount — same start path, same single-flight gate, same `bench-config.json`, no change to what is measured.

## Pipeline stages

| Stage | Result |
| --- | --- |
| Orchestrator | classified **standard**, worktree created |
| Architect → critic | LGTM (deep-link autostart; `NATIVE_CHANGES=NO`) |
| Planner → critic | LGTM (5 steps + arch-doc fold) |
| Implementer | 6 atomic commits, lint + typecheck clean |
| Tester | full suite 2268 passed, coverage gate PASS, §6 A–E covered |
| Pipeline-reviewer | APPROVE (PR creation held until on-device validation) |
| Round-1 external review | 3 CONCERNs → all addressed in 3 follow-up commits |

## Round-1 follow-ups

- `6b4d567` — moved deep-link protocol (`BENCHMARK_RUNNER_URL_PREFIX`, `isBenchmarkRunnerUrl`, `parseBenchmarkAutostart`) from `src/utils/navigationConstants.ts` to `src/__automation__/benchmarkRoute.ts`.
- `36c058a` — dropped the `useRoute` try/catch and `__autostart` test seam; `useRoute` is now called unconditionally; tests use the codebase's per-file `jest.mock('@react-navigation/native')` pattern.
- `b76a1d0` — WDIO spec fails fast (30 s) when autostart never leaves `idle`; both timeout messages now interpolate the last observed status.

Round-1 review artifacts: [`workflows/reviews/PR-733/round-1/`](../../reviews/PR-733/round-1/).

## On-device validation

E2E APK built locally and exercised on the two devices that motivated the feature (the ones whose synthetic taps the OS was dropping). Cold-launch with `?autostart=1` and **zero taps**:

| Device | Bare URL (regression guard) | `?autostart=1` (no tap) |
| --- | --- | --- |
| POCO F7 Ultra (klee, HyperOS) | `idle` ✓ | `running → complete` ✓ |
| POCO X7 Pro (myron, MediaTek) | `idle` ✓ | `running → complete` ✓ |

Run on the final round-1 head (`b76a1d0`) before merge.

## Architecture

Flow doc folded into [`context/architecture/benchmark-matrix.md`](../../../context/architecture/benchmark-matrix.md) §0 (Trigger & routing). I-AS5 records the boundary: the protocol surface lives in `src/__automation__/benchmarkRoute.ts`; the two prod-reachable mount points (`App.tsx`, `src/hooks/useDeepLinking.ts`) are allow-listed by the `no-restricted-imports` rule.
