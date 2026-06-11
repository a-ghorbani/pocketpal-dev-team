# Model Loading & Device-Rule-Driven Preset List

Cumulative architecture truth for how PocketPal sources its model list: the device-rule-driven preset list, the offline bundled floor, and the migration off the old static default list.

**Conventions**: `(C)` current (in `main`), `(D)` decision.

---

## 0. Where the default model list comes from (C)

The model list is **data-driven**, not a hand-maintained array. `src/store/defaultModels.ts` was removed. Device rules decide **which preset models populate the existing list** — there is **no separate suggestions UI**. Two sources feed the same path:

- **Fetched rules** (`rules.<platform>.json` via jsDelivr) — the online override.
- **Bundled rules** (`src/store/bundledDeviceRules/rules.<platform>.json`, committed, statically imported) — the offline floor and replacement for the old static list.

The hosted schema is **thin and flat**: each tier carries a `candidates[]` array of plain candidate objects (no nested `hfModel`/`modelFile`, no baked `oid`/`lfs`/sibling URLs). The app **consumes the thin schema directly and defers HF-derivable data to download time, exactly like an HF-browser model** — instead of baking it. At list-build, the app synthesizes the minimal `{hfModel, modelFile}` pair the existing `hfAsModel` transform reads, derives a deterministic `downloadUrl`, and yields a `Model` with `origin: ModelOrigin.HF`. Resolved models merge into `ModelStore.models` where `defaultModels` used to merge, and render through the **existing** `ModelCard` grouping. (C)

### 0a. Wire key vs internal key (D24)

The **wire** array key is `tiers[T].candidates[]` (the hosted schema). The **internal/parsed** array key stays `tiers[T].models[]`. The parse layer maps `candidates → models` **once** (in `parseCandidate`/`parseTiers`). So `rules.ts`'s `hasAnyModels` (reads `rules.tiers[tier].models.length`) and `DeviceRules.tiers: Record<Tier, {models}>` are genuinely unchanged — the rename never reaches them. Below, "candidate" = one parsed entry; "wire `candidates[]`" = the on-the-wire array; "internal `models[]`" = the parsed array `rules.ts` reads.

### 0b. Two phases — display stub vs download resolve (D1)

| Phase | When | Network | What is produced |
| --- | --- | --- | --- |
| **List build** | init / re-tier | none | a display **Model stub** (origin: HF) per candidate carrying everything the card needs *before* download: `id`, `name`, `size`, `params`, multimodal flag/modalities, projector size for the fit check, and a deterministic `downloadUrl` |
| **Download resolve** | user taps Download | yes (downloading needs network anyway) | HF-derivable data — `oid`, `lfs`, chat-template tokens, real sibling URLs — resolved live via the **existing** HF download path, NOT from the rules JSON |

The `downloadUrl` is deterministic and needs no network: `https://huggingface.co/{hf_repo}/resolve/main/{hf_filename}` (the same `/resolve/main/...` shape `hfAsModel` reads from `modelFile.url`). So `downloadUrl` is set at stub-build; everything HF-derivable defers to download.

### 0c. Stub-build mechanism — synthesize the minimal `{hfModel, modelFile}` `hfAsModel` already reads (D3)

The existing pure `hfAsModel` is **reused, not replaced**. From each thin candidate, `resolvePresetModels` builds the minimal `(HuggingFaceModel, ModelFile)` `hfAsModel` consumes, then calls it verbatim:

- `modelFile = { rfilename: hf_filename, url: deriveUrl(hf_repo, hf_filename), size: size_bytes }` — no `oid`/`lfs`; they resolve at download.
- `hfModel = { id: hf_repo, author: hf_repo.split('/')[0], url: https://huggingface.co/{hf_repo}, specs: { gguf: { total: params } }, siblings }`. For a multimodal candidate, `siblings = [ {rfilename: hf_filename, size: size_bytes}, {rfilename: mmproj.hf_filename, url: deriveUrl(mmproj.hf_repo, mmproj.hf_filename), size: mmproj.size_bytes} ]`; otherwise `undefined`.
- `stub = hfAsModel(hfModel, modelFile)` → `origin: HF`, `id = author/repo/filename`, `downloadUrl` set.
- `display_name` (if present) overrides `name`; every resolved stub is marked `isRulePreset: true`.

