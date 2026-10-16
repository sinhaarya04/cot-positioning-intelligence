"""Run the data/analysis stages and save a local reproducibility manifest."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import uuid

from src import db

ROOT = Path(__file__).resolve().parents[1]


def source_identity():
    digest = hashlib.sha256()
    for path in sorted([*ROOT.joinpath("src").glob("*.py"), ROOT / "pyproject.toml", ROOT / "requirements.lock"]):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return {"git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
            "source_sha256": digest.hexdigest()}


def coverage():
    result = {}
    with db.get_conn() as conn:
        for table, identity, date in [("cot_legacy", "market", "report_date"),
                                      ("cot_disagg", "market", "report_date"),
                                      ("eia_inventory", "commodity", "report_date"),
                                      ("futures_prices", "market", "price_date")]:
            extra = ", SUM(CASE WHEN release_quality = 'verified' THEN 1 ELSE 0 END) AS verified_releases" if table != "futures_prices" else ""
            frame = conn.execute(f'SELECT "{identity}" AS market, COUNT(*) AS n, MIN("{date}") AS first_date, '
                                 f'MAX("{date}") AS last_date {extra} FROM "{table}" GROUP BY "{identity}"').fetchdf()
            result[table] = json.loads(frame.to_json(orient="records", date_format="iso"))
    return result


def run_pipeline(*, skip_ingest=False, skip_eia=False, start_date=None, output_dir=None):
    from src.ingest_cftc import ingest_all as ingest_cftc
    from src.ingest_prices import ingest_all as ingest_prices
    from src.signals import compute_signals
    from src.backtest import run_backtest
    output_dir = Path(output_dir or ROOT / "output")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    record = {"run_id": run_id, "started_at": started.isoformat(), **source_identity(),
              "config": {"skip_ingest": skip_ingest, "skip_eia": skip_eia, "start_date": start_date},
              "dependencies": {name: version(name) for name in ("pandas", "numpy", "duckdb", "requests", "yfinance")},
              "status": "running", "limitations": ["latest-vintage inputs", "daily continuous price proxies",
                                                       "no contract roll/cost/portfolio accounting"]}
    manifest = output_dir / f"run-{run_id}.json"
    try:
        db.init_schema()
        if not skip_ingest:
            record["cftc_rows"] = ingest_cftc(start_date=start_date)
            record["price_inventory_rows"] = ingest_prices(skip_eia=skip_eia)
        signals = compute_signals()
        result = run_backtest(audit_path=output_dir / f"events-{run_id}.csv")
        record["signal_rows"] = len(signals)
        record["summary_rows"] = len(result)
        record["coverage"] = coverage()
        record["status"] = "complete" if not result.empty else "needs_release_evidence_or_history"
        return record
    except Exception as error:
        record["status"] = "failed"
        # Never serialize provider exception URLs or request credentials.
        record["error_type"] = type(error).__name__
        raise
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        manifest.write_text(json.dumps(record, indent=2, default=str) + "\n")
        print(f"Run manifest: {manifest}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-ingest", action="store_true", help="Recompute from the local database only")
    parser.add_argument("--skip-eia", action="store_true", help="Explicitly omit EIA ingestion")
    parser.add_argument("--start-date", help="CFTC observation-date lower bound, YYYY-MM-DD")
    args = parser.parse_args(argv)
    try:
        result = run_pipeline(**vars(args))
    except Exception as error:
        parser.exit(1, f"Pipeline failed ({type(error).__name__}); inspect the stage output.\n")
    if result["status"] != "complete":
        parser.exit(2, "Data/features saved, but corrected evaluation needs sourced release dates and enough history.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
