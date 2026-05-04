from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import uuid


class Quiz(Base):
    __tablename__ = "quizzes"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title       = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    time_per_q  = Column(Integer, default=30)       # seconds per question
    max_points  = Column(Integer, default=1000)     # points for first correct answer
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teacher   = relationship("User", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz",
                             order_by="Question.order_index",
                             cascade="all, delete-orphan")
    sessions  = relationship("Session", back_populates="quiz",
                             cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id        = Column(UUID(as_uuid=True), ForeignKey("quizzes.id"), nullable=False)
    text           = Column(Text, nullable=False)
    image_url      = Column(String, nullable=True)
    options        = Column(JSONB, nullable=False)   # ["Option A", "Option B", "Option C", "Option D"]
    correct_option = Column(Integer, nullable=False) # 0, 1, 2, or 3
    order_index    = Column(Integer, default=0)

    quiz = relationship("Quiz", back_populates="questions")