This works with **no network** at stub-build because:

- `hfAsModel`'s vision detection (`isVisionRepo`/`getMmprojFiles`) is **filename-pattern only** — the synthesized `siblings[].rfilename` (mmproj filename matches `MMProjRegex`) is sufficient to flag the LLM `supportsMultimodal`, build `compatibleProjectionModels`/`defaultProjectionModel`, and pair the projector. No URL is needed for detection.
- `getVisionModelSizeBreakdown` reads `siblings[].size` — baking `mmproj.size_bytes` onto the synthesized projector sibling makes `hasEnoughSpace` add the projector (~1GB for gemma-4) to the pre-download fit check. **This is the fit fix:** `min_ram_gb` may exclude projector memory; the projector's `size_bytes` enters the disk/fit check via the synthesized sibling.
- The projector **sibling carries a deterministic `url`**, so the materialized projection Model's `downloadUrl` is non-empty and `checkSpaceAndDownload` does **not** early-return for it. The LLM `modelFile` carries no `oid`/`lfs`; those resolve at download.

### 0d. Vision — explicit `mmproj`, single-repo constraint (D10), projector quant fixed at authoring (D25)

For `multimodal` candidates the projector is given **explicitly** (`mmproj.hf_repo`/`hf_filename`/`size_bytes`). The app does **not** run `getRecommendedProjectionModel`/`MMProjRegex` sibling-scan + quant-match discovery (that is for HF-browser models). The explicit `mmproj.hf_filename` **fixes the projector quant at authoring time** — there is no app-side validation that the authored projector quant fits the LLM quant. This is acceptable because we own the rules JSON (`a-ghorbani/pocketpal-device-rules`), but the fit is now an **authoring** invariant enforced by an operational pre-merge gate, not by code. (D25)

`modalities` is recorded as a forward-compat hint (vision today, audio later — one mmproj covers both per llama.cpp); the engine's `getMultimodalSupport()` stays authoritative at load.

**Single-repo constraint (D10):** `hfAsModel` builds projection ids as `${hfModel.id}/${file.rfilename}` and the download path resolves the projector under the LLM's repo. Today every shipped multimodal candidate has `mmproj.hf_repo === hf_repo`. The stub-build synthesizes the projector as a sibling of `hfModel.id = hf_repo`. A future candidate with `mmproj.hf_repo !== hf_repo` would mis-pair, so cross-repo projectors are out of scope until the download path supports them.

### 0e. Download-tap resolve — reuse the existing HF path verbatim (D1)

At download, HF-derivable data is resolved the way an HF-browser model already gets it. The stub's `downloadUrl` is already correct, so the **primary download proceeds with no new resolve hop** (`checkSpaceAndDownload` → `downloadUrl` → `getModelFullPath` HF branch → `models/hf/...`). The two HF-derivable consumers self-heal online:

- **Integrity:** `checkModelFileIntegrity` detects the missing `lfs` and calls `fetchAndUpdateModelFileDetails` to populate it from HF — no baked `lfs` needed.
- **Chat template / stop words:** GGUF-embedded (resolved at load) or filled by `getHFDefaultSettings` defaults; the stub carries no `bos_token`/`eos_token` and the engine/template path tolerates that exactly as for a minimally-resolved HF model.

`resolveHFModelForDownload` (`src/utils/hfResolve.ts`) and `fetchModelFilesDetails` remain the live-resolve primitives; the design **reuses** them via the existing self-heal callsite — it does **not** add a new pre-download resolve call. (D1)

