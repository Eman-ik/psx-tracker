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
├── fundamentals.py      # manually maintained quarterly company results
├── view.py               # quick CLI to eyeball the latest numbers
├── export_snapshot.py     # dumps latest data to data/latest.json (git-friendly)
├── site/
│   └── index.html          # deployable static dashboard (no server required)
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
python fundamentals.py    # stores maintained quarterly fundamentals
python export_snapshot.py # rebuilds data/latest.json
python view.py            # print a quick summary of everything above
```

## Verification status

Live integrations were verified on July 17, 2026:

- ✅ `fetch_data.py` successfully fetched and upserted 1,122 historical
  OHLCV rows for each of FFC, FATIMA, and EFERT, covering January 3, 2022
  through July 16, 2026.
- ✅ `sentiment.py` successfully fetched and stored 15 Google News RSS
  headlines for each tracked company.
- ✅ The SQLite schema, upsert logic, `pandas-ta` calculations, sentiment
  keyword scorer, delayed quote API, and dashboard routes are tested.

`psxdata` reported a small number of OHLC/order anomalies in the upstream
history. The pipeline preserved its anomaly flags; inspect flagged records
before using the dataset for analysis.

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

## Delayed quote API

The daily workflow remains responsible for historical OHLCV, indicators,
sentiment, and `data/latest.json`. A separate FastAPI service in `app.py`
serves current screener quotes without writing to the database or repository.

Install and run it locally:

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Set `PSX_CORS_ORIGINS` to the comma-separated origins allowed to call the API
(for example, `https://example.com,https://www.example.com`). The included
`render.yaml` can deploy the service on Render; set that environment variable
in the Render dashboard before calling the API from a public website.

`GET /api/quotes` returns successful quotes, per-symbol errors, a UTC fetch
time, and a suggested 900-second refresh interval. Some values may be `null`
when the PSX screener does not publish that field. The frontend should label
the result **“PSX prices — approximately 15-minute delayed”** and poll it like:

The included responsive dashboard is available at the service root (`/`).
When running locally, open `http://localhost:8000/` (or whichever port was
passed to Uvicorn).

```js
const REFRESH_INTERVAL = 15 * 60 * 1000;

async function loadQuotes() {
  const response = await fetch("https://your-backend-domain.com/api/quotes");
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  const result = await response.json();
  renderQuotes(result.quotes);
  showLastUpdated(result.fetched_at);
}

loadQuotes().catch(showStaleDataWarning);
setInterval(() => loadQuotes().catch(showStaleDataWarning), REFRESH_INTERVAL);
```

`psxdata` being open source does not grant market-data redistribution rights.
Obtain written clarification or a suitable licence from PSX before deploying a
public or commercial site.

## Static dashboard

Open `site/index.html` directly in a browser. It reads the published
`data/latest.json` from this repository's `main` branch, so no local web server
is required. The same `site/` directory can be deployed with GitHub Pages,
Netlify, or Vercel.

## Automating the daily workflow (free, via GitHub Actions)

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
3. **Maintain fundamentals** — add each new quarter to `fundamentals.py`
   using the company's investor-relations filing as the source.
4. **Upgrade sentiment scoring** to FinBERT once the pipeline is stable
   (see the docstring at the top of `sentiment.py` — it's a ~5 line swap).
5. **Deploy the static dashboard** from `site/` once the snapshot looks right.

## Gitignore

Add this before pushing to GitHub — you don't want to commit the DB file
or a venv:

```
venv/
data/*.db
__pycache__/
*.pyc
```
