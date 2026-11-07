import random

import pytest

from app.models.question import Question
from app.rag import KeywordRetriever, RetrievalQuery, get_retriever, select_questions
from app.rag.retriever import tokenize


@pytest.fixture()
def retriever(full_db_session):
    with full_db_session() as db:
        yield KeywordRetriever(db)


def ids(result):
    return [sq.question.source_id for sq in result.items]


# ---- filtering ----------------------------------------------------------------------------------
def test_no_filters_returns_everything_unscored(retriever):
    r = retriever.search(RetrievalQuery(limit=None))
    assert r.total == 112 and len(r.items) == 112
    assert all(sq.score is None for sq in r.items)


def test_subject_filter(retriever):
    r = retriever.search(RetrievalQuery(subject="English", limit=None))
    assert r.total == 16 and {sq.question.subject for sq in r.items} == {"English"}


def test_unknown_subject_returns_nothing(retriever):
    assert retriever.search(RetrievalQuery(subject="Astrology")).total == 0


def test_difficulty_filter(retriever):
    r = retriever.search(RetrievalQuery(difficulty="hard", limit=None))
    assert r.total > 0 and {sq.question.difficulty for sq in r.items} == {"hard"}


def test_topic_filter_is_case_insensitive(retriever):
    a = retriever.search(RetrievalQuery(topic="Constitutional Amendments", limit=None))
    b = retriever.search(RetrievalQuery(topic="  constitutional AMENDMENTS ", limit=None))
    assert a.total == b.total >= 2
    assert {sq.question.topic for sq in a.items} == {"Constitutional Amendments"}


def test_tag_filter(retriever):
    r = retriever.search(RetrievalQuery(tag="Kashmir", limit=None))
    assert set(ids(r)) >= {"pa-015", "ir-016"}
    assert all("kashmir" in sq.question.tags for sq in r.items)


def test_combined_filters(retriever):
    r = retriever.search(RetrievalQuery(subject="Governance and Constitutional Studies", difficulty="easy", limit=None))
    assert r.total == 5
    assert {sq.question.subject for sq in r.items} == {"Governance and Constitutional Studies"}
    assert {sq.question.difficulty for sq in r.items} == {"easy"}


def test_exclude_ids(retriever):
    everything = retriever.search(RetrievalQuery(subject="English", limit=None))
    skip = frozenset(sq.question.id for sq in everything.items[:5])
    r = retriever.search(RetrievalQuery(subject="English", exclude_ids=skip, limit=None))
    assert r.total == 11 and not ({sq.question.id for sq in r.items} & skip)


# ---- keyword search & relevance -----------------------------------------------------------------
@pytest.mark.parametrize(
    "query,expected_top",
    [
        ("Objectives Resolution", "pa-002"),
        ("doctrine of necessity", "pa-010"),
        ("riba interest banking", "is-007"),
        ("Paris Agreement climate justice", "ca-013"),
        ("security dilemma", "ir-010"),
        ("Article 140A local government", "gc-003"),
        ("simile metaphor", "en-001"),
        ("Cabinet Mission 1946", "pa-008"),
        ("Indus", "gk-001"),
        ("circular debt power sector", "ca-009"),
        ("Council of Common Interests", "gc-012"),
        ("Farewell Sermon", "is-008"),
    ],
)
def test_search_relevance_top_hit(retriever, query, expected_top):
    r = retriever.search(RetrievalQuery(text=query, limit=5))
    assert ids(r)[0] == expected_top, ids(r)


def test_scores_are_positive_and_sorted_descending(retriever):
    r = retriever.search(RetrievalQuery(text="constitution amendment federal", limit=None))
    scores = [sq.score for sq in r.items]
    assert r.total > 3 and all(s > 0 for s in scores) and scores == sorted(scores, reverse=True)


def test_search_matches_only_relevant_questions(retriever):
    r = retriever.search(RetrievalQuery(text="zzzznomatch"))
    assert r.total == 0 and r.items == []


def test_search_is_case_insensitive_and_stopword_tolerant(retriever):
    a = ids(retriever.search(RetrievalQuery(text="what is the Security Council", limit=3)))
    b = ids(retriever.search(RetrievalQuery(text="SECURITY COUNCIL", limit=3)))
    assert a[0] == b[0] == "ir-001"


def test_plurals_and_prefixes_match(retriever):
    singular = ids(retriever.search(RetrievalQuery(text="treaty", limit=None)))
    plural = ids(retriever.search(RetrievalQuery(text="treaties", limit=None)))
    assert singular and singular == plural  # stemming makes them equivalent
    assert retriever.search(RetrievalQuery(text="constitu", limit=None)).total > 0  # prefix (>=4 chars)


def test_search_combined_with_filters(retriever):
    r = retriever.search(RetrievalQuery(text="water", subject="General Knowledge", limit=None))
    assert r.total >= 1 and {sq.question.subject for sq in r.items} == {"General Knowledge"}
    assert ids(r)[0] == "gk-003"


