# Evidence and Decisions

How a story's `evidence.md` and `decisions.md` are planned, filled, and read. Pipeline runbook: [`pipeline.md`](pipeline.md).

## Evidence plan

`evidence.md` (`templates/evidence-template.md`) lists what the change must show to count as done:

1. **The claim.** A bug: the reporter's symptom reproduced on `main` (red) before the fix, then the same steps on the branch (green). A feature: the done check in the requester's words, one that can fail.
2. **Where** it must hold: platforms; real system vs fake.
3. Every risk row below that matches what the request touches.

| The change touches | It always needs |
| --- | --- |
| a surface an existing e2e spec drives (grep `e2e/specs` for the changed screens, stores, services) | those specs, on the PR's CI APK (`/run-pr-e2e`) |
| a llama.rn bump, backend selection, inference code | `bench` smoke and focused, compared with the baseline and the previous llama.rn PR; `memory-profile`; a device run with a stateful (hybrid / recurrent) and a multimodal model as well as a transformer |
| model loading | `bench` smoke and `memory-profile` |
| native dependencies, Gradle, Podfile, podspecs, ProGuard / dependency trims | iOS and Android release builds; `bench` smoke; a real-store `.e2e` smoke build plus a negative control |
| purchases, store, entitlements, Plus | the `iap-purchase`, `iap-restore`, and `iap-recovery` specs and a real store sandbox run, not only FakeStore |
| remote-server wire format | a strict OpenAI-compatible server as well as llama-server; read what the server applied (`/slots`), not the status code |
| downloads, network resilience | the slow-network proxy (stall, resume, terminal failure) and a permission decline |
| sheets, keyboard, layout | iOS and Android, rotation, multi-window or tablet width (`wm density`), dark mode, from a focused input |
| a heuristic that filters, blocks, or parses | false-positive cases that must still pass, alongside the hostile ones |
| imported or external data reaching a file, network, or render sink | a hostile input at each sink that is reachable on `main` |
| voice, audio, mic, TTS / ASR engines | the voice specs and `tts-memory-profile`; a device run covering first-time setup, interruption, and a model that does not fit |
| iOS-only code paths | a run through `ios-router`; this host has no iOS |
| render-heavy paths, perf claims | the Reassure gate; an on-device A/B for any claimed speed-up or regression, interleaved in one session (iOS: A B B A, cooled; `skills/bench`) |

| Stage | Evidence work |
| --- | --- |
| intake | writes the claim, the platforms, the matching rows |
| tester, repro mode (bugs) | runs the claim on `main` before any code and records the red receipt and the cause |
| architect | adds an item per canonical scenario and per required WHAT section it fills |
| implementer, fix rounds | add items for touched surfaces the plan didn't foresee |
| tester | runs each item as a command, spec, or device run and records the receipt. **CI APK** rows (e2e specs, bench, memory profiles, store runs) run post-PR on the draft PR's CI APK; compare any red against `main` before calling it |
| pipeline-reviewer | checks every pre-PR item has a receipt or a documented reason it could not run; posts the **evidence comment** (what was proven and its receipt, public references only, captures inline); the tester appends post-PR rows |

Any stage may add an item; dropping one needs a reason in its row. A capture is an evidence item whose receipt is an image.

## Decisions and product calls

`decisions.md` logs every decision except the architect's engineering ones (WHAT §8); later stages and reviewers read it.

| Kind | Who decides | Rule |
| --- | --- | --- |
| **Fact** (library behaviour, platform limit, what a server accepts) | nobody: it is proven | `(C)` read from code at `file:line`, or `(F)` proven by a spike with its receipt |
| **Product call** (user-visible behaviour the request leaves open, copy, accepting a limitation or regression) | the operator | logged with a recommended default, citing `research.md` when it ran; one that shapes the contract is `NEEDS_INPUT`, the rest proceed on the default and are listed in the stage reply |
| **Engineering choice** | the architect | a WHAT (D) row, defended against a real alternative |
| **Prior decision** (existing code shaped that way on purpose) | its original PR | logged by the repro with the PR; a fix that undoes it is a product call |
| **Operator or PM ruling** | as given | logged verbatim with its date |
| **Review dismissal** | the review's refutation | logged from `final.md` by the orchestrator, its only writer; later rounds don't re-raise it without new evidence |

A decision is reversed only by a new row that names the one it replaces.
