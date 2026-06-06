A. Headline feature

  A1. Warning → Full → Recover (end-to-end)

  Setup. Context = 512 tokens. Load a small local model. Fresh chat.
  Steps. Have enough turns to cross ~80% used. Observe banner. Dismiss it. Continue until truncation. Tap "Increase context", confirm 2048.
  Expected.
  - Warning banner appears before truncation; dismissable.
  - After dismiss, warning reappears on the next still-tight turn.
  - Once truncated, a sticky no-dismiss "full" banner appears.
  - After Increase reload, the sticky banner clears without sending a new message; chat history intact.

  A2. New-chat CTA

  Setup. Be in a "full" state.
  Steps. Tap "New chat".
  Expected. Fresh empty chat opens; no banner; old chat remains in the list.

  A3. Remote model: hedged advisory, no Increase CTA

  Setup. Activate a remote model. Send a prompt that returns a long response with no terminal punctuation and no explicit length-stop signal.
  Expected. A softer "may be cut off" advisory appears. No "Increase context" button. Dismissable. Wording is hedged (may), not assertive.

  A4. Pal-load hint: heavy pal fires, light pal doesn't

  Setup. Context = 2048. Two pals: one with render_html, one with only light talents (datetime/calculate).
  Steps. Activate each pal in turn (separate chats).
  Expected. Heavy pal raises a one-shot snackbar with an "Increase context" action; dismissable. Light pal raises no snackbar. After dismiss, switching back
  to the heavy pal in the same session does not re-fire the snackbar.

  A5. Trigger is ratio-only (talent-agnostic)

  Setup. Identical model, identical context size, identical conversation length. One chat has render_html pal, the other has no pal.
  Expected. The warning banner appears at the same ratio in both. Talent metadata may differ the copy on the full banner or trigger the pal-load snackbar, but
   it never moves the banner's ratio threshold.

  B. State sync across screens

  B1. Banner-driven Increase is visible in Settings (immediately)

  Setup. Settings = 250. Load a model. Verify model card / details show loaded = 250.
  Steps. Go to chat, trigger Increase to 2048, wait for reload. Navigate to Settings without unmounting / restarting.
  Expected. Settings shows 2048. Loaded-context indicator shows 2048. No "reload required" mismatch indicator.

  B2. Settings Reload uses the Settings value, not anything else

  Setup. Be at the end of B1 (Settings = 2048, model loaded at 2048).
  Steps. Change Settings to 512. Reload-required indicator should appear (if surfaced). Tap Reload.
  Expected. Model reloads at 512. Indicator clears. Loaded-context shows 512. (No stale value from chat-side bumps wins.)

  B3. Models-screen load of a different model uses the Settings value

  Setup. Settings = 4096, model A loaded at 4096.
  Steps. Tap a different model (B) in the Models screen.
  Expected. Model B loads at 4096.

  B4. App restart: cold load matches Settings, no phantom mismatch

  Setup. Settings = 4096, model A loaded at 4096. Force-kill.
  Steps. Relaunch. Wait for auto-reload of last-used model.
  Expected. Model A loads at 4096. Settings shows 4096. No reload-required indicator on first launch.

  D. Failure recovery

  D1. Reload failure (Increase or Settings) leaves the user able to continue

  Setup. Force initContext to fail (low-memory device + large request, or a corrupted target).
  Steps. Trigger the failing reload from each surface: (a) banner Increase, (b) Settings Reload.
  Expected for both. A failure snackbar. Chat is still usable: the model is either still loaded at the prior n_ctx or in a clear "no model" state with a
  recovery path. The user is not stuck with a dead chat or a frozen Settings screen.

  D2. Increase CTA is hidden when no larger tier fits

  Setup. Low-memory device or context already at the device's memory ceiling.
  Steps. Reach the full-banner state.
  Expected. Banner shows only "New chat" — no Increase button. New chat works.

  E. Coexistence and suppression

  E1. No banner when no model is loaded

  Setup. No model selected. Navigate to a chat that previously hit "full".
  Expected. No context-warning / context-full / hedged banner. (Existing HTML soft-cap may still fire on its own conditions — it's independent.)

  E2. Full banner suppresses the per-turn "cut off" footer

  Setup. Reach the full-banner state.
  Expected. The turn that triggered "full" does not show its usual "cut off — likely context full" footer text. The sticky banner is the single advisory
  surface. (Plain "interrupted" footer for non-context stops still appears in other situations.)

  E3. HTML soft-cap coexistence

  Setup. Trigger HTML soft-cap conditions (4+ HTML previews) once with context-full active, once without.
  Expected. When context-full is active: context-full wins, HTML soft-cap hidden. When only HTML soft-cap conditions hold: HTML soft-cap appears as before.

  F. Session scoping

  F1. Dismiss is per-session

  Setup. Two chats, both in a warning state.
  Steps. In chat A: dismiss. Open chat B.
  Expected. Chat B still shows its warning.

  F2. Sticky full survives a session switch

  Setup. Chat A in full state.
  Steps. Open chat B, then return to chat A.
  Expected. Chat A still shows the sticky full banner.