"""
Pulls historical + latest daily OHLCV for the tickers in config.py
and upserts them into the local SQLite database.

Run manually:
    python fetch_data.py

Run daily after market close (~3:30pm PKT) via cron / GitHub Actions —
see README.md for the free scheduling option.
"""

import datetime as dt
import sqlite3

import pandas as pd
import psxdata

from config import TICKERS, HISTORY_START
from db import get_connection, init_db


def fetch_symbol(symbol: str) -> pd.DataFrame:
    """Fetch full history for one symbol. psxdata caches historical
    data on disk forever, so re-running this is cheap after day one."""
    df = psxdata.stocks(symbol, start=HISTORY_START, end=dt.date.today())
    if df.empty:
        print(f"  ! No data returned for {symbol} (check ticker spelling)")
        return df
    df = df.reset_index() if df.index.name == "date" else df
    df["symbol"] = symbol
    # normalize date to plain ISO string for SQLite
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df[["symbol", "date", "open", "high", "low", "close", "volume", "is_anomaly"]]


def upsert_prices(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    # IMPORTANT: cast every value to a native Python type before binding.
    # numpy.int64 (unlike numpy.float64, which subclasses Python's float)
    # is NOT recognized by sqlite3 and gets silently stored as a raw byte
    # blob instead of an integer. Explicit int()/float() casts avoid this.
    rows = [
        (str(r.symbol), str(r.date), float(r.open), float(r.high), float(r.low),
         float(r.close), int(r.volume), int(r.is_anomaly))
        for r in df.itertuples(index=False)
    ]
    conn.executemany(
        """
        INSERT INTO prices (symbol, date, open, high, low, close, volume, is_anomaly)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, date) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume, is_anomaly=excluded.is_anomaly;
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def main():
    init_db()
    conn = get_connection()
    for symbol in TICKERS:
        print(f"Fetching {symbol}...")
        df = fetch_symbol(symbol)
        n = upsert_prices(conn, df)
        print(f"  -> upserted {n} rows")
    conn.close()


if __name__ == "__main__":
    main()
