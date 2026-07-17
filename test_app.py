import math
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

import app


class QuoteApiTests(unittest.TestCase):
    def test_dashboard_asset_exists(self):
        response = app.dashboard()

        self.assertTrue(app.STATIC_DIR.joinpath("index.html").is_file())
        self.assertEqual(response.media_type, "text/html")

    def test_fetch_quote_normalizes_dataframe_and_calculates_change(self):
        raw = pd.DataFrame(
            [{"symbol": "FFC", "price": 125.0, "ldcp": 120.0, "volume": 42_000}]
        )

        with patch("app.psxdata.quote", return_value=raw), patch(
            "app._today_row", return_value={}
        ):
            result = app.fetch_quote("FFC", "2026-07-16T12:00:00+00:00")

        self.assertEqual(result["price"], 125.0)
        self.assertEqual(result["change"], 5.0)
        self.assertAlmostEqual(result["change_percentage"], 4.1666667)
        self.assertEqual(result["volume"], 42_000)
        self.assertIsNone(result["last_updated"])

    def test_fetch_quote_converts_nan_to_none(self):
        raw = pd.DataFrame([{"symbol": "FFC", "price": 125.0, "high": math.nan}])

        with patch("app.psxdata.quote", return_value=raw), patch(
            "app._today_row", return_value={}
        ):
            result = app.fetch_quote("FFC", "now")

        self.assertIsNone(result["high"])

    def test_fetch_quote_supplements_ohlcv_and_derives_change(self):
        raw = pd.DataFrame([{"symbol": "FFC", "price": 125.0, "change_pct": 4.0}])
        today = {"high": 127.0, "low": 119.0, "volume": 42_000}

        with patch("app.psxdata.quote", return_value=raw), patch(
            "app._today_row", return_value=today
        ):
            result = app.fetch_quote("FFC", "now")

        self.assertEqual(result["change"], 4.81)
        self.assertEqual(result["high"], 127.0)
        self.assertEqual(result["low"], 119.0)
        self.assertEqual(result["volume"], 42_000)

    def test_endpoint_keeps_partial_successes(self):
        def fake_fetch(symbol, fetched_at):
            if symbol == "FFC":
                raise RuntimeError("upstream unavailable")
            return {"symbol": symbol, "price": 100, "fetched_at": fetched_at}

        with patch("app.fetch_quote", side_effect=fake_fetch):
            result = app.get_quotes()

        self.assertEqual(len(result["quotes"]), len(app.QUOTE_TICKERS) - 1)
        self.assertEqual(result["errors"][0]["symbol"], "FFC")
        self.assertEqual(result["refresh_interval_seconds"], 900)

    def test_endpoint_returns_503_when_every_symbol_fails(self):
        with patch("app.fetch_quote", side_effect=RuntimeError("offline")):
            with self.assertRaises(HTTPException) as raised:
                app.get_quotes()

        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
