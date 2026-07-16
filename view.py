"""
Quick sanity-check CLI: prints the latest price + indicators + recent
sentiment for each tracked ticker. Not a UI — just a fast way to eyeball
that the pipeline is producing sane numbers before you build a frontend.

    python view.py
"""

import pandas as pd

from config import TICKERS
from db import get_connection


def main():
    conn = get_connection()
    for symbol in TICKERS:
        print(f"\n{'=' * 50}\n{symbol}\n{'=' * 50}")

        latest_price = pd.read_sql_query(
            "SELECT * FROM prices WHERE symbol=? ORDER BY date DESC LIMIT 1", conn, params=(symbol,)
        )
        latest_ind = pd.read_sql_query(
            "SELECT * FROM indicators WHERE symbol=? ORDER BY date DESC LIMIT 1", conn, params=(symbol,)
        )
        recent_news = pd.read_sql_query(
            "SELECT published, headline, sentiment_label FROM news_sentiment "
            "WHERE symbol=? ORDER BY fetched_on DESC LIMIT 5",
            conn, params=(symbol,),
        )

        if latest_price.empty:
            print("No price data — run: python fetch_data.py")
            continue
        print(latest_price[["date", "close", "volume"]].to_string(index=False))

        if not latest_ind.empty:
            print("\nIndicators:")
            print(latest_ind.drop(columns=["symbol"]).to_string(index=False))
        else:
            print("\nNo indicators yet — run: python indicators.py")

        if not recent_news.empty:
            print("\nRecent headlines:")
            for _, row in recent_news.iterrows():
                print(f"  [{row.sentiment_label:8s}] {row.headline}")
        else:
            print("\nNo news yet — run: python sentiment.py")

    conn.close()


if __name__ == "__main__":
    main()
