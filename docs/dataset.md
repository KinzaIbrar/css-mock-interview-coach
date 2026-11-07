# Question Dataset & Retrieval

## Status: sample, unverified
`data/questions/` is a **curated starter set written as study aids**. It is **not** official CSS/FPSC material, has **not been independently verified**, and cites no official source. Every record has `"is_sample": true`, and the API repeats this in a `notice` field. Facts (dates, article numbers, figures) should be cross-checked against standard textbooks and primary documents before being relied on. Question topics in Current Affairs are deliberately durable; recent figures are avoided.

## Contents (112 questions)
Seven subjects x 16 questions, each with 5 easy, 6-7 medium and 4-5 hard questions:
Pakistan Affairs, Current Affairs, Islamic Studies, General Knowledge, English, International Relations, Governance and Constitutional Studies.
One JSON file per subject in `data/questions/`. Run `python -m app.rag.validate` for live counts.

> Scope note: the subjects are the CSS (Central Superior Services) exam subjects. Web-development CSS topics (Flexbox, Grid...) are **not** part of this dataset.

## Record format
```json
{
  "id": "pa-002",                       // lower-case prefix, hyphen, 3 digits; globally unique
  "question": "...",                    // >= 15 chars, unique and not a near-duplicate of another
  "subject": "Pakistan Affairs",        // one of the 7 subjects
  "topic": "Constitutional History",
  "difficulty": "medium",               // easy | medium | hard
  "expected_answer": "...",             // >= 40 chars, non-blank
  "important_concepts": ["...", "..."], // >= 3 unique entries (used for keyword search and the dev evaluator)
  "evaluation_criteria": ["...", "..."],// >= 2 unique entries (for the Phase 4 evaluation agent)
  "tags": ["constitution"],             // >= 1; stored lower-case
  "explanation": "...",                 // why the question is asked / how to answer it
  "is_sample": true
}
```
Each file is `{"meta": {...}, "questions": [ ... ]}`. Unknown fields are rejected (catches typos).

Mapping to the database (`questions` table): `id`->`source_id`, `question`->`text`, `expected_answer`->`reference_answer`, `important_concepts`->`keywords`, and `evaluation_criteria`, `tags`, `explanation`, `topic`, `subject`, `difficulty`, `is_sample` map to same-named columns.

## Validation (`app/rag/dataset.py`)
Checks, collecting **all** problems in one pass: required fields; field types and minimum lengths; id format and uniqueness; subject and difficulty values; non-empty expected answer; evaluation criteria present and unique; duplicate question text; near-duplicates (token Jaccard >= 0.85). Coverage gaps (a subject or level with < 2 questions) are reported as warnings. An invalid dataset **aborts startup seeding** so bad content never reaches the database.

```
cd backend
.venv\Scripts\python -m app.rag.validate            # whole data/questions directory
.venv\Scripts\python -m app.rag.validate file.json  # a single file
```

## Loading
At startup the app runs Alembic migrations, then `seed_questions()` upserts every record by `id`. It is idempotent; existing rows keep their primary key so past interviews stay valid. Records removed from the files are **not** deleted from the database (past interviews may reference them).

## Retrieval architecture (`backend/app/rag/`)
| Module | Role |
|---|---|
| `dataset.py` | Record model, validation, loading |
| `retriever.py` | `QuestionRetriever` protocol, `KeywordRetriever`, `get_retriever()` factory |
| `selection.py` | `select_questions()` - interview question choice |
| `validate.py` | CLI checker |

**KeywordRetriever**: structured filters (subject, topic, difficulty, tag, excluded ids) in SQL/Python, then optional relevance ranking. Text is tokenised (lower-case, stopwords removed, light plural stemming). Each query term scores `idf x log(1 + weighted term frequency)`, with field weights text 3, topic/tags/concepts 2, expected answer 1, explanation 0.5; prefix matches (>= 4 chars) count at 0.6 and an exact multi-word phrase gets a bonus. Only questions with a positive score are returned. Pagination applies after ranking and `total` is the pre-pagination count. With ~100 documents this runs in milliseconds, so no index is persisted.

**Interview selection**: distinct questions only; questions from the user's last 5 interviews are avoided (reused longest-ago-first only if the pool is too small); topics are spread by round-robin; `mixed` difficulty draws across easy/medium/hard and orders the interview easy -> hard. An optional `topic` restricts the interview to one topic.

**Adding vector search later**: implement a class with `search(RetrievalQuery) -> RetrievalResult`, return it from `get_retriever()` for `RETRIEVAL_BACKEND=vector`, and nothing else changes (routes, services and agents depend only on the protocol). No vector database or embedding model is installed now: at ~100 short documents keyword ranking already finds the right question first for the queries in `tests/test_retrieval.py`, so there is no demonstrated benefit yet. Revisit if the bank grows into the thousands or users search by paraphrase.

## Adding or editing questions
1. Edit/add records in the relevant `data/questions/*.json` file using the next free id.
2. `python -m app.rag.validate`
3. `python -m pytest` (dataset tests also assert minimum coverage per subject/level).
