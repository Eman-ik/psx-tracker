from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import HealthResponse, MetaResponse, QuotesResponse
from .providers import get_provider, normalize_quotes
from .settings import get_settings, is_market_open
from .ws import WebSocketHub

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("psx-live-api")

settings = get_settings()
provider = get_provider(settings.provider)
hub = WebSocketHub()
bearer = HTTPBearer(auto_error=False)

LATEST: dict[str, dict] = {}
LAST_SUCCESS: str | None = None
LAST_ERROR: str | None = None
_refresh_task: asyncio.Task | None = None
_refresh_lock = asyncio.Lock()


async def refresh_quotes(symbols: list[str]) -> None:
    """Fetches quotes from the active provider, normalizes them, keeps the
    last-good value per symbol (a temporary empty/partial response never
    blanks the cache), and pushes the update to WebSocket subscribers."""
    global LAST_SUCCESS, LAST_ERROR
    async with _refresh_lock:
        try:
            raw = await asyncio.to_thread(provider.fetch_quotes, symbols)
            normalized = normalize_quotes(raw, provider_name=provider.name)
            for q in normalized:
                LATEST[q.symbol] = q.__dict__
            LAST_SUCCESS = datetime.now(timezone.utc).isoformat()
            LAST_ERROR = None
            await hub.broadcast(
                {
                    "type": "quotes",
                    "server_time": LAST_SUCCESS,
                    "provider": provider.name,
                    "quotes": list(LATEST.values()),
                }
            )
        except Exception as exc:  # keep serving last-good cache on any provider failure
            LAST_ERROR = f"{type(exc).__name__}: {exc}"
            logger.warning("quote refresh failed: %s", LAST_ERROR)


async def poll_loop() -> None:
    while True:
        open_now = is_market_open()
        if open_now or settings.app_env != "production":
            await refresh_quotes(settings.symbols_list)
            await asyncio.sleep(settings.poll_seconds)
        else:
            # Outside trading hours / holidays, poll far less often instead
            # of hammering the source or spinning the loop for nothing.
            await asyncio.sleep(settings.off_hours_poll_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _refresh_task
    await refresh_quotes(settings.symbols_list)  # warm the cache before serving traffic
    _refresh_task = asyncio.create_task(poll_loop())
    yield
    if _refresh_task:
        _refresh_task.cancel()


app = FastAPI(title="psx-tracker live API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _is_stale() -> bool:
    if not LAST_SUCCESS:
        return True
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(LAST_SUCCESS)).total_seconds()
    return age > settings.stale_after_seconds


def _resolve_symbols(symbols: str | None) -> list[str]:
    return [s.strip().upper() for s in symbols.split(",")] if symbols else settings.symbols_list


@app.get("/healthz", response_model=HealthResponse)
async def healthz():
    return HealthResponse(
        ok=LAST_ERROR is None or bool(LATEST),
        provider=provider.name,
        last_success=LAST_SUCCESS,
        last_error=LAST_ERROR,
        symbols=settings.symbols_list,
    )


@app.get("/api/v1/meta", response_model=MetaResponse)
async def get_meta():
    return MetaResponse(
        provider=provider.name,
        delayed=True,
        market_open=is_market_open(),
        poll_seconds=settings.poll_seconds,
        last_success=LAST_SUCCESS,
        last_error=LAST_ERROR,
        symbols=settings.symbols_list,
    )


@app.get("/api/v1/quotes", response_model=QuotesResponse)
async def get_quotes(symbols: str | None = Query(default=None)):
    chosen = _resolve_symbols(symbols)
    missing = [s for s in chosen if s not in LATEST]
    if missing:
        await refresh_quotes(chosen)
    stale = _is_stale()
    quotes = []
    for s in chosen:
        if s in LATEST:
            q = dict(LATEST[s])
            q["stale"] = stale
            quotes.append(q)
    return QuotesResponse(
        server_time=datetime.now(timezone.utc).isoformat(),
        quotes=quotes,
        delayed=True,
        provider=provider.name,
    )


@app.post("/admin/refresh")
async def admin_refresh(creds: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not creds or creds.credentials != settings.admin_bearer_token or settings.admin_bearer_token == "replace-me":
        raise HTTPException(status_code=401, detail="Invalid or missing admin bearer token")
    await refresh_quotes(settings.symbols_list)
    return {"ok": True, "last_success": LAST_SUCCESS, "connections": hub.connection_count}


@app.websocket("/ws/quotes")
async def quotes_ws(ws: WebSocket, symbols: str | None = None):
    selected = [s.strip().upper() for s in symbols.split(",")] if symbols else []
    await hub.connect(ws, symbols=selected)
    try:
        await ws.send_json(
            {
                "type": "snapshot",
                "server_time": datetime.now(timezone.utc).isoformat(),
                "provider": provider.name,
                "quotes": list(LATEST.values()),
            }
        )
        while True:
            await ws.receive_text()  # heartbeat/ping from client; also detects disconnects
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)


@app.get("/sse/quotes")
async def quotes_sse(symbols: str | None = None):
    chosen = _resolve_symbols(symbols)

    async def event_stream():
        last_sent = None
        while True:
            snapshot = {s: LATEST[s] for s in chosen if s in LATEST}
            payload = json.dumps(
                {
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "provider": provider.name,
                    "quotes": list(snapshot.values()),
                }
            )
            if payload != last_sent:
                yield f"data: {payload}\n\n"
                last_sent = payload
            await asyncio.sleep(settings.poll_seconds)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
