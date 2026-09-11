# Release — the Android native build and the shipped payload

## Purpose

How PocketPal's Android artifacts get their llama.rn native payload (build mode, compiled variants, the Hexagon/NPU backend), and the payload gate that must pass before any Android artifact is uploaded. Not covered yet: signing, version bumping, TestFlight and Play metadata. iOS is out of scope, because it vendors the prebuilt `ios/rnllama.xcframework`. `model-loading.md` owns runtime Hexagon device selection ("Contracts and invariants", "Hexagon resolution") and the llama.rn version rationale ("Traps and decisions").

**Not on `main` yet:** open PR #869 adds publish-ordering tests, 16 KB alignment checks, and top-level payload assets. The previous version of this doc described them (`git show 1ad6ce1:context/architecture/release.md`); distill them back in when it lands.

## Code map

| Path | Role |
| --- | --- |
| `scripts/android-payload-manifest.json` | The one declaration of what an artifact must contain, per ABI: `requiredLibs`, `requiredAssets` + `requiredAssetElfMachine`, `requiredSymbols` (`lib` + `mustExport`). |
| `scripts/verify-android-payload.js` | The payload gate. `loadManifest` enforces the manifest floors, `checkArtifact` checks an APK/AAB, and `readDynsym`/`readElfMachine` read ELF in-process. `--print-variants` emits the gradle allowlist. |
| `scripts/__tests__/verify-android-payload.test.js` | Gate behaviour on synthetic APK/AAB fixtures. |
| `scripts/__tests__/android-ladder-coverage.test.js` | Ties the manifest to llama.rn's CMake call sites and `RNLlama.java` (`NAMED_BETS`, the DSP asset list). |
| `scripts/__tests__/hexagon-sdk-coverage.test.js` | Ties the SDK digest's consumed paths to what llama.rn's CMake references. |
| `.github/actions/setup-hexagon-sdk/action.yml` | Provisions, verifies and caches the SDK, and exports `HEXAGON_SDK_ROOT`/`HEXAGON_TOOLS_ROOT`. The only home of the SDK version and both digests. |
| `.github/actions/setup-ccache/action.yml` | ccache for `ci.yml` only. |
| `.github/workflows/release.yml` (`build_android`) | Release path: bump, `build_android_release`, allowlist check, gate on APK + AAB, `upload_android_alpha`, tag push, GitHub Release. |
| `.github/workflows/ci.yml` (`build-android`) | Gated `assembleProdRelease`, then the DCE check, then the APK upload. Skipped for translation-only changes. |
| `.github/workflows/e2e-tests.yml` (`build-android`) | Gated `assembleE2eReleaseE2e`, with the same SDK and allowlist as release. |
| `android/fastlane/Fastfile` | `build_android_release` (assemble + bundle, prod flavor) and `upload_android_alpha` (Play, explicit `aab:`). |
| `android/app/build.gradle` | `abiFilters`, the `prod`/`e2e` flavors, `variantFilter`, and `enableProguardInReleaseBuilds = false`. |
| `android/gradle.properties` | `reactNativeArchitectures`. Must **not** carry `rnllamaBuildFromSource`. |
| `scripts/postinstall.sh` | Clones the OpenCL headers that the from-source OpenCL variant compiles against. |

Upstream, under `node_modules/llama.rn/` after `yarn install`:

| Path | Role |
| --- | --- |
| `android/gradle.properties` | `rnllamaBuildFromSource=true` |
| `android/build.gradle` | `findProperty` for the mode and `rnllamaVariants`, `hexagonPresent`, the `Building rnllama variants:` println, `syncRNLlamaHtpAssets`; blanks `jniLibs.srcDirs` from source. |
| `android/src/main/rnllama/CMakeLists.txt` | `build_rnllama_library` call sites, `_hexagon`/`_opencl` name matching, and `HEXAGON_SDK_AVAILABLE` |
| `android/src/main/CMakeLists.txt` | `build_rnllama_jni` call sites (the wrappers the ladder loads) |
| `android/src/main/cmake/rnllama-build-options.cmake` | `rnllama_variant_enabled`. An empty list means build all variants. |
| `android/src/main/java/com/rnllama/RNLlama.java` | `loadNative` (the ladder), `HTP_LIBS`/`ensureHtpLibraries`, `isHexagonSupported` |

