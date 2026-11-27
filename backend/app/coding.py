import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.config import settings
from app.models import Code


@dataclass(frozen=True)
class CodeProposal:
    code_id: str
    confidence: float
    rationale: str


class Coder(Protocol):
    def code(self, answer: str, codebook: Sequence[Code]) -> list[CodeProposal]: ...


_STOPWORDS = frozenset(
    "about after again also because been before being between could does doing during each "
    "from have having into more most other over same should some such than that their them "
    "then there these they this those through under very what when where which while with "
    "would your teacher teachers student students".split()
)
_STEM = 5


def _stems(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {word[:_STEM] for word in words if len(word) > 3 and word not in _STOPWORDS}


class KeywordCoder:
    """Rule-based stand-in for the model that will apply the codebook.

    A code is proposed when words from its name or description appear in the
    answer. Confidence grows with the number of distinct matches. It cannot
    read meaning, so it misses paraphrases and is fooled by negation; it is
    here as a floor for a model-based coder to be compared against.
    """

    FULL_CONFIDENCE_HITS = 3

    def code(self, answer: str, codebook: Sequence[Code]) -> list[CodeProposal]:
        answer_stems = _stems(answer)
        proposals = []
        for code in codebook:
            hits = sorted(_stems(f"{code.name} {code.description}") & answer_stems)
            if not hits:
                continue
            proposals.append(
                CodeProposal(
                    code_id=code.id,
                    confidence=round(min(1.0, len(hits) / self.FULL_CONFIDENCE_HITS), 2),
                    rationale="Matched: " + ", ".join(hits),
                )
            )
        return proposals


def get_coder() -> Coder:
    if settings.coder == "keyword":
        return KeywordCoder()
    raise ValueError(f"Unknown coder: {settings.coder}")
