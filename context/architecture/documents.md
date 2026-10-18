# Documents (pending PR)

## Purpose

Attaching PDFs and plain-text files to a chat message and getting their text to the model, local or remote, within a fixed cap: small documents go in whole, larger ones are searched and only cited excerpts are sent. Nothing is cut without the chip saying so. Covers the document store (copy, extraction, ranges, cleanup), the plan (full or searched), chunking and BM25 retrieval, the model-facing rendering, and the budget check. The composer, send funnel and message chip are in `chat-flow.md`; the system-message rule and the `read_url` allowlist are in `pals-and-talents.md`; the native dependency is in `release.md`. Projects, embeddings and a `search_documents` talent are not built; the store is per-document and session-agnostic, and retrieval sits behind a `Retriever` interface, so they can reuse both.

## Code map

| Path | Role |
| --- | --- |
| `src/services/documents/types.ts` | `DocumentRef`, `ComposerDocument`, refusal reasons, limits, `REPLY_RESERVE` |
| `src/services/documents/store.ts` | `importDocument`, `setDocumentPageRange`, `loadDocumentTexts`, `findMissingDocuments`, `releaseDocuments`, `sweepOrphanDocuments`, the held-id API |
| `src/services/documents/paths.ts` | `documents/<id>/` layout, derived from `DocumentDirectoryPath` at call time |
| `src/services/documents/render.ts` | full block, searched stub, missing line, excerpt block and citations; `documentContentFor`, `documentKey`, `modeOf` |
| `src/services/documents/plan.ts` | pure `documentPlan`: each new ref's mode, `excerptBudget`, the verdict (`fits | unknown | over{reason}`) |
| `src/services/documents/estimate.ts` | `estimateDocTokens`: one per CJK / kana / Hangul / Thai code point (CJK punctuation and fullwidth forms included), a third per other |
| `src/services/documents/chunk.ts` | `chunkDocument`: page-bounded passages of ≤ 200 estimated tokens |
| `src/services/documents/retrieve.ts` | `retrieveExcerpts` (BM25 `bm25Retriever`, page mentions, fallback query, selection, exact trim), the index LRU |
| `src/services/documents/budget.ts` | `hasDocuments`, `documentTokens`, `displayTokens` |
| `src/utils/documentCounting.ts` | `documentCountingOptions`: the only `tokenize` call site |
| `src/specs/NativePdfText.ts`, `ios/PocketPal/PdfTextModule.mm`, `android/.../PdfText{Module,Package}.kt` | `extractPages(path, from, to)`: PDFKit on iOS, PdfBox-Android on Android |
| `src/components/DocumentChip/`, `DocumentRangeSheet/`, `DocumentBudgetSheet/` | chip (composer and message), page-range sheet, over-budget sheet |

## How it works

1. **Import** (`importDocument`, called per picked file by `ChatInput`): allocate a uuid and hold it, classify by extension, `keepLocalCopy` into the caches dir and move to `documents/<id>/source.<ext>`, extract, apply limits, write `text.all.json`, count. A refusal deletes the dir and unholds. A PDF over 500 pages, or whose text is over 1M chars, returns `needs_range` without writing text.
2. **Range** (`setDocumentPageRange`, from the range sheet): returns a new ref with the same id and `pageRange`; reads `text.<from>-<to>.json` if it exists, else extracts that range from `source.pdf` and writes it once.
3. **Plan** (`documentPlan`, inputs from `planInputs` in `useChatSession`, only when documents are involved): history refs keep their persisted mode (absent = `full`). Pass 1 makes a new ref `searched` when pinned, over 2048 estimated tokens, or over the chat's 2048 full total; pass 2 (known window) demotes new `full` refs in reverse attach order until the full load plus one excerpt's floor fits `effectiveContextLength − 1024`. `excerptBudget = min(2048, room)` when anything is searched. The funnel, the resend gate and the composer's mode prediction call it read-only through `evaluateSendBudget`.
4. **Send:** `sendUnderLease` plans again under the lease, stamps `mode` on copies of the new refs, and persists them on the user `Text` row (`metadata.documents`, beside `imageUris`). An `over` plan there writes nothing and returns `UndoneSend.verdict`; ChatView restores the composer once and opens the sheet. The visible `text` is what the user typed.
5. **Completion** (`prepareCompletion`): `loadDocumentTexts` over every ref, then `convertToChatMessages(rows, multimodal, resolver)` prefixes each user row with `documentContentFor(row.documents)`: full blocks, searched stubs, missing lines. The new message gets the same, plus, when `excerptBudget > 0`, `retrieveExcerpts` over every searched ref of the chat, queried by the typed text (the previous user text joins when fewer than 5 passages match a discriminative term), rendered as cited excerpts.
6. **Cleanup:** deleting sessions collects the ids their rows referenced and calls `releaseDocuments`; launch runs `sweepOrphanDocuments` once, detached.

```
picked → importing → ready | needs_range | refused(removed)
needs_range | ready ─range applied→ importing → ready | needs_range
any ─chip removed→ gone (files left for the sweep)
```

## Contracts and invariants