## How it works

1. Each Android building job sets `ORG_GRADLE_PROJECT_rnllamaBuildFromSource: 'true'` in its job `env`. Its build step fails unless the value is exactly `true`.
2. `--print-variants` exports `ORG_GRADLE_PROJECT_rnllamaVariants`. llama.rn's gradle passes it on as `-DRNLLAMA_ANDROID_VARIANTS`, and `rnllama_variant_enabled` gates each library and its JNI wrapper.
3. `setup-hexagon-sdk` provisions the SDK. Gradle passes the SDK roots only if both directories exist. CMake compiles the backend into `rnllama_v8_2_dotprod_i8mm_hexagon_opencl` only if `libcdsprpc.so` exists as well.
4. `syncRNLlamaHtpAssets` copies `bin/arm64-v8a/libggml-htp-v{73,75,79,81}.so` into the app's `assets/ggml-hexagon/` (gitignored).
5. The build is teed to `android/android-build.log`. A later step greps that log for `Building rnllama variants: <list>`.
6. "Verify the Android payload" runs the gate on the exact paths uploaded next. `payload-report.txt` uploads under `if: always()`.
7. Release only: `upload_android_alpha` runs, then `git push origin "v$VERSION"` (the tag was created at the bump), then `softprops/action-gh-release` attaches the APK.
8. At runtime, `RNLlama.loadNative` extracts the HTP libs and walks the ladder: hexagon_opencl → dotprod_i8mm → dotprod → i8mm → v8_2 → v8 (rungs 1–6, or x86_64), falling back to the generic `rnllama_jni` (rung 7). It then loads `rnllama` unconditionally.

## Contracts and invariants

- **Build mode is declared, never detected.** All three building jobs set `ORG_GRADLE_PROJECT_rnllamaBuildFromSource` at job level. No workflow infers the mode from `package.json`, a ref, or a file.
- **The manifest is the allowlist.** `variantsFromManifest` drops the wrappers, strips `lib`/`.so`, dedupes, and emits bare names (`rnllama_variant_enabled` matches names). An empty allowlist is refused, because CMake reads empty as "build all".
- **Every rung the ladder can select is built,** except the named bets in `NAMED_BETS`, each of which states its fall-through rung. Enforced by `android-ladder-coverage.test.js`. Today that is 6 of the 7 arm64 variants (the generic `rnllama` included), plus `rnllama_x86_64`.
- **`librnllama.so` is required in every ABI.** `System.loadLibrary("rnllama")` runs outside the ladder, and an `UnsatisfiedLinkError` there disables the module.
- **Backend presence is decided from `.dynsym` only.** `lm_ggml_backend_hexagon_reg` and `lm_ggml_backend_is_hexagon` must be *defined* (`st_shndx != SHN_UNDEF`) in the hexagon variant. No symbol count is declared. Not `strings` or file size: `strings` false-positives on `codec_*_ht` symbols, and backend-less and sound builds have identical `opencl` string counts. The APK that shipped issue #858 carried all 12 libraries and all 4 DSP assets, so this rule is the only one that would have failed it.
- **The four DSP assets are required as a set, each an `EM_QDSP6` (164) ELF.** `ensureHtpLibraries` stops at the first asset it cannot extract, which disables the backend. The manifest list must equal `HTP_LIBS` (ladder test).
- **Instrument honesty.** An unreadable archive, library, section table or `.dynsym`, or an unwritable `--report`, fails the gate. It never passes by absence.
- **Every manifest list has a floor** (`loadManifest`):
  - non-empty `abis` and `requiredLibs`;
  - at least one symbol rule;
  - at least one ABI with a non-wrapper `_hexagon` library;
  - per accelerator ABI: a symbol rule on that library itself (not its `librnllama_jni…` wrapper), non-empty `requiredAssets`, and an integer `requiredAssetElfMachine`.

  `parseArgs` refuses a repeated flag, and refuses `--print-variants` given with an artifact.
