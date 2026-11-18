"""Vector (semantic) retrieval of supplementary CSS-knowledge evidence, for grounding answer
evaluation -- a different responsibility from `app.rag.retriever.KeywordRetriever`, which picks
*interview questions* from the curated dataset. The two are never substituted for each other:
`KeywordRetriever`/`QuestionRetriever` are untouched by this module.

`QuestionRetriever`'s `search(RetrievalQuery) -> RetrievalResult` is shaped around `Question` ORM rows
(`ScoredQuestion.question: Question`), which doesn't fit free-text knowledge-base chunks -- reusing that
exact protocol here would force the wrong domain into it. This module follows the same *style*
(frozen dataclasses, a plain `search`-like entry point, cosine scores) without pretending the two are
interchangeable.

Plain FAISS cosine top-k only -- no hybrid keyword reranking, no additional ranking algorithm.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from app.rag.vector import embedder
from app.rag.vector.errors import RagError, RagRetrievalFailed
from app.rag.vector.loader import get_cached_bundle

logger = logging.getLogger("app.rag.vector")


@dataclass(frozen=True)
class EvidenceHit:
    chunk_id: str
    score: float
    subject: str
    topic: str
    source_type: str
    source_title: str
    source_url: str | None
    page_number: int | None
    content: str


def search(query_text: str, *, index_dir: Path, top_k: int) -> list[EvidenceHit]:
    """Returns up to `top_k` hits ranked by cosine similarity (highest first), or [] for a blank query.

    Raises a `RagError` subclass if the index/model cannot be used at all; callers (see `evidence.py`)
    are expected to catch that and fall back to "no evidence" -- this function never does that itself,
    so a caller that genuinely needs to distinguish "disabled/broken" from "no results" still can.
    """
    if not query_text or not query_text.strip():
        return []

    bundle = get_cached_bundle(index_dir)  # raises RagError subclasses; not caught here
    query_vec = embedder.encode_query(query_text, model_name=bundle.model_name, expected_dim=bundle.embedding_dim)

    try:
        scores, indices = bundle.index.search(query_vec, min(top_k, bundle.chunk_count))
    except Exception as exc:  # noqa: BLE001 - faiss raises untyped errors
        raise RagRetrievalFailed(f"FAISS search failed: {exc}") from None

    hits: list[EvidenceHit] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        r = bundle.records[idx]
        hits.append(
            EvidenceHit(
                chunk_id=r["chunk_id"],
                score=float(score),
                subject=r["subject"],
                topic=r["topic"],
                source_type=r["source_type"],
                source_title=r["source_title"],
                source_url=r.get("source_url"),
                page_number=r.get("page_number"),
                content=r["content"],
            )
        )
    return hits
