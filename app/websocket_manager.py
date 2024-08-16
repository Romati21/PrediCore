import asyncio
import logging
from fastapi import WebSocket
from typing import List

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.ping_task = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Новое WebSocket соединение: {websocket.client}")
        if self.ping_task is None:
            self.ping_task = asyncio.create_task(self.ping_clients())

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket соединение закрыто: {websocket.client}")

    async def broadcast(self, message: str):
        logger.info(f"Рассылка сообщения всем клиентам: {message}")
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения: {e}")
                dead_connections.append(connection)

        for dead_connection in dead_connections:
            self.active_connections.remove(dead_connection)

    async def ping_clients(self):
        while True:
            await asyncio.sleep(30)  # Отправляем пинг каждые 30 секунд
            dead_connections = []
            for connection in self.active_connections:
                try:
                    await connection.send_text('ping')
                except Exception as e:
                    logger.error(f"Ошибка при отправке пинга: {e}")
                    dead_connections.append(connection)

            for dead_connection in dead_connections:
                self.active_connections.remove(dead_connection)

manager = ConnectionManager()