- **An undeclared ABI tree fails** (the `UNDECLARED` branch of `checkArtifact`). Extra `librnllama*` variants in a declared ABI are reported and permitted.
- **AAB entries sit under `base/`.** `release.yml` gates both the APK (GitHub Release) and the AAB (Play). `ci.yml` and `e2e-tests.yml` gate only the APK.
- **The gate runs before every upload in its job and names the same paths.** The lane split means no lane both builds and uploads. On main this ordering is held by review, not by a test.
- **The `aab:` in `upload_android_alpha` must match the gate's `--aab` in `release.yml`.** It is one path written twice. On a fresh runner a mismatch fails closed.
- **Test builds may add instrumentation, never subtract capability.** `e2e-tests.yml` provisions the SDK, applies the allowlist and runs the gate exactly as release does.
- **The SDK version and digests live only in `setup-hexagon-sdk`.** The tarball digest is checked on download, and the consumed-subset digest on every run, cache hits included. Bump them together. `hexagon-sdk-coverage.test.js` keeps the subset aligned with CMake.

## Traps and decisions

- **The root `android/gradle.properties` is not a lever.** A subproject's own `gradle.properties` beats the root's (measured on Gradle 9.0.0). Only `ORG_GRADLE_PROJECT_…`, `-P`, or a `$GRADLE_USER_HOME/gradle.properties` override llama.rn's value. The last is live: `release.yml`'s build step points `GRADLE_USER_HOME` at `runner.temp`.
- **Every way of losing the backend is silent.** A missing SDK directory only prints a line, a missing `libcdsprpc.so` is a CMake `WARNING`, and missing DSP sources make the sync task skip. The build succeeds each time. This shipped once (issue #858), which is why the check sits on the artifact.
- **`build.gradle` defaults `HEXAGON_SDK_ROOT` to `~/.hexagon-sdk/6.4.0.2`.** Local builds therefore include or omit the backend depending on whether that directory exists. Run the gate locally to find out which you got.
- **A macOS host can build the backend.** The SDK is `amd64-lnx`, but nothing on the Android path invokes `hexagon-clang`: the QAIC stubs and DSP payloads ship prebuilt in llama.rn.
- **Why the rule names Hexagon, not OpenCL.** OpenCL's sources and `-DLM_GGML_USE_OPENCL` sit outside the `libOpenCL.so` stub guard, so a missing stub fails at link time. Hexagon's sources sit inside their guard.
- **Rung 6 (`rnllama_v8`) is not a duplicate of rung 7 (`rnllama`),** even though both are armv8-a. Non-generic arches add `ggml-cpu/arch/arm/quants.c` and `repack.cpp`, and generic compiles with `-DLM_GGML_CPU_GENERIC`. Dropping rung 6 silently demotes pre-fp16 devices to portable C.
- **`rnllama_v8_2_dotprod_i8mm` and the hexagon variant share arch and flags.** They differ only in name-matched sources and macros, so an "(arch, flags) equal ⇒ covered" predicate would license dropping the hexagon variant.
- **`v8_2_i8mm` is the one dropped rung, a costed bet:** no shipping SoC is known to report i8mm without dotprod. Upstream's 3-variant CI list is unsafe to copy, because it demotes every non-Snapdragon arm64 device to generic.
- **The allowlist grep proves the env route only because `rnllamaVariants` is defined in no properties file.** Adding it to one keeps the grep green while it proves nothing. Its literal is upstream's println: after a rewording, update the literal. The mode has no log proof (upstream's `true` matches ours; the CMake status line vanishes on a warm `.cxx`), so the build step asserts the env value.
- **The lanes are split so the gate is a workflow step between them.** A Gradle task on assemble/bundle cannot gate an upload in a second fastlane process.
- **Without an explicit `aab:`, the upload lane goes green having uploaded no binary.** Supply reads `lane_context`, which exists only in the build process, and its fallback globs miss the flavored path.
- **`print_command: false` on both `gradle(...)` calls.** Fastlane's command echo leaked the signing passwords into `android-build.log`.
- **The tag is pushed after the upload,** so a failed gate leaves only the pushed bump commit behind.
- **The escape hatch is `./gradlew <task> -PrnllamaBuildFromSource=false`.** Use the `-P` form, which upstream's CI also documents. It is not the default: the JNI wrapper, built from the tarball's headers, links against a prebuilt from another snapshot, and struct-layout drift would not surface.
- **`RNLLAMA_SKIP_POSTINSTALL=1` (release, e2e) is safe only when building from source.** In prebuilt mode the missing `jniLibs` makes the JNI CMake "Skip … no prebuilt" and drop variants, which the gate catches. The DSP assets under `bin/` are tarball content and arrive regardless. `ci.yml` does not set it, because its `node_modules` cache is shared with `build-and-test`.
- **Consume npm releases, not llama.rn git refs.** A git install lacks `bin/`, `htp/v73` (CMake `FATAL_ERROR` once the SDK is present), `jniLibs` and `lib/`, so supporting it would take a second native build pipeline.
- **No ccache on the release path.** Its SHA key never hits a fresh bump commit, so only the prefix restore could hit, linking objects of unreviewed provenance into the shipped binary. The `.cxx` cache is `ci.yml`-only, because only there are `node_modules` mtimes preserved. ccache itself needs `CCACHE_COMPILERCHECK=content` plus the sloppiness list: the NDK is reinstalled per run, and at the defaults every lookup misses, which looks like a cold cache.
- **GitHub caps caches at 10 GB per repo, and eviction is invisible** (`setup-java`'s gradle cache is the largest consumer): an evicted SDK or ccache entry shows only as a slow run.
- **The DSP assets also reach x86_64 (~2.8 MB).** `assets/` is packaged once per artifact, and no supported mechanism scopes it by ABI. Accepted.
- **The gate and the DCE check stay separate:** one asserts that the full payload is present, the other that prod carries no automation code. Release runs no DCE check.
- **Where manifest hardening stops.** The script can require that a rule demand presence, not that the demand is meaningful (a rule re-pointed at `librnllama.so` passes). Past the floors, the control is a reviewed manifest diff: add floors, not hardcoded semantics.
- **Enabling release minify needs a `-keep class com.rnllama.**` rule.** None exists.
- **The gate proves presence, not engagement.** `isHexagonSupported()` gates the backend at runtime on SoC hints, and no emulator has a DSP.

## Verification

- `yarn test scripts/__tests__/verify-android-payload.test.js android-ladder-coverage hexagon-sdk-coverage`. The latter two read `node_modules/llama.rn`, so run them after `yarn install`.
- Local gate: `node scripts/verify-android-payload.js --apk android/app/build/outputs/apk/prod/release/app-prod-release.apk`, plus `--aab android/app/build/outputs/bundle/prodRelease/app-prod-release.aab` for a bundle. A conforming artifact shows 12 arm64 + 4 x86_64 `librnllama*` libraries, 4 assets, and both symbols `present`. A backend-less build passes every row except the two `MISSING` symbols.
- If `readDynsym` changes, re-calibrate it against the NDK's `llvm-nm -D` on both a backend-less and a sound artifact.
- On a llama.rn upgrade, re-check the println wording, the 8 + 8 call sites (the ladder test's vacuity guard), `HTP_LIBS`, and the SDK paths CMake references.
- `release.yml` publishes and cannot be rehearsed: verify lane, `aab:` and step-order changes by reading, then watch the next release. To see the backend engage before release, run an `e2e-tests.yml` APK on a Snapdragon 8-series fleet device.
- `ci.yml` `build-android`: about 44 min cold, 23 min warm. A warm run near cold means the caches missed.
