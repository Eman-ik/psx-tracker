"""
Exports the latest row per ticker (price + indicators + last 5 headlines)
to data/latest.json — a small, git-friendly snapshot.

Why this exists: the SQLite db is treated as ephemeral working storage
(gitignored, rebuilt each run). This JSON file is the actual durable
artifact — small enough to commit every day, diffable, and it's what
a future frontend would fetch instead of talking to SQLite directly.

    python export_snapshot.py
"""

import json
import datetime as dt

import pandas as pd

from config import TICKERS
from db import get_connection


def main():
    conn = get_connection()
    snapshot = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "tickers": {}}

    for symbol in TICKERS:
        price = pd.read_sql_query(
            "SELECT * FROM prices WHERE symbol=? ORDER BY date DESC LIMIT 1", conn, params=(symbol,)
        )
        ind = pd.read_sql_query(
            "SELECT * FROM indicators WHERE symbol=? ORDER BY date DESC LIMIT 1", conn, params=(symbol,)
        )
        news = pd.read_sql_query(
            "SELECT published, headline, source, link, sentiment_label, sentiment_score "
            "FROM news_sentiment WHERE symbol=? ORDER BY fetched_on DESC LIMIT 5",
            conn, params=(symbol,),
        )

        entry = {
            "price": price.drop(columns=["symbol"]).to_dict("records")[0] if not price.empty else None,
            "indicators": ind.drop(columns=["symbol"]).to_dict("records")[0] if not ind.empty else None,
            "recent_news": news.to_dict("records") if not news.empty else [],
        }
        snapshot["tickers"][symbol] = entry

    with open("data/latest.json", "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    print("Wrote data/latest.json")


if __name__ == "__main__":
    main()
