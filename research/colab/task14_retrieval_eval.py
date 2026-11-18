"""Task 14 Phase 5: baseline-vs-candidate retrieval comparison, using the EXACT same 32 scenarios,
query text (the question_text, matching production's rag_evidence.get_evidence(question.text)
convention), embedding model, similarity metric (cosine via normalized inner product) and top_k
settings for both conditions -- only the index differs. No keyword shortcuts, no hand-picked results,
no query rewriting. Writes raw top-5 hits for both conditions to retrieval_comparison_raw.json for
human-judgment review (automated similarity scores alone cannot establish relevance).
"""

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
DATASET = Path(__file__).parents[1] / "evaluation" / "task12" / "evaluation_dataset.jsonl"
BASELINE_DIR = HERE / "output_promoted_baseline" / "InterviewIQ_Dataset" / "08_Embeddings"
CANDIDATE_DIR = HERE / "output_task14_coverage" / "InterviewIQ_Dataset" / "08_Embeddings"
OUT = Path(__file__).parents[1] / "evaluation" / "task14" / "retrieval_comparison_raw.json"
TOP_K = 5


def load_condition(embed_dir: Path):
    index = faiss.read_index(str(embed_dir / "css_knowledge_base.faiss"))
    records = []
    with open(embed_dir / "css_knowledge_base_metadata.jsonl", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    with open(embed_dir / "index_config.json", encoding="utf-8") as f:
        config = json.load(f)
    assert index.ntotal == len(records) == config["chunk_count"], "index/metadata/config mismatch"
    return index, records, config


def search(model, index, records, query_text, top_k=TOP_K):
    vec = model.encode([query_text], normalize_embeddings=True).astype("float32")
    scores, idxs = index.search(vec, min(top_k, len(records)))
    hits = []
    for rank, (score, idx) in enumerate(zip(scores[0], idxs[0]), start=1):
        if idx == -1:
            continue
        r = records[idx]
        hits.append({
            "rank": rank, "score": float(score), "chunk_id": r["chunk_id"],
            "subject": r["subject"], "topic": r["topic"], "source_title": r["source_title"],
            "source_type": r["source_type"], "page_number": r.get("page_number"),
            "content_excerpt": r["content"][:300],
        })
    return hits


def main():
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    baseline_index, baseline_records, baseline_config = load_condition(BASELINE_DIR)
    candidate_index, candidate_records, candidate_config = load_condition(CANDIDATE_DIR)
    print(f"Baseline: {baseline_config['chunk_count']} chunks. Candidate: {candidate_config['chunk_count']} chunks "
          f"({candidate_config.get('new_chunk_count', '?')} new).")

    scenarios = [json.loads(l) for l in open(DATASET, encoding="utf-8") if l.strip()]
    results = []
    for s in scenarios:
        query = s["question_text"]
        baseline_hits = search(model, baseline_index, baseline_records, query)
        candidate_hits = search(model, candidate_index, candidate_records, query)
        results.append({
            "scenario_id": s["scenario_id"], "subject": s["subject"], "topic": s["topic"],
            "question_text": query, "baseline_top5": baseline_hits, "candidate_top5": candidate_hits,
        })
        print(f"{s['scenario_id']}: baseline top1 score={baseline_hits[0]['score']:.3f} "
              f"vs candidate top1 score={candidate_hits[0]['score']:.3f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Wrote", OUT, "|", len(results), "scenario(s)")


if __name__ == "__main__":
    main()
