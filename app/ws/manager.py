import asyncio
import uuid
from fastapi import WebSocket
from typing import Dict, List, Optional


class ConnectionManager:
    def __init__(self):
        # room_code → list of { ws, name, role }
        self.rooms: Dict[str, List[dict]] = {}
        # room_code → metadata (current question, locks, etc.)
        self.meta: Dict[str, dict] = {}

    async def connect(self, ws: WebSocket, room_code: str, name: str, role: str):
        # Note: ws.accept() is already called in the router before this
        if room_code not in self.rooms:
            self.rooms[room_code] = []
        self.rooms[room_code].append({
            "id": uuid.uuid4().hex,
            "ws": ws,
            "name": name,
            "role": role,
        })

    def disconnect(self, ws: WebSocket, room_code: str):
        if room_code in self.rooms:
            self.rooms[room_code] = [
                c for c in self.rooms[room_code] if c["ws"] is not ws
            ]
            if not self.rooms[room_code]:
                del self.rooms[room_code]
        if room_code in self.meta and room_code not in self.rooms:
            del self.meta[room_code]

    async def broadcast(self, room_code: str, message: dict):
        if room_code not in self.rooms:
            return
        conns = list(self.rooms[room_code])
        tasks = [conn["ws"].send_json(message) for conn in conns]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for conn, res in zip(conns, results):
            if isinstance(res, Exception):
                if conn in self.rooms.get(room_code, []):
                    self.rooms[room_code].remove(conn)

    async def send_to_one(self, ws: WebSocket, message: dict):
        try:
            await ws.send_json(message)
        except Exception:
            pass

    def get_students(self, room_code: str) -> List[str]:
        if room_code not in self.rooms:
            return []
        return [c["name"] for c in self.rooms[room_code] if c["role"] == "student"]

    def get_conn_id(self, room_code: str, ws: WebSocket) -> Optional[str]:
        for c in self.rooms.get(room_code, []):
            if c["ws"] is ws:
                return c["id"]
        return None

    def ensure_room_meta(self, room_code: str) -> dict:
        if room_code not in self.meta:
            self.meta[room_code] = {
                "lock": asyncio.Lock(),
                "question": None,  # set by handler.send_question
            }
        return self.meta[room_code]


manager = ConnectionManager()
