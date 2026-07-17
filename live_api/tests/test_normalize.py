from live_api.app.providers import MockProvider, normalize_quotes


def test_normalize_basic_row():
    raw = [
        {
            "symbol": "ogdc",
            "price": "145.30",
            "change_pct": "0.76",
            "change_1y_pct": "14.20",
            "pe_ratio": "7.85",
            "dividend_yield": "6.40",
            "market_cap": "625000000000",
            "free_float": "15.00",
            "volume_avg_30d": "1234567",
        }
    ]
    result = normalize_quotes(raw, provider_name="psxdata")
    assert len(result) == 1
    q = result[0]
    assert q.symbol == "OGDC"
    assert q.price == 145.30
    assert q.change_pct == 0.76
    assert q.change_points_derived == 1.10
    assert q.change_1y_pct == 14.20
    assert q.pe_ratio == 7.85
    assert q.dividend_yield == 6.40
    assert q.market_cap == 625000000000
    assert q.free_float == 15.00
    assert q.volume_avg_30d == 1234567
    assert q.source_timestamp is None
    assert q.currency == "PKR"
    assert q.delayed is True
    assert q.stale is False


def test_normalize_uses_observed_psxdata_column_names():
    raw = [{"symbol": "PPL", "price": "120.5", "change_pct": "-0.4", "volume_avg_30d": "500"}]
    result = normalize_quotes(raw, provider_name="psxdata")
    assert result[0].price == 120.5
    assert result[0].change_points_derived == -0.48
    assert result[0].volume_avg_30d == 500


def test_normalize_drops_bad_price_and_average_volume():
    raw = [{"symbol": "HBL", "price": "-5", "volume_avg_30d": "-100"}]
    result = normalize_quotes(raw, provider_name="psxdata")
    assert result[0].price is None
    assert result[0].volume_avg_30d is None


def test_normalize_handles_missing_and_garbage_values():
    raw = [{"symbol": "LUCK", "price": "nan", "change_pct": None, "volume_avg_30d": "not-a-number"}]
    result = normalize_quotes(raw, provider_name="psxdata")
    q = result[0]
    assert q.price is None
    assert q.change_points_derived is None
    assert q.volume_avg_30d is None


def test_derived_change_rejects_impossible_minus_100_percent():
    result = normalize_quotes(
        [{"symbol": "ENGRO", "price": "10", "change_pct": "-100"}],
        provider_name="psxdata",
    )
    assert result[0].change_points_derived is None


def test_normalize_skips_rows_without_symbol():
    raw = [{"price": "100"}, {"symbol": "ENGRO", "price": "300"}]
    result = normalize_quotes(raw, provider_name="psxdata")
    assert len(result) == 1
    assert result[0].symbol == "ENGRO"


def test_mock_provider_returns_rows_for_all_symbols():
    provider = MockProvider()
    rows = provider.fetch_quotes(["OGDC", "PPL"])
    assert {r["symbol"] for r in rows} == {"OGDC", "PPL"}
    for row in rows:
        assert row["price"] > 0


def test_mock_provider_output_normalizes_cleanly():
    provider = MockProvider()
    rows = provider.fetch_quotes(["HBL"])
    normalized = normalize_quotes(rows, provider_name="mock")
    assert len(normalized) == 1
    assert normalized[0].symbol == "HBL"
    assert normalized[0].price > 0
