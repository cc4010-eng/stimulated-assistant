import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
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
