from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class WebSocketHub:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.symbol_filters: dict[WebSocket, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, symbols: list[str] | None = None) -> None:
        await ws.accept()
        async with self._lock:
            self.connections.add(ws)
            self.symbol_filters[ws] = {s.upper() for s in (symbols or [])}

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.connections.discard(ws)
            self.symbol_filters.pop(ws, None)

    async def broadcast(self, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.connections):
            try:
                wanted = self.symbol_filters.get(ws, set())
                if wanted and "quotes" in payload:
                    filtered = [q for q in payload["quotes"] if q.get("symbol", "").upper() in wanted]
                    await ws.send_json({**payload, "quotes": filtered})
                else:
                    await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self.connections)
