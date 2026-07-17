"""
Manual fundamentals entry for the tracked tickers. For 3 companies this
isn't worth automating/scraping — just edit the FUNDAMENTALS dict below
each time a new quarterly report comes out, then run this file.

    python fundamentals.py

Where to find the numbers: each company's own investor-relations page
publishes quarterly reports as PDFs (revenue, net profit, and EPS are
usually on the first page of the income statement / in the press release
summary). Use the company's own filing as the source, not a news
article's summary of it.

Period format: use "YYYY-QN" for quarters (e.g. "2025-Q4") or
"FY-YYYY" for full-year figures. Whatever you use, be consistent —
it's how rows get grouped/sorted later.

Units: pick one and stay consistent across all entries (e.g. PKR
millions). Note which one you used in the `revenue`/`net_profit`
comments below so you don't mix units six months from now.
"""

import datetime as dt

from db import get_connection, init_db

# ---------------------------------------------------------------------
# EDIT THIS. Add a new period under a ticker each time you have fresh
# numbers. revenue and net_profit are in PKR millions — keep it that way.
# ---------------------------------------------------------------------
FUNDAMENTALS = {
    "FFC": {
        # "2025-Q4": {
        #     "revenue": 0.0,
        #     "net_profit": 0.0,
        #     "eps": 0.0,
        #     "source_url": "https://www.fauji.com.pk/...",
        # },
    },
    "FATIMA": {
        # "2025-Q4": {"revenue": 0.0, "net_profit": 0.0, "eps": 0.0, "source_url": ""},
    },
    "EFERT": {
        # "2025-Q4": {"revenue": 0.0, "net_profit": 0.0, "eps": 0.0, "source_url": ""},
    },
}
# ---------------------------------------------------------------------


def main():
    init_db()
    conn = get_connection()
    today = dt.date.today().isoformat()

    total = 0
    for symbol, periods in FUNDAMENTALS.items():
        for period, vals in periods.items():
            conn.execute(
                """
                INSERT INTO fundamentals (symbol, period, revenue, net_profit, eps, source_url, entered_on)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, period) DO UPDATE SET
                    revenue=excluded.revenue, net_profit=excluded.net_profit,
                    eps=excluded.eps, source_url=excluded.source_url, entered_on=excluded.entered_on;
                """,
                (symbol, period, vals.get("revenue"), vals.get("net_profit"),
                 vals.get("eps"), vals.get("source_url", ""), today),
            )
            total += 1
            print(f"{symbol} {period}: revenue={vals.get('revenue')} "
                  f"net_profit={vals.get('net_profit')} eps={vals.get('eps')}")

    conn.commit()
    conn.close()

    if total == 0:
        print("\nNo entries found — the FUNDAMENTALS dict above is still empty/commented out.")
        print("Add at least one period per ticker, then re-run this script.")
    else:
        print(f"\nWrote {total} fundamentals row(s). Now run: python export_snapshot.py")


if __name__ == "__main__":
    main()
