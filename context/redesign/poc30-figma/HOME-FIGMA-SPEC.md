# Home screen — canonical Figma spec (pixel-parity target)

Source: Figma `RZxDJea4t6jnBZrV4YBacF`, node **888:33822** "Homepage - default". Reference render: `home-default-REF.png` (393×852 @1x). This is the pixel-parity target. Compare LAYOUT / SIZE / SPACING / TYPOGRAPHY / COLOR / RADIUS / SHADOW — not the placeholder content strings (pal names, model id, history titles are mock data).

Device chrome to EXCLUDE from parity (OS-owned, not app UI): the `9:41` status bar + signal/battery (888:33823) and the bottom Home Indicator bar (888:33855). The app uses the real OS status bar / home indicator.

## Token value table (Figma → exact hex/number)

| Figma token | Value |
|---|---|
| Color/Background/Muted (screen bg) | `#fafafa` |
| Color/Background/Card | `#ffffff` |
| Color/Foreground/Primary | `#181715` |
| Color/Foreground/Secondary | `#474747` |
| Color/Foreground/Tertiary | `#81807e` |
| Color/Foreground/Subtle | `#c4c2c0` |
| Color/Muted/Subtle | `#f3f2f2` |
| Color/Secondary/Default | `#f3f2f2` |
| Color/Primary/Foreground | `#fafafa` |
| Color/Border/Light Grey | `#e5e3e1` |
| Color/Border/Strong | `#81807e` |
| Color/Yellow/Accent (active pal border) | `#c58334` |
| Color/Yellow/Highest Contrast (active pal label) | `#a86c34` |
| Color/Yellow/Subtle (active tab pill bg) | `#f5dbbc` |
| Color/Yellow/Mute (active tab pill border) | `#f8f1e2` |
| Color/Midnight/900 / 1500 (send gradient) | `#2a2928` → `#0e0d0c` |
| Spacing: None/XXS/XS/S/SM/M/ML/L/XXL | 0 / 2 / 4 / 8 / 12 / 16 / 20 / 24 / 40 |
| Radius: S/M/ML/XXL | 8 / 12 / 16 / 40 |
| Stroke/xs | 0.5 |
| Font H1 (Fraunces) | size 36, weight 500/Regular, lineHeight ×1.4 (≈50.4px), letterSpacing 0, `fontVariationSettings "SOFT" 0 "WONK" 1` |
| Font Title/sm (Inter Medium) | 16 / lh 22 / ls +0.16 |
| Font Title/xs (Inter Medium) | 14 / lh 20 / ls +0.14 |
| Font Body/md (Inter Regular) | 15 / lh 28 / ls −0.15 |
| Font Caption/sm (Inter Medium) | 11 / lh 18 / ls +0.11 |
| Font Caption/xs (Inter Regular) | 10 / lh 18 / ls +0.10 |
| Effect xs (pal avatar shadow) | drop-shadow 0 2 2 / `#0000001F` (12%) |
| Effect xxs (composer card shadow) | drop-shadow 0 1 2 / `#00000008` (3%) |
| Effect Subtle (tab bar shadow) | drop-shadow 0 2 4 / `#00000014` (8%) |
| history row shadow | drop-shadow 0 1 1 / `rgba(0,0,0,0.03)` |

> Implementer: map each to the nearest existing app theme token (`src/theme/tokens/`). If a needed color (e.g. yellow/accent `#c58334`, yellow/subtle `#f5dbbc`, yellow/mute `#f8f1e2`, yellow/highest-contrast `#a86c34`) has no token, add it to the token module (these are design-system accent values, additive). Never hardcode a raw hex in a screen `styles.ts` — bind a token. Verify the existing `accent.peach` token (`#FCE7CF`) vs Figma's tab pill `#f5dbbc` — they DIFFER; the floating tab pill must be `#f5dbbc` with border `#f8f1e2`.

## Layout (top → bottom), node 888:33822

Frame 393 wide, bg `#fafafa`. Below the OS status bar:

