from __future__ import annotations

import json
from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent
KARACHI_TZ = ZoneInfo("Asia/Karachi")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    # Which provider backs /api/v1/quotes. "psxdata" hits the real (public,
    # unofficial) scraper. "mock" generates synthetic quotes and is useful
    # for local dev, demos, or any sandboxed environment without outbound
    # access to psx.com.pk.
    provider: str = "mock"

    default_symbols: str = "OGDC,PPL,HBL,ENGRO,LUCK"
    poll_seconds: int = 60
    off_hours_poll_seconds: int = 300  # slower poll cadence outside market hours
    allowed_origins: str = "http://localhost:3000"

    public_read: bool = True
    admin_bearer_token: str = "replace-me"

    stale_after_seconds: int = 1200  # 20 minutes, per the plan's UI guidance

    @property
    def symbols_list(self) -> list[str]:
        return [s.strip().upper() for s in self.default_symbols.split(",") if s.strip()]

    @property
    def origins_list(self) -> list[str]:
        return [s.strip() for s in self.allowed_origins.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def _load_holidays() -> set[date]:
    """Loads the PSX holiday calendar. Currently ships 2026 only (sourced
    from psx.com.pk/psx/exchange/general/calendar-holidays); extend by
    dropping additional holidays_<year>.json files next to this module."""
    holidays: set[date] = set()
    for path in APP_DIR.glob("holidays_*.json"):
        try:
            payload = json.loads(path.read_text())
            for entry in payload.get("dates", []):
                holidays.add(date.fromisoformat(entry["date"]))
        except Exception:
            continue
    return holidays


def is_holiday(d: date) -> bool:
    return d in _load_holidays()


def is_market_open(now: datetime | None = None) -> bool:
    """Mirrors PSX's published trading hours:
    Mon-Thu 09:32-15:30, Fri 09:17-12:00 and 14:32-16:30, PKT.
    Excludes weekends and the holiday calendar. This governs the poller's
    cadence, not correctness of any single quote.
    """
    now = (now or datetime.now(KARACHI_TZ)).astimezone(KARACHI_TZ)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if is_holiday(now.date()):
        return False

    t = now.time()
    if now.weekday() == 4:  # Friday
        return (time(9, 17) <= t <= time(12, 0)) or (time(14, 32) <= t <= time(16, 30))
    return time(9, 32) <= t <= time(15, 30)
