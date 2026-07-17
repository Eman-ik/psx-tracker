"""HTTP API for approximately 15-minute-delayed PSX quotes.

This service is intentionally independent of the daily SQLite/snapshot
pipeline. Run it with:

    uvicorn app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import math
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psxdata
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import QUOTE_TICKERS

REFRESH_INTERVAL_SECONDS = 15 * 60
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _cors_origins() -> list[str]:
    configured = os.getenv(
        "PSX_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="PSX Tracker API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _json_value(value: Any) -> Any:
    """Convert pandas/numpy values into strict JSON-compatible values."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = _json_value(data.get(key))
        if value is not None:
            return value
    return None


def _quote_row(raw_quote: Any) -> dict[str, Any]:
    if isinstance(raw_quote, pd.DataFrame):
        if raw_quote.empty:
            raise ValueError("Symbol was not found in the PSX screener")
        return raw_quote.iloc[0].to_dict()
    if isinstance(raw_quote, pd.Series):
        return raw_quote.to_dict()
    return dict(raw_quote)


def _today_row(symbol: str) -> dict[str, Any]:
    """Return today's OHLCV row, if PSX has published one."""
    today = date.today()
    daily = psxdata.stocks(symbol, start=today, end=today)
    if daily.empty:
        return {}
    return daily.iloc[-1].to_dict()


def fetch_quote(symbol: str, fetched_at: str) -> dict[str, Any]:
    """Fetch one symbol and expose a stable subset of psxdata's fields."""
    data = _quote_row(psxdata.quote(symbol))
    # quote() currently omits actual volume/high/low. Today's cached OHLCV row
    # fills those fields without coupling this service to the daily database.
    try:
        today_data = _today_row(symbol)
    except Exception:
        today_data = {}

    price = _first_value(data, "price", "current", "close")
    if price is None:
        price = _first_value(today_data, "close")
    previous_close = _first_value(data, "ldcp", "previous_close")
    change = _first_value(data, "change")
    change_percentage = _first_value(data, "change_pct", "change_percentage")

    if change is None and price is not None and previous_close is not None:
        change = price - previous_close
    if (
        change_percentage is None
        and change is not None
        and previous_close not in (None, 0)
    ):
        change_percentage = change / previous_close * 100
    if (
        change is None
        and price is not None
        and change_percentage is not None
        and change_percentage != -100
    ):
        # The screener exposes percentage change but not the absolute amount.
        # Derive an approximate two-decimal currency change from that value.
        change = round(price * change_percentage / (100 + change_percentage), 2)

    return {
        "symbol": symbol,
        "price": _json_value(price),
        "change": _json_value(change),
        "change_percentage": _json_value(change_percentage),
        "volume": _first_value(data, "volume") or _first_value(today_data, "volume"),
        "high": _first_value(data, "high") or _first_value(today_data, "high"),
        "low": _first_value(data, "low") or _first_value(today_data, "low"),
        # psxdata's screener does not guarantee an exchange timestamp, so make
        # the retrieval timestamp explicit rather than inventing one.
        "last_updated": _first_value(data, "timestamp", "last_updated", "date"),
        "fetched_at": fetched_at,
    }


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/quotes")
def get_quotes() -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    quotes: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for symbol in QUOTE_TICKERS:
        try:
            quotes.append(fetch_quote(symbol, fetched_at))
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})

    if not quotes:
        raise HTTPException(
            status_code=503,
            detail={"message": "No market data available", "errors": errors},
        )

    return {
        "quotes": quotes,
        "errors": errors,
        "fetched_at": fetched_at,
        "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
        "data_type": "approximately 15-minute delayed",
    }
