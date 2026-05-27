# Deliberation log — TASK-20260526-2259

Audit trail for WHAT review rounds + post-LGTM amendments.
Contract content lives in `./what.md`. This file is history only.

---

## Round 1 — architect-critic — HAS_BLOCKERS

### BLOCKER 1 — Session override has no real seam in `ModelStore.initContext` — FIXED

- Verified: `ModelStore.initContext(model, mmProjPath?)` at `src/store/ModelStore.ts:1492` takes NO context-params argument. Effective n_ctx is read inside `getEffectiveContextInitParams` (`ModelStore.ts:419-478`), line 423: `const effectiveContext = this.contextInitParams.n_ctx`. D10 forbids mutating `modelStore.contextInitParams`. The seam did not exist; round 1 described it as if it did.
- Resolution: picked option (a). `getEffectiveContextInitParams` extended with one cross-store read of `chatSessionStore.sessionContextOverrides.get(activeSessionId)`; prefers it over `this.contextInitParams.n_ctx` when present. Documented in §5 as the only `ModelStore → ChatSessionStore` read direction; codified as I5 in §4f. `initContext` signature unchanged — override flows through silently at init time. D2 updated in §8 to name the seam explicitly. §4h step 3 no longer says "with the override applied" — just calls `initContext(model)`; override honoured silently. Auto-load after eviction (§7c) gets the same silent honouring through the same read site. One seam, two callers.
- Option (b) (explicit `nCtxOverride?` argument threaded through `initContext` and auto-load) rejected — requires two callers to remember the override; option (a) puts the read in one co-located helper.

### BLOCKER 2 — Disk-reload recovery doesn't work as described — FIXED

- Verified: grep for `completionResult` in `useChatSession.ts`, `ChatSessionStore.ts`, `ChatSessionRepository.ts` returns ZERO production writers. Field is only read as a sentinel by `PlayButton.tsx:56` (presence-check for "streaming finished") and in tests. The round-1 draft assumed a writer that doesn't exist.
- Resolution: picked option (b) AND folded SUGGESTION 1 — the four scalars collapse into one `lastCompletionResult: CompletionResultSnapshot | null` (§1a). The `run_finished` / abort-catch writer writes BOTH the snapshot into `ChatSessionStore.lastCompletionResult` AND the same snapshot fields onto `message.metadata.completionResult` (existing field gets tightened shape; existing `content` / `reasoning_content` readers like `PlayButton.tsx:56` keep working — new fields are additive on the same key).
- `setActiveSession` rehydrates `lastCompletionResult` from the most recent assistant message's `metadata.completionResult` (I7). `resetActiveSession` clears it to `null`. Scenario L rewritten to describe recovery; Scenario M added for cold-launch. Legacy sessions without `metadata.completionResult` start at `null` and rebuild on next turn (D12, §7i).

### CONCERN 1 — chat-flow.md drift on `metadata.completionResult` — FIXED

- Same fix as BLOCKER 2 option (b). chat-flow.md §5 line 415 currently says `metadata.completionResult` is written at `run_finished`, but no production writer exists. After this story lands, that line becomes TRUE — implementer's chat-flow.md absorption step replaces "raw final result" with a reference to the tightened `CompletionResultSnapshot` shape from §1b. Repair part of this delta, not a separate reconciliation PR.

### CONCERN 2 — `lastFinishReason` in §5 but not §1a/§2 — FIXED

- Resolved by collapsing four scalars into one snapshot (BLOCKER 2 + SUGGESTION 1). `finishReason` is now a field of `CompletionResultSnapshot` (§1a) with explicit derivation table. No separate `lastFinishReason` observable; no fourth single-writer row.

### CONCERN 3 — D2 silent-survival downstream of BLOCKER 1 — FIXED

- D2 updated in §8 to name the seam explicitly: `getEffectiveContextInitParams` reading `sessionContextOverrides.get(activeSessionId)` (the I5 seam). §7c also updated to name the seam.

### CONCERN 4 — "Sticky" wording for `context-remote-hedged` — FIXED

