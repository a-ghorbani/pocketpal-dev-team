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
  assets: AssetRequirement        // artifact-scoped, so declared beside abis[] and not inside it
  nativeLibsMappedInPlace: true   // the app ships extractNativeLibs=false; floored at true

AbiRequirement
  abi: "arm64-v8a" | "x86_64"
  requiredLibs: string[]          // librnllama*.so + librnllama_jni*.so that MUST be present
  requiredLibAlignment: int       // minimum p_align of every PT_LOAD of every shipped library
  requiredSymbols: SymbolRule[]   // per-library exported-symbol assertions

AssetRequirement
  scope: "artifact"               // refusal hook, not an assertion (§4g)
  required: string[]              // non-lib payload the backend needs, from the artifact root
  elfMachine: int                 // 164 (EM_QDSP6)
  usableByAbis: string[]          // ABIs whose shipped libraries can load them

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
- **`p_align`** — the alignment field of an ELF program header. Android 15+ requires every `PT_LOAD`
  of a shared library to be 16 KB-aligned on a 16 KB-page device.
- **Building job** — a job running an Android gradle `assemble*`/`bundle*` task, directly or through
  a fastlane lane that does. **Gate step** — a step running `verify-android-payload.js` with
  `--apk`/`--aab`. **Publishing step** — the five classifications in §4h.

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

| ABI | Required libraries | Minimum `p_align` |
| --- | --- | --- |
| `arm64-v8a` | `librnllama.so`, `librnllama_v8.so`, `librnllama_v8_2.so`, `librnllama_v8_2_dotprod.so`, `librnllama_v8_2_dotprod_i8mm.so`, `librnllama_v8_2_dotprod_i8mm_hexagon_opencl.so` — each with its `librnllama_jni*.so` wrapper | 16384 |
| `x86_64` | `librnllama.so`, `librnllama_x86_64.so` — each with its wrapper | 16384 |

The DSP assets — `assets/ggml-hexagon/libggml-htp-v{73,75,79,81}.so` — are required once per
artifact, not per ABI: Android packages `assets/` once, so an ABI could never have had its own set
(§4g). The alignment requirement is per ABI and covers **every** shipped library, not only the ones
named above (§4f).

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

**A workflow that builds an Android APK builds it with the same native payload as the release build,
and asserts that it did. Test builds may add instrumentation; they may never subtract capability
(D14).** There is no exemption for "this artifact is not published".

The e2e APK *legitimately* differs from the release APK: a different flavor and application id, the
automation bridge, `debuggable=true` so `adb run-as` works, dummy signing. Those are additive and
expected. What must not differ is the production surface — the same libraries, the same variant set,
the same DSP assets, the same backend symbols. So `e2e-tests.yml` provisions the Hexagon SDK, applies
the allowlist and runs the payload gate exactly as the publishing jobs do. The manifest describes only
that production surface, and the native payload does not vary by flavor, so it applies to
`assembleE2eReleaseE2e` unchanged. If some payload-relevant difference is ever genuinely correct — an
ABI that build does not need, say — it belongs in a job-specific manifest input, never in skipping the
assertion.

**This completes an invariant that already had one half.** `ci.yml`'s DCE check asserts the *prod*
artifact carries **no test code**; the e2e payload gate asserts the *test* artifact carries **all the
production payload**. Same invariant, opposite directions — which is why the two artifact-assertion
mechanisms are not duplicates and are deliberately not merged (D12). Each would be blind to what the
other catches: DCE says nothing about a missing backend, and the payload gate says nothing about
automation markers leaking into a release.

**Why the backend rule names Hexagon and not OpenCL.** OpenCL cannot degrade the same way. Its sources
and `-DLM_GGML_USE_OPENCL` are added *outside* the `if (EXISTS ${OPENCL_STUB})` guard
(`rnllama/CMakeLists.txt:437-459`), and its `.dynsym` entries are undefined imports, so a missing
`libOpenCL.so` fails loudly at link time. Hexagon's sources are added *inside* its guard — which is
exactly why its absence is silent and needs an artifact-level assertion.

### 4c. The payload gate (C)

1. One implementation (`scripts/verify-android-payload.js`), one manifest, consumed by every workflow
   that produces a shippable Android artifact, and runnable locally against a local build. No workflow
   restates a rule inline.
2. It runs **before any upload, publish, or release step**, in every such workflow, and having
   examined the very artifact that step publishes — asserted by a test, not by review (§4h).
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
   | `requiredSymbols` | at least one rule overall; and for any ABI declaring a `_hexagon` library, at least one rule **whose `lib` is that accelerator library itself** — not merely a rule, and not its JNI wrapper, whose name also contains `_hexagon` but which is a shim exporting stable `Java_*` entry points and none of the backend symbols |
   | each symbol rule | `mustExport` non-empty, **or** an `expectedMatchCount` with a non-empty `pattern` and `count > 0` |
   | `nativeLibsMappedInPlace` | must be exactly `true`. It records that the platform maps libraries out of the APK, which is what makes both the offset rule and the stored requirement apply; `false` would retire them both in one word |
   | `assets` | the block must exist |
   | `abis[].requiredAssets` / `requiredAssetElfMachine` | **refused.** Nothing reads them since the assets moved to the top-level block, and a key nothing reads is worse than a missing one: an editor working from the old shape declares assets, is never told they are ignored, and gets a green gate. The base version's shape guard went away with the key it guarded, so even `requiredAssets: "not even a list"` passed |
   | `assets.scope` | `"artifact"` and nothing else — a refusal hook, counted as no check (D21) |
   | `assets.required` | non-empty, and each entry must be an ELF object for `assets.elfMachine` (EM_QDSP6) — presence by filename is not enough |
   | `assets.elfMachine` | an integer |
   | `assets.usableByAbis` | present, and naming only ABIs the manifest declares — an ABI nobody declared is never enumerated, so naming one is a claim the check never reaches |
   | `requiredLibAlignment` | present per ABI, an integer power of two, **≥ 16384** (D20) |
   | accelerator ABI | at least one ABI must declare a real accelerator library, or every floor below is satisfied vacuously |
   | derived allowlist | non-empty |

   The symbol floor is conditional on the ABI carrying an accelerator, since an ABI without one
   legitimately declares none. The asset floors are unconditional, and safe to be so **only** because
   the accelerator-ABI guard above them refuses a manifest declaring no accelerator at all; that
   guard keys off `abis[].requiredLibs` and survives the assets moving out of `abis[]` (scenario O).

   The alignment floor runs **last**, after every other manifest floor, so a manifest weakened in
   some other way is still refused with the message naming what it weakened.

   **Ground truth for why the symbol rule carries so much weight:** the APK that shipped the
   regression contains **all 12 declared libraries and all 4 DSP assets**. Every other rule in the
   manifest passes on it. The symbol rule is the only load-bearing assertion, which is why each way of
   quietly disarming it — asserting nothing, demanding a count of zero, or pointing the rule at a
   different library — mattered more than it looked. The report prints the `assets:` row once per
   artifact, and a per-ABI usability row beside it — the summary line claims assets were checked, so
   what was checked has to be visible in the evidence rather than inferred from a pass.

   Six weakenings were **measured passing on real artifacts** before these floors existed: a rule
   that named the library and asserted nothing; a rule whose only demand was
   `{pattern: "hexagon", count: 0}`, which does not merely assert nothing but asserts the backend is
   *absent*, so the incident build satisfies it exactly; an emptied required-asset list, which passed
   an APK with **zero** DSP libraries — backend compiled in, dead on the device; and emptied arm64
   symbol rules while x86_64 still carried one. In every case the other rules were already
   *satisfied* by the bad build, so the emptied one was the only thing standing between it and a
   green pipeline. The last two were subtler: a rule pointing at the accelerator's own **JNI wrapper**,
   which satisfies a naive `_hexagon` name test, and a manifest declaring **no accelerator ABI at
   all**, which satisfies every conditional floor vacuously. Both passed the incident APK. Each is the kind of edit a dependency bump invites: a renamed
   `libggml-htp-v*.so` makes the asset rule fail, and emptying the list is the single edit that
   unblocks it.

   A repeated `--apk`/`--aab`/`--manifest` is refused for the same reason, as is `--print-variants`
   alongside an artifact.

   **The same drift problem applies to the SDK digest.** The provisioning action verifies a digest over
   a narrow subset of the SDK — the include roots CMake adds and the library it links — which is only
   sound while that subset still covers what llama.rn references. A widened include set would leave the
   digest green over a stale, narrower set, and on a cache hit the tarball digest is not there to catch
   it. `scripts/__tests__/hexagon-sdk-coverage.test.js` ties the two together, with a vacuity guard on
   both parses, in the same shape as the variant-ladder and DSP-asset ties.

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

