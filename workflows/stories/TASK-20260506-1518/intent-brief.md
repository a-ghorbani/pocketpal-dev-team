# Intent: Settings toggle to enable/disable TTS, defaulting based on device memory

## Metadata

- **Task ID**: TASK-20260506-1518
- **Source**: prompt
- **Worktree**: `./worktrees/TASK-20260506-1518`
- **Branch**: `feature/TASK-20260506-1518`
- **Complexity**: standard
- **Native Changes**: NO
- **Visual Confirmation**: YES
- **Created**: 2026-05-06
- **Status**: approved

---

## Request

Add a Settings toggle to enable/disable TTS, defaulting based on device memory.

Currently TTS is hard-gated by a memory requirement; users on devices below the threshold cannot try it at all. The user has received good feedback on TTS and wants to let curious users on lower-memory devices opt in, while keeping the safe default behaviour for everyone else.

Requirements:

- Single on/off toggle in the Settings screen, placed wherever it looks natural — no new section, not promoted, not hidden.
- Default state: ON if device meets the current TTS memory requirement, OFF if it doesn't.
- When the device is below the memory threshold, show a small helper line under the toggle: something like "Your device's memory is low — this may not work reliably." (exact copy is for the planner/implementer to finalise.)
- Final TTS availability gate becomes: `deviceMeetsMemory || userOverride`.
- No crash-recovery or auto-revert logic. If it fails on a low-memory device, it fails — the user opted in knowingly. (Reasoning: if it crashes, it's hard to attribute between TTS and a competing loaded LLM model; not worth complicating UX.)
- Persisted setting (survives app restart).

---

## Clarifications

none — request was clear and self-contained.
