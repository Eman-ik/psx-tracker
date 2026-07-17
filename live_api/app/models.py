from __future__ import annotations

from pydantic import BaseModel


class Quote(BaseModel):
    symbol: str
    price: float | None = None
    change_pct: float | None = None
    change_points_derived: float | None = None
    change_1y_pct: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None
    free_float: float | None = None
    volume_avg_30d: int | None = None
    currency: str = "PKR"
    source_timestamp: str | None = None
    fetched_at: str
    delayed: bool = True
    stale: bool = False


class QuotesResponse(BaseModel):
    server_time: str
    quotes: list[Quote]
    delayed: bool = True
    provider: str


class MetaResponse(BaseModel):
    provider: str
    delayed: bool
    market_open: bool
    poll_seconds: int
    last_success: str | None
    last_error: str | None
    symbols: list[str]


class HealthResponse(BaseModel):
    ok: bool
    provider: str
    last_success: str | None
    last_error: str | None
    symbols: list[str]