Two alternatives were considered and rejected. Calling the gate from inside the lane would put the
ordering guarantee in Ruby statement order rather than the workflow graph, and the two workflows would
then invoke the gate differently.

A **Gradle verification task attached to the `assemble`/`bundle` output** looks stronger — it would
satisfy the ordering invariant by construction — but it **cannot reach the risk that matters**. The
release path's exposure spans two separate `fastlane` processes and a Play upload; a task bound to
`assemble`/`bundle` completes inside the first of them and has no way to gate what the second does.
It would secure the build and leave the upload exactly as unguarded as before. That it would also
block local release builds for a developer without the 673 MB SDK is a real cost, but it is the
secondary objection, not the reason.

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

### 4h-bis. The default is inverted inside a building job (C)

Rules R1a through R5 all answer the same question — *does this step publish?* — by recognising what
publishing looks like across free-form shell and arbitrary actions. That is a **blacklist over an
open set**, and it behaved like one: five review rounds produced five new spellings of a single
defect, each closing the ones someone had thought of. `uses:` branches, then command-line branches,
then composite actions, then a command-token pre-filter, then quote state spanning lines. The
finding was never about a fix; it was about the approach.

So inside a job that builds Android, the default is the other way round. **A step is a violation
unless something accounts for it**: it is the gate, or it classifies as a publisher (and then the
ordering rules apply to it), or its `uses:` is in the reviewed action allowlist, or it is named in
`ACCOUNTED_STEPS` with a reason and an assertion that holds. Nothing falls through to "nobody
looked at it".

This trades an impossible question for a finite one. Recognising every way a step might publish
cannot be completed; naming the steps this repository actually has can — **55** across the three
building jobs: 3 gate steps, 8 publishers, 17 allowlisted actions and 27 ordinary `run` steps.
`ACCOUNTED_STEPS` holds 58 rows, the extra three being the steps outside those jobs that the
suspicion net flags. Those counts are asserted, not described, because a count in a comment is a
claim nothing checks — and the first version of this paragraph had one wrong.

A new step costs a reviewed line whether or not it looks dangerous: `echo hello` is refused exactly
as `bash tools/ship.sh` is, because the point is that no judgement about the step's text is being
made.

**Being recognised is not an exemption, and neither is being unchanged.** Two things had to follow
before the inversion was real. First, classification as a publisher — or as the gate, or as an
allowlisted action — used to end the enquiry, which left the largest steps in the workflow outside
it: appending a line to `Push the release tag` moved nothing. Every step is accounted for now,
publishers and gates included. Second, and more important, **each row pins a digest of the step's
content**. The list of steps was closed while what a step contained stayed open, so an edit *inside*
an accounted step cost nothing, and each exemption's assertion could only refuse the transports
somebody had thought of — a census over 30 entries × 10 hostile appends left every assertion holding
for `gcloud storage cp`, `az storage blob upload`, `nc`, `ssh`, `python -m http.server` and plain
`cp`. With content pinned, all of those fail on the digest without anyone having anticipated them.
The transport predicates remain as a second line of defence and are no longer load-bearing.

**The pin covers the container and the delegate, not only the step.** Three boundaries, one argument
— a step's behaviour is decided by more than the step's own text:

- **The job and its workflow.** `defaults.run.shell` replaces the shell for every step in the job, so
  `bash -c "bash {0}; true"` makes each one exit 0 without touching any of them; a job-level `env`
  preloads a module into every `node`; `defaults.run.working-directory` moves the paths a script's
  flags name; `container` and `runs-on` decide the machine. Each building job therefore pins a digest
  of its own keys and its workflow's. Both Android jobs already carry a job-level `env:` block, so
  this was a one-line edit inside an existing one.
- **The Fastfiles.** `release.yml/build_android` — the job holding the keystore and the Play key —
  runs its entire build as 1,313 bytes of Ruby behind one `run: bundle exec fastlane
  build_android_release`. All three Fastfiles are pinned by content, and lane calls are followed
  **transitively**: a lane reached only through another lane is as much part of what the step does as
  the one it names.
- **The composite actions.** A composite is free-form shell behind one `uses:`, so reading it for
  transports would be the same enumeration; each `action.yml` carries a digest and `shipsNothing`
  stands behind it.

The digest is 96-bit and covers every key. It hashes the comment-stripped script, so rewording a
comment is not a change — adding or removing a comment *line* is, because stripping leaves the blank
line behind. What remains unpinned by construction: a shebang or `#define` inside a heredoc, which
`codeOf` removes before hashing.

**What is deliberately outside all of this**: the three rows with no digest — the iOS TestFlight
upload, the iOS build and the Weblate upload. They sit outside the Android building jobs, so the
inversion does not reach them and their assertions are the older, weaker instrument. A census of
hostile appends survives on them. That is scope, not oversight: they ship no Android payload, and the
gate this document describes is the Android one.

Two consequences worth stating. The suspicion net now applies **only outside** the building jobs,
where it remains the weaker instrument it always was — the inversion is strictly stronger and would
make it redundant there. And a publisher class that must name an artifact (everything except a tag
push) is refused when the parse can read **no** path out of it: an empty path set is otherwise
indistinguishable from a satisfied one.

`actions/upload-artifact` classifies whenever it carries a `path:`, not only when an `.apk`/`.aab`
can be read out of it. Conditioning the classification made the empty-resolution refusal unreachable
for the one class it was written for, and handed the step to an action allowlist that asserts
nothing about it — three committed report uploads sat in exactly that state, each under
`if: always()`. What a report upload legitimately ships is pinned instead as a short list of
**non-artifact upload paths**, asserted disjoint from `build/outputs`: a concrete filename that is
not an `.apk`/`.aab` is not thereby harmless, since `tar czf out/x.tgz …/apk` produces one.

