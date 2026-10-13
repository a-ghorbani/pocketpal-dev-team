# llama-soak: Stop / release / chat-state soak for llama.rn

Device harness for the app's Stop, release and chat-state paths. Run it on every llama.rn upgrade while the app carries its own llama.rn patch (`patches/llama.rn+<version>.patch`), and on any change to Stop, release, model switching or chat sessions. It was built for #955.

It has two parts:
- an uncommitted app-side harness, which adds test-only hooks to an E2E build;
- host drivers that run fixed regression cells and seeded random soaks through those hooks, and check every reply against a cold replay.

## Layout

| Path | What |
| --- | --- |
| `app/harness.patch` | The app harness, for Android and iOS: `CrashReproAdapter.tsx` (new), its mount in `AutomationBridge.tsx`, send/Stop listeners in `ChatScreen.tsx`, regenerate/edit listeners in `ChatView.tsx`. |
| `app/android-local-build.patch` | Local-host-only `android/app/build.gradle` edits: a `hermesCommand` override (no linux-arm64 hermesc) and `abiFilters "arm64-v8a"`. Only for building on a Linux aarch64 host. |
| `run.py` | Android entry point. `--mode soak` runs `soak.py`; `--mode soak --scenario NAME` runs `triage.py`; the other modes are the older one-shot matrix (see "Matrix modes"). |
| `soak.py` | Seeded random soak: one seed, K steps, one phone. |
| `triage.py` | Fixed scenarios (`SCENARIOS`), each ending in a cold-replay oracle. The regression cells live here. |
| `queue.sh` | Runs a list of soak/triage lines on one phone, one at a time, and checks the APK sha. |
| `batch.sh` | Runs a list of `attempt\|flags` lines through `run.py` matrix modes. |
| `soak_report.py` | Coverage table: oracle tallies, Stop and release latency, problems per cell. |
| `stoplat.py` | Stop latency split by prefill and generation, from seed logcats. |
| `show.py` | Compact per-step view of triage rows. |
| `script_variant.py` | Replays a recorded seed with steps dropped, kept or replaced (bisects a mismatch). |
| `android/` | `install-apk.sh` (wake, MIUI watcher, install, print sha), `swap-apk.sh` (install any versionCode and keep the models), `push-models.sh` (size-checked push). |
| `ios/` | `devicectl` device layer (`ios_dev.py`), entry point (`ios_run.py`), its own extra scenarios, `ios-queue.sh`, `ios_report.py`. |
| `lists/` | Example run lists: Android regression cells, Android soak cells, iOS regression cells and baselines, iOS soak. |
| `models.sha256` | Checksums of the standard model set. |

Output goes to `$LLAMA_SOAK_OUT` (default `out/` here, git-ignored). Point it at the task's story folder, one directory per build and phone, for example `export LLAMA_SOAK_OUT=$PWD/workflows/stories/<task>/soak-pixel`. Layout: `soak/<tag>/seed-N.jsonl` + `seed-N-logcat.txt.gz`, `soak/summary.jsonl`, `soak/triage/<tag>/…`, `soak/queue-<serial>.log`, and for matrix modes `runs/` and `result.json`.

## What the harness adds, and why it is never committed

The app has no host-reachable way to press Stop at a chosen moment, release a context mid-reply, or replay a completion cold. The harness adds one, behind `__E2E__`.

`CrashReproAdapter` polls `<files dir>/crash-command.json` every 250 ms and runs the command in it:
- `load` (with `deterministic` = temperature 0, seed 42, `n_predict` cap; `backend` cpu/gpu/hexagon; `speculative`; `draft`; `mmproj`), `switch`, `release` (adapter or the Models-screen unload path);
- `send` / `send-tool`, with an in-app Stop armed at `send`, `completion-start`, `first-token` or `tool-start` plus a delay (`stopOn`, `stopAfterMs`), and `thenSend` for a follow-up in the same tick as the Stop;
- `stop`, `regenerate`, `edit`, `session`, `wipe-sessions`, `chat-state`, `status`, `hold` / `unhold`;
- `replay`: release, cold reload, and re-issue the last completion's exact params.

