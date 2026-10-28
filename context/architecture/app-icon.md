# App icon (pending PR)

## Purpose

The launcher icon on Android and iOS: three SVG sources, one generator, and the committed outputs it writes. Not covered: in-app logos and store metadata, including the Play listing icon (`fastlane/metadata/android/en-US/images/icon.png`), which the generator does not write. Native build and payload concerns are in `release.md`.

## Code map

| Path | Role |
| --- | --- |
| `scripts/app-icon/foreground-light.svg`, `foreground-dark.svg`, `monochrome.svg` | sources on the 108 dp adaptive canvas, in Figma units |
| `scripts/generate-app-icons.js` | the only writer of every output below; `parseSvg`, `toVectorDrawable`, `buildTextOutputs`, `generate` |
| `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher{,_round}.xml` | adaptive icon: background colour, foreground, monochrome |
| `android/app/src/main/res/drawable/ic_launcher_{foreground,monochrome}.xml`, `values/ic_launcher_background.xml` | VectorDrawable layers and the plate colour |
| `android/app/src/main/res/mipmap-{m,h,xh,xxh,xxxh}dpi/ic_launcher{,_round}.png` | legacy icons for API 24-25 |
| `ios/PocketPal/Images.xcassets/AppIcon.appiconset/` | single-size set: `AppIcon.png` (any), `-dark`, `-tinted`, all 1024 |
| `android/app/src/main/AndroidManifest.xml` | `android:icon` / `android:roundIcon` |

## How it works

Edit a source, run `yarn icons:generate`, commit both. The generator parses all sources and builds every output before writing any, then deletes any other appiconset file. Text outputs are pure functions of the sources; PNGs come from `@resvg/resvg-js` (dev dependency, loaded only to rasterize). `--preview <dir>` writes full-canvas and themed/tinted previews outside the repo.

## Contracts and invariants

- Canvas `viewBox -28 -28 168 168`; its central `[0,112]²` is the 72 dp viewport: the Figma frame and the iOS icon. Inside it, the foreground is Figma path data verbatim.
- Sources use only the subset that maps 1:1 onto a VectorDrawable (`path`, `g` with one translate/rotate/scale and an optional `clip-path`, clips only as one-path `clipPath` in `defs`, explicit `fill`). Anything else fails the run, naming it.
- The pal (body, band, face, highlights) sits in one `<g id="pal">` per source and inside the 66 dp safe circle; only rim, pocket, road and pocket edge cross it.
- Both manifest names resolve on every API level: `anydpi-v26` XML on 26+, density PNGs on 24-25.
- No output is hand-edited. The iOS any-appearance 1024 (App Store icon) has no alpha.
- Android has no dark icon; `foreground-dark.svg` feeds iOS only.

## Traps and decisions

- The bleed (outside the viewport) shows during launcher parallax. It holds only end-tangent continuations of rim, pocket and road; Figma's off-frame dash runs at `122.94` are dropped, or they would surface as a second road.
- The eye stadiums, monochrome holes, pal clip, pocket-edge gap and bleed are hand-computed path data. Figma holds none of it until the sources are pushed back.
- Themed icons exist on Android 13+ only; iOS dark and tinted only on 18+. The Android 12+ splash shows the adaptive icon.
- `Contents.json` is serialized as Xcode writes it, so opening Xcode leaves no diff.

## Verification

`scripts/__tests__/generate-app-icons.test.js`: parser, VD mapping, freshness of every output (PNGs by decoded pixels with a small tolerance, so arm64 and x64 agree), PNG sizes and colour type, opaque-pixel and `--preview` guards, safe circle. Idempotence: `yarn icons:generate` twice leaves `git status` clean. APK: `aapt2 dump resources` shows both mipmap names with `anydpi-v26` plus five densities. On device: themed icons off and on, drawer, splash; iOS home in light, dark, tinted.
