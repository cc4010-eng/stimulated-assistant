import structlog
from sqlalchemy.orm import Session

from app.models import Material, TranscriptSegment
from app.storage import Storage
from app.transcription import Transcriber

log = structlog.get_logger()


def process_material(
    material_id: str, db: Session, storage: Storage, transcriber: Transcriber
) -> None:
    """Transcribe one material and store its segments.

    Takes an id and looks everything else up, so it can move to a background
    worker unchanged. Safe to run again: existing segments are replaced.
    """
    material = db.get(Material, material_id)
    if material is None:
        return

    material.status = "transcribing"
    material.error = None
    db.commit()

    try:
        segments = transcriber.transcribe(storage.path(material.storage_key))
    except Exception as exc:
        material.status = "failed"
        material.error = str(exc)
        db.commit()
        log.error("transcription_failed", material_id=material_id, error=str(exc))
        return

    material.segments = [
        TranscriptSegment(
            position=position,
            speaker=segment.speaker,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
        )
        for position, segment in enumerate(segments)
    ]
    material.status = "ready"
    db.commit()
    log.info("transcription_done", material_id=material_id, segments=len(segments))
