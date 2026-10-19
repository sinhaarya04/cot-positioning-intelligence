"""Read-only research-data audit; evidence dates are never promoted to timestamps.

Run from a repository checkout. The output is a coverage diagnostic, not a
forecasting sample, and does not update release metadata or evaluate returns.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import duckdb
import pandas as pd

from src.db import DB_PATH, MARKET_CONFIG

ROOT = Path(__file__).resolve().parents[1]
MARKETS = ("CRUDE_OIL", "NATURAL_GAS")
COLUMNS = ["evidence_id", "dataset", "market", "report_date", "release_date",
           "release_at", "status", "source", "note"]
TABLES = {"legacy": ("cot_legacy", "market"), "disagg": ("cot_disagg", "market"),
          "eia": ("eia_inventory", "commodity")}
EVENT_COLUMNS = ["dataset", "market", "report_date", "evidence_status", "evidence_ids",
                 "release_date", "release_at", "document_publication_date", "availability_lower_bound",
                 "availability_upper_bound", "database_release_quality", "metadata_conflict",
                 "declared_vintage", "series_id"]


def _date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Evidence dates must use YYYY-MM-DD")
    return date.fromisoformat(value)


def load_evidence(paths):
    """Validate curated ledger syntax. URLs are references, not authentication.

    Superseded/planned entries remain visible but cannot substantiate availability.
    Conflicting confirmed entries are retained for explicit audit exclusion.
    """
    rows, identifiers = [], set()
    for path in paths:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        if set(frame.columns) != set(COLUMNS):
            raise ValueError(f"Evidence columns must be exactly {COLUMNS}")
        for row in frame[COLUMNS].to_dict("records"):
            row = {key: value.strip() for key, value in row.items()}
            if any(not row[key] for key in COLUMNS if key != "release_at"):
                raise ValueError("Blank required evidence field")
            if row["evidence_id"] in identifiers:
                raise ValueError("Duplicate evidence_id")
            identifiers.add(row["evidence_id"])
            if row["dataset"] not in {"legacy", "disagg", "tff", "eia"}:
                raise ValueError("Unknown evidence dataset")
            if row["market"] not in {*MARKET_CONFIG, "*"}:
                raise ValueError("Unknown evidence market")
            if row["dataset"] == "eia" and row["market"] not in MARKETS:
                raise ValueError("EIA evidence must identify an energy market")
            if row["status"] not in {"confirmed", "scheduled", "superseded", "available_by"}:
                raise ValueError("Unknown evidence status")
            if row["status"] == "available_by" and row["release_at"]:
                raise ValueError("Available-by evidence must be a document date without an inferred timestamp")
            report, release = _date(row["report_date"]), _date(row["release_date"])
            if release < report:
                raise ValueError("Evidence publication precedes observation")
            launch = {"disagg": date(2009, 9, 4), "tff": date(2010, 7, 22)}
            if row["dataset"] in launch and release < launch[row["dataset"]]:
                raise ValueError("Evidence claims publication before dataset launch")
            if row["release_at"]:
                timestamp = pd.Timestamp(row["release_at"])
                if timestamp.tzinfo is None:
                    raise ValueError("Evidence timestamp must have an explicit timezone")
                if timestamp.tz_convert("America/New_York").date() != release:
                    raise ValueError("Timestamp does not match New York release_date")
                row["release_at"] = timestamp.tz_convert("UTC").isoformat()
            url = urlsplit(row["source"])
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise ValueError("Evidence source must be a public HTTP(S) URL")
            rows.append(row)
    return rows


def resolve_evidence(evidence, dataset, market, report_date):
    matches = [row for row in evidence if row["dataset"] == dataset
               and row["market"] in {market, "*"} and row["report_date"] == report_date]
    confirmed = [row for row in matches if row["status"] == "confirmed"]
    # Market-specific confirmed evidence takes precedence over report-wide rows.
    specific = [row for row in confirmed if row["market"] == market]
    confirmed = specific or confirmed
    available = [row for row in matches if row["status"] == "available_by"]
    ids = ";".join(sorted(row["evidence_id"] for row in (confirmed + available if confirmed else matches)))
    empty = {"evidence_ids": ids, "release_date": None, "release_at": None, "document_publication_date": None,
             "availability_lower_bound": None, "availability_upper_bound": None}
    if not confirmed:
        if available:
            earliest = min(row["release_date"] for row in available)
            end = pd.Timestamp(_date(earliest) + timedelta(days=1)).tz_localize("America/New_York")
            return {**empty, "evidence_status": "documented_by_date", "document_publication_date": earliest,
                    "availability_upper_bound": end.tz_convert("UTC").isoformat()}
        status = "scheduled_only" if any(r["status"] == "scheduled" for r in matches) else (
            "superseded_only" if matches else "missing")
        return {**empty, "evidence_status": status}
    dates = {r["release_date"] for r in confirmed}
    times = {r["release_at"] for r in confirmed if r["release_at"]}
    if len(dates) > 1 or len(times) > 1:
        return {**empty, "evidence_status": "conflict"}
    release_date = next(iter(dates))
    if available:
        by_date = min(row["release_date"] for row in available)
        upper = pd.Timestamp(_date(by_date) + timedelta(days=1)).tz_localize("America/New_York")
        lower = pd.Timestamp(next(iter(times))) if times else pd.Timestamp(release_date).tz_localize("America/New_York")
        if lower >= upper:
            return {**empty, "evidence_status": "conflict"}
    if times:
        stamp = next(iter(times))
        return {**empty, "evidence_status": "confirmed_timestamp", "release_date": release_date,
                "release_at": stamp, "availability_lower_bound": stamp,
                "availability_upper_bound": stamp}
    # A date means an interval, not the generic scheduled publication time.
    start = pd.Timestamp(release_date).tz_localize("America/New_York")
    end = pd.Timestamp(_date(release_date) + timedelta(days=1)).tz_localize("America/New_York")
    return {**empty, "evidence_status": "confirmed_date", "release_date": release_date,
            "availability_lower_bound": start.tz_convert("UTC").isoformat(),
            "availability_upper_bound": end.tz_convert("UTC").isoformat()}


def _text(value, default="unknown"):
    return default if value is None or pd.isna(value) else str(value)


def audit_frames(frames, evidence):
    """Pure coverage calculation, including conservative inventory-date overlap.

    Overlap counts mean only that a sourced inventory issue was available by the
    start of the COT release interval. They do not validate values, freshness,
    contract targets, feature histories, or a research-ready common sample.
    """
    events, summaries = [], []
    for dataset, (table, identity) in TABLES.items():
        frame = frames.get(table, pd.DataFrame())
        for market in MARKETS:
            part = frame.loc[frame[identity].eq(market)] if identity in frame else pd.DataFrame()
            group = []
            if not part.empty and "report_date" not in part:
                raise ValueError(f"{table} missing report_date")
            for row in part.to_dict("records"):
                if pd.isna(row["report_date"]):
                    raise ValueError(f"{table} has a missing report_date")
                observed = pd.Timestamp(row["report_date"]).date().isoformat()
                resolved = resolve_evidence(evidence, dataset, market, observed)
                quality = _text(row.get("release_quality"))
                conflict = False
                stored = row.get("release_at")
                if quality == "verified" and resolved["availability_upper_bound"]:
                    conflict = stored is None or pd.isna(stored)
                    if not conflict:
                        timestamp = pd.Timestamp(stored)
                        conflict = timestamp.tzinfo is None
                        if not conflict and resolved["release_date"]:
                            conflict = timestamp.tz_convert("America/New_York").date().isoformat() != resolved["release_date"]
                            if resolved["release_at"]:
                                conflict |= timestamp != pd.Timestamp(resolved["release_at"])
                        elif not conflict:
                            conflict = timestamp >= pd.Timestamp(resolved["availability_upper_bound"])
                event = {"dataset": dataset, "market": market, "report_date": observed, **resolved,
                         "database_release_quality": quality, "metadata_conflict": bool(conflict),
                         "declared_vintage": _text(row.get("vintage")),
                         "series_id": _text(row.get("series_id"), "")}
                events.append(event)
                group.append(event)
            confirmed = [e for e in group if e["evidence_status"].startswith("confirmed_") and not e["metadata_conflict"]]
            available = sum(e["evidence_status"] == "documented_by_date" and not e["metadata_conflict"] for e in group)
            summaries.append({"dataset": dataset, "market": market, "rows": len(group),
                              "first_observation": min((e["report_date"] for e in group), default=None),
                              "last_observation": max((e["report_date"] for e in group), default=None),
                              "confirmed_date_rows": sum(e["evidence_status"] == "confirmed_date" for e in confirmed),
                              "confirmed_timestamp_rows": sum(e["evidence_status"] == "confirmed_timestamp" for e in confirmed),
                              "documented_by_date_rows": available,
                              "without_publication_evidence_rows": len(group) - len(confirmed) - available,
                              "metadata_conflicts": sum(e["metadata_conflict"] for e in group),
                              "database_verified_labels": sum(e["database_release_quality"] == "verified" for e in group),
                              "declared_vintages": pd.Series([e["declared_vintage"] for e in group], dtype=str).value_counts().to_dict(),
                              "series_ids": sorted({e["series_id"] for e in group if e["series_id"]})})
    overlap = []
    for market in MARKETS:
        released = [e for e in events if e["market"] == market and not e["metadata_conflict"]
                    and (e["evidence_status"].startswith("confirmed_") or e["evidence_status"] == "documented_by_date")]
        stocks = [e for e in released if e["dataset"] == "eia"]
        # A later document containing COT observations gives only an upper bound.
        # Without a release lower bound we cannot freeze a pre-COT baseline.
        for cot in (e for e in released if e["dataset"] == "disagg" and e["availability_lower_bound"]):
            cutoff = pd.Timestamp(cot["availability_lower_bound"])
            known = [e for e in stocks if pd.Timestamp(e["availability_upper_bound"]) < cutoff or (
                e["evidence_status"] != "confirmed_timestamp" and pd.Timestamp(e["availability_upper_bound"]) == cutoff)]
            # Pick the newest observation, not a revision of an older issue.
            latest = max(known, key=lambda e: e["report_date"], default=None)
            overlap.append({"market": market, "cot_report_date": cot["report_date"],
                            "cot_release_date": cot["release_date"],
                            "inventory_report_date": latest["report_date"] if latest else None,
                            "inventory_age_days_at_release": (_date(cot["release_date"]) - _date(latest["report_date"])).days if latest else None})
    prices = frames.get("futures_prices", pd.DataFrame())
    price_summary = []
    for market in MARKETS:
        part = prices.loc[prices.market.eq(market)] if "market" in prices else pd.DataFrame()
        dates = pd.to_datetime(part.price_date) if "price_date" in part else pd.Series(dtype="datetime64[ns]")
        price_summary.append({"market": market, "rows": len(part),
                              "first_date": dates.min().date().isoformat() if dates.notna().any() else None,
                              "last_date": dates.max().date().isoformat() if dates.notna().any() else None,
                              "price_kinds": part.price_kind.fillna("unknown").value_counts().to_dict() if "price_kind" in part else {"unknown": len(part)}})
    return {"coverage": summaries, "prices": price_summary, "inventory_overlap": overlap}, events


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_audit(db_path, evidence_paths, output_dir):
    db_path = Path(db_path).expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"Existing database required: {db_path}")
    if Path(str(db_path) + ".wal").exists():
        raise ValueError("Audit requires a checkpointed database without a WAL file")
    evidence_paths = [Path(p).expanduser().resolve() for p in evidence_paths]
    output_dir = Path(output_dir).expanduser()
    output_names = ("research-audit.json", "research-audit.md", "release-coverage.csv")
    if any((output_dir / name).resolve() in {db_path, *evidence_paths} for name in output_names):
        raise ValueError("Audit output must not overwrite a database or evidence input")
    evidence_hashes = {p: _hash(p) for p in evidence_paths}
    evidence = load_evidence(evidence_paths)
    before = _hash(db_path)
    frames = {}
    with duckdb.connect(str(db_path), read_only=True) as conn:
        existing = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
        for table in [*(table for table, _ in TABLES.values()), "futures_prices"]:
            if table in existing:
                frames[table] = conn.execute(f'SELECT * FROM "{table}"').fetchdf()
    if _hash(db_path) != before:
        raise RuntimeError("Database changed while auditing; rerun on a stable snapshot")
    if any(_hash(p) != digest for p, digest in evidence_hashes.items()):
        raise RuntimeError("Evidence changed while auditing; rerun on stable inputs")
    report, events = audit_frames(frames, evidence)
    report.update({"audit_version": "1", "generated_at": datetime.now(timezone.utc).isoformat(),
                   "database_file": db_path.name, "database_sha256": before,
                   "missing_tables": sorted(set([t for t, _ in TABLES.values()] + ["futures_prices"]) - set(frames)),
                   "evidence_files": [{"file": p.name, "sha256": digest} for p, digest in evidence_hashes.items()],
                   "audit_source_sha256": _hash(__file__),
                   "evidence_rows": len(evidence),
                   "evidence_status_counts": pd.Series([r["status"] for r in evidence], dtype=str).value_counts().to_dict(),
                   "research_status": "not_established",
                   "limitations": [
                       "Curated evidence is partial; uncovered rows are not proof of absent historical publication.",
                       "Date-only evidence is an interval in America/New_York, never an exact release timestamp.",
                       "Secondary issue or correction-notice dates establish an available-by bound only; original release dates remain unknown.",
                       "No database release metadata or evaluation eligibility is changed by this audit.",
                       "Declared vintage labels are not reconciliation of values to original releases.",
                       "Inventory overlap is a timing diagnostic, not a validated feature or common research sample.",
                       "The current price table lacks individual contracts, expiries, multipliers and a maturity curve.",
                       "Current national crude stocks are not the proposed Cushing seasonal-state series.",
                       "Training history, statistical power, data rights and model evaluation remain unassessed."]})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "research-audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    pd.DataFrame(events, columns=EVENT_COLUMNS).to_csv(output_dir / "release-coverage.csv", index=False)
    lines = ["# Research-data coverage audit", "", "Research readiness: **not established**.", "",
             "This read-only diagnostic does not change the database or establish an eligible forecasting sample.", "",
             "| Dataset | Market | Rows | Date evidence | Timestamp evidence | Available-by only | No evidence / conflict |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for row in report["coverage"]:
        lines.append(f"| {row['dataset']} | {row['market']} | {row['rows']} | {row['confirmed_date_rows']} | {row['confirmed_timestamp_rows']} | {row['documented_by_date_rows']} | {row['without_publication_evidence_rows']} |")
    lines += ["", "## Interpretation", "", *[f"- {item}" for item in report["limitations"]], "",
              "See research-audit.json for input hashes, price coverage and conservative inventory overlap, and release-coverage.csv for every observation.", ""]
    (output_dir / "research-audit.md").write_text("\n".join(lines))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("COT_DB_PATH") or str(DB_PATH), help="Existing checkpointed DuckDB file; opened read-only")
    parser.add_argument("--evidence", nargs="+", default=[str(ROOT / "config/release_evidence_cftc.csv"), str(ROOT / "config/release_evidence_eia.csv")])
    parser.add_argument("--output-dir", default=str(ROOT / "output/research-audit"))
    args = parser.parse_args(argv)
    try:
        report = run_audit(args.db, args.evidence, args.output_dir)
    except (ValueError, OSError, RuntimeError, duckdb.Error) as error:
        parser.exit(1, f"Research audit failed: {error}\n")
    print(f"Audit complete: {report['evidence_rows']} ledger rows; research readiness not established. Outputs: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