The gate step's own shape is pinned the same way, for the same reason. Every way `bash -e` can be
made to report success for a failing command is a shell feature — `||`, a pipe, `&`, `!`,
`if`/`while`, `set +e` in four spellings, `trap … ERR`, another command after it on the same line —
and enumerating them leaked in three consecutive rounds. What the gate step is *permitted* to be is
one command, optionally preceded by `set -euo pipefail`, and its **key set** is pinned to `name` and
`run`: the script is only one of the things that decide what executes, and `env` can preload a
module, `working-directory` can move the paths the flags name. That is a list of two either way, and
all three gate steps already have that shape. The same two mechanisms operate one level up, at job
and workflow scope, which is why those are pinned too — naming them on the step alone was the gap.

### 4e. Hard invariants

- **I1 — declared payload**: every shipped Android artifact contains, for each ABI, at least every
  library and asset the manifest declares.
- **I2 — backend presence**: the hexagon variant defines `lm_ggml_backend_hexagon_reg` and
  `lm_ggml_backend_is_hexagon` in `.dynsym`.
- **I3 — evidence source**: backend presence is decided from `.dynsym` only.
- **I4 — instrument honesty**: a check that could not run fails; it never passes by absence. This
  applies to the gate's read paths and to the workflow's declaration assertions alike, and now to
  both new instruments: a library whose program headers cannot be read, or a workflow that cannot be
  parsed, fails.
- **I5 — gate precedes publication**: no upload/publish step runs before a passing gate **that
  examined the bytes being published**, in any workflow and inside any lane it invokes. Checked
  mechanically (§4h), not by review of the workflow graph.
- **I6 — mode is not evidence**: build mode is a cost and provenance choice. Correctness is asserted on
  the artifact, never inferred from the mode.
- **I7 — ladder coverage**: the compiled-variant allowlist contains every rung the ladder can select.
  A rung may be omitted only when it is **build-equivalent** to a retained rung — same `-march`, same
  source list, same compile definitions — or as a *named, costed* bet with the fall-through rung
  recorded. "Same `-march`" alone never qualifies.
- **I8 — page alignment**: every shipped `lib/<abi>/*.so` in a declared ABI has every `PT_LOAD` at
  `p_align >= 16384` and, in an APK, is **stored uncompressed** at a zip data offset that is a
  multiple of 16384. The app maps its libraries in place, so all three are required to load.
- **I9 — scope is structural**: a required path's scope is declared by where it sits in the manifest,
  never inferred from where it happens to be written.

### 4f. 16 KB page alignment (C)

Android 15+ refuses to load a shared library whose segments are not page-aligned on a 16 KB-page
device. The NDK already produces that alignment; this is a tripwire holding it, not a repair.

1. Every `lib/<abi>/*.so` entry of a **declared** ABI is read, and **two** properties are asserted,
   because a library needs both to load and neither is the Android 15 requirement on its own:
   every `PT_LOAD` at `p_align >= requiredLibAlignment` with a power-of-two `p_align`, and the
   entry's **zip data offset** at a multiple of the same number. The app ships
   `extractNativeLibs=false`, so bionic maps each library in place out of the archive; conforming
   segments at an unaligned offset still cannot be loaded. Asserting only the first certified
   exactly that artifact — the fixture repacked without zip padding, every ELF untouched, printed
   `PASS / EXIT=0` on 68/68 misaligned offsets.

   The offset is read from the archive's **local** header. `unzip -Z -v` reports the *central*
   directory's extra-field length, which is 0 for every library, while the padding that does the
   aligning lives in the local header and is whatever it took to reach the next page boundary — so
   the difference between the two is the entire field, and the magnitude varies per entry.

   Scoped to an **APK**, because an AAB is repackaged by bundletool on the way to the device:
   `p_align` survives that and is still checked there, and only the offset, which repackaging
   destroys, is dropped.

   **The subject set is named from the central directory, not from `unzip`.** Info-ZIP transliterates
   bytes it cannot render — a library it lists as `libevi+l.so` is `libevi\uFFFDl.so` decoded as
   UTF-8 — so a subject set taken from its listing and an index built from the directory disagree on
   exactly the entries whose naming is chosen freely. A deflated library under such a name passed the
   gate outright, with the report contradicting itself (`segment alignment: 13/13` beside
   `zip data offset: 12/12`) and nothing reading the contradiction. The two readings are now
   asserted to agree, the denominator is the whole subject set, and a name in one but not the other
   is instrument failure.

   *This was recorded here as unreachable in the previous round, on an argument that the two readings
   came from the same directory and could not differ. The argument was never tested. It is the same
   error as the deflated-entry premise before it, and both times the untested claim was the one that
   removed a defence.*

   **A deflated library is refused, not excused.** An earlier draft skipped deflated entries as
   "extracted at install" — a true statement about Android in general and a false one about this
   app. The manifest declares `nativeLibsMappedInPlace`, matching the `extractNativeLibs=false` that
   AGP injects from the `useLegacyPackaging=false` default, so nothing is extracted and a compressed
   `lib/*/*.so` cannot be loaded on **any** device, 16 KB-page or not. The skip excused the more
   serious of the two faults and was reachable: deflating every library left the gate printing
   `0/0 stored` and exit 0. The declaration is floored at `true`, so retiring the rule now means
   editing the manifest to claim the app extracts its libraries — a reviewed change, and a false
   one.

   The fixtures had to gain a stored-mode zip writer for this. `zip -q -r -X` deflates even
   incompressible data, so a stored-scoped rule would have had an **empty subject set across every
   existing fixture and passed having checked nothing** — the same defect as the rule it implements,
   one level up.
2. The subject is **every** shipped library, not only `requiredLibs` (D19): alignment is a property
   of what the platform loads, not of the llama.rn payload. Measured on the release APK: 68
   libraries — 38 arm64, 30 x86_64 — of which 52 are not `librnllama*`, all at `p_align` 16384. The
   whole scan costs **0.7 s** against a 233 MB artifact.
3. `assets.required` was never in the subject set, which is scoping rather than exclusion — the
   distinction still matters, because the four DSP assets are ELF32 `EM_QDSP6` objects at `p_align`
   **4096**, loaded by the DSP and not by Android. One floor spanning libraries and assets would fail
   the gate on a correct artifact.
4. The program-header reader handles **both ELF widths and both byte orders**, like `readElfMachine`
   and unlike `readDynsym`, which is ELF64-LE by assertion. It is a separate function for exactly
   that reason (scenario L).
5. Being a tripwire on what the toolchain already emits, it has to be shown capable of failing —
   against the artifact (scenario H) and against a weakened declaration (scenario N).

### 4g. Asset scope and usability (C)

Declaring artifact-scoped paths under an ABI is what invited the belief that they could be scoped to
one; they now sit in a top-level `assets` block (D22).

1. `assets.required` paths resolve from the artifact root, and the block's **position** is what makes
   that structural rather than implied (I9).
2. `assets.scope` admits only `"artifact"`. It is a **refusal hook, not an assertion** — it cannot
   fail except on a typo — and exists so a maintainer reaching for `"abi"` is refused with the reason
   rather than shipping a scope no packager delivers (D21).
