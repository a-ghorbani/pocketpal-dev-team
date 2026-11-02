# Review Lenses

Lens definitions for `docs/standards/code-review.md` (the shared contract); `pocketpal-reviewer` applies those named in its prompt. Checks are a floor. Every lens reads the review map (or WHAT in slice mode), the changed code, and its own context below.

## Correctness

Worldview: a test engineer probing normal, edge, async, interruption, and recovery behaviour; concrete failure modes over style. Context: story, PR body, issue, acceptance criteria; `context/patterns.md`, `context/pocketpal-overview.md`. Prioritize changed behaviour and regression paths over speculative coverage.

Inspect:
- broken behaviour, bad assumptions, state transitions, cancellation, retries, partial updates, stale data, async races;
- null/undefined handling and malformed inputs;
- branches for success, error, disabled, missing, and cleanup states;
- regression risk in existing user flows.

Common risks: empty assistant messages, streaming partials, interrupted completions; settings clear paths that keep stale values.

## Architecture and maintainability

Worldview: a mobile/RN software architect. Context: `docs/standards/architecture.md`, `context/patterns.md`, `context/pocketpal-overview.md`; the touched flow docs (story `ARCHITECTURE_DOCS`, else the `context/architecture/README.md` index rows covering the changed files). Where context and code disagree, the code and diff are the truth; report drift only when it creates risk.

Inspect:
- cross-module contracts and public types; hidden dependencies; coupling and layering;
- store/repository/component boundaries; hook and MobX ownership;
- registry, dispatch, plugin, and extension points;
- abstractions adding indirection, not removing complexity; divergence from `context/patterns.md`;
- maintainability and readability: duplication, naming, fragile logic, magic constants, hard-to-test design;
- **comment load** (reported here, reviewed unasked; a recurring defect): classify each questionable comment by the test in `docs/standards/comments.md` and **name the case** ("case 2: does three things", never "too many comments"). Volume signals a clarity or design problem; fix the code. Flag task narrative;
- **flow-doc sync** (pipeline PRs only): a behaviour change a flow doc describes, without a matching update to that doc (or without `(pending #<PR>)` on lines for unlanded code), is a finding; on an external PR the lead notes it in `final.md` (`code-review.md`, Canonical Inputs).

Common risks: app code bypassing the worktree/story pipeline; feature-specific branching inside shared model/chat flows; pal-id coupling where a name- or capability-keyed contract is expected; UI components owning persistence or model-runtime concerns; registry/schema/test names drifting from dispatch keys.

## Tests

Inspect: missing coverage, skipped tests, manual validation gaps; whether assertions, mocks, and test names prove the contract; E2E coverage for user-visible multi-step workflows.

- **Coverage floor: 60%** (statements, branches, functions, lines) on the changed surface; below it is a `BLOCKER` unless explicitly waived.
- **Test strength (mutation-style).** Coverage is a weak proxy. For each critical test, state what regression it catches: if the production line under test were broken or deleted, would it fail? A test that passes against a broken implementation is theater: flag it, don't count it.

Common risks: tests asserting implementation details while missing behaviour; mocks hiding native, database, or runtime contract breaks; manual-only coverage for complex chat/model flows.

## Security and privacy

Worldview: a **mobile, on-device** security engineer: local LLMs on the user's phone, no server perimeter. The threat is untrusted content crossing into the app and reaching a dangerous sink, plus data exposure on the device. Server-appsec instincts mostly do not apply. Context: `docs/standards/architecture.md`, `context/pocketpal-overview.md`.

A trust-boundary finding names an untrusted **source**, the **sink** it reaches unsanitized, and shows it **reachable on `main`** with that input (call path, `file:line` per hop). A guard on a path no attacker input reaches is defence in depth: at most a SUGGESTION.

- **Sources:** model output (text, tool calls, markdown/HTML); downloaded GGUF files and metadata; web-search results; deep-link/App Intent/Shortcuts/universal-link params; PalsHub rows (shared Supabase); imported pals/files; clipboard and share-sheet input.
- **Sinks:** WebView/HTML/markdown render and any JS execution (incl. the Pals-as-apps capability bridge); file-system paths (model load/import); native-bridge calls; outbound network; logs and crash reports; persisted stores (chat history, keys).

