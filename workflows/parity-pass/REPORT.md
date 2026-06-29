# Figma Parity Pass — REPORT (redesign/phase-3)

**Branch:** `redesign/phase-3` @ 276663a9 · **Canonical Figma:** `RZxDJea4t6jnBZrV4YBacF`, page `0:1` ("App design")
**Captures:** `workflows/stories/redesign-captures/` (iPhone 17 Pro sim + Android emulator-5554, light+dark)
**Montages:** `workflows/parity-pass/montages/<screen>-{light/dark rows}.png` (3×2: Figma|iOS|Android × light/dark)
**Figma renders (live, this pass):** `workflows/parity-pass/figma/` · **node map:** `workflows/parity-pass/MAPPING.md`
**Figma auth:** confirmed live (handle `Asghar`, pro). Renders are fresh — not the stale POC `figma/` PNGs.

> _Findings table populated from 5 per-group montage analyses. Severity: BLOCKER (breaks design intent / wrong element) · CONCERN (clear drift, should fix) · NIT (minor)._ 

## Executive summary

**20 screens montaged** (3×2 Figma|iOS|Android × light/dark). Figma side rendered **live** from the
canonical file this pass (auth confirmed). Verdict tally (**final, after re-capture rounds 2 & 3** — all
capture-blocked screens now resolved):

- **CLEAN:** 2 — `search-prompt`, `create-pal-generation`.
- **DRIFT (real parity bugs):** 12 — `home`, `chat-conversation`, `models-ready`, `models-explore`,
  `model-settings`, `my-pals-downloaded`, `my-pals-created`, `create-pal-general`, `search-0-results`,
  `settings-preferences`, `settings-app`, `settings-about` — plus `settings-launcher` (DRIFT + state-mismatch).
- **CONCERN / surface-question:** 1 — `chat-model-picker` (Models tab now shows a model row; richness/
  structure differs from canonical — confirm surface mapping; downgraded from BLOCKER).
- **DEFERRED (chrome clean, content server-gated):** 1 — `explore-pals` (PalsHub 3010 down).
- **NO-FIGMA-SOURCE (DS-derived / intended stub):** 3 — `chat-empty-no-model`, `chat-gen-menu`,
  `explore-models-stub` (intended disabled "coming soon" segment).
- **CAPTURE-UNRELIABLE:** 0 — all 5 resolved via round-2/3 re-capture (worktree→repo sync). See the
  **Re-capture round 3 — FINAL** section.

**Reliable BLOCKERs (our-render-vs-Figma, fix candidates):**
1. **Home pal carousel** ships as solid colored circles/avatars instead of the Figma rounded-18 **image
   cards** (peach active border `#c58334` / label `#a86c34`). [`home`]
2. **Home "Model used / id / chevron" two-tone chip** is absent (device shows a flat "Select a model"). [`home`]
3. **Model-settings footer** reads **"Cancel / Save Changes"** vs Figma **"Close / Download"** (copy). [`model-settings`]
   - _(The first-pass "Models filter chip red vs amber" BLOCKER was WITHDRAWN after round 2 — the chip is amber, matching Figma.)_
- *Verify (was a 5th BLOCKER, downgraded after reconcile):* `chat-model-picker` — canonical `454:25590`
  is a model-row modal; device shows a Pals|Models list → confirm on device whether it's wrong-capture or
  genuine UI divergence.

**Source-reconcile results** (live Figma re-check of ambiguous findings — see `RECONCILE.md`):
- `my-pals` header: device serif title is **drift** — canonical Page Header is **Inter Medium 18 sans**
  (POC-9 what.md conflict flagged for PM); the device back-chevron is **correct** (canonical has it).
- `chat-model-picker`: confirmed canonical = model-row modal; device surface differs → **verify on device**.
- `settings-launcher`: launcher row reorder (Account Settings → bottom) confirmed as real drift.