3. **`usableByAbis` is checked against the artifact, never against the manifest** (D23). For each
   declared ABI, `lib/<abi>/` must contain a library that is a non-wrapper `_hexagon` variant **iff**
   that ABI is listed. The subject is the whole `lib/<abi>/` tree, not the "extra libraries"
   enumeration: the accelerator variant is itself in `requiredLibs`, so a set derived from the
   leftovers is empty for arm64 and would refuse a correct artifact. Measured: the unmodified release
   APK yields `[arm64-v8a]`; a hexagon variant appearing under `x86_64` yields `[arm64-v8a, x86_64]`
   and fails; arm64 reduced to its JNI wrapper yields `[]` and fails.
4. The report prints per-ABI usability, so the 2.84 MB of DSP assets that reach `x86_64` is a stated
   fact rather than an oversight (deferred cleanup 12).

**No supported mechanism scopes `assets/` to an ABI**, which is why the asked-for exclusion was
refused rather than deferred (D26). bundletool parses five directory-targeting keys — `countries`,
`group`, `lang`, `tcf`, `tier` — and no `abi` key; asset packs target min-SDK, device feature, tier,
texture format and country; AGP asset source sets are per flavor and build type; and `splits { abi }`
copies the whole asset tree into every split. The two mechanisms that would work — an ABI flavor
dimension, or an upstream llama.rn move of the HTP payload into `jniLibs` — cost more than the 1.2%
of artifact size at stake.

### 4h. No publish outruns the gate, mechanically (C)

`scripts/__tests__/android-publish-ordering.test.js` parses every `.github/workflows/*.yml` with
`js-yaml`, and the three Fastfiles by their explicit paths — `fastlane/`, `android/fastlane/`,
`ios/fastlane/`, never by glob, since a fourth ships under `vendor/bundle` wherever `bundle install`
has run and a glob count would be environment-dependent. `js-yaml` is declared in `devDependencies`
rather than relied on transitively; it was already resolved at the version the lockfile pins, so
declaring it left `yarn.lock` unchanged.

`release.yml/build_android` runs **no `gradlew` at all**, so that job's building-ness — and with it
every ordering rule over the release path — rests entirely on resolving the lane name its step
invokes. Lane names are therefore matched against the known set rather than by position, because
`fastlane <lane>`, `fastlane android <lane>` and `fastlane run <action>` are all valid here:
`android/fastlane/Fastfile` declares `default_platform :android`, so the platform-prefixed form
works, and a position-based parse silently resolved it to the platform instead and emptied the rule.
A cliff edge rather than a bypass — the building-job count fails first — but a sharp one.

Both files are read as **code, not commentary**: Ruby and shell both use `#`, and the upload lane's
own comment quotes `gradle(task: "bundle")` to explain why it does not build — read literally, that
comment makes the upload lane look like a build lane.

| Classification | Publishing step |
| --- | --- |
| `workflow-artifact` | `uses: actions/upload-artifact@*` whose `path` names an `.apk` or `.aab` |
| `play-upload` | a `run` reaching `upload_to_play_store`, directly or via a fastlane lane whose body does |
| `tag-push` | a `run` pushing a git **tag** — a `git push` carrying a refspec, as against the bare `git push` of the version bump |
| `github-release` | `uses: softprops/action-gh-release@*` |
| `gh-release-cli` | a `run` invoking `gh release create`/`upload` |

The rule and classification names below are the identifiers the test uses, so the doc and the code
cannot drift into two vocabularies.

**Rules.**

1. **R1a — ordering** (`violationsOfOrdering`). In every building job, each publishing step sits at a higher step index than
   some gate step in the same job.
2. **R1b — path identity, and no interposition** (`violationsOfPathIdentity`). Every artifact path a publishing step names must
   also be named by a gate step at a lower index in the same job, compared by basename (fastlane runs
   under `working-directory: android`, so roots legitimately differ). Ordering alone binds the gate
   to nothing: gating `--apk` while publishing the `.aab` is ordered and examines neither. And no step
   between that gate and the publish may name the artifact again — otherwise gate at *i*, rewrite at
   *i+1*, publish at *i+2* satisfies ordering and identity while the published bytes were never
   examined. The realistic accidental form is a post-gate `zipalign`, `apksigner` or re-sign step
   added to fix a signing problem.
3. **R2 — the gate must still be able to fail the job** (`violationsOfGateCanFail`). A gate step carries no `if:` at all, no
   `continue-on-error`, no `shell:` override; its `run` invokes the script as the **final** command,
   with no `||`, no pipe, no trailing `exit`, no `set +e`, and no `--manifest` (a test flag). Banning
   only `always()`/`failure()`/`cancelled()` would leave cheaper edits standing, and a *skipped* step
   is not a failed step, so R1a stays green while nothing is asserted. **The pipe is the likeliest of
   these**: no `shell:` key appears in any workflow, so every `run` executes under GitHub's default
   `bash -e {0}`, which does not set `pipefail`, and `… 2>&1 | tee gate.log` therefore exits with
   `tee`'s status. That is not a reach — `ci.yml` already pipes gradle through `tee` a few steps
   above, so a maintainer wanting the gate's output in a log writes the same line without thinking.
   The enumeration also covers the forms `bash -e` never reports a failure for: `&` (backgrounded),
   a leading `!`, and a gate wrapped in a single-line `if <gate>; then …; fi` or
   `while <gate>; do …; done` — each verified to exit 0 for a gate exiting 7. The multi-line `if`
   was already caught, so a check testing only for the script's *presence* rewarded collapsing it
   onto one line; the invocation must now **begin** the final command. `set +o errexit` is the same
   instruction as `set +e` spelled long, and the pattern read only the short form.

   **The mirror of this rule sat unwritten until review.** `if: always()` on a *publishing* step runs
   it on a build the gate has just refused, while its position in the job stays perfectly correct —
   on `release.yml` that is the AAB reaching Play Alpha, the tag pushed and the Release created. The
   idiom already appears three and seven lines above two of the uploads, so it is the natural thing
   to write there. This rule's own recorded reasoning — *a skipped step is not a failed step, so
   ordering stays green while nothing is asserted* — had been applied to the gate side and never to
   the publisher side. A publishing step in a gated job may now carry no `if:` mentioning
   `always()`, `failure()` or `cancelled()`; an ordinary branch conditional is untouched.
4. **R3 — cross-job** (`violationsOfCrossJobPublish`). A publishing step in a non-building job is refused unless the job obtains no
   Android build output: no `actions/download-artifact`, no `gh run download`, no `curl`/`wget`
   fetch, and no `actions/cache` restore whose `path` reaches a `build/outputs` directory. Named as
   four mechanisms because absence-of-`download-artifact` misses the other three, and `actions/cache`
   is already in use.
5. **R4** (`violationsOfLaneSplit`) — no fastlane lane both builds and publishes an Android artifact. D13's split is invisible
   to the workflow graph, so only this rule holds it.
6. **R5 — suspicion net** (`violationsOfSuspicionNet`), **outside the building jobs only.** Every step
   whose `run` matches a broad publish-or-fetch pattern
   (`upload|publish|release|git push|gh |curl|wget|scp|rsync|aws s3`) or whose `uses:` is outside the
   reviewed action allowlist must be either classified as one of the publishers above or listed in
   `ACCOUNTED_STEPS` with its reason **and** the assertion that makes the reason checkable.