Inspect:
- model output → render/execution (markdown, HTML, WebView, JS eval, tool-call/JSON parsing);
- the Pals-as-apps capability allowlist: over-grant, sandbox escape, bridge calls reachable from model-driven content;
- downloaded models and imported files: path traversal, unchecked source, oversized/malformed input to native parsers (llama.rn, GGUF, tokenizer);
- deep links, App Intents, Shortcuts: attacker params reaching sensitive actions;
- data at rest and in logs: chat history, API keys, server/auth tokens, crash reports;
- network egress: what leaves the device, where, with which tokens/headers; PalsHub PostgREST trust (RLS/grants live outside the review surface);
- debug/E2E hooks reachable in production builds;
- new dependencies with elevated execution or parsing risk.

Common risks: config copied into worktrees outside the allowlisted sync scripts; weak parsing around tool calls, JSON, URLs, or generated markup.

## Performance and resources

Job: find performance-sensitive paths the evidence plan missed. Context: `docs/standards/architecture.md`, `context/pocketpal-overview.md`, `context/patterns.md`, the story's `evidence.md`.

Look for:
- re-render per token on streaming paths; hot render paths in repeated chat components;
- per-keystroke writes; repeated serialization, parsing, database writes, large object copies, bridge traffic;
- output or context growth over a long chat (HTML/tool outputs persisted or replayed unbounded, message reconstruction);
- bundle-size jumps (large or duplicate packages, WebView/native additions);
- timers, background/foreground work, long-running or unbounded work (generated JS, expensive parsers);
- RAM/heap, model load time, startup, battery.

Each such path without a measurement row is a `CONCERN` that requires a row in `evidence.md` (`bench` smoke, `memory-profile`, Reassure, or an on-device A/B; `docs/workflows/evidence-and-decisions.md`), resolved by that measurement, not by argument. Never opine on speed in place of numbers.

## Platform

iOS vs Android behaviour differences only; native-build verification is not this lens (`code-review.md`, Native verification). Context: `context/patterns.md`; `docs/workflows/visual-capture.md` when capture evidence is relevant.

Inspect: safe area, keyboard, modals, WebView, permissions, hardware behaviour; iOS simulator/device vs Android emulator/device differences; version floors (iOS minimum, Android API min).

Common risks: UI behaviour tested on one platform only; E2E specs assuming one platform's accessibility or navigation behaviour.

## Data and migration

Worldview: a data and persistence engineer. Context: `docs/standards/architecture.md`, `context/patterns.md`.

Inspect:
- WatermelonDB schema, versions, and migrations;
- model adapters and safe parse/stringify helpers;
- repository create/update/read paths; persisted settings and defaults; cache invalidation;
- backward compatibility for existing users, downgraded app states, rollback;
- round-trip and clear/remove tests.

Common risks: optional fields unclearable because `undefined` means no-op; schema version bumps without migrations or native verification; JSON parse fallbacks masking corrupted persisted state; new settings missing from import/export or migration paths; local store and database state diverging.

## UX and accessibility

Worldview: a product designer and accessibility specialist. Context: story/PR requirements and screenshots; `context/patterns.md`; `docs/workflows/visual-capture.md` when visual evidence is required. Don't require screenshots for invisible changes.

Inspect:
- visible flows, honest states, error messages, copy consistency, lost affordances;
- new visible strings and localization;
- loading, pending, disabled, empty, error, and recovery states;
- hit targets, labels, accessibility roles/state, focus, screen-reader behaviour;
- modal, safe-area, and keyboard interactions;
- test IDs for E2E without test-only UI leaking into production;
- visual regressions in repeated chat/message components.

Common risks: hardcoded strings outside `en.json`; pending states that never clear or lack user context; icon-only controls without accessible labels; suggested prompts or chips overlapping the chat input or keyboard; new bubbles/cards disrupting chat scanability or message grouping.

## Local invariants

Worldview: small contract breaks on changed lines that broader lenses miss; narrow, mechanical, line-grounded. Context: `context/patterns.md` when the change touches named registries, schemas, selectors, stores, model adapters, or test fixtures.

Inspect:
- injected/derived settings have clear/disable paths;
- wrappers, parsers, and regex handle malformed plausible input;
- registry/schema/UI/test names match dispatch keys;
- mapped React keys survive duplicate values;
- test names and comments match actual assertions;
- constants and IDs match callers, selectors, and persisted values.

Common risks: `undefined` accidentally meaning "preserve stale value"; duplicate display values used as React keys; test IDs renamed without E2E selector updates; a registry name differing from schema, localization, or fixture name; comments describing a previous implementation after review fixes.
