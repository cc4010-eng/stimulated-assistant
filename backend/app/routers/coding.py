import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.coding import Coder, get_coder
from app.config import settings
from app.db import get_db
from app.models import Code, Coding, CodingEvent, Interview, InterviewTurn, Moment, Study
from app.schemas import (
    CodeCreate,
    CodedTurn,
    CodeOut,
    CodingCreate,
    CodingOut,
    CodingSummary,
    CodingUpdate,
)

router = APIRouter(tags=["coding"])


# --- codebook ---------------------------------------------------------------


@router.get("/studies/{study_id}/codes", response_model=list[CodeOut])
def list_codes(study_id: str, db: Session = Depends(get_db)) -> list[Code]:
    return _get_study(study_id, db).codes


@router.post(
    "/studies/{study_id}/codes", response_model=CodeOut, status_code=status.HTTP_201_CREATED
)
def add_code(study_id: str, payload: CodeCreate, db: Session = Depends(get_db)) -> Code:
    study = _get_study(study_id, db)
    name = payload.name.strip()
    if any(code.name.lower() == name.lower() for code in study.codes):
        raise HTTPException(status.HTTP_409_CONFLICT, "This study already has a code by that name")
    code = Code(name=name, description=payload.description.strip())
    study.codes.append(code)
    db.commit()
    return code


# --- coding an interview ----------------------------------------------------


@router.post("/interviews/{interview_id}/code", response_model=CodingSummary)
def run_coding(
    interview_id: str, db: Session = Depends(get_db), coder: Coder = Depends(get_coder)
) -> CodingSummary:
    interview = _get_interview(interview_id, db)
    if interview.state != "finished":
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the interview before coding it")
    codebook = interview.material.study.codes
    if not codebook:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add codes to the study's codebook first")

    # Running again only fills gaps. A coding the researcher already reviewed,
    # including one they rejected, is never overwritten or proposed again.
    existing = {(c.turn_id, c.code_id) for c in _codings(interview_id, db)}
    for turn in interview.turns:
        if turn.speaker != "participant":
            continue
        for proposal in coder.code(turn.text, codebook):
            if (turn.id, proposal.code_id) in existing:
                continue
            auto_accepted = proposal.confidence >= settings.coding_auto_accept
            coding = Coding(
                interview_id=interview.id,
                turn_id=turn.id,
                code_id=proposal.code_id,
                confidence=proposal.confidence,
                rationale=proposal.rationale,
                source="ai",
                status="accepted" if auto_accepted else "needs_review",
            )
            coding.events.append(
                CodingEvent(
                    action="proposed",
                    actor="ai",
                    detail={
                        "coder": type(coder).__name__,
                        "confidence": proposal.confidence,
                        "auto_accepted": auto_accepted,
                    },
                )
            )
            db.add(coding)
    db.commit()
    return _summary(interview, db)


@router.get("/interviews/{interview_id}/codings", response_model=CodingSummary)
def list_codings(interview_id: str, db: Session = Depends(get_db)) -> CodingSummary:
    return _summary(_get_interview(interview_id, db), db)


@router.post(
    "/interviews/{interview_id}/codings",
    response_model=CodingOut,
    status_code=status.HTTP_201_CREATED,
)
def add_coding(
    interview_id: str, payload: CodingCreate, db: Session = Depends(get_db)
) -> CodingOut:
    interview = _get_interview(interview_id, db)
    turn = next((t for t in interview.turns if t.position == payload.turn_position), None)
    if turn is None or turn.speaker != "participant":
        raise HTTPException(422, "Pick a participant answer")
    code = db.get(Code, payload.code_id)
    if code is None or code.study_id != interview.material.study_id:
        raise HTTPException(422, "Unknown code for this study")

    coding = db.scalar(select(Coding).where(Coding.turn_id == turn.id, Coding.code_id == code.id))
    if coding is None:
        coding = Coding(
            interview_id=interview.id,
            turn_id=turn.id,
            code_id=code.id,
            confidence=1.0,
            source="researcher",
            status="accepted",
        )
        coding.events.append(CodingEvent(action="added", actor="researcher"))
        db.add(coding)
    elif coding.status != "accepted":
        # The researcher is applying a code the AI was unsure about, or one
        # they rejected earlier and changed their mind on.
        coding.events.append(
            CodingEvent(action="accepted", actor="researcher", detail={"before": coding.status})
        )
        coding.status = "accepted"
    db.commit()
    return _coding_out(coding)


@router.patch("/codings/{coding_id}", response_model=CodingOut)
def review_coding(
    coding_id: str, payload: CodingUpdate, db: Session = Depends(get_db)
) -> CodingOut:
    coding = db.get(Coding, coding_id)
    if coding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coding not found")
    if payload.status != coding.status:
        coding.events.append(
            CodingEvent(action=payload.status, actor="researcher", detail={"before": coding.status})
        )
        coding.status = payload.status
        db.commit()
    return _coding_out(coding)


@router.get("/interviews/{interview_id}/codings.csv")
def export_codings(interview_id: str, db: Session = Depends(get_db)) -> Response:
    interview = _get_interview(interview_id, db)
    moments = {
        m.id: m.timestamp_ms
        for m in db.scalars(select(Moment).where(Moment.material_id == interview.material_id))
    }
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["turn", "moment_ms", "answer", "code", "source", "confidence"])
    for coding in _codings(interview_id, db):
        if coding.status != "accepted":
            continue
        turn = coding.turn
        writer.writerow(
            [
                turn.position,
                moments.get(turn.moment_id or "", ""),
                turn.text,
                coding.code.name,
                coding.source,
                coding.confidence,
            ]
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="codings-{interview_id}.csv"'},
    )


# --- helpers ----------------------------------------------------------------


def _get_study(study_id: str, db: Session) -> Study:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Study not found")
    return study


def _get_interview(interview_id: str, db: Session) -> Interview:
    interview = db.get(Interview, interview_id, options=[selectinload(Interview.turns)])
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return interview


def _codings(interview_id: str, db: Session) -> list[Coding]:
    stmt = (
        select(Coding)
        .join(InterviewTurn, Coding.turn_id == InterviewTurn.id)
        .join(Code, Coding.code_id == Code.id)
        .where(Coding.interview_id == interview_id)
        .options(selectinload(Coding.turn), selectinload(Coding.code))
        .order_by(InterviewTurn.position, Code.name)
    )
    return list(db.scalars(stmt))


def _coding_out(coding: Coding) -> CodingOut:
    return CodingOut(
        id=coding.id,
        turn_position=coding.turn.position,
        code_id=coding.code_id,
        code_name=coding.code.name,
        confidence=coding.confidence,
        rationale=coding.rationale,
        source=coding.source,
        status=coding.status,
    )


def _summary(interview: Interview, db: Session) -> CodingSummary:
    by_turn: dict[str, list[CodingOut]] = {}
    for coding in _codings(interview.id, db):
        by_turn.setdefault(coding.turn_id, []).append(_coding_out(coding))
    turns = [
        CodedTurn(
            position=turn.position,
            text=turn.text,
            moment_id=turn.moment_id,
            codings=by_turn.get(turn.id, []),
        )
        for turn in interview.turns
        if turn.speaker == "participant"
    ]
    needs_review = sum(1 for t in turns for c in t.codings if c.status == "needs_review")
    return CodingSummary(interview_id=interview.id, needs_review=needs_review, turns=turns)
