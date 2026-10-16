"""Explicit, sourced publication calendars. No weekday guessing.

CSV columns: dataset, market, report_date, release_at, source.
dataset is legacy/disagg/tff/eia. market may be '*' for a report-wide release.
release_at must include a timezone offset; dates are observation dates.
"""
import os
from pathlib import Path
import pandas as pd

CALENDAR_COLUMNS = ["dataset", "market", "report_date", "release_at", "source"]


def load_release_calendar(path=None) -> pd.DataFrame:
    path = path or os.environ.get("COT_RELEASE_CALENDAR")
    if not path:
        return pd.DataFrame(columns=CALENDAR_COLUMNS)
    frame = pd.read_csv(Path(path).expanduser(), dtype=str, keep_default_na=False)
    missing = set(CALENDAR_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Release calendar missing columns: {sorted(missing)}")
    frame = frame[CALENDAR_COLUMNS].copy()
    for name in CALENDAR_COLUMNS:
        frame[name] = frame[name].str.strip()
        if frame[name].eq("").any():
            raise ValueError(f"Release calendar has blank {name}")
    if not frame.dataset.isin(["legacy", "disagg", "tff", "eia"]).all():
        raise ValueError("Unknown release-calendar dataset")
    frame["report_date"] = pd.to_datetime(frame.report_date, format="%Y-%m-%d", errors="raise").dt.date
    releases = []
    for value in frame.release_at:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            raise ValueError("release_at must include an explicit timezone offset")
        releases.append(timestamp.tz_convert("UTC"))
    frame["release_at"] = pd.to_datetime(releases, utc=True)
    local_dates = frame.release_at.dt.tz_convert("America/New_York").dt.date
    if (local_dates < frame.report_date).any():
        raise ValueError("Publication precedes observation date")
    if frame.duplicated(["dataset", "market", "report_date"]).any():
        raise ValueError("Duplicate release-calendar keys")
    if (frame.source.str.startswith(("https://", "http://")) == False).any():
        raise ValueError("Calendar source must be an evidence URL")
    # Historical disaggregated/TFF backfills were not public on observation dates.
    # TFF launch announcement: CFTC release 5857-10 (22 July 2010).
    for dataset, first_release in [("disagg", "2009-09-04"), ("tff", "2010-07-22")]:
        bad = frame.dataset.eq(dataset) & (local_dates < pd.Timestamp(first_release).date())
        if bad.any():
            raise ValueError(f"{dataset} calendar claims a release before public launch")
    return frame


def attach_release_metadata(frame: pd.DataFrame, dataset: str, market_column="market", calendar_path=None):
    """Attach sourced timestamps; unmatched observations stay explicitly unknown.

    A sourced date does not establish that a downloaded value is first vintage.
    Caller-supplied metadata is overwritten to prevent accidental promotion.
    """
    if dataset not in {"legacy", "disagg", "tff", "eia"}:
        raise ValueError("Unknown dataset")
    result = frame.copy()
    result["release_at"] = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns, UTC]")
    result["release_source"] = pd.Series(None, index=result.index, dtype=object)
    result["release_quality"] = "unknown"
    result["vintage"] = "latest"
    result["ingested_at"] = pd.Timestamp.now(tz="UTC")
    if result.empty:
        return result
    calendar = load_release_calendar(calendar_path)
    calendar = calendar[calendar.dataset.eq(dataset)]
    if calendar.empty:
        return result
    lookup = {(r.market, r.report_date): r for r in calendar.itertuples()}
    dates = pd.to_datetime(result.report_date, errors="raise").dt.date
    for index, date in dates.items():
        market = result.at[index, market_column]
        row = lookup.get((market, date), lookup.get(("*", date)))
        if row is not None:
            result.at[index, "release_at"] = row.release_at
            result.at[index, "release_source"] = row.source
            result.at[index, "release_quality"] = "verified"
    return result


def apply_calendar(calendar_path=None):
    """Apply sourced dates to already downloaded rows without re-fetching APIs."""
    from src.db import get_conn, init_schema, write_frame
    init_schema()
    # Validate once, including an explicitly configured nonexistent file.
    calendar = load_release_calendar(calendar_path)
    if calendar.empty:
        raise ValueError("No release calendar supplied; set COT_RELEASE_CALENDAR")
    counts = {}
    for dataset, table, key in [("legacy", "cot_legacy", "market"),
                                ("disagg", "cot_disagg", "market"),
                                ("tff", "cot_tff", "market"), ("eia", "eia_inventory", "commodity")]:
        with get_conn() as conn:
            frame = conn.execute(f'SELECT * FROM "{table}"').fetchdf()
        if frame.empty:
            continue
        attached = attach_release_metadata(frame, dataset, key, calendar_path)
        unmatched = attached.release_quality.ne("verified")
        for column in ("release_at", "release_source", "release_quality"):
            attached.loc[unmatched, column] = frame.loc[unmatched, column]
        # Applying a calendar must not pretend that the values were fetched now.
        attached["ingested_at"] = frame["ingested_at"]
        attached["vintage"] = frame["vintage"]
        write_frame(table, attached)
        counts[table] = int(attached.release_quality.eq("verified").sum())
    return counts


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calendar", help="Sourced release calendar CSV")
    args = parser.parse_args()
    print(apply_calendar(args.calendar))