7. **R6 — every step accounted for** (`violationsOfUnaccountedSteps`), **inside them.** A step in a
   building job that is not the gate, not a publisher, not an allowlisted action and not named in
   `ACCOUNTED_STEPS` is a **violation**. See "The default is inverted" below — this is the rule the
   other five rest on.

**Both exemption surfaces carry the same floor** — a reason plus a machine-checked assertion, and a
stale entry fails rather than lying dormant. That covers the action allowlist as much as
`NON_PUBLISHERS`: otherwise the cheapest way to publish through a new third-party action is to add
its name. The allowlist is keyed by the full `uses:` value including its version, so an action bump
costs a reviewed edit; there are 14 distinct values today, 12 third-party and 2 local composite.

**An exemption assertion must constrain the step, and must be falsifiable.** Two ways of getting
that wrong were found by review and both are closed:

- **Constraining the job instead of the step.** The three `Build …` entries first asserted only that
  a gate step follows them in the same job — true of the *job*, so adding `curl -T`, `wget
  --post-file`, `scp` or `gh api` to the build step itself left every rule green. They now also
  assert that the step names no Android artifact and carries no transport; measured on the committed
  files, all three already satisfied both, so the strengthening cost nothing. The transport pattern
  gained `curl`, `wget` and `gh api` — the DCE check cannot use "names no artifact", since it names
  the APK by design, so a widened transport pattern is its only defence.
- **An assertion no input can falsify.** Every assertion that reads a step is applied to one
  adversarial step — it names the APK, sends it out, pushes a tag — and **must return false**. The
  composites are held to the same standard through their own source rather than the step. This is
  the floor that caught the second problem below, and it is the mechanism to add to whenever a new
  exemption appears.
- **An assertion that decides on the job and discards its step.** One probe job was not enough: an
  assertion reading only the job is falsified by an adversarial *job* without ever looking at the
  step it was handed, and reads as sound. `runsNoAndroidGradle` did exactly that, so a `curl -T`
  appended to the iOS upload step left it exempt and every rule at zero. The probe now runs a second
  job that satisfies **every** job-level predicate — builds nothing, gate below the step — where only
  the step half can carry the assertion. Each such assertion is now paired with a step-reading one.
- **A composite's `with:` block.** `shipsNothing` read `run` and `uses` and dropped `with` entirely,
  while its step-level twin went through `stepText`, which includes it. A composite whose only step
  was `uses: actions/upload-artifact@v4` with `path: …apk` returned *ships nothing* — and its probe
  exercised four `run:` spellings and no `uses:` spellings, so half of what the function read had
  never been shown able to fail it. Both composites run in the job holding the keystore and the Play
  key. It now reads all three fields and refuses an inner publishing action outright.

**Two allowlist entries carry no assertion of their own, and say so.** For
`actions/upload-artifact@v4` and `softprops/action-gh-release@v1`, whether a step is a publisher is
decided by the action name and its own path — so any assertion phrased over the step restates its
own lookup key and cannot fail. Both originally had one, and both were tautologies. They now declare
`carriedBy: 'ordering and path identity'` instead, and negative tests prove the carrying is real:
an `upload-artifact` step and a release-action step, each shipping ungated bytes, are caught by the
path-identity rule. Only those two names may stand on `carriedBy`; a third costs a reviewed edit.
Writing a tautology and labelling it a check is the same shape as the six manifest holes, so it is
better to name the rule that actually holds the property than to manufacture a local one.

**A path the parse cannot resolve is refused, not skipped.** The classifier first read only literal
`.apk`/`.aab` filenames, so a publishing step whose `path` was a **glob**
(`…/apk/**/*.apk`), a **bare directory** (`…/apk/prod/release/`) or an **expression**
(`${{ env.APK_PATH }}`) resolved to no artifact at all — and, resolving to none, was not classified
as a publisher. Measured: such a step spliced *above* the gate in `ci.yml/build-android` — an APK
published before the gate had run — was invisible to every rule at once. The suspicion net could not
recover it either, because the allowlist exempts the action by name whatever its `with` says.

Those spellings now classify as a publisher carrying an **unresolvable** path, which no gate step
can ever be shown to have examined, so ordering and path identity both refuse it. In a `with:` path
field the whole value is a path, so the test is simply *is this a concrete filename* — which also
catches `dist/`, `artifacts/` and `android/app/release/`, none of which mention `build/outputs` and
all of which classified as **no publisher at all** while that was the key. The carrying probe runs
over every spelling rather than the one that already worked: a rule keyed on literal filenames holds
only for the spelling it can read. Nothing committed moves — today's `upload-artifact` paths and the
single `files:` are all explicit filenames.

**Classification is additive, and a path list is read entry by entry.** Both were first-match, and
both hid a second artifact behind the first one recognised: a path naming the gated APK *and* a glob
reaching the bundle reported only the APK, and `gh release upload <dir>` appended to the Play-upload
step was swallowed whole by the `upload_to_play_store` branch, since the classifier returned on its
first hit. A step can be two publishers at once, and one path field can name a file the gate read
beside one it never saw.

**The same fallback applies to the command-line publishers**, which name their paths as arguments
rather than in a `with:` block. `gh release create v1.0.0 dist/*.apk` was *classified* — so ordering
held it on position — while path identity had an empty path list and therefore nothing to compare:
**vacuous, which reads exactly like satisfied**. Below the gate it was unguarded outright. Both CLI
branches now take the same treatment, and the negative cases assert path identity fires, not merely
ordering. The Fastfile's `aab:` literal is unaffected and still resolves to `app-prod-release.aab`;
it is separately pinned by the lane test, so replacing it with a variable fails there first.

Refusing the expression form goes one step past what the classifier can prove: `${{ … }}` may well
name something harmless. It fails closed on purpose. A future step that legitimately publishes
through an expression costs a reviewed exemption, which is the same price as a fourth building job
and the right direction for a rule whose whole subject is bytes nobody examined. The clause is read
differently in the two places, deliberately: in a `with:` path field the whole value is the path, so
any expression hides one; in a shell command a `${{ }}` is as likely to be a tag or a secret — `gh
release create v1.0.0` publishes no binary at all — so only an expression sitting against an
`.apk`/`.aab` counts there.

`NON_PUBLISHERS` holds 14 entries, not the three the design predicted. The pattern is deliberately
broader than the concept: `release` matches `pocketpal-release-key.keystore`, `assembleProdRelease`
and `app-prod-release.apk`, so the keystore steps, the build steps, the DCE check and the gate steps
themselves are all caught. Each carries an assertion worth having rather than a restatement of
"this is not a publisher" — the build steps assert that a gate step follows them in the same job, the
bump step asserts that its `git push` carries no refspec, the iOS upload asserts that no iOS lane
publishes to Play, and the gate steps assert they are still gate steps, which puts them under R2
instead. Narrowing the pattern to make the count match would have been the cheaper edit and the
weaker net.

**One committed file changed to satisfy the rules rather than be exempted from them.** `ci.yml`'s DCE
sanity check reads the built APK by name and sat between the gate and the upload, which R1b's
no-interposition clause refuses. It reads the artifact and does not rewrite it, so an exemption was
available; moving it above the gate was preferred, because the invariant then holds rather than
having a hole with a note attached. The gate is now the last step to name the APK before it is
uploaded.

