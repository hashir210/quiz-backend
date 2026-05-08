import time
import asyncio
from fastapi import WebSocket
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.ws.manager import manager
from app.models.session import Session
from app.models.quiz import Question
from app.models.participant import Participant, Answer
from app.core.database import AsyncSessionLocal


async def get_question(quiz_id: str, index: int):
    async with AsyncSessionLocal() as db:
        total_res = await db.execute(
            select(func.count()).select_from(Question).where(Question.quiz_id == quiz_id)
        )
        total = int(total_res.scalar() or 0)
        if index >= total:
            return None, total

        q_res = await db.execute(
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.order_index)
            .offset(index)
            .limit(1)
        )
        question = q_res.scalar_one_or_none()
        return question, total


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
        await flush_current_question(room_code)
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
    manager.ensure_room_meta(room_code)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session)
            .options(selectinload(Session.quiz))
            .where(Session.room_code == room_code)
        )
        session = result.scalar_one_or_none()
        if not session:
            return

    question, total = await get_question(str(session.quiz_id), q_index)

    if not question:
        await flush_current_question(room_code)
        await end_quiz(room_code)
        return

    # Store question start time in memory (separate from connections).
    rmeta = manager.ensure_room_meta(room_code)
    rmeta["question"] = {
        "q_index": q_index,
        "total": total,
        "q_id": str(question.id),
        "correct": question.correct_option,
        "start_time": time.time(),
        "time_limit": int(session.quiz.time_per_q),
        "max_points": int(session.quiz.max_points),
        "answered": {},   # conn_id → chosen_option
        "answers": [],    # buffered rows to flush to DB
        "end_scheduled": False,
    }

    # Send question to all — do NOT include correct answer
    await manager.broadcast(room_code, {
        "event": "question_show",
        "index": q_index,
        "total": total,
        "text": question.text,
        "options": question.options,
        "image_url": question.image_url,
        "time_limit": session.quiz.time_per_q,
    })


async def handle_answer(ws: WebSocket, room_code: str, name: str, data: dict):
    rmeta = manager.ensure_room_meta(room_code)
    q = rmeta.get("question")
    if not q:
        return

    conn_id = manager.get_conn_id(room_code, ws) or name
    should_end = False

    async with rmeta["lock"]:
        # Prevent answering twice per connection
        if conn_id in q["answered"]:
            return

        elapsed = time.time() - q["start_time"]
        chosen = data.get("option")
        is_correct = chosen == q["correct"]

        # Enforce time limit server-side
        if elapsed > q["time_limit"]:
            is_correct = False
            score = 0
            timed_out = True
        else:
            timed_out = False
            score = 0

        q["answered"][conn_id] = chosen

        # If this is the last question and everyone answered, auto-end quiz.
        if not q.get("end_scheduled"):
            students_count = len(manager.get_students(room_code))
            if students_count > 0 and len(q["answered"]) >= students_count:
                if int(q.get("q_index", 0)) >= int(q.get("total", 1)) - 1:
                    q["end_scheduled"] = True
                    should_end = True

    await manager.broadcast(room_code, {
        "event": "student_answered",
        "answered_count": len(q["answered"]),
        "students_count": len(manager.get_students(room_code)),
    })

    # Compute score (read-only operations; no DB writes here)
    if is_correct and not timed_out:
        max_points = q["max_points"]
        time_limit = q["time_limit"]
        elapsed_ratio = min(elapsed / max(time_limit, 1), 1)
        score = max(100, int(max_points * (1 - elapsed_ratio * 0.9)))

    # Buffer DB writes (flush on next question or end)
    async with rmeta["lock"]:
        q["answers"].append({
            "name": name,
            "question_id": q["q_id"],
            "chosen_option": chosen,
            "is_correct": 1 if is_correct else 0,
            "points_earned": score,
        })

    await manager.send_to_one(ws, {
        "event": "answer_result",
        "correct": is_correct,
        "points_earned": score,
        "correct_option": q["correct"],
        **({"timed_out": True} if timed_out else {}),
    })

    if should_end:
        # Persist final question answers, then broadcast final leaderboard.
        await flush_current_question(room_code)
        await end_quiz(room_code)


async def flush_current_question(room_code: str):
    """
    Persist buffered answers in one DB transaction.
    This drastically reduces writes on Supabase free tier.
    """
    rmeta = manager.ensure_room_meta(room_code)
    q = rmeta.get("question")
    if not q:
        return

    async with rmeta["lock"]:
        buffered = list(q.get("answers", []))
        q["answers"] = []

    if not buffered:
        return

    async with AsyncSessionLocal() as db:
        s_result = await db.execute(
            select(Session).where(Session.room_code == room_code)
        )
        session = s_result.scalar_one_or_none()
        if not session:
            return

        names = {a["name"] for a in buffered}
        p_res = await db.execute(
            select(Participant).where(
                Participant.session_id == session.id,
                Participant.name.in_(names),
            )
        )
        participants = {p.name: p for p in p_res.scalars().all()}

        # Create missing participants
        for nm in names:
            if nm not in participants:
                p = Participant(session_id=session.id, name=nm, total_score=0)
                db.add(p)
                participants[nm] = p

        await db.flush()

        # Apply updates + insert answers
        for a in buffered:
            p = participants[a["name"]]
            p.total_score += int(a["points_earned"] or 0)
            db.add(Answer(
                participant_id=p.id,
                question_id=a["question_id"],
                chosen_option=a["chosen_option"],
                is_correct=a["is_correct"],
                points_earned=a["points_earned"],
            ))

        await db.commit()


async def end_quiz(room_code: str):
    await flush_current_question(room_code)
    # Get final leaderboard from database
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session).where(Session.room_code == room_code)
        )
        session = result.scalar_one_or_none()
        if not session:
            return

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
