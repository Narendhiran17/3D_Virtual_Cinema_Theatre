import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import WebSocket


class ShowSeatConnectionManager:
    def __init__(self):
        # Map: show_id -> list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, show_id: str, websocket: WebSocket):
        await websocket.accept()
        if show_id not in self.active_connections:
            self.active_connections[show_id] = []
        self.active_connections[show_id].append(websocket)

    def disconnect(self, show_id: str, websocket: WebSocket):
        if show_id in self.active_connections:
            if websocket in self.active_connections[show_id]:
                self.active_connections[show_id].remove(websocket)
            if not self.active_connections[show_id]:
                del self.active_connections[show_id]

    async def broadcast_seat_event(
        self,
        show_id: str,
        event_name: str,
        seat_labels: List[str],
        new_status: str,
    ):
        """Broadcasts real-time seat inventory state transitions to all connected clients."""
        connections = self.active_connections.get(show_id, [])
        if not connections:
            return

        payload = {
            "event_id": f"evt-{uuid.uuid4().hex[:12]}",
            "event": event_name,
            "show_id": show_id,
            "seat_labels": seat_labels,
            "status": new_status,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        message = json.dumps(payload)

        # Dispatch concurrently to all connected clients
        dead_connections = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(show_id, dead)


ws_manager = ShowSeatConnectionManager()
