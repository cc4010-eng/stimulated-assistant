from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import settings


@dataclass(frozen=True)
class Segment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


class Transcriber(Protocol):
    def transcribe(self, audio: Path) -> list[Segment]: ...


class StubTranscriber:
    """Returns the same short classroom exchange for any file.

    It lets the upload-to-transcript path run in tests and local development
    without a speech API key. It does not listen to the audio.
    """

    def transcribe(self, audio: Path) -> list[Segment]:
        return [
            Segment("Teacher", 0, 4200, "Who can tell me which is bigger, one third or one fifth?"),
            Segment(
                "Student",
                4600,
                9100,
                "One fifth. The bigger the denominator, the bigger the fraction.",
            ),
            Segment("Teacher", 11100, 14800, "Hmm. Any other ideas? Lin, go ahead."),
        ]


def get_transcriber() -> Transcriber:
    if settings.transcriber == "stub":
        return StubTranscriber()
    raise ValueError(f"Unknown transcriber: {settings.transcriber}")
