from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.clock import Clock, get_clock
from app.db import get_db
from app.interview.engine import InterviewEngine, InvalidAction
from app.interview.policy import FollowUpPolicy, get_followup_policy
from app.models import Interview, InterviewEvent, Material, Moment
from app.schemas import (
    ApproveIn,
    InterviewCreate,
    InterviewEventOut,
    InterviewOut,
    ModeIn,
    MomentOut,
    TextIn,
    TurnOut,
)

router = APIRouter(tags=["interviews"])


def get_engine(
    interview_id: str,
    db: Session = Depends(get_db),
    policy: FollowUpPolicy = Depends(get_followup_policy),
    clock: Clock = Depends(get_clock),
) -> InterviewEngine:
    interview = db.get(
        Interview,
        interview_id,
        options=[selectinload(Interview.turns), selectinload(Interview.events)],
    )
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return InterviewEngine(db, interview, policy, clock)


def _act(engine: InterviewEngine, action: Callable[[], None]) -> InterviewOut:
    try:
        action()
    except InvalidAction as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    engine.db.commit()
    return _snapshot(engine)


def _snapshot(engine: InterviewEngine) -> InterviewOut:
    interview = engine.interview
    moment = engine.current_moment()
    decisions = [e for e in interview.events if e.type == "followup_decided"]
    return InterviewOut(
        id=interview.id,
        material_id=interview.material_id,
        mode=interview.mode,
        state=interview.state,
        budget_seconds=interview.budget_seconds,
        elapsed_seconds=round(engine.elapsed_seconds()),
        remaining_seconds=round(engine.remaining_seconds()),
        moments_total=len(engine.moments),
        moment_index=interview.moment_index,
        current_moment=MomentOut.model_validate(moment) if moment else None,
        moment_seconds=round(engine.moment_elapsed_seconds()) if moment else 0,
        moment_allowance_seconds=interview.moment_allowance_seconds,
        followups_used=interview.followups_used,
        max_followups=interview.max_followups,
        pending_question=interview.pending_text,
        suggested_question=interview.suggestion_text,
        last_decision=decisions[-1].detail if decisions else None,
        finished_reason=interview.finished_reason,
        turns=[TurnOut.model_validate(turn) for turn in interview.turns],
    )


@router.post(
    "/materials/{material_id}/interviews",
    response_model=InterviewOut,
    status_code=status.HTTP_201_CREATED,
)
def start_interview(
    material_id: str,
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    policy: FollowUpPolicy = Depends(get_followup_policy),
    clock: Clock = Depends(get_clock),
) -> InterviewOut:
    if db.get(Material, material_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")

    has_confirmed = db.scalar(
        select(Moment.id).where(Moment.material_id == material_id, Moment.status == "confirmed")
    )
    if has_confirmed is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Confirm at least one moment before starting an interview"
        )

    interview = Interview(
        material_id=material_id,
        mode=payload.mode,
        budget_seconds=payload.budget_minutes * 60,
        max_followups=payload.max_followups,
    )
    db.add(interview)
    db.flush()  # apply column defaults before the engine reads them
    engine = InterviewEngine(db, interview, policy, clock)
    engine.start()
    db.commit()
    return _snapshot(engine)


@router.get("/interviews/{interview_id}", response_model=InterviewOut)
def get_interview(engine: InterviewEngine = Depends(get_engine)) -> InterviewOut:
    return _snapshot(engine)


@router.post("/interviews/{interview_id}/answer", response_model=InterviewOut)
def answer(payload: TextIn, engine: InterviewEngine = Depends(get_engine)) -> InterviewOut:
    return _act(engine, lambda: engine.answer(payload.text.strip()))


@router.post("/interviews/{interview_id}/approve", response_model=InterviewOut)
def approve(
    payload: ApproveIn | None = None, engine: InterviewEngine = Depends(get_engine)
) -> InterviewOut:
    return _act(engine, lambda: engine.approve(payload.text if payload else None))


@router.post("/interviews/{interview_id}/skip", response_model=InterviewOut)
def skip(engine: InterviewEngine = Depends(get_engine)) -> InterviewOut:
    return _act(engine, engine.skip)


@router.post("/interviews/{interview_id}/expire", response_model=InterviewOut)
def expire(engine: InterviewEngine = Depends(get_engine)) -> InterviewOut:
    return _act(engine, engine.expire)


@router.post("/interviews/{interview_id}/say", response_model=InterviewOut)
def say(payload: TextIn, engine: InterviewEngine = Depends(get_engine)) -> InterviewOut:
    return _act(engine, lambda: engine.say(payload.text.strip()))


@router.post("/interviews/{interview_id}/next", response_model=InterviewOut)
def next_moment(engine: InterviewEngine = Depends(get_engine)) -> InterviewOut:
    return _act(engine, engine.next_moment)


@router.post("/interviews/{interview_id}/mode", response_model=InterviewOut)
def set_mode(payload: ModeIn, engine: InterviewEngine = Depends(get_engine)) -> InterviewOut:
    return _act(engine, lambda: engine.set_mode(payload.mode))


@router.post("/interviews/{interview_id}/end", response_model=InterviewOut)
def end(engine: InterviewEngine = Depends(get_engine)) -> InterviewOut:
    return _act(engine, engine.end)


@router.get("/interviews/{interview_id}/events", response_model=list[InterviewEventOut])
def list_events(engine: InterviewEngine = Depends(get_engine)) -> list[InterviewEvent]:
    return engine.interview.events
