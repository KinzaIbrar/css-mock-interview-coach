# CSS knowledge base builder (Colab)

**Terminology:** "CSS" in this folder and notebook always means the **Central Superior Services
Examination** conducted by Pakistan's Federal Public Service Commission (FPSC) — never Cascading Style
Sheets. See `CLAUDE.md` at the repo root for the main project this supports.

Standalone data-prep notebook, kept deliberately separate from the app's backend/frontend. It runs
entirely on Google Colab's cloud compute and Google Drive storage, not on your laptop, and is
independent of this repo's hardware rules (no local models / no large embedding models / no GPU on the
dev machine) because none of its heavy dependencies (`faiss-cpu`, `sentence-transformers`) ever touch
the backend.

## Implementation status (what's real vs. pending)

| Area | Status |
|---|---|
| Source discovery/verification (18 sources) | **Done, locally verified** -- real HTTP checks + extracted text samples |
| PDF/web/YouTube extraction + chunking | **Done, locally executed** -- 979 real chunks from a real run |
| SSL fix (`truststore`) | **Done, locally verified** -- 3 previously-failing downloads now succeed, verification stays on |
| Syllabus subject-heading detection (52/52) | **Done, locally verified** |
| Stable chunk IDs + dedup-on-load | **Done, locally verified** -- tested with a simulated double-run |
| Chunk quality / subject-distribution report | **Done, locally executed** -- see below for real numbers |
| Embedding generation (`all-MiniLM-L6-v2`) | **Not executed** -- code written and reviewed, requires Colab |
| FAISS index build + save | **Not executed** -- code written and reviewed, requires Colab |
| Index persistence (fresh-runtime reload) | **Not executed** -- requires Colab |
| Real retrieval evaluation (Precision@5 etc.) | **Not executed** -- code written, requires Colab; only a non-embedding keyword-overlap proxy has been run |

## What's in this folder

| File | Purpose |
|---|---|
| `css_knowledge_base_builder.ipynb` | The Colab notebook itself. |
| `sources.json` | Catalog of every source the notebook uses, plus how each one was actually verified (HTTP status + sampled extracted text), and a list of sources that were checked and rejected (dead links, scanned PDFs, JS-rendered pages). Read this before adding more sources. |

## Coverage

Section 7b adds a single official 158-page FPSC document covering the exam scheme/marks and a detailed
topic-by-topic syllabus for English Essay, English Precis & Composition, General Science & Ability,
Current Affairs, Pakistan Affairs, Islamic Studies, and all ~52 optional subjects (Political Science,
Public Administration, International Relations, International Law, Economics, Sociology, History,
Criminology, Psychology, Philosophy, and more) -- the per-page subject-heading detection now correctly
tags all 52 (an earlier version silently missed subjects whose heading contained "&" or a parenthetical
as its own word, e.g. "GENERAL SCIENCE & ABILITY"; fixed and re-verified -- see `sources.json`'s first
`pdf_sources` entry). It's an Internet Archive snapshot of an official FPSC document, not a
currently-live fpsc.gov.pk URL -- read that entry's `reliability` note before treating any specific
topic as still current for CE-2027.

Also added: the official CSS CE Rules 2019 (viva voce/psychological-assessment rules), FPSC's CE-2025
viva voce instructions letter, the UN Charter's full text plus the UN's own "principal organs" page, a
MOFA press release on Pakistan-UN peacekeeping, and the Constitution (18th Amendment) Act 2010 compiled
with devolution commentary (PIPS, Parliament of Pakistan's own research body) -- added specifically
because a keyword-overlap coverage check flagged "role of the UN", "18th Amendment", and "CSS viva voce
qualities" as weak/missing. Re-running that check afterwards showed real, direct hits for all three (see
the retrieval-evaluation section of the implementation report for exact matched text) -- though that
check is a keyword proxy only; the real measure is the embedding-based retrieval in section 12, run once
you execute this in actual Colab.

**SSL note:** `fpsc.gov.pk` and `na.gov.pk` downloads used to fail under plain `requests` with a
certificate-chain error (those servers omit their intermediate cert). Fixed with
`truststore.inject_into_ssl()` in section 4 -- confirmed working locally, with certificate verification
**fully enabled** throughout; `verify=False` was never used.

**Stable chunk IDs:** `chunk_id`/`document_id` are now a deterministic hash of (source, page, position)
instead of a random UUID, so re-running a section doesn't silently create a second, differently-ID'd
copy of the same content. Section 10 deduplicates by `chunk_id` before anything gets embedded. Verified
locally by simulating a double run (re-running sections 7-9 appends to the shared jsonl files): 979
chunks appended twice -> 1,958 raw rows -> section 10's dedup correctly collapses back to 979.

