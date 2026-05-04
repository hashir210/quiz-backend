from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class SessionStartRequest(BaseModel):
    quiz_id: str


class SessionResponse(BaseModel):
    id: UUID
    room_code: str
    status: str
    quiz_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ParticipantScore(BaseModel):
    name: str
    total_score: int
    rank: int
