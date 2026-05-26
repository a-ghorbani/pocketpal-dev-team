# Intent: Thinking toggle locked by active pal's saved setting in no-session chat path

## Metadata

- **Task ID**: TASK-20260525-1739
- **Source**: GitHub issue #744 (https://github.com/a-ghorbani/pocketpal-ai/issues/744)
- **Worktree**: `./worktrees/TASK-20260525-1739`
- **Branch**: `feature/TASK-20260525-1739`
- **Complexity**: standard
- **Native Changes**: NO
- **Visual Confirmation**: NO
- **Created**: 2026-05-25
- **Status**: approved

---

## Request

### [Bug]: Thinking toggle in chat is locked by the active pal's saved setting; user can't override

## Summary

When a pal is active in chat, the thinking toggle visible in the chat input is effectively read-only — taps don't stick. The toggle reflects the pal's stored `enable_thinking` value (which every pal carries), and the user's manual flip gets immediately overwritten on the next render. The bug is most visible on a fresh chat (no first message sent yet).

## Repro

1. Pick any model (the bug is independent of whether the model supports thinking; tried with Mistral-3-3B, but reproduces with thinking-capable models too).
2. Activate any pal — either one whose `enable_thinking` you've turned off in the pal editor, or any default pal.
3. Open a new chat with the pal selected, *before sending the first message*.
4. Tap the thinking toggle in the chat input.

**Expected**: toggle flips and stays flipped, just like with no pal active.

**Actual**:
- If the pal has `enable_thinking: false` saved → toggle is stuck OFF; tapping it on snaps back to OFF.
- If the pal has `enable_thinking: true` saved (the default for every pal) → toggle is stuck ON; tapping it off snaps back to ON.

If you send a first message first, then tap, the toggle does take effect (the handler takes a different branch). The bug is the no-active-session path.

## Root cause (preliminary — verify independently)

Three pieces interact:

1. **Every pal stores `enable_thinking`**, whether the user authored it or not. `defaultCompletionParams.enable_thinking = true` in `src/utils/completionSettingsVersions.ts`, the version-3 migration backfills it onto every pre-existing pal, and new pals inherit a full snapshot from `defaultModel.completionSettings` (`src/store/PalStore.ts`).
2. **The resolver applies pal *after* global**: `resolveCompletionSettings` in `src/store/ChatSessionStore.ts` runs `defaults → global → pal → (session only if settingsSource === 'custom')`. Pal wins over global for any key pal has set.
3. **The chat-screen toggle handler writes to global when there's no active session**: in `src/screens/ChatScreen/ChatScreen.tsx` `handleThinkingToggle`, the `else` branch writes to `chatSessionStore.newChatCompletionSettings`. The handler's `if (currentSession)` branch correctly writes to `session.completionSettings` and flips `settingsSource` to `'custom'` — which works. The `else` branch (taken before the first message in a new chat) writes to global, and the pal's `enable_thinking` value re-overlays it on the next resolve.

Net: in the no-session path, pal preference deterministically beats user input every render cycle.

## When this regressed

The async re-resolution that re-applies pal overrides on every render was introduced when the toggle composition moved from a synchronous selector (read session-or-global directly) to a `useEffect` that calls `getCurrentCompletionSettings()` and refires whenever `activePalId` changes. Before that change, the toggle was a function of stored session/global settings only, so pal preference didn't re-overlay on every render. The async path is the right call for honoring pal settings on session start; the bug is just that there's no escape hatch for the user.

## Fix shape (options listed in the issue — pick after investigation)

These trade off scope vs. cleanliness:

1. **Don't store `enable_thinking` in pal `completionSettings` by default** — treat it as a global/session setting only; pals can opt in by setting it explicitly. Needs a migration to strip the backfilled `true` from every pal.
2. **Add a per-chat user-override layer** that's applied last regardless of `settingsSource`. Cleaner long-term but bigger.
3. **In the no-session toggle path, force-flip `settingsSource` to `'custom'` on the next session creation** so the user's preference carries. Most surgical.
4. **Make the resolver apply user-explicit toggles after pal** (e.g. detect that the user changed thinking specifically, and treat that single key as user-owned). Most invasive at the merge boundary.

## Acceptance criteria

- In a fresh chat (no first message sent) with any pal active, tapping the thinking toggle persists and is reflected in the next inference (whichever path the runtime takes).
- Pal's authored `enable_thinking` still applies as the *initial* state when the user enters a new chat with that pal.
- Pal-specific completion settings other than `enable_thinking` (temperature, top_p, etc.) are not lost as a side effect of the user toggling thinking.
- The active-session toggle path (current `if (currentSession)` branch) continues to work as it does today.
- Toggle UI reflects the user's choice immediately after the tap (no snap-back on the next render).

## Native impact

None expected — TS/JS only.

## Investigator notes (verified by caller before delegating)

- Confirmed `src/screens/ChatScreen/ChatScreen.tsx:178-200` `handleThinkingToggle` matches the issue (else-branch writes to `newChatCompletionSettings` only, doesn't flip source).
- Confirmed `src/screens/ChatScreen/ChatScreen.tsx:114-131` useEffect re-runs `getCurrentCompletionSettings()` whenever `newChatCompletionSettings`/`activePalId` change.
- Confirmed `src/store/ChatSessionStore.ts:1346-1403` `resolveCompletionSettings` overlays pal on top of global for any palId passed.
- Noticed asymmetry: `src/store/ChatSessionStore.ts:1408-1417` `getCurrentCompletionSettings` passes `this.newChatPalId` unconditionally for the no-session path, while session-creation in `src/store/ChatSessionStore.ts:427-432` respects `newChatSettingsSource` (palId is undefined when source is `'custom'`). This asymmetry is part of the bug — even if option 3's fix flips source on toggle, the read path also needs to honor that.
- Option 3 needs care: simply flipping `newChatSettingsSource = 'custom'` makes the resolver skip the pal layer entirely, dropping pal's other completion settings. A clean implementation needs to either (a) bake the pal-resolved snapshot into the session at create time (snapshot already includes pal overrides + user's thinking choice), and store source='custom'; or (b) add a thin per-chat override layer applied last in the resolver.

Metadata:
- GitHub issue: #744
- Labels: bug

---

## Clarifications

none — request is detailed, repro is unambiguous, acceptance criteria are explicit, and the requester deliberately leaves fix-shape selection to the architect/planner.