## Chunk quality & subject distribution (real numbers, locally tested -- see "Implementation status" below)

From the 979-chunk local run (18/18 sources, 0 failures):

- **Duplicates:** 13 exact-duplicate pairs, all from the 226-page PIPS 18th Amendment document --
  repeated title-page/section-divider boilerplate ("PAKISTAN INSTITUTE FOR PARLIAMENTARY SERVICES...",
  a repeated short section-divider line), not corrupted or misattributed content. None removed from the
  source jsonl; section 10's chunk_id-based dedup is the only thing that would collapse them, and it
  only acts on byte-identical content.
- **Short chunks (<20 words):** 86 total -- 76 from the same PIPS document (near-blank divider pages),
  9 from the syllabus document (legitimately one-page subjects like Philosophy/Law), 1 from the
  Constitution. Flagged for review, never auto-removed, per the "don't delete legitimately short content"
  rule -- a one-page subject syllabus is short because the real subject is short, not because extraction
  broke.
- **Missing metadata:** 0 chunks missing `subject`/`topic`/`source_title`/`source_type`/`source_url`.
- **Subject-label sanity (syllabus document only):** checked whether each chunk's own in-text
  `PAPER: <NAME>` heading matches its assigned `subject` metadata -- 0 mismatches out of 161 syllabus
  chunks.
- **Subject distribution and concentration risk:** "Governance and Constitutional Studies" is 559/979
  chunks (57.1%), from only 2 source documents (the 225-page Constitution PDF and the 226-page PIPS
  18th-Amendment compilation) -- both long, dense legal texts chunked at a fixed 350-word size, versus
  every syllabus subject deriving from just 1-7 pages of one shared document. **This is a real retrieval-
  bias risk worth watching in Colab's actual results**, not a bug to silently fix by force-balancing
  subject counts (which the task explicitly said not to do): a FAISS top-k search over this index is
  more likely to surface a constitutional-law chunk purely because there's more of that mass in the
  index, even for a query that's only tangentially constitutional. If Colab's real retrieval results
  show this skew distorting unrelated questions, consider re-chunking those two documents at a larger
  chunk size (fewer, denser chunks) or splitting "Governance and Constitutional Studies" into a more
  granular per-article subject label, rather than discarding real constitutional content.
- International Relations is the next-largest at 101 chunks (10.3%) across 7 source documents -- healthy
  diversity, not single-document concentration.
- 19 subjects have 2 or fewer chunks (every optional subject that gets only 1-2 syllabus pages) --
  expected given the source, not a defect, but worth knowing before judging why a niche-subject query
  retrieves thin evidence.

## What this does and does not produce

- **Produces:** a general CSS/Pakistan *knowledge base* (chunked text + a FAISS vector index) that an
  interviewer/RAG agent could search for subject background.
- **Does not produce** the app's actual interview *question bank* (`data/questions/*.json`, the schema
  `backend/app/rag/dataset.py` validates). For that, use `backend/scripts/generate_questions.py` in the
  main repo — see below.
- **Does not get wired into the backend.** The running app's RAG retrieval is keyword-based by design
  (`backend/app/rag/retriever.py`). Adding FAISS + embeddings to the backend itself would be a real
  architecture change needing explicit sign-off; this notebook only prepares data and doesn't make that
  call for you.

## Execution checklist (Colab -- this has NOT been run there yet)

Everything above has been validated locally in a sandboxed Python environment (real downloads, real
PyMuPDF/trafilatura/youtube-transcript-api extraction, real chunking, real quality validation -- see the
implementation report for exact counts). **It has not been run inside actual Google Colab**, and the
embedding/FAISS steps specifically cannot be validated outside Colab, because `faiss-cpu` and
`sentence-transformers` are intentionally kept out of this local environment (and out of the backend) by
project policy. This checklist is what running it for real looks like -- tick these off yourself:

1. [ ] **Mount Google Drive** -- run section 2; authorize when prompted; confirm `InterviewIQ_Dataset/`
   with its 10 subfolders appears in My Drive.
2. [ ] **Install dependencies** -- run section 1 (`pymupdf`, `trafilatura`, `youtube-transcript-api`,
   `sentence-transformers`, `faiss-cpu`, `requests`, `truststore`). Confirm no install errors.
3. [ ] **Configure API keys** -- none needed for this notebook (confirm you did NOT put `GEMINI_API_KEY`
   or any secret into a notebook cell; that key belongs only in `backend/.env`, never here).