- §4d rewritten: `context-full` is sticky via `snap.contextFull` + auto-clear (I3). `context-remote-hedged` is non-dismissible but reactively cleared — when the next remote turn lands without all four §4e conditions, the variant drops naturally (no store-side state survives beyond what `lastCompletionResult` already carries). (This posture is later revised in Round 2.)

### SUGGESTION 1 — Fold four scalars into one snapshot — FIXED

- Adopted. Drove resolution of BLOCKER 2 and CONCERN 2. Net effect: §1a goes from 3 scalars + a fourth implicit `lastFinishReason` to ONE snapshot observable. §5 single-writer table goes from 5 added rows to 4. `metadata.completionResult` is a tightening of an EXISTING row, not a new one.

### SUGGESTION 2 — Pin WARNING_THRESHOLD and AUTOCLEAR_RUNWAY location — FIXED

- §4b pins both as named exports from the resolver module (one file). New D11 in §8 records location and rationale (no runtime tunable; no settings UI; tuning is a single-line PR).

---

## Round 2 — plan-critic — ARCHITECTURE_DRIFT

### ARCHITECTURE_DRIFT 1 — HOW §A.4 made `context-remote-hedged` per-draft dismissible, contradicting WHAT §4d and §6 Scenario G — FIXED (architect amendment)

