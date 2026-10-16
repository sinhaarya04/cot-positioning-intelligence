import json
import pandas as pd
import pytest
from src import db
from src.availability import attach_release_metadata, load_release_calendar, apply_calendar
from src.provenance import save_snapshot


def test_failed_replace_rolls_back_existing_rows():
    db.init_schema()
    row = {"price_date": "2024-01-02", "market": "GOLD", "close_price": 2000.0}
    db.write_frame("futures_prices", pd.DataFrame([row]))
    with pytest.raises(Exception):
        db.write_frame("futures_prices", pd.DataFrame([{**row, "close_price": "invalid"}]), mode="replace")
    with db.get_conn() as conn:
        assert conn.execute("SELECT close_price FROM futures_prices").fetchone()[0] == 2000


def test_empty_replace_and_duplicate_keys_cannot_erase_data():
    db.init_schema()
    frame = pd.DataFrame([{"price_date": "2024-01-02", "market": "GOLD", "close_price": 2000}])
    db.write_frame("futures_prices", frame)
    assert db.write_frame("futures_prices", pd.DataFrame(), mode="replace") == 0
    with pytest.raises(ValueError, match="duplicate"):
        db.write_frame("futures_prices", pd.concat([frame, frame]))
    with db.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM futures_prices").fetchone()[0] == 1


def test_additive_migration_preserves_old_data_as_unknown():
    with db.get_conn() as conn:
        conn.execute("CREATE TABLE futures_prices (price_date DATE, market VARCHAR, close_price DOUBLE, volume BIGINT)")
        conn.execute("INSERT INTO futures_prices VALUES ('2020-01-01', 'GOLD', 1500, 1)")
    db.init_schema()
    db.init_schema()
    with db.get_conn() as conn:
        assert conn.execute("SELECT close_price,price_kind FROM futures_prices").fetchone() == (1500, "legacy_unknown")


def calendar(tmp_path, release="2024-01-05T15:30:00-05:00", dataset="legacy"):
    path = tmp_path / "calendar.csv"
    pd.DataFrame([{"dataset": dataset, "market": "*", "report_date": "2024-01-02",
                   "release_at": release, "source": "https://www.cftc.gov/example"}]).to_csv(path, index=False)
    return path


def test_calendar_unknown_and_verified_are_distinct(tmp_path):
    frame = pd.DataFrame([{"market": "GOLD", "report_date": "2024-01-02"},
                          {"market": "GOLD", "report_date": "2024-01-09"}])
    attached = attach_release_metadata(frame, "legacy", calendar_path=calendar(tmp_path))
    assert attached.release_quality.tolist() == ["verified", "unknown"]
    assert attached.release_at.iloc[0] == pd.Timestamp("2024-01-05T20:30:00Z")
    assert pd.isna(attached.release_at.iloc[1])
    assert attached.vintage.eq("latest").all()


@pytest.mark.parametrize("release", ["2024-01-05 15:30", "2024-01-01T15:30:00-05:00"])
def test_calendar_rejects_naive_or_early_publication(tmp_path, release):
    with pytest.raises(ValueError):
        load_release_calendar(calendar(tmp_path, release))


def test_partial_calendar_does_not_erase_previously_verified_dates(tmp_path):
    db.init_schema()
    frame = pd.DataFrame([{"report_date": "2024-01-09", "market": "GOLD",
                           "release_at": pd.Timestamp("2024-01-12T20:30Z"),
                           "release_quality": "verified", "release_source": "https://example.org/existing"}])
    db.write_frame("cot_legacy", frame)
    apply_calendar(calendar(tmp_path))
    with db.get_conn() as conn:
        assert conn.execute("SELECT release_quality FROM cot_legacy").fetchone()[0] == "verified"


def test_snapshots_redact_credentials_and_are_content_addressed():
    payload = {"response": {"data": [1, 2]}, "request": {"params": {"api_key": "not-a-real-key"}}}
    a, b = save_snapshot("eia", "test", payload), save_snapshot("eia", "test", payload)
    assert a["path"] == b["path"]
    raw = open(a["path"]).read()
    assert "not-a-real-key" not in raw
    assert json.loads(raw)["response"]["data"] == [1, 2]


def test_refresh_preserves_verified_release_metadata_and_invalidates_outputs():
    db.init_schema()
    source = pd.DataFrame([{"report_date": "2024-01-05", "commodity": "CRUDE_OIL", "inventory_level": 100,
                            "release_at": pd.Timestamp("2024-01-10T15:30Z"), "release_quality": "verified",
                            "release_source": "https://eia.gov/archive", "vintage": "latest"}])
    db.write_frame("eia_inventory", source)
    db.write_frame("signals", pd.DataFrame([{"report_date": "2024-01-09", "market": "CRUDE_OIL",
                                              "analysis_eligible": True, "evaluation_version": "release_aware_v1"}]))
    source.loc[0, "inventory_level"] = 101
    source["release_at"], source["release_quality"], source["release_source"] = pd.NaT, "unknown", None
    db.write_frame("eia_inventory", source)
    with db.get_conn() as conn:
        row = conn.execute("SELECT inventory_level,release_quality,release_at FROM eia_inventory").fetchone()
        assert row[0] == 101 and row[1] == "verified" and row[2] is not None
        assert conn.execute("SELECT evaluation_version,analysis_eligible FROM signals").fetchone() == ("stale", False)


def test_corrupt_archived_response_is_detected():
    from pathlib import Path
    result = save_snapshot("test", "test", {"data": [1]})
    Path(result["path"]).write_text("partial")
    with pytest.raises(ValueError, match="checksum"):
        save_snapshot("test", "test", {"data": [1]})
