# Figma SVG export: normalising for RN

Read from `skills/figma-implement/SKILL.md` (Step 2) whenever you save a Figma SVG into the repo.

When you save a Figma SVG asset into the repo, normalise it before committing:

1. **Strip CSS variables, then immediately decide the colour** (steps 1 and 2 are one operation — do not stop after 1). `react-native-svg-transformer` doesn't parse `fill="var(--fill-0, #181715)"` — the icon renders transparent — so the mechanical fix is to drop in the hex fallback. **That fix is also how the dark-mode bug gets born.** Verify with `grep -l 'var(' src/assets/icons/*.svg` returning nothing, then go straight to 2.

2. **Colour: `currentColor` unless the icon is genuinely one colour forever.** A baked hex does not react to theme switches, and — this is the part that bites — **passing `fill=` or `stroke=` at the call site will NOT override it.** `.svgrrc`'s `replaceAttrValues` rewrites only a fixed list of hexes (today `#333333`, `#858585`, `#FF653F`) into `{props.fill}`. Any other hex stays literal in the generated component, the path defines its own paint, and it therefore does not inherit from the root `Svg` either. The call site looks correct and does nothing.
   - **Themed icon** → set the path to `fill="currentColor"` (or `stroke="currentColor"`) and pass `color={theme.colors.<token>}` at the call site.
   - **Icon whose hex happens to be in `replaceAttrValues`** → it already binds to `{props.fill}`; note that a stroke-only icon binds its *stroke* to the `fill` prop, so passing `fill="none"` paints nothing and omitting `fill` is what yields the outline.
   - **Deliberately multicolour brand mark** (e.g. `GoogleIcon`) → leave the hexes and pass no colour. Say so in the spec table so a reviewer doesn't "fix" it.

3. **`preserveAspectRatio="none"` warning**: Figma exports set this so the icon stretches to its container. If you pass non-proportional `width`/`height`, the path distorts. Either pass dims proportional to the viewBox, OR remove the attribute to keep aspect locked.

**Why this needs care: nothing catches it.** The raw-hex ESLint ban covers `src/components/ui/**/styles.ts` only — it does not scan `src/assets/icons/*.svg`, and the token-invariant test polices which files *read* tokens, not which files *bypass* them. A baked hex passes typecheck, lint, the full Jest suite and both invariant suites. It is also invisible in light mode, because the exported hex is usually a near-black that looks right on a light surface — it only shows as a near-invisible glyph on the dark-mode container. Assume your gates will not tell you; check dark mode yourself.

Verify each asset visually before committing: open in Preview, confirm it renders crisp at the target size; then run a screen capture **in both light and dark** to confirm it actually shows up in the app.
