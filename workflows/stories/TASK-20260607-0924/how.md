# HOW — TASK-20260607-0924 (E2E fixes for #764)

Quick tier. All edits live under `e2e/` (no app `src/` change). Sequencing: land
the three static fixes first (①②④), then the device-gated ③.

## Steps

1. **① Env-controllable reset** — `e2e/wdio.android.local.conf.ts`
   - `'appium:noReset': process.env.E2E_NO_RESET === 'true'`
   - `'appium:fullReset': process.env.E2E_FULL_RESET !== 'false'`
   - Document the two env vars in the file header. Defaults preserve today's
     behaviour (reset on, full-reset on).

2. **④ Locale-proof Pals tab** — `e2e/helpers/selectors.ts`
   - `drawer.palsTab → byTestId('drawer-item-pals')` (app already exposes this
     testID at `SidebarContent.tsx:504`; no app change). `palsTab` is the
     drawer-open indicator used by `DrawerPage.isOpen/waitForOpen/waitForClose`,
     so this fixes the `language`-spec breakage at its root.

3. **② Dismiss the more-room sheet** — `e2e/helpers/model-actions.ts`
   - Add `dismissContextRoomSheetIfPresent()` mirroring
     `dismissPerformanceWarningIfPresent()`, tapping
     `Selectors.contextBanner.sheetCancel` (`increase-context-cancel`) when
     displayed; no-op otherwise.
   - Call it at the top of the `waitForInferenceComplete` poll loop.
   - The sheet is opened by the pal-load-hint snackbar's "More room" action
     (ChatView `setIncreaseSheetOpen(true)`), not auto-opened — verify the real
     overlay on device and extend call sites (e.g. after `sendMessage`) if the
     snackbar itself is the blocker.

4. **③ Voices/TTS sheet (device investigation)** — `thinking-pal-override.spec.ts`
   - Static finding: `TTSSetupSheet` ("Voices") opens only via a *press* of the
     expanded `VoiceChip` (`!hasVoice` state); `VoiceChip` renders null when TTS
     is unavailable → explains Aether passing.
   - Run the spec on a TTS-capable real device (`--skip-build` against the
     installed v1.15.2 e2e app) and inspect the failure screenshot to confirm
     the overlay + trigger.
   - Fix per finding: most likely dismiss the sheet before the toggle read
     (reuse `dismissContextRoomSheetIfPresent`-style helper for
     `voicechip`/setup sheet) and/or stabilise the toggle tap.

## Verification

- `e2e` typecheck (`yarn --cwd e2e typecheck`).
- Device run of `thinking-pal-override` (and a smoke of `talent-tool-use` /
  `language`) on connected Android devices, skip-build.
- No native build required.

## Outcome (verified on Pixel 9, Android 16)

All four items implemented (e2e-only; no app `src/` change) and device-verified
against the installed v1.15.2 e2e build (`--skip-build`, APK pulled from a
fleet device):

- **① env reset** — `E2E_NO_RESET`/`E2E_FULL_RESET` plumbed; live-exercised
  (noReset runs reused the install; fullReset runs reinstalled).
- **④ Pals tab** — `byTestId('drawer-item-pals')`; the drawer-open detection and
  Pals navigation worked across every run.
- **③ Voices overlap** — root cause: the TTS `VoiceChip` overlaps the thinking
  toggle's centre, so the centre-tap opened the "Voices" sheet instead of
  flipping the toggle (null VoiceChip on Aether ⇒ it passed there). Fix: tap the
  toggle's left edge + dismiss the sheet. `thinking-pal-override` 0/3 → 3/3.
- **② more-room overlay** — root cause: the pal-load-hint snackbar overlays the
  send button; the send-tap hit its "More room" action, opened the
  increase-context sheet, and the message never posted (so `ai-message` never
  appeared). Fix: clear overlays + wait out the snackbar before sending, confirm
  the user message posted (retry once), and `waitForAiMessage` dismisses the
  sheet mid-inference. `talent-tool-use` timeout → passing (HTML preview ✓).

Note: ③ and ② are both real, if minor, app-layout overlaps (a user could also
mis-tap the toggle / send button when these controls overlap). Scoped here to
the e2e suite per the issue; flagged as a possible app-side follow-up.

`yarn --cwd e2e typecheck` has only pre-existing failures (worktree lacks the
app root `node_modules`; `SettingsPage.serverConfig` predates this work) — none
in the changed files; the specs compiled and ran on device.
