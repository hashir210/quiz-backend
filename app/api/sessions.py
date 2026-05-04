from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import require_teacher
from app.models.user import User
from app.models.quiz import Quiz
from app.models.session import Session
from app.models.participant import Participant
from app.schemas.session import SessionStartRequest, SessionResponse
import random, string

router = APIRouter()


def generate_room_code(length=6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


@router.post("/start", response_model=SessionResponse)
async def start_session(
    data: SessionStartRequest,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    # Verify quiz belongs to teacher
    result = await db.execute(select(Quiz).where(Quiz.id == data.quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if str(quiz.teacher_id) != str(teacher.id) and teacher.role != "admin":
        raise HTTPException(403, "Not your quiz")

    # Generate unique room code
    for _ in range(10):
        code = generate_room_code()
        existing = await db.execute(
            select(Session).where(Session.room_code == code, Session.status != "finished")
        )
        if not existing.scalar_one_or_none():
            break

    session = Session(quiz_id=data.quiz_id, room_code=code, status="waiting")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{room_code}/validate")
async def validate_room(room_code: str, db: AsyncSession = Depends(get_db)):
    # Public endpoint — no auth — students call this
    result = await db.execute(
        select(Session).where(
            Session.room_code == room_code.upper(),
            Session.status.in_(["waiting", "active"])
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Room not found or quiz has ended")
    return {"valid": True, "status": session.status}


@router.get("/{session_id}/results")
async def get_results(
    session_id: str,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Participant)
        .where(Participant.session_id == session_id)
        .order_by(Participant.total_score.desc())
    )
    participants = result.scalars().all()
    return [
        {"rank": i + 1, "name": p.name, "total_score": p.total_score}
        for i, p in enumerate(participants)
    ]
