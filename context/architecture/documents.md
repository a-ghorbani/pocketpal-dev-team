# Documents (pending PR)

## Purpose

Attaching PDFs and plain-text files to a chat message and sending their full text to the model, local or remote, without ever truncating it silently. Covers the document store (copy, extraction, ranges, cleanup), the model-facing block, and the budget check. The composer, send funnel and message chip are in `chat-flow.md`; the system-message rule and the `read_url` allowlist are in `pals-and-talents.md`; the native dependency is in `release.md`. Projects and retrieval are not built; the store is per-document and session-agnostic so they can reuse it.

## Code map

| Path | Role |
| --- | --- |
| `src/services/documents/types.ts` | `DocumentRef`, `ComposerDocument`, refusal reasons, limits, `REPLY_RESERVE` |
| `src/services/documents/store.ts` | `importDocument`, `setDocumentPageRange`, `loadDocumentTexts`, `findMissingDocuments`, `releaseDocuments`, `sweepOrphanDocuments`, the held-id API |
| `src/services/documents/paths.ts` | `documents/<id>/` layout, derived from `DocumentDirectoryPath` at call time |
| `src/services/documents/render.ts` | `renderDocumentBlock`, `renderDocumentContent`, `documentContentFor`, `documentKey` |
| `src/services/documents/budget.ts` | pure `evaluateDocumentBudget`, `hasDocuments`, `documentTokens` |
| `src/utils/documentCounting.ts` | `documentCountingOptions`: the only `tokenize` call site |
| `src/specs/NativePdfText.ts`, `ios/PocketPal/PdfTextModule.mm`, `android/.../PdfText{Module,Package}.kt` | `extractPages(path, from, to)`: PDFKit on iOS, PdfBox-Android on Android |
| `src/components/DocumentChip/`, `DocumentRangeSheet/`, `DocumentBudgetSheet/` | chip (composer and message), page-range sheet, over-budget sheet |

## How it works

1. **Import** (`importDocument`, called per picked file by `ChatInput`): allocate a uuid and hold it, classify by extension, `keepLocalCopy` into the caches dir and move to `documents/<id>/source.<ext>`, extract, apply limits, write `text.all.json`, count. A refusal deletes the dir and unholds. A PDF over 500 pages, or whose text is over 1M chars, returns `needs_range` without writing text.
2. **Range** (`setDocumentPageRange`, from the range sheet): returns a new ref with the same id and `pageRange`; reads `text.<from>-<to>.json` if it exists, else extracts that range from `source.pdf` and writes it once.
3. **Send:** refs ride on the user `Text` row as `documents`, persisted in `metadata.documents` beside `imageUris`. The visible `text` is what the user typed.
4. **Completion** (`prepareCompletion`): `loadDocumentTexts` over every ref in the conversation plus the new message, then `convertToChatMessages(rows, multimodal, resolver)` prefixes each user row's content (or its leading `text` part) with `documentContentFor(row.documents)`. The same prefix goes on the new message.
5. **Budget** (`evaluateSendBudget` in `useChatSession`, only when documents are involved): `needed = estimate(system + fragments + tools + every non-document text) + Σ doc tokens`; `available = effectiveContextLength − 1024`. `fits | unknown | over{historyOverflow}`.
6. **Cleanup:** deleting sessions collects the ids their rows referenced and calls `releaseDocuments`; launch runs `sweepOrphanDocuments` once, detached.

```
picked → importing → ready | needs_range | refused(removed)
needs_range | ready ─range applied→ importing → ready | needs_range
any ─chip removed→ gone (files left for the sweep)
```

## Contracts and invariants

- **Never truncate silently.** The only reducers are a user-chosen page range and user removal; the over-budget sheet has no "send anyway" (`DocumentBudgetSheet`).
- **Persisted `text` is only what the user typed.** Document text exists only in the range text files and in a run's API messages; copy, title, TTS, search and export see the typed text.
- **The block is deterministic in `(ref, pages)`.** Delimiter is `id.slice(0, 8)`, English, no nonce or clock (`render.ts`), so turn N replays turn 1's bytes and prefix caches stay valid.
- **Documents go only in user messages**, so the one-system-message rule holds (`pals-and-talents.md`).
- **Document text never seeds the `read_url` allowlist:** seeding takes the typed texts (`pals-and-talents.md`).
- **A ref and each `(id, range)` text file are immutable once written.** Range changes write a new file; no path is stored, the dir is derived from the id at read time (the iOS container path changes across updates).
- **Files are deleted only by `releaseDocuments`, `sweepOrphanDocuments`, or an import's own refusal**, and only for an id that is neither referenced nor held. Never by a message delete, edit, regenerate or composer removal.
- **Held ids** (`store.ts`): the union of import holds (allocation until the caller adds the chip and calls `releaseImportHold`), composer holds (`setComposerHeld`, called synchronously by ChatView's single writer `updateComposerDocuments`), and send holds (`holdForSend` from the funnel or regenerate gate until the user row is persisted or the send settles).
- **Release and sweep re-read references when any hold was released mid-run** (`releaseEpoch` in `deleteUnlive`), so a send that persists and unholds between the snapshot and the delete is not lost.
- **A missing text file renders `[Attached document "<name>" is no longer available]` and counts 0 tokens**; the send is never refused for it (imported chats, deleted files).
- **Exact counts come only from the loaded local context** (`documentCountingOptions`); `tokenize` is unclaimed and may run outside the lease (`model-loading.md`). A count for another model id is ignored in favour of the estimate.

## Traps and decisions

- **Ranged extraction, not page-count refusal.** A huge PDF stays usable through a range; memory is bounded by the range (≤ 500 pages, ≤ 1M chars), not the file.
- **Text files are capped at 3,000,000 bytes before decoding**, and `RNFS.readFile` utf8 is lossy (Buffer); a NUL in the first 8 KB means binary.
- **Virtual Android files** convert to PDF when offered, else `text/plain`, else refuse.
- **Unknown window sends without a check**: remote servers without `/props` have nothing to compare against; server errors stay explicit.
- **1024-token reply reserve is fixed**: `n_predict` defaults to unbounded, so it cannot size it.
- **Send still requires typed text**: `convertToChatMessages` drops empty-text rows, and their documents with them.
- **Orphans from composer removal and cancelled sends wait for the next launch.**

## Verification

- Unit: `src/services/documents/__tests__/` (render, budget, store: refusals, staging cleanup, ranges, sweep/release with holds), `useChatSession.documents` (assembly, replay, allowlist, budget verdicts), `useMessageActions.documents`, `ChatView.documents` (gate, holds, range, overflow), `ChatInput.documents`, `ChatSessionRepository.documents`.
- By hand, both platforms: a 12-page text PDF (chip, block, typed-only bubble); a scanned PDF (`no_text`); a 1,200-page PDF (needs range, app responsive); 40 pages narrowed to 3–5; a password PDF (refused); on Android also an empty-user-password PDF (imports) with `adb logcat` free of `NoClassDefFoundError`.
