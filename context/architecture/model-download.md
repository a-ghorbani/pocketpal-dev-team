# Model Download (Android)

**Not on `main` yet:** this describes branch `feature/TASK-20261004-1030` (resumable downloads with a user-initiated job on Android 14+). Until it merges, `main` downloads in a monolithic `DownloadWorker` observed through WorkManager LiveData.

How an Android LLM model file gets from Hugging Face onto disk: scheduling, the shared download loop, resume safety, stop semantics, and the JS signals. Not covered: iOS downloads (RNFS in `DownloadManager`), TTS/ASR model downloads, and which models exist (`model-loading.md`). The User-Agent wire is in `deep-linking.md`.

## Code map

Native paths are under `android/app/src/main/java/com/pocketpalai/download/` (Kotlin package `com.pocketpal.download`).

| Path | Role |
| --- | --- |
| `DownloadModule.kt` | TurboModule: resolves RN inputs, calls the controller, collects the Room row per download and emits JS events |
| `DownloadEvents.kt` | row → JS event mapping (`event()`, `endsObservation`) and `percent` |
| `DownloadController.kt` | every control operation (start/upsert, pause, resume, retry, cancel, active, reattach), each on `Dispatchers.IO`; no RN types |
| `DownloadScheduler.kt` | `RunnerScheduler`: UIDT on API 34+ (`UidtPort` / `JobSchedulerUidt`, namespace `downloads`), WorkManager fallback (`WorkPort` / `WorkManagerPort`) |
| `DownloadEngine.kt` | the runner-agnostic loop: mutex, entry CAS, legacy adoption, request/validate/write, commit, stop bookkeeping; shared OkHttp client; User-Agent |
| `DownloadRuns.kt` | in-process registry: destination mutexes, per-destination start locks, per-run `StopSignal`s |
| `DownloadWorker.kt` | WorkManager runner (all APIs): `RESCHEDULE` → `Result.retry()` |
| `DownloadJobService.kt`, `DownloadNotifications.kt` | UIDT runner (API 34+): `setNotification` (re-posted only when title or percent changes), stop-reason mapping, `jobFinished` |
| `DownloadEntity.kt`, `DownloadDao.kt`, `DownloadDatabase.kt` | Room `downloads` table (v3: `etag`, `stalledRuns`, `failureUnreported`), CAS queries, `MIGRATION_2_3` |
| `android/app/src/main/AndroidManifest.xml` | `RUN_USER_INITIATED_JOBS`, `POST_NOTIFICATIONS`, the `DownloadJobService` declaration |
| `src/services/downloads/DownloadManager.ts` | JS job map (`isDownloading`), native event handling, asks `POST_NOTIFICATIONS` before an API 34+ start |
| `src/utils/androidPermission.ts` | `ensureNotificationPermission`: asks at most once per app session |
| `src/store/ModelStore.ts` | download callbacks, `downloadError`, `retryDownload` |
| `src/components/DownloadOverlay/DownloadBanner.tsx` | progress row, and the failure row (status alone on line 1; pal or model name and the +N badge on line 2) with Retry |

## How it works

`startDownload` → `DownloadController.start` takes the destination's start lock and upserts by destination: it reuses the newest QUEUED/RUNNING/PAUSED/FAILED row for that path (keeping its id and `.part`) or inserts a fresh one, retires every other live row for the path, then `RunnerScheduler.schedule`. The module attaches its row collector only after the row reads QUEUED.

`schedule` cancels any existing runner, then on API 34+ builds a UIDT `JobInfo` (job id `downloadId.hashCode()`); if `schedule()` does not return `RESULT_SUCCESS` or throws, it enqueues WorkManager unique work `download_<id>` with `REPLACE`.

Either runner registers a `StopSignal` and calls `DownloadEngine.get(context).run`. The engine takes the destination mutex, CASes QUEUED|RUNNING → RUNNING, adopts a pre-upgrade in-place partial (renamed to `.part` when `totalBytes` is known, deleted when it is not), then loops: request the row's `url` with `Range: bytes=<.part length>-`, validate, append, write progress on the interval, and at clean EOF verify size, rename `.part` → destination, CAS → COMPLETED. Transient errors retry in-run with Range (backoff 2 s doubling to 30 s) until 2 minutes pass without a byte; then the run ends QUEUED and the runner reschedules, or FAILED after 5 consecutive zero-byte runs.

