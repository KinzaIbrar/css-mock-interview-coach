"""Task 15 Phase 5: targeted re-check of exactly the 6 scenarios affected by the Task 14 re-scoping
(the 2 regressions + the 4 scenarios whose wins depended on the re-scoped sources), using the SAME
query text/model/metric as Task 12/14 -- not the full 32-scenario sweep, since the other 26 are
provably unaffected (nothing about their retrieval changed)."""

import json
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
DATASET = Path(__file__).parents[1] / "evaluation" / "task12" / "evaluation_dataset.jsonl"
TASK15_DIR = HERE / "output_task15_coverage" / "InterviewIQ_Dataset" / "08_Embeddings"
OUT = Path(__file__).parents[1] / "evaluation" / "task15" / "verification_raw.json"

TARGET_SCENARIOS = {
    "t12-pa-001",         # misleading Lahore Declaration match -- check unaffected (unchanged)
    "t12-pa-002",         # REGRESSION to fix
    "t12-ps-custom-001",  # REGRESSION to fix
    "t12-ps-custom-002",  # must preserve this win
    "t12-is-016",         # must preserve this win
    "t12-is-003",         # must preserve this win
}


def main():
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    index = faiss.read_index(str(TASK15_DIR / "css_knowledge_base.faiss"))
    records = [json.loads(l) for l in open(TASK15_DIR / "css_knowledge_base_metadata.jsonl", encoding="utf-8") if l.strip()]
    with open(TASK15_DIR / "index_config.json", encoding="utf-8") as f:
        config = json.load(f)
    assert index.ntotal == len(records) == config["chunk_count"]

    scenarios = [json.loads(l) for l in open(DATASET, encoding="utf-8") if l.strip() if json.loads(l)["scenario_id"] in TARGET_SCENARIOS]
    results = []
    for s in scenarios:
        vec = model.encode([s["question_text"]], normalize_embeddings=True).astype("float32")
        scores, idxs = index.search(vec, 5)
        hits = []
        for rank, (score, idx) in enumerate(zip(scores[0], idxs[0]), start=1):
            r = records[idx]
            hits.append({
                "rank": rank, "score": float(score), "chunk_id": r["chunk_id"],
                "source_title": r["source_title"], "page_number": r.get("page_number"),
                "content_excerpt": r["content"][:200],
            })
        results.append({"scenario_id": s["scenario_id"], "question_text": s["question_text"], "task15_top5": hits})
        print(f"\n=== {s['scenario_id']} | {s['question_text'][:80]} ===")
        for h in hits[:3]:
            print(f"  r{h['rank']} score={h['score']:.3f} [{h['source_title'][:45]}] {h['content_excerpt'][:100]!r}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nWrote", OUT)


if __name__ == "__main__":
    main()
