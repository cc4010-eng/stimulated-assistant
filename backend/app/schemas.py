from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StudyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    research_questions: str = ""


class ParticipantCreate(BaseModel):
    label: str = Field(min_length=1, max_length=64)


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    created_at: datetime


class StudyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    research_questions: str
    created_at: datetime
    participants: list[ParticipantOut] = []
