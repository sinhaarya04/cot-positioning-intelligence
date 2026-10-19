"""Validate authorized contract CSVs and archive a separate research package.

This module never writes the descriptive price database or declares research
readiness. Calendar coverage, licensing and original vintages need other evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import tempfile
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo


MASTER_COLUMNS = (
    "contract_id", "market", "delivery_month", "last_trade_date", "multiplier",
    "currency", "price_unit",
)
PRICE_COLUMNS = ("contract_id", "price_date", "settlement")
OPTIONAL_PRICE_COLUMNS = ("volume", "open_interest")
MARKETS = {
    "CRUDE_OIL": (Decimal("1000"), "USD/barrel"),
    "NATURAL_GAS": (Decimal("10000"), "USD/MMBtu"),
}
GENERIC_ID = re.compile(
    r"^(?:CL|NG)\s*(?:\d+|A|=F|c\d+)?(?:\s+(?:COMB|PIT|ELEC))?(?:\s+COMDTY)?$",
    re.IGNORECASE,
)
BLOOMBERG_ID = re.compile(
    r"^(CL|NG)\s*([FGHJKMNQUVXZ])(\d{1,2}|\d{4})(?:\s+(?:COMB|PIT|ELEC))?\s+COMDTY$",
    re.IGNORECASE,
)
MONTH_CODES = {letter: index for index, letter in enumerate("FGHJKMNQUVXZ", start=1)}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _date(value: str, field: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{field} must be an ISO YYYY-MM-DD date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid calendar date") from exc


def _number(value: str, field: str, *, integer: bool = False) -> Decimal:
    # Strings such as #N/A, NaN and Infinity are data errors, never zeroes.
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not number.is_finite() or not math.isfinite(float(number)):
        raise ValueError(f"{field} must be a finite number")
    if integer and (number < 0 or number != number.to_integral_value()):
        raise ValueError(f"{field} must be a nonnegative integer or blank")
    return number


def _identity(value: str, field: str) -> str:
    if not value or value != value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError(f"{field} must be a nonempty exact provider identifier")
    if GENERIC_ID.fullmatch(value):
        raise ValueError(f"{field} must identify one delivery contract, not a generic/active proxy")
    return value


def _read_csv(raw: bytes, required: tuple[str, ...], optional: tuple[str, ...], name: str):
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{name} must be UTF-8 CSV") from exc
    if "\x00" in decoded:
        raise ValueError(f"{name} contains a NUL byte")
    try:
        reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
        header = reader.fieldnames
        if not header or len(set(header)) != len(header):
            raise ValueError(f"{name} requires unique column names")
        missing, unexpected = set(required) - set(header), set(header) - set(required + optional)
        if missing or unexpected:
            raise ValueError(f"{name} columns invalid: missing={sorted(missing)}, unexpected={sorted(unexpected)}")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{name} row {reader.line_num} has the wrong number of cells")
            rows.append(row)
    except csv.Error as exc:
        raise ValueError(f"{name} is not valid CSV: {exc}") from exc
    if not rows:
        raise ValueError(f"{name} contains no data rows")
    return rows, [column for column in required + optional if column in header]


def _bloomberg_identity(contract_id: str, market: str, delivery: date, label: str):
    match = BLOOMBERG_ID.fullmatch(contract_id)
    if not match:
        raise ValueError(f"{label} requires a resolved Bloomberg CL/NG delivery ticker with Comdty suffix")
    root, month_code, year = match.groups()
    expected_root = "CL" if market == "CRUDE_OIL" else "NG"
    if root.upper() != expected_root or MONTH_CODES[month_code.upper()] != delivery.month:
        raise ValueError(f"{label} Bloomberg root/month disagrees with declared market/delivery_month")
    expected_year = delivery.year if len(year) == 4 else delivery.year % (10 ** len(year))
    if int(year) != expected_year:
        raise ValueError(f"{label} Bloomberg year disagrees with declared delivery_month")


def _validate(master_raw: bytes, prices_raw: bytes, *, bloomberg: bool, export_day: date):
    master, _ = _read_csv(master_raw, MASTER_COLUMNS, (), "contract_master")
    prices, price_columns = _read_csv(prices_raw, PRICE_COLUMNS, OPTIONAL_PRICE_COLUMNS, "contract_prices")
    contracts = {}
    for index, row in enumerate(master, start=2):
        label = f"contract_master row {index}"
        contract_id = _identity(row["contract_id"], f"{label} contract_id")
        if contract_id in contracts:
            raise ValueError(f"{label} duplicates contract_id")
        if row["market"] not in MARKETS:
            raise ValueError(f"{label} has an unknown market")
        month = row["delivery_month"]
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ValueError(f"{label} delivery_month must be YYYY-MM")
        delivery = _date(month + "-01", f"{label} delivery_month")
        expiry = _date(row["last_trade_date"], f"{label} last_trade_date")
        prior_year, prior_month = (delivery.year - 1, 12) if delivery.month == 1 else (delivery.year, delivery.month - 1)
        if (expiry.year, expiry.month) != (prior_year, prior_month):
            raise ValueError(f"{label} last_trade_date must be in the immediately preceding CL/NG delivery month")
        if bloomberg:
            _bloomberg_identity(contract_id, row["market"], delivery, label)
        multiplier, unit = MARKETS[row["market"]]
        if _number(row["multiplier"], f"{label} multiplier") != multiplier:
            raise ValueError(f"{label} has the wrong standard-contract multiplier")
        if row["currency"] != "USD" or row["price_unit"] != unit:
            raise ValueError(f"{label} has incompatible currency or price_unit")
        row["multiplier"] = str(multiplier)
        contracts[contract_id] = row

    seen = set()
    for index, row in enumerate(prices, start=2):
        label = f"contract_prices row {index}"
        contract_id = _identity(row["contract_id"], f"{label} contract_id")
        if contract_id not in contracts:
            raise ValueError(f"{label} contract_id is not an exact match in contract_master")
        observed = _date(row["price_date"], f"{label} price_date")
        if observed > export_day:
            raise ValueError(f"{label} price_date is after the export's New York date")
        if observed > date.fromisoformat(contracts[contract_id]["last_trade_date"]):
            raise ValueError(f"{label} price_date is after last_trade_date")
        key = contract_id, observed
        if key in seen:
            raise ValueError(f"{label} duplicates contract_id/price_date")
        seen.add(key)
        row["settlement"] = str(_number(row["settlement"], f"{label} settlement"))
        for field in OPTIONAL_PRICE_COLUMNS:
            if field in row and row[field] != "":
                row[field] = str(int(_number(row[field], f"{label} {field}", integer=True)))
    master.sort(key=lambda row: (row["market"], row["delivery_month"], row["contract_id"]))
    prices.sort(key=lambda row: (row["contract_id"], row["price_date"]))
    return master, prices, price_columns


def _csv_bytes(rows, columns) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _retrieval_time(value: str | None) -> str:
    if value is None:
        observed = _utc_now()
    else:
        try:
            observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError("retrieved_at must be an ISO timestamp with a timezone") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        if observed > _utc_now():
            raise ValueError("retrieved_at cannot be in the future")
    return observed.astimezone(timezone.utc).isoformat()


def _coverage(master, prices):
    groups = {row["contract_id"]: [] for row in master}
    for row in prices:
        groups[row["contract_id"]].append(row)
    by_contract = []
    for contract in master:
        rows = groups[contract["contract_id"]]
        by_contract.append({
            "contract_id": contract["contract_id"], "market": contract["market"],
            "delivery_month": contract["delivery_month"], "last_trade_date": contract["last_trade_date"],
            "rows": len(rows), "first_price_date": rows[0]["price_date"] if rows else None,
            "last_price_date": rows[-1]["price_date"] if rows else None,
            "negative_settlements": sum(Decimal(row["settlement"]) < 0 for row in rows),
            "zero_settlements": sum(Decimal(row["settlement"]) == 0 for row in rows),
        })
    return {
        "readiness": "not_established", "contracts": len(master), "price_rows": len(prices),
        "contracts_without_prices": sum(not rows for rows in groups.values()),
        "by_contract": by_contract,
        "unvalidated": ["exchange_session_calendar", "historical_availability", "original_vintages",
                        "license_and_storage_rights", "complete_curve_and_common_research_sample"],
        "note": "CSV schema validation is not evidence of research readiness. Missing sessions are not inferred or filled.",
    }


def import_contract_data(master_path, prices_path, *, source: str, price_field: str,
                         output_dir="data/contracts", retrieved_at: str | None = None) -> Path:
    """Publish one immutable package after validating the exact archived bytes."""
    if not source or source != source.strip():
        raise ValueError("source must be a nonempty provider/access description")
    if not price_field or price_field != price_field.strip():
        raise ValueError("price_field must identify the settlement field")
    if price_field.upper() == "PX_LAST":
        raise ValueError("PX_LAST cannot be imported as settlement")
    if "bloomberg" in source.casefold() and price_field.upper() != "PX_SETTLE":
        raise ValueError("Bloomberg imports require the verified PX_SETTLE field")
    timestamp = _retrieval_time(retrieved_at)
    export_day = datetime.fromisoformat(timestamp).astimezone(ZoneInfo("America/New_York")).date()
    # Read each source once. Parsing, hashing and copies all use these bytes,
    # so a subsequent source-file edit cannot produce mismatched provenance.
    master_path, prices_path = Path(master_path), Path(prices_path)
    master_raw, prices_raw = master_path.read_bytes(), prices_path.read_bytes()
    master, prices, price_columns = _validate(master_raw, prices_raw,
                                              bloomberg="bloomberg" in source.casefold(), export_day=export_day)
    coverage = _coverage(master, prices)
    payloads = {
        "original_contract_master.csv": master_raw,
        "original_contract_prices.csv": prices_raw,
        "contract_master.csv": _csv_bytes(master, MASTER_COLUMNS),
        "contract_prices.csv": _csv_bytes(prices, price_columns),
        "coverage.json": _json_bytes(coverage),
    }
    run_id = str(uuid.uuid4())
    manifest = {
        "schema_version": 1, "run_id": run_id, "source": source, "price_field": price_field,
        "retrieved_at": timestamp, "readiness": "not_established",
        "retrieval_time_basis": "user_supplied_export_time" if retrieved_at is not None else "import_time",
        "imported_at": _utc_now().isoformat(),
        "identity_validation": "bloomberg_ticker_metadata_consistency" if "bloomberg" in source.casefold() else "declared_metadata_only",
        "metadata_verification": "Caller-declared metadata; no provider lookup performed. A short ticker year does not independently resolve its decade.",
        "inputs": {"master_name": master_path.name, "prices_name": prices_path.name},
        "files": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                  for name, raw in payloads.items()},
        "database_modified": False,
    }
    payloads["manifest.json"] = _json_bytes(manifest)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    package = destination / run_id
    temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=destination))
    try:
        for name, raw in payloads.items():
            with (temporary / name).open("xb") as handle:
                handle.write(raw)
        # Every successful import gets a new UUID. Existing imports are never
        # opened for writing, and a collision is an explicit failure.
        if package.exists():
            raise FileExistsError(f"Import package already exists: {package}")
        temporary.rename(package)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return package


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", required=True, type=Path)
    parser.add_argument("--prices", required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--price-field", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/contracts"))
    parser.add_argument("--retrieved-at", help="ISO retrieval timestamp with timezone; defaults to now")
    args = parser.parse_args(argv)
    try:
        package = import_contract_data(args.master, args.prices, source=args.source,
                                       price_field=args.price_field, output_dir=args.output_dir,
                                       retrieved_at=args.retrieved_at)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Contract import failed: {exc}\n")
    print(json.dumps({"package": str(package), "readiness": "not_established"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
