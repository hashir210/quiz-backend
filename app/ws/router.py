from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws.manager import manager
from app.ws.handler import handle_event
from app.models.session import Session
from app.models.participant import Participant
from app.core.database import AsyncSessionLocal
from sqlalchemy import select

router = APIRouter()


@router.websocket("/ws/{room_code}")
async def websocket_endpoint(ws: WebSocket, room_code: str):
    # First message must be: {"event": "join", "name": "Ali", "role": "student"}
    await ws.accept()

    try:
        init = await ws.receive_json()
    except Exception:
        await ws.close()
        return

    name = init.get("name", "Anonymous")
    role = init.get("role", "student")   # "student" or "teacher"
    room_code = room_code.upper()

    # For students: create participant record in DB
    if role == "student":
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Session).where(Session.room_code == room_code)
            )
            session = result.scalar_one_or_none()
            if session:
                participant = Participant(session_id=session.id, name=name)
                db.add(participant)
                await db.commit()

    await manager.connect(ws, room_code, name, role)

    try:
        while True:
            data = await ws.receive_json()
            await handle_event(ws, room_code, name, role, data)

    except WebSocketDisconnect:
        manager.disconnect(ws, room_code)
        await manager.broadcast(room_code, {
            "event": "student_left",
            "name": name,
            "students": manager.get_students(room_code),
        })