It wraps every context (auto-reloads too, through a MobX reaction) and logs `[CRASH_REPRO] <ms> <event> <json>` for each completion start, first token, settle (`interrupted`, `prompt_n`, `tokens_evaluated`, `tokens_cached`, and a 64-bit hash of the full text), Stop and release. The drivers read those lines from logcat.

The hooks sit in production components (`ChatScreen`, `ChatView`, `AutomationBridge`) and expose test-only commands, so the harness stays out of the app repo: apply it uncommitted, build, and never stage it.

## Apply the harness in an app worktree

```bash
cd worktrees/<task>
git apply ../../tools/llama-soak/app/harness.patch
git apply ../../tools/llama-soak/app/android-local-build.patch    # Linux aarch64 build host only
```

If a hunk no longer applies (for example `ChatView.tsx` moved), fall back to a 3-way apply. It uses the blob ids in the patch, so it works when the worktree's repo has the base commit:

```bash
git apply -3 ../../tools/llama-soak/app/harness.patch
git status --short    # -3 stages what it applies: resolve conflicts, then git restore --staged src
```

`android-local-build.patch` has `versionCode` in its context, so it conflicts after every version bump. Make its two edits by hand when that happens.

After porting, refresh the patch from the worktree so the next upgrade starts from it:

```bash
git add -N src/__automation__/CrashReproAdapter.tsx
git diff -- src/__automation__ src/screens/ChatScreen/ChatScreen.tsx src/components/ChatView/ChatView.tsx \
  > ../../tools/llama-soak/app/harness.patch
git reset -q src/__automation__/CrashReproAdapter.tsx
```

Before you finish, revert the harness (`git apply -R …`, or `git checkout` the three files and delete the adapter). `git status` must show none of it before anything is committed.

## Build a soak APK (Android)

1. **Native libraries.** The local build compiles llama.rn from source, so the CPU variants carry this worktree's patch:

   ```bash
   cd worktrees/<task>/android && E2E_BUILD=true \
     ORG_GRADLE_PROJECT_rnllamaBuildFromSource=true \
     ORG_GRADLE_PROJECT_rnllamaVariants=rnllama,rnllama_v8_2_dotprod \
     ./gradlew assembleE2eReleaseE2e -PreactNativeArchitectures=arm64-v8a
   ```

   The variant allowlist skips `…_hexagon_opencl`, because its link segfaults under qemu on an aarch64 host. So this APK fails the full payload gate by design, and it runs CPU only. A cold native rebuild takes about 1.5 h on that host.
2. **GPU and Hexagon.** To run `--backend gpu|hexagon`, take the OpenCL/Hexagon pair from the CI build of the same head:
   - download artifact `android-release-apk` (`gh run download <run-id> -n android-release-apk`);
   - check that its payload report passes and shows the expected markers;
   - extract `lib/arm64-v8a/librnllama_v8_2_dotprod_i8mm_hexagon_opencl.so` and `librnllama_jni_v8_2_dotprod_i8mm_hexagon_opencl.so`;
   - copy them into `android/app/src/e2e/jniLibs/arm64-v8a/`.

   Copy them **before** the gradle run. If you swap them after a build, `mergeE2eReleaseE2eJniLibFolders` has already packaged the old pair; rerun the build so that task and `mergeE2eReleaseE2eNativeLibs` run again (about 40 s, with native and bundle up to date). Delete stale pairs from a previous llama.rn version first. They are git-ignored build inputs, and they get packaged silently.
3. **Verify the patch markers in the APK.** The app's llama.rn patch defines version markers. On rc.7 they were `rnllama_patch_abort_v3` (`librnllama*.so`) and `rnllama_jsi_patch_ownership_v3` (`librnllama_jni*.so`). Every `librnllama*.so` must carry the current `_vN` and no older one:

   ```bash
   unzip -o -q app-e2e-releaseE2e.apk 'lib/arm64-v8a/librnllama*' -d /tmp/apk
   for f in /tmp/apk/lib/arm64-v8a/librnllama*.so; do
     echo "$f: $(readelf -W --dyn-syms "$f" | grep -o 'rnllama_[a-z_]*patch[a-z_]*_v[0-9]*' | sort -u | tr '\n' ' ')"
   done
   ```

   Use `strings -a` as a cross-check. If you add a marker in a new patch revision, bump N. A stale library carries the old N and passes every other check.
