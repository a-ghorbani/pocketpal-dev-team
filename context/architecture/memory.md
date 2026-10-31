# Memory Flow

> **Status:** design, not on `main`; pending operator approval. Describes the target. Today, each caller listed in the code map runs its own rule.

## Purpose

How the app decides whether something fits in memory: the **need** of everything resident together, the **budget** this phone gives the app, the one **policy** that turns the two into fits / tight / won't fit, and how the budget **learns** from real outcomes, including being killed. Out of scope: loading itself (`model-loading.md`), the Whisper and TTS engines (`asr.md`, `tts.md`), voice-mode entry UI (`voice-mode.md`), disk-space preflights, and speed gates (the voice and dictation device-tier gates decide latency, not memory).

## Code map

| Path | Role |
| --- | --- |
| `src/services/memory/check.ts` (planned) | `check(set) → {status, needBytes, budgetBytes, totalBytes, rows, killedBefore}`, the only fit decision; `accept(set)` records a tight set the user continued with (scope per operator decision: per process or per entry) |
| `src/services/memory/need.ts` (planned) | `need(set)`: one row per component, each with its `basis` (`measured` / `engine` / `gguf` / `size`) |
| `src/services/memory/ggufNeed.ts` (planned; replaces `utils/memoryEstimator.ts`) | per-architecture formula from GGUF metadata: weights, per-layer KV, recurrent state, compute, checkpoints, draft, MTP, projector |
| `src/services/memory/budget.ts` (planned) | `budget()`: the platform prior, raised by survivals and capped by kills |
| `src/services/memory/residentSet.ts` (planned) | `residentNow()`: the loaded context (model, projector, draft, effective init params), the active TTS engine, the pinned Whisper tier; `withAdded(set, component)` |
| `src/store/MemoryStore.ts` (planned) | outcome log, learned budget, accepted sets (in memory), `ready` (hydrated and last session classified). Single writer of all of them |
| `src/specs/NativeHardwareInfo.ts`, `HardwareInfoModule.{kt,mm}` | planned additions: footprint (Android PSS + swap PSS, iOS `phys_footprint`), a durable marker store (`SharedPreferences.commit`, `NSUserDefaults`), Android exit reasons, native memory-pressure and terminate flags |
| `ttsRuntime` (`src/services/tts/`) | `acquire` / `release` call `MemoryStore.setResident(residentNow())` with no check and no prompt, so the marker includes a voice engine loaded for auto-speak |
| `src/utils/ggufHeader.ts` | bounded HTTP range reader, reused for an undownloaded model's metadata |
| Callers | `ModelStore.checkMemoryAndConfirm` and `initContext`, `useMemoryCheck` (model card, HF file card), `MemoryRequirement`, `IncreaseContextSheet` and `ChatView`'s context CTA, `PalModelStep/modelOffer`, `ASRStore.captureMemoryFit`, `useVoiceMode.checkMemoryAndEnter` / `VoiceMemorySheet`, `__automation__/voiceAutomation`. TTS activation is not a caller: a resident engine is counted in every set |

## How it works

**Resident set.** A caller asks about `withAdded(residentNow(), component)`: everything already in memory (the loaded context, a TTS engine kept for auto-speak, a pinned Whisper tier) plus what it is about to add.

**Need.** `need(set)` sums model rows in one unit: bytes the models add above the app's no-model baseline. A chat row's basis, best first:
1. `measured`: this phone ran this exact configuration. The row is the footprint at a chat-only checkpoint, minus the session's no-model baseline, plus the mapped weight bytes that footprint leaves out. On iOS that is every file-backed weight byte not copied to a buffer. On Android it is those bytes minus the model file's resident pages (smaps), because PSS already counts them. Which tensors were copied comes from the engine's buffer breakdown (repack is per tensor). iOS need stays weight-inclusive. The `measured` basis turns on together with learning.
2. `engine`: llama.rn's no-alloc dry run (`common_get_device_memory_data`).
3. `gguf`: the formula over local metadata or the remote header.
4. `size`: file size × the measured factor, when no header can be read.

Whisper and TTS rows are their measured `runtimeBytes`.

