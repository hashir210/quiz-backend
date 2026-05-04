from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import uuid


class Participant(Base):
    __tablename__ = "participants"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id  = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    name        = Column(String, nullable=False)   # just display name, NO login required
    total_score = Column(Integer, default=0)
    joined_at   = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="participants")
    answers = relationship("Answer", back_populates="participant",
                           cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)
    question_id    = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    chosen_option  = Column(Integer, nullable=False)   # 0-3
    is_correct     = Column(Integer, nullable=False)   # 0 or 1
    points_earned  = Column(Integer, default=0)
    answered_at    = Column(DateTime, default=datetime.utcnow)

    participant = relationship("Participant", back_populates="answers")
