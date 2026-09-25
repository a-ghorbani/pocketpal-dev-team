# Release — the Android native build and the shipped payload

## Purpose

How PocketPal's Android artifacts get their llama.rn native payload (build mode, compiled variants, the Hexagon/NPU backend), and the payload gate that runs before any Android artifact is uploaded. What the gate checks is enforced by its script and fails loudly; this doc holds what CI cannot tell you. Not covered: signing, version bumping, TestFlight and Play metadata, and iOS (it vendors the prebuilt `ios/rnllama.xcframework`). `model-loading.md` owns runtime Hexagon device selection and the llama.rn version rationale.

**Not on `main` yet:** open PR #869 adds publish-ordering tests, 16 KB alignment checks, and top-level payload assets. The previous version of this doc described them (`git show 1ad6ce1:context/architecture/release.md`); distill them back in when it lands.

## Code map

| Path | Role |
| --- | --- |
| `scripts/android-payload-manifest.json` | What an artifact must contain, per ABI (libs, DSP assets, required symbols). Also the source of the gradle variant allowlist. |
| `scripts/verify-android-payload.js` | The payload gate; `--print-variants` emits the allowlist. |
| `scripts/__tests__/` | `verify-android-payload`, `android-ladder-coverage` (manifest vs llama.rn's CMake and `RNLlama.java`), `hexagon-sdk-coverage` (SDK digest vs CMake). |
| `.github/actions/setup-hexagon-sdk/action.yml` | Provisions and verifies the SDK. The only home of its version and both digests. |
| `.github/workflows/{release,ci,e2e-tests}.yml` | The three Android building jobs; each gates the artifact it uploads. |
| `android/fastlane/Fastfile` | `build_android_release` and `upload_android_alpha` (explicit `aab:`). |
| `android/app/build.gradle`, `android/gradle.properties` | ABI filters, flavors; the root properties file must not carry `rnllamaBuildFromSource`. No Play Billing pin: Billing (9.x) arrives through `react-native-iap`'s `openiap-google`. |
| `node_modules/llama.rn/android/` | Upstream: its own `gradle.properties` (`rnllamaBuildFromSource=true`), `build.gradle` (mode, variants, `syncRNLlamaHtpAssets`), CMake variant list, and `RNLlama.java` (the load ladder, `HTP_LIBS`, `isHexagonSupported`). |
| `node_modules/llama.rn/{cmake,vendor}/` | Upstream: `cmake/rnllama-sources.cmake` (source lists) and `vendor/llama.cpp`, unrenamed upstream llama.cpp pinned in `vendor/VERSIONS`. |

## How it works

1. Each Android building job sets `ORG_GRADLE_PROJECT_rnllamaBuildFromSource: 'true'` and exports the manifest's variant allowlist as `ORG_GRADLE_PROJECT_rnllamaVariants`. llama.cpp compiles from source.
2. `setup-hexagon-sdk` provisions the SDK. The Hexagon backend compiles into `rnllama_v8_2_dotprod_i8mm_hexagon_opencl` only when the SDK roots and `libcdsprpc.so` exist. `syncRNLlamaHtpAssets` copies the four DSP libraries into `assets/ggml-hexagon/`.
3. A log grep for `Building rnllama variants: <list>` proves the allowlist reached gradle. Then the gate runs on the exact paths about to be uploaded.
4. Release only: upload to Play, then push the version tag, then attach the APK to the GitHub Release.
5. At runtime, `RNLlama.loadNative` walks the ladder (hexagon_opencl → dotprod_i8mm → dotprod → i8mm → v8_2 → v8 → generic `rnllama_jni`), then loads `rnllama` unconditionally.

## Traps and decisions

**Build mode and the backend**
- **The root `android/gradle.properties` is not a lever.** llama.rn's own `gradle.properties` wins for its subproject (measured on Gradle 9.0.0). Only `ORG_GRADLE_PROJECT_…`, `-P`, or a `$GRADLE_USER_HOME/gradle.properties` override it, and the last is live because `release.yml` points `GRADLE_USER_HOME` at `runner.temp`. Build mode is always declared in the job, never inferred.
- **Every way of losing the Hexagon backend is silent.** A missing SDK directory prints one line, a missing `libcdsprpc.so` is a CMake warning, and missing DSP sources skip the sync. The build succeeds each time. That shipped once (issue #858), which is why the check sits on the artifact.
- **Backend presence is read from `.dynsym`, never `strings` or file size.** Both give false results. The #858 APK had all 12 libraries and all 4 DSP assets, so only the symbol rule would have failed it.
- **Symbol names match exactly.** From llama.rn 0.13.0-rc.5, ggml symbols are unprefixed, and each older `lm_` name ends with its successor, so a suffix or substring reader would pass an old artifact. The gate's fixtures keep the `lm_` names as defined noise for that reason.
- **Local builds are a coin toss.** `build.gradle` defaults `HEXAGON_SDK_ROOT` to `~/.hexagon-sdk/6.4.0.2`, so the backend is included only if that directory exists. Run the gate locally to find out. A macOS host can build it: nothing on the Android path invokes `hexagon-clang`.
- **The gate proves presence, not engagement.** `isHexagonSupported()` gates the backend on SoC hints at runtime, and no emulator has a DSP.
- **The escape hatch is `-PrnllamaBuildFromSource=false`**, not the default. The JNI wrapper would link against a prebuilt from another snapshot, and struct-layout drift wouldn't surface.
- **Consume llama.rn npm releases, not git refs.** A git install lacks `bin/`, `jniLibs`, `lib/`, and the QAIC `vendor/llama.cpp/ggml/src/ggml-hexagon/htp/v73` artifacts.

**The variant ladder**
- **Rung 6 (`rnllama_v8`) is not a duplicate of the generic `rnllama`.** Non-generic arches add optimised ARM sources; dropping rung 6 silently demotes pre-fp16 devices to portable C.
- **`rnllama_v8_2_dotprod_i8mm` and the hexagon variant share arch and flags.** An "equal flags means covered" rule would wrongly license dropping the hexagon variant.
- **`v8_2_i8mm` is the one dropped rung**, a costed bet: no shipping SoC is known to report i8mm without dotprod. Upstream's 3-variant CI list demotes every non-Snapdragon arm64 device to generic; don't copy it.
- **The allowlist grep proves the env route only because `rnllamaVariants` is set in no properties file.** Adding it to one keeps the grep green while it proves nothing. The grep literal is upstream's println; reword it when upstream does.

**Held by review, not by CI**
- **The gate runs before every upload, on the same paths.** The fastlane lanes are split so the gate can sit between build and upload; nothing tests the ordering.
- **`upload_android_alpha`'s `aab:` must match the gate's `--aab` in `release.yml`.** It is one path written twice. Without an explicit `aab:`, the lane goes green having uploaded no binary.
- **The manifest can be weakened and still pass**, for example with a symbol rule re-pointed at `librnllama.so`. The script enforces floors, not meaning; the control is a reviewed manifest diff.
- **Test builds may add instrumentation, never subtract capability.** `e2e-tests.yml` provisions the SDK and runs the gate exactly as release does.
- **Bump the SDK version and both digests together**, in `setup-hexagon-sdk` only.

**CI hygiene**
- **`print_command: false` on both `gradle(...)` calls.** Fastlane's command echo leaked the signing passwords into the build log.
- **`RNLLAMA_SKIP_POSTINSTALL=1` (release, e2e) is safe only when building from source.** `ci.yml` doesn't set it because its `node_modules` cache is shared with `build-and-test`.
- **No ccache on the release path**: a prefix restore could link objects of unreviewed provenance into the shipped binary. In `ci.yml`, ccache needs `CCACHE_COMPILERCHECK=content` plus the sloppiness list, or every lookup misses and it looks like a cold cache.
- **GitHub caps caches at 10 GB per repo and evicts silently.** An evicted SDK or ccache entry shows only as a slow run. `ci.yml` `build-android` takes about 44 min cold and 23 min warm.
- **Enabling release minify needs a `-keep class com.rnllama.**` rule.** None exists.
- **Play Billing comes only from `react-native-iap`.** `openiap-versions.json` in the package pins `openiap-google`, which brings `billingclient:billing` 9.x; the app declares no billing dependency, so check `./gradlew :app:dependencies --configuration prodReleaseRuntimeClasspath | grep billingclient` after a library bump. iOS gains the `NitroIap`, `NitroModules` and `openiap` pods.

## Verification

- `yarn test scripts/__tests__/` after `yarn install` (the ladder and SDK tests read `node_modules/llama.rn`).
- Local gate: `node scripts/verify-android-payload.js --apk <apk> [--aab <aab>]`. A sound artifact shows 12 arm64 + 4 x86_64 `librnllama*` libraries, 4 assets, and both Hexagon symbols `present`. A backend-less build fails only those two symbols.
- On a llama.rn upgrade, re-check the println wording, the CMake call sites, `HTP_LIBS`, and the SDK paths CMake references. Also re-check:
  - the manifest's symbol names against the vendored header: `grep -n ggml_backend_hexagon_reg node_modules/llama.rn/vendor/llama.cpp/ggml/include/ggml-hexagon.h`;
  - every env var `MainApplication.kt` sets against the vendored ggml's `getenv` names (a name nothing reads is a silent no-op): `for v in $(grep -o 'setenv("[A-Z_]*"' android/app/src/main/java/com/pocketpalai/MainApplication.kt | cut -d'"' -f2); do grep -rq "getenv(\"$v\")" node_modules/llama.rn/vendor/llama.cpp/ggml/src && echo "ok $v" || echo "DEAD $v"; done`.
- `release.yml` publishes and can't be rehearsed. Check lane, `aab:` and step-order changes by reading, then watch the next release. To see the backend engage, run an `e2e-tests.yml` APK on a Snapdragon 8-series device.