4. [ ] **Extract all available documents** -- run sections 7, 7b, 8, 9 in order; check section 9b's
   summary shows 0 (or an explained, non-zero) failed count. Expect 18 sources, ~979 chunks if nothing
   upstream changed since this session (see the quality report above for the exact breakdown).
5. [ ] **Generate chunks and metadata, and load/deduplicate them** -- section 10 reads every
   `07_Processed_Chunks/*.jsonl`, dedupes by `chunk_id`, and flags (not removes) short chunks. Confirm
   the printed "kept N distinct chunk(s)" count matches step 4's expectation.
6. [ ] **Generate `all-MiniLM-L6-v2` embeddings in batches** -- section 11; confirm it reports a batch
   size, an embedding dimension, and no encoding errors.
7. [ ] **Build the FAISS cosine-similarity index** -- still section 11; confirm `index.ntotal` matches
   the chunk count (the cell asserts this itself).
8. [ ] **Save the index, metadata, and index/model configuration** -- still section 11; confirm
   `css_knowledge_base.faiss`, `css_knowledge_base_metadata.jsonl`, AND `index_config.json` (model name,
   dimension, index type, chunk count, a content fingerprint, build timestamp) are written to
   `08_Embeddings/`.
9. [ ] **Reload the saved index to verify persistence** -- section 11b does an immediate same-session
   check (cheap, not sufficient alone). For the real test: in a *fresh* runtime (Runtime -> Disconnect
   and delete runtime, then reconnect), re-mount Drive, re-run section 11b's reload logic against the
   files already on Drive, and confirm `index.ntotal`/`index.d` still match the saved `index_config.json`
   -- this is what proves what got saved is actually what gets searched, not just what was still in
   memory from the session that built it.
10. [ ] **Run the real retrieval evaluation** -- section 13, only after step 9 passes in a fresh
    runtime. Confirm it writes `09_Evaluation_Dataset/retrieval_evaluation_report.json` with real
    similarity scores (not the keyword-overlap numbers quoted in this README, which are a different,
    weaker proxy from local testing).

Only after step 9 passes in a genuinely fresh runtime does section 13's output count as the real,
executed retrieval evaluation this task set out to produce.

## 1. Google Colab setup

