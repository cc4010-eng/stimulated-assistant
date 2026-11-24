from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Material, Moment, MomentEvent
from app.schemas import MomentCreate, MomentEventOut, MomentOut, MomentUpdate
from app.suggestion import MomentSuggester, get_suggester

router = APIRouter(tags=["moments"])


def _get_material(material_id: str, db: Session) -> Material:
    material = db.get(
        Material,
        material_id,
        options=[selectinload(Material.segments), selectinload(Material.moments)],
    )
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    return material


def _get_moment(moment_id: str, db: Session) -> Moment:
    moment = db.get(Moment, moment_id)
    if moment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Moment not found")
    return moment


def _record(moment: Moment, action: str, actor: str, **detail: object) -> None:
    moment.events.append(MomentEvent(action=action, actor=actor, detail=detail))


@router.post("/materials/{material_id}/moments/suggest", response_model=list[MomentOut])
def suggest_moments(
    material_id: str,
    db: Session = Depends(get_db),
    suggester: MomentSuggester = Depends(get_suggester),
) -> list[Moment]:
    material = _get_material(material_id, db)
    if material.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "The transcript is not ready yet")

    # Asking twice must not duplicate a suggestion, and must not bring back
    # one the researcher already removed.
    seen = {m.timestamp_ms for m in material.moments if m.source == "ai"}
    for suggestion in suggester.suggest(material.segments):
        if suggestion.timestamp_ms in seen:
            continue
        moment = Moment(
            timestamp_ms=suggestion.timestamp_ms,
            reason=suggestion.reason,
            question=suggestion.question,
            source="ai",
        )
        _record(moment, "suggested", "ai", suggester=type(suggester).__name__)
        material.moments.append(moment)
    db.commit()
    return _visible_moments(material_id, db)


@router.get("/materials/{material_id}/moments", response_model=list[MomentOut])
def list_moments(material_id: str, db: Session = Depends(get_db)) -> list[Moment]:
    _get_material(material_id, db)
    return _visible_moments(material_id, db)


@router.post(
    "/materials/{material_id}/moments",
    response_model=MomentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_moment(material_id: str, payload: MomentCreate, db: Session = Depends(get_db)) -> Moment:
    material = _get_material(material_id, db)
    moment = Moment(
        timestamp_ms=payload.timestamp_ms,
        reason=payload.reason,
        question=payload.question,
        source="researcher",
        status="confirmed",
    )
    _record(moment, "added", "researcher")
    material.moments.append(moment)
    db.commit()
    return moment


@router.patch("/moments/{moment_id}", response_model=MomentOut)
def update_moment(moment_id: str, payload: MomentUpdate, db: Session = Depends(get_db)) -> Moment:
    moment = _get_moment(moment_id, db)
    if moment.status == "removed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This moment was removed")

    if payload.question is not None and payload.question != moment.question:
        _record(moment, "edited", "researcher", before=moment.question, after=payload.question)
        moment.question = payload.question

    if payload.status is not None and payload.status != moment.status:
        action = "accepted" if payload.status == "confirmed" else "removed"
        _record(moment, action, "researcher")
        moment.status = payload.status

    db.commit()
    return moment


@router.get("/materials/{material_id}/moments/events", response_model=list[MomentEventOut])
def list_moment_events(material_id: str, db: Session = Depends(get_db)) -> list[MomentEvent]:
    _get_material(material_id, db)
    stmt = (
        select(MomentEvent)
        .join(Moment)
        .where(Moment.material_id == material_id)
        .order_by(MomentEvent.created_at, MomentEvent.id)
    )
    return list(db.scalars(stmt))


def _visible_moments(material_id: str, db: Session) -> list[Moment]:
    stmt = (
        select(Moment)
        .where(Moment.material_id == material_id, Moment.status != "removed")
        .order_by(Moment.timestamp_ms)
    )
    return list(db.scalars(stmt))
