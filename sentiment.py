"""
Pulls recent news headlines for each tracked company via Google News RSS
(free, no API key) and scores them.

Run manually:
    python sentiment.py

--- Two scoring modes ---

1) DEFAULT (works out of the box, zero extra installs):
   A small finance-flavored keyword scorer. It's crude — a headline
   with "profit surges" scores positive, "loss widens" scores negative —
   but it's transparent, free, and good enough to build the pipeline
   and UI around before you invest in something heavier.

2) UPGRADE (recommended once the pipeline works end to end):
   Swap in FinBERT, a finance-tuned sentiment model, via Hugging Face
   `transformers`. It's still free and runs locally (CPU is fine for
   headline-length text), but the first run downloads ~440MB of model
   weights, so do this on your own machine with normal internet access:

       pip install transformers torch
       from transformers import pipeline
       finbert = pipeline("sentiment-analysis", model="ProsusAI/finbert")
       finbert("Fauji Fertilizer posts record quarterly profit")
       # -> [{'label': 'positive', 'score': 0.97}]

   Then replace score_headline() below with a call to `finbert(text)`.

Note: this script was written and logic-tested in a sandboxed environment
that can't reach news.google.com — test the live RSS fetch on your own
machine before relying on it.
"""

import datetime as dt
import sqlite3
from urllib.parse import quote_plus

import feedparser

from config import TICKERS, TICKER_NAMES
from db import get_connection

POSITIVE_WORDS = {
    "profit", "surge", "surges", "growth", "record", "rally", "gain", "gains",
    "rise", "rises", "beat", "beats", "strong", "upgrade", "expansion",
    "dividend", "bullish", "outperform", "boost", "boosts", "higher",
}
NEGATIVE_WORDS = {
    "loss", "losses", "decline", "declines", "fall", "falls", "drop", "drops",
    "down", "weak", "downgrade", "cut", "cuts", "shortage", "crisis",
    "bearish", "underperform", "default", "fine", "penalty",
    "slide", "slides", "sliding", "slid", "tumble", "tumbles", "plunge",
    "plunges", "lower",
}


def score_headline(text: str) -> tuple[str, float]:
    """Crude keyword scorer. Returns (label, score in [-1, 1]).
    label is one of: positive, negative, neutral (no signal), mixed
    (both positive and negative signals present — genuinely ambiguous,
    e.g. "delivers strong profit, yet sends PSX sliding"). Score is
    net polarity either way. Replace with FinBERT (see module docstring)
    when this stops being good enough."""
    words = {w.strip(".,!?").lower() for w in text.split()}
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)

    if pos == 0 and neg == 0:
        return "neutral", 0.0
    if pos > 0 and neg > 0:
        return "mixed", round((pos - neg) / (pos + neg), 3)

    score = (pos - neg) / (pos + neg)
    label = "positive" if score > 0 else "negative"
    return label, round(score, 3)


def fetch_headlines(company_name: str, max_items: int = 15):
    query = quote_plus(f'"{company_name}" PSX')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-PK&gl=PK&ceid=PK:en"
    feed = feedparser.parse(url)
    return feed.entries[:max_items]


def upsert_headlines(conn: sqlite3.Connection, symbol: str, entries) -> int:
    rows = []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for e in entries:
        title = e.get("title", "").strip()
        if not title:
            continue
        label, score = score_headline(title)
        rows.append((
            symbol,
            e.get("published", ""),
            title,
            e.get("source", {}).get("title", "") if hasattr(e.get("source"), "get") else "",
            e.get("link", ""),
            label,
            score,
            now,
        ))
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO news_sentiment
            (symbol, published, headline, source, link, sentiment_label, sentiment_score, fetched_on)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, headline) DO UPDATE SET
            sentiment_label=excluded.sentiment_label,
            sentiment_score=excluded.sentiment_score,
            fetched_on=excluded.fetched_on;
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def main():
    conn = get_connection()
    for symbol in TICKERS:
        name = TICKER_NAMES.get(symbol, symbol)
        print(f"Fetching news for {symbol} ({name})...")
        entries = fetch_headlines(name)
        n = upsert_headlines(conn, symbol, entries)
        print(f"  -> stored {n} headlines")
    conn.close()


if __name__ == "__main__":
    main()
