from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import require_teacher
from app.core.config import settings
from app.models.user import User
from app.models.quiz import Quiz
from app.models.session import Session
from app.models.participant import Participant
from app.schemas.session import SessionStartRequest, SessionResponse
from typing import Optional
import io, qrcode, random, string

router = APIRouter()


@router.get("/")
async def list_sessions(
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session, Quiz.title)
        .join(Quiz, Session.quiz_id == Quiz.id)
        .where(Quiz.teacher_id == teacher.id, Session.status == "finished")
        .order_by(Session.id.desc())
    )
    sessions = result.all()
    
    output = []
    for s, title in sessions:
        # Get count of participants
        p_res = await db.execute(select(Participant).where(Participant.session_id == s.id))
        participants = p_res.scalars().all()
        
        output.append({
            "id": str(s.id),
            "quiz_title": title,
            "room_code": s.room_code,
            "participants_count": len(participants),
            "date": "Recently" # Simple placeholder for now
        })
    return output



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
    code = None
    for _ in range(10):
        code = generate_room_code()
        existing = await db.execute(
            select(Session).where(Session.room_code == code, Session.status != "finished")
        )
        if not existing.scalar_one_or_none():
            break
    else:
        raise HTTPException(500, "Could not generate a room code")

    session = Session(quiz_id=data.quiz_id, room_code=code, status="waiting")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{room_code}/qr")
async def get_room_qr(
    room_code: str,
    join_url: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(
            Session.room_code == room_code.upper(),
            Session.status.in_(["waiting", "active"])
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Room not found or quiz has ended")

    frontend_url = settings.FRONTEND_URL.split(",")[0].strip().rstrip("/")
    target_url = join_url or f"{frontend_url}/play/{room_code.upper()}"
    image = qrcode.make(target_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


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
    return {"valid": True, "status": session.status, "quiz_id": str(session.quiz_id)}


@router.get("/{room_code}/results")
async def get_results(
    room_code: str,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    # Find session by room code
    s_result = await db.execute(select(Session).where(Session.room_code == room_code.upper()))
    session = s_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    quiz_result = await db.execute(select(Quiz).where(Quiz.id == session.quiz_id))
    quiz = quiz_result.scalar_one_or_none()
    if not quiz or (str(quiz.teacher_id) != str(teacher.id) and teacher.role != "admin"):
        raise HTTPException(403, "Not your session")

    result = await db.execute(
        select(Participant)
        .where(Participant.session_id == session.id)
        .order_by(Participant.total_score.desc())
    )
    participants = result.scalars().all()
    return [
        {"rank": i + 1, "name": p.name, "total_score": p.total_score}
        for i, p in enumerate(participants)
    ]
