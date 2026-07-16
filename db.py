"""
SQLite schema + connection helper.
Using SQLite (not Postgres) on purpose: for 3 tickers with daily bars,
you'll have a few thousand rows total. A single file DB is genuinely
enough — don't reach for a hosted database until this is a bottleneck.
"""

import sqlite3
import os
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            symbol      TEXT NOT NULL,
            date        TEXT NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            volume      INTEGER,
            is_anomaly  INTEGER,
            PRIMARY KEY (symbol, date)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS indicators (
            symbol      TEXT NOT NULL,
            date        TEXT NOT NULL,
            rsi_14      REAL,
            macd        REAL,
            macd_signal REAL,
            macd_hist   REAL,
            sma_20      REAL,
            sma_50      REAL,
            bb_lower    REAL,
            bb_mid      REAL,
            bb_upper    REAL,
            PRIMARY KEY (symbol, date)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            symbol          TEXT NOT NULL,
            period          TEXT NOT NULL,   -- e.g. "2025-Q4" or "FY2025"
            revenue         REAL,
            net_profit      REAL,
            eps             REAL,
            source_url      TEXT,
            entered_on      TEXT,
            PRIMARY KEY (symbol, period)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS news_sentiment (
            symbol          TEXT NOT NULL,
            published       TEXT,
            headline        TEXT NOT NULL,
            source          TEXT,
            link            TEXT,
            sentiment_label TEXT,
            sentiment_score REAL,
            fetched_on      TEXT,
            PRIMARY KEY (symbol, headline)
        );
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
