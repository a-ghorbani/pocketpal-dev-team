# Intent: Stabilize prompt identity + tool-loop cache instrumentation for PR #709

---

## Metadata

- **Task ID**: TASK-20260509-1733
- **Source**: [GOOA-19](/GOOA/issues/GOOA-19) — driven by Morgan (VP Eng) on top of Sage's research memo at [GOOA-18](/GOOA/issues/GOOA-18)
- **Worktree**: `./worktrees/TASK-20260509-1733`
- **Branch**: `feature/TASK-20260509-1733` (stacked on `feature/TASK-20260502-2115` = PR [#709](https://github.com/a-ghorbani/pocketpal-ai/pull/709))
- **Complexity**: complex
- **Native Changes**: YES (must surface tokenized prompt length / `tokens_cached` / `n_past` from native via the `llama.rn` bridge to JS — minimal change, gated to dev-mode log)
- **Visual Confirmation**: NO (instrumentation, serialization, grammar mode toggle, runtime fallback — no UI surface beyond optional "preparing tool call" marker, which is an open question, not a deliverable)
- **Created**: 2026-05-09
- **Status**: approved

---

## Request

Verbatim from [GOOA-19](/GOOA/issues/GOOA-19):

> # Implementation: PocketPal-side stabilization for tool-loop KV cache reuse
>
> ## Source
>
> Approved by Morgan based on Sage's research memo on [GOOA-18](/GOOA/issues/GOOA-18).
>
> - Full memo: https://github.com/a-ghorbani/rd-team/blob/main/research/reports/2026-05-09-tool-calling-kv-cache-json-tool-calls-llama-cpp-llama-rn.md
> - Verdict: GO (decision matrix 4.2/5 for this path vs 2.4/5 for upstream-wait; ship-now TRL 7 vs 4)
> - Headline finding: in `llama.rn`, KV reuse is decided from token-prefix identity *before* grammar ever samples a token. Grammar is not in the cache-match path — prompt drift is. PR #709 changes the prefix-producing layer, so that's where we patch.
>
> ## Goal
>
> Land a PocketPal-side patch alongside or on top of PR [#709](https://github.com/a-ghorbani/pocketpal-ai/pull/709) that:
> 1. Proves whether KV cache reuse actually collapses, by instrumenting the message-to-API boundary.
> 2. Removes any prompt-identity drift across turns introduced by `assistant_turn.steps[]` → API message reconstruction.
> 3. Provides a two-stage unconstrained-then-constrained fallback that protects long-context prefix reuse when grammar-on-everything would collapse it.
>
> ## Scope
>
> ### Step 1 — Per-turn diagnostics at the message-to-API boundary
>
> For every turn in the multi-turn tool loop, log (dev-mode only is fine):
>
> - Rendered prompt hash (stable hash of the final string sent to the runtime)
> - Tokenized prompt length (surfaced from native via the bridge)
> - Longest common prefix (LCP) vs previous turn's prompt tokens
> - `tokens_cached` / `n_past` / prompt-eval time from completion result
>
> Goal: confirm the **≥80% prefill reuse** target on append-only turns. Below threshold triggers the Step 4 fallback path.
>
> ### Step 2 — Prompt-identity stabilization in `assistant_turn` → API message reconstruction
>
> Audit and lock down the PR #709 path that walks `assistant_turn.steps[]` and re-emits assistant/tool messages. Add a unit test that proves byte-for-byte stable serialization across:
>
> - Successful completion
> - Retry of a tool-using turn
> - Reload of the conversation
> - Orphan-pair synthesis (`role: 'tool', content: 'aborted'`)
> - Tool argument stringification (whitespace, key ordering, escaping)
> - Assistant content projection / reasoning text retention
>
> ### Step 3 — Lazy grammar mode
>
> Where the chat template supports it, prefer lazy tool-call grammar (`tool_choice=auto` + grammar triggers) over eager whole-turn JSON schema constraint. Fall back to eager when the template doesn't support triggers.
>
> ### Step 4 — Two-stage unconstrained-then-constrained fallback
>
> Gated behind a feature flag (off by default). When Step-1 diagnostics show reuse <80% under constrained mode:
>
> 1. Run the long-context turn **unconstrained**, detect tool-call intent.
> 2. Run a **short follow-up constrained completion** for tool arguments only.
> 3. Append the tool result and continue with the stable serialized transcript.
>
> ## Constraints
>
> - Mobile target: do not regress steady-state memory or per-turn latency vs current PR #709 baseline.
> - Stay within llama.cpp / llama.rn ecosystem — no new structured-output runtime dependency.
> - Ship alongside PR #709 — do **not** block its merge on Step 4 (the fallback can land in a follow-up if needed).
>
> ## Acceptance criteria
>
> - [ ] Step 1 instrumentation logs prompt hash / token length / LCP / `tokens_cached` per turn.
> - [ ] Unit test proves byte-stable assistant/tool transcript serialization across the 6 scenarios in Step 2.
> - [ ] On a 3-turn tool loop on at least one target model, prefill reuse ≥80% on append-only turns (measured via Step 1 logs).
> - [ ] Lazy grammar in use where the template supports it (Step 3).
> - [ ] Two-stage fallback implemented behind a flag; verified to keep tool args structurally valid while preserving long-context prefix reuse (Step 4).
>
> ## Open questions to resolve during implementation
>
> - Which target model families are most sensitive to eager grammar on long turns? Split the bench by architecture: standard decoder-only vs SWA / hybrid / recurrent.
> - Does the failure reproduce identically in raw `llama.rn` outside PocketPal's reducer/store path? A 30-minute minimal harness resolves "is this product or runtime".
> - UX: do we expose a "preparing tool call" marker earlier if final args are generated in a short second pass?
>
> ## Out of scope
>
> - Upstream `llama.cpp` patches. We watch the memo's "Watch-for" list but do not block on upstream.
> - `llama.rn` bridge fixes beyond what's necessary to surface prompt-token diagnostics from native to JS.

---

## Clarifications

The request was reviewed by Morgan and approved with sufficient detail to proceed. The only design questions are the three "open questions" the requester wants resolved during implementation, not blockers on intent. Captured here so the architect/planner can answer them in `what.md` / `how.md`:

- **Q1**: Which target model families are most sensitive to eager grammar on long turns? Split the bench by architecture (standard decoder-only vs SWA / hybrid / recurrent).
  - **A1**: To be answered by the architect during the bench plan in `what.md` / `how.md`. The Sage memo on [GOOA-18](/GOOA/issues/GOOA-18) covers the per-architecture risk; carry that forward into the bench matrix.
- **Q2**: Does the failure reproduce identically in raw `llama.rn` outside PocketPal's reducer/store path? A 30-minute minimal harness resolves "is this product or runtime".
  - **A2**: To be answered as part of Step 1 diagnostics — if Step-1 logs on PocketPal's path show reuse ≥80%, we have already isolated this to PR #709's reconstruction layer and the harness is unnecessary; if reuse < 80% AND Step-2 stabilization does not lift it, run the harness before committing to Step 4. Answer in `how.md`.
- **Q3**: UX: do we expose a "preparing tool call" marker earlier if final args are generated in a short second pass?
  - **A3**: Not in scope for this story unless required by the Step 4 implementation; if it is, the architect should flag in `what.md` and we open a separate UX issue rather than pulling design work into this PR.

Approved by Morgan (VP Eng, requester for this run) on 2026-05-09 — moving directly to architect stage. The three open questions are not blockers on intent; they are downstream answers the architect/planner own.

---

## What this brief is NOT

- not a design doc — `pocketpal-architect` produces `what.md`
- not an implementation plan — `pocketpal-planner` produces `how.md`
- not a place for invented acceptance criteria, performance budgets, coding conventions, or design constraints — those are downstream work or already covered by `context/patterns.md`
- not a paraphrase of the issue — the request above is the issue body verbatim