The module's collector maps the row (`DownloadEvents.kt`): RUNNING → `onDownloadProgress`, COMPLETED → `onDownloadComplete`, FAILED → `onDownloadFailed` with the kept `progress`, then `failureUnreported` is cleared; the collector stops on COMPLETED, FAILED or CANCELLED. `onDownloadCancelled` comes from `cancelDownload` itself. On app start `syncWithActiveDownloads` → `getActiveDownloads` (newest live row per destination, plus FAILED rows with `failureUnreported` whose destination has no live row) → `reattachDownloadObserver`, which schedules only the newest QUEUED/RUNNING row with no runner and attaches the collector either way.

Row status: insert/upsert → QUEUED → RUNNING → COMPLETED | FAILED; system stop RUNNING → QUEUED; the engine writes CANCELLED for a row superseded by a newer COMPLETED one (found during adoption); the controller writes PAUSED, CANCELLED (cancel, and retiring superseded live rows), and QUEUED (start, resume, retry). COMPLETED and CANCELLED are terminal and never reused.

## Contracts and invariants

- **`.part` deletion has a closed list**: `DownloadController.start` (fresh row or url change) and `cancel`; in the engine, a validator mismatch (restart from 0), a size mismatch at commit, and truncation when a `200` answers a Range request. A system stop, process kill, user stop or transient failure never deletes it.
- **`destination` exists only after a verified commit** (`Transfer.commit`), except a pre-upgrade in-place partial: `adopt` renames it to `.part` only when the row's `totalBytes` is known, and deletes it otherwise (after `resetResource` zeroes `totalBytes` its bytes may belong to another url, and a `206` from the new url would splice them in).
- **Every engine status and progress write is a CAS on RUNNING** (entry: QUEUED|RUNNING), made while holding the destination mutex. The engine never overwrites PAUSED, CANCELLED or FAILED. A progress write that misses ends the run as a stop.
- **Every `.part` mutation runs under `DownloadRuns.withDestinationLock`**, by the engine for a whole run, by the controller for deletion. `start` is serialised per destination by `withStartLock`, so at most one live row per destination after `start` or `active`.
- **Bytes are appended only after a `206`** whose Content-Range start equals the `.part` length, whose total equals the known `totalBytes`, and whose strong ETag matches the stored one when both exist. Otherwise `.part` is discarded and the run restarts from 0, once; a second mismatch fails "Remote file changed during download".
- **COMPLETED requires** `.part` length == `totalBytes` (when known) and a successful rename.
- **`onDownloadFailed` fires only for a FAILED row.** Cancel and system stops never produce it (`download-cancel.spec.ts` asserts no error dialog).
- **Every FAILED reaches JS once, even across process death.** Any write to FAILED sets `failureUnreported`; requeue or any status write away from FAILED clears it, and so does the module after emitting `onDownloadFailed`. `getActiveDownloads` returns those rows, so a failure in a process without JS (a WorkManager rerun) shows on next open.
- **A FAILED row's `downloadedBytes` is what `.part` still holds** (0 when the engine deleted it): every engine FAILED write (error, user stop, stall bound) goes through `DownloadDao.fail`. JS `onError` sets `progress` to that kept value on Android and to 0 on iOS.
- **Single writers:** the engine owns RUNNING/QUEUED-on-stop/COMPLETED/FAILED, CANCELLED for a superseded row, and `downloadedBytes`/`totalBytes`/`etag`/`stalledRuns` during a run; `DownloadController` owns QUEUED on start/resume/retry (`requeue` also zeroes `stalledRuns`), PAUSED, CANCELLED, `url`, `authToken`, and on a url change `resetResource` zeroes `etag`/`totalBytes`/`downloadedBytes`. JS never deletes `.part`.
- **No FGS type:** no `foregroundServiceType`, no typed `FOREGROUND_SERVICE_*` permission, no `setForeground`/`startForeground`. WorkManager's inherited plain `FOREGROUND_SERVICE` and untyped `SystemForegroundService` stay.
- **JS "is downloading" is `modelStore.isDownloading(id)`**, never `progress > 0`. `ModelFileCard` fills from `progress` only while downloading or downloaded, and `ProjectionModelSelector` shows its spinner only while downloading.

## Traps and decisions

