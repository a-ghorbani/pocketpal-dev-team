# Architecture Library

This directory holds the **cumulative architecture truth** for PocketPal AI, organised per flow.

The library exists to stop the team from rebuilding the same design over and over inside each story. It captures **what the system must obey** — contracts, invariants, single-writer rules, canonical scenarios — independent of the implementation steps that get the code there.

---

## What lives here

One file per **flow**, bounded by a single user-facing concept. Per-component is too narrow (components churn); per-system is too broad (becomes a book nobody reads).

**Read this index, then open only the flows your change touches.** Match on the scope and the code named in each row; a change that touches none of them is in an undocumented area.

| Flow doc | Scope | Key code |
| --- | --- | --- |
| `agent-runner.md` | `runAgent()` turn loop: emitted events, abort / error / follow-up contracts | `src/services/agent/`, `useChatSession` |
| `chat-flow.md` | chat rendering, streaming, tool-call display, `AssistantTurn` shape, reasoning | chat components, `ToolUsedChip`, `reasoningCapability` |
| `remote-servers.md` | OpenAI-compatible servers: `ServerConfig`, request layer, timeouts, llama-server router | `src/api/openai.ts`, `ServerStore`, `routerState`, `serverUrl` |
| `model-loading.md` | preset model list from device rules, GGUF header / caps, native model load | `deviceRules/`, `ModelStore`, `ggufHeader`, `modelCaps` |
| `pals-and-talents.md` | what a Pal and a Talent are; tool opt-in and execution boundary | `src/services/talents/`, `src/types/pal`, `PalsSheets` |
| `palshub-checkout.md` | buying a premium PalsHub Pal in-app; ownership confirmation | `CheckoutFlowStore`, `src/services/palshub/`, native auth-session / external-link specs |
| `explore-tab.md` | Explore tab: PalsHub discovery, `[Pals \| Models]` sub-tabs | `ExploreScreen` |
| `app-shell.md` | bottom-tab navigation shell and the Home (Chats) screen | `HomeScreen`, root navigator |
| `settings.md` | Settings root and pushed sub-screens, per-control writers, testID freeze | `SettingsScreen`, `LanguageSelector` |
| `onboarding.md` | first-launch onboarding screens and completion gate | `src/store/onboarding`, `uiStore.hasCompletedOnboarding` |
| `theming.md` | design tokens, typography, DS component layer, Paper-import blocklist | `src/theme/tokens`, `src/components/ui/` |
| `asr.md` | voice input: availability gate, Whisper model wire, push-to-talk FSM, native coexistence | `src/services/asr/` |
| `tts.md` | text-to-speech: availability gate, Supertonic model wire, re-download sentinel | `src/services/tts/` |
| `deep-linking.md` | `pocketpal://` links and the Hugging Face User-Agent / attribution wire | `useDeepLinking`, `hfResolve`, `hubRunLink` |
| `benchmark-matrix.md` | on-device benchmark matrix runner and its CLI / spec / compare toolchain | `BenchmarkRunnerScreen`, `src/__automation__/`, `e2e/benchmark/` |
| `release.md` | Android native build, llama.rn payload variants (incl. Hexagon), payload gate | `android/`, `android/fastlane/`, `scripts/` |

A flow file appears here once a story has produced a vetted WHAT for it; the library accrues lazily. Adding a flow doc means adding its row.

---

## What a flow doc is for

The code is the truth. A flow doc is a **map** of it plus what the code cannot tell you: it gets an agent to the right files quickly, and warns it about what it would otherwise get wrong. If a reader could recover a line by reading the code, the line doesn't belong here.

Every flow doc has this shape, in this order:

1. **Purpose** (2–4 lines): what the flow covers, what it deliberately doesn't, and which neighbouring flow docs own the rest.
2. **Code map**: a table of the key files, modules and entry points, one line each on their role. Every path must exist.
3. **How it works** (≤ 20 lines): the main path through the code, named by function or component so the reader can jump to it. Include a state machine or lifecycle only when the flow has one.
4. **Contracts and invariants**: the load-bearing rules a change must not break, one line each with a code pointer. This covers single-writer ownership, ordering, wire formats, and cross-file agreements.
5. **Traps and decisions**: non-obvious behaviour, external constraints, and choices a reader would otherwise undo, each with its reason. Include a decision only when it is hard to reverse, surprising without context, and the result of a real trade-off.
6. **Verification**: where the tests and e2e specs for the flow live, and how to check a change by hand.

**Budget:** about 1,200 words, 2,000 for the largest flows. Going over usually means field lists, enumerations, step-by-step logic, or history, all of which the code or git already hold. A flow doc has no story IDs, round notes, or PR narrative, and no (C)/(P)/(D) markers: everything here is current truth. Reference other flow docs by file and section name, not section numbers.

## Lifecycle

A story's `what.md` is a detailed, story-scoped delta, drafted against the flow doc (`templates/what-template.md`). When the work lands, the implementer distills that delta into the flow doc in the same round, as a path-scoped commit in this repo. Only what the code can't say survives: new code-map entries, new or changed invariants, new traps and decisions. The WHAT itself stays with the story.

## Drift prevention

Architecture docs and code drift unless the pipeline enforces alignment:

- **PR-time check** — every PR's diff review verifies: "does this PR change any behaviour described in `context/architecture/*.md`?" If yes, the doc is updated in the same round.
- **Story-time check** — the architect reads the relevant architecture doc at the start of every story. If the doc no longer matches code, the architect produces a small fix-up commit BEFORE drafting the story's `what.md`. The story doesn't get to add a delta on top of stale truth.

Drift runs in **both** directions and the checks above only catch one. Code moving ahead of the doc
is the familiar case; a doc ahead of the code — behaviour designed, agreed and never implemented —
reads exactly like description, and no diff check will ever fire on it. So the story-time check asks
both questions: are recent changes reflected, and does code exist for each behaviour this doc
asserts?

Architecture drift is the failure mode that brings back the ping-pong this library was created to
prevent.

---

## What this library is NOT

- **Not a TODO list** — it describes the system as it should be, not work to be done.
- **Not an implementation plan** — those live in story-scoped `how.md` files.
- **Not historical** — old behaviour gets overwritten on merge, not appended. Git history preserves the past.
- **Not exhaustive** — only the flows currently under active design or that have hit pain points need a doc. Don't back-document the rest of the app speculatively.
- **Not a substitute for code** — when the doc and the code disagree, the code wins, then the doc gets fixed. Drift is fought, not ignored.