- **Never cut without the chip saying so.** A `full` document is never cut; a `searched` one shows "searched" on every chip and reaches the model only as cited excerpts. A request never goes out with a searched ref whose excerpt floor is unmet (that is `over`). The sheet has no "send anyway".
- **Fixed cap, whatever the window or engine** (`plan.ts`): whole-document text ≤ 2048 and excerpts ≤ 2048 estimated tokens per request. A big window never qualifies a document for `full`; the window only demotes. On local, the exact count trims excerpts, never below one.
- **`mode` has one writer**, `sendUnderLease` from its plan under the lease; it is immutable once persisted. `searchPinned` is written only by the composer (Search instead). `setDocumentPageRange` keeps `searchPinned` and clears `mode`.
- **Excerpts appear only in the message being sent** and are never persisted or replayed; the next turn renders that row with its stubs only. Each turn re-prefills one exchange; everything before it stays byte-stable.
- **Passages and indexes are derived in memory** from the write-once range text files (`CHUNKER_VERSION` in the cache key). Any later derived file lives in `documents/<id>/`, keyed by range and versions, written once, so release and sweep cover it.
- **Persisted `text` is only what the user typed.** Document text exists only in the range text files and in a run's API messages; copy, title, TTS, search and export see the typed text.
- **Blocks, stubs and lead lines are deterministic in `(ref, pages)`.** Delimiter is `id.slice(0, 8)`, English, no nonce or clock (`render.ts`). Retrieval is deterministic in (query texts, corpus, budget, chunker version, and the local model for the trim), so an unchanged regenerate sends the same bytes.
- **Documents go only in user messages**, so the one-system-message rule holds (`pals-and-talents.md`).
- **Document text, stubs, excerpts and retrieval queries never seed the `read_url` allowlist:** seeding takes the typed texts (`pals-and-talents.md`).
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
- **Cap first, window second.** The clarified intent rejects window-sized stuffing: a 26B model on a large remote window must not receive whole large documents.
- **Unknown window sends without a window check**: remote servers without `/props` have nothing to compare against; the caps still bound the request.
- **Token estimates are script-aware and conservative** (`estimateDocTokens`): chars/3 for other scripts, because chars/4 under-counted markdown tables and technical PDF text by up to about 1.5x (prose lands near 0.9x), and one per CJK / kana / Hangul / Thai character, which chars/4 under-counts about fourfold. Search talents keep their own estimator.
- **One excerpt-cost function** (`excerptCost` in `plan.ts`: overhead plus each passage and its newline) sets both the plan's floor and retrieval's selection; if they differ, a budget at exactly the floor selects nothing while the plan says it fits.
- **Retrieval is BM25 in JS** (k1 1.2, b 0.75, Lucene IDF, NFC-normalised word runs that include combining marks (Devanagari, Thai vowels), the same for queries and text; CJK / kana / Hangul / Thai as character bigrams; no stopwords): no model, no files. "p./pp./page(s) N–M" (English only) ranks those pages first. An excerpt is a passage plus its same-page neighbour when the budget allows, else one passage; at most 5.
- **Chunking is linear and yields**: `pagePieces` estimates any slice from prefix sums and cuts within a bounded window, and `chunkDocument` yields between pages and every 64 passages inside one (a text file is one page). A 1M-character file splits in about 0.1 s on a workstation; the old whole-remainder estimate took about 20 s. The LRU is bounded by indexed characters (4M), not entries, and holds nothing that changes results.
- **Passages are 50–200 estimated tokens where the page allows.** `splitPage` prefers the latest paragraph, sentence or space break that leaves both sides at least a quarter of the limit, so a heading never becomes a passage of its own and a page never ends on a stray tail.
- **Document text cannot open or close a block**: `<<<` before `BEGIN`/`END` `DOCUMENT`/`EXCERPT` (any case or spacing) in page or passage text becomes `<<\<`, deterministically, so prefix-cache bytes stay stable.
- **Document names are escaped inside quotes** (backslash, quote, line breaks) in headers, stubs, missing lines and excerpt delimiters, so a file name cannot close its quotes or forge a delimiter line.
- **The excerpt lead tells the model to say when the excerpts lack the answer** instead of guessing; the text is fixed English, like the rest of the block.
- **1024-token reply reserve is fixed**: `n_predict` defaults to unbounded, so it cannot size it.
- **Send still requires typed text**: `convertToChatMessages` drops empty-text rows, and their documents with them.
- **Orphans from composer removal and cancelled sends wait for the next launch.**

## Verification

- Unit: `src/services/documents/__tests__/` (`documentPlan`, `estimate`, `chunk`, `retrieve`, render, budget, store), `useChatSession.documents` (assembly, stubs and excerpts, turn-2 prefix, regenerate bytes, allowlist, plan under the lease), `useMessageActions.documents`, `ChatView.documents` (gate, holds, range, overflow, predicted modes, Search instead), `ChatInput.documents`, `ChatSessionRepository.documents`.
- By hand: a 120-page PDF on a local model, asking about a known page (≤ 5 excerpts, the page cited); a 500-page PDF's first turn on a low-tier Android (UI responsive while indexing); a remote llama-server log showing stub plus ≤ 2048 tokens of excerpts.
- By hand, both platforms: a 12-page text PDF (chip, block, typed-only bubble); a scanned PDF (`no_text`); a 1,200-page PDF (needs range, app responsive); 40 pages narrowed to 3–5; a password PDF (refused); on Android also an empty-user-password PDF (imports) with `adb logcat` free of `NoClassDefFoundError`.
