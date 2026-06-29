# Source-reconcile checks (live Figma re-verification of ambiguous findings)

Done with live `get_design_context` / `get_metadata` on the canonical file `RZxDJea4t6jnBZrV4YBacF`.

## 1. My Pals header (node 787:17313 "Header", Page Header instance 3011:23150) — RESOLVED

Canonical design context (verbatim from get_design_context):
- Title **"My Pals"** is `font-['Inter:Medium']`, **Title/md = 18/26, weight 500** — i.e. **Inter Medium 18, SANS**. NOT Fraunces serif.
- A **back-chevron button IS present** at the start of the header (`I3011:23150;3011:23077`, a 16px stroke chevron) — so a back affordance is part of the canonical Page Header.
- Trailing **"+ Create Pal"** button (Caption/sm 11, plus icon) — confirmed.
- Tab bar **"Downloaded | Created by me"**, active tab = `Created by me` with **Yellow/Strong `#eab06c` 1.5px underline**.

**Verdicts (corrections to first-pass report):**
- **Back chevron = CORRECT, not drift.** The first-pass montage's Figma tile read as "no chevron"; the canonical Page Header DOES include it. Drop the "back-chevron on a tab-root" concern.
- **Header title font = REAL DRIFT (CONCERN).** Canonical = **Inter Medium 18 (sans)**; device renders a **Fraunces serif** title. The device over-applied the serif hero-title treatment to a Page Header.
  - ⚠️ Conflict to adjudicate: POC-9 `what.md` §4a.1 says "serif (Fraunces) title 'My Pals'". The canonical Page Header component disagrees (Inter Medium 18). Per the parity brief, **Figma is the single source of truth → the serif title is drift**. PM to decide whether to (a) fix device to Inter Medium 18, or (b) update the canonical Figma if serif was the intended later decision. Serif is correct for the **Home hero** ("Chat with your pals" = Fraunces 36), but the My Pals **Page Header** is Inter Medium 18.

## 2. chat-model-picker (node 454:25590 "Models") — RESOLVED (capture/surface mismatch confirmed)

Canonical metadata: `454:25590` is the in-chat picker = an **Overlay → Module (373×544 bottom sheet)** containing a **Modal Header** + a Container with **3 "Models" row instances** (`772:33629/30/31`). So the canonical surface is a **bottom-sheet modal "Available Models" with model rows** (id/size/state/badges).

Device capture (`chat-model-picker.png`) instead shows a **segmented "Pals | Models" list** with pal entries (Lookie/Pip). That is a different surface (a pal/model chooser), not the model-row modal.

**Verdict:** the BLOCKER from the first pass is a **capture/surface mismatch, NOT confirmed impl drift.** Either the capture opened the wrong sheet, or the app's `ChatPalModelPickerSheet` genuinely uses a Pals|Models segmented design that diverges from canonical. **Needs on-device verification** (open the in-chat model picker and compare to 454:25590). Add to the re-verify list (not a confirmed fix item yet).

## 3. Settings launcher row order (already read from light render 787:19024) — CONFIRMED

Canonical registered launcher order: My pals · Account Settings · Preferences · Benchmark · Models ·
App Settings · About App. Device (not-registered) pushes **Account Settings to the bottom** (greyed =
legit not-registered state; the **reorder** is real drift, independent of state). Stands as a CONCERN.
