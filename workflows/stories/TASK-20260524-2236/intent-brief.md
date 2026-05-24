# Intent: Wire Palshub-side pact.talents + greeting fields into PocketPal pal download

## Metadata

- **Task ID**: TASK-20260524-2236
- **Source**: https://linear.app/pocketpal/issue/FOU-128
- **Worktree**: `./worktrees/TASK-20260524-2236`
- **Branch**: `feature/TASK-20260524-2236`
- **Complexity**: standard
- **Native Changes**: NO
- **Visual Confirmation**: NO
- **Created**: 2026-05-24
- **Status**: approved

---

## Request

FOU-128

Linear: https://linear.app/pocketpal/issue/FOU-128

Implement PocketPal-side consumption of new Palshub pal fields that landed in palshub-app PR #66 (greeting/images/models/disclaimer) and PR #68 (PACT talents).

Scope (this task):
1. pact.talents — copy through palshub detail/mobile payload into local Pal.pact on download
2. greeting.text + greeting.suggested_prompts — map to local Pal.greeting.text + greeting.suggestedPrompts (camelCase boundary rename); UI for both already exists
3. Primary image — confirm existing thumbnail_url path keeps working (Palshub now derives it server-side from images[].is_primary)
4. Recommended model — confirm existing model_reference/model_settings path keeps working (Palshub now derives it server-side from models[].is_recommended)

Deferred (explicit non-goals):
- disclaimers
- multi-image gallery / carousel
- alternative model picker (models[] beyond is_recommended)

Key references:
- Palshub PR #66: https://github.com/llm-ventures/palshub-app/pull/66 (additive JSONB columns, server-derives legacy singular columns from the new arrays)
- Palshub PR #68: https://github.com/llm-ventures/palshub-app/pull/68 (talents registry + pals.pact = { version: 1, talents: [{ name, required? }] }; mobile route /api/mobile/pals/[id] forwards pact)
- PocketPal local Pal.pact + Pal.greeting shape: src/types/pal.ts:115-136
- Local DB v7 already has pact + greeting columns: src/database/migrations.ts:133, src/database/schema.ts:128
- Download conversion site: src/store/PalStore.ts:430-490 (convertPalsHubPalToLocalPal)
- Persistence: src/repositories/PalRepository.ts (already JSON-stringifies pact/greeting for local pals)

What's needed:
- Extend PalsHubPal interface in src/types/palshub.ts with pact, greeting (snake_case fields as they arrive over the wire); optional loose types for images/models since they're not consumed yet
- Update convertPalsHubPalToLocalPal to populate pact and greeting (with snake_case → camelCase rename for suggestedPrompts)
- Verify PalRepository create/update paths correctly persist pact/greeting for palshub-sourced pals (and round-trip across app restart)
- Verify re-downloading an existing palshub pal refreshes pact/greeting without dropping them
- Verify no regression when palshub returns pact/greeting as null/absent (older pals)

Acceptance criteria (from FOU-128):
- Download palshub pal declaring pact.talents → local pal.pact.talents set; recognized talents (e.g. render_html on SketchPal) activate at chat time via TalentRegistry
- Download palshub pal with greeting.text → greeting bubble shows on empty session
- Download palshub pal with greeting.suggested_prompts → tappable chips appear above input
- Recommended model still resolves (regression on model_reference after Palshub PR #66 server-side derivation)
- pact/greeting survive app restart
- Re-download refreshes pact/greeting without dropping them
- No regression when fields null/absent

Out of scope (don't touch):
- Per-user consent UX for talents
- Re-evaluation on edit
- Marketplace badges/filters

Native impact: none expected (TS/JS only, no native modules, no schema migration — DB v7 already has the columns). NATIVE_CHANGES=NO unless you discover otherwise.

Repository: ./repos/pocketpal-ai

---

## Clarifications

none — request is self-contained: scope, non-goals, file pointers, acceptance criteria, and native impact are all explicit.
