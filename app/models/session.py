from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import uuid


class Session(Base):
    __tablename__ = "sessions"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id    = Column(UUID(as_uuid=True), ForeignKey("quizzes.id"), nullable=False)
    room_code  = Column(String(8), unique=True, nullable=False, index=True)
    status     = Column(String, default="waiting")  # waiting | active | finished
    started_at = Column(DateTime, nullable=True)
    ended_at   = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    quiz         = relationship("Quiz", back_populates="sessions")
    participants = relationship("Participant", back_populates="session",
                                cascade="all, delete-orphan")
