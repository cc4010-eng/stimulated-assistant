"""Rules the interviewer must always follow, enforced in code.

The policy (later, a model) decides what would be worth asking. Nothing here
depends on its judgment: these checks run on whatever it proposes.
"""

import re

NEUTRAL_FOLLOWUP = "Can you say more about what you were thinking at that point?"

# Phrasings that suggest an answer to the participant. A leading question
# contaminates the data, so the engine refuses to ask one.
_LEADING_PATTERNS = [
    r"\bdon'?t you (think|feel|agree)\b",
    r"\bwouldn'?t you (say|agree)\b",
    r"\bisn'?t it (true|fair|the case)\b",
    r"\bwas(n'?t)? (it|that) because\b",
    r"\byou must have\b",
    r"\bsurely\b",
    r"\bobviously\b",
    r"\bright\?\s*$",
]
_LEADING = re.compile("|".join(_LEADING_PATTERNS), re.IGNORECASE)


def find_leading_phrase(question: str) -> str | None:
    match = _LEADING.search(question)
    return match.group(0) if match else None


def moment_allowance(remaining_seconds: float, moments_left: int) -> int:
    """Split the remaining time evenly over the moments still to cover."""
    if moments_left <= 0:
        return 0
    return int(remaining_seconds // moments_left)


def normalize(question: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", question.lower()).strip()