**Budget.** The budget is the platform prior, in the same unit:
- **Android:** a share of visible total RAM minus the measured no-model baseline. The share was measured against estimates that included the baseline. It never uses `availMem` (#982).
- **iOS:** a share of the no-model headroom, which is already net of the baseline. It is then folded over the outcome log for the current llama.rn version:
- a survival raises it to `need(set)`, never above the lowest kill;
- a kill caps it below `need(killedSet)`, recomputed from the stored set identity.

**Check.** `check(set)` returns `fits` (need ≤ budget), `tight` (need ≤ total RAM) or `wont_fit`, plus `killedBefore` when a kill's set needed no more than this one. Callers map:
- `fits`: silent;
- `tight`: Cancel / Continue, firm when `killedBefore` (it says the app closed last time; Cancel is the default);
- `wont_fit`: refuse.

**Marker.** `MemoryStore.setResident(set)` writes the current resident set natively and synchronously on every residency change: before an allocation, and after a release, exit or stop. An empty set clears it. The marker also carries `foreground` (it follows AppState both ways), an iOS `terminated` flag, and the last checkpoint: footprint and pressure evidence, sampled off the JS thread at load done, first reply, and voice entry. A set that completed a reply or turn records a survival when it leaves residency. On launch, `MemoryStore.ready` (hydrated, previous marker classified; see the table under Contracts) gates `check()` and `setResident()`.

## Contracts and invariants

- **One decision.** No caller compares bytes or reads RAM to decide fit; every status comes from `check()`. The exceptions are display-only reads (usage stats, benchmark device card, error report) and the named exceptions under Traps.
- **Whole set.** A check counts everything resident, plus what is being added. A pairing that fits voice mode fits dictation, because dictation's set is a subset.
- **Refuse only above physical RAM.** `wont_fit` iff need > total RAM. Nothing else blocks. The iOS load path warns instead of refusing on `wont_fit` until the operator decides otherwise: an mmap'd model larger than RAM loads and pages.
- **A missing input never refuses.**
  - An unreadable total RAM uses the last known value; if none is known, the status is `tight`.
  - An unreadable footprint learns nothing.
  - A check that throws is `tight`.
- **One unit.** Need, budget (the Android prior included), survivals and kills are all model bytes above the no-model baseline, with the mapped weights the footprint leaves out added back. Process totals are only stored as inputs to that arithmetic.
- **Learn from measurements, never estimates.** A `measured` row comes from a footprint. A load that only initialised is not a survival.
- **Kills are asymmetric.** A survival never raises the budget above the lowest kill need. Boundary kills are random (3 of 15 on the S23 at one pairing).
- **The budget is a pure function** of the prior and the outcome log for the current llama.rn version. A version bump drops survivals and kills together.
- **Classification before residency.** `ready` precedes any `setResident` and any `check`. Background, terminated and unknown exits teach nothing.
- **Launch classification.** A marker that is non-empty, `foreground` and not `terminated` is classified by the first matching row:

  | # | Evidence | Outcome | Learns |
  | --- | --- | --- | --- |
  | 1 | Reboot since the marker (boot count / boot time) | `unknown` | no |
  | 2 | Android 11+: `ApplicationExitInfo` matched by pid and time. `USER_REQUESTED`, `PERMISSION_CHANGE`, `PACKAGE_UPDATED`, `ANR`, `EXIT_SELF` | `unknown` | no |
  | 3 | Android 11+: `REASON_LOW_MEMORY` | `kill` | yes |
  | 4 | A crash (Android `CRASH*`; a JS fatal or native signal mark) with pressure evidence | `memory_crash` | as a kill |
  | 5 | A crash without pressure evidence | `crash` | no |
  | 6 | No crash mark, with pressure evidence: Android `REASON_SIGNALED` / `OTHER`, Android < 11, iOS | `kill` | yes |
  | 7 | Anything else | `unknown` | no |

  **Pressure evidence** is sampled by the app at the last checkpoint: `ActivityManager.MemoryInfo.lowMemory` or `availMem` ≤ `threshold` on Android, a memory warning on iOS, or footprint ≥ budget on either. Android 14 no longer delivers the `onTrimMemory` running levels, hence the app's own samples. Platforms without an exit reason (row 6) share one rule.
- **Durable marker, fail open.** The marker is stored natively and synchronously under its own key, never through `makePersistable`. A failed write logs and never blocks the allocation. The outcome log keeps one latest record per set identity and outcome.
- **Single writer.** `MemoryStore` alone writes outcomes, budget, acceptances and the marker. `ModelStore` writes GGUF metadata and nothing about calibration.
- **`measured` key** = the effective init params that size memory (model file identity, `n_ctx`, `n_batch` / `n_ubatch`, cache types, `flash_attn`, devices / `n_gpu_layers`, `n_parallel` / `kv_unified`, `use_mmap`, `state_cache_budget_mb`), plus projector, draft and the llama.rn version. Any change falls back to the next basis.
- **Every constant has a measured reason beside it.** That covers the priors, the size factor, `runtimeBytes`, and the swap share in survival. A constant without one fails review.

## Traps and decisions

- **Arrays in metadata.** `head_count_kv` is per-layer on hybrids (LFM2: `[0,0,8,…]`). A scalar parse returns NaN, and the old fallback to `n_head` counted KV on every layer: LFM2.5-8B at 16k was estimated at 9.5 GB against 6.7 GB measured.
  - `vocab_size` is often absent (Gemma, Qwen3.5). The real vocab is the length of `tokenizer.ggml.tokens`; an arch default halves the compute buffer.
  - SWA patterns, `full_attention_interval` and `shared_kv_layers` decide which layers hold KV.
- **Memory metric.**
  - **Android: PSS + swap PSS.** RSS understates need by gigabytes under swap (F8 Ultra Gemma 4 E4B: RSS 1.1–1.5 GB of a 6.9 GB native heap). Native heap misses Graphics, where OpenCL and Hexagon keep weight copies. `Debug.getMemoryInfo` walks smaps, so it is sampled only at checkpoints.
  - **iOS: `phys_footprint`**, the figure jetsam enforces.
- **iOS need includes the weights.** `os_proc_available_memory` barely moves when mmap'd weights load (4.2 → 3.7 GB with a 4.3 GB file, iPhone 13 Pro). But the iOS prior (0.8 of no-model headroom) was measured with the weights in. Without them, the pair that once aborted Whisper's init (4B Q4 + Small, 3.85 of 4.2 GB) would fit silently. The split waits for a reserve measured in weights-excluded units.
- **mmap is an input, not a policy.** `use_mmap` is a user setting whose default resolves to off on Android and on on iOS. Weights become evictable only when the effective mmap is on and nothing copies them: no OpenCL, Hexagon or CPU_REPACK (Q4_0 / IQ4_NL). Any change to that rule comes from a measured mmap study and changes `need`, not the policy.
- **No phone-size tiers in memory decisions.** The prior is a share of this phone's own RAM, and what this phone did replaces it. `stateCacheBudgetMb` and any remaining RAM-threshold gate are named exceptions until moved onto `check()`.
- **Swap-bound survival is not proof.** A session that lives mostly in swap (F8 Ultra Gemma 4 E4B, 0.09 tok/s) is not recorded as a survival unless its swap share is under the measured limit.
- **iOS signal marks use a pre-opened file descriptor.** `NSUserDefaults` is not async-signal-safe, so a crash handler that writes through it can deadlock or write nothing. A watchdog kill (`0x8badf00d`) leaves no mark; if a memory warning preceded it, it is misclassified as a kill. This is accepted: the cost is one firmer warning.
- **Projector and MTP runtime are measured, not derived.** Gemma vision ran ~1.1–1.3 GB above the estimate on both device points, and the bench archive holds no clip buffer size. The formula carries a measured term per projector family until the engine reports it.

## Verification

- **Unit (planned)**, in `src/services/memory/__tests__/`:
  - `ggufNeed` over verbatim GGUF headers: dense, Gemma 3, Gemma 4 E-series, LFM2, LFM2-MoE, Qwen3.5, Qwen3-VL with its projector, and a draft pair;
  - `check` zones, missing inputs and `killedBefore`;
  - `budget` with survivals capped by kills;
  - classification over every row of the table.
- **Device:** need against the measured row for the same families at 4k and 16k, on a Pixel 9, Galaxy S23 and iPhone 13 Pro.
  - **Kill path:** Galaxy S23 with Gemma 3 4B, Whisper Base and a voice (lmkd kills it). On relaunch, `kill` is recorded and the next voice entry warns firmly.
  - **Nothing recorded:** a background kill, an Android swipe-away and an iOS app-switcher swipe.
  - **iOS jetsam:** force it with a large `n_ctx` or `use_mmap` off. An oversized mmap'd model does not count.
- **e2e:** `tts-memory-profile`, `memory-profile`, the voice specs. The forced states in `voiceAutomation` go through `check()`.
