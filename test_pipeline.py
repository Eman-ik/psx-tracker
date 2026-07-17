import sqlite3
import unittest

import numpy as np
import pandas as pd

from fetch_data import upsert_prices


class PricePipelineTests(unittest.TestCase):
    def test_numpy_volume_is_stored_as_sqlite_integer(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE prices (
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                is_anomaly INTEGER,
                PRIMARY KEY (symbol, date)
            )
            """
        )
        frame = pd.DataFrame(
            [
                {
                    "symbol": "FFC",
                    "date": "2026-07-16",
                    "open": 548.0,
                    "high": 555.0,
                    "low": 547.2,
                    "close": 551.28,
                    "volume": np.int64(1_872_699),
                    "is_anomaly": np.int64(0),
                }
            ]
        )

        upsert_prices(connection, frame)
        volume, storage_type = connection.execute(
            "SELECT volume, typeof(volume) FROM prices"
        ).fetchone()
        connection.close()

        self.assertEqual(volume, 1_872_699)
        self.assertEqual(storage_type, "integer")


if __name__ == "__main__":
    unittest.main()
