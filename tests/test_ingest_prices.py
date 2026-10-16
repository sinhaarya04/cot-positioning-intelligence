import pandas as pd
import pytest
import requests
from src.ingest_prices import parse_eia_records, parse_futures_prices, fetch_eia_records, ingest_all


def test_inventory_missing_values_and_first_change_are_unknown():
    rows = [{"period": "2024-01-19", "value": "130"}, {"period": "2024-01-05", "value": "100"},
            {"period": "2024-01-12", "value": None}, {"period": "2024-01-26", "value": "135"}]
    result = parse_eia_records(rows, "CRUDE_OIL", "test")
    assert pd.isna(result.inventory_level.iloc[1])
    assert result.weekly_change.iloc[:3].isna().all()
    assert result.weekly_change.iloc[3] == 5
    assert result.release_quality.eq("unknown").all()


def test_inventory_change_does_not_cross_missing_week():
    result = parse_eia_records([{"period": "2024-01-05", "value": "100"},
                                {"period": "2024-01-19", "value": "130"}], "CRUDE_OIL", "test")
    assert result.weekly_change.isna().all()


def test_daily_prices_keep_dates_and_mark_unknown_execution_time():
    frame = pd.DataFrame({"Close": [100, 110], "Volume": [None, 10]}, index=pd.to_datetime(["2024-01-04", "2024-01-05"]))
    result = parse_futures_prices(frame, "GOLD")
    assert result.price_date.astype(str).tolist() == ["2024-01-04", "2024-01-05"]
    assert result.price_at.isna().all()
    assert result.price_kind.eq("daily_close_proxy").all()
    assert pd.isna(result.volume.iloc[0])


def test_eia_pagination_checks_total_and_does_not_repeat(monkeypatch):
    offsets = []
    class Response:
        def __init__(self, rows): self.rows = rows
        def raise_for_status(self): pass
        def json(self): return {"response": {"total": "3", "data": self.rows}}
    def get(url, params, timeout):
        offsets.append(params["offset"])
        rows = [{"period": f"2024-01-{day:02d}", "value": "1"} for day in [5, 12, 19]]
        return Response(rows[params["offset"]:params["offset"] + params["length"]])
    monkeypatch.setattr(requests, "get", get)
    assert len(fetch_eia_records("test", "dummy", page_size=2)) == 3
    assert offsets == [0, 2]


def test_eia_network_errors_do_not_expose_key(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.HTTPError("url?api_key=not-a-real-key")
    monkeypatch.setattr(requests, "get", fail)
    with pytest.raises(RuntimeError) as caught:
        fetch_eia_records("test", "not-a-real-key")
    assert "not-a-real-key" not in str(caught.value)


def test_no_embedded_key_fallback():
    with pytest.raises(ValueError, match="EIA_API_KEY"):
        ingest_all()


def test_short_daily_refresh_preserves_history_and_removes_only_legacy():
    from src import db
    db.init_schema()
    db.write_frame("futures_prices", pd.DataFrame([
        {"price_date": "2024-01-01", "market": "GOLD", "close_price": 90, "price_kind": "legacy_unknown"},
        {"price_date": "2024-01-02", "market": "GOLD", "close_price": 100, "price_kind": "daily_close_proxy"},
    ]))
    daily = parse_futures_prices(pd.DataFrame({"Close": [110]}, index=pd.to_datetime(["2024-01-03"])), "GOLD")
    db.write_frame("futures_prices", daily)
    with db.get_conn() as conn:
        assert conn.execute("SELECT close_price FROM futures_prices ORDER BY price_date").fetchall() == [(100,), (110,)]


def test_daily_refresh_cannot_overwrite_contract_prices():
    from src import db
    db.init_schema()
    db.write_frame("futures_prices", pd.DataFrame([
        {"price_date": "2024-01-02", "market": "GOLD", "close_price": 100, "price_kind": "contract_settlement"},
    ]))
    daily = parse_futures_prices(pd.DataFrame({"Close": [110]}, index=pd.to_datetime(["2024-01-03"])), "GOLD")
    with pytest.raises(ValueError, match="contract"):
        db.write_frame("futures_prices", daily)
    with db.get_conn() as conn:
        assert conn.execute("SELECT close_price FROM futures_prices").fetchall() == [(100,)]
