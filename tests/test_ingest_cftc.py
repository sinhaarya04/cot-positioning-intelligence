"""Regression coverage for the CFTC source schema and safe ingestion."""

from copy import deepcopy
from datetime import date

import pandas as pd
import pytest

from src import db
from src import ingest_cftc as ingest


# Literal source fields keep the mapping test independent of production maps.
SOURCES = {
    "legacy": {
        "noncomm_positions_long_all": "11", "noncomm_positions_short_all": "12",
        "noncomm_postions_spread_all": "13", "comm_positions_long_all": "14",
        "comm_positions_short_all": "15", "nonrept_positions_long_all": "962",
        "nonrept_positions_short_all": "960",
    },
    "disagg": {
        "prod_merc_positions_long": "11", "prod_merc_positions_short": "12",
        "swap_positions_long_all": "13", "swap__positions_short_all": "14",
        "swap__positions_spread_all": "15", "m_money_positions_long_all": "16",
        "m_money_positions_short_all": "17", "m_money_positions_spread": "18",
        "other_rept_positions_long": "19", "other_rept_positions_short": "20",
        "other_rept_positions_spread": "21", "nonrept_positions_long_all": "887",
        "nonrept_positions_short_all": "883",
    },
    "tff": {
        "dealer_positions_long_all": "11", "dealer_positions_short_all": "12",
        "dealer_positions_spread_all": "13", "asset_mgr_positions_long": "14",
        "asset_mgr_positions_short": "15", "asset_mgr_positions_spread": "16",
        "lev_money_positions_long": "17", "lev_money_positions_short": "18",
        "lev_money_positions_spread": "19", "other_rept_positions_long": "20",
        "other_rept_positions_short": "21", "other_rept_positions_spread": "22",
        "nonrept_positions_long_all": "868", "nonrept_positions_short_all": "864",
    },
}
EXPECTED = {
    "legacy": {"noncomm_long": 11, "noncomm_short": 12, "noncomm_spreading": 13,
               "comm_long": 14, "comm_short": 15, "nonrep_long": 962, "nonrep_short": 960},
    "disagg": {"prod_merc_long": 11, "prod_merc_short": 12, "swap_long": 13,
               "swap_short": 14, "swap_spreading": 15, "mgd_money_long": 16,
               "mgd_money_short": 17, "mgd_money_spreading": 18, "other_long": 19,
               "other_short": 20, "other_spreading": 21},
    "tff": {"dealer_long": 11, "dealer_short": 12, "dealer_spreading": 13,
            "asset_mgr_long": 14, "asset_mgr_short": 15, "asset_mgr_spreading": 16,
            "lev_money_long": 17, "lev_money_short": 18, "lev_money_spreading": 19,
            "other_long": 20, "other_short": 21, "other_spreading": 22},
}


def source(kind="legacy", report_date="2024-01-09T00:00:00.000"):
    return {**deepcopy(SOURCES[kind]), "report_date_as_yyyy_mm_dd": report_date,
            "cftc_contract_market_code": "088691", "open_interest_all": "1000"}


def parse(kind, rows):
    return getattr(ingest, f"parse_{kind}")(pd.DataFrame(rows), "GOLD")


@pytest.mark.parametrize("kind", SOURCES)
def test_exact_official_field_mappings(kind):
    result = parse(kind, [source(kind)])[0]
    assert result == {"report_date": date(2024, 1, 9), "market": "GOLD",
                      "cftc_code": "088691", "open_interest": 1000, **EXPECTED[kind]}


@pytest.mark.parametrize("kind,field", [
    ("legacy", "noncomm_postions_spread_all"),
    ("disagg", "prod_merc_positions_long"),
    ("disagg", "m_money_positions_spread"),
    ("tff", "asset_mgr_positions_long"),
    ("tff", "lev_money_positions_short"),
    ("tff", "other_rept_positions_spread"),
])
def test_missing_source_fields_fail_instead_of_becoming_zero(kind, field):
    row = source(kind)
    del row[field]
    with pytest.raises(ValueError, match="missing required fields"):
        parse(kind, [row])


