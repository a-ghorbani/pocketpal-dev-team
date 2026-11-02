# Per-component spec table and defect map

Read from `skills/figma-implement/SKILL.md` (Step 3.5) when writing the table.

For every component (NEW or modified) emit a table in the story doc BEFORE writing the component code, then re-verify after coding. The table forces an explicit Figma → code mapping for the properties most likely to drift: dimensions, colour fills, border widths/colours, radii, padding, sub-icon sizes.

Format:

```markdown
### Component: <name>  (Figma node `<id>`)

| Property         | Figma value                          | Code value                  | Status |
|------------------|--------------------------------------|-----------------------------|--------|
| container size   | 48×48                                | width: 48, height: 48       | ✓      |
| bg               | `Color/Secondary/Default` `#f3f2f2`  | theme.colors.secondaryDefault | ✓      |
| border           | 0.5px `Color/Border/Light-grey` `#e5e3e1` | theme.stroke.sm + theme.colors.mutedLight | ✓ |
| corner radius    | `Radius/ml` 16                       | theme.radius.ml             | ✓      |
| chevron asset    | `chevron-left lg` (746:26300)        | ChevronLeftLgIcon           | ✓      |
| chevron display  | 6.5×11.5 (viewBox native)            | width: 6.5, height: 11.5    | ✓      |
```

Rules:

- Every Figma property the visual depends on must appear. If a property is missing from the table, you don't know what Figma says — pull it before guessing.
- "Status" is one of `✓` (matches), `≈` (close enough by design — note why), `✗` (deviation — must justify under deferred items in `designer-asks.md`).
- If you find yourself writing a literal value (`borderColor: '#some-hex'`) in code, the corresponding token binding belongs in this table; if the token doesn't exist yet, that's a design-token follow-up.

This table is the single mechanical check that catches the class of bug where the implementer mapped Figma `Color/Secondary/Default` to RN `secondaryContainer` because "the names sound similar" — without verifying the hex values match. The check costs ~2 minutes per component and finds these mismatches every time.

## Defects this skill prevents

- "Wireframe ships instead of design" (no Step 4 captures → caught by reviewer).
- "Silently dropped Figma children" (Step 1 metadata walk → Step 5 reviewer coverage check).
- "Raw hex in screen styles" (Step 3 tokens-only → reviewer grep).
- "Blurry raster icons" (Step 2 vector-first → reviewer eyeball).
- "x=137 shipped as `left: 137`" (Step 3 decode → reviewer responsive check).
- "Wrong token because the names sounded similar" (Step 3.5 per-component table — Figma hex side-by-side with the resolved theme token).
- "Hand-coded chevron at the wrong dimensions" (Step 2 prefers exported DS icons over hand-drawn SVGs; Step 3.5 captures the asset choice + dimensions).
- "Icon ships transparent because Figma SVG used a CSS var" (Step 2 normalisation requires stripping `var(...)` fills on import).
