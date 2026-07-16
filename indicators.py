"""
Computes technical indicators from the prices table and stores results
in the indicators table. Run this after fetch_data.py.

    python indicators.py

Indicators included (deliberately a small, standard starter set —
add more via pandas-ta once these are working end to end):
  - RSI(14)
  - MACD(12,26,9)
  - SMA(20), SMA(50)
  - Bollinger Bands(20, 2 std)
"""

import sqlite3

import pandas as pd
import pandas_ta as ta

from config import TICKERS
from db import get_connection


def load_prices(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM prices WHERE symbol = ? ORDER BY date",
        conn,
        params=(symbol,),
    )
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.sma(length=20, append=True)
    df.ta.sma(length=50, append=True)
    df.ta.bbands(length=20, std=2, append=True)

    out = pd.DataFrame(index=df.index)
    out["rsi_14"] = df.get("RSI_14")
    out["macd"] = df.get("MACD_12_26_9")
    out["macd_signal"] = df.get("MACDs_12_26_9")
    out["macd_hist"] = df.get("MACDh_12_26_9")
    out["sma_20"] = df.get("SMA_20")
    out["sma_50"] = df.get("SMA_50")
    out["bb_lower"] = df.get("BBL_20_2.0_2.0")
    out["bb_mid"] = df.get("BBM_20_2.0_2.0")
    out["bb_upper"] = df.get("BBU_20_2.0_2.0")
    return out.reset_index()


def upsert_indicators(conn: sqlite3.Connection, symbol: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df = df.where(pd.notnull(df), None)  # NaN -> NULL for early rows before indicators warm up
    rows = [
        (symbol, r.date, r.rsi_14, r.macd, r.macd_signal, r.macd_hist,
         r.sma_20, r.sma_50, r.bb_lower, r.bb_mid, r.bb_upper)
        for r in df.itertuples(index=False)
    ]
    conn.executemany(
        """
        INSERT INTO indicators
            (symbol, date, rsi_14, macd, macd_signal, macd_hist, sma_20, sma_50, bb_lower, bb_mid, bb_upper)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, date) DO UPDATE SET
            rsi_14=excluded.rsi_14, macd=excluded.macd, macd_signal=excluded.macd_signal,
            macd_hist=excluded.macd_hist, sma_20=excluded.sma_20, sma_50=excluded.sma_50,
            bb_lower=excluded.bb_lower, bb_mid=excluded.bb_mid, bb_upper=excluded.bb_upper;
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def main():
    conn = get_connection()
    for symbol in TICKERS:
        prices = load_prices(conn, symbol)
        if prices.empty:
            print(f"{symbol}: no price data yet — run fetch_data.py first.")
            continue
        ind = compute_indicators(prices)
        n = upsert_indicators(conn, symbol, ind)
        print(f"{symbol}: wrote {n} indicator rows")
    conn.close()


if __name__ == "__main__":
    main()