4. **Check that the bundle is fresh.** `assets/index.android.bundle` in the APK must equal `android/app/build/generated/assets/react/e2eReleaseE2e/index.android.bundle`. Check its sha256, and `strings -a` it for harness strings such as `thenSend` and `wipe-sessions:done`. A fresh APK can still ship a stale bundle.
5. **Install** with `android/install-apk.sh <serial> <apk>` (or `swap-apk.sh` for a lower versionCode). It prints the installed sha256. Export that sha as `LLAMA_SOAK_APK_SHA`, or pass it as `--expect-sha`: every run then refuses a different APK on the phone. Another session's fullReset e2e run once replaced the build mid-soak, and this check is what catches that.

**Models.** `android/push-models.sh <serial> <file…>` pushes into `/sdcard/Android/data/com.pocketpalai.e2e/files/`. Bare names resolve in `$LLAMA_SOAK_MODELS`, default `~/.cache/pocketpal-soak-models`. The standard set (checksums in `models.sha256`):
- dense Q4_0: `gemma-3-1b-it-q4_0.gguf`, `Llama-3.2-1B-Instruct-Q4_0.gguf`;
- hybrid: `LFM2.5-1.2B-Instruct-Q4_0.gguf`, plus `LFM2.5-350M-Q4_K_M.gguf` / `-Q4_0.gguf` (LiquidAI GGUF repos);
- MTP: `Qwen3.5-0.8B-Q4_0.gguf`;
- vision: `Qwen3.5-2B-Q4_0.gguf` + `mmproj-F32.gguf`, and `LFM2.5-VL-450M-Q8_0.gguf` + `mmproj-LFM2.5-VL-450M-Q8_0.gguf`;
- Q4_K: `smollm2-1.7b-instruct-q4_k_m.gguf` (HuggingFaceTB);
- breadth: `granite-4.0-h-350m-Q8_0.gguf`, `mamba-130m-Q3_K_M.gguf`, `gemma-3-4b-it-Q4_0.gguf` + `mmproj-gemma-3-4b-f16.gguf`;
- images: `soak-image.jpg`, `test-image.jpg`.

Uninstalling the e2e package deletes the files dir.

## Run (Android)

**Claim the phone first** and release it when done, saying what you left on it. Use agistry only:

```bash
~/.claude/skills/agistry/agistry.sh resources free
~/.claude/skills/agistry/agistry.sh claim adb:<serial> 21600 "soak: installing <apk sha>"
~/.claude/skills/agistry/agistry.sh release adb:<serial> "left soak APK <sha> + models in the e2e files dir"
```

Keep the phone awake and unlocked; a locked phone makes setup fail with `wipe-sessions failed`. Never touch prod `com.pocketpalai`. The drivers only use `com.pocketpalai.e2e`.

**Regression cells** (fixed scenarios; run these first, on an exact-oracle phone):

```bash
export LLAMA_SOAK_APK_SHA=<sha> LLAMA_SOAK_OUT=<story>/soak-<phone>
./queue.sh <serial> lists/android-regression.txt
# one cell: python3 run.py --mode soak --scenario stop-before-start --serial <serial> --model-a gemma-3-1b-it-q4_0.gguf --seed 1 --tag gemma3-stop-before-start
```

