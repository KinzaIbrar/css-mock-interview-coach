SUBJECTS = [
    "Pakistan Affairs",
    "Current Affairs",
    "Islamic Studies",
    "General Knowledge",
    "English",
    "International Relations",
    "Governance and Constitutional Studies",
]

QUESTION_DIFFICULTIES = ["easy", "medium", "hard"]
INTERVIEW_DIFFICULTIES = QUESTION_DIFFICULTIES + ["mixed"]
INTERVIEW_MODES = ["mock", "practice"]

CRITERIA = ["relevance", "subject_knowledge", "accuracy", "reasoning", "structure", "clarity"]

DEV_EVAL_NOTICE = (
    "DEVELOPMENT MODE: this evaluation is produced by a simple keyword/length heuristic, "
    "NOT by an AI model. Scores are indicative only."
)
AI_EVAL_NOTICE = (
    "AI-generated evaluation by {model}. AI can make mistakes: scores are indicative, and the reference "
    "answers used for comparison are unverified study aids."
)
MIXED_EVAL_NOTICE = (
    "Mixed evaluation: some answers were evaluated by {model}; the others fell back to the development "
    "keyword heuristic (NOT AI) because Gemini was unavailable. See the per-question source."
)
SAMPLE_DATA_NOTICE = (
    "Sample question bank: questions and reference answers are unverified study aids, "
    "not official CSS material."
)
