import re
import unicodedata

# Known delimiter tag names that must never survive inside untrusted text, however they're obfuscated
# (case, internal whitespace/separators, nesting, repetition). <retrieved_background> is included here
# too: a candidate must never be able to make their own text look like a retrieved-evidence block, not
# just the candidate_*/system/instructions tags. Matched *after* Unicode normalization (see _normalize).
_TAGS = re.compile(
    r"</?\s*(candidate[\s_-]*[a-z][a-z\s_-]*|system|instructions?|retrieved[\s_-]*background)\s*>",
    re.IGNORECASE,
)

# A small set of Unicode "angle bracket" look-alikes a candidate could type to build a tag-like string
# that would survive a naive ASCII-only check. NFKC normalization (applied first in _normalize) already
# folds fullwidth/halfwidth variants such as U+FF1C/FF1E to plain ASCII < / >; these additional code
# points are not NFKC-equivalent to < / > so they need an explicit mapping.
_BRACKET_LOOKALIKES = {
    "‹": "<", "›": ">",  # ‹ ›  single angle quotation marks
    "〈": "<", "〉": ">",  # 〈 〉 CJK angle brackets
    "《": "<", "》": ">",  # 《 》 CJK double angle brackets
    "〈": "<", "〉": ">",  # 〈 〉 deprecated angle bracket block
    "﹤": "<", "﹥": ">",  # ﹤ ﹥ small variant forms
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(_BRACKET_LOOKALIKES.get(ch, ch) for ch in text)


def sanitize_user_text(text: str, limit: int = 4000) -> str:
    """Candidate (or retrieved-corpus) text is DATA, never a delimiter. Normalizes Unicode bracket
    look-alikes, strips anything that could imitate one of our named delimiter tags -- including
    <retrieved_background>, not just <candidate_*>/<system>/<instructions> -- and then escapes any '<'
    or '>' still remaining. That final escaping pass is the real guarantee: it means no tag of ANY name,
    known or not, nested or repeated, can survive this function, regardless of how the first pass is
    evaded. The tag-name pass only exists to keep the common, known attempts readable as
    "[tag removed]" instead of a wall of &lt;/&gt;."""
    text = _normalize((text or "").strip())
    text = _TAGS.sub("[tag removed]", text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    return text[:limit]