- **The HF CDN ignores `If-Range`.** A wrong validator still gets a `206`. `If-Range` is sent but gives no protection; the guard is the client-side ETag and Content-Range check on every `206`.
- **The CDN `ETag` is the xet hash**, not the resolve `302`'s `x-linked-etag` (sha256). Only CDN ETags are compared.
- **Every attempt re-requests the `huggingface.co` resolve URL.** The redirect target is signed and rotating; it is never persisted.
- **`CoroutineWorker` cancels the coroutine on stop**, so Room calls in that coroutine throw. Stop bookkeeping runs in `NonCancellable`, and the blocking loop runs as a non-child `async`: a structured child would make the scope wait out a blocked socket read (up to the 60 s read timeout). Cancellation raises `signal.stop`, which cancels the OkHttp `Call`.
- **Stop signals are per run instance.** `unregister` removes only its own signal; a REPLACE or resume can overlap an unwinding run of the same id. A user stop is raised only on the runner's own signal.
- **The mutex is keyed by destination, not id**, and taken before the entry CAS: a status CAS cannot tell two runs of one row apart, and duplicate pre-upgrade rows share one `.part`.
- **The start lock is separate from the destination mutex** because the engine holds the mutex for a whole run; `start` takes the mutex only briefly to delete `.part`, after stopping runners.
- **Controller work runs on `Dispatchers.IO`** although the module scope is `Dispatchers.Main.immediate`: `.part` deletion (multi-GB) and JobScheduler binder calls must stay off the UI thread.
- **UIDT stop reasons:** `CANCELLED_BY_APP` → no write; `USER` (Task Manager, process alive) → FAILED "Download stopped", reported once through `failureUnreported`; anything else → QUEUED and reschedule. `jobFinished` is called only if `onStopJob` has not claimed the job.
- **Process kills resume by design** (recents swipe, force-stop, OOM, update): the row stays RUNNING/QUEUED and the entry CAS accepts RUNNING, so a job rerun or reattach resumes it. A swipe must never read as a failure.
- **UIDT is refused when the app is not visible**, so a resume after restart typically falls back to WorkManager and stays there.
- **The notification is requested on API 34+ start but never required**, at most once per app session so a model and its chained projection or draft downloads prompt once; a denied UIDT still runs and shows in Task Manager.
- **`.part` writes are buffered (64 KB) and flushed on each progress tick and at EOF**, so during a stall up to one buffer sits in memory and a process kill loses only that.
- **A storage error stays permanent through close.** `openPart` returns the raw file stream and the engine owns the buffer: after a write or flush error it closes only the raw stream (the buffer is dropped, so nothing is written after a recorded failure), and the normal close is itself a storage check. Letting `use` close the buffer re-flushes, throws, and `attempt` maps that IOException to a transient retry that never gives up (each retry buffers bytes, so `lastByteAt` advances).
- **`networkType` from JS is stored but not applied** (WorkManager always uses `CONNECTED`, UIDT `NETWORK_TYPE_ANY`).

## Verification

- JVM unit tests: `android/app/src/test/java/com/pocketpalai/download/` (engine on MockWebServer, controller, scheduler, worker, migration, DAO, runs, row → event mapping, job service). On the Linux aarch64 dev host Robolectric's native SQLite is unavailable, so tests use Room's `BundledSQLiteDriver` and fake WorkManager; run `./gradlew --init-script <hermes override> :app:testProdDebugUnitTest` (the task depends on the JS bundle). CI does not run them.
- JS: `ModelStore.test.ts`, `DownloadBanner.test.tsx`, `DownloadManager.test.ts`, `androidPermission.test.ts`, `ProjectionModelSelector.test.tsx`, `ModelFileCard.test.tsx`.
- Manifest: `:app:processProdReleaseMainManifest`, then grep the merged manifest for `foregroundServiceType` and `FOREGROUND_SERVICE_[A-Z]` (expect none).
- By hand: throttle with a CONNECT proxy (`adb reverse tcp:8888 tcp:8888`, `settings put global http_proxy 127.0.0.1:8888`), stall or drop mid-body, and expect a `206` resume. Fleet phones are battery-allowlisted, which hides background limits: `dumpsys deviceidle whitelist -<pkg>` first. Stop a UIDT job with `cmd jobscheduler stop -n downloads -s <reason> <pkg> <jobId>` (7 connectivity, 13 user).
