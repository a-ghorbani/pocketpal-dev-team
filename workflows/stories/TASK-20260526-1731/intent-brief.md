# Intent: FOU-116 [Redesign] Phase 3a — Onboarding flow

## Metadata

- **Task ID**: TASK-20260526-1731
- **Source**: https://linear.app/pocketpal/issue/FOU-116
- **Worktree**: `./worktrees/TASK-20260526-1731`
- **Branch**: `feature/TASK-20260526-1731`
- **Complexity**: complex
- **Native Changes**: NO (expected — no new native modules; Phase 1/FOU-114 already wired fonts and Phase 2/FOU-115 the DS layer; flag if a new native asset/module appears during WHAT)
- **Visual Confirmation**: YES
- **Created**: 2026-05-26
- **Status**: approved

---

## Request

FOU-116 [Redesign] Phase 3a — Onboarding flow

Linear: https://linear.app/pocketpal/issue/FOU-116

Parent: FOU-112 (redesign rollout). BlockedBy FOU-115 (merged 2026-05-24 via PR #742). Blocks FOU-117, FOU-123. RelatedTo FOU-98 (7-screen pal-first flow brief).

Description (verbatim from Linear):

First flow slice (FOU-112 prioritizes onboarding). Greenfield — the app has no onboarding today, so no migration risk. Implement → review → usability pass. Full plan: `context/redesign/FOU-112-rollout.md`.

Scope: Onboarding screens 1–6 (`884:28223`) + Splash + first-time Homepage from canonical file `RZxDJea4t6jnBZrV4YBacF`. The dark render of the same screens lives at `3011:25220` — not a separate flow; dark derives from tokens. Align with FOU-98 (7-screen pal-first flow).

Wire to the Phase 2 component library + Phase 1 tokens. Includes the UX/behavior of a pal-first first-session flow (greenfield, not a reskin). RTL (`he`, `fa`) + non-Latin handled per the locked requirement. Freeze testIDs for E2E.

Done when: onboarding matches screens 1–6 in light + dark; behavior implemented; E2E onboarding path passes; usability pass complete; iOS + Android builds green.

Metadata:
- Linear issue: FOU-116
- Parent: FOU-112
- BlockedBy: FOU-115 (merged via PR #742)
- Blocks: FOU-117, FOU-123
- RelatedTo: FOU-98
- Canonical Figma file: RZxDJea4t6jnBZrV4YBacF
- Canonical onboarding frames (light): 884:28223 (screens 1–6)
- Dark render: 3011:25220
- In-repo tracking doc: context/redesign/FOU-112-rollout.md

Run the full pipeline autonomously per AGENTS.md (Intent → WHAT → HOW → Implementation → Test → Pipeline Review). Stop only on NEEDS_INPUT or HAS_BLOCKERS after round 2.

Repository: ./repos/pocketpal-ai

---

## Clarifications

none — the request is self-contained for a Phase 3a slice: canonical Figma frames (light + dark) are named, the rollout doc (`context/redesign/FOU-112-rollout.md` §4 / §5) sets the cross-cutting contract (token + DS layer wiring, RTL + non-Latin rule, testID freeze, light + dark parity per slice, architecture-doc updates in the same PR), and the boundary with FOU-117 is set by the rollout doc (FOU-117 owns Homepage + Chat proper; what FOU-116 calls "first-time Homepage" is the destination state visible at the end of onboarding). Behavior of the pal-first first-session flow is to be defined by the architect against the canonical frames + FOU-98 brief during WHAT — that is design work, not a missing clarification.
