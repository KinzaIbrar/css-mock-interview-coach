"""Question retrieval.

`QuestionRetriever` is the seam for retrieval backends. The shipped `KeywordRetriever` does
structured filtering (subject / topic / difficulty / tag) plus weighted keyword relevance ranking.
A future `VectorRetriever` (embeddings) only has to implement the same `search()` and be returned by
`get_retriever()`; routes, services and agents depend on the protocol, not on this class.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.question import Question

STOPWORDS = frozenset(
    "a an and are as at be by for from how in is it its of on or that the this to was what when where which "
    "who why with explain discuss describe analyse analyze evaluate critically briefly role main".split()
)
FIELD_WEIGHTS = {"text": 3.0, "topic": 2.0, "tags": 2.0, "keywords": 2.0, "answer": 1.0, "explanation": 0.5}
PREFIX_MATCH_WEIGHT = 0.6
PHRASE_BONUS = 2.0


def tokenize(text: str) -> list[str]:
    """Lower-case alphanumeric tokens, stopwords removed, with a very light plural stemmer."""
    out = []
    for raw in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(raw) < 2 or raw in STOPWORDS:  # drops fragments such as the 's' of "Pakistan's"
            continue
        if len(raw) > 4 and raw.endswith("ies"):
            raw = raw[:-3] + "y"  # treaties -> treaty
        elif len(raw) > 4 and raw.endswith(("sses", "xes", "zes", "ches", "shes")):
            raw = raw[:-2]  # classes -> class
        elif len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss"):
            raw = raw[:-1]  # provinces -> province
        out.append(raw)
    return out


@dataclass(frozen=True)
class RetrievalQuery:
    text: str | None = None
    subject: str | None = None
    topic: str | None = None
    difficulty: str | None = None  # easy | medium | hard (None = any)
    tag: str | None = None
    exclude_ids: frozenset[int] = field(default_factory=frozenset)
    limit: int | None = 20  # None = no limit
    offset: int = 0


@dataclass
class ScoredQuestion:
    question: Question
    score: float | None  # None when no text query was given


@dataclass
class RetrievalResult:
    items: list[ScoredQuestion]
    total: int  # matches before pagination


class QuestionRetriever(Protocol):
    def search(self, query: RetrievalQuery) -> RetrievalResult: ...


class KeywordRetriever:
    def __init__(self, db: Session):
        self.db = db

    def _candidates(self, q: RetrievalQuery) -> list[Question]:
        stmt = select(Question)
        if q.subject:
            stmt = stmt.where(Question.subject == q.subject)
        if q.difficulty:
            stmt = stmt.where(Question.difficulty == q.difficulty)
        rows = list(self.db.scalars(stmt.order_by(Question.subject, Question.id)))
        if q.topic:
            rows = [r for r in rows if r.topic.lower() == q.topic.strip().lower()]
        if q.tag:
            tag = q.tag.strip().lower()
            rows = [r for r in rows if tag in [t.lower() for t in (r.tags or [])]]
        if q.exclude_ids:
            rows = [r for r in rows if r.id not in q.exclude_ids]
        return rows

    @staticmethod
    def _field_tokens(question: Question) -> dict[str, list[str]]:
        return {
            "text": tokenize(question.text),
            "topic": tokenize(question.topic),
            "tags": [t for tag in (question.tags or []) for t in tokenize(tag)],
            "keywords": [t for kw in (question.keywords or []) for t in tokenize(kw)],
            "answer": tokenize(question.reference_answer),
            "explanation": tokenize(question.explanation),
        }

    def _rank(self, rows: list[Question], text: str) -> list[ScoredQuestion]:
        query_tokens = list(dict.fromkeys(tokenize(text)))
        if not query_tokens:
            return []
        docs = [self._field_tokens(r) for r in rows]
        n = len(rows)
        phrase = " ".join(re.findall(r"[a-z0-9]+", text.lower()))

        def matches(q_tok: str, d_tok: str) -> float:
            if q_tok == d_tok:
                return 1.0
            if len(q_tok) >= 4 and d_tok.startswith(q_tok):
                return PREFIX_MATCH_WEIGHT
            return 0.0

        # document frequency per query token (any field)
        df = {
            qt: sum(1 for d in docs if any(matches(qt, dt) for toks in d.values() for dt in set(toks)))
            for qt in query_tokens
        }
        scored: list[ScoredQuestion] = []
        for row, doc in zip(rows, docs):
            score = 0.0
            for qt in query_tokens:
                if df[qt] == 0:
                    continue
                idf = math.log(1 + n / (1 + df[qt]))
                weighted_tf = sum(
                    FIELD_WEIGHTS[f] * sum(matches(qt, dt) for dt in toks) for f, toks in doc.items()
                )
                if weighted_tf:
                    score += idf * math.log(1 + weighted_tf)
            if len(query_tokens) > 1 and phrase:
                haystack = " ".join(
                    re.findall(r"[a-z0-9]+", f"{row.text} {row.topic} {' '.join(row.keywords or [])}".lower())
                )
                if phrase in haystack:
                    score += PHRASE_BONUS
            if score > 0:
                scored.append(ScoredQuestion(row, round(score, 4)))
        scored.sort(key=lambda s: (-s.score, s.question.id))
        return scored

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        rows = self._candidates(query)
        if query.text and query.text.strip():
            items = self._rank(rows, query.text)
        else:
            items = [ScoredQuestion(r, None) for r in rows]
        total = len(items)
        end = None if query.limit is None else query.offset + query.limit
        return RetrievalResult(items=items[query.offset:end], total=total)


def get_retriever(db: Session) -> QuestionRetriever:
    """Factory for the configured backend (`RETRIEVAL_BACKEND`). Add 'vector' here later."""
    backend = settings.retrieval_backend
    if backend == "keyword":
        return KeywordRetriever(db)
    raise ValueError(f"Unknown retrieval backend {backend!r}; supported: 'keyword'")
