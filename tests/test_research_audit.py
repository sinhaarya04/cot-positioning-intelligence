import csv
import hashlib
import json

import duckdb
import pandas as pd
import pytest

from src.research_audit import COLUMNS, audit_frames, load_evidence, resolve_evidence, run_audit


def entry(**changes):
    return {"evidence_id": "cot-1", "dataset": "disagg", "market": "*",
            "report_date": "2023-01-31", "release_date": "2023-02-24", "release_at": "",
            "status": "confirmed", "source": "https://www.cftc.gov/example", "note": "Test evidence", **changes}


def ledger(tmp_path, rows, name="evidence.csv"):
    path = tmp_path / name
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def resolve(rows, dataset="disagg", market="CRUDE_OIL", report_date="2023-01-31"):
    return resolve_evidence(rows, dataset, market, report_date)


@pytest.mark.parametrize("change", [
    {"release_at": "2023-02-24T15:30:00"},
    {"release_at": "2023-02-25T01:00:00-05:00"},
    {"release_date": "2023-01-30"},
    {"report_date": "2023-1-31"},
    {"status": "estimated"},
    {"source": "https://user:password@example.com/source"},
    {"source": "file:///source"},
    {"dataset": "eia", "market": "*"},
    {"status": "available_by"},
    {"report_date": "2008-01-01", "release_date": "2008-01-04"},
])
def test_invalid_evidence_fails(tmp_path, change):
    with pytest.raises(ValueError):
        load_evidence([ledger(tmp_path, [entry(**change)])])