**Platform story:** iOS and Android are **highly consistent with each other** — almost all drift is shared
our-vs-Figma, not OS splits. The genuine **iOS-vs-Android** inconsistencies worth fixing:
(a) iOS `<Switch>` off-track invisible (`ios_backgroundColor` unset) — `settings-app`;
(b) Flash Attention = Switch on iOS but 3-state segmented on Android — `settings-preferences`;
(c) slider thumb shape (Figma ring vs iOS oval vs Android dot) — `settings-preferences`;
(d) Download-Model button fill (solid iOS vs outlined Android) — `chat-empty-no-model`;
(e) About action-button emphasis — `settings-about`.

**Capture completeness (RESOLVED):** the first device set had failed tab/state-switch captures; round-2
mostly missed due to a worktree→repo mirror lag; **round-3 (after the agent rsynced worktree→repo) landed
all targets** and they are now pixel-verified. No screen remains capture-blocked. (`explore-models-stub` is
an intended disabled stub.) The capture agent now writes directly to the repo path, so no further mirror lag.

> Severity rollup: ~4 reliable BLOCKERs · ~12 CONCERNs · several NITs · 5 screens blocked on re-capture.
> None of the BLOCKERs are platform-split; all are uniform our-vs-Figma reskin gaps.

---

## ⚠️ Capture-quality issues (device side — surfaced before parity verdicts)

The existing device capture set has several **failed tab/state-switch captures** (byte-identical
duplicates) and one mislabel. These limit what can be compared and several screens need re-capture:

| Issue | Affected files | Sets | Impact |
|---|---|---|---|
| Models internal tab switch (Explore↔Ready) did not register | `models-screen-explore-tab` == `models-screen-ready-tab` | iOS-light, Android-light, Android-dark | Explore-tab montage shows the wrong tab → CAPTURE-UNRELIABLE |
| Explore sub-tab switch (Pals↔Models) did not register | `explore-models-stub` == `explore-pals-tab` | all 4 | Models-stub montage shows the Pals tab → CAPTURE-UNRELIABLE |
| My Pals tab switch (Downloaded↔Created) did not register | `my-pals-created-tab` == `my-pals-downloaded` | iOS-dark, Android-light, Android-dark | Created-tab montage shows Downloaded → unreliable (iOS-light may be valid) |
| Create-pal Generation sub-tab unresolved | `create-pal-form-generation__BLOCKED` == `create-pal-form-general` | all 4 | Generation montage device tiles show General → CAPTURE-UNRELIABLE |
| `chat-model-loaded.png` actually shows the **Home** screen (mislabel) | `chat-model-loaded` | all 4 | excluded from this pass |
| Thinking bubble N/A (no reasoning model) | `chat-thinking-bubble__BLOCKED` == `chat-conversation` | all 4 | expected; not montaged |
| `model-settings-sheet__BLOCKED` fell back to Models screen | `__BLOCKED` variant | — | real `model-settings-sheet.png` exists and was used |

**Recommendation:** re-capture the four tab/state-switch screens (Models Explore tab, Explore Models
sub-tab, My Pals Created tab, Create-pal Generation tab) using `waitForExist+click` on the DS Tabs
wrapper (see `learning_redesign_visual_capture_appium`) — the tab testID sits on a wrapper View.

---

## 🔄 Re-capture round 2 — outcome (PARTIAL — supersedes the affected entries below)

A re-capture round was run for the 7 flagged screens. **Verified against actual pixels** at the canonical
path `workflows/stories/redesign-captures/` (captures are gitignored; uniform mtime `00:26:35` = bulk write).
**Only `my-pals-created` fully landed.** The other targets still show the pre-fix failed states at this path
(and `INDEX.md` was not regenerated for `create-pal-form-generation`). This contradicts the capture agent's
"all 7 verified" report for those screens — reported here as observed, not as claimed.

