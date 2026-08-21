# Release — the Android native build and the shipped payload

Cumulative truth for how PocketPal's Android artifacts get their native llama.rn payload, and what
guarantees that payload before it ships.

**Scope.** The Android native build (build mode, compiled variants, the Hexagon/NPU backend) and the
payload gate that guards publication. TestFlight and Play upload mechanics, signing, and version
bumping are **not** documented here yet — they accrue when a story needs them (deferred cleanup 4).
iOS is out of scope: it vendors the prebuilt `ios/rnllama.xcframework` and cannot regress this way.

Cross-reads: `model-loading.md § Build note` states the dependency shape and the llama.rn version
rationale and points here for the build contract; this doc does not restate it.

**Conventions**: `(C)` current, verified from code or a recorded run; `(D)` decision with rationale.

---

## 1. The declaration

The only durable state is a committed statement of what a shipped Android artifact must contain.
No app runtime state is involved.

```
AndroidPayloadManifest                       scripts/android-payload-manifest.json
  abis: AbiRequirement[]

AbiRequirement
  abi: "arm64-v8a" | "x86_64"
  requiredLibs: string[]          // librnllama*.so + librnllama_jni*.so that MUST be present
  requiredSymbols: SymbolRule[]   // per-library exported-symbol assertions
  requiredAssets: string[]        // non-lib payload the backend needs at runtime

SymbolRule
  lib: string
  mustExport: string[]                  // exact .dynsym names — the correctness rule
  expectedMatchCount: {pattern, count}  // drift tripwire, not the correctness rule
```

Persisted: the manifest, in the app repo. Derived: the variant allowlist (§4b). (C)

**Glossary**

- **Variant** — one full compile of the llama.cpp tree under a specific `-march`, producing
  `librnllama_<variant>.so` plus its `librnllama_jni_<variant>.so` wrapper.
- **Build mode** — from-source (`rnllamaBuildFromSource=true`, compiles `cpp/`) vs prebuilt (links
  llama.rn's downloaded `jniLibs`).
- **Ladder** — the ordered runtime probe in `RNLlama.java:196-260` that picks the best variant present
  on the device.
- **Payload gate** — `scripts/verify-android-payload.js`, which validates a built APK/AAB against the
  manifest.
- **DSP assets** — `assets/ggml-hexagon/libggml-htp-v{73,75,79,81}.so`, synced from
  `node_modules/llama.rn/bin/arm64-v8a` by llama.rn's `syncRNLlamaHtpAssets` task.

### 1b. External inputs

- The Hexagon SDK, a public GitHub release (`snapdragon-toolchain/hexagon-sdk` v6.4.0.2, `amd64-lnx`,
  673 MB compressed / ~3.1 GB extracted, no account or licence gate). `amd64-lnx` only — usable on
  `ubuntu-latest`, **not** on macOS runners. (C)
- llama.rn's checksum-pinned native artifacts, downloaded by its own postinstall from
  `releases/download/v<version>/` and verified against `install/native-artifacts.json`. Excluded from
  the npm tarball and absent from the upstream git repo. (C)

---

## 2. What determines the shipped backend (C)

Verified from code; the whole contract rests on it.

1. `node_modules/llama.rn/android/gradle.properties:9` sets `rnllamaBuildFromSource=true`.
   `llama.rn/android/build.gradle:20` reads it with `project.findProperty`.
2. **A subproject's own `gradle.properties` beats the root project's for that subproject.** Measured on
   Gradle 9.0.0 (the pinned wrapper) with a two-project probe: root `false` + subproject `true` ⇒ the
   subproject reads **`true`**. The root `android/gradle.properties` is therefore not a lever at all;
   its commented-out `rnllamaBuildFromSource` line has been deleted (D10). Only
   `ORG_GRADLE_PROJECT_rnllamaBuildFromSource` or `-P` override it.
3. From-source ⇒ `build.gradle:188-195` blanks `jniLibs.srcDirs`, so the downloaded prebuilts are
   removed from the source set, not merely ignored.
4. Backend inclusion is gated **twice**, and both gates degrade to a *warning*:
   - `build.gradle:143-169` — `hexagonPresent = file(HEXAGON_SDK_ROOT).exists() &&
     file(HEXAGON_TOOLS_ROOT).exists()`; false ⇒ prints `🚫 Hexagon SDK not found` and omits two `-D` args.
   - `rnllama/CMakeLists.txt:165-240` — requires `HEXAGON_SDK_ROOT`, `HEXAGON_TOOLS_ROOT` **and**
     `ipc/fastrpc/remote/ship/android_aarch64/libcdsprpc.so`; otherwise
     `message(WARNING "Hexagon backend will not be built.")`.
5. Only variants matching `.*_hexagon.*` carry the backend — exactly one exists
   (`rnllama_v8_2_dotprod_i8mm_hexagon_opencl`).
6. `RNLlama.java:259` calls `System.loadLibrary("rnllama")` **unconditionally**, outside the ladder.
   An `UnsatisfiedLinkError` there is caught and disables the module.
7. `rnllamaVariants` (root project property, or `ORG_GRADLE_PROJECT_rnllamaVariants`) reaches the
   llama.rn subproject and becomes `-DRNLLAMA_ANDROID_VARIANTS`.
8. ccache is already wired into upstream's CMake (`cmake/rnllama-build-options.cmake:9-22`, default ON,
   used if a `ccache`/`sccache` binary is on PATH). CI supplies the binary and the cache, nothing more.
