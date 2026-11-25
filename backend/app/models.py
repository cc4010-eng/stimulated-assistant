import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Single-user for now. Every study still carries an owner so that auth can be
# added later without a data migration.
DEFAULT_OWNER = "local"


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Study(Base):
    __tablename__ = "studies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_OWNER, index=True)
    title: Mapped[str] = mapped_column(String(200))
    research_questions: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    participants: Mapped[list["Participant"]] = relationship(
        back_populates="study", cascade="all, delete-orphan"
    )
    materials: Mapped[list["Material"]] = relationship(
        back_populates="study", cascade="all, delete-orphan"
    )


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), index=True)
    # A pseudonym such as "T07". Real names stay out of the database.
    label: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    study: Mapped[Study] = relationship(back_populates="participants")


class Material(Base):
    """A recording the participant will review: audio or video of their own activity."""

    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(255))
    # uploaded -> transcribing -> ready | failed
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    study: Mapped[Study] = relationship(back_populates="materials")
    moments: Mapped[list["Moment"]] = relationship(
        back_populates="material", cascade="all, delete-orphan", order_by="Moment.timestamp_ms"
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.position",
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(64))
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    material: Mapped[Material] = relationship(back_populates="segments")


class Moment(Base):
    """A point in the material to stop at and ask about during the interview."""

    __tablename__ = "moments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    timestamp_ms: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    question: Mapped[str] = mapped_column(Text)
    # Who proposed it: "ai" or "researcher".
    source: Mapped[str] = mapped_column(String(20))
    # candidate -> confirmed | removed. Removed moments are kept for evaluation.
    status: Mapped[str] = mapped_column(String(20), default="candidate")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    material: Mapped[Material] = relationship(back_populates="moments")
    events: Mapped[list["MomentEvent"]] = relationship(
        back_populates="moment", cascade="all, delete-orphan", order_by="MomentEvent.created_at"
    )


class MomentEvent(Base):
    """Append-only record of what happened to a moment and who did it.

    Researcher decisions on AI suggestions are the ground truth for judging
    the suggester later, so nothing here is updated or deleted.
    """

    __tablename__ = "moment_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    moment_id: Mapped[str] = mapped_column(ForeignKey("moments.id", ondelete="CASCADE"), index=True)
    # suggested | added | accepted | edited | removed
    action: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(20))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    moment: Mapped[Moment] = relationship(back_populates="events")


class Interview(Base):
    """One interview about one material. Holds the state machine's position."""

    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    # ai_leads | ai_asks_first | researcher_leads
    mode: Mapped[str] = mapped_column(String(20))
    # awaiting_answer | awaiting_approval | researcher_turn | finished
    state: Mapped[str] = mapped_column(String(20), default="awaiting_answer")
    budget_seconds: Mapped[int] = mapped_column(Integer)
    max_followups: Mapped[int] = mapped_column(Integer, default=2)

    moment_index: Mapped[int] = mapped_column(Integer, default=0)
    followups_used: Mapped[int] = mapped_column(Integer, default=0)
    moment_allowance_seconds: Mapped[int] = mapped_column(Integer, default=0)
    moment_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # A question the AI wants to ask but has not said: waiting for approval
    # (pending) or offered to the researcher as a hint (suggestion).
    pending_text: Mapped[str | None] = mapped_column(Text, default=None)
    suggestion_text: Mapped[str | None] = mapped_column(Text, default=None)
    # moment | followup
    pending_kind: Mapped[str | None] = mapped_column(String(20), default=None)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_reason: Mapped[str | None] = mapped_column(String(40), default=None)

    material: Mapped[Material] = relationship(back_populates="interviews")
    turns: Mapped[list["InterviewTurn"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewTurn.position",
    )
    events: Mapped[list["InterviewEvent"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewEvent.position",
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    # ai | researcher | participant
    speaker: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    moment_id: Mapped[str | None] = mapped_column(String(36), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    interview: Mapped[Interview] = relationship(back_populates="turns")


class InterviewEvent(Base):
    """Append-only log of every decision the engine or the researcher made."""

    __tablename__ = "interview_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    interview: Mapped[Interview] = relationship(back_populates="events")
