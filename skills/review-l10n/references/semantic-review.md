# Stage 4 — Per-language semantic review

Read from `skills/review-l10n/SKILL.md` when spawning language reviewers.

```bash
node skills/review-l10n/scripts/diff-entries.mjs "${SCRATCH}/head" "${SCRATCH}/base" \
  "${SCRATCH}/diff-report.txt" --manifest="${SCRATCH}/review-manifest.json"

# Split per language for parallel agents
awk -v scratch="${SCRATCH}" '/^## [A-Za-z_]+:/ {f=scratch "/diff-" $2 ".txt"; sub(":","",f)} f {print > f}' "${SCRATCH}/diff-report.txt"
```

For each changed wired language, spawn a `general-purpose` agent **in parallel**. Each agent gets:
- The path to its diff file only (never another language's file), plus its `feedback-<lang>.md` and `history-<lang>.md` when they exist.
- A language-specific prompt that:
  - States the app context (mobile, RN, local LLMs, Settings/Models/Chat).
  - Lists language-specific gotchas: orthography (e.g. Russian ё, missing measure word 个 in Chinese, Korean register mismatch), brand-name policy (keep `OpenAI`, `Groq`, `Hugging Face`, model names, engine names like `Kitten/Kokoro/Supertonic` in English).
  - Reminds: placeholders `{{name}}` must stay byte-identical.
  - Names the reference(s) for that language (table below) and grants WebFetch to consult them.
  - States the scope: **WRONG only** when `feedback.json` lists an active translator for the language; WRONG + AWKWARD otherwise.
  - Asks for output limited to AWKWARD/WRONG entries with key, en, lang, `kind`, one-line note, and `source` where required.

## Grounded findings — a norm needs a reference, not a belief

The failure this guards against is real: on PR #884 the Belarusian reviewer asserted
"the standard abbreviation is X" and "the genitive is Y" for a low-resource language,
with no source, and a native translator refuted every one with CLDR. A model's
confidence in a grammar rule is not evidence of the rule.

- Every finding carries `kind`: `meaning` (sense changed, English leaked, wrong term),
  `grammar`, `orthography`, `style`, `brand`, `placeholder`.
- `grammar` and `orthography` findings **must** carry `source`: the URL the reviewer
  actually fetched (CLDR data, a dictionary entry, a published style guide). The gate
  drops any without one. The reviewer's prompt must say this outright, and say that
  its own knowledge does not count. Language-model consensus is exactly what was wrong
  on PR #884.
- `meaning` findings need no external source — the English string and the app context
  are the evidence — but the note must say what the current text means and why that
  differs from the source.
- **Active translator → meaning only.** If `feedback.json` shows translator activity in
  the last 90 days for a language, the reviewer is told to report WRONG only. Style is
  that person's job, and thirty style notes on a volunteer's work is how a locale loses
  its translator. The gate enforces this even if the reviewer ignores it.
- **Cap.** At most 10 AWKWARD suggestions per language per run are posted; the rest are
  recorded in `decision.json` and mentioned in the report. Reviewers should put the
  most consequential first.

References to hand each reviewer (verify the URL works before relying on it; extend as
languages are added):

| lang | reference |
| --- | --- |
| any | CLDR data: `https://raw.githubusercontent.com/unicode-org/cldr/main/common/main/<code>.xml` (dates, units, relative-time abbreviations, plurals); survey tool `https://st.unicode.org/cldr-apps/v#/<code>/` |
| be | skarnik.by (ТСБМ + Belarusian–Russian dictionaries) `https://www.skarnik.by/` |
| ru | Грамота.ру `https://gramota.ru/` |
| uk | Словник.ua `https://slovnyk.ua/` · СУМ `https://sum.in.ua/` |
| pl | Słownik PWN `https://sjp.pwn.pl/` |
| pt / pt_BR | Priberam `https://dicionario.priberam.org/` |
| id | KBBI `https://kbbi.kemdikbud.go.id/` |
| ms | PRPM (DBP) `https://prpm.dbp.gov.my/` |
| fa | Vajehyab `https://www.vajehyab.com/` |
| he | Academy of the Hebrew Language `https://hebrew-academy.org.il/` |
| ko | 표준국어대사전 `https://stdict.korean.go.kr/` |
| zh_Hant | 教育部重編國語辭典 `https://dict.revised.moe.edu.tw/` |
| ja / zh | CLDR plus in-app consistency; treat grammar claims as `style` unless a source is found |

**Chunk anything large — one agent per 50 entries.** `review-manifest.json` gives each language a `chunks` count; honour it. A reviewer handed 300 entries and asked "flag what's wrong" degrades badly: it reads the head of the diff carefully and skims the tail, and the whole point of the pass is the one bad string among the 299 fine ones. Give each agent a slice and a line range, and tell it the slice is a slice. A 300-entry `zh` polish pass is 7 reviewers, not one.

Mass-rewrite passes deserve extra suspicion, not less. When a language shows hundreds of changed (not added) entries it is usually a human style sweep — spacing, punctuation, terminology — and the risk is not that the sweep is bad but that one entry quietly acquired a *new claim* while everything around it was cosmetic. Prompt the reviewer to hunt for meaning drift specifically, and to ignore the cosmetic churn it is swimming in.

Language-specific gotchas worth encoding (extend over time):
- **Russian / Ukrainian** — naive `{{count}} step(s)` patterns; missing ё; Russianisms in Ukrainian.
- **Chinese (zh)** — missing measure word `个` after `{{count}}`; 远端 vs 远程 consistency.
- **Chinese (zh_Hant)** — simplified chars leaking in (e.g. 设 vs 設); 語音 vs 聲音 distinction.
- **Korean** — register mix (합쇼체 vs 해요체); particle errors; brand names.
- **Indonesian** — title-case headers; "Mengunduh" vs "Mendownload"; reduplicated plurals.
- **Hebrew** — RTL ok; verbatim brand names; imperative form for buttons.