That reorder has one benign side effect worth knowing before it is met in a log. Both steps are
unconditional and the job halts at the first failure, so a **DCE failure now stops the gate from
running**, and the `if: always()` report upload finds no `payload-report.txt` (`if-no-files-found:
ignore` swallows it silently). Before the move, a DCE failure still left a payload report behind.
That is a swap of diagnostic coverage, not a weakening of the gate — the two checks are independent
and either one failing blocks the upload either way. Everything else about the job is unchanged:
same `steps:` list, same `needs:`, no `if:` added or removed, and gate → report upload → APK upload
still in that order.

**Vacuity guards**, in the shape the ladder-coverage test already uses:

- **V1** every workflow parses to at least one job with a non-empty `steps` array; the four known
  filenames are present; a newly-globbed file is parsed, never exempted.
- **V2** exactly **three** building jobs — `release.yml/build_android`, `ci.yml/build-android`,
  `e2e-tests.yml/build-android` — each with at least one gate step. A legitimate new Android build
  job costs a reviewed edit to this list, which is the intended price: an ungated fourth one fails
  here before R1a is reached.
- **V3** the three `release.yml` publishing steps are found **by name** — Play upload, tag push,
  GitHub Release — as a positive control on the classifier. Two of the three resolve to a path R1b can
  compare; the tag push names no artifact, and R1b is properly vacuous for it.
- **V4** the suspicion net matches more than zero steps, and no `NON_PUBLISHERS` entry and no
  allowlist entry goes unmatched.
- **V5** exactly two lanes in `android/fastlane/Fastfile`, with `gradle(` in the build lane and
  `upload_to_play_store` plus an `aab:` literal in the upload lane.

**Every rule is exercised against a deliberately broken in-memory copy of the parse**, never against
the committed files. A rule that has only ever been seen passing is not known to be capable of
failing, which is exactly how the six manifest weakenings became possible.

---

## 5. Single-writer rule

| Thing | Single determinant |
| --- | --- |
| effective Android build mode | `ORG_GRADLE_PROJECT_rnllamaBuildFromSource` set by the workflow → `$GRADLE_USER_HOME/gradle.properties` → `node_modules/llama.rn/android/gradle.properties`. **Never** `android/gradle.properties`. The middle rung is live: `release.yml` sets `GRADLE_USER_HOME` to `${{ runner.temp }}/.gradle` and `setup-java` caches it, so that variable belongs on the *build* step of the split lane |
| variants compiled | `rnllamaVariants` project property → `-DRNLLAMA_ANDROID_VARIANTS`, derived from the manifest |
| Hexagon backend compiled in | `HEXAGON_SDK_ROOT` + `HEXAGON_TOOLS_ROOT` reaching a tree containing `libcdsprpc.so` |
| DSP assets in the artifact | llama.rn's `syncRNLlamaHtpAssets`, sourced from `node_modules/llama.rn/bin/arm64-v8a` |
| required payload | the committed manifest |
| minimum library alignment | `abis[].requiredLibAlignment` (D6), floored at 16384 by the script (D20) |
| where required assets resolve from | the `assets` block's position in the manifest (D22) |
| which ABIs can load the assets | the **artifact**: `lib/<abi>/` carrying a non-wrapper `_hexagon` library, asserted equal to `usableByAbis` (D23) |
| publish ordering and path identity | the committed workflow and Fastfile text, asserted by one test (§4h) |
| what the Play upload ships | the `aab:` path passed explicitly by `upload_android_alpha` (`Fastfile`) |
| what the payload gate reads | the `--aab` path in `release.yml` |

The last two rows are the one place the lane split traded a single determinant for two: the path is now
written in both `release.yml` and the `Fastfile`, and they must agree. A fresh runner makes divergence
**fail closed** — the gate reads a path that does not exist (instrument honesty) or supply's
`verify_block` rejects a missing `aab:` — so this is recorded rather than defended with a check. It
would only fail open on a dirty runner holding a stale bundle at the other path.

**Two declarations are asserted separately, because they are not the same problem.** Both reach gradle
only through the environment and both used to fail silently, and the gate sees neither:

- **Allowlist — asserted from the build log.** The build is teed to `android/android-build.log` and a
  separate step greps for `Building rnllama variants: <the exact list>`. `build.gradle:155-158` reads
  the value with `project.findProperty("rnllamaVariants")`, which is **route-agnostic** — it would
  equally read a properties file or `-P`. So the printed line proves only that *a project property of
  that name reached the subproject*. It proves the environment route specifically because
  `rnllamaVariants` is defined in **no** properties file anywhere — not llama.rn's, not ours, not the
  root (verified by grep, with `reactNativeArchitectures` as the positive control) — so the
  environment is currently the only way it can arrive.

  **That is contingent, and it is the design's only live proof that the env → gradle route works.** If
  anyone ever adds `rnllamaVariants` to a properties file, this assertion keeps passing while silently
  no longer proving transport. Treat adding it as a change to the verification, not just to a default.

  An unarrived allowlist builds all seven arm64 variants, which §4c.6 would pass as permitted extras.
  The grep is also a *substring* match, so it proves the declared list was reported, not that the built
  set is exactly it — extras are permitted by design and the payload gate is what reports them. The
  step's message says so.
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

Lettering continues H–Q. There is no J: the case it held became edge case 9t.

### H. A library regresses below 16 KB
```
lib/arm64-v8a/librnllama_v8.so has a PT_LOAD at p_align 4096
─────
gate fails on I8, naming the entry, the segment alignment and the declared floor
```

### H2. The archive is repacked, losing alignment or compressing the libraries
```
every ELF untouched and conforming; libraries land on arbitrary offsets, or are deflated
─────
segment alignment still reports 68/68; the archive-side half of I8 fails, naming the
entry and either the byte it begins at or that it is compressed at all. A deflated
library is unloadable on every device, not only 16 KB ones, so it is refused too
```

### I. A publishing step is moved above the gate
```
release.yml — "Upload Android app to Alpha track" precedes "Verify the Android payload"
─────
R1a fails, naming the job, the step and the index it publishes at
```

### K. The fastlane lanes are re-merged
```
build_android_release regains upload_to_play_store
─────
R4 fails; the workflow graph still looks correctly ordered, which is why R4 exists
```

### L. The program-header reader accepts ELF32
```
assets/ggml-hexagon/libggml-htp-v73.so — ELF32 LE, EM_QDSP6, PT_LOAD p_align 4096
─────
reader returns [4096, 4096]; one that had copied readDynsym's ELF64-LE guard throws instead
```

### M. The arm64 assets survive — positive evidence, not absence of failure
```
the release APK, unmodified (233,443,745 bytes, built from the merged payload-gate code)
─────
assets 4/4 present, all EM_QDSP6; usableByAbis ≡ {arm64-v8a}, read from the lib/ trees;
16 rnllama libraries (12 arm64 + 4 x86_64); 68/68 libraries at p_align >= 16384; exit 0 in 0.76 s
```

### N. The alignment declaration is weakened
```
manifest lowers arm64-v8a requiredLibAlignment to 4096
─────
gate refuses the manifest before opening any artifact (D20)
```

### O. The accelerator guard survives the assets restructure
```
assets{} populated, but no ABI declares a non-wrapper _hexagon library
─────
still refused by the accelerator-ABI guard — the guard was relocated past, not orphaned
```

