from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.logging import logger
from app.core.websockets import ws_manager

router = APIRouter(tags=["Real-time WebSockets"])


@router.websocket("/ws/shows/{show_id}/seats")
async def show_seats_websocket_endpoint(websocket: WebSocket, show_id: str):
    await ws_manager.connect(show_id, websocket)
    logger.info(f"Client connected to WebSocket for show {show_id}")
    try:
        while True:
            # Keep-alive ping/pong listener
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(show_id, websocket)
        logger.info(f"Client disconnected from WebSocket for show {show_id}")