**Body** (888:33824): paddingTop 120 (incl. status-bar zone → in-app use top safe-area inset + remaining ≈ to match the hero sitting low), paddingH 16, flex-col, gap 40 (XXL) between **Content** and **Previous chats**.

### A. Content (888:33825) — flex-1, justify-end (bottom-anchored), gap 24 (L), paddingBottom 40 (XXL)
1. **Title** (888:33826): "Chat" / "with your pals" on **two lines**. Fraunces Regular 36, lineHeight ×1.4, color `#181715`, full width, `fontVariationSettings "SOFT" 0 "WONK" 1`.
2. **Chat items / pal carousel** (888:33827): horizontal row, gap 8 (S). Each **Chat item**: flex-col, gap 2 (XXS), padding pt2/pb4/px4, rounded 18.
   - **Avatar**: **w 48 × h 45.45**, rounded **18**, padding 2, drop-shadow xs (0 2 2 12%), bg `#ffffff`. Inner "Visuals" rounded **16** (ML), `overflow:hidden`, shows the **pal image filling the card** (cover). NOT a circle, NOT an initial — a rounded-rect card with the pal's image.
   - **Active pal**: avatar border **2px `#c58334`**; label color `#a86c34`.
   - **Inactive pal**: no border; label color `#81807e`.
   - **Label**: Inter Medium 11 / lh 18 / center / ls +0.11, 1 line.
   - **Add item** (last): avatar bg `#f3f2f2`, border **2px `#fafafa`**, centered **plus** icon 16; label "Add" `#81807e`.
3. **Composer card** (888:33834 "Bottom nav bar"): bg `#ffffff`, border **0.5px `#e5e3e1`**, rounded **8** (S), drop-shadow xxs (0 1 2 3%), paddingTop 16 / paddingBottom 8, flex-col, items-center, full width.
   - **Text area** (I…764:28532): height ~74, paddingH 16 / paddingV 8. Placeholder "Start messaging with <pal>…": Inter Regular **15** / lh 28 / `#81807e` / ls −0.15, left-aligned, top.
   - **Addon row** (764:28534): paddingH 16 / paddingV 8, justify-between, items-end.
     - **Start addon** = **attach button**: a box bg `#f3f2f2`, border 0.5 `#e5e3e1`, **h 40**, paddingH 12, rounded **12** (M), containing a **plus/attach icon 16**.
     - **End addon**: gap 16, right-aligned —
       - **mic icon** 16 (in a 20px hit box, rounded 8). [currently MISSING in impl]
       - **send button**: **gradient** top→bottom `#2a2928`→`#0e0d0c`, **opacity 0.4** (disabled-empty state), **h 32**, paddingH 8, rounded **8** (S), arrow-up icon 16 `#fafafa`.
4. **Model-used chip row** (888:33835): paddingV/H 8 (p-8), gap 4, justify-center, full width. Three parts inline:
   - "Model used" — Inter **Regular 10** (caption/xs) / `#c4c2c0` (subtle).
   - model id — Inter **Medium 11** / `#81807e` / ellipsis.
   - chevron-down icon **14** (in a small button).

### B. Previous chats (888:33840) — bg `#fafafa`, gap 4 (XS), height ~180 (peek; scrolls in "scrolled-up" variant)
1. **Header** (MainHeader 3011:23736): row, gap 12, paddingV 4. Title "Chat history" Inter Medium **14** (title/xs) / **`#81807e`** (tertiary) / ls +0.14, flex-1. Right: **search icon** button — icon 20 in a 28-high button, rounded 12. [search icon currently MISSING]
2. **Chat item rows** (888:33844…): bg `#ffffff`, drop-shadow (0 1 1 3%), paddingH 16 / paddingV 20 (ML), rounded **8** (S), full width, row, items-start. Left content (flex-1, gap 2):
   - **Title**: Inter Medium **14** (title/xs) / `#181715` / ls +0.14, ellipsis 1 line.
   - **Information** row (gap 4, items-center): pal **avatar 16** (rounded 8, pal image) + pal name Inter Medium 11 `#81807e` + **bullet** "·" + **clock icon 14** + "2d ago" Inter Medium 11 `#81807e`.
   - Right: **more / dots** button — icon 14 (horizontal dots) in a small button. [avatar + clock + dots currently MISSING]

