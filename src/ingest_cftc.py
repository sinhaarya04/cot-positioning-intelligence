"""Validated ingestion of the CFTC's futures-only Socrata datasets.

The API's spelling is not consistent between datasets. Field names below are
literal source names, verified against the official endpoints. Missing fields
are errors, never zero positions. Current API history is labelled ``latest``;
it does not establish what an investor saw in the original publication.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import os
import re

import pandas as pd
import requests

from src.availability import attach_release_metadata
from src.db import MARKET_CONFIG, init_schema, write_frame
from src.provenance import save_snapshot

ENDPOINTS = {
    "legacy": "https://publicreporting.cftc.gov/resource/6dca-aqww.json",
    "disagg": "https://publicreporting.cftc.gov/resource/72hh-3qpy.json",
    "tff": "https://publicreporting.cftc.gov/resource/gpe5-46if.json",
}
PAGE_SIZE = 50000
DATE_FIELD = "report_date_as_yyyy_mm_dd"
CODE_FIELD = "cftc_contract_market_code"

# Source spelling, including "postions" and double underscores, is intentional.
FIELD_MAPS = {
    "legacy": {
        "noncomm_long": "noncomm_positions_long_all",
        "noncomm_short": "noncomm_positions_short_all",
        "noncomm_spreading": "noncomm_postions_spread_all",
        "comm_long": "comm_positions_long_all",
        "comm_short": "comm_positions_short_all",
        "nonrep_long": "nonrept_positions_long_all",
        "nonrep_short": "nonrept_positions_short_all",
        "open_interest": "open_interest_all",
    },
    "disagg": {
        "prod_merc_long": "prod_merc_positions_long",
        "prod_merc_short": "prod_merc_positions_short",
        "swap_long": "swap_positions_long_all",
        "swap_short": "swap__positions_short_all",
        "swap_spreading": "swap__positions_spread_all",
        "mgd_money_long": "m_money_positions_long_all",
        "mgd_money_short": "m_money_positions_short_all",
        "mgd_money_spreading": "m_money_positions_spread",
        "other_long": "other_rept_positions_long",
        "other_short": "other_rept_positions_short",
        "other_spreading": "other_rept_positions_spread",
        "open_interest": "open_interest_all",
    },
    "tff": {
        "dealer_long": "dealer_positions_long_all",
        "dealer_short": "dealer_positions_short_all",
        "dealer_spreading": "dealer_positions_spread_all",
        "asset_mgr_long": "asset_mgr_positions_long",
        "asset_mgr_short": "asset_mgr_positions_short",
        "asset_mgr_spreading": "asset_mgr_positions_spread",
        "lev_money_long": "lev_money_positions_long",
        "lev_money_short": "lev_money_positions_short",
        "lev_money_spreading": "lev_money_positions_spread",
        "other_long": "other_rept_positions_long",
        "other_short": "other_rept_positions_short",
        "other_spreading": "other_rept_positions_spread",
        "open_interest": "open_interest_all",
    },
}


def _contract_code(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9A-Z]{5}[0-9A-Z+]", value):
        raise ValueError(f"Invalid CFTC contract code: {value!r}; keep leading zeros")
    return value


def _report_date(value) -> date:
    if not isinstance(value, (str, date, datetime, pd.Timestamp)) or pd.isna(value):
        raise ValueError(f"Invalid CFTC report date: {value!r}")
    if isinstance(value, str) and not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:T00:00:00(?:\.0+)?)?", value
    ):
        raise ValueError(f"Invalid CFTC report date: {value!r}")
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid CFTC report date: {value!r}") from exc
    if stamp != stamp.normalize() or stamp.tzinfo is not None:
        raise ValueError(f"CFTC report date must be a date, not a timestamp: {value!r}")
    return stamp.date()


def _integer(value, field: str) -> int:
    if isinstance(value, bool) or value is None or pd.isna(value):
        raise ValueError(f"Missing or invalid position in {field}: {value!r}")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid position in {field}: {value!r}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"Position must be a finite integer in {field}: {value!r}")
    if number < 0 or number > 2**63 - 1:
        raise ValueError(f"Position outside nonnegative BIGINT range in {field}: {value!r}")
    return int(number)


def _validate_keys(frame: pd.DataFrame, expected_code: str | None = None) -> pd.DataFrame:
    missing = {DATE_FIELD, CODE_FIELD} - set(frame.columns)
    if missing:
        raise ValueError(f"CFTC response missing required fields: {sorted(missing)}")
    keys = pd.DataFrame({
        "report_date": frame[DATE_FIELD].map(_report_date),
        "cftc_code": frame[CODE_FIELD].map(_contract_code),
    })
    if expected_code is not None and not keys["cftc_code"].eq(expected_code).all():
        raise ValueError(f"CFTC response contains a different contract from {expected_code}")
    if keys["cftc_code"].nunique() != 1:
        raise ValueError("CFTC parser requires exactly one contract per market")
    if keys.duplicated().any():
        raise ValueError("Duplicate CFTC report_date/contract keys; no rows have been written")
    return keys


def _start_date(value=None) -> date | None:
    value = os.environ.get("COT_START_DATE") if value is None else value
    if value is None:
        return None
    if isinstance(value, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("CFTC start date must use YYYY-MM-DD")
    if isinstance(value, datetime):
        raise ValueError("CFTC start date must be a date, not a timestamp")
    return _report_date(value)


def fetch_cftc_data(
    report_type: str, cftc_code: str, limit: int = PAGE_SIZE, start_date=None,
) -> pd.DataFrame:
    """Fetch every page for one contract; ``limit`` is the page size.

    Raw responses are saved before parsing. An incomplete/empty response raises
    instead of silently producing a successful, partially populated run.
    """
    if report_type not in ENDPOINTS:
        raise ValueError(f"Unsupported CFTC dataset: {report_type}")
    cftc_code = _contract_code(cftc_code)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= PAGE_SIZE:
        raise ValueError(f"Page size must be an integer between 1 and {PAGE_SIZE}")
    start_date = _start_date(start_date)
    where = f"{CODE_FIELD}='{cftc_code}'"
    if start_date is not None:
        where += f" AND {DATE_FIELD} >= '{start_date.isoformat()}T00:00:00'"
    records, snapshots = [], []
    seen_keys = set()
    offset = 0
    while True:
        params = {
            "$where": where,
            "$order": f"{DATE_FIELD} ASC, :id ASC",
            "$limit": limit,
            "$offset": offset,
        }
        response = requests.get(ENDPOINTS[report_type], params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        snapshots.append(save_snapshot(
            f"cftc_{report_type}", f"{cftc_code}-offset-{offset}",
            {"url": ENDPOINTS[report_type], "params": params, "rows": data},
        ))
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError(f"Invalid CFTC response for {report_type}/{cftc_code}")
        if len(data) > limit:
            raise ValueError("CFTC response exceeded the requested page size")
        if data:
            page_keys = _validate_keys(pd.DataFrame(data), expected_code=cftc_code)
            key_set = set(page_keys.itertuples(index=False, name=None))
            if seen_keys.intersection(key_set):
                raise ValueError("Duplicate CFTC keys across pages; pagination may be unstable")
            seen_keys.update(key_set)
        records.extend(data)
        if len(data) < limit:
            break
        offset += len(data)
    if not records:
        raise ValueError(f"No CFTC data for required dataset {report_type}/{cftc_code}")
    frame = pd.DataFrame(records)
    _validate_keys(frame, expected_code=cftc_code)
    frame.attrs["snapshots"] = snapshots
    print(f"  {report_type}: {len(frame)} rows for code {cftc_code}")
    return frame


def _reconcile(row: dict, source: dict, report_type: str) -> None:
    """Check exact contract-count identities, including spreads on both sides."""
    open_interest = row["open_interest"]
    for side in ("long", "short"):
        reported = sum(
            value for name, value in row.items()
            if (name.endswith(f"_{side}") and not name.startswith("nonrep_"))
            or name.endswith("_spreading")
        )
        if reported > open_interest:
            raise ValueError(f"{report_type} {side} positions exceed open interest")
        total_field = (
            "tot_rept_positions_long_all" if side == "long" else "tot_rept_positions_short"
        )
        if total_field in source:
            total = _integer(source[total_field], total_field)
            if reported != total:
                raise ValueError(f"{report_type} {side} positions do not reconcile to reportable total")
        nonrep_field = f"nonrept_positions_{side}_all"
        if nonrep_field in source:
            nonrep = _integer(source[nonrep_field], nonrep_field)
            if reported + nonrep != open_interest:
                raise ValueError(f"{report_type} {side} positions do not reconcile to open interest")


def _parse(df: pd.DataFrame, market: str, report_type: str) -> list[dict]:
    if df.empty:
        raise ValueError(f"Cannot parse empty {report_type} data for {market}")
    if not isinstance(market, str) or not market.strip():
        raise ValueError("A nonempty market identity is required")
    mapping = FIELD_MAPS[report_type]
    missing = {DATE_FIELD, CODE_FIELD, *mapping.values()} - set(df.columns)
    if missing:
        raise ValueError(f"{report_type} missing required fields: {sorted(missing)}")
    expected = MARKET_CONFIG.get(market, {}).get("cftc_code")
    keys = _validate_keys(df, expected_code=expected)
    rows = []
    for position, source in enumerate(df.to_dict("records")):
        report_date = keys.iloc[position]["report_date"]
        try:
            row = {
                "report_date": report_date,
                "market": market,
                "cftc_code": keys.iloc[position]["cftc_code"],
                **{target: _integer(source[field], field) for target, field in mapping.items()},
            }
            _reconcile(row, source, report_type)
        except ValueError as exc:
            raise ValueError(f"{report_type}/{market}/{report_date}: {exc}") from exc
        rows.append(row)
    return rows


def parse_legacy(df: pd.DataFrame, market: str) -> list[dict]:
    return _parse(df, market, "legacy")


def parse_disagg(df: pd.DataFrame, market: str) -> list[dict]:
    return _parse(df, market, "disagg")


def parse_tff(df: pd.DataFrame, market: str) -> list[dict]:
    return _parse(df, market, "tff")


def upsert_rows(table: str, rows: list[dict]) -> None:
    """Validate identity and atomically write explicitly named columns."""
    tables = {f"cot_{kind}": kind for kind in FIELD_MAPS}
    if table not in tables:
        raise ValueError(f"Unsupported CFTC table: {table}")
    if not rows:
        raise ValueError(f"Refusing empty CFTC ingestion for {table}")
    frame = pd.DataFrame(rows)
    if frame.duplicated(["report_date", "market"]).any():
        raise ValueError("Duplicate CFTC report_date/market keys; no rows have been written")
    frame = attach_release_metadata(frame, dataset=tables[table], market_column="market")
    frame["vintage"] = "latest"
    frame["ingested_at"] = datetime.now(timezone.utc)
    write_frame(table, frame, mode="upsert", keys=["report_date", "market"])


def ingest_all(start_date=None) -> dict[str, int]:
    """Ingest the configured reports; any required failure fails the run.

    All currently configured markets are physical commodities and therefore
    default to Legacy and Disaggregated. Financial markets must explicitly set
    ``reports`` in MARKET_CONFIG to include TFF.
    """
    start_date = _start_date(start_date)
    init_schema()
    parsers = {"legacy": parse_legacy, "disagg": parse_disagg, "tff": parse_tff}
    counts, failures = {}, []
    for market, config in MARKET_CONFIG.items():
        print(f"CFTC ingestion: {market}")
        reports = config.get("reports", ("legacy", "disagg"))
        if isinstance(reports, str) or not reports:
            failures.append(f"{market}: reports must be a nonempty sequence")
            continue
        for report_type in reports:
            try:
                if report_type not in parsers:
                    raise ValueError(f"Unsupported configured CFTC report: {report_type}")
                frame = fetch_cftc_data(report_type, config["cftc_code"], start_date=start_date)
                rows = parsers[report_type](frame, market)
                upsert_rows(f"cot_{report_type}", rows)
                counts[f"{market}/{report_type}"] = len(rows)
            except Exception as exc:
                failures.append(f"{market}/{report_type}: {exc}")
    if failures:
        raise RuntimeError("Required CFTC ingestion failed:\n" + "\n".join(failures))
    if not counts:
        raise RuntimeError("No CFTC markets were configured or ingested")
    print(f"CFTC ingestion complete: {sum(counts.values())} rows across {len(counts)} datasets")
    return counts


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date", metavar="YYYY-MM-DD",
        help="Earliest observation date (or COT_START_DATE); default is all API history",
    )
    args = parser.parse_args(argv)
    try:
        start_date = _start_date(args.start_date)
    except ValueError as exc:
        parser.error(str(exc))
    return ingest_all(start_date=start_date)


if __name__ == "__main__":
    main()
