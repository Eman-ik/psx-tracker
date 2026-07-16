# PSX Tracker — FFC / FATIMA / EFERT starter

A minimal, free-tier pipeline for fundamental/technical/sentiment tracking
of Fauji Fertilizer (FFC), Fatima Fertilizer (FATIMA), and Engro Fertilizers
(EFERT) on the Pakistan Stock Exchange.

## What's here

```
psx-tracker/
├── config.py        # ticker list — edit this to add/remove symbols
├── db.py             # SQLite schema (prices, indicators, fundamentals, news_sentiment)
├── fetch_data.py      # pulls OHLCV from PSX via the `psxdata` library
├── indicators.py       # RSI/MACD/SMA/Bollinger Bands via pandas-ta
├── sentiment.py         # news headlines via Google News RSS + basic scoring
├── view.py               # quick CLI to eyeball the latest numbers
├── export_snapshot.py     # dumps latest data to data/latest.json (git-friendly)
├── .github/workflows/
│   └── update.yml           # daily automation — see "Automating it" below
├── requirements.txt
└── data/
    ├── psx_tracker.db         # SQLite db (gitignored — rebuilt each run)
    └── latest.json             # small snapshot, safe to commit
```

## Setup

```bash
cd psx-tracker
python3 -m venv venv && source venv/bin/activate     # optional but recommended
pip install -r requirements.txt
python db.py              # creates the empty SQLite database
python fetch_data.py      # pulls price history for FFC, FATIMA, EFERT
python indicators.py      # computes RSI/MACD/SMA/Bollinger Bands
python sentiment.py       # pulls recent news + scores it
python view.py            # print a quick summary of everything above
```

## What's tested vs. what isn't

I built and ran this in a sandboxed environment that can only reach
PyPI/GitHub — **not** PSX's or Google's servers. So:

- ✅ **Tested and verified working:** the SQLite schema, the upsert logic,
  the `pandas-ta` indicator calculations (against synthetic OHLCV data
  matching PSX's exact schema), and the sentiment keyword scorer.
- ⚠️ **Not tested live:** `fetch_data.py`'s actual call to PSX via
  `psxdata`, and `sentiment.py`'s actual call to Google News RSS. These
  use documented, real APIs (I inspected `psxdata`'s live source to get
  the exact function signatures and column names right), but you should
  run `python fetch_data.py` yourself first and check the row counts
  make sense before building anything on top.

If `psxdata` breaks (it's alpha software, `0.1.0a5` — PSX also changes
its HTML periodically, which is what breaks every scraper eventually):
fall back to `psx-data-reader` on PyPI, or scrape `dps.psx.com.pk`
directly — same general approach, different library call in `fetch_data.py`.

## Legal note

PSX's terms restrict **commercial redistribution** of their market data
without a license (contact marketdatarequest@psx.com.pk). This is fine
for personal use / learning / a private tool. If you plan to make the
site public-facing or monetize it, that's the point to reach out to PSX
first.

## Automating it (free, via GitHub Actions)

`.github/workflows/update.yml` runs the full pipeline every weekday at
4:00pm PKT and commits `data/latest.json` back to the repo — a small,
diffable snapshot a future frontend can fetch directly from GitHub
(e.g. `raw.githubusercontent.com/you/repo/main/data/latest.json`), no
server required.

The SQLite db itself is *not* committed — it's rebuilt from scratch
each run. For 3 tickers this is cheap. If you outgrow that (many more
tickers, or you want the db's full history to persist across runs),
switch to caching `data/psx_tracker.db` with `actions/cache` instead
of rebuilding it, or move to Supabase's free Postgres tier.

**To turn it on:**
1. Push this repo to GitHub.
2. Go to the **Actions** tab → find "Update PSX data" → click
   **Run workflow** to trigger it manually and confirm it works before
   trusting the schedule.
3. Check the commit it makes — `data/latest.json` should have real
   numbers, not nulls.

## Next steps, roughly in order

1. **Get `fetch_data.py` running for real** and confirm the row counts
   in `data/psx_tracker.db` look right (`python view.py`).
2. **Turn on the GitHub Actions workflow** above.
3. **Fundamentals table** — for just 3 companies, hand-enter quarterly
   EPS/revenue/net profit into the `fundamentals` table from each
   company's own investor-relations PDF. Not worth automating at this scale.
4. **Upgrade sentiment scoring** to FinBERT once the pipeline is stable
   (see the docstring at the top of `sentiment.py` — it's a ~5 line swap).
5. **Build the frontend last**, once you trust the numbers underneath it —
   have it read `data/latest.json` straight from GitHub rather than
   standing up a backend.

## Gitignore

Add this before pushing to GitHub — you don't want to commit the DB file
or a venv:

```
venv/
data/*.db
__pycache__/
*.pyc
```
