"""Task 14 experimental-corpus pipeline. Standalone script, NOT a modification of
`css_knowledge_base_builder.ipynb` -- the notebook itself is untouched, per this task's instruction to
explain before changing extraction/chunking code at all. Everything below is a line-for-line port of
the notebook's own section 4-6 and section 11 functions (clean_text, chunk_text, make_chunk_records,
extract_pdf_text, extract_web_article, the embedding/FAISS build), run locally in `.venv-rag` (which
already has faiss-cpu/sentence-transformers/pymupdf/trafilatura/truststore installed from earlier
sessions) against the SAME chunk size (350 words / 70 overlap), the SAME metadata schema
(document_id/subject/topic/source_type/source_title/source_url/page_number/language/content/chunk_id),
the SAME deterministic chunk-ID scheme, and the SAME embedding model/index type as the approved
baseline. Writes ONLY to `research/colab/output_task14_coverage/` -- never touches
`output_promoted_baseline/`.

Usage:
    cd research/colab
    ..\\..\\.venv-rag\\Scripts\\python task14_pipeline.py fetch      # downloads/extracts new sources only
    ..\\..\\.venv-rag\\Scripts\\python task14_pipeline.py build      # merges with baseline + builds the candidate index
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests
import truststore

truststore.inject_into_ssl()

HERE = Path(__file__).parent
BASELINE_META = HERE / "output_promoted_baseline" / "InterviewIQ_Dataset" / "08_Embeddings" / "css_knowledge_base_metadata.jsonl"
OUT_DIR = HERE / "output_task14_coverage" / "InterviewIQ_Dataset"
RAW_DIR = OUT_DIR / "01_Raw_Data"
CHUNKS_DIR = OUT_DIR / "07_Processed_Chunks"
EMBED_DIR = OUT_DIR / "08_Embeddings"
for d in (RAW_DIR, CHUNKS_DIR, EMBED_DIR):
    d.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE_WORDS = 350
CHUNK_OVERLAP_WORDS = 70
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_BATCH_SIZE = 32


# ------------------------------------------------------------------ ported from notebook section 5/6
def clean_text(text: str) -> str:
    text = text.replace("\r", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


def _stable_id(*parts, length: int = 12) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:length]


def make_chunk_records(text, *, subject, topic, source_type, source_title, source_url, page_number=None, language="English"):
    document_id = _stable_id(source_url or source_title)
    records = []
    for i, chunk in enumerate(chunk_text(clean_text(text)), start=1):
        records.append({
            "document_id": document_id,
            "subject": subject,
            "topic": topic,
            "source_type": source_type,
            "source_title": source_title,
            "source_url": source_url,
            "page_number": page_number,
            "language": language,
            "content": chunk,
            "chunk_id": _stable_id(source_url or source_title, page_number, i, length=16),
        })
    return records


def append_jsonl(records, out_path: Path) -> None:
    with open(out_path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ ported from notebook section 4
def download_file(url: str, dest_path: Path, user_agent: str = "Mozilla/5.0 (compatible; InterviewIQ-notebook)") -> None:
    last_exc = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=30)
            resp.raise_for_status()
            dest_path.write_bytes(resp.content)
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            print(f"    attempt {attempt}/3 failed: {exc}")
            if attempt < 3:
                time.sleep(3.0 * attempt)
    raise last_exc


def extract_pdf_text(pdf_path: Path) -> list[dict]:
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        if text.strip():
            pages.append({"page_number": i, "text": text})
    doc.close()
    return pages


def extract_web_article(url: str) -> dict | None:
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    if not text:
        return None
    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata and metadata.title else url
    return {"title": title, "text": text, "url": url}


# ------------------------------------------------------------------ job processing (mirrors section 7/8)
def process_pdf_job(job: dict, log: dict) -> None:
    local_path = RAW_DIR / job["filename"]
    print("Processing (PDF):", job["source_title"])
    try:
        if not local_path.exists():
            download_file(job["url"], local_path)
        pages = extract_pdf_text(local_path)
        if not pages:
            raise ValueError("no extractable text (likely a scanned/image PDF)")
        chunk_count = 0
        out_path = CHUNKS_DIR / "pdf_chunks.jsonl"
        for page in pages:
            records = make_chunk_records(
                page["text"], subject=job["subject"], topic=job["topic"], source_type=job.get("source_type", "official_document"),
                source_title=job["source_title"], source_url=job["url"], page_number=page["page_number"],
            )
            append_jsonl(records, out_path)
            chunk_count += len(records)
        log["success"].append({"source": job["source_title"], "url": job["url"], "pages": len(pages), "chunks": chunk_count})
        print("  OK:", len(pages), "page(s),", chunk_count, "chunk(s)")
    except Exception as exc:  # noqa: BLE001
        log["failed"].append({"source": job["source_title"], "url": job["url"], "error": str(exc)})
        print("  FAILED:", exc)


def process_web_job(job: dict, log: dict) -> None:
    print("Processing (web):", job["source_title"])
    try:
        article = extract_web_article(job["url"])
        if not article:
            raise ValueError("extraction returned no article text")
        records = make_chunk_records(
            article["text"], subject=job["subject"], topic=job["topic"], source_type=job.get("source_type", "official_document"),
            source_title=job["source_title"], source_url=job["url"],
        )
        out_path = CHUNKS_DIR / "web_chunks.jsonl"
        append_jsonl(records, out_path)
        log["success"].append({"source": job["source_title"], "url": job["url"], "chunks": len(records)})
        print("  OK:", len(records), "chunk(s)")
    except Exception as exc:  # noqa: BLE001
        log["failed"].append({"source": job["source_title"], "url": job["url"], "error": str(exc)})
        print("  FAILED:", exc)


# ------------------------------------------------------------------ build step (mirrors section 10 + 11)
def build_index():
    baseline_records = []
    with open(BASELINE_META, encoding="utf-8") as f:
        baseline_records = [json.loads(line) for line in f if line.strip()]
    print(f"Loaded {len(baseline_records)} baseline chunk(s) (read-only, from the approved baseline).")

    new_records_raw = []
    for path in sorted(CHUNKS_DIR.glob("*_chunks.jsonl")):
        with open(path, encoding="utf-8") as f:
            new_records_raw.extend(json.loads(line) for line in f if line.strip())
    print(f"Loaded {len(new_records_raw)} newly-processed chunk row(s) from {CHUNKS_DIR}.")

    seen_ids = {r["chunk_id"] for r in baseline_records}
    new_records = []
    dup_vs_baseline = 0
    dup_within_new = 0
    for r in new_records_raw:
        if r["chunk_id"] in seen_ids:
            if any(r["chunk_id"] == b["chunk_id"] for b in baseline_records):
                dup_vs_baseline += 1
            else:
                dup_within_new += 1
            continue
        seen_ids.add(r["chunk_id"])
        new_records.append(r)
    print(f"Kept {len(new_records)} distinct new chunk(s); "
          f"dropped {dup_vs_baseline} duplicate-of-baseline, {dup_within_new} duplicate-within-new.")

    all_records = baseline_records + new_records
    short_new = [r for r in new_records if len(r["content"].split()) < 20]
    print(f"FLAGGED (not removed): {len(short_new)} new chunk(s) under 20 words.")
    missing_meta = [r for r in new_records if not all(r.get(k) for k in ("subject", "topic", "source_title", "source_type"))]
    print(f"New chunks missing required metadata: {len(missing_meta)}")

    import numpy as np
    import faiss
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    texts = [r["content"] for r in all_records]
    print(f"Embedding {len(texts)} total chunk(s) (baseline + new)...")
    embeddings = model.encode(texts, batch_size=EMBED_BATCH_SIZE, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype="float32")
    embedding_dim = embeddings.shape[1]
    assert embeddings.shape[0] == len(all_records)

    index = faiss.IndexFlatIP(embedding_dim)
    index.add(embeddings)
    assert index.ntotal == len(all_records)

    faiss.write_index(index, str(EMBED_DIR / "css_knowledge_base.faiss"))
    with open(EMBED_DIR / "css_knowledge_base_metadata.jsonl", "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    content_fingerprint = hashlib.sha1("".join(sorted(seen_ids)).encode()).hexdigest()[:16]
    import datetime
    index_config = {
        "model_name": EMBEDDING_MODEL_NAME,
        "embedding_dim": embedding_dim,
        "index_type": "faiss.IndexFlatIP (cosine via normalized inner product)",
        "normalize_embeddings": True,
        "embed_batch_size": EMBED_BATCH_SIZE,
        "chunk_count": len(all_records),
        "baseline_chunk_count": len(baseline_records),
        "new_chunk_count": len(new_records),
        "chunk_id_set_fingerprint": content_fingerprint,
        "built_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(EMBED_DIR / "index_config.json", "w", encoding="utf-8") as f:
        json.dump(index_config, f, indent=2)
    print("Saved candidate index to", EMBED_DIR)
    print(json.dumps(index_config, indent=2))

    reloaded = faiss.read_index(str(EMBED_DIR / "css_knowledge_base.faiss"))
    assert reloaded.ntotal == len(all_records) and reloaded.d == embedding_dim
    print("Fresh-process reload check: OK (ntotal/dim match what was just saved).")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("fetch", "build"):
        print("usage: task14_pipeline.py [fetch|build]")
        sys.exit(1)
    if sys.argv[1] == "build":
        build_index()