| Screen | Round-2 result (pixel-verified) | Updated verdict |
|---|---|---|
| `my-pals-created` | ✅ landed — "Created by me" tab now shows (Lookie/Pip) | DRIFT (header ruling) else chrome OK |
| `models-screen-ready-tab` | ❌ all 4 sets still show the **Explore** tab, empty "Available to Download" — Ready-to-Use populated cards never shown (even ios/dark) | CAPTURE-UNRELIABLE — re-capture |
| `models-screen-explore-tab` | ❌ still empty Explore (≈dup of ready) | CAPTURE-UNRELIABLE |
| `chat-model-picker` | ❌ still the **Pals** tab (Lookie/Pip), not the Models model-row sheet | **BLOCKER NOT CLEARED** — capture on Models tab |
| `create-pal-form-general` | ❌ still My Pals + AddPalMenu popover — form never reached | CAPTURE-UNRELIABLE |
| `create-pal-form-generation` | ❌ still My Pals + AddPalMenu popover | CAPTURE-UNRELIABLE |
| `explore-models-stub` | ✅ accept — disabled "Models" segment (tap=no-switch by design) | NO-FIGMA-SOURCE / intended disabled stub |

**Corrections / rulings applied this round:**
- ❎ **Models filter-chip "red vs amber" BLOCKER — WITHDRAWN.** On the legible ios/dark Models capture the
  selected "All Models" chip is **amber/tan** (matches Figma `Yellow/Subtle`), NOT red. First pass misread a
  downscaled/empty-tab tile. **Not a defect.**