### P. A publisher ships bytes the gate never examined
```
ci.yml gains a bundle build and a Play upload; the gate still passes --apk only
─────
R1a passes (ordered); R1b fails — no gate step below it named the .aab basename
```

### Q. The gate is neutered in place
```
"Verify the Android payload" gains `if: false`, a trailing `|| true`,
or `… 2>&1 | tee gate.log` (which exits with tee's status under the default bash -e)
─────
R2 fails on each; a skipped, suppressed or piped gate would keep R1a green
```

---

## 7. Signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `hexagonPresent` | `llama.rn/android/build.gradle:145` | gradle → CMake args | both SDK and tools dirs exist on the runner |
| `HEXAGON_SDK_AVAILABLE` | `rnllama/CMakeLists.txt:168-178` | the variant's source list | above ∧ `libcdsprpc.so` exists |
| `RNLLAMA_BUILD_FROM_SOURCE` | `-DRNLLAMA_BUILD_FROM_SOURCE` from `build.gradle:148` | both CMake entry points | build mode is from-source |
| `Building rnllama variants: …` | `build.gradle:155-158` (`println`) | the workflow's allowlist assertion | the property arrived by the `ORG_GRADLE_PROJECT_` route |
| manifest conformance | the payload gate | the workflow's publish step | I1–I4, I8 and I9 hold on the produced artifact |
| publish ordering | the committed workflow and Fastfile text | `android-publish-ordering.test.js` | I5 holds across every workflow and lane |

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
| D12 | The payload gate does not absorb the DCE check | Opposite directions of one invariant: DCE says prod carries no test code, the gate says a build carries all production payload |
| D13 | Split the fastlane release lane; gate between build and upload | A gate the publish step can outrun is not a gate |
| D14 | Every Android APK build carries the release's native payload and asserts it; test builds may add instrumentation, never subtract capability | A build used to validate a release cannot be missing what the release has |
| D15 | Push the release tag after the gate, not after the version bump | A failed gate should leave no tag to reuse or delete |
| D16 | Set the full ccache env, not just dir and size | The NDK is reinstalled per run, so `compiler_check=mtime` would miss on everything and read as cold rather than misconfigured |
| D17 | No ccache on the release path | Only a prefix restore could ever hit there, and that links objects of unreviewed provenance into the shipped artifact |
| D18 | Pin the Hexagon SDK by content, not by tag | A third party redistributes it without checksums, and a tag names a mutable asset |
| D19 | Alignment is checked on every shipped library, not only the required ones | The platform loads all of them; the whole scan costs 0.7 s |
| D20 | The 16384 floor is a script constant the manifest cannot undercut | Otherwise a weaker declaration is the cheapest edit that unblocks a build |
| D21 | `assets.scope` is a refusal hook, counted as no check | One legal value cannot fail; structure carries I9 |
| D22 | Assets move to a top-level `assets` block | Declaring artifact-scoped paths under an ABI invited exactly this bug |
| D23 | `usableByAbis` is asserted against the shipped `lib/` trees | Equality with a value derived from the same document is vacuous |
| D24 | Ordering is checked as order **and** path identity | An ordered gate that examined other bytes proves nothing |
| D25 | Both exemption surfaces need a reason plus a checked assertion | An asserted exemption is the hole the payload work kept finding |
| D26 | The x86_64 asset exclusion is refused, not deferred silently | Measured impossible; the alternatives cost more than the 1.2% at stake |

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

**`release.yml` runs no ccache, deliberately (D17).** Before this contract the shipped native libraries
came from the npm tarball, integrity-pinned in `yarn.lock`; now they are compiled, and compilation can
reuse cached objects. The ccache key is the commit SHA and a release builds a fresh version-bump commit,
so the exact key can never hit — the *only* way ccache could help a release is the `ccache-android-`
prefix restore, i.e. linking objects of unreviewed provenance into the artifact that ships. GitHub scopes
cache **writes** per ref, so an unprivileged fork cannot poison what a `main` run restores; the residual
exposure is that a transient compromise of a privileged run becomes a persistent one until the entry is
evicted. Since `release.yml` also caches no `.cxx` tree, the choice was binary — accept that on the
shipped path, or get nothing from ccache there. Removed: it costs build minutes on the least frequent
workflow, and it frees a ~850 MB entry from a cache budget already over cap. `ci.yml` keeps ccache; its
artifacts are never published.

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
| 9l | `e2e-tests.yml` Android build | Treated exactly as a publishing job: SDK provisioned, allowlist applied and asserted, payload gated before the APK is uploaded. The earlier exemption was wrong twice over — the APK's purpose is to exercise the release's production payload, and e2e runs on **real devices** including a Snapdragon 8 Gen 2 (`e2e/baselines/benchmark/samsung-s23.json`), the one SoC family `isHexagonSupported()` accepts. Excluding the SDK there blinded the only place on-device Hexagon behaviour could be observed before release |
| 9m | `RNLLAMA_SKIP_POSTINSTALL=1` on the release Android job | Safe: from-source ignores the downloaded `jniLibs` and that job builds no iOS target. If the mode declaration ever failed, the absent `jniLibs` would drop variants and the gate would fail on I1 — loudly. Not set on `ci.yml`, whose Linux `node_modules` cache is shared with `build-and-test` |
| 9n | A library has zero `PT_LOAD` segments | Instrument failure (I4), not a pass — a stripped or synthetic object proves nothing about its alignment |
| 9o | `p_align` is 65536 | Passes: the rule is `>= declared`, and a larger page size conforms |
| 9p | x86_64 stops being 16 KB-aligned upstream | Gate fails. No platform rule requires it there, so this is a tripwire; the fix is a reviewed schema change, never a lowered number |
| 9q | A step adds an unrecognised `uses:` | R5 refuses it until it is classified or allowlisted with a checkable assertion |
| 9r | A publishing step names a path built in another job | R3: refused unless the job obtains no Android build output by any of the four named mechanisms |
| 9s | Two artifacts, one gate step | R1b holds only if that step names both basenames — the `release.yml` shape today |
| 9t | A new workflow builds and publishes an Android APK with no gate | Parsed by V1; **V2 fails first**, on a fourth building job, before R1a/R1b are reached. A legitimate new build job costs a reviewed edit to V2's list |

---

## 10. What this contract costs, and what is still unproven

**Build time.** Measured on `ubuntu-latest` `build-android`: cold (all three caches miss) **≈ 44 min**,
warm (all three restore) **≈ 23 min**, against thresholds of 75 and 35 min set before the first run and
a 21 min pre-regression prebuilt baseline. The caches are worth roughly half the wall clock: with the
`.cxx` tree restored, ninja drops cacheable compiler invocations by about 85%, and ccache then serves
essentially all of the remainder as *direct* hits. That direct-hit rate depends on
`CCACHE_COMPILERCHECK=content` and the `CCACHE_SLOPPINESS` list — the NDK is reinstalled every run and
`yarn install` rewrites mtimes under `node_modules`, so at ccache's defaults nearly every object would
miss, and it would read as a cold cache rather than as a misconfigured one. Provisioning the SDK itself
costs well under a minute.

Missing either threshold reopens the allowlist (deferred cleanup 6) or the escape hatch (§4d); it does
not silently become the new normal.

