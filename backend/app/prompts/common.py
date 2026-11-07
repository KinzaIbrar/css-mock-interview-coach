import re

_TAGS = re.compile(r"</?\s*(candidate_[a-z_]+|system|instructions?)\s*>", re.IGNORECASE)


def sanitize_user_text(text: str, limit: int = 4000) -> str:
    """Candidate text is DATA. Strip anything that could imitate our delimiter tags and cap the length."""
    return _TAGS.sub("[tag removed]", (text or "").strip())[:limit]