def test_duplicate_ids_across_ledgers_fail(tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        load_evidence([ledger(tmp_path, [entry()]), ledger(tmp_path, [entry()], "other.csv")])


def test_timestamp_normalized_and_equivalent_sources_agree(tmp_path):
    rows = load_evidence([ledger(tmp_path, [entry(release_at="2023-02-24T15:30:00-05:00"),
        entry(evidence_id="cot-2", release_at="2023-02-24T20:30:00Z")])])
    result = resolve(rows)
    assert result["evidence_status"] == "confirmed_timestamp"
    assert result["release_at"] == "2023-02-24T20:30:00+00:00"
    assert result["availability_lower_bound"] == result["availability_upper_bound"]


@pytest.mark.parametrize("release, hours", [("2023-03-12", 23), ("2023-11-05", 25)])
def test_date_only_interval_respects_daylight_saving(release, hours):
    result = resolve([entry(release_date=release)])
    assert result["release_at"] is None
    duration = pd.Timestamp(result["availability_upper_bound"]) - pd.Timestamp(result["availability_lower_bound"])
    assert duration == pd.Timedelta(hours=hours)


def test_planned_superseded_and_missing_do_not_establish_availability():
    for status in ("scheduled", "superseded"):
        result = resolve([entry(status=status)])
        assert result["evidence_status"] == status + "_only"
        assert result["availability_upper_bound"] is None
    assert resolve([])["evidence_status"] == "missing"


def test_conflicts_are_excluded_and_specific_evidence_overrides_wildcard():
    rows = [entry(), entry(evidence_id="cot-2", release_date="2023-02-25")]
    assert resolve(rows)["evidence_status"] == "conflict"
    rows[1]["market"] = "CRUDE_OIL"
    assert resolve(rows)["release_date"] == "2023-02-25"
    assert resolve(rows, market="NATURAL_GAS")["release_date"] == "2023-02-24"


def test_available_by_is_only_an_upper_bound_and_cannot_override_conflict():
    row = entry(dataset="eia", market="NATURAL_GAS", status="available_by", release_date="2023-02-23")
    result = resolve([row], dataset="eia", market="NATURAL_GAS")
    assert result["release_date"] is None
    assert result["release_at"] is None
    assert result["availability_lower_bound"] is None
    assert result["availability_upper_bound"] == "2023-02-24T05:00:00+00:00"
    confirmed = {**row, "evidence_id": "original", "status": "confirmed", "release_date": "2023-02-24"}
    assert resolve([row, confirmed], dataset="eia", market="NATURAL_GAS")["evidence_status"] == "conflict"
    confirmed["release_date"] = "2023-02-23"
    assert resolve([row, confirmed], dataset="eia", market="NATURAL_GAS")["evidence_status"] == "confirmed_date"


def timing_frames():
    return {"cot_disagg": pd.DataFrame([{"market": "CRUDE_OIL", "report_date": "2023-01-31", "vintage": "latest"}]),
            "eia_inventory": pd.DataFrame([{"commodity": "CRUDE_OIL", "report_date": "2023-02-17", "vintage": "latest"}])}


def test_inventory_date_bounds_include_previous_day_but_exclude_same_day():
    inventory = entry(evidence_id="eia-1", dataset="eia", market="CRUDE_OIL", report_date="2023-02-17", release_date="2023-02-23")
    for status in ("confirmed", "available_by"):
        inventory["status"] = status
        report, events = audit_frames(timing_frames(), [entry(), inventory])
        assert report["inventory_overlap"][0]["inventory_report_date"] == "2023-02-17"
        assert report["inventory_overlap"][0]["inventory_age_days_at_release"] == 7
        assert all(e["declared_vintage"] == "latest" for e in events)
        same_day, _ = audit_frames(timing_frames(), [entry(), {**inventory, "release_date": "2023-02-24"}])
        assert same_day["inventory_overlap"][0]["inventory_report_date"] is None


def test_simultaneous_exact_publications_not_in_pre_cot_baseline():
    stamp = "2023-02-24T20:30:00+00:00"
    cot = entry(release_at=stamp)
    inventory = entry(evidence_id="eia-1", dataset="eia", market="CRUDE_OIL", report_date="2023-02-17", release_at=stamp)
    report, _ = audit_frames(timing_frames(), [cot, inventory])
    assert report["inventory_overlap"][0]["inventory_report_date"] is None


@pytest.mark.parametrize("stored, conflict", [("2023-02-23T15:30:00Z", False), ("2023-02-24T05:00:00Z", True), (None, True)])
def test_available_by_metadata_conflicts_respect_bound(stored, conflict):
    frames = timing_frames()
    frames["eia_inventory"]["release_quality"] = "verified"
    frames["eia_inventory"]["release_at"] = pd.to_datetime([stored], utc=True)
    evidence = entry(evidence_id="eia-1", dataset="eia", market="CRUDE_OIL", report_date="2023-02-17", release_date="2023-02-23", status="available_by")
    report, events = audit_frames(frames, [entry(), evidence])
    eia_event = next(e for e in events if e["dataset"] == "eia")
    assert eia_event["metadata_conflict"] == conflict
    summary = next(r for r in report["coverage"] if r["dataset"] == "eia" and r["market"] == "CRUDE_OIL")
    assert summary["without_publication_evidence_rows"] == int(conflict)


def test_conflicting_database_timestamp_excluded_from_overlap():
    frames = timing_frames()
    frames["cot_disagg"]["release_quality"] = "verified"
    frames["cot_disagg"]["release_at"] = pd.to_datetime(["2023-02-03T20:30:00Z"])
    report, events = audit_frames(frames, [entry()])
    assert report["inventory_overlap"] == []
    assert events[0]["metadata_conflict"]


def make_database(path):
    with duckdb.connect(str(path)) as conn:
        conn.execute("CREATE TABLE cot_disagg AS SELECT 'CRUDE_OIL' AS market, DATE '2023-01-31' AS report_date, 'latest' AS vintage")
    return path


def test_run_is_read_only_records_hashes_and_does_not_claim_readiness(tmp_path):
    database = make_database(tmp_path / "snapshot.duckdb")
    before = database.read_bytes()
    source = ledger(tmp_path, [entry()])
    result = run_audit(database, [source], tmp_path / "audit")
    assert database.read_bytes() == before
    assert result["database_sha256"] == hashlib.sha256(before).hexdigest()
    assert result["evidence_files"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result["research_status"] == "not_established"
    assert "futures_prices" in result["missing_tables"]
    saved = json.loads((tmp_path / "audit/research-audit.json").read_text())
    assert saved == result
    events = pd.read_csv(tmp_path / "audit/release-coverage.csv")
    assert events.release_at.isna().all()
    assert events.database_release_quality.tolist() == ["unknown"]


@pytest.mark.parametrize("symlink", [False, True])
def test_outputs_cannot_overwrite_input_database(tmp_path, symlink):
    database = make_database(tmp_path / ("snapshot.duckdb" if symlink else "research-audit.json"))
    if symlink:
        (tmp_path / "research-audit.json").symlink_to(database)
    before = database.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        run_audit(database, [ledger(tmp_path, [entry()])], tmp_path)
    assert database.read_bytes() == before


def test_outputs_cannot_overwrite_evidence(tmp_path):
    database = make_database(tmp_path / "snapshot.duckdb")
    source = ledger(tmp_path, [entry()], "release-coverage.csv")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        run_audit(database, [source], tmp_path)
    assert source.read_bytes() == before


def test_missing_database_does_not_create_one(tmp_path):
    missing = tmp_path / "missing.duckdb"
    with pytest.raises(FileNotFoundError):
        run_audit(missing, [], tmp_path / "audit")
    assert not missing.exists()


def test_evidence_mutation_aborts_instead_of_recording_wrong_hash(tmp_path, monkeypatch):
    from src import research_audit
    database = make_database(tmp_path / "snapshot.duckdb")
    source = ledger(tmp_path, [entry()])
    original = research_audit.load_evidence

    def mutate(paths):
        rows = original(paths)
        source.write_text(source.read_text().replace("Test evidence", "Changed evidence"))
        return rows

    monkeypatch.setattr(research_audit, "load_evidence", mutate)
    with pytest.raises(RuntimeError, match="Evidence changed"):
        run_audit(database, [source], tmp_path / "audit")
    assert not (tmp_path / "audit").exists()