@pytest.mark.parametrize("value", [None, "", "NaN", float("inf"), "1.5", "-1", True, str(2**63)])
def test_invalid_numeric_values_rejected(value):
    row = source()
    row["noncomm_positions_long_all"] = value
    with pytest.raises(ValueError):
        parse("legacy", [row])


def test_real_zero_positions_remain_zero():
    row = source()
    for key in SOURCES["legacy"]:
        row[key] = "0"
    row["open_interest_all"] = "0"
    assert parse("legacy", [row])[0]["noncomm_long"] == 0


@pytest.mark.parametrize("value", [None, "2024-02-30", "2024-01-09T12:00:00", "yesterday", 20240109])
def test_invalid_report_dates_rejected(value):
    row = source()
    row["report_date_as_yyyy_mm_dd"] = value
    with pytest.raises(ValueError):
        parse("legacy", [row])


@pytest.mark.parametrize("value", [88691, "88691", "08869'", "084691"])
def test_invalid_or_mismatched_contract_identity_rejected(value):
    row = source()
    row["cftc_contract_market_code"] = value
    with pytest.raises(ValueError):
        parse("legacy", [row])


@pytest.mark.parametrize("value", ["13874A", "13874+"])
def test_valid_alphanumeric_and_consolidated_contract_codes(value):
    assert ingest._contract_code(value) == value


@pytest.mark.parametrize("kind", SOURCES)
def test_position_totals_must_reconcile_to_open_interest(kind):
    row = source(kind)
    row["nonrept_positions_long_all"] = str(int(row["nonrept_positions_long_all"]) + 1)
    with pytest.raises(ValueError, match="reconcile to open interest"):
        parse(kind, [row])


@pytest.mark.parametrize("kind", SOURCES)
def test_official_reportable_totals_are_checked(kind):
    row = source(kind)
    row["tot_rept_positions_short"] = "1"
    with pytest.raises(ValueError, match="reconcile to reportable total"):
        parse(kind, [row])


def test_positions_cannot_exceed_open_interest_without_nonreportable_fields():
    row = source("disagg")
    del row["nonrept_positions_long_all"]
    del row["nonrept_positions_short_all"]
    row["open_interest_all"] = "1"
    with pytest.raises(ValueError, match="exceed open interest"):
        parse("disagg", [row])


def test_duplicate_dates_rejected_even_when_source_formats_differ():
    with pytest.raises(ValueError, match="Duplicate"):
        parse("legacy", [source(), source(report_date="2024-01-09")])


def mock_pages(monkeypatch, pages):
    calls, snapshots = [], []

    class Response:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    def get(url, params, timeout):
        calls.append(params.copy())
        return Response(pages[len(calls) - 1])

    def snapshot(*args):
        snapshots.append(args)
        return {"source_hash": str(len(snapshots)), "retrieved_at": "2024-01-15T00:00:00Z"}

    monkeypatch.setattr(ingest.requests, "get", get)
    monkeypatch.setattr(ingest, "save_snapshot", snapshot)
    return calls, snapshots


def test_pagination_retains_every_page_and_archives_raw_payloads(monkeypatch):
    rows = [source(report_date=f"2024-01-{day}") for day in ["02", "09", "16"]]
    calls, snapshots = mock_pages(monkeypatch, [rows[:2], rows[2:]])
    frame = ingest.fetch_cftc_data("legacy", "088691", limit=2)
    assert len(frame) == 3
    assert [call["$offset"] for call in calls] == [0, 2]
    assert [entry[2]["rows"] for entry in snapshots] == [rows[:2], rows[2:]]
    assert len(frame.attrs["snapshots"]) == 2


def test_exact_full_page_fetches_terminating_empty_page(monkeypatch):
    calls, _ = mock_pages(monkeypatch, [[source()], []])
    assert len(ingest.fetch_cftc_data("legacy", "088691", limit=1)) == 1
    assert len(calls) == 2


def test_repeated_page_fails_without_infinite_pagination(monkeypatch):
    calls, _ = mock_pages(monkeypatch, [[source()], [source()]])
    with pytest.raises(ValueError, match="Duplicate"):
        ingest.fetch_cftc_data("legacy", "088691", limit=1)
    assert len(calls) == 2