### 0f. App-side generator? (D3) — **No.** The app imports the committed thin JSON as the floor and `fetchRules` online; there is no app/CI bake (the thin JSON is HF-derivable-free, so there is nothing to bake). (C)

---

## 1. Data model

### Device rules — `src/services/deviceRules/`

- `types.ts` — `DeviceRules` (parsed wire), `RuleCandidate` (flat candidate; see §1b), `RuleMmproj` (explicit projector reference), `Classifier`, `DeviceSignals`, `Tier = low|mid|high|flagship`. `tiers: Record<Tier, {models: RuleCandidate[]}>` (internal key `models`, D24).
- `signals.ts` — `readDeviceSignals()` reads once: RAM (`DeviceInfo.getTotalMemory`), iOS `machine` (`getDeviceId`), Android `socModel`/`hardware`/`cpuFeatures`/`maxFreqMhz` (`NativeHardwareInfo.getCPUInfo`).
- `classify.ts` — pure `classify(signals, classifier, platform): Tier`; total (last-resort floor → `low`).
- `parse.ts` — `parseDeviceRules`: classifier normalizer (snake→camel) + a flat `parseCandidate` per wire candidate. `parseCandidate` reads the wire `candidates[]` array, applies the §1b split + segment guard, and emits the internal `models[]`. Exports `deriveUrl(repo, filename)` so parse and the stub-build agree on the URL shape. An old fat `models[]` doc (or a candidate missing a required field) parses to empty tiers (does not throw).
- `rulesUrls.ts` — jsDelivr URL per platform.
- `rules.ts` — `fetchRules(platform)`: timeout-bounded fetch + `parseDeviceRules` + platform-match guard. Returns `null` (→ bundled floor) on any failure, **including a parse that yields zero models across all tiers** (an incompatible hosted JSON). Reads the internal `.models` length, unchanged by the rename (D24).

### Bundled offline floor — `src/store/bundledDeviceRules/rules.{android,ios}.json`

Committed, statically imported by `ModelStore`, run through the same `parseDeviceRules` as the fetched path. Thin `candidates[]` schema (`schema_version 1.2.0-draft`, §1b). No committed app/CI generator — the thin JSON is HF-derivable-free, so there is nothing to bake (D3). (C)

### Lookie offline constant — `src/store/builtinPalModels.ts`

`LOOKIE_DEFAULT_MODEL: Model` — full SmolVLM-500M vision model, origin HF, resolved offline at pal init (no network). (C, D15)

### Backing store — `ModelStore` (MobX)

No separate device-rules store. `ModelStore` gains:

- `deviceTier: Tier | null` — resolved once per init via `classify`.
- `rulesVersion: string | null` — provenance of the list (fetched vs bundled).
- `models[]` — now contains rule-resolved `origin: HF` stubs instead of static PRESET `defaultModels`.

Persisted: `ModelStore.{models, version, deviceTier, rulesVersion, …}` via the existing `makePersistable` + AsyncStorage. (C)

### 1b. Thin candidate schema (`tiers[T].candidates[]`)

Read-only consumption. Each candidate is flat:

```
{
  model,            // stable identity key (NOT the Model id; D2)
  display_name?,    // human UI name → Model.name (else derived)
  quant?,           // informational, app ignores
  hf_repo,          // "author/repo"                              (required)
  hf_filename,      // GGUF filename                              (required)
  params?,          // → Model.params
  size_bytes?,      // → Model.size
  min_ram_gb?,      // fit hint (advisory; may exclude projector)
  obs_tg?,          // informational, app ignores
  multimodal?,      // bool
  native_low_bit?,  // informational, app ignores
  sha256?,          // informational, app ignores
  mmproj?: {        // present iff multimodal — explicit projector
    hf_repo,        // (required for multimodal)
    hf_filename,    // (required for multimodal)
    size_bytes,     // projector size → fit check (required for multimodal)
    modalities?     // ["vision"]|["audio"]|both — forward-compat hint
  }
}
```