### C. Bottom gradient (888:33853): absolute bottom, height 129, linear-gradient `rgba(250,250,250,0)` → `#fafafa` (fades the history under the tab bar).

### D. Floating tab bar (888:33854 — the DS BottomNavBar `floating` variant): absolute, centered, bottom 33. Container: bg `#ffffff`, drop-shadow Subtle (0 2 4 8%? — actually `0 2 2 rgba(0,0,0,0.08)`), height 48, paddingH 4 / paddingV 2, rounded **40** (XXL). Three tabs, each w 102 / h 40 / px 10 / py 8 / rounded 40, gap 4:
- **Chats (active)**: bg **`#f5dbbc`** (yellow/subtle), border **0.6px `#f8f1e2`** (yellow/mute), message-circle icon 16 + "Chats" Inter Medium 14 `#181715`.
- **Explore**: compass icon 16 + "Explore" Inter Medium 14 `#474747` (secondary).
- **Settings**: settings icon 14 + "Settings" Inter Medium 14 `#474747`.

## Known current-impl discrepancies (starting point — non-exhaustive; reviewer is the authority)
- Pal avatars are circles (radius xxl) with initials; must be **rounded-18 image cards (48×45.45)**, inner radius 16, drop-shadow, active border `#c58334`.
- Composer: missing **mic** icon; attach is a bare icon, must be a **boxed button** (`#f3f2f2`, border, rounded-12, h40); send is solid primary square, must be **gradient midnight, rounded-8, h32, opacity-0.4-when-empty**; placeholder font/spacing per body/md.
- Model chip: must be the **"Model used" + id + chevron** row (two-tone), positioned per spec (inside the content block), not a separate rounded chip.
- History header: missing the **search icon**; title color must be tertiary `#81807e`.
- History rows: missing **pal avatar (16)**, **clock icon**, **"·" bullet**, **dots/more button**; must be a **white card** (rounded-8, shadow, px16/py20).
- Layout: hero content is **bottom-anchored** (Content flex-1 justify-end) with history peeking + bottom gradient + floating tab bar — current impl is a plain top-anchored scroll.
- Title must be **two lines** Fraunces 36 / lh ×1.4.
- Tab pill color `#FCE7CF` → must be `#f5dbbc` (border `#f8f1e2`).

---

## First-time-user / EMPTY state (node 888:33856)

When there are NO chat sessions, the "Previous chats" region (888:33874) is NOT the history list and NOT bottom-pinned text. It is a centered empty-state block:
- Region: bg #fafafa, height ~212, flex-col, **items-center + justify-center** (vertically + horizontally centered), sits in normal flow below the model-chip (after the Content hero block + its gap).
- Header (888:33875): flex-col, gap 8 (S), items-center/justify-center, px 8.
  1. **Chat-bubble icon** (888:33876): a speech/chat-bubble outline icon **20px**, inside a 28-high button (padding 2, radius 12 M). Color ~ subtle grey.
  2. **Message** (888:33877): Body/sm = Inter Regular **13px / lineHeight 20 / letterSpacing +0.195**, color **#c4c2c0 (foreground/subtle)**, **text-center**. Copy: "Select a pal or model, then start typing. Your conversations will appear here." (the app already uses this copy — keep it).
- So: centered chat-bubble icon ABOVE a centered subtle-grey 13px message. NOT bottom-pinned, NOT occluded by the tab bar.

Note: the populated default (888:33822) and the empty first-time (888:33856) share the same hero (title/carousel/composer/model-chip); they differ ONLY in the lower region (history rows vs centered icon+message). The app must render the centered empty block when `sessions.length === 0`.