9. The four DSP libraries are required as a **set**: `RNLlama.java:26-31` hardcodes v73/v75/v79/v81 and
   `ensureHtpLibraries` returns `false` on the first one it cannot extract, disabling the backend
   outright. One missing asset is as fatal as four.

**The failure this doc exists to prevent:** three independent conditions can drop the backend, all
silently, and one of them did — every Android release between the llama.rn 0.13.0-rc.0 upgrade and this
change shipped without the NPU backend (issue
[#858](https://github.com/a-ghorbani/pocketpal-ai/issues/858)).

---

## 3. The runtime ladder, and what a missing variant costs (C)

`RNLlama.java:196-260`, arm64 branch, in order. Each rung falls through if the library is absent.

| # | Rung | Selected when | Lost if dropped |
| --- | --- | --- | --- |
| 1 | `..._dotprod_i8mm_hexagon_opencl` | dotprod ∧ i8mm ∧ hexagon ∧ Adreno | the NPU + OpenCL |
| 2 | `..._v8_2_dotprod_i8mm` | dotprod ∧ i8mm | every modern non-Snapdragon arm64 device drops to rung 3 |
| 3 | `..._v8_2_dotprod` | dotprod | 2019–2022 flagships drop to rung 5 |
| 4 | `..._v8_2_i8mm` | i8mm ∧ ¬dotprod | **the one dropped rung** — see below |
| 5 | `..._v8_2` | fp16 | pre-2019 devices drop to rung 6 |
| 6 | `..._v8` (`arm`, `-march=armv8-a`) | always, on arm64 | **the ARM CPU kernels** |
| 7 | `rnllama_jni` / `rnllama` (`generic`) | fallback | mandatory regardless (§2.6) |

**Rung 6 is not a duplicate of rung 7, despite matching `-march`.**
`rnllama/CMakeLists.txt:132-135` adds `ggml-cpu/arch/${arch}/quants.c` and `repack.cpp` for every
non-`generic` arch, and `:149-150` compiles `generic` with `-DLM_GGML_CPU_GENERIC`. So `rnllama` is the
portable-C fallback and `rnllama_v8` carries the ARM quantised-matmul kernels. Dropping rung 6 would
demote every arm64 device failing the fp16 check to portable C — and silently, since `librnllama.so`
would still be present. Same `-march` is not same build.

**Rung 4 is a costed bet, not a proof.** FEAT_I8MM is optional from Armv8.2 and mandatory from 8.6;
FEAT_DotProd is optional from 8.2 and mandatory from 8.4. Neither implies the other, and the runtime
gate is a string scrape of `/proc/cpuinfo`. The claim is empirical: no shipping SoC is known to report
i8mm without dotprod. A device that did would land on rung 5, or rung 6 if it also lacks fp16.
Recorded in `scripts/__tests__/android-ladder-coverage.test.js`, which fails if any other rung is dropped.

**The allowlist is 6 of 7 arm64 variants, not upstream's 3.** Upstream's own CI list
(`rnllama, rnllama_v8_2_dotprod_i8mm_hexagon_opencl, rnllama_x86_64`) is not safe to copy: it silently
demotes every non-Snapdragon arm64 device from rung 2 to rung 7. Build-time relief comes from the
caches (§8 D2), not from narrowing. Narrowing further needs a real-device measurement of what each rung
is worth (deferred cleanup 6).

---

## 4. Contract

### 4a. Build mode is declared, never detected (C)

1. **Every workflow that builds Android** sets `ORG_GRADLE_PROJECT_rnllamaBuildFromSource` at job level:
   `ci.yml` `build-android`, `release.yml` `build_android`, `e2e-tests.yml` `build-android`. A job that
   inherits its mode from `node_modules/llama.rn/android/gradle.properties` is in exactly the posture
   this abolishes, whether or not its artifact ships.
2. The declared default is **from-source** (`true`).
3. No workflow may infer the mode from `package.json`, a git ref, or the presence of a file. An
   ordinary npm version now builds from source, so any such detector is wrong by construction.
4. `android/gradle.properties` carries no `rnllamaBuildFromSource` line. It could not work (§2.2).
5. "Correct build-mode detection" is satisfied by **removing the need to detect**, not by fixing a detector.

### 4b. What a shipped Android artifact must contain (C)

Declared in the manifest (§1), enforced by the gate (§4c).

| ABI | Required libraries | Required assets |
| --- | --- | --- |
| `arm64-v8a` | `librnllama.so`, `librnllama_v8.so`, `librnllama_v8_2.so`, `librnllama_v8_2_dotprod.so`, `librnllama_v8_2_dotprod_i8mm.so`, `librnllama_v8_2_dotprod_i8mm_hexagon_opencl.so` — each with its `librnllama_jni*.so` wrapper | `assets/ggml-hexagon/libggml-htp-v{73,75,79,81}.so` |
| `x86_64` | `librnllama.so`, `librnllama_x86_64.so` — each with its wrapper | — |

Required exported symbols, `arm64-v8a` / `librnllama_v8_2_dotprod_i8mm_hexagon_opencl.so`:

- `lm_ggml_backend_hexagon_reg` and `lm_ggml_backend_is_hexagon` **must** be defined in `.dynsym`.
  These are the correctness rule.
- The count of `.dynsym` entries matching `hexagon` is declared as `16` and is a **drift tripwire**: a
  change fails the gate and must be consciously re-declared in the same PR that causes it.

**Matching convention, pinned in the manifest.** `expectedMatchCount` counts every `.dynsym` entry
containing the pattern, case-insensitively, undefined imports included — the convention of
`llvm-nm -D | grep -ci`, which is how the number was measured. `mustExport` instead requires the names
to be **defined** (`st_shndx != SHN_UNDEF`); an undefined import would prove nothing.

**The allowlist is the manifest.** `ORG_GRADLE_PROJECT_rnllamaVariants` is derived at build time by
`verify-android-payload.js --print-variants`: required libraries, wrappers dropped, `lib`/`.so` stripped,
deduped across ABIs. Today that is
`rnllama,rnllama_v8,rnllama_v8_2,rnllama_v8_2_dotprod,rnllama_v8_2_dotprod_i8mm,rnllama_v8_2_dotprod_i8mm_hexagon_opencl,rnllama_x86_64`.
Bare variant names, not filenames: `rnllama_variant_enabled` matches the bare name and gates both the
library and its JNI wrapper.

`e2e-tests.yml` applies the same allowlist but **not** the gate and **no** SDK: its APK is never
published and emulators have no DSP (D14).

**Why the backend rule names Hexagon and not OpenCL.** OpenCL cannot degrade the same way. Its sources
and `-DLM_GGML_USE_OPENCL` are added *outside* the `if (EXISTS ${OPENCL_STUB})` guard
(`rnllama/CMakeLists.txt:437-459`), and its `.dynsym` entries are undefined imports, so a missing
`libOpenCL.so` fails loudly at link time. Hexagon's sources are added *inside* its guard — which is
exactly why its absence is silent and needs an artifact-level assertion.

### 4c. The payload gate (C)

1. One implementation (`scripts/verify-android-payload.js`), one manifest, consumed by every workflow
   that produces a shippable Android artifact, and runnable locally against a local build. No workflow
   restates a rule inline.
2. It runs **before any upload, publish, or release step**, in every such workflow.
3. It reads `.dynsym`. Not `strings`, not file size: `strings` false-positives on `codec_*_ht` symbols,
   and the two builds that differ in whether the backend exists have identical `opencl` string counts
   (644). `.dynsym` survives stripping.
4. It self-checks its instrument before judging: it fails if it cannot open the artifact, cannot locate
   a required library, cannot parse the ELF, or reads an empty `.dynsym`. A zero-match read is an
   instrument failure, never a pass.
4b. **Every list in the manifest has a floor**, because the check's own failure mode is passing by
   absence and an emptied list is the cheapest edit that unblocks a build. The rule is that a
   declaration must demand something be **present**:

   | List | Floor |
   | --- | --- |
   | `abis` | non-empty |
   | `requiredLibs` | non-empty, per ABI |
   | `requiredSymbols` | at least one rule overall, and at least one for any ABI declaring a `_hexagon` library |
   | each symbol rule | `mustExport` non-empty, **or** an `expectedMatchCount` with a non-empty `pattern` and `count > 0` |
   | `requiredAssets` | non-empty for any ABI declaring a `_hexagon` library |
   | derived allowlist | non-empty |

   The asset and symbol floors are conditional on the ABI carrying an accelerator, since an ABI
   without one legitimately declares neither. The report also prints the `assets:` row even when
   nothing is declared — the summary line claims assets were checked, so a manifest that declares
   none must be visible in the evidence rather than quietly losing the row.

   Four weakenings were **measured passing on real artifacts** before these floors existed: a rule
   that named the library and asserted nothing; a rule whose only demand was
   `{pattern: "hexagon", count: 0}`, which does not merely assert nothing but asserts the backend is
   *absent*, so the incident build satisfies it exactly; an emptied `requiredAssets`, which passed an
   APK with **zero** DSP libraries — backend compiled in, dead on the device; and emptied arm64
   symbol rules while x86_64 still carried one. In every case the other rules were already
   *satisfied* by the bad build, so the emptied one was the only thing standing between it and a
   green pipeline. Each is the kind of edit a dependency bump invites: a renamed
   `libggml-htp-v*.so` makes the asset rule fail, and emptying the list is the single edit that
   unblocks it.

   A repeated `--apk`/`--aab`/`--manifest` is refused for the same reason, as is `--print-variants`
   alongside an artifact.

   **Where this hardening stops, and why.** The script can enforce that a declaration *demands
   presence*. It cannot enforce that the demand is *meaningful*. Two weakenings defeat the gate and
   are not defects in it: re-pointing a rule's `lib` at `librnllama.so` and demanding a symbol that
   is always there, or keeping the hexagon library but demanding a trivially-true symbol of it.
   Catching either would mean hardcoding which library and which symbols matter — duplicating in the
   script the very thing the manifest exists to declare, and leaving two places to disagree. Past
   this line the control is a **reviewed manifest diff**, not more validation. A future maintainer
   should add floors, not semantics.

   Two weakenings that already fail closed, and are worth keeping that way: dropping the hexagon
   library from `requiredLibs` while keeping its symbol rule (the allowlist derives from
   `requiredLibs`, so the variant stops being built and instrument-honesty fires — removing the
   library from the contract *cannot* hide it), and deleting the arm64 ABI entry outright.
5. It checks **both** shipped forms on the release path — the APK attached to the GitHub Release and
   the AAB uploaded to Play — resolving paths per form: an APK holds `lib/<abi>/…` and `assets/…`, an
   AAB holds `base/lib/<abi>/…` and `base/assets/…`. The `base/` layout is verified against a genuine
   `:app:bundleProdRelease` output, not a synthetic one. `ci.yml` builds no bundle and so checks only
   the APK.
6. Extra `librnllama*` variants beyond the manifest are permitted and reported, not failed: the ladder
   can only benefit, and the prebuilt escape hatch (§4d) legitimately produces all seven.
7. The ELF reader is in-process, not a shell-out to `readelf`/`llvm-nm`: macOS ships no `readelf` and
   the NDK's `llvm-nm` sits at a host-specific path, so shelling out would make the check unrunnable on
   the machines that most need to run it locally. It is calibrated against `llvm-nm -D` (§10).

**`android/fastlane/Fastfile` is part of the contract.** `release_android_alpha` used to run
`gradle(assemble)` → `gradle(bundle)` → `upload_to_play_store` inside a single lane invoked as one
workflow step, so any gate placed in the workflow ran *after* Play already held the AAB. The lane is
split into `build_android_release` and `upload_android_alpha`, with the gate between them as its own
workflow step — so the ordering is enforced by the workflow graph rather than by Ruby statement order,
and the gate looks identical in both workflows (D13).

**The upload lane must pass `aab:` explicitly.** `upload_to_play_store` otherwise fills it from
`lane_context[SharedValues::GRADLE_AAB_OUTPUT_PATH]`, which only exists in the process that ran
`gradle(task: "bundle")`. Across two `bundle exec fastlane` invocations that value is `nil`, supply's
fallback globs do not match this project's flavored path, `metadata_path` with
`skip_upload_metadata: false` satisfies supply's no-metadata-and-no-binary guard, and the run goes
**green having uploaded metadata and no binary**. With the path passed explicitly, supply's
`verify_block` turns a wrong path into a loud failure instead.

Two alternatives were considered and rejected: calling the gate from inside the lane (ordering would
live in Ruby statement order, and the two workflows would invoke the gate differently), and a Gradle
verification task attached to the `assemble`/`bundle` output (strongest — it would satisfy the ordering
invariant by construction and cover local builds for free — but it would fail every local release build
for a developer without the 673 MB SDK, turning an advisory into a blocker on machines that have no
business being blocked). Worth revisiting only if local from-source builds stop being routine.

### 4d. Escape hatch (C)

Forcing prebuilts stays available as a documented emergency lever, and is verified to work (§2.2).
**Use the command-line form:** `./gradlew <task> -PrnllamaBuildFromSource=false`. The environment form
also wins by our own Gradle 9.0.0 measurement, but upstream's CI comments assert that only the command
line beats a subproject's `gradle.properties`. The two sources disagree only for the `false` case — the
only case where the lever is actually used — so use the mechanism both agree on.

It is not the default: the JNI wrapper is always compiled from the tarball's `cpp/` headers and then
linked against a binary from a different snapshot. A missing symbol would surface at link time;
**struct-layout drift would not surface at all.** Using the lever does not weaken the gate; the gate is
what makes it usable at all.

### 4e. Hard invariants

- **I1 — declared payload**: every shipped Android artifact contains, for each ABI, at least every
  library and asset the manifest declares.
- **I2 — backend presence**: the hexagon variant defines `lm_ggml_backend_hexagon_reg` and
  `lm_ggml_backend_is_hexagon` in `.dynsym`.
- **I3 — evidence source**: backend presence is decided from `.dynsym` only.
- **I4 — instrument honesty**: a check that could not run fails; it never passes by absence. This
  applies to the gate's read paths and to the workflow's declaration assertions alike.
- **I5 — gate precedes publication**: no upload/publish step runs before a passing gate, in any
  workflow and inside any lane it invokes.
- **I6 — mode is not evidence**: build mode is a cost and provenance choice. Correctness is asserted on
  the artifact, never inferred from the mode.
- **I7 — ladder coverage**: the compiled-variant allowlist contains every rung the ladder can select.
  A rung may be omitted only when it is **build-equivalent** to a retained rung — same `-march`, same
  source list, same compile definitions — or as a *named, costed* bet with the fall-through rung
  recorded. "Same `-march`" alone never qualifies.

---

## 5. Single-writer rule

| Thing | Single determinant |
| --- | --- |
| effective Android build mode | `ORG_GRADLE_PROJECT_rnllamaBuildFromSource` set by the workflow → `$GRADLE_USER_HOME/gradle.properties` → `node_modules/llama.rn/android/gradle.properties`. **Never** `android/gradle.properties`. The middle rung is live: `release.yml` sets `GRADLE_USER_HOME` to `${{ runner.temp }}/.gradle` and `setup-java` caches it, so that variable belongs on the *build* step of the split lane |
| variants compiled | `rnllamaVariants` project property → `-DRNLLAMA_ANDROID_VARIANTS`, derived from the manifest |
| Hexagon backend compiled in | `HEXAGON_SDK_ROOT` + `HEXAGON_TOOLS_ROOT` reaching a tree containing `libcdsprpc.so` |
| DSP assets in the artifact | llama.rn's `syncRNLlamaHtpAssets`, sourced from `node_modules/llama.rn/bin/arm64-v8a` |
| required payload | the committed manifest |
| what the Play upload ships | the `aab:` path passed explicitly by `upload_android_alpha` |

**Two declarations are asserted separately, because they are not the same problem.** Both reach gradle
only through the environment and both used to fail silently, and the gate sees neither:

- **Allowlist — asserted from the build log.** The build is teed to `android/android-build.log` and a
  separate step greps for `Building rnllama variants: <the exact list>`. `build.gradle:155-158` prints
  that line **only** when the property arrived by the `ORG_GRADLE_PROJECT_` route, so its presence
  proves transport and its content proves the value. An unarrived allowlist builds all seven arm64
  variants, which §4c.6 would pass as permitted extras. Note the grep is a *substring* match, so it
  proves the declared list was reported, not that the built set is exactly it — extras are permitted
  by design and the payload gate is what reports them. The step's message says so.
- **Mode — asserted from the environment, not a log line.** `rnllamaBuildFromSource` has a competing
  definition with the same value today, so a typo in our variable name produces a build
  *indistinguishable* from a correct one — until the day upstream flips its flag to `false`, at which
  point a mis-named declaration would silently switch CI to prebuilt mode with the gate still passing.
  The build step therefore fails when the variable is empty. `CMakeLists.txt:30`'s
  `message(STATUS "Building rnllama libraries from source")` is deliberately **not** used: it is
  configure-time output, so a warm `.cxx` restore can skip configure and drop it.

**What this evidence supports, stated precisely:** the allowlist is verified end-to-end; the mode
declaration is verified as *set*. Nothing observable distinguishes our `true` from upstream's `true`
while both agree — §2.2's measured precedence carries the rest.

Past pain: the regression itself — three independent silent-degrade paths and no assertion anywhere.

---

## 6. Canonical scenarios

### A. Conforming build
```
ubuntu-latest, mode=from-source, SDK provisioned, allowlist = manifest set
─────
artifact holds 12 arm64 + 4 x86_64 rnllama libraries + 4 DSP assets;
hexagon variant defines both named symbols, 16 hexagon .dynsym matches; gate passes; upload proceeds
```

### B. The regression
```
mode=from-source, HEXAGON_SDK_ROOT unset
─────
build succeeds with a CMake warning; hexagon .dynsym matches = 0
gate fails on I2; nothing is uploaded
```

### C. Allowlist edited without updating the manifest
```
rnllamaVariants loses rnllama_v8_2_dotprod
─────
artifact lacks librnllama_v8_2_dotprod.so; gate fails on I1
```

### D. Emergency lever
```
./gradlew … -PrnllamaBuildFromSource=false
─────
all 7 arm64 variants present (superset of manifest); backend symbols present
gate passes on I1/I2; extra variants reported, not failed
```

### E. llama.rn upgrade changes the symbol surface
```
new llama.rn version, hexagon .dynsym matches = 18
─────
named symbols still present; count tripwire fails
manifest re-declared to 18 in the same PR, with the diff visible in review
```

### F. Ladder coverage — every rung a device can land on is buildable (I7)

Checked over the manifest and llama.rn's CMake call sites, not over a built artifact.

```
for each build_rnllama_library(name, arch, flags) call site reachable for the ABI
─────
name ∈ manifest.requiredLibs
  OR ∃ retained r : (arch, flags, source-list, compile-defs) identical  → build-equivalent
  OR name ∈ the named-bet list, with the fall-through rung stated
otherwise: fail
```

The near-miss the predicate must get right: `rnllama_v8_2_dotprod_i8mm` (`:479`) and
`rnllama_v8_2_dotprod_i8mm_hexagon_opencl` (`:480`) have **identical `arch` and identical `cpu_flags`**.
They diverge only inside the function body, where `.*_hexagon.*` and `.*_opencl$` match on the *name*
and add sources and `-D` macros. A predicate reading "(arch, flags) match ⇒ interchangeable" would
license dropping the hexagon variant — the one this whole contract exists to protect.

**Coupling assumption.** The check quantifies over `build_rnllama_library`
(`rnllama/CMakeLists.txt:471-484`), but the ladder loads `librnllama_jni_*`, produced by
`build_rnllama_jni` (`android/src/main/CMakeLists.txt:153-174`) in a different file. The two lists are
1:1 today because both gate on `rnllama_variant_enabled(<rnllama_name>)`, and the test asserts that
1:1-ness rather than assuming it.

**Vacuity guard.** The parse asserts 8 library and 8 JNI call sites (1 unconditional, 6 arm64, 1
x86_64) *before* iterating. Without it, an upstream reformat matching zero sites would make the check
pass on nothing. I4 applied to a second instrument.

### G. Release path — the gate cannot be outrun by the upload
```
release workflow, build lane produces APK + AAB, gate fails on I2
─────
upload lane never runs; Play receives nothing; no tag is pushed; no GitHub Release is created
```

---

## 7. Signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `hexagonPresent` | `llama.rn/android/build.gradle:145` | gradle → CMake args | both SDK and tools dirs exist on the runner |
| `HEXAGON_SDK_AVAILABLE` | `rnllama/CMakeLists.txt:168-178` | the variant's source list | above ∧ `libcdsprpc.so` exists |
| `RNLLAMA_BUILD_FROM_SOURCE` | `-DRNLLAMA_BUILD_FROM_SOURCE` from `build.gradle:148` | both CMake entry points | build mode is from-source |
| `Building rnllama variants: …` | `build.gradle:155-158` (`println`) | the workflow's allowlist assertion | the property arrived by the `ORG_GRADLE_PROJECT_` route |
| manifest conformance | the payload gate | the workflow's publish step | I1–I4 hold on the produced artifact |

---

## 8. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Provision the Hexagon SDK on the two *publishing* Android jobs; keep from-source | Public SDK, correct toolchain, no vendor fight |
| D2 | Cache the SDK, the NDK `.cxx` tree, and ccache | 673 MB and full-tree compiles per job otherwise |
| D3 | Allowlist = 6 arm64 variants + 2 x86_64, not upstream's 3 | Upstream's list silently demotes non-Snapdragon devices |
| D4 | Drop `rnllama_v8_2_i8mm` only, as a named bet | No shipping SoC reports i8mm without dotprod |
| D5 | `rnllama` is mandatory in every ABI's list | `System.loadLibrary("rnllama")` runs unconditionally |
| D6 | Requirement lives in a committed manifest with one gate | One declaration, every workflow, runnable locally |
| D7 | Named `.dynsym` symbols are the rule; the count is a tripwire | Names prove behaviour; count catches silent upgrade drift |
| D8 | iOS is out of scope | From-source excludes hexagon/opencl; macOS can't use the amd64-lnx SDK |
| D9 | Commit-pinning a llama.rn git ref deferred to its own story | Git installs lack DSP, OpenCL, jniLibs and `lib/` artifacts |
| D10 | Declare the build mode; delete the root `gradle.properties` knob | Measured inert; detection is inference where declaration is available |
| D11 | Keep prebuilt-forcing as a documented, gated emergency lever | Works, and cheap — but its ABI pairing is unverifiable |
| D12 | The payload gate does not absorb the DCE check | Different subject, different manifest; coupling them helps neither |
| D13 | Split the fastlane release lane; gate between build and upload | A gate the publish step can outrun is not a gate |
| D14 | `e2e-tests.yml` declares mode + allowlist, but no SDK and no gate | Emulators have no DSP; its APK never ships |
| D15 | Push the release tag after the gate, not after the version bump | A failed gate should leave no tag to reuse or delete |
| D16 | Set the full ccache env, not just dir and size | The NDK is reinstalled per run, so `compiler_check=mtime` would miss on everything and read as cold rather than misconfigured |

**On D2, the cache budget and the subset alternative.** The Android host build reads only `incs`,
`incs/stddef`, `ipc/fastrpc/rpcmem/inc`, and links
`ipc/fastrpc/remote/ship/android_aarch64/libcdsprpc.so` — well under 1 MB of a ~3.1 GB tree.
`HEXAGON_TOOLS_ROOT` is only *existence-checked*; the 2.7 GB toolchain is never invoked, because the
DSP build that would use it is not part of the Android host build. A curated subset would work and
would nearly erase the cache cost — rejected because it depends on undocumented internal SDK layout
that upstream may rearrange, and the existence check would pass on a subset that later stops satisfying
CMake. Full tree now; subset is deferred cleanup 7.

GitHub Actions caps caches at **10 GB per repository**, shared across `gradle`, `node_modules`, `.cxx`,
ccache and the SDK. Eviction thrash would silently defeat D2 rather than fail loudly, so cache keys and
eviction behaviour must be reviewed together, not chosen per-step.

> **Measured 2026-08-20, before any of the three new entries existed: the repository was already at
> 9.78 GB of the 10 GB cap across 17 entries.** Three `setup-java-Linux-gradle` entries at ~2.24 GB
> each account for 6.7 GB — 69% of the whole budget — and they come from `actions/setup-java`'s
> `cache: 'gradle'`, not from anything in this contract.
>
> **After the first provisioned run: 10.62 GB across 14 entries**, the three new entries being
> `hexagon-sdk-6.4.0.2` 963 MB, `ccache-android` 852 MB and `Linux-cxx` 659 MB — 2.47 GB together.
> **After the following run it had settled at 8.98 GB across 13 entries**, with all three new entries
> intact and all three restored. So LRU took the eviction out of older, unused entries and warmth was
> not harmed. The standing exposure is that eviction is *invisible*: a warm run that silently misses
> looks like a cold run rather than like a misconfiguration, which is precisely how D2 gets defeated
> without anyone noticing. A busier week could evict `hexagon-sdk-6.4.0.2` with no symptom but a slow
> run.
>
> The pre-committed rule (over ~8 GB, drop the `.cxx` entry first, it being the most redundant with
> ccache) was **already triggered by the starting state**, before this contract added anything. But
> the three new entries are 23% of the budget and the gradle cache is 63%, so dropping `.cxx` treats
> the smaller half. Reducing the `setup-java` gradle cache footprint is the larger lever and belongs
> to its own change (deferred cleanup 9).

The `.cxx` cache is `ci.yml` only: a restored tree is only useful while ninja's mtime comparison
against `node_modules/llama.rn/cpp/` still holds, and `ci.yml` caches `node_modules` so those mtimes
are tar-preserved, while `release.yml` does not. Upstream caches ccache but not `.cxx`, a weak prior in
the same direction.

**On D11, what was actually checked**: the pinned 0.13.0-rc.0 prebuilt hexagon variant measures **16**
hexagon `.dynsym` symbols and **15** `barbet` strings. So the "missing Barbet arch" half of upstream's
stated reason for forcing from-source is false for the assets this version pins. The completion-loop
half is not checkable at this cost, and the risk it names — struct-layout drift across a header/binary
boundary — does not announce itself. One falsified half does not license ignoring the other.

**On D9, the evidence** (positive controls passed, so these are real absences): a git-ref install lacks
`bin/` (no DSP libraries, no `libOpenCL.so`), lacks `cpp/ggml-hexagon/htp/v73/` (so CMake raises
**FATAL_ERROR** once the SDK is present), lacks `android/src/main/jniLibs`, and lacks `lib/` (compiled
JS); llama.rn's postinstall would additionally 404. Making commit-pinning work means running
`build-hexagon-htp.sh` + `build-opencl.sh` + `bob build` and suppressing the vendor postinstall — a
second, larger build pipeline. That is a scope boundary, not a preference.

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | SDK dirs present but `libcdsprpc.so` missing | The provisioning step fails first; if it were bypassed, CMake warns and the gate fails on I2 |
| 9b | SDK present, QAIC `htp/v73` artifacts missing | CMake `FATAL_ERROR`; build fails loudly (relevant only under D9) |
| 9c | `node_modules` restored from cache without llama.rn's postinstall | Hits the **escape hatch**, not from-source. Missing `jniLibs` makes `CMakeLists.txt:52-58` log "Skipping … no prebuilt" and drop variants silently — caught by I1. From-source is immune, and the DSP assets are safe either way: `bin/` is tarball content |
| 9d | Emergency lever in use | I1 satisfied as a superset, I2 holds; extras reported |
| 9e | Hexagon symbol count changes on upgrade | Tripwire fails; re-declared in the same PR (scenario E) |
| 9f | Translation-only PR | `build-android` is skipped, so no artifact and no gate; the release workflow's gate is the backstop |
| 9g | Gate cannot read the artifact | Fails on I4 — never passes by absence |
| 9h | Upstream later flips `rnllamaBuildFromSource` to `false` | Our declaration wins, so nothing changes silently; switching becomes a deliberate one-line edit |
| 9i | iOS build | Unaffected — vendors the prebuilt xcframework; its from-source path excludes hexagon/opencl |
| 9j | Local build by a developer without the SDK | Still produces a backend-less binary; the gate is runnable locally to expose it (deferred cleanup 3) |
| 9k | Gate fails during a release run | The version bump commit is already pushed, but the tag is not (D15) and nothing is published. The residue is a pushed bump commit, which is already the behaviour for any post-bump failure |
| 9l | `e2e-tests.yml` Android build | Declares mode + allowlist, is **not** gated: the APK is never published and emulators have no DSP |
| 9m | `RNLLAMA_SKIP_POSTINSTALL=1` on the release Android job | Safe: from-source ignores the downloaded `jniLibs` and that job builds no iOS target. If the mode declaration ever failed, the absent `jniLibs` would drop variants and the gate would fail on I1 — loudly. Not set on `ci.yml`, whose Linux `node_modules` cache is shared with `build-and-test` |

---

## 10. Verification record

What was actually proven, and by what. Local, branch-CI, and release-path proofs are different things.

**Proven locally** (machine with `~/.hexagon-sdk/6.4.0.2`):

- From-source build with the allowlist applied → gate **passes** on both the APK and the AAB, 12/12
  arm64 libraries, 4/4 DSP assets, 4/4 x86_64 libraries, both symbols defined, **exactly 16** hexagon
  `.dynsym` entries, **extras: none** (the allowlist dropped `rnllama_v8_2_i8mm` as intended).
- **Instrument calibration**: on that same `librnllama_v8_2_dotprod_i8mm_hexagon_opencl.so`, the gate's
  in-process ELF reader and
  `ndk/27.0.12077973/…/llvm-nm -D | grep -ci hexagon` agree exactly — 6527 `.dynsym` entries and 16
  hexagon matches on both, with both required symbols reported `T` (defined). The reader is
  cross-checked, not trusted.
- Gate against the **currently shipped, broken CI APK** (run 32347391124) → **fails**, naming both
  symbols, with I1 satisfied and extras `librnllama_v8_2_i8mm.so`, `librnllama_jni_v8_2_i8mm.so` —
  the pre-allowlist seven-variant build.
- `bundle exec fastlane build_android_release` produces both artifacts at the paths the workflow and
  the upload lane hardcode.

**Proven by branch CI** — the only proof that provisioning works on `ubuntu-latest`, that the
declarations reach gradle there, and that the gate blocks an upload:

- Run 32401062065 (gate + allowlist, **no SDK**): `build-android` red **at the payload check and
  nowhere else**; the report shows I1 satisfied, extras **empty**, both symbols absent, count 0, on a
  `.dynsym` of **6458** entries; the APK upload step **skipped**, proving I5 on `ci.yml`. The allowlist
  assertion passed. Job wall clock 53 min, no new caches.
- Run 32410730113 (**SDK provisioning the only change**): all four jobs green. The report shows both
  symbols **present**, **exactly 16** hexagon matches on a `.dynsym` of 6527 entries, extras still
  empty. **Absent → present on the two named symbols, with one variable moved** — the stop condition
  is met and no re-declaration was needed. `Provision the Hexagon SDK` succeeded on `ubuntu-latest` in
  ~33 s (673 MB fetch + parallel xz extract). Both `HEXAGON_SDK_ROOT` and `HEXAGON_TOOLS_ROOT`, all
  four ccache variables, and the seven-name allowlist are visible in the build step's environment.

- Run 32415207752 (**warm**, one commit later): green, gate passes, both symbols present, 16 matches,
  extras empty. All three new caches **restored**.

**Build time**, against thresholds committed before the first run:

| | Threshold | Measured |
| --- | --- | --- |
| cold `build-android` | ≤ 75 min | **43.9 min** (run 32410730113) |
| warm `build-android` | ≤ 35 min | **23.2 min** (run 32415207752) |

Run 32410730113 is a **clean cold** measurement: its logs show `Cache not found` for all three new
entries, including the `ccache-android-` restore-key prefix — run 32401062065 predates the ccache step
entirely, so there was nothing for it to be partly warm from. A salted cache-busting run was therefore
not needed, and was not run: it would have added an orphaned entry to a budget already over cap.

**What each cache is worth**, from the warm run: cacheable compiler invocations fell from **2965 to
412** — the restored `.cxx` tree lets ninja skip the rest — and ccache served **398/398 of the
remainder, 100% direct hits, 0 misses**, at 0.9 GB of its 2 GB ceiling. The `.cxx` entry therefore
earns its budget on evidence rather than assumption. The 100% *direct* hit rate is attributable to
`CCACHE_COMPILERCHECK=content` and the `CCACHE_SLOPPINESS` list: the NDK is reinstalled every run and
`yarn install` rewrites mtimes under `node_modules`, so at ccache's defaults nearly every object would
have missed — and would have read as a cold cache rather than as a misconfigured one.

**Provable only on the release path** (post-merge, first real release): the lane split, the gate's
position between build and upload, the AAB path, and the moved tag push. `release.yml` is
`workflow_dispatch` and would bump the version, push a tag and upload to Play, so it cannot be
rehearsed. Residual risk is bounded in the safe direction — a lane-name or path error fails *before*
`upload_to_play_store`, and supply's `verify_block` rejects a wrong `aab:` path.

> **Handover: the first post-merge release run must be watched.** The upload lane and the moved tag
> push have no pre-merge proof.

**Stop condition, for any future repeat of this work**: if the two named symbols do not go from
**absent to present** in a CI-produced artifact, the diagnosis is wrong — stop and report rather than
proceeding. A count other than 16 with both symbols present is **not** a stop: from-source and
upstream's standalone build need not export identically (LTO and visibility differ). Treat it as
scenario E.

**Build-time acceptance**, set before the first run: cold (all three caches miss) ≤ **75 min**, warm
(all three restore) ≤ **35 min**, against 62 and 58 min from-source-without-caches baselines and a 21
min pre-regression prebuilt baseline. Missing either threshold reopens the allowlist (deferred cleanup
6) or the escape hatch (§4d); it does not silently become the new normal.

---

## Deferred cleanups

1. Commit-pinning a llama.rn git ref (D9) — needs its own story.
2. iOS from-source (D8).
3. Local-vs-CI divergence for developers without the SDK: a local build still silently differs. The
   gate is runnable locally, which mitigates but does not remove it.
4. `release.md` covering TestFlight/Play upload mechanics, signing, and version bumping.
5. **The DCE check has the same publication gap this contract closes for the native payload.**
   `ci.yml` asserts the prod bundle carries no automation markers, but nothing equivalent runs on the
   release path — the artifact Play receives is never checked. Different subject and a different
   manifest, so it is not folded into this gate (D12); it deserves the same treatment in its own story.
6. Measuring what each ladder rung is worth on real hardware, so the allowlist can be narrowed on
   evidence rather than left at 6 of 7.
7. A Hexagon SDK *subset* rather than the full 3.1 GB tree, if cache pressure proves it necessary.
8. No `-keep class com.rnllama.** { *; }` proguard rule. Latent only — proguard is off for release
   builds — but it would bite the day it is turned on.
9. **The repository cache budget is over cap and the dominant consumer is `actions/setup-java`'s
   gradle cache** (6.7 GB of ~10.6 GB, three entries). Until that is addressed, every cache in the
   repo is subject to eviction, silently. This is the larger half of the D2 budget problem and is not
   specific to the Android native build.
10. **The payload gate only inspects the ABIs the manifest names.** An artifact carrying an
    unexpected `lib/<abi>/` directory would not be looked at, so a backend-less payload for a
    newly-added ABI would ship unnoticed. Unreachable today — `reactNativeArchitectures` pins
    `arm64-v8a,x86_64` and llama.rn filters 32-bit regardless — but the gate is silent rather than
    loud about it, which is the shape of failure this contract exists to remove.