- Plan-critic flagged HOW §A.4 amended the dismiss posture for `context-remote-hedged` to per-draft dismissible, contradicting WHAT §4d ("non-dismissible but reactively cleared") and §6 Scenario G ("dismiss: NOT rendered"). Drift route went back to architect (a bug in WHAT is fixed in WHAT, per AGENTS.md critic-loop rule).
- Resolution: amended WHAT §4d and §6 Scenario G to allow per-draft dismiss on `context-remote-hedged`. D6 in §8 updated to reflect the asymmetry between `context-full` (non-dismissible, authoritative signal) and `context-remote-hedged` (per-draft dismissible, weak signal).
- Rationale (planner's argument, accepted):
  - §4e heuristic is intentionally conservative (all four conditions must hold), but it is still a weak signal: cannot prove the truncation IS a context issue, only that it looks like one. Forcing non-dismissibility on uncertain signals is the wrong posture.
  - A per-draft dismiss costs nothing: the variant re-derives on the next remote turn anyway, so dismiss is just a single-turn hide. Reactive clear path is preserved unchanged.
  - The asymmetry vs `context-full` (which remains non-dismissible) is now load-bearing and documented: strong signal → no dismiss; weak signal → per-draft dismiss.
- Contract additions are minimal:
  - `context-remote-hedged` added to dismiss-set users in §5 (single-writer rule unchanged: same `dismissedBannerVariants` Set, same writer, same clear-on-run_finished cycle).
  - I4 (one banner at a time) unchanged.
  - Reactive clear path (§4e re-derivation every render) unchanged.
- HOW §A.4 no longer needs amendment — it already matches the corrected WHAT. Planner's two remaining HOW-side concerns (CONCERN 1 `lastAssistantText` extraction; CONCERN 2 `effectiveNCtxOf` vs `effectiveNCtx` naming) addressed by planner in a separate small revision; do not affect this delta.

---

## Post-LGTM amendment 1 — `tokens_cached` correction (architect-only, no critic loop)

The plan-critic LGTM'd HOW after WHAT Round 2 corrected the `context-remote-hedged` dismiss posture. After LGTM, a fact-check against llama.rn 0.12.4's `NativeCompletionResult` revealed the `used` formula in §4b (and the §1a snapshot shape) was undercounting KV occupancy.

The error:
- `repos/pocketpal-ai/node_modules/llama.rn/src/types.ts:400-409` exposes three turn-derived token counts on `CompletionResult`:
  - `tokens_cached` — KV-prefix from prior turns that was REUSED (not re-evaluated)
  - `tokens_evaluated` — freshly evaluated prompt tokens this turn
  - `tokens_predicted` — tokens this turn generated
- Total KV occupancy at end of turn = sum of all three. WHAT v2 only summed the last two. On turn 1 (no cache reuse, `tokens_cached == 0`) the formula was right by accident. On turn 2+, prefix caching kicks in and `tokens_cached` can dominate — e.g. on turn 5, actual occupancy might be 1800 cached + 50 fresh + 200 generated = 2050, while the old formula reported 250. Warning threshold (`ratio >= 0.80`) and auto-clear predicate (`used < nCtx − 32`) would both fire LATE on long conversations — exactly the case the banner exists to catch.

Amendment:
1. §1a — added `tokensCached: number` to `CompletionResultSnapshot`. Derivation: `result.tokens_cached ?? 0`. Four scalar fields plus `finishReason`.
2. §1b — added `tokens_cached: number` to persisted `metadata.completionResult` shape so disk-reload recovery (I7, Scenario L, Scenario M) carries the new field.
3. §1d — added `tokens_cached?` to `CompletionResult` recap so readers see the wire-shape origin.
4. §4b — `used = snap.tokensCached + snap.tokensEvaluated + snap.tokensPredicted`. Same `used` used by both warning predicate (`ratio >= WARNING_THRESHOLD`) and auto-clear predicate (`used < nCtx − AUTOCLEAR_RUNWAY`).
5. §4f I2 — extended to cover `tokensCached` alongside the other two.
6. §6 Scenarios B and E — example math updated to show all three summands explicitly (B: `0 + 1500 + 200 = 1700`; E shows three-component breakdown).

Not touched: §5 single-writer table (the `lastCompletionResult` row already covers the whole snapshot; new field rides inside the existing atomic swap), Decisions D1–D14, auto-clear runway value (D4 still 32 absolute tokens), banner variant precedence (§4c), §4e remote heuristic, dismiss/recovery semantics (§4d), scenarios C / D / F / G / H / I / J / K / L / M.

Drift check on architecture library: `context/architecture/chat-flow.md` does NOT reference the `used` formula (formula is brand-new to this story); no drift repair needed there.

Planner follow-up required: HOW Steps 2, 4, and Step 10 test names need a quick read-through to swap `lastTokensEvaluated + lastTokensPredicted` → `lastTokensCached + lastTokensEvaluated + lastTokensPredicted`. Change is mechanical (one new field name threaded through the same three sites that already handle `tokensEvaluated` and `tokensPredicted`).

---

## Post-LGTM amendment 2 — α (pal-load hint) + β (heavy-talent post-fail copy)

Additive contract surface, NOT a re-design. After the `tokens_cached` correction, the user decided two small additive pieces are needed to address on-device economics: token generation is expensive, and the default `n_ctx = 2048` plus a heavy talent like `render_html` deterministically overflows on the first generation. Both additions reuse the existing §4h CTA mechanism — no new tier-pick logic, no new reload flow, no new confirm sheet, no new banner variant.

α — Pal-load hint (snackbar, not banner):
- §1e adds optional `recommendedContextTokens?: number` on `TalentEngine`. `RenderHtmlEngine` declares `4096`; `Datetime` and `Calculate` omit.
- §1f adds `palLoadHintSeen: Set<string>` (key `${palId}:${n_ctx}`) on `ChatSessionStore`. In-memory, session-scoped. One-shot per (palId, n_ctx).
- §4i adds trigger lifecycle: predicate flips false → true at pal load / model load / talent-set change, gate against `palLoadHintSeen`, emit ONE snackbar reusing §4h `IncreaseContextSheet`. No-fit fallback uses the same "Start new chat" path §7j documents.
- §2, §5 grow by one row each for `palLoadHintSeen`. §5 names the talent-registry read direction (no new cross-store concern).
- §7j adds the no-fit edge-case.
- I8 added: snackbar and banner do not occupy the same surface; §4c precedence unchanged.

β — Heavy-talent post-fail sub-copy (NOT a new variant):
- §4a tail amendment: when `context-full` fires AND the just-finished `assistant_turn` invoked a tool whose talent declares `recommendedContextTokens`, the copy key swaps to `chat.contextWarning.fullHeavyTalent`. Variant stays `context-full`. Banner shell, dismissibility (sticky), CTA actions, and I4 (banner-singleton) unchanged.
- β path adds zero per-turn talent inspection beyond the copy-key resolution. No new banner variant. No new CTA.

Decisions added:
- D15 — declarative-only, not predictive. Two pure read sites. No per-turn talent logic on the banner state path.
- D16 — heavy-talent UX is sub-copy of `context-full`, not a new variant. Preserves I4 and keeps the §4c precedence table at five entries.

Hard constraints respected:
- No new banner variant (β is a copy-key swap on `context-full`).
- No new CTA path (α reuses §4h; β reuses §4h).
- No new tier-pick variant (`hasEnoughMemoryWithNCtx` + tier table `[2048, 4096, 8192, 16384, 32768]`).
- No new memory-fallback path (no-fit → "Start new chat" — same as §4h J/K).
- α (snackbar) and §4a–§4h (banner) cannot overlap by construction: α fires before user starts chatting; banner fires on `run_finished`. I8 codifies the layering.

Drift check on architecture library:
- `context/architecture/chat-flow.md`: no drift on the α/β surface itself (the surface is brand-new). The pre-existing `metadata.completionResult` drift repair from this story is unaffected.
- `context/architecture/pals-and-talents.md`: gains ONE line for the new optional `TalentEngine.recommendedContextTokens?: number` field. Implementer's doc-absorption step adds that line in the same PR as the code.

Planner follow-up required (handoff items):
- α: pal-load detector hook (subscribes to active-pal change, `modelStore.context` becomes-available, and `pact.talents` mutations) + snackbar trigger that gates on `palLoadHintSeen` and picks the next-fit tier via `hasEnoughMemoryWithNCtx`. Snackbar UI reuses the existing snackbar shell.
- β: resolver heavy-talent lookup (`messages[0].steps[].tool_calls[].function.name` → `talentRegistry.get(name)?.recommendedContextTokens`) + new l10n key `chat.contextWarning.fullHeavyTalent` (planner pins the exact string and talent-name localization).
- HOW UX section needs α copy decision (snackbar text + action label for "Increase context" / "Start new chat") AND β specific copy (`chat.contextWarning.fullHeavyTalent` value, with `{talentName}` placeholder).
- HOW Step 10 tests: Scenarios N (α fires on default n_ctx + render_html), O (suppressed by `palLoadHintSeen` second time), P (heavy-talent sub-copy on `context-full`). Also the no-fit fallback edge §7j.
- HOW still needs `tokens_cached` mechanical sweep from prior amendment (Steps 2 / 4 / 10 test names).

---

## Round 1 — plan-critic — CONCERNS (HOW-side, no design impact)

### CONCERN 1 — `lastAssistantText` extraction under-specified — FIXED

- Step 6 had a placeholder `(messages.find(m => m.type === 'assistant_turn') as any)?...?? ''` for the §4e #4 trailing-punctuation source. `AssistantTurn` has `steps: AssistantStep[]` (each with `.content`), not a single `.text`; only legacy `Text` has `.text`. Without pinning, the heuristic would silently always pass on `''` ("ends without terminal punctuation") → false-positive hedged variant on every short remote answer.
- Resolution: pinned reuse of the existing `derivedText(message)` helper at `src/utils/chat.ts:32` — the codebase's single domain-owner of "final visible content for an assistant message" (already consumed by Bubble copy, drawer preview, exports, session titles). For `AssistantTurn` it concatenates every step's `.content` with `\n\n` (skipping empty/tool-only steps); for legacy `Text` it returns `.text ?? ''`. Concatenate-all-steps chosen over last-step-only because the visible reply IS the full block-per-step rendering, the trailing char is the last non-empty step's last char (exactly what §4e #4 asks about), and last-step-only would misfire on tool-only final steps. The pin lives in Step 4 as a "Text extraction" subsection; caller-side snippet updated in Step 6. Step 10 gains three resolver tests (§4e #4 / G, §4e #4 / H, concatenation-preserves-trailing-char invariant).

### CONCERN 2 — `effectiveNCtxOf` vs `effectiveNCtx` name inconsistency — FIXED

- Step 4 named the shared helper `effectiveNCtx(sessionId)` (matching WHAT §5); Step 6's JSX block called `effectiveNCtxOf(activeSessionId)`. Two names for one symbol.
- Resolution: settled on `effectiveNCtx(sessionId)` across Steps 4–6 (matches WHAT §5). The local variable that holds the return value in `ChatView` Step 6 is renamed to `effectiveNCtxForSession` to disambiguate the binding from the function name; all call sites use the renamed local.

Neither concern touched the design; both were HOW-side specification gaps. WHAT and HOW §A.4 unchanged by these two findings.

---

## Round 2 — plan-critic — LGTM (HOW)

After WHAT Round 2's ARCHITECTURE_DRIFT was repaired by the architect (per-draft dismiss on `context-remote-hedged` codified in WHAT §4d) and the two HOW-side CONCERNs above were fixed, plan-critic LGTM'd HOW. Implementer path opened. The post-LGTM `tokens_cached` correction + α/β amendments arrived before implementer-handoff and are absorbed in Round 3 below.

---

## Round 3 — HOW absorption pass (post-LGTM amendments)

Single planner pass combining (a) the `tokens_cached` mechanical sweep (Steps 2, 4, 10 test names — three sites where `lastTokensEvaluated + lastTokensPredicted` becomes `lastTokensCached + lastTokensEvaluated + lastTokensPredicted`, with new `tokensCached` field on the snapshot type), (b) α + β additive contract surface (new Step 9 for `usePalLoadHint` + `TalentEngine.recommendedContextTokens`, β heavy-talent scan folded into Step 4 resolver, l10n copy for `palLoadHint.*` + `fullHeavyTalent.*` pinned in §A.1.2, new scenarios N/O/P added to test coverage), and (c) full structural restructure to table-per-step form. Body dropped from ~1294 lines of essay prose to 496 lines. Review history relocated here (planner side); `how.md` footer cross-links.

Structural moves:
- §A.1 became a 3-table register (l10n pressure-test, copy decisions, softCap fate).
- §A.2 worked-example traces compressed to numbered bullet lists; added Trace 4 (β heavy-talent).
- §A.3 reload UX bulleted timeline (event → user-visible state) replacing the phase-by-phase paragraph.
- §A.4 hedged remote: one short paragraph + dismiss/action recap (no longer re-litigates the dismiss decision — already pinned in WHAT R2).
- §A.5 three pinned decisions as one table (threshold, snapshot vs live, first-time render_html + α mitigant).
- §B 10 plumbing steps + Step 11 architecture-doc absorption — each step a small table (implements / files / approach / risk / verification / tests), with code blocks reserved for type changes and predicates only.
- Tests matrix maps every WHAT §6 A–P scenario (including N/O/P) plus key edge cases (§4d escalation, §7a, §7c, §7j) to a specific test file and test name.

Hard checks before close:
- `tokens_cached` correctly threaded through Step 2 writer construction, Step 4 resolver `used` derivation, Step 10 test fixtures, snapshot type definition (4th field after `finishReason`).
- α detector + snackbar trigger + suppression in Step 9 with edge-trigger semantics spelled out, memory-aware no-fit fallback documented.
- β heavy-talent extraction (`messages[0].steps[].tool_calls[].function.name`) + sub-copy key swap + variant-identity invariance (still `context-full`, D16) documented in Step 4.
- All CTA reuses noted: α reuses §4h sheet; α no-fit reuses §4h memory-aware fallback; β reuses §4h banner CTA (Increase context / New chat) on the same `context-full` shell.
- Scenarios A–P + N/O/P all map to tests.
- Body 496 lines (target 400–500). No prose duplication of WHAT contract surface.

No design content invented; no new contracts. WHAT remains the single design source.
