from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.config import settings
from app.models import TranscriptSegment


@dataclass(frozen=True)
class Suggestion:
    timestamp_ms: int
    reason: str
    question: str


class MomentSuggester(Protocol):
    def suggest(self, segments: Sequence[TranscriptSegment]) -> list[Suggestion]: ...


class PauseSuggester:
    """Flags long pauses between one speaker finishing and another starting.

    A pause before responding is a classic stimulated recall prompt: something
    made the person stop. This is a rule-based baseline. It needs no model, and
    it gives a model-based suggester something to be measured against.
    """

    def __init__(self, min_gap_ms: int = 1500) -> None:
        self.min_gap_ms = min_gap_ms

    def suggest(self, segments: Sequence[TranscriptSegment]) -> list[Suggestion]:
        suggestions = []
        for previous, current in zip(segments, segments[1:], strict=False):
            gap_ms = current.start_ms - previous.end_ms
            if previous.speaker == current.speaker or gap_ms < self.min_gap_ms:
                continue
            suggestions.append(
                Suggestion(
                    timestamp_ms=previous.end_ms,
                    reason=(
                        f"{current.speaker} waited {gap_ms / 1000:.1f} s before responding "
                        f"to {previous.speaker}."
                    ),
                    question="You paused here. What was going through your mind?",
                )
            )
        return suggestions


def get_suggester() -> MomentSuggester:
    if settings.suggester == "pause":
        return PauseSuggester()
    raise ValueError(f"Unknown suggester: {settings.suggester}")
