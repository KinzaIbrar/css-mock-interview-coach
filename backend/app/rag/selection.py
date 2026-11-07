"""Choosing the questions for an interview from a candidate pool.

Goals: no repeats within an interview, avoid questions the user was asked recently, spread the
questions over different topics, and (for 'mixed' difficulty) cover easy/medium/hard and order the
interview from easier to harder. Pure functions so they are easy to test and reuse from an agent.
"""

import random
from collections import defaultdict
from collections.abc import Sequence

from app.models.question import Question

DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}


def _round_robin(groups: list[list[Question]]) -> list[Question]:
    out: list[Question] = []
    for i in range(max((len(g) for g in groups), default=0)):
        for g in groups:
            if i < len(g):
                out.append(g[i])
    return out


def _spread_by_topic(questions: Sequence[Question], rng: random.Random) -> list[Question]:
    by_topic: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        by_topic[q.topic].append(q)
    groups = list(by_topic.values())
    rng.shuffle(groups)
    for g in groups:
        rng.shuffle(g)
    return _round_robin(groups)


def _spread(questions: Sequence[Question], rng: random.Random, mixed: bool) -> list[Question]:
    if not mixed:
        return _spread_by_topic(questions, rng)
    buckets: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        buckets[q.difficulty].append(q)
    order = sorted(buckets, key=lambda d: DIFFICULTY_RANK.get(d, 9))
    return _round_robin([_spread_by_topic(buckets[d], rng) for d in order])


def select_questions(
    candidates: Sequence[Question],
    n: int,
    recently_seen_ids: Sequence[int] = (),
    mixed_difficulty: bool = False,
    rng: random.Random | None = None,
) -> list[Question]:
    """Pick `n` distinct questions from `candidates`.

    `recently_seen_ids` is ordered most-recent first. Unseen questions are always preferred; if there
    are not enough, the questions seen longest ago are used to fill the remainder.
    Raises ValueError if fewer than `n` candidates exist.
    """
    rng = rng or random.Random()
    unique = list({q.id: q for q in candidates}.values())
    if len(unique) < n:
        raise ValueError(f"only {len(unique)} candidate question(s) for {n} requested")

    seen_position = {qid: pos for pos, qid in reversed(list(enumerate(recently_seen_ids)))}  # most recent wins
    fresh = [q for q in unique if q.id not in seen_position]
    stale = [q for q in unique if q.id in seen_position]

    chosen = _spread(fresh, rng, mixed_difficulty)[:n]
    if len(chosen) < n:
        stale.sort(key=lambda q: -seen_position[q.id])  # seen longest ago first
        chosen += stale[: n - len(chosen)]

    if mixed_difficulty:
        chosen.sort(key=lambda q: DIFFICULTY_RANK.get(q.difficulty, 9))
    return chosen