@pytest.mark.parametrize("body", [[], {"error": "schema changed"}, ["not-a-row"]])
def test_empty_and_malformed_api_responses_fail(monkeypatch, body):
    mock_pages(monkeypatch, [body])
    with pytest.raises(ValueError):
        ingest.fetch_cftc_data("legacy", "088691")


def test_explicit_start_date_overrides_environment_and_is_recorded(monkeypatch):
    monkeypatch.setenv("COT_START_DATE", "2010-01-01")
    calls, snapshots = mock_pages(monkeypatch, [[source()]])
    ingest.fetch_cftc_data("legacy", "088691", start_date="2009-09-01")
    assert "report_date_as_yyyy_mm_dd >= '2009-09-01T00:00:00'" in calls[0]["$where"]
    assert snapshots[0][2]["params"]["$where"] == calls[0]["$where"]


def test_start_date_environment_is_optional_and_does_not_change_default(monkeypatch):
    monkeypatch.delenv("COT_START_DATE", raising=False)
    calls, _ = mock_pages(monkeypatch, [[source()]])
    ingest.fetch_cftc_data("legacy", "088691")
    assert calls[0]["$where"] == "cftc_contract_market_code='088691'"
    monkeypatch.setenv("COT_START_DATE", "2009-09-01")
    assert ingest._start_date() == date(2009, 9, 1)


@pytest.mark.parametrize("value", ["2009-02-30", "2009-9-1", "2009-09-01T00:00:00", "x' OR 1=1", ""])
def test_start_date_must_be_valid_iso_date(value):
    with pytest.raises(ValueError):
        ingest._start_date(value)


def test_cli_validates_and_passes_start_date(monkeypatch):
    monkeypatch.setattr(ingest, "ingest_all", lambda start_date: {"date": start_date})
    assert ingest.main(["--start-date", "2009-09-01"]) == {"date": date(2009, 9, 1)}
    with pytest.raises(SystemExit) as exc:
        ingest.main(["--start-date", "nonsense"])
    assert exc.value.code == 2


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "cot.duckdb")
    monkeypatch.delenv("COT_RELEASE_CALENDAR", raising=False)
    db.init_schema()
    return tmp_path


def test_upsert_stores_unknown_availability_without_inventing_friday(database):
    ingest.upsert_rows("cot_legacy", parse("legacy", [source()]))
    with db.get_conn() as conn:
        row = conn.execute("SELECT release_at, release_quality, vintage, ingested_at FROM cot_legacy").fetchone()
    assert row[:3] == (None, "unknown", "latest")
    assert row[3] is not None


def test_invalid_and_duplicate_replacements_preserve_existing_rows(database):
    rows = parse("legacy", [source()])
    ingest.upsert_rows("cot_legacy", rows)
    with pytest.raises(ValueError, match="Duplicate"):
        ingest.upsert_rows("cot_legacy", rows + rows)
    invalid = [{**rows[0], "open_interest": "not-an-integer"}]
    with pytest.raises(Exception):
        ingest.upsert_rows("cot_legacy", invalid)
    with db.get_conn() as conn:
        assert conn.execute("SELECT open_interest FROM cot_legacy").fetchall() == [(1000,)]


def test_ingestion_skips_tff_for_physical_markets(monkeypatch):
    calls = []
    monkeypatch.setattr(ingest, "MARKET_CONFIG", {"GOLD": {"cftc_code": "088691"}})
    monkeypatch.setattr(ingest, "init_schema", lambda: None)
    monkeypatch.setattr(ingest, "fetch_cftc_data", lambda kind, code, **kwargs: calls.append(kind) or pd.DataFrame([source(kind)]))
    monkeypatch.setattr(ingest, "upsert_rows", lambda *args: None)
    assert sum(ingest.ingest_all().values()) == 2
    assert calls == ["legacy", "disagg"]


def test_required_ingestion_failure_is_not_silently_successful(monkeypatch):
    monkeypatch.setattr(ingest, "MARKET_CONFIG", {"GOLD": {"cftc_code": "088691"}})
    monkeypatch.setattr(ingest, "init_schema", lambda: None)

    def fail(*args, **kwargs):
        raise ValueError("upstream unavailable")

    monkeypatch.setattr(ingest, "fetch_cftc_data", fail)
    with pytest.raises(RuntimeError, match="Required CFTC ingestion failed"):
        ingest.ingest_all()