**The e2e build costs nothing measurable to bring up to parity.** Measured on `e2e-tests.yml`,
`ubuntu-latest`: **48.9 min** with the SDK provisioned and the payload gated, against **54.3 min** for
the immediately preceding run of the same branch without them, and 57.1 min on `main` before the
variant allowlist existed. The SDK is cached under an immutable key and the allowlist already applied
there, so the added work is one more variant's backend compile; the difference between those runs is
within GitHub runner variance, and there is certainly no meaningful increase to trade against.

**The gate's instrument is calibrated, not trusted.** Its in-process ELF reader was cross-checked
against the NDK's `llvm-nm -D | grep -ci hexagon` on two real artifacts — a backend-less build (6458
`.dynsym` entries, 0 hexagon matches) and a sound one (6527 entries, 16 matches) — with both readings
agreeing exactly and both required symbols reported as *defined*. Re-run that cross-check if the reader
is ever changed.

**The program-header reader is cross-checked against an external oracle too.** The oracle is not
`readelf` — macOS ships none, which is the same reason the reader is in-process at all — but the
NDK's own `llvm-readelf`, under `$ANDROID_HOME/ndk/27.3.13750724/`. All **72** `.so` entries of the
release APK (68 libraries + 4 DSP assets) were read with it and with a second, independently written
reader: **zero mismatches** on segment type and `p_align`. The test's synthetic builders were put
through the same oracle, including the ELF32 big-endian shape that has no real object behind it —
which is the case a hand-rolled reader is most likely to get wrong and least likely to notice.

Do not re-open this as unknown. If the reader changes, re-run that comparison; the NDK path above is
where the oracle lives, and it is present on any machine that can build the app at all.

**Stop condition, for any future repeat of this work.** If the two named symbols do not go from
**absent to present** in a CI-produced artifact when the SDK is added, the diagnosis is wrong — stop
and report rather than proceeding. A count other than the declared one *with both symbols present* is
**not** a stop: from-source and upstream's standalone build need not export identically, since LTO and
visibility differ. That is scenario E, and it is re-declared in the PR that causes it.

**What no pre-merge run can prove.** `release.yml` is `workflow_dispatch` and would bump the version,
push a tag and upload to Play, so it cannot be rehearsed. The lane split, the gate's position between
build and upload, the AAB path and the moved tag push are therefore verified by reading only. Residual
risk is bounded in the safe direction: a lane-name or path error fails *before* `upload_to_play_store`,
and supply's `verify_block` rejects a wrong `aab:` path.

> **On-device confirmation is now reachable before release.** `e2e-tests.yml` builds with the SDK and
> is gated, and the fleet includes a Snapdragon 8 Gen 2, so an e2e run on that device is the first
> opportunity to observe the backend actually engaging rather than merely being present.
>
> **Live obligation: the first release run after this landed must be watched**, and the backend
> confirmed on a real device. Two separate reasons:
>
> - The upload lane and the moved tag push have no pre-merge proof.
> - **Everything here proves the backend is *present in the shipped library*, not that it *engages on a
>   device*.** `RNLlama.java`'s `isHexagonSupported()` gates the backend on Snapdragon 8-series SoCs,
>   and nothing in CI can observe that — no emulator has a DSP, and the payload gate reads `.dynsym`,
>   not runtime behaviour. Presence is necessary and was what regressed; it is not sufficient.
>   Confirming engagement needs a real 8-series device.
>
> Remove this note once a release has gone through cleanly and a device has been checked.

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
10. ~~I5 is the only invariant enforced by prose rather than a check.~~ **Closed.** §4h mechanises
    it, in the shape this entry predicted and then some: ordering, path identity, no interposition,
    and the gate's own ability to fail.
11. ~~The payload gate only inspects the ABIs the manifest names, and is silent about an undeclared
    `lib/<abi>/` tree.~~ **Was already wrong when written, and is corrected here.** The gate
    enumerates the shipped ABI trees, reports them, and fails loudly on one the manifest does not
    declare (`verify-android-payload.js`, the `UNDECLARED` branch of `checkArtifact`; test *fails on
    an ABI tree the manifest never declared*). What remains true is only the premise: the manifest
    still describes the ABIs it names, so an undeclared tree is refused rather than inspected.
12. **The DSP assets reach `x86_64` devices** — 2,836,288 bytes (2.84 MB / 2.70 MiB) of a 233 MB
    artifact, 1.2%, for an ABI that can never load them. Refused rather than fixed (D26): no
    supported toolchain mechanism scopes `assets/` by ABI, and the two that would work — an ABI
    flavor dimension, or an upstream llama.rn move of the HTP payload into `jniLibs` — cost more than
    the saving. `usableByAbis` makes the fact visible in every report; the disposition is the
    requester's.
13. ~~Zip-entry alignment is not checked.~~ **Closed for the case that ships, and it was not
    cosmetic.** Both halves of 16 KB compatibility are now asserted (I8), and asserting only the
    first certified an artifact that cannot load: the fixture repacked without zip padding, every
    ELF untouched, printed `PASS / EXIT=0` on 68/68 misaligned data offsets. What remains outside
    the subject set is only the AAB, which bundletool repackages on the way to the device. A deflated
    library is **not** outside it: this app maps its libraries in place, so a compressed one is
    unloadable everywhere and is refused. Nor is a library whose name the entry listing and the
    central directory spell differently — that is instrument failure, not an exclusion.
14. **The ordering test sees only committed text.** A publish through a third-party action whose name
    reveals nothing is caught by R5's allowlist floor, not by understanding. The irreducible
    remainder of R1b's no-interposition clause is the same shape: the parse reads step text, not
    build semantics, so a step that rewrites the artifact without naming its path — through a
    variable, a `working-directory`-relative form, or a script it invokes — is not seen. I5's claim
    is therefore "the gate examined the bytes at that path, and nothing named it after", not a proof
    of byte identity at publish time.

    **The same remainder limits the exemption assertions**, and the widened transport pattern does
    not close it: a step that assigns the artifact path to a shell variable and then sends `"$APK"`
    somewhere defeats the artifact-naming half, and a transport invoked from a script the step calls
    defeats the transport half. What the assertions do buy is that the *cheap, thoughtless* version —
    a literal `curl -T …app-prod-release.apk` appended to a build step — fails. Deliberate
    exfiltration through an indirection is out of reach of a text parse and is not claimed.

    **The unresolvable-path fallback is bounded differently now, and more tightly.** In a `with:`
    path field the whole value is a path, so *anything* that is not a concrete filename counts —
    `dist/`, `artifacts/` and `android/app/release/` included, which keying on `build/outputs` did
    not catch. In a shell command only the tokens that reach a build output or carry an `.apk`/`.aab`
    are read that way, because most of a command's words are not paths. What remains outside both:
    a token that is a bare word naming an APK by some other route.
15. ~~`codeOf`'s comment stripping is quote-unaware.~~ **Closed, and the reasoning that deferred it
    was wrong.** The measurement behind the deferral — zero committed lines carry a `#` inside a
    string — was correct; the conclusion drawn from it was not, because the question is reachability
    by an ordinary edit and `--notes "Fixes #862"` is one. The direction mattered: every consumer is
    an unanchored presence test, so a truncated line can only *lose* matches, which moves a step
    toward "publishes nothing" and "carries no transport". It is quote-aware now, and an unbalanced
    quote leaves the line unstripped — keeping text rather than losing it.
