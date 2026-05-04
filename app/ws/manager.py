from fastapi import WebSocket
from typing import Dict, List
import json


class ConnectionManager:
    def __init__(self):
        # room_code → list of { ws, name, role }
        self.rooms: Dict[str, List[dict]] = {}

    async def connect(self, ws: WebSocket, room_code: str, name: str, role: str):
        # Note: ws.accept() is already called in the router before this
        if room_code not in self.rooms:
            self.rooms[room_code] = []
        self.rooms[room_code].append({"ws": ws, "name": name, "role": role})

    def disconnect(self, ws: WebSocket, room_code: str):
        if room_code in self.rooms:
            self.rooms[room_code] = [
                c for c in self.rooms[room_code] if c["ws"] is not ws
            ]
            if not self.rooms[room_code]:
                del self.rooms[room_code]

    async def broadcast(self, room_code: str, message: dict):
        if room_code not in self.rooms:
            return
        dead = []
        for conn in self.rooms[room_code]:
            try:
                await conn["ws"].send_json(message)
            except Exception:
                dead.append(conn)
        for c in dead:
            if c in self.rooms.get(room_code, []):
                self.rooms[room_code].remove(c)

    async def send_to_one(self, ws: WebSocket, message: dict):
        try:
            await ws.send_json(message)
        except Exception:
            pass

    def get_students(self, room_code: str) -> List[str]:
        if room_code not in self.rooms:
            return []
        return [c["name"] for c in self.rooms[room_code] if c["role"] == "student"]


manager = ConnectionManager()
