from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Participant, Study
from app.schemas import ParticipantCreate, ParticipantOut, StudyCreate, StudyOut

router = APIRouter(prefix="/studies", tags=["studies"])


def _get_study(study_id: str, db: Session) -> Study:
    study = db.get(Study, study_id, options=[selectinload(Study.participants)])
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Study not found")
    return study


@router.get("", response_model=list[StudyOut])
def list_studies(db: Session = Depends(get_db)) -> list[Study]:
    stmt = select(Study).options(selectinload(Study.participants)).order_by(Study.created_at.desc())
    return list(db.scalars(stmt))


@router.post("", response_model=StudyOut, status_code=status.HTTP_201_CREATED)
def create_study(payload: StudyCreate, db: Session = Depends(get_db)) -> Study:
    study = Study(**payload.model_dump())
    db.add(study)
    db.commit()
    return _get_study(study.id, db)


@router.get("/{study_id}", response_model=StudyOut)
def get_study(study_id: str, db: Session = Depends(get_db)) -> Study:
    return _get_study(study_id, db)


@router.post(
    "/{study_id}/participants",
    response_model=ParticipantOut,
    status_code=status.HTTP_201_CREATED,
)
def add_participant(
    study_id: str, payload: ParticipantCreate, db: Session = Depends(get_db)
) -> Participant:
    study = _get_study(study_id, db)
    participant = Participant(study_id=study.id, label=payload.label)
    db.add(participant)
    db.commit()
    return participant
