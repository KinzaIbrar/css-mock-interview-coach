"""Interviewer Agent (the panel's voice): greeting, the introduction prompt, question order and difficulty adaptation.

Wording of the greeting is fixed text (not generated, so never mislabelled as AI). Question *selection* uses the
Question agent; this agent only re-orders the questions that are still unasked, by rules, so the interview adapts
to how the candidate is doing without ever repeating or dropping a question.
"""

from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.question import Question
from app.schemas.interview import IntroductionPrompt

DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}
STRONG = 70.0  # last main answer at/above this -> prefer a harder next question
WEAK = 40.0  # last main answer below this -> prefer an easier next question


def introduction_prompt(subject: str) -> IntroductionPrompt:
    return IntroductionPrompt(
        greeting=(
            f"Assalam-o-Alaikum, and welcome to your CSS mock interview on {subject}. "
            "I am your interviewer for this session. Please take a moment to settle in."
        ),
        question="To begin, please tell me about yourself: your background, your studies and why you want to join the civil service.",
    )


def adapt_next(db: Session, interview: Interview, last_overall: float | None) -> bool:
    """Swap the best-matching unasked question into the next slot. Returns True if the order changed.

    Only applies to "mixed" interviews (a fixed-difficulty interview keeps its level) and only reorders questions
    that have not been asked yet, so nothing is repeated or lost."""
    if interview.difficulty != "mixed" or last_overall is None:
        return False
    nxt = interview.current_index + 1
    ids = list(interview.question_ids)
    if nxt >= len(ids) - 1:
        return False  # zero or one unasked question: nothing to choose between
    rest = {q.id: q for q in db.query(Question).filter(Question.id.in_(ids[nxt:])).all()}
    current = DIFFICULTY_RANK.get(rest[ids[nxt]].difficulty, 1)
    if last_overall >= STRONG:
        target = min(current + 1, 2) if current < 2 else 2
        want = max(DIFFICULTY_RANK.get(q.difficulty, 1) for q in rest.values())
        target = min(target, want)
    elif last_overall < WEAK:
        target = 0
        want = min(DIFFICULTY_RANK.get(q.difficulty, 1) for q in rest.values())
        target = max(target, want)
    else:
        return False
    for offset, qid in enumerate(ids[nxt:]):
        if DIFFICULTY_RANK.get(rest[qid].difficulty, 1) == target:
            if offset == 0:
                return False
            ids[nxt], ids[nxt + offset] = ids[nxt + offset], ids[nxt]
            interview.question_ids = ids
            return True
    return False
