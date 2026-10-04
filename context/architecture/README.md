# Architecture Library

This directory holds the **cumulative architecture truth** for PocketPal AI, organised per flow.

The library exists to stop the team from rebuilding the same design over and over inside each story. It captures **what the system must obey** — contracts, invariants, single-writer rules, canonical scenarios — independent of the implementation steps that get the code there.

---

## What lives here

One file per **flow**, bounded by a single user-facing concept. Per-component is too narrow (components churn); per-system is too broad (becomes a book nobody reads).

**Read this index, then open only the flows your change touches.** Match on the scope and the code named in each row; a change that touches none of them is in an undocumented area.

| Flow doc | Scope | Key code |
| --- | --- | --- |
| `agent-runner.md` | `runAgent()` turn loop: emitted events, abort / error / follow-up contracts | `src/services/agent/` (`runAgent`, `agentStateReducer`, `triggerMarkers`), `useChatSession` |
| `chat-flow.md` | sending, streaming, persisting and rendering a turn: tool-call and reasoning display, footer, context banner, session list | `useChatSession`, `ChatSessionStore`, `Message` / `TalentSurface`, `bannerVariantResolver`, `reasoningCapability` |
| `remote-servers.md` | OpenAI-compatible servers: `ServerConfig`, request layer and timeouts, `/props` and `/v1/models` capability discovery | `src/api/openai.ts`, `ServerStore`, `remoteCaps` / `listCaps` / `modelCaps`, `ModelStore.setRemoteModel`, `RemoteModelSheet` |
| `model-loading.md` | preset list from device rules, GGUF metadata and caps, speculative drafts, Hexagon device selection, load errors | `src/services/deviceRules/`, `ModelStore`, `store/draftResolution.ts`, `utils/{mtp,ggufHeader,modelCaps,deviceSelection}.ts` |
| `pals-and-talents.md` | what a Pal and a Talent are; tool opt-in, search grounding, execution boundary | `src/services/talents/`, `src/services/search/`, `ChatSessionStore.resolveCompletionSettings`, `systemPromptResolver`, `TalentSurface` |
| `custom-tools.md` | user-authored HTTP tools: definition, request encoding, response pipeline, secrets, manager and editor | `src/services/customTools/`, `CustomToolStore`, `CustomToolsScreen`, `CustomToolSheet`, `docs/custom-tools/` |
| `in-app-purchase.md` | buying a paid PalsHub Pal through StoreKit 2 / Play Billing; ledger, recovery, refresh, restore, link | `PurchaseStore`, `src/services/iap/`, `StorePort` |
| `explore-tab.md` | Explore tab: PalsHub discovery and `[Pals \| Models]` sub-tabs (**`redesign/phase-3` only**) | `ExploreScreen`, `ExplorePalsPanel`, `PalDetailSheet` |
| `pals-screen.md` | Pals screen grid: width-driven column count, shared row chunking, card content sizing, testIDs e2e depends on | `PalsScreen`, `palGridLayout`, `PalGridRow`, `SquarePalCard` |
| `app-shell.md` | root providers, onboarding switch, Drawer and sidebar, global hosts | `App.tsx` (`SwitchPoint`, Drawer), `SidebarContent`, `HeaderLeft`, `ROUTES` |
| `settings.md` | the Settings screen: controls and their writers, testIDs e2e depends on | `SettingsScreen`, `LanguageSelector` / `SearchableSelectSheet`, `SearchProviderStore` |
| `onboarding.md` | first-launch onboarding screens and the completion gate | `src/screens/OnboardingScreens/`, `src/store/onboarding/`, `uiStore.hasCompletedOnboarding`, `App.tsx` `SwitchPoint` |
| `theming.md` | design tokens, typography, DS component layer, Paper-import blocklist | `src/theme/tokens/`, `src/utils/theme.ts`, `useTheme`, `src/components/ui/`, `.eslintrc.js` blocklist |
| `asr.md` | voice input: availability gate, Whisper model wire, push-to-talk (**PR #786 only**) | `ASRStore`, `src/services/asr/`, `usePushToTalk`, `MicButton` |
| `tts.md` | text-to-speech: availability gate, Supertonic model wire, re-download sentinel | `TTSStore`, `src/services/tts/`, `TTSSetupSheet` |
| `model-download.md` | Android model downloads: scheduling (UIDT on API 34+, WorkManager), the shared resumable loop, resume validation, stop semantics, JS signals (**not on `main` yet**) | `DownloadModule`, `DownloadController`, `DownloadScheduler`, `DownloadEngine`, `DownloadJobService`, `DownloadBanner` |
| `deep-linking.md` | inbound `pocketpal://` links and the Hugging Face User-Agent attribution wire | `useDeepLinking`, `hubRunLink`, `HubRunSheetHost`, `hfResolve`, `hfUserAgent` |
| `benchmark-matrix.md` | on-device benchmark matrix runner and its config / merge / compare toolchain | `src/__automation__/`, `e2e/helpers/bench-runner.ts`, `e2e/scripts/` |
| `release.md` | Android native build, llama.rn payload variants (incl. Hexagon), payload gate | `scripts/verify-android-payload.js`, `scripts/android-payload-manifest.json`, `android/fastlane/`, `.github/actions/setup-hexagon-sdk/` |

A flow file appears here once a story has produced a vetted WHAT for it; the library accrues lazily. Adding a flow doc means adding its row. Flow docs describe `main`; a doc marked with a branch or PR describes code that hasn't landed yet.

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
