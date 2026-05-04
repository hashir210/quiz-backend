from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class QuestionCreate(BaseModel):
    text: str
    options: List[str]          # exactly 4 options
    correct_option: int          # 0, 1, 2, or 3
    image_url: Optional[str] = None
    order_index: int = 0


class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    options: Optional[List[str]] = None
    correct_option: Optional[int] = None
    image_url: Optional[str] = None
    order_index: Optional[int] = None


class QuestionResponse(BaseModel):
    id: UUID
    text: str
    options: List[str]
    correct_option: int
    image_url: Optional[str]
    order_index: int

    class Config:
        from_attributes = True


class QuizCreate(BaseModel):
    title: str
    description: Optional[str] = None
    time_per_q: int = 30
    max_points: int = 1000


class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    time_per_q: Optional[int] = None
    max_points: Optional[int] = None


class QuizResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    time_per_q: int
    max_points: int
    created_at: datetime
    question_count: int = 0

    class Config:
        from_attributes = True


class QuizDetailResponse(QuizResponse):
    questions: List[QuestionResponse] = []
