"""Contract import tests use small synthetic panels, not a licensed export."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

import pytest

from src.contract_data import MASTER_COLUMNS, import_contract_data, main


def encode(rows, columns):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr("src.contract_data._utc_now", lambda: datetime(2026, 10, 19, 3, 30, tzinfo=timezone.utc))
    master = [
        dict(contract_id="CLK20 Comdty", market="CRUDE_OIL", delivery_month="2020-05",
             last_trade_date="2020-04-21", multiplier="1000", currency="USD", price_unit="USD/barrel"),
        dict(contract_id="NGK20 Comdty", market="NATURAL_GAS", delivery_month="2020-05",
             last_trade_date="2020-04-28", multiplier="10000", currency="USD", price_unit="USD/MMBtu"),
    ]
    prices = [
        dict(contract_id="CLK20 Comdty", price_date="2020-04-20", settlement="-37.63", volume="123", open_interest=""),
        dict(contract_id="CLK20 Comdty", price_date="2020-04-21", settlement="0", volume="0", open_interest="5"),
        dict(contract_id="NGK20 Comdty", price_date="2020-04-20", settlement="2.50", volume="", open_interest="1"),
    ]
    return tmp_path, master, prices


def write_inputs(sample):
    root, master, prices = sample
    master_path, prices_path = root / "master.csv", root / "prices.csv"
    master_path.write_text(encode(master, MASTER_COLUMNS))
    prices_path.write_text(encode(prices, tuple(prices[0])))
    return master_path, prices_path


def run_import(sample, **kwargs):
    master_path, prices_path = write_inputs(sample)
    options = dict(source="Bloomberg institutional lab", price_field="PX_SETTLE",
                   output_dir=sample[0] / "packages", retrieved_at="2026-10-18T12:00:00-04:00")
    options.update(kwargs)
    return import_contract_data(master_path, prices_path, **options)


def test_signed_prices_provenance_and_source_nonmutation(sample):
    master_path, prices_path = write_inputs(sample)
    before = {path: path.read_bytes() for path in (master_path, prices_path)}
    database = sample[0] / "existing.duckdb"
    database.write_bytes(b"stand-in for an untouched descriptive database")
    package = run_import(sample)
    for path, raw in before.items():
        assert path.read_bytes() == raw
    assert database.read_bytes() == b"stand-in for an untouched descriptive database"
    assert (package / "original_contract_master.csv").read_bytes() == before[master_path]
    assert (package / "original_contract_prices.csv").read_bytes() == before[prices_path]
    normalized = list(csv.DictReader(io.StringIO((package / "contract_prices.csv").read_text())))
    assert [row["settlement"] for row in normalized] == ["-37.63", "0", "2.50"]
    assert len(normalized) == 3  # No padded weekends, dates or maturities.
    manifest = json.loads((package / "manifest.json").read_text())
    assert manifest["retrieved_at"] == "2026-10-18T16:00:00+00:00"
    assert manifest["retrieval_time_basis"] == "user_supplied_export_time"
    assert manifest["source"] == "Bloomberg institutional lab"
    assert manifest["price_field"] == "PX_SETTLE"
    assert manifest["database_modified"] is False
    assert manifest["readiness"] == "not_established"
    for name, record in manifest["files"].items():
        raw = (package / name).read_bytes()
        assert record == dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    coverage = json.loads((package / "coverage.json").read_text())
    assert coverage["price_rows"] == 3
    assert coverage["by_contract"][0]["negative_settlements"] == 1
    assert coverage["by_contract"][0]["zero_settlements"] == 1
    assert "exchange_session_calendar" in coverage["unvalidated"]


def test_repeated_import_preserves_previous_package(sample):
    first = run_import(sample)
    first_bytes = {path.name: path.read_bytes() for path in first.iterdir()}
    sample[2][0]["settlement"] = "-36.0"
    second = run_import(sample)
    assert first != second
    assert {path.name: path.read_bytes() for path in first.iterdir()} == first_bytes
    assert not list(first.parent.glob(".pending-*"))


@pytest.mark.parametrize("contract_id", [
    "CL1 Comdty", "NG12 COMB Comdty", "CL=F", "NG=F", "CLA Comdty", "NGA", "CL 1 Comdty", "CLc1", "NGc2", "CL",
])
def test_rejects_generic_and_active_identifiers(sample, contract_id):
    sample[1][0]["contract_id"] = contract_id
    with pytest.raises(ValueError, match="delivery contract"):
        run_import(sample)
    assert not (sample[0] / "packages").exists()


@pytest.mark.parametrize("value", ["", "#N/A", "#N/A Authorization", "NaN", "inf", "-Infinity", "1e9999"])
def test_rejects_missing_error_and_nonfinite_prices(sample, value):
    sample[2][0]["settlement"] = value
    with pytest.raises(ValueError, match="finite number"):
        run_import(sample)
    assert not (sample[0] / "packages").exists()


@pytest.mark.parametrize("field,value,reason", [
    ("market", "BRENT", "unknown market"),
    ("delivery_month", "2020-5", "YYYY-MM"),
    ("delivery_month", "2020-13", "valid calendar"),
    ("last_trade_date", "2020-04-31", "valid calendar"),
    ("last_trade_date", "04/21/2020", "ISO"),
    ("last_trade_date", "2020-05-01", "preceding"),
    ("last_trade_date", "2019-04-21", "preceding"),
    ("multiplier", "100", "multiplier"),
    ("currency", "GBP", "currency"),
    ("price_unit", "USD/MMBtu", "price_unit"),
    ("contract_id", " TEST-CL-202005", "exact provider"),
])
def test_rejects_incompatible_contract_metadata(sample, field, value, reason):
    sample[1][0][field] = value
    with pytest.raises(ValueError, match=reason):
        run_import(sample)


def test_rejects_duplicate_master_even_if_identical(sample):
    sample[1].append(sample[1][0].copy())
    with pytest.raises(ValueError, match="duplicates contract_id"):
        run_import(sample)


def test_rejects_duplicate_prices_even_if_identical(sample):
    sample[2].append(sample[2][0].copy())
    with pytest.raises(ValueError, match="duplicates contract_id/price_date"):
        run_import(sample)


@pytest.mark.parametrize("field,value,reason", [
    ("contract_id", "UNKNOWN-202005", "exact match"),
    ("price_date", "2020-04-22", "after last_trade_date"),
    ("price_date", "2020-4-20", "ISO"),
    ("volume", "-1", "nonnegative integer"),
    ("open_interest", "1.5", "nonnegative integer"),
    ("open_interest", "#N/A", "finite number"),
])
def test_price_identity_expiry_and_optional_counts(sample, field, value, reason):
    sample[2][0][field] = value
    with pytest.raises(ValueError, match=reason):
        run_import(sample)


def test_optional_fields_can_be_absent_and_unobserved_contract_is_reported(sample):
    sample[2][:] = [{k: v for k, v in row.items() if k not in ("volume", "open_interest")}
                    for row in sample[2] if row["contract_id"] == "CLK20 Comdty"]
    package = run_import(sample)
    coverage = json.loads((package / "coverage.json").read_text())
    assert coverage["contracts_without_prices"] == 1
    assert coverage["by_contract"][1]["first_price_date"] is None
    assert (package / "contract_prices.csv").read_text().splitlines()[0] == "contract_id,price_date,settlement"


@pytest.mark.parametrize("change,reason", [
    (lambda s: s.replace("contract_id,", "contract_id,contract_id,", 1), "unique column"),
    (lambda s: s.replace("settlement", "PX_LAST", 1), "columns invalid"),
    (lambda s: s + '"unterminated', "not valid CSV"),
    (lambda s: s.replace("-37.63,123,", "-37.63,123,extra,", 1), "wrong number"),
    (lambda s: s.splitlines()[0] + "\n", "no data rows"),
])
def test_rejects_malformed_csv_without_creating_package(sample, change, reason):
    master_path, prices_path = write_inputs(sample)
    prices_path.write_text(change(prices_path.read_text()))
    with pytest.raises(ValueError, match=reason):
        import_contract_data(master_path, prices_path, source="Bloomberg", price_field="PX_SETTLE",
                             output_dir=sample[0] / "packages")
    assert not (sample[0] / "packages").exists()


@pytest.mark.parametrize("options,reason", [
    ({"source": ""}, "source"),
    ({"price_field": ""}, "price_field"),
    ({"price_field": "PX_LAST"}, "PX_LAST"),
    ({"price_field": "SETTLEMENT"}, "PX_SETTLE"),
    ({"retrieved_at": "2026-10-18"}, "timezone"),
    ({"retrieved_at": "2026-10-18T12:00:00"}, "timezone"),
    ({"retrieved_at": "bad"}, "ISO timestamp"),
    ({"retrieved_at": "2026-10-19T03:30:01+00:00"}, "future"),
])
def test_rejects_missing_provenance_and_wrong_price_semantics(sample, options, reason):
    with pytest.raises(ValueError, match=reason):
        run_import(sample, **options)


def test_archives_exact_bytes_parsed_even_if_source_changes_after_read(sample, monkeypatch):
    master_path, prices_path = write_inputs(sample)
    original = prices_path.read_bytes()
    original_read = Path.read_bytes

    def read_then_change(path):
        value = original_read(path)
        if path == prices_path:
            path.write_text("source changed after the read\n")
        return value

    monkeypatch.setattr(Path, "read_bytes", read_then_change)
    package = import_contract_data(master_path, prices_path, source="Bloomberg", price_field="PX_SETTLE",
                                   output_dir=sample[0] / "packages")
    assert original_read(package / "original_contract_prices.csv") == original
    assert "-37.63" in (package / "contract_prices.csv").read_text()


def test_cli_fails_on_invalid_export_without_touching_inputs(sample, capsys):
    sample[2][0]["settlement"] = "#N/A Authorization"
    master_path, prices_path = write_inputs(sample)
    original = prices_path.read_bytes()
    with pytest.raises(SystemExit) as result:
        main(["--master", str(master_path), "--prices", str(prices_path),
              "--source", "Bloomberg", "--price-field", "PX_SETTLE",
              "--output-dir", str(sample[0] / "packages")])
    assert result.value.code == 1
    assert "Contract import failed" in capsys.readouterr().err
    assert prices_path.read_bytes() == original
    assert not (sample[0] / "packages").exists()


def test_failed_publication_cleans_pending_package_and_keeps_old_import(sample, monkeypatch):
    first = run_import(sample)
    original_manifest = (first / "manifest.json").read_bytes()
    original_open = Path.open

    def fail_new_price_write(path, mode="r", *args, **kwargs):
        if path.name == "contract_prices.csv" and mode == "xb":
            raise OSError("simulated storage failure")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_new_price_write)
    with pytest.raises(OSError, match="storage failure"):
        run_import(sample)
    assert list(first.parent.iterdir()) == [first]
    assert (first / "manifest.json").read_bytes() == original_manifest


def test_cli_success_records_default_timestamp_basis(sample, capsys):
    master_path, prices_path = write_inputs(sample)
    assert main(["--master", str(master_path), "--prices", str(prices_path),
                 "--source", "Bloomberg", "--price-field", "PX_SETTLE",
                 "--output-dir", str(sample[0] / "packages")]) == 0
    response = json.loads(capsys.readouterr().out)
    manifest = json.loads((Path(response["package"]) / "manifest.json").read_text())
    assert manifest["retrieval_time_basis"] == "import_time"
    assert response["readiness"] == "not_established"


@pytest.mark.parametrize("identifier,reason", [
    ("CLM20 Comdty", "root/month"),
    ("NGK20 Comdty", "root/month"),
    ("CLK21 Comdty", "year"),
    ("CLK2021 Comdty", "year"),
    ("BBG000000000", "resolved Bloomberg"),
])
def test_bloomberg_identifier_must_agree_with_metadata(sample, identifier, reason):
    sample[1][0]["contract_id"] = identifier
    for row in sample[2]:
        if row["contract_id"] == "CLK20 Comdty":
            row["contract_id"] = identifier
    with pytest.raises(ValueError, match=reason):
        run_import(sample)


@pytest.mark.parametrize("identifier", ["CLK0 COMB Comdty", "CLK2020 Comdty", "CL K20 ELEC Comdty"])
def test_matching_bloomberg_year_lengths_and_sessions(sample, identifier):
    sample[1][0]["contract_id"] = identifier
    for row in sample[2]:
        if row["contract_id"] == "CLK20 Comdty":
            row["contract_id"] = identifier
    package = run_import(sample)
    manifest = json.loads((package / "manifest.json").read_text())
    assert manifest["identity_validation"] == "bloomberg_ticker_metadata_consistency"
    assert "no provider lookup" in manifest["metadata_verification"]


def test_export_date_uses_new_york_not_utc_calendar_day(sample):
    # 00:30 UTC on April 21 is still April 20 in New York. The April 21
    # observation cannot already have existed in this declared export.
    with pytest.raises(ValueError, match="export's New York date"):
        run_import(sample, retrieved_at="2020-04-21T00:30:00+00:00")


def test_non_bloomberg_source_reports_declared_identity_only(sample):
    sample[1][0]["contract_id"] = "NYMEX-CL-202005"
    for row in sample[2]:
        if row["contract_id"] == "CLK20 Comdty":
            row["contract_id"] = "NYMEX-CL-202005"
    package = run_import(sample, source="Another settlement provider", price_field="settlement")
    manifest = json.loads((package / "manifest.json").read_text())
    assert manifest["identity_validation"] == "declared_metadata_only"
