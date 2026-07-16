"""
Single place to configure which PSX symbols this project tracks.
Add or remove tickers here — everything else reads from this list.
"""

# PSX ticker symbols (exact case matters — psxdata expects uppercase).
TICKERS = ["FFC", "FATIMA", "EFERT"]

# Map tickers to full company names — used for news search queries in sentiment.py.
TICKER_NAMES = {
    "FFC": "Fauji Fertilizer Company",
    "FATIMA": "Fatima Fertilizer",
    "EFERT": "Engro Fertilizers",
}

DB_PATH = "data/psx_tracker.db"

# How far back to backfill on first run.
HISTORY_START = "2022-01-01"
