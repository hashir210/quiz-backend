from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import require_teacher
from app.models.user import User
from app.models.quiz import Quiz, Question
from app.schemas.quiz import (
    QuizCreate, QuizUpdate, QuizResponse,
    QuizDetailResponse, QuestionCreate, QuestionUpdate
)
from app.core.config import settings
import uuid, io, httpx

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────

async def upload_to_supabase(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload a file to Supabase Storage and return the public URL."""
    bucket = "quiz-images"
    file_path = f"questions/{uuid.uuid4()}-{filename}"

    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{settings.SUPABASE_URL}/storage/v1/object/{bucket}/{file_path}",
            headers={
                "apikey": settings.SUPABASE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                "Content-Type": content_type,
            },
            content=file_bytes,
        )
        if response.status_code not in [200, 201]:
            raise HTTPException(500, f"Upload failed: {response.text}")

    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{file_path}"


# ── Quiz Routes ───────────────────────────────────────────

@router.get("/", response_model=list[QuizResponse])
async def list_quizzes(
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Quiz).where(Quiz.teacher_id == teacher.id)
        .order_by(Quiz.created_at.desc())
    )
    quizzes = result.scalars().all()
    for quiz in quizzes:
        q_count = await db.execute(
            select(func.count()).where(Question.quiz_id == quiz.id)
        )
        quiz.question_count = q_count.scalar()
    return quizzes


@router.post("/", response_model=QuizResponse)
async def create_quiz(
    data: QuizCreate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    quiz = Quiz(**data.model_dump(), teacher_id=teacher.id)
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)
    quiz.question_count = 0
    return quiz


@router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(
    quiz_id: str,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Quiz)
        .options(selectinload(Quiz.questions))
        .where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if str(quiz.teacher_id) != str(teacher.id) and teacher.role != "admin":
        raise HTTPException(403, "Not your quiz")
    quiz.question_count = len(quiz.questions)
    return quiz


@router.put("/{quiz_id}")
async def update_quiz(
    quiz_id: str,
    data: QuizUpdate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if str(quiz.teacher_id) != str(teacher.id):
        raise HTTPException(403, "Not your quiz")
    for key, val in data.model_dump(exclude_none=True).items():
        setattr(quiz, key, val)
    await db.commit()
    return {"message": "Quiz updated"}


@router.delete("/{quiz_id}")
async def delete_quiz(
    quiz_id: str,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if str(quiz.teacher_id) != str(teacher.id) and teacher.role != "admin":
        raise HTTPException(403, "Not your quiz")
    await db.delete(quiz)
    await db.commit()
    return {"message": "Quiz deleted"}


# ── Question Routes ───────────────────────────────────────

@router.post("/{quiz_id}/questions")
async def add_question(
    quiz_id: str,
    data: QuestionCreate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    if len(data.options) != 4:
        raise HTTPException(400, "Exactly 4 options required")
    if data.correct_option not in [0, 1, 2, 3]:
        raise HTTPException(400, "correct_option must be 0, 1, 2, or 3")
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz or str(quiz.teacher_id) != str(teacher.id):
        raise HTTPException(403, "Not your quiz")
    question = Question(**data.model_dump(), quiz_id=quiz_id)
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


@router.delete("/{quiz_id}/questions")
async def delete_all_questions(
    quiz_id: str,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz or str(quiz.teacher_id) != str(teacher.id):
        raise HTTPException(403, "Not your quiz")
    
    from sqlalchemy import delete
    await db.execute(delete(Question).where(Question.quiz_id == quiz_id))
    await db.commit()
    return {"message": "All questions deleted"}


@router.put("/questions/{question_id}")
async def update_question(
    question_id: str,
    data: QuestionUpdate,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    query = select(Question).join(Quiz, Question.quiz_id == Quiz.id).where(Question.id == question_id)
    if teacher.role != "admin":
        query = query.where(Quiz.teacher_id == teacher.id)
    result = await db.execute(query)
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")
    if data.options is not None and len(data.options) != 4:
        raise HTTPException(400, "Exactly 4 options required")
    if data.correct_option is not None and data.correct_option not in [0, 1, 2, 3]:
        raise HTTPException(400, "correct_option must be 0, 1, 2, or 3")
    for key, val in data.model_dump(exclude_none=True).items():
        setattr(question, key, val)
    await db.commit()
    return {"message": "Question updated"}


@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: str,
    teacher: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    query = select(Question).join(Quiz, Question.quiz_id == Quiz.id).where(Question.id == question_id)
    if teacher.role != "admin":
        query = query.where(Quiz.teacher_id == teacher.id)
    result = await db.execute(query)
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")
    await db.delete(question)
    await db.commit()
    return {"message": "Question deleted"}


# ── Image Upload (Supabase Storage) ──────────────────────

@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    teacher: User = Depends(require_teacher),
):
    allowed = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    if file.content_type not in allowed:
        raise HTTPException(400, "Only JPEG, PNG, WebP, GIF allowed")

    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 5MB")
    url = await upload_to_supabase(file_bytes, file.filename, file.content_type)
    return {"url": url}