- ✅ **My-Pals header — PM RULING APPLIED.** Canonical Page Header title = **Inter Medium 18 (sans)**; the
  device **Fraunces serif** title is confirmed **DRIFT to fix**. **POC-9 `what.md` §4a.1 ("serif (Fraunces)
  title 'My Pals'") is a documentation error → flagged for doc-correction.** Applies to my-pals
  downloaded + created. (Back-chevron remains correct.)
- ⚠️ **chat-model-picker BLOCKER stays OPEN** — could not verify against canonical `454:25590`; the capture
  is still on the Pals tab. (The sheet *has* a "Models" tab, so the model rows are likely reachable — the
  switch just wasn't captured.)

**Recommendation for the next capture pass:** the Models internal tab, the in-chat picker's Models tab, and
the create-pal form were **not** successfully captured at this path. Confirm the capture agent writes to
`/Users/aghorbani/codes/pocketpal-dev-team/workflows/stories/redesign-captures/` (not a worktree copy), and
assert on **tab BODY content** (a loaded ModelCard / a visible form field / a model row) before each shot —
not merely that a wrapper testID exists. Several "verified switches" asserted a wrapper that was present
while the body had not changed.

---

## ✅ Re-capture round 3 — FINAL (worktree→repo sync; all targets now landed)

Root cause of round-2's failures: the capture agent wrote to a **worktree** copy
(`worktrees/redesign-captures/...`) while this review reads the **repo** path; an early bulk mirror (00:26)
was stale. The agent rsynced worktree→repo (fresh mtimes 10:57–10:58) and going forward writes directly to
the repo path. Re-montaged + **pixel-verified** — all previously-failed targets now show the correct state.
Final verdicts (these supersede the round-2 "❌" rows):

### models-ready — DRIFT (minor) — _now valid_
- Ready-to-Use tab now populated: `SmolLM2-135M-instruct-Q2_K` card with **Downloaded** badge + **Load**
  button, "All Models" chip **amber** (correct). Parity good.
- [CONCERN] design-drift — **Section grouping**: Figma groups by **model family** ("Llama" header); device
  uses a status header ("Ready to Use"). Grouping axis differs.
- [NIT] device card omits the "Vision Support" badge (model-dependent — SmolLM2 has no vision; likely data, not drift).
- iOS-vs-Android: consistent.

### models-explore — DRIFT (minor) — _now valid_
- Explore tab now populated: downloadable cards (Gemma 3 4B / 4 E4B / 4 E2B / Boreal 8B) with **Download**
  buttons, **Recommended** badges, and **storage Warning** ("You need … GB"). Matches Figma intent; chip amber.
- [CONCERN] design-drift — **Section grouping** by status ("Ready to Use" / "Available to Download") vs Figma
  by **family** ("Llama" / "Gemma"). Same grouping-axis divergence as models-ready.
- iOS-vs-Android: consistent.

### chat-model-picker — CONCERN (downgraded from BLOCKER) — _now shows Models tab_
- The picker's **Models** tab now renders a model row (`SmolLM2-135M-instruct-Q2_K`) — the surface is no
  longer "missing".
- [CONCERN] design-drift / surface-question — the device picker is a **"Pals | Models" segmented sheet**
  (from the Home composer) with **minimal rows** (plain model name); canonical `454:25590` is an
  **"Available Models" modal** with **rich rows** (icon, id, **size**, Unload/Download, **Recommended**,
  **Vision Support**). Either the app simplified the rows (drift) or the captured Home-composer picker is a
  **different surface** than the in-chat `454:25590` sheet. **Design/PM to confirm the surface mapping**
  before filing as drift. No longer a BLOCKER.

### create-pal-general — DRIFT (minor) — _form now reached_
- New-Pal form, General tab: Pal Name / Description / Default Model / World / Location / AI Role (Roleplay
  fields) all present and matching the Roleplay Figma (`787:16481`). General|Generation tab bar = the POC-9
  fold (intended). Field styling parity good.
- [CONCERN] design-drift — header **title copy**: device "New Pal" vs Figma "Create Pal for Roleplay".
- [CONCERN] design-drift — Figma shows a centered **avatar "Upload"** affordance at the top of the form;
  not visible in the device viewport — verify present (may be omitted or scrolled).
- iOS-vs-Android: consistent.

### create-pal-generation — CLEAN (parity-OK) — _Generation tab now reached_
- Generation tab matches intent: **SettingsLevelIndicator "Inherited settings for <pal>" + Reset**,
  **N-Predict** (Unlimited|Custom), Include-Thinking-in-Context toggle, **Temperature** / **Top-P** sliders.
- [NIT] slider **thumb shape** (Figma outlined ring vs device solid oval/dot) — same as `settings-preferences`.
- iOS-vs-Android: consistent.

**Net effect:** the 5 capture-blocked screens are resolved. **Reliable BLOCKERs hold at 3** (home carousel,
home model chip, model-settings footer) — none introduced by the re-captures. `chat-model-picker` is now a
CONCERN/surface-question, not a BLOCKER.

---

## Findings index

| Screen | Figma light / dark | Verdict | Top findings |
|---|---|---|---|
| home | 888:33856 / 3011:25505 | **DRIFT** | pal carousel = circles not rounded image-cards (BLOCKER); two-tone "Model used" chip absent (BLOCKER); attach not boxed / send not gradient (CONCERN) |
| chat-conversation | 139:3792 / 3011:25555 | DRIFT | header subtitle line missing (CONCERN); assistant-bubble bg treatment differs (CONCERN) |
| chat-model-picker | 454:25590 / 3011:25873 | CONCERN (r3) | Models tab now shows a model row; device=Pals\|Models segmented sheet w/ minimal rows vs canonical rich "Available Models" modal → confirm surface mapping (downgraded from BLOCKER) |
| chat-empty-no-model | none (no-model state) | NO-SOURCE | Download-Model button fill differs iOS(solid) vs Android(outlined) (CONCERN) |
| chat-gen-menu | none clean (DS menu) | NO-SOURCE | dark popover surface in light theme looks un-tokenized (CONCERN) |
| models-ready | 477:13944 / 3011:26004 | DRIFT minor (r3 ✅) | Ready-to-Use populated (SmolLM2 card, Load); chip amber OK; CONCERN: section grouping by status vs Figma by family |
| models-explore | 477:20848 / 3011:26085 | DRIFT minor (r3 ✅) | Explore populated (Gemma downloadable cards + Recommended/storage badges); CONCERN: grouping by status vs Figma family |
| model-settings | 771:29912 / 3011:26309 | **DRIFT** | footer "Cancel/Save Changes" vs Figma "Close/Download" (BLOCKER copy); toggle default-state iOS≠Android (CONCERN) |
| explore-pals | 788:18186 / 3011:28062 | DEFERRED (chrome CLEAN) | chrome matches; default sort "Newest" vs Figma "Most Relevant" (CONCERN); pal cards server-gated |
| explore-models-stub | none (deferred stub) | NO-FIGMA-SOURCE (intended disabled stub) | Models segment disabled by design (unreachable by tap = correct); re-shoot to show greyed segment |
| my-pals-downloaded | 787:17312 / 3011:26198 | DRIFT (+DEFERRED) | RULING: header serif = DRIFT (canonical Inter Medium 18 sans; POC-9 doc-fix); back-chevron CORRECT; downloaded list empty=server-gated (ios/light valid; other sets unreliable) |
| my-pals-created | 772:34754(roleplay 787:16481) / 3011:26198 | DRIFT (r2 ✅ landed) | Created tab now shows; header serif=DRIFT (ruling); card simplification (no ★/chips) intended per POC-9 D2 |
| create-pal-general | 787:16481 / 3011:28688 (roleplay) | DRIFT minor (r3 ✅) | form reached; fields match; CONCERN: title "New Pal" vs "Create Pal for Roleplay"; verify avatar Upload affordance |
| create-pal-generation | 772:36034 / 3011:28733 | CLEAN (r3 ✅) | Generation tab matches (Inherited+Reset, N-Predict, Temp/Top-P sliders); NIT slider thumb shape |
| settings-launcher | 787:19024 / 3011:25948 | STATE-MISMATCH (+DRIFT) | device = not-registered variant (expected); launcher row ORDER differs (Account Settings last vs Figma 2nd) (CONCERN) |
| settings-preferences | 771:36287 / 3011:26233 | DRIFT | slider thumb shape Figma-ring vs iOS-oval vs Android-dot (CONCERN); Flash Attention Switch(iOS)≠3-state(Android) (CONCERN) |
| settings-app | 771:36876 / 3011:26211 | DRIFT | iOS Switch off-track invisible — ios_backgroundColor unset (CONCERN); device adds Language/TTS rows (state) |
| settings-about | 771:36058 / 3011:26106 | DRIFT | extra "Become a Sponsor" btn + "Star on GitHub" demoted from filled-primary (CONCERN); "Please"→"please" copy (NIT) |
| search-prompt | 989:234988 / 3011:28870 | CLEAN | overlay placement = our Portal impl; prompt copy/field match |
| search-0-results | 989:235063 / 3011:28943 | DRIFT | typed-query accent-color highlight missing in no-results title (CONCERN) |

## Per-screen detail

### home — DRIFT
- [BLOCKER] design-drift — Pal carousel renders as solid colored circles/avatars with initials, NOT the Figma rounded-18 **image cards** (active border peach `#c58334`, active label `#a86c34`). All device tiles.
- [BLOCKER] design-drift — The two-tone **"Model used" + id + chevron** chip is absent; device shows only the composer placeholder / a flat "Select a model". All tiles.
- [CONCERN] design-drift — Composer **attach** is a plain ghost `+`, not the boxed button (`#f3f2f2` rounded-12 h40). 
- [CONCERN] design-drift — **Send** button is a flat grey square, not the gradient-midnight rounded-8 (opacity-0.4 when empty).
- [CONCERN] design-drift — **Mic** glyph present on iOS, appears missing/different on Android composer — verify.
- [NIT] Title two-line Fraunces 36 and floating peach tab pill render correctly. Empty-hint copy/placement differs slightly from Figma's single subtle line.
- iOS-vs-Android: highly consistent with each other; both diverge from Figma identically (so these are our-vs-Figma bugs, not platform splits).

### chat-conversation — DRIFT
- [CONCERN] design-drift — Header is missing the pal **subtitle/selector line** under the name that Figma shows.
- [CONCERN] design-drift — Assistant message **bubble background** treatment differs from Figma (Figma plain-on-bg vs device grey bubble).
- [NIT] Per-message action bar iconography + time-label treatment more compact than Figma.
- iOS-vs-Android: consistent; divergences are vs-Figma.

### chat-model-picker — CAPTURE/SURFACE MISMATCH (verify on device) — _reconciled_
- Source-reconcile (live `get_metadata` on `454:25590`): the canonical node IS a bottom-sheet **modal
  "Available Models"** (Overlay→Module 373×544, Modal Header + 3 model-row instances). The device tiles
  show a segmented **"Pals | Models" list** with pal entries (Lookie/Pip) — a **different surface**.
- [VERIFY — not a confirmed fix] — Either the capture opened the wrong sheet, or the app's
  `ChatPalModelPickerSheet` uses a Pals|Models segmented design diverging from canonical. **Needs
  on-device verification** before filing as impl drift. Downgraded from BLOCKER to verify-on-device.
- iOS-vs-Android: consistent (both show the same list).

### chat-empty-no-model — NO-SOURCE
- No canonical Figma for the "No Models Available / Download Model" state (DS-derived). 
- [CONCERN] design-drift (iOS-vs-Android) — **Download Model** button: solid pill on iOS vs lighter/outlined on Android.
- Title, illustration, subcopy consistent. Disabled composer chrome = platform-legit.

### chat-gen-menu — NO-SOURCE
- No clean Figma source (the canonical chat menu is a different message-options menu). DS-derived popover.
- [CONCERN] design-drift — Popover **surface is dark-grey even in light mode** on both platforms → looks un-tokenized for the light theme.
- iOS-vs-Android: consistent items (Generation settings / Model[disabled] / Export-Import); minor anchor offset (within OS norms).

### models-ready — DRIFT
- [BLOCKER] design-drift — Filter chip selected state renders **red/orange**, not the Figma **amber/yellow** (`Yellow/Subtle`) fill. All device tiles, reliable regardless of tab.
- [BLOCKER/capture-suspect] design-drift — Populated **ModelCards** (thumbnail/title/size/status badges) are absent; device shows the Explore/empty "Available to Download" list. Likely the capture is on the wrong tab (see capture-quality dup) — re-capture the Ready-to-Use tab to disambiguate impl vs capture.
- [PLATFORM-LEGIT] iOS centered title + back-chevron vs Android left-aligned; overflow placement.
- iOS-vs-Android: consistent (both exhibit the same chip color + content).

### models-explore — DRIFT minor (RESOLVED in round 3 — see "Re-capture round 3 — FINAL")
- _Round-1/2 history:_ device tiles were byte-identical to Ready-to-Use (tab switch / mirror lag) — could not judge.
- _Final (round 3):_ Explore tab now populated (Gemma downloadable cards + Recommended/storage Warning badges, amber chip). CONCERN = section grouping by status vs Figma by family. See round-3 section for the full verdict.

### model-settings — DRIFT
- [BLOCKER] design-drift — Footer buttons are **"Cancel / Save Changes"** on device vs Figma **"Close / Download"** (copy mismatch). All device tiles.
- [CONCERN] design-drift — **"Add Generation Prompt"** toggle reads OFF on iOS-light but ON on Android-dark/Figma — verify default-state parity (possible real bug).
- [CONCERN] design-drift — Confirm **Reset** action is present + right-aligned on iOS.
- Rows (Rename, BOS/EOS/Add-Gen-Prompt, System Prompt, Template preview+Edit, Stop Words) otherwise parity-OK.
- iOS-vs-Android: mostly consistent; the toggle state divergence is the one to confirm.

### explore-pals — DEFERRED (chrome CLEAN)
- Chrome parity GOOD: serif "Explore" header, "Get your pals" promo + "Log in to PalsHub", segmented Pals|Models, filter dropdowns, "Available Pals" header + sort + search icon — all render on both platforms matching Figma.
- [CONCERN] design-drift — Default **sort label "Newest"** on device vs Figma **"Most Relevant"** — verify intended default.
- [NIT] Empty-state copy "No Pals Found" vs Figma end-state "You've reached the end" (distinct states; confirm intended string).
- Pal **cards absent = DEFERRED** (PalsHub 3010 down), not drift.
- iOS-vs-Android: consistent.

### explore-models-stub — NO-FIGMA-SOURCE (intended disabled stub)
- The Explore "Models" segment is an **intentionally disabled "coming soon" stub** (POC-11 deferred-state;
  `ExploreScreen.tsx` `items:[{value:'models',disabled:true}]`, confirmed by the capture agent). It is
  **unreachable by tap by design** — that is correct behavior, not a bug — and there is **no canonical
  Figma** for a Models panel, so there is nothing to montage against.
- Current capture is a byte-dup of the active Pals tab → being replaced with a non-duplicate shot that
  visibly shows the **greyed/disabled Models segment**. Verdict = NO-FIGMA-SOURCE / intended-disabled-stub
  (NOT a parity fail, NOT a real capture defect once the disabled segment is visible).

### my-pals-downloaded — DRIFT (+ DEFERRED content) — _reconciled vs canonical_
- [CONCERN — PM RULED] design-drift — **Header title font.** Source-reconcile (live `get_design_context`
  on header `787:17313`): canonical "My Pals" Page Header title is **Inter Medium 18 (Title/md), SANS**;
  the device renders a **Fraunces serif** title → DRIFT (device over-applied the hero-title serif to a Page
  Header). **PM ruling: canonical wins → fix device to Inter Medium 18; POC-9 `what.md` §4a.1 is a doc error
  to correct.**
- [RESOLVED — not drift] Back chevron: the canonical Page Header **includes** a back-chevron button, so
  the device chevron is **correct**. (First-pass "back-chevron on a tab-root" concern is withdrawn.)
- Card list chrome (single-column, avatar/name/desc/overflow) reskinned and present.
- Downloaded list empty = **DEFERRED** (server-gated), not drift.
- iOS-vs-Android: consistent.

### my-pals-created — DRIFT (re-capture round 2 ✅ landed)
- The "Created by me" tab now renders correctly on all device tiles (Lookie/Pip local pal cards).
- [CONCERN] design-drift — **Header title serif** (per PM ruling): canonical = Inter Medium 18 sans; device = Fraunces serif → fix. (Same finding as my-pals-downloaded.)
- [intended — not drift] Device cards are simplified (no ★rating / no category chips) vs the Figma mock cards. Per **POC-9 decision D2** (local pals have no rating data) this omission is intended, not drift. Device pal data (Lookie/Pip) ≠ Figma mock data (Immeria/Lunabot/etc.) = data, not drift.
- iOS-vs-Android: consistent.

### create-pal-general — DRIFT minor (RESOLVED in round 3 — see "Re-capture round 3 — FINAL")
- _Round-1/2 history:_ device tiles showed the My Pals list + AddPalMenu popover (form never reached) due to the worktree→repo mirror lag.
- _Final (round 3):_ New-Pal form reached; fields match the Roleplay Figma. CONCERN = title "New Pal" vs "Create Pal for Roleplay"; verify the avatar Upload affordance. Full verdict in the round-3 section.

### create-pal-generation — CLEAN (RESOLVED in round 3 — see "Re-capture round 3 — FINAL")
- _Round-1/2 history:_ BLOCKED — showed My Pals + AddPalMenu popover (mirror lag).
- _Final (round 3):_ Generation tab reached; matches intent (Inherited+Reset, N-Predict, Temp/Top-P sliders). NIT = slider thumb shape. Full verdict in the round-3 section.

### search-prompt — CLEAN
- Search field + "Start typing" prompt copy + illustration match Figma. The top-pinned overlay placement is our POC-12 Portal-overlay implementation (vs Figma's mid-screen mock) — acceptable/legit. Keyboard = OS chrome.
- iOS-vs-Android: consistent.

### search-0-results — DRIFT
- [CONCERN] design-drift — The typed-query substring in the no-results title is **not accent-colored** on device (both platforms); Figma renders it in the accent/orange color. Missing per-query highlight.
- [NIT] Device body copy adds "or check your connection," — likely the PalsHub-down branch (PLATFORM-LEGIT if so; confirm).
- "Explore Pals" CTA matches. iOS-vs-Android: consistent.

### settings-launcher — STATE-MISMATCH (+ DRIFT)
- [STATE] Figma is the REGISTERED variant ("Welcome, Sam / Member since 2025" serif header); both devices are NOT-REGISTERED ("Create Account" CTA). Expected per brief — not a defect.
- [CONCERN] design-drift — Launcher **row order** differs: Figma order is My pals · Account Settings · Preferences · Benchmark · Models · App Settings · About App; device pushes **Account Settings to the bottom** (greying = legit not-registered state, but the reorder is independent drift).
- [NIT] design-drift — Figma rows are individual rounded **card containers** with inset margins + subtitle on every row; device rows are flush full-width list rows with thinner separators (card insets less pronounced).
- iOS-vs-Android: consistent (same not-registered layout/order).

### settings-preferences — DRIFT
- [CONCERN] design-drift — **Slider thumb** shape: Figma = hollow **outlined ring** on a thin track; iOS = solid **oval/pill**; Android = solid **round dot**. Neither matches Figma and the two platforms differ from each other.
- [CONCERN] design-drift — **Flash Attention** control type: Switch on iOS (matches Figma) vs **3-state Auto/On/Off segmented** on Android. Cross-platform inconsistency.
- [STATE] Device(Metal/GPU) row: iOS shows Metal/CPU toggle; Android shows "GPU only — no hardware acceleration available" (plausibly legit hardware-capability difference; confirm).
- [NIT] Numeric inputs (Context Size, Seed) boxed — parity OK; Android adds an "Image Max Tokens" row.
- iOS-vs-Android: diverge (Flash Attention control, slider thumb, Device row) — real, not OS chrome.

### settings-app — DRIFT
- [CONCERN] design-drift — **iOS Switch off-state track is nearly invisible** (white-on-white, no border — `ios_backgroundColor` unset). Figma/Android off-track is a visible grey pill. (This is exactly the iOS `<Switch>` polish POC-10a flagged — appears unresolved on device.)
- [STATE] Device adds **Language** and **Text-to-speech** rows beyond Figma's 3 (Dark Mode, Background Download, Display Memory Usage) — device superset, not a parity bug.
- [NIT] design-drift — Subtitle parity inconsistent: iOS keeps row subtitles; Android drops most (e.g. Dark Mode has none).
- iOS-vs-Android: diverge — iOS off-track invisible vs Android visible; Android omits subtitles iOS keeps.

### settings-about — DRIFT
- [CONCERN] design-drift — Action block differs: Figma "Support the Project" = **Star on GitHub (filled primary)** + Or + Share Your Thoughts. Device adds a third **"Become a Sponsor"** button and demotes Star-on-GitHub to outlined/secondary (button-emphasis + extra-element drift).
- [STATE] Device adds a **"Tour / Replay the welcome screens"** block not in Figma.
- [NIT] design-drift — Copy case: Figma "**Please** consider supporting…" vs device "**please** … :" (lowercase + trailing colon).
- [data] Version strings differ (data, not layout) — llama.cpp/version line layout matches.
- iOS-vs-Android: diverge in button emphasis; both add the Tour block consistently.

---

## DEFERRED (PalsHub server 3010 DOWN — our side only; Figma captured for reference)

These surfaces need the 192.168.0.92:3010 PalsHub test server for OUR render (populated discovery).
Figma side was captured where cheap; no montage built (no valid our-side populated state).

- Explore populated discovery (pal cards): Figma `788:18914` (registered) / cards in `788:18186`
- Pal-details sheet/page: Figma `225:19393` (reviews) / `788:17247` (downloaded) / dark `3011:26813`
- Filter / sort sheets: Categories `989:230881`, Price-range `989:230920`
- Search RESULTS (populated): Figma `989:235099` / dark `3011:28978`

(Explore Pals empty chrome, Search prompt, Search 0-results, My Pals empty chrome ARE in scope and
montaged — only the populated/server-backed content is deferred.)
