"""Basic content moderation — a keyword/pattern pre-filter that runs before
any AI provider call (and its cost) is made.

This is deliberately NOT a machine-learning classifier and will not catch
everything a determined user can phrase around. Patterns are narrow on
purpose: each one covers a category with essentially zero legitimate
ebook use case (CSAM, step-by-step weapon/explosive instructions), so a
false positive should be rare. It exists to block the obvious, unambiguous
cases at zero cost, before the pipeline even starts — provider-side safety
filtering (each LLM's own refusal behavior) remains the primary defense
for anything subtler than this.
"""
import re

_BLOCKED_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bchild\s*(sexual|porn(ography)?|abuse material)\b",
        r"\bhow\s+to\s+(build|make|synthesi[sz]e|construct)\s+an?\s*"
        r"(bomb|explosive|chemical\s+weapon|biological\s+weapon|nerve\s+agent|pipe\s*bomb)\b",
        r"\bstep[- ]by[- ]step\s+(instructions?|guide)\s+(for|to|on)\s+"
        r"(making|building|creating)\s+an?\s*(bomb|explosive)\b",
    ]
]

REJECTION_MESSAGE = (
    "This request appears to involve content this platform does not "
    "generate (e.g. child sexual abuse material, or instructions for "
    "weapons/explosives). If this is a false positive, rephrase and try again."
)


def check_content(text: str) -> str | None:
    """Return REJECTION_MESSAGE if text trips a blocked pattern, else None.
    Checks only the first 5000 chars — a fast pre-filter, not a full scan."""
    if not text:
        return None
    sample = text[:5000]
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(sample):
            return REJECTION_MESSAGE
    return None