1. Go to [colab.research.google.com](https://colab.research.google.com/).
2. File -> Upload notebook -> select `css_knowledge_base_builder.ipynb` from this folder (or upload it
   to Google Drive first and open it from there).
3. Runtime -> Change runtime type -> CPU is enough; no GPU/TPU needed for `all-MiniLM-L6-v2` + FAISS at
   this scale.

## 2. Google Drive setup

Section 2 of the notebook (`drive.mount('/content/drive')`) will prompt you to authorize Colab to access
your Google Drive the first time you run it. It then creates `InterviewIQ_Dataset/` with ten subfolders
(`01_Raw_Data` through `10_Final_Export`) under "My Drive" — safe to re-run, it won't overwrite existing
files.

## 3. API key configuration

This notebook needs **no API keys** — `all-MiniLM-L6-v2` runs locally inside the Colab runtime, and the
starter sources are all public URLs / public YouTube captions. (The backend's `GEMINI_API_KEY`, used by
`generate_questions.py` below, is unrelated to this notebook and lives only in `backend/.env`.)

## 4. How to add more CSS examination sources

1. Check `sources.json` first — don't re-add something already listed in `excluded_or_failed` without a
   new reason, and check `portal_references_not_auto_scraped` before trying to scrape a portal homepage.
2. Verify a candidate URL yourself before adding it to `PDF_JOBS` / `WEB_JOBS` / `YOUTUBE_JOBS` (section
   7, 8 or 9): confirm it returns HTTP 200 and that extraction actually produces real text, not just that
   a search engine mentioned it. FPSC's own site (`fpsc.gov.pk`) is a client-rendered app whose document
   paths change every exam cycle — a URL that worked last month may 404 today.
3. Add the entry with accurate `subject` / `topic` metadata, re-run sections 7-9, then re-run 10-14.
4. Append the same source to `sources.json` (with how you verified it) so the catalog stays accurate for
   the next person.

## 5. How to run the notebook end to end

Run the cells in order, top to bottom:

1. **Section 1** installs dependencies (Colab only).
2. **Section 2** mounts Drive and creates folders.
3. **Section 3** sets chunking/embedding config.
4. **Sections 4-6** define the extraction, cleaning, chunking and metadata functions used by everything
   after them (includes the `truststore` SSL fix and the stable-ID chunk/document hashing).
5. **Sections 7, 7b, 8, 9** download/scrape/transcribe the configured sources into
   `07_Processed_Chunks/*.jsonl`, with retries and a success/failure log (section 9b).
6. **Section 10** loads all chunks and deduplicates by `chunk_id` (safe even if a section above was
   re-run and appended twice).
7. **Section 11** builds the embeddings and FAISS index, and saves `index_config.json` alongside it.
8. **Section 11b** does an immediate same-session reload sanity check (not the real persistence test --
   see the execution checklist's step 9 for that).
9. **Section 12** runs dataset-quality validation and the subject-distribution report.
10. **Section 13** runs the real retrieval evaluation (20 questions, Precision@5 subject-match proxy).
11. **Section 14** exports the final JSONL/CSV.

## 6. How to generate embeddings

Section 11 embeds each distinct chunk's `content` with `sentence-transformers/all-MiniLM-L6-v2`
(small, CPU-friendly, ~80MB) in batches of 32, with `normalize_embeddings=True` so inner product equals
cosine similarity, into a `faiss.IndexFlatIP`. It asserts the embedding count matches the chunk count
and that `index.ntotal` matches too, then saves the index, its metadata, and `index_config.json` (model
name, dimension, index type, chunk count, a content fingerprint, build timestamp) to `08_Embeddings/`.
Re-run sections 10-11 whenever you add new sources in sections 7-9.

## 7. How to test retrieval

Section 13 runs 20 CSS exam/interview questions -- covering every compulsory subject plus the Task-6
optional-subject list (Pakistan Affairs, Current Affairs, Islamic Studies, English Essay, English
Precis, General Science & Ability, International Relations, International Law, Political Science,
Public Administration, Economics, the Constitution, the 18th Amendment, the UN, and CSS viva voce) --
against the real FAISS index, reports the top-5 matches with similarity scores, and computes a
**Precision@5 subject-match proxy**: each question carries an `expected_subjects` list, and precision@5
= (top-5 chunks whose `subject` is in that list) / 5. **This measures topical alignment, not whether a
human would judge the retrieved text as actually answering the question** -- read the printed excerpts
yourself for that. It also reports source diversity per question and flags any question with zero
subject-matching evidence in its top-5 as a coverage gap. Results are saved to
`09_Evaluation_Dataset/retrieval_evaluation_report.json`.

**This has only ever been run as a cheap keyword-overlap proxy locally (no embeddings), never with the
real embedding-based FAISS retrieval** -- that only happens once you run this notebook in actual Colab
(see the execution checklist above). The proxy run did show that the sources added for
UN/18th-Amendment/viva-voce coverage contain directly relevant text for those questions (e.g. the
CSS CE Rules 2019's actual viva-voce clause: *"he shall be asked questions on matters of general
interest. The object of the interview is to assess his suitability..."* surfaced directly for the viva
voce question); whether the *real* embedding retrieval surfaces the same text, and with what similarity
score and Precision@5, is unverified until section 13 runs for real. Section 12's validation should also
show close to 0 issues before you trust any of it.

## 8. How to export the knowledge base

Section 14 copies the metadata into `10_Final_Export/` as both JSONL and CSV. Download that folder from
Drive, or point a later, explicitly-approved backend-integration effort at it.

## 9. How to generate CSS interview questions (the actual question bank)

This notebook is unrelated to this step — use `backend/scripts/generate_questions.py` in the main repo:

```
cd backend
.venv\Scripts\python -m scripts.generate_questions --subject "Current Affairs" --topic "Climate Policy" --count 5
```

Requires `GEMINI_API_KEY` in `backend/.env` (same key the running app uses). It drafts questions in the
exact schema `backend/app/rag/dataset.py` validates (`id`, `expected_answer`, `evaluation_criteria`,
`important_concepts`, `tags`, `explanation`, `is_sample: true`), checks them against the existing dataset
for duplicates/near-duplicates, and never writes into `data/questions/*.json` directly.

## 10. How to review and approve drafts

1. Run the command above; it writes to `data/questions/_drafts/<subject>_draft_<timestamp>.json` and
   prints any validation issues (duplicates, near-duplicates, schema problems) to the console.
2. `data/questions/_drafts/` is never read by the running app (`app.rag.dataset.read_raw_items` only
   globs `*.json` directly inside `data/questions/`), so nothing reaches production automatically.
3. A human reviews each drafted question for factual accuracy — the script labels everything
   `is_sample: true` and the file's `meta.status` as an unreviewed AI draft, but it cannot itself verify
   facts.
4. To publish a question, copy its object from the draft file into the right `data/questions/<subject>.json`
   file by hand, then re-run `cd backend; .venv\Scripts\python -m app.rag.validate` to confirm the whole
   dataset is still valid before committing.
