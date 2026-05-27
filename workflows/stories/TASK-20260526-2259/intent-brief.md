# Intent: Context-full warning UX in chat

**Purpose**: confirm **what** the requester wants built, before any design or implementation begins.

---

## Metadata

- **Task ID**: TASK-20260526-2259
- **Source**: prompt (3-round deliberation distilled by the user)
- **Worktree**: `./worktrees/TASK-20260526-2259`
- **Branch**: `feature/TASK-20260526-2259`
- **Complexity**: standard
- **Native Changes**: NO
- **Visual Confirmation**: YES
- **Created**: 2026-05-26
- **Status**: approved

---

## Request

Context-full warning UX in chat. The story is intentionally small in code surface but UX-heavy — the planner must spend most of the budget on UX analysis (copy, l10n, dismiss/recovery semantics, reload feedback, remote variant), not on plumbing.

### Problem

PocketPal's default model context is 2048 tokens (`src/utils/contextInitParamsVersions.ts:43`). Long conversations and tool-heavy talents (especially `render_html`, which generates 1000–3000 token HTML payloads that re-enter context) overflow the budget with no user-visible warning today. Users see truncated replies or "Tool call cut off" errors (`src/locales/en.json:1085`, handler at `src/hooks/useChatSession.ts:637-643`) and don't understand why.

### Chosen design (simplified after a 3-round deliberation)

We deliberately rejected a talent-aware predictive system (too many wrong heuristics, false positives on fresh chats with capable pals). The shipped design is ratio-based and talent-agnostic:

**Two states, one rule:**

```
used = lastTokensEvaluated + lastTokensPredicted   // from CompletionResult per turn
ratio = used / n_ctx

WARNING_THRESHOLD = 0.80   // default; tunable

warning state:  ratio >= 0.80 && !lastContextFull
full state:     lastContextFull === true            // set on context_full or truncated
```

**Signals (greenfield wiring — fields exist on `CompletionResult` at `src/utils/completionTypes.ts:93-99` but are not yet stored):**
- `lastTokensEvaluated`, `lastTokensPredicted`, `lastContextFull` added to `ChatSessionStore` per session.
- For remote models: `finish_reason === 'length'` or `truncated === true` → "full" state. Weak signal (no `finish_reason`, length > 500, no terminal punctuation) → hedged variant only. No pre-emptive remote warning since we don't own remote n_ctx.

**Banner surface:**
- Reuse the existing soft-cap banner shell at `ChatView.tsx:1073-1079` + style at `styles.ts:85-97`. One computed `bannerVariant`. Context warning wins precedence over the existing `htmlPreviewCount >= 4` soft-cap.
- Three copy variants: `warning` / `full` / `remote-full-hedged`.
- Per-draft dismiss; reappears next turn if still triggered. "Full" variant is sticky with dismiss hidden; auto-clears on the next successful completion that uses `< n_ctx − 32` tokens. Escalates copy after 2 consecutive failures.

**"Increase context" CTA:**
- Session-only override on the active `LlamaContext`. No `contextSizeOverride` field on the Pal record (deliberately deferred).
- Tier table `[2048, 4096, 8192, 16384, 32768]`; next tier gated on `useMemoryCheck.ts` + `memoryEstimator.ts`. Hidden if no tier fits.
- Confirm sheet: friendly tokens-primary copy with time as parenthetical hedge. Advanced disclosure shows raw tokens.
- Reload uses existing `releaseContext → initContext` (preserves chat history — messages live in `chatSessionStore`).
- Snackbar on success; revert + error snackbar on failure (existing pattern).

### What the planner MUST give real UX attention to (this is the bulk of the work)

