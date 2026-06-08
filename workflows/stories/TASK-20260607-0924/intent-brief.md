# Intent Brief — TASK-20260607-0924

**Source:** GitHub issue [#764](https://github.com/a-ghorbani/pocketpal-ai/issues/764) — "E2E test fixes from v1.15.2 release validation"

**Status:** shipped — PR #765 merged; issue #764 closed (2026-06-08)
**Complexity:** quick (E2E test-harness only; no app `src/` change)
**Base:** `origin/main` @ `f0c0ca2` (v1.15.2)

## Request

Four E2E fixes surfaced during v1.15.2 device-fleet validation. Validate each
against the code, then fix the ones that apply.

1. **Env-controllable reset** — `e2e/wdio.android.local.conf.ts:39-40` hardcodes
   `noReset:false` / `fullReset:true`; MIUI/HyperOS devices hit
   `INSTALL_FAILED_USER_RESTRICTED` and the cap has to be re-patched every
   release. Make it env-overridable.
2. **Dismiss the #763 "Give this chat more room" overlay** in chat-driving
   specs — it sits over the chat and stalls inference (`talent-tool-use` times
   out on `ai-message`). Add a `dismissContextRoomSheetIfPresent()` helper
   mirroring `dismissPerformanceWarningIfPresent()` and call it in the
   inference-wait path.
3. **Voices/TTS sheet interference** in `thinking-pal-override.spec.ts` — a
   Voices sheet overlays the chat at the toggle read (`Expected false / Received
   true`, 5/6 devices; passes on Aether). Find why it opens and dismiss/avoid it.
4. **Pals drawer tab looked up by English text** — `e2e/helpers/selectors.ts`
   `palsTab → byText('Pals')` breaks after a language switch (`language` spec).
   Use a stable testID or locale-aware match.

## Constraints (this machine)

- Android only — no iOS build/verification available.
- Native builds are slow (virtualization). Prefer changes that need no APK
  rebuild; reuse the installed v1.15.2 e2e build for device verification.

## Validation outcome

All four apply. ①②④ are test-harness-only (no APK rebuild). ③ requires a device
repro to confirm the trigger (full investigation requested).

## Acceptance criteria

- `noReset`/`fullReset` driven by `E2E_NO_RESET` / `E2E_FULL_RESET` with
  backward-compatible defaults.
- A `dismissContextRoomSheetIfPresent()` helper that no-ops when the sheet is
  absent and is wired into the inference-wait path.
- `palsTab` survives a language switch.
- ③ root-caused on device and dismissed/avoided, or a documented follow-up if
  the trigger can't be reproduced.
- Architecture docs unaffected (test-infra only).

## Resolution

Shipped in PR #765 (merged), issue #764 closed. All four items fixed in the
e2e harness — no app `src/` change, no APK rebuild. Verified on a 6-device
physical Android fleet (parallel pass + sequential re-run to filter contention).

Fleet follow-ups recorded on #764 (out of scope for this story, not blockers):
- `thinking-pal-override` still fails where a long pal name overflows the input
  control bar (toggle fully covered) — app-layout, resolved by the chat-input
  redesign that drops the pal name from the input.
- `language` can time out when a long language menu scrolls the target option
  off-screen — spec should scroll to it.
- Models >~500MB won't load on low-RAM devices (POCO X5 / Redmi 12) — so
  `talent-tool-use` / `draft-autosave` fail there by hardware.
- `purchase-flow` requires `E2E_API_KEY`.
