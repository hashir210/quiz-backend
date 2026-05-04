import time
import json
import asyncio
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.ws.manager import manager
from app.models.session import Session
from app.models.quiz import Quiz, Question
from app.models.participant import Participant, Answer
from app.core.database import AsyncSessionLocal


async def get_question(quiz_id: str, index: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.order_index)
        )
        questions = result.scalars().all()
        if index < len(questions):
            return questions[index], len(questions)
        return None, len(questions)


async def handle_event(ws: WebSocket, room_code: str, name: str, role: str, data: dict):
    event = data.get("event")

    # ── Student joins waiting room ────────────────────────
    if event == "student_join":
        await manager.broadcast(room_code, {
            "event": "student_joined",
            "name": name,
            "students": manager.get_students(room_code),
        })

    # ── Teacher starts quiz ───────────────────────────────
    elif event == "teacher_start":
        if role != "teacher":
            return
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Session).where(Session.room_code == room_code)
            )
            session = result.scalar_one_or_none()
            if not session:
                return
            session.status = "active"
            await db.commit()

        await manager.broadcast(room_code, {"event": "quiz_started"})
        await asyncio.sleep(2)
        await send_question(room_code, 0)

    # ── Teacher advances to next question ─────────────────
    elif event == "teacher_next":
        if role != "teacher":
            return
        q_index = data.get("next_index", 0)
        await send_question(room_code, q_index)

    # ── Student answers ───────────────────────────────────
    elif event == "student_answer":
        await handle_answer(ws, room_code, name, data)

    # ── Teacher ends quiz ─────────────────────────────────
    elif event == "teacher_end":
        if role != "teacher":
            return
        await end_quiz(room_code)


async def send_question(room_code: str, q_index: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session).where(Session.room_code == room_code)
        )
        session = result.scalar_one_or_none()
        if not session:
            return

    question, total = await get_question(str(session.quiz_id), q_index)

    if not question:
        await end_quiz(room_code)
        return

    # Store question start time in memory (manager)
    manager.rooms[room_code + "_meta"] = [{
        "q_index": q_index,
        "q_id": str(question.id),
        "correct": question.correct_option,
        "start_time": time.time(),
        "answered": {},   # name → chosen_option
    }]

    # Send question to all — do NOT include correct answer
    await manager.broadcast(room_code, {
        "event": "question_show",
        "index": q_index,
        "total": total,
        "text": question.text,
        "options": question.options,
        "image_url": question.image_url,
        "time_limit": 30,
    })


async def handle_answer(ws: WebSocket, room_code: str, name: str, data: dict):
    meta_key = room_code + "_meta"
    if meta_key not in manager.rooms or not manager.rooms[meta_key]:
        return

    meta = manager.rooms[meta_key][0]

    # Prevent answering twice
    if name in meta["answered"]:
        return

    elapsed = time.time() - meta["start_time"]
    chosen = data.get("option")
    is_correct = chosen == meta["correct"]

    # Scoring: 1000 points minus 100 per second elapsed, minimum 100 if correct
    if is_correct:
        score = max(100, int(1000 - (elapsed * 100)))
    else:
        score = 0

    meta["answered"][name] = chosen

    # Save to database
    async with AsyncSessionLocal() as db:
        # Get participant
        result = await db.execute(
            select(Participant)
            .join(Participant.session)
            .where(
                Session.room_code == room_code,
                Participant.name == name,
            )
        )
        participant = result.scalar_one_or_none()
        if participant:
            participant.total_score += score
            answer = Answer(
                participant_id=participant.id,
                question_id=meta["q_id"],
                chosen_option=chosen,
                is_correct=1 if is_correct else 0,
                points_earned=score,
            )
            db.add(answer)
            await db.commit()

    # Tell this student their result privately
    await manager.send_to_one(ws, {
        "event": "answer_result",
        "correct": is_correct,
        "points_earned": score,
        "correct_option": meta["correct"],
    })


async def end_quiz(room_code: str):
    # Get final leaderboard from database
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session).where(Session.room_code == room_code)
        )
        session = result.scalar_one_or_none()
        if session:
            session.status = "finished"
            await db.commit()

        p_result = await db.execute(
            select(Participant)
            .where(Participant.session_id == session.id)
            .order_by(Participant.total_score.desc())
        )
        participants = p_result.scalars().all()
        leaderboard = [
            {"rank": i + 1, "name": p.name, "score": p.total_score}
            for i, p in enumerate(participants)
        ]

    await manager.broadcast(room_code, {
        "event": "quiz_ended",
        "leaderboard": leaderboard,
    })