def test_blank_search_text_behaves_like_no_search(retriever):
    r = retriever.search(RetrievalQuery(text="   ", subject="English", limit=None))
    assert r.total == 16 and all(sq.score is None for sq in r.items)


def test_query_of_only_stopwords_matches_nothing(retriever):
    assert retriever.search(RetrievalQuery(text="what is the of")).total == 0


# ---- pagination ---------------------------------------------------------------------------------
def test_pagination_pages_are_disjoint_and_cover_all(retriever):
    pages = [retriever.search(RetrievalQuery(subject="Islamic Studies", limit=5, offset=o)) for o in (0, 5, 10, 15)]
    assert all(p.total == 16 for p in pages)
    assert [len(p.items) for p in pages] == [5, 5, 5, 1]
    seen = [i for p in pages for i in ids(p)]
    assert len(seen) == len(set(seen)) == 16


def test_pagination_with_search_keeps_ranking_order(retriever):
    full = ids(retriever.search(RetrievalQuery(text="constitution", limit=None)))
    p1 = ids(retriever.search(RetrievalQuery(text="constitution", limit=4, offset=0)))
    p2 = ids(retriever.search(RetrievalQuery(text="constitution", limit=4, offset=4)))
    assert p1 + p2 == full[:8]


def test_offset_past_the_end_is_empty_but_reports_total(retriever):
    r = retriever.search(RetrievalQuery(subject="English", limit=10, offset=100))
    assert r.items == [] and r.total == 16


# ---- backend factory ----------------------------------------------------------------------------
def test_factory_returns_keyword_retriever(full_db_session):
    with full_db_session() as db:
        assert isinstance(get_retriever(db), KeywordRetriever)


def test_factory_rejects_unknown_backend(full_db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "retrieval_backend", "vector")
    with full_db_session() as db, pytest.raises(ValueError, match="Unknown retrieval backend"):
        get_retriever(db)


def test_tokenize_basics():
    assert tokenize("The Treaties of Pakistan's provinces") == ["treaty", "pakistan", "province"]
    assert tokenize("the constitution") == ["constitution"]
    assert tokenize("class classes") == ["class", "class"]


# ---- interview selection ------------------------------------------------------------------------
@pytest.fixture()
def english_pool(full_db_session):
    with full_db_session() as db:
        yield list(db.query(Question).filter_by(subject="English").order_by(Question.id))


def test_select_returns_distinct_questions(english_pool):
    chosen = select_questions(english_pool, 8, rng=random.Random(1))
    assert len({q.id for q in chosen}) == 8


def test_select_dedupes_duplicate_candidates(english_pool):
    chosen = select_questions(english_pool + english_pool, 16, rng=random.Random(1))
    assert len({q.id for q in chosen}) == 16


def test_select_raises_when_pool_too_small(english_pool):
    with pytest.raises(ValueError):
        select_questions(english_pool[:3], 4)


def test_select_prefers_unseen_questions(english_pool):
    seen = [q.id for q in english_pool[:10]]
    chosen = select_questions(english_pool, 6, recently_seen_ids=seen, rng=random.Random(2))
    assert not ({q.id for q in chosen} & set(seen))


def test_select_falls_back_to_least_recently_seen(english_pool):
    seen_most_recent_first = [q.id for q in english_pool]  # everything has been seen
    chosen = select_questions(english_pool, 3, recently_seen_ids=seen_most_recent_first)
    expected = set(seen_most_recent_first[-3:])  # seen longest ago = end of the list
    assert {q.id for q in chosen} == expected


def test_select_uses_all_unseen_first_then_stale(english_pool):
    seen = [q.id for q in english_pool[:14]]  # only 2 unseen remain
    unseen = {q.id for q in english_pool[14:]}
    chosen = select_questions(english_pool, 4, recently_seen_ids=seen, rng=random.Random(3))
    assert unseen <= {q.id for q in chosen}


def test_select_spreads_over_topics(english_pool):
    assert len({q.topic for q in english_pool}) >= 5
    chosen = select_questions(english_pool, 5, rng=random.Random(4))
    assert len({q.topic for q in chosen}) == 5


def test_mixed_difficulty_covers_levels_and_ramps_up(english_pool):
    chosen = select_questions(english_pool, 6, mixed_difficulty=True, rng=random.Random(5))
    rank = {"easy": 0, "medium": 1, "hard": 2}
    levels = [rank[q.difficulty] for q in chosen]
    assert set(levels) == {0, 1, 2}
    assert levels == sorted(levels)


def test_select_is_deterministic_for_a_seed(english_pool):
    a = [q.id for q in select_questions(english_pool, 5, rng=random.Random(42))]
    b = [q.id for q in select_questions(english_pool, 5, rng=random.Random(42))]
    assert a == b