1. **Copy register and l10n.** 8 integrated languages (en/he/id/ja/ko/ms/ru/zh) including RTL (he, fa). Banner + up to 2 action buttons on iPhone SE width. Never use "n_ctx", "tokens" in primary copy where avoidable. Decide: tokens-primary with time-hedge, OR friendly-only? My deliberation pick was tokens-primary, but the planner should pressure-test on actual translated string lengths.
2. **Dismiss / recovery semantics.** Per-draft dismiss vs session-sticky. Coexistence with the existing `htmlPreviewCount` soft-cap banner (precedence rule + visual). Auto-clear conditions for "full" state. Escalation after 2 failures.
3. **Reload UX feedback.** What the user sees during the 10–30s `releaseContext → initContext` cycle. Reuse existing `loadingModel` state with a subcopy. Confirmation moment after reload completes (snackbar copy).
4. **Hedged remote variant copy.** Must say *"you may be near the model's context limit"* — NOT *"this can happen near the model's context limit"* (the second presupposes causation we don't have on a weak signal).
5. **Three decisions to pin with reasoning:**
   - **Threshold:** 0.80 default? 0.75? 0.85? Pick a number and defend it for both n_ctx=2048 (~1638 used = 410 tokens runway) and n_ctx=8192 (~6553 used = 1600 tokens runway).
   - **Snapshot vs live:** compute "used" only at turn boundaries from `CompletionResult` (cheap, simple), or hook into streaming `tokens_predicted` during generation (richer, more invasive)? Recommendation: snapshot for v1, but planner should verify the streaming path's complexity before committing.
   - **First-time render_html on fresh chat:** explicitly acknowledge this case warns *reactively* (after the model actually fires the tool and ratio crosses 0.80), not pre-emptively. Document this as an accepted trade-off vs. the rejected talent-aware design.

### Caveats the implementer must carry forward

These came out of the deliberation and survive the simplification:

1. **Session override survival across `LlamaContext` destruction.** App background → OS evicts model → foreground → reload silently reverts override. Pick one: (a) persist override in a session-keyed in-memory map that outlives `LlamaContext` within session, OR (b) surface a one-time toast on silent reload-to-default. Do not leave implicit.
2. **No per-pal `contextSizeOverride` field.** The brief constraint stands — talents declare needs, n_ctx resolves at model-load time. Per-pal persistence is a separate follow-up story once telemetry shows repeat-override patterns.
3. **Hedged remote copy presupposition.** See point 4 above.

### Scope boundaries

**In scope:**
- New state fields on `ChatSessionStore` (3 numbers + 1 boolean).
- Wiring `tokens_evaluated` / `tokens_predicted` / `context_full` from `CompletionResult` into the store (currently unread).
- Banner variant resolver (replace the existing single `htmlPreviewCount` conditional in `ChatView.tsx:1073` with a computed variant).
- New l10n keys under `chat.contextWarning.*` (extend `src/locales/en.json` around line 1080).
- "Increase context" confirm sheet + reload flow.
- Remote `finish_reason` / `truncated` detection and hedged-weak-signal path.

**Out of scope (defer to follow-up stories):**
- Per-pal `contextSizeOverride` field on Pal record.
- Known-provider context window registry (OpenAI/Anthropic/Groq/Mistral) for pre-emptive remote warnings.
- Live during-stream tracking (snapshot-at-turn-boundary v1).
- Heads-up vs critical two-tier banner variants (rely on persistence-as-state for "critical").
- Talent-aware predictive thresholds (explicitly rejected after deliberation).
- Pal-edit chip or other discoverability surfaces outside the banner itself.

### Verification expectations

- Targeted Jest for the new `ChatSessionStore` state transitions and the banner variant resolver.
- l10n string lengths verified for he/ja/ko/ru/zh on iPhone SE width and Android narrow phones.
- No native changes expected (`NATIVE_CHANGES=NO`).
- Manual verification on a real device: trigger warning by sending a long pasted prompt, trigger "full" by sending a `render_html`-using request on default n_ctx=2048, verify "Increase context" reload preserves chat history and recovers state.

---

## Clarifications

none — request resulted from a 3-round deliberation that explicitly resolved the open questions (rejected talent-aware design, pinned ratio-based two-state model, defined three remaining decisions for the planner to pin with reasoning rather than re-litigate). The brief is the verbatim handoff; design questions inside it are addressed to the planner, not the orchestrator.

---

## Note on the planner's bulk of work

Per the requester's explicit emphasis ("the story is small, but we need a good ux analysis. so the planner should pay attention on it."), the planner's primary deliverable is the UX analysis described in "What the planner MUST give real UX attention to" above. Plumbing (3 numbers + 1 boolean on `ChatSessionStore`, banner variant resolver, l10n key additions, confirm sheet wiring) is small. Copy register, dismiss/recovery semantics, reload feedback, hedged remote variant, and the three pinned decisions (threshold, snapshot-vs-live, reactive-first-tool acknowledgement) are where the planning budget belongs.