Required: `platform`, `rules_version`, `schema_version`, `classifier.{ram_bands, tier_matrix}` + platform classifier maps, and per candidate `{model, hf_repo, hf_filename}`. Required for multimodal: `mmproj.{hf_repo, hf_filename, size_bytes}`. The app **ignores** `quant`, `obs_tg`, `sha256`, `native_low_bit` (informational). Unknown fields ignored; a candidate missing a required field → skipped. (C, D9)

The schema is owned cross-repo in `a-ghorbani/pocketpal-device-rules` — out of the app's diff. (D1b)

**Parse-guard contract (untrusted input — the real boundary is the path segments, D19).** Rule JSON is fetched from a third-party CDN, so it is untrusted. `parse.ts` **derives** `downloadUrl = https://huggingface.co/{hf_repo}/resolve/main/{hf_filename}`, so validating that derived URL with `isHuggingFaceUrl` is a **tautology** (the host is hard-coded in the template) — it is **defense-in-depth only, NOT the primary guard**. The primary guard is `isSafePathSegment` (non-empty, no `/`, `\`, `..`) on the **path segments**. Because `hf_repo` is `"author/repo"` (contains `/`), it cannot be passed to `isSafePathSegment` whole. Per candidate:

1. **Split** `hf_repo` on `/`; require **exactly two non-empty parts** (`author`, `repo`). Zero or ≥2 slashes, or an empty part → **skip candidate**.
2. Run `isSafePathSegment` on **`author`**, **`repo`**, AND **`hf_filename`** (each must pass). Any fail → **skip candidate**.
3. Only then build `downloadUrl` from the validated parts.
4. **Same contract for `mmproj.hf_repo` / `mmproj.hf_filename`**. A multimodal candidate whose `mmproj` segments fail (or whose `mmproj` is missing / has no `size_bytes`) → **skip the whole candidate** (do not ship a vision model with an unvalidated projector path).
5. `isHuggingFaceUrl` on each derived URL is applied as a final defense-in-depth assertion; it can never fail given the template, so it is not the boundary.

`DownloadManager` nulls the Bearer token for non-HF hosts, a second defense-in-depth layer. (C, D19)

---

## 2. Event flow

```
app start / ModelStore.initializeStore
  readDeviceSignals() once
  resolvePresets():                           (NO network — bundled floor only)
    rules = parseDeviceRules(bundled rules.<platform>.json)   // thin candidates → internal models
    classify(signals, rules.classifier, Platform.OS) → deviceTier
    presets = resolvePresetModels(rules, signals)
      // per candidate: synthesize {hfModel, modelFile} (§0c) → hfAsModel → origin:HF stub, isRulePreset
      // multimodal candidates also push their synthesized mmproj projector stub
  merge presets into ModelStore.models (reconcile, §6)   ← list is populated NOW, offline
  upgradeToFetchedRules() (fire-and-forget, off the first-population path):
    fetched = fetchRules(platform)            (jsDelivr, timeout-bounded, parsed)
      ok (≥1 candidate)         → re-classify + reconcile (id-keyed dedup, §6)
      fail / old-schema / empty → no-op (bundled floor stays)
  user taps a model in the EXISTING list → checkSpaceAndDownload → deterministic downloadUrl → models/hf/...
    integrity/template HF-derivable data self-heals online (§0e)
```

The bundled floor is applied **synchronously of the network** so a slow or hanging fetch never leaves the list empty on a fresh install; the online override is folded in afterwards. No new UI, no producer, no new transform. The only download-time addition vs a baked model: `lfs`/template resolve via the existing self-heal (§0e), which an HF-browser model already triggers. (C)

---

## 3. State machine

No lifecycle store. Rules resolution inside `initializeStore` is two-phase: (1) `bundled → classify → stub-build → reconcile` populates the list immediately, offline; (2) `fetch → (ok → re-classify + reconcile | fail/old-schema/empty → no-op)` upgrades it in the background. On fetch failure (offline, non-2xx, old-schema, parse error) the user-visible result is the bundled model list (possibly an older `rules_version`). (C)

---

## 4. Contract

### 4a. Model resolution & merge (C)
1. The model list = `rules.tiers[classify(signals)].models` (internal key, D24) materialized through the §0c stub-build (each candidate → synthesized pair → `hfAsModel`; multimodal candidates also push their projector stub). Result `origin: HF`, merged where `defaultModels` was merged.
2. **No UI change.** Resolved stubs render through the existing `ModelCard` / grouping path; no new screen, section, card, or primitive.
3. Fetched rules override bundled rules; bundled rules are the always-present offline floor (statically imported).
4. A model downloads via the existing HF path (`checkSpaceAndDownload` → deterministic `downloadUrl` → `getModelFullPath` HF branch → `models/hf/...`). The primary download needs **no** pre-tap HF resolve; only the integrity/template HF-derivable data self-heals online at/after download (§0e).
5. `getOriginalModelName` has no `defaultModels` lookup (delegates to `getDisplayNameFromFilename`); rule-model names come from the optional `display_name` else `hfAsModel`'s derived name.
6. **id = `hf_repo + '/' + hf_filename` (= `author/repo/filename`)** — same convention `hfAsModel` and legacy PRESET ids use; this keeps migration/reconcile (keyed on `model.id`) and `isRulePreset` prune working unchanged. The candidate's `model` key is NOT the id.

### 4b. Hard invariants (C)
- **I1** — Rule stubs ARE the model list (`origin: HF` via `hfAsModel`); no separate suggestions list.
- **I2** — `classify` is pure, deterministic, total (last-resort floor → `low`).
- **I3** — Deterministic `downloadUrl`; no pre-tap HF resolve for the primary file. Only HF-derivable `lfs`/template self-heal online via the existing path (§0e).
- **I4** — Reuse `hfAsModel`; add no transform. The stub-build synthesizes the minimal `{hfModel, modelFile}` it reads.
- **I5** — `defaultModels.ts` is removed, not retained; its 3 consumers are re-sourced (§7).
- **I6** — Migration preserves every already-downloaded model regardless of origin.
- **I7** — Offline never breaks the list; bundled rules are imported and applied without awaiting the network fetch.
- **I8** — A multimodal candidate materializes its mmproj projector stub into `ModelStore.models` (`addHFModel`-style), so the download path's `this.models.find(m => m.id === projModelId)` resolves. The projector sibling carries a deterministic `url` so its stub `downloadUrl` is non-empty.
- **I9** — Every download target's path segments (`author`, `repo`, `hf_filename`; and `mmproj` equivalents) pass `isSafePathSegment` at parse BEFORE the deterministic `huggingface.co` URL is built; the HF token is only sent to `huggingface.co`. A candidate whose `hf_repo` lacks exactly two non-empty parts, or any segment fails, is dropped at parse. `isHuggingFaceUrl` on the derived URL is defense-in-depth only, not the boundary.
- **I10** — Reconcile keeps the list equal to the current rule set: it prunes non-downloaded rule-provenance (`isRulePreset`) entries no longer resolved, and never prunes downloaded models (any origin) or user-added HF/LOCAL models.

### 4c. Classifier resolution (C)
- iOS: `machine → device_id_to_chip → chip_to_class`; miss → `device_family_fallback`; then `ram_bands → tier_matrix`.
- Android: `socModel → soc_model_to_class`; miss → `hardware → hardware_to_class`; miss → `cpu_heuristic` (`features_any`/`features_all`/`max_freq_mhz_min`); then `ram_bands → tier_matrix`.

### 4d. Component renders (C)
- Model picker (`ModelsScreen`, unchanged): downloaded/HF/local + rule-resolved `origin: HF` stubs from `ModelStore.models` via the existing `ModelCard` grouping. No static PRESET section, no suggestions section.
- Download path (existing HF path): tap → deterministic `downloadUrl` download/progress in the existing card.

### 4e. Native signals (C)
- iOS `machine`: `RNDeviceInfo.getDeviceId()`.
- Android `socModel`/`cpuFeatures`/`hardware` (`Build.HARDWARE`)/`maxFreqMhz` (big-core max freq): `NativeHardwareInfo.getCPUInfo()`; `hardware` + `maxFreqMhz` are distinct fields kept separate from the coalesced chipset.

---

## 5. Single-writer rule (C)

| Field | Single writer |
| --- | --- |
| `ModelStore.deviceTier` | `classify()` result in `resolvePresets` (bundled), then `upgradeToFetchedRules` (fetched) |
| `ModelStore.rulesVersion` | bundled selection in `resolvePresets`, then fetched selection in `upgradeToFetchedRules` |
| `ModelStore.models` (rule stubs) | reconcile path (`hfAsModel` on synthesized pairs, not `defaultModels`) |
| `DeviceRules.tiers[T].models[]` (internal) | `parseCandidate`/`parseTiers` — the sole wire-`candidates`→internal-`models` rename site (D24) |
| `Model.isRulePreset` (provenance) | `resolvePresetModels` (set on every materialized stub) |
| `Model.downloadUrl` (rule stub) | stub-build (deterministic `/resolve/main`) |
| device signals | `readDeviceSignals` (read-once) |
| model download | existing `checkSpaceAndDownload` |
| HF-derivable `lfs`/template | `fetchAndUpdateModelFileDetails` at download (existing self-heal) |
| HF auth header attachment | `DownloadManager.startDownload` (host-gated to `huggingface.co`) |
| Lookie default model | `LOOKIE_DEFAULT_MODEL` constant (carries an `hfModel` so it downloads via `downloadHFModel`) |
| `ModelStore.version` / re-merge gate | `initializeStore` (gate `version < MODEL_LIST_VERSION`) |

Cross-store reads: download URLs are public `/resolve/main` — no HF token needed.

**Deferred cleanups (out of scope):** unify iOS/Android signal reads behind one native call; periodic background rules refresh beyond the init gate; CI step to refresh the committed bundled JSON; support `mmproj.hf_repo !== hf_repo` (cross-repo projector — none ship today, D10).

---

## 6. Migration policy (C)

On `version < MODEL_LIST_VERSION` (bumped to 15, single 14→15 bump), `mergeModelLists` runs once; preset resolution + reconcile run every init:

1. Keep every `isDownloaded` model regardless of origin (incl. legacy PRESET).
2. Drop non-downloaded PRESET/rule stubs (re-derivable from rules).
3. No static re-inject — the list is the §0c stub-build of `rules.tiers[deviceTier].models` (internal key, D24; multimodal candidates also push projector stubs, I8).
4. **Reconcile presets by the full `model.id` (`author/repo/filename`) across origins** (NOT `id && origin`, NOT `{repo,filename}`): `hfAsModel` builds the same `id` from a candidate's `hf_repo` + `hf_filename` as a legacy PRESET's `id`, so the key is origin-spanning AND collision-free across authors sharing a repo name. The reconcile suppresses the rule stub when a downloaded model with the same `id` exists at **any** origin, keeping the downloaded record (and its `models/preset/...` file). This covers Case A (legacy PRESET downloaded), Case B (HF downloaded), and Case C (not downloaded → resolves as `origin: HF`).
5. `MODEL_LIST_VERSION` lives in `ModelStore.ts` (single 14→15 bump — not re-bumped).
6. **Steady-state prune.** `reconcilePresets` is two-sided: before appending the fresh set it prunes non-downloaded `isRulePreset` entries whose `id` is not in the fresh set (a newer `rulesVersion` dropped them or the device re-tiered), so the list stays equal to `rules.tiers[tier].models`. Downloaded models (any origin) and user-added HF/LOCAL models are never pruned. (I10)

---

## 7. Cutover — the 3 `defaultModels.ts` consumers (C)

`defaultModels.ts` is removed with zero references; its consumers are re-sourced:

| # | Consumer | Re-sourced to |
| --- | --- | --- |
| 1 | `createBasicModelFromReference` (`PalStore.ts`, degraded fallback) | generic `chatTemplates.default` + `defaultCompletionParams` (D17) |
| 2 | `getOriginalModelName` (`formatters.ts`) | `getDisplayNameFromFilename`; no `defaultModels` lookup (D18) |
| 3 | `initializeLookiePal` (`PalStore.ts`) | `LOOKIE_DEFAULT_MODEL` offline constant in `builtinPalModels.ts`, carrying an `hfModel` (SmolVLM repo subset: LLM + mmproj siblings) so the download warning routes through `downloadHFModel → addHFModel` (D15, D20) |

---

## 8. Decisions (D)

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Consume the thin schema; defer HF-derivable data (oid/lfs/templates/sibling URLs) to download (no bake) | Less JSON, fewer app LOC; matches an HF-browser add |
| D1b | Schema owned in `a-ghorbani/pocketpal-device-rules` | App imports/fetches, never resolves per model |
| D2 | id = `hf_repo/hf_filename`; `display_name` → name; candidate `model` not used as id | Keeps migration/reconcile/`isRulePreset` working unchanged |
| D3 | No app/CI generator; commit thin JSON, import as floor | Thin JSON is HF-derivable-free; nothing to bake |
| D6 | Migration: keep downloaded any-origin; reconcile by `model.id` across origins | Origin-spanning AND collision-free key |
| D7 | Single 14→15 `MODEL_LIST_VERSION` bump | Data-driven list |
| D8 | Reconcile by `model.id`, NOT `id && origin` | Else legacy PRESET + new HF dup-card and re-download |
| D9 | Skip candidates missing required fields; ignore informational ones; fetch falls to floor on empty/old-schema | Lets the JSON evolve without app breakage |
| D10 | Assume `mmproj.hf_repo === hf_repo`; cross-repo projector out of scope | `hfAsModel` pairs the projector within the LLM repo; none ship cross-repo |
| D15 | Lookie default = offline constant, not network resolve | Vision model outside tiers |
| D17 | `createBasicModelFromReference` fallback → `defaultCompletionParams` + default chat template | Generic params suffice (degraded path) |
| D18 | `getOriginalModelName` is filename-derived for all | No `defaultModels` dependency |
| D19 | Primary guard = `isSafePathSegment` on split `hf_repo` parts + `hf_filename`; `isHuggingFaceUrl` on the derived URL is defense-in-depth | Derived URL host is hard-coded → tautological; path segments are the real risk |
| D20 | Lookie constant carries an `hfModel` with mmproj siblings | Routes the warning's download through `downloadHFModel` |
| D21 | Reconcile/dedup key = full `model.id`, not `{repo,filename}` | Origin-spanning AND collision-free across authors with the same repo name |
| D22 | Bundled floor applied without awaiting the fetch; fetched override folded in fire-and-forget | Fresh install on slow network is never empty while a fetch is in flight |
| D23 | `reconcilePresets` prunes stale non-downloaded `isRulePreset` entries | List stays equal to the current rule set |
| D24 | Wire key `candidates[]`; internal parsed key stays `models[]`; rename once in `parseCandidate` | Keeps `rules.ts`/`types.ts` `.models` reads genuinely unchanged |
| D25 | Explicit `mmproj.hf_filename` fixes the projector quant at authoring; no app quant-match | We own the JSON; bypasses `getRecommendedProjectionModel`; enforced by a pre-merge gate |

---

## 9. Edge cases (C)

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | Offline / fetch fails | imported bundled rules → list renders (I7) |
| 9b | Malformed fetched JSON | parse throws in `fetchRules` → `null` → bundled floor; never crash |
| 9c | Candidate missing `hf_repo`/`hf_filename`/`model` | skip that candidate; rest render |
| 9d | Old fat `models[]` or otherwise incompatible hosted JSON | parses to empty tiers → `fetchRules` returns `null` → bundled floor |
| 9e | `platform` mismatches `Platform.OS` | fetched rules treated invalid → bundled floor |
| 9f | Device unknown to classifier | last-resort floor → `low` tier (I2) |
| 9g | Legacy downloaded PRESET same `model.id` as a rule stub | reconcile keeps PRESET download, suppresses HF stub; PRESET file still found |
| 9h | Already-downloaded HF model also in rule list | same id → reconcile keeps download, suppresses stub |
| 9i | Two tiers list the same `model.id` | dedup by `model.id` at stub-build; first wins |
| 9j | Multimodal candidate | synthesize `siblings = [llm, mmproj(url, size)]`; LLM + projector stubs pushed; fit adds the projector size; both download; lfs self-heals online (I8, §0c) |
| 9k | Lookie pal init offline | `LOOKIE_DEFAULT_MODEL` constant, no network |
| 9l | `hf_repo` has zero slashes, or ≥2 slashes, or an empty part | split yields ≠2 non-empty parts → skip candidate at parse (I9) |
| 9m | `..` / path separator in `author`/`repo`/`hf_filename` (or `mmproj` equivalents) | `isSafePathSegment` rejects → skip candidate at parse (traversal guard, D19) |
| 9m2 | Derived URL somehow off-`huggingface.co` (cannot happen given the template) | `isHuggingFaceUrl` defense-in-depth assertion drops it; never the boundary |
| 9n | Multimodal candidate whose `mmproj` segments fail, or `mmproj` missing / no `size_bytes` | skip the whole candidate (never ship a vision model with an unvalidated projector path) |
| 9o | Newer `rulesVersion` drops a model the device hadn't downloaded | reconcile prunes the stale non-downloaded `isRulePreset` stub (I10, D23) |
| 9p | Two authors share a repo name + filename | distinct `model.id` → both kept (no cross-author collision, D21) |
| 9q | User taps Download on the Lookie warning | routes through the model's `hfModel` → `downloadHFModel → addHFModel` materializes LLM + mmproj and downloads both (D20) |

---

## Caveats (data/runtime — not schema blockers)

- Multimodal `min_ram_gb` may exclude projector memory. The disk/fit check additively counts the projector via the synthesized sibling (§0c); `min_ram_gb` itself stays advisory. Affects fit accuracy, not correctness.
- Newly-added vision models need a real **on-device vision load + inference check** before relied on — a runtime-support gate, not a schema concern. Part of the operational pre-merge gate alongside the Android `getCPUInfo()` check.
- **Projector-quant fit is an authoring responsibility (D25).** The explicit `mmproj.hf_filename` bypasses `getRecommendedProjectionModel`'s quant-match, so the pre-merge gate must validate the authored projector quant pairs sanely with the LLM quant per multimodal candidate. No app-side validation exists.
- **Offline-integrity cost (thin trade-off).** Integrity-checking an already-downloaded thin-stub model requires **one HF metadata fetch** (the deferred `lfs`) on first check, via `checkModelFileIntegrity → fetchAndUpdateModelFileDetails`. The superseded fat-bake avoided this hop. Acceptable: the download itself is already online, and the result caches after the first resolve.

---

## Cross-repo ordering

The `rules.<platform>.json` schema (thin `candidates[]` with explicit `mmproj`, `schema_version 1.2.0-draft`) is owned in `a-ghorbani/pocketpal-device-rules`. The app ships the committed thin bundled floor and tolerates the hosted JSON still being an incompatible schema (falls to the floor), so neither repo blocks the other. The hosted-JSON regeneration to the thin schema is a separate, user-owned step.
