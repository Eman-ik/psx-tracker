from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


class MarketDataProvider(Protocol):
    """Narrow interface every quote source implements. The frontend and the
    rest of the backend never know which concrete provider is behind this -
    that's what lets us start with the unofficial psxdata scraper and swap
    in a licensed vendor (e.g. Capital Stake) later without touching
    anything downstream of fetch_quotes()."""

    name: str

    def fetch_quotes(self, symbols: list[str]) -> list[dict[str, Any]]: ...


def _pick(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] not in (None, "", "nan"):
            return row[name]
    return None


@dataclass
class NormalizedQuote:
    symbol: str
    price: float | None
    change_pct: float | None
    change_points_derived: float | None
    change_1y_pct: float | None
    pe_ratio: float | None
    dividend_yield: float | None
    market_cap: float | None
    free_float: float | None
    volume_avg_30d: int | None
    currency: str
    source_timestamp: str | None
    fetched_at: str
    delayed: bool
    stale: bool


class PsxDataProvider:
    """Thin adapter around the psxdata package (psxdata.quote(symbol)).

    quote() returns a screener/fundamentals snapshot, not a tick-level
    trading quote. In particular, it has no source timestamp, absolute
    point change, or today's traded volume.

    IMPORTANT: psxdata is an unofficial, keyless scraper of PSX's public
    site. It documents ~15 minute local disk-cache refresh for "current"
    prices - this is an intraday-delayed source, not a broker feed. It also
    means it needs outbound network access to psx.com.pk at runtime; it
    will not work in network-sandboxed environments (see README).
    """

    name = "psxdata"

    def fetch_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        import pandas as pd
        import psxdata

        rows: list[dict[str, Any]] = []
        for symbol in symbols:
            df = psxdata.quote(symbol)
            if isinstance(df, pd.DataFrame) and not df.empty:
                row = df.iloc[0].to_dict()
                row["symbol"] = row.get("symbol") or symbol.upper()
                rows.append(row)
        return rows


class MockProvider:
    """Synthetic data generator for local development, demos, CI, and any
    environment (like a sandboxed container) that can't reach psx.com.pk.
    Produces a small random walk seeded per-symbol so numbers look plausible
    and move a little on every poll, without pretending to be real market
    data (see the 'delayed'/mock provider name surfaced in /api/v1/meta).
    """

    name = "mock"

    _base_prices = {
        "OGDC": 145.0,
        "PPL": 120.0,
        "HBL": 195.0,
        "ENGRO": 310.0,
        "LUCK": 780.0,
    }

    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def fetch_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for symbol in symbols:
            sym = symbol.upper()
            base = self._last.get(sym, self._base_prices.get(sym, 100.0))
            drift = base * random.uniform(-0.004, 0.004)
            price = max(0.5, round(base + drift, 2))
            self._last[sym] = price
            first_base = self._base_prices.get(sym, 100.0)
            change = round(price - first_base, 2)
            change_pct = round((change / first_base) * 100, 2) if first_base else 0.0
            rows.append(
                {
                    "symbol": sym,
                    "price": price,
                    "change_pct": change_pct,
                    "change_1y_pct": round(random.uniform(-20, 45), 2),
                    "pe_ratio": round(random.uniform(4, 18), 2),
                    "dividend_yield": round(random.uniform(0, 12), 2),
                    "market_cap": random.randint(25_000_000_000, 900_000_000_000),
                    "free_float": round(random.uniform(10, 55), 2),
                    "volume_avg_30d": random.randint(50_000, 2_500_000),
                }
            )
        return rows


def get_provider(name: str) -> MarketDataProvider:
    if name == "psxdata":
        return PsxDataProvider()
    if name == "mock":
        return MockProvider()
    raise ValueError(f"Unknown provider: {name!r} (expected 'psxdata' or 'mock')")


def normalize_quotes(raw_rows: list[dict[str, Any]], *, provider_name: str) -> list[NormalizedQuote]:
    now = datetime.now(timezone.utc).isoformat()
    result: list[NormalizedQuote] = []
    for row in raw_rows:
        symbol_val = _pick(row, "symbol")
        if symbol_val is None:
            continue
        symbol = str(symbol_val).upper()
        price = _pick(row, "price", "current", "close", "ldcp")
        change_pct = _pick(row, "change_pct")
        change_1y_pct = _pick(row, "change_1y_pct")
        pe_ratio = _pick(row, "pe_ratio")
        dividend_yield = _pick(row, "dividend_yield")
        market_cap = _pick(row, "market_cap")
        free_float = _pick(row, "free_float")
        volume_avg_30d = _pick(row, "volume_avg_30d")
        ts = _pick(row, "time", "timestamp", "last_updated", "date")

        price = _safe_float(price)
        change_pct = _safe_float(change_pct)
        change_1y_pct = _safe_float(change_1y_pct)
        pe_ratio = _safe_float(pe_ratio)
        dividend_yield = _safe_float(dividend_yield)
        market_cap = _safe_float(market_cap)
        free_float = _safe_float(free_float)
        volume_avg_30d = _safe_int(volume_avg_30d)

        # Data quality guards
        if price is not None and price < 0:
            price = None
        if volume_avg_30d is not None and volume_avg_30d < 0:
            volume_avg_30d = None

        # change_pct is source data, but the corresponding point move is
        # not. Reconstruct it from current price and percentage change:
        # previous = price / (1 + change_pct/100), change = price - previous.
        change_points_derived = _derive_point_change(price, change_pct)

        result.append(
            NormalizedQuote(
                symbol=symbol,
                price=price,
                change_pct=change_pct,
                change_points_derived=change_points_derived,
                change_1y_pct=change_1y_pct,
                pe_ratio=pe_ratio,
                dividend_yield=dividend_yield,
                market_cap=market_cap,
                free_float=free_float,
                volume_avg_30d=volume_avg_30d,
                currency="PKR",
                source_timestamp=str(ts) if ts is not None else None,
                fetched_at=now,
                # psxdata documents ~15 min cache refresh for "current" data;
                # the mock provider is obviously synthetic. Neither is a
                # licensed real-time feed, so both are marked delayed=True.
                delayed=True,
                stale=False,
            )
        )
    return result


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _derive_point_change(price: float | None, change_pct: float | None) -> float | None:
    if price is None or change_pct is None:
        return None
    denominator = 1 + (change_pct / 100)
    if denominator <= 0:
        return None
    return round(price - (price / denominator), 2)
