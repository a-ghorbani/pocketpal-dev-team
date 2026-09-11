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

## Lifecycle

```
Story-scoped WHAT (delta)            Cumulative architecture (this dir)
─────────────────────────            ──────────────────────────────────
workflows/stories/<TASK-ID>/         context/architecture/<flow>.md
  what.md                            (current truth)

  proposes additions, changes,       (read by next story's architect
  decisions, edge cases on top       to draft its delta against this)
  of context/architecture/<flow>.md
                                                ▲
            on PR merge ──────────────────────  │
                                                │
              architect updates the architecture
              file with the approved delta in
              the same round that lands the code
```

The story-scoped `what.md` is born **as a delta** on the architecture file and dies **merged into it** when the work ships.

---

## Conventions used in architecture files

Mark every claim with one of:

- **(C)** — current behaviour, documented from code
- **(P)** — proposal, open for challenge
- **(?)** — open question, decision needed
- **(D)** — decision (was an open question, now resolved)

Architecture files should mostly be **(C)** — they're current truth. Story WHATs are mostly **(P)** and **(?)** — they're deltas being proposed. On merge, the architect resolves the markers (anything (P) becomes (C); any remaining (?) is a bug — the WHAT shouldn't have shipped).

---

## Required sections (template)

Every architecture file should have:

1. **Data model** — the on-disk and in-memory shape. Glossary for any term used elsewhere in the doc.
2. **External shape** — wire format / API / protocol the flow exposes (if any).
3. **State machine** — lifecycle states, transitions, what the user sees in each (if any).
4. **Contract** — for each component participating in the flow: what it renders / produces / writes; what it does NOT.
5. **Single-writer rule** — for each mutable field, the canonical writer. Reading is unrestricted.
6. **Canonical scenarios** — the rendered or observable shapes the design must produce. Manually testable.
7. **Edge cases** — what happens at the boundaries (cancel, empty, race, missing dependency).
8. **Decisions** — resolved trade-offs. Each has a short rationale.

Use `templates/what-template.md` as a starting point.

---

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