The cells cover:
- Stop before the completion starts (`stop-before-start`, Gemma's strict alternation), in prefill, and in generation;
- cold Stop then resend (`cold-stop-same` / `-diff`);
- MTP (`--speculative`) Stop with its no-Stop baseline;
- image Stop during encode and during generation;
- Stop during tool exec, in the gap after it, and in the post-tool completion;
- the SWA new-chat case.

`triage.py` lists all scenarios. `--stop-ms` overrides every Stop delay.

**Random soak** (one seed per call). Steps are weighted random choices:
- send short/long, Stop, Stop-then-send, regenerate, edit;
- switch session or new chat, including mid-reply;
- background (Home → auto-release → resume);
- model switch, release mid-reply;
- tool / tool-stop, image / image-stop, composer drafts.

```bash
./queue.sh <serial> lists/android-soak.txt
# one seed: python3 run.py --mode soak --serial <serial> --seed 21 --steps 40 --model-a LFM2.5-1.2B-Instruct-Q4_0.gguf \
#   --model-b smollm2-1.7b-instruct-q4_k_m.gguf --tools --drafts --tag lfm25-1.2b-cpu
```

Per step it checks:
- crash (PID change, `Fatal signal`, tombstone);
- hang (not idle within `--step-timeout`; it saves thread states);
- `Context is busy`, DSP errors, lmkd kills;
- session invariants: other chats' message counts and last message are unchanged, and drafts stay in their own chat;
- the replay oracle, with probability `--oracle-rate`, on any completion that ran to its end.

`--control` disables every Stop, release, background, switch-mid and model switch. That gives the warm-vs-cold baseline of a cell; always run a control next to a GPU, Hexagon or non-Q4_0 CPU cell. Each row also records `flags.abort_kind`:
- `restore` / `clear:<reason>` / `dense-trim`: the native `Decoding interrupted, …` line;
- `implicit`: interrupted with no line, the rc.7 path for dense and non-MTP hybrids.

It records `flags.load_path` too (`load-restore`, `swa-guard`, `eval-fail`, `draft-abort`, …). When a new llama.rn version changes those log wordings, update `LOAD_RES` / `abort_kind` in `soak.py`.

**Reading results.**
- `python3 soak_report.py` gives the table per cell; read the rows with problems.
- `python3 stoplat.py $LLAMA_SOAK_OUT/soak/<tag>/seed-*-logcat.txt.gz` splits Stop latency by phase.
- `python3 show.py '$LLAMA_SOAK_OUT/soak/triage/*/seed-*.jsonl'` shows triage rows step by step.
- To bisect a soak mismatch: `python3 script_variant.py NAME --base <seed-N.jsonl> --drop 5 -- --serial <s> --seed N <the seed's soak flags>`. `--extra-replays 1,2,4,512` adds cold replays at those `n_batch`/`n_ubatch` sizes, which shows whether the cold text itself depends on batch splitting.

**Matrix modes** (`run.py --mode baseline|background|release|switch|stop-send|mtp-stop|stop-retry|wait-gate|wait-switch|…`). These are the older one-shot runs that tap the real Stop and Send buttons via uiautomator and can take screen captures (`--capture`). `batch.sh` runs a list of them. Two modes need builds that are not kept here: `dc1` needs debug lines in `node_modules/llama.rn/src/index.ts`, and `fault` needs a native fault-injection build. Prefer the soak and triage paths.

## iOS

Run iOS on the Mac that hosts the iPhone, through its ios-router (`skills/ios-router`), which holds the iPhone lease. Copy or clone this folder there; `ios/` imports `soak.py` and `triage.py` from the parent.

```bash
export IOS_UDID=<xcrun devicectl list devices> LLAMA_SOAK_BUILD=<ipa label> LLAMA_SOAK_OUT=…
ios/ios-queue.sh lists/ios-regression.txt      # lines: `triage <flags>` or `soak <flags>`
python3 ios/ios_report.py                       # triage table; soak_report.py for the seeds
```

- **Device layer.** `ios_dev.py` replaces adb with `xcrun devicectl`:
  - commands are copied into the app container's `Documents/crash-command.json`;
  - `Documents/crash-repro.log` is pulled about once a second into the seed's log file, so `soak.py` parses it unchanged;
  - crash reports are diffed per seed. `cpu_resource` / `diskwrites` reports are resource diagnostics, not crashes.
- **Adapter edits needed on iOS (not in `app/harness.patch`).** The adapter reads `RNFS.ExternalDirectoryPath`, which iOS does not have. The iOS build needs three edits:
  - read commands and model files from `RNFS.DocumentDirectoryPath`;
  - append every `[CRASH_REPRO]` line to `Documents/crash-repro.log`, in the logcat line shape that `EVENT_RE` matches;
  - (the "v2" build) forward native log lines.

  These edits were made on the Mac during the #955 iOS run and are not in this repo. Port them into the patch on the next iOS run.
- **Native logs.** On iOS, rnllama's `LOG_INFO` goes to stdout, so `ios_setup` launches the app with `devicectl device process launch --console --terminate-existing` and scans that stream for checkpoint, abort and SWA lines (`seed-N-stdout.txt`).
- **Background and resume.** Home is simulated by launching `com.apple.Preferences`. Resume relaunches the bundle **without** `--terminate-existing`; with that flag it is a cold start, not a resume.
- **Pre-start Stop window.** A tap cannot reach the pre-start Stop window (Stop between Send and `completion:start`) on iOS. Use the adapter's armed Stop (`stop-before-start --stop-ms 0`).
- **Backends.** Metal is `--backend gpu` (devices `MTL0`). Drafts and other uiautomator steps are not ported; `--drafts` steps record `draft_error`.

## The oracle

A warm reply (one that reused live KV or recurrent state) is replayed cold: release, reload, and the same params at temperature 0, seed 42. The two full-text hashes must match. The cold path is deterministic (`cold-twice` matched on CPU and Hexagon). But warm vs cold is exact only where the kernels give the same result however the prompt is split into batches:
- **Exact:** Android CPU with Q4_0 models (Gemma 3 1B, Llama 3.2 1B, LFM2.5-1.2B on a Pixel 9 dotprod build), Qwen3.5-0.8B MTP on the Pixel CPU, and Metal on iOS.
- **Baseline-relative:** OpenCL, Hexagon, Q4_K / Q8_0 on CPU, the F8 Ultra CPU (i8mm build), mamba and Granite-H. These mismatch with no Stop at all. Single-token decodes and batched decodes round differently (`n_ubatch` 1-2 vs 4+), and near-tie prompts flip the greedy choice. Run `--control` seeds and the no-Stop scenarios (`gen-then-send`, `cold-same-nostop`, `baseline3` on iOS) next to them.

Count a mismatch as corruption only if one of these holds:
- it beats the baseline: an exact cell, or a rate clearly above the cell's control, or a matched pair (same script with and without the Stop) that separates the two;
- the warm text is incoherent: wrong facts, garbage, a wrong chat's content.

Otherwise bisect it with `script_variant.py` before calling it. Crashes, hangs, `Context is busy` and session leaks count on every backend.

## Host load

The build host is shared:
- check `uptime` before starting;
- run heavy builds one at a time (`nice -n 19`, `--max-workers=3`, `--no-daemon`);
- run jest with `--maxWorkers=2`.

Each phone takes one queue at a time. The drivers are light, but a soak queue runs for hours, so start it in the background and leave a mechanism that outlives the session, such as the queue log or a monitor.

## Last known results

#955, llama.rn 0.13.0-rc.7 with the app patch (`_v3` markers), on Android F8 Ultra (CPU, OpenCL, Hexagon), Pixel 9 (CPU) and Galaxy S23 (OpenCL, CPU), and on iPhone 13 Pro (CPU, Metal). It ran about 40 Android seeds (1,084 steps, 420 oracles), every regression cell, and the iOS cells and seeds. No finding was caused by the patch: no crash, hang, `Context is busy` or session leak. Every mismatch matched its no-Stop baseline, or was explained by the numerics above.

Known pre-existing items, not caused by the patch:
- a CLIP/mtmd image encode cannot be aborted, so a Stop waits for the image chunk;
- an OpenCL Stop during prefill waits up to one 512-token ubatch (about 2 s on the S23);
- Gemma templates wedge a chat that holds a tool turn or a full context.
