"""Descriptive positioning features with explicit publication-time eligibility.

Verified rows use only observations whose releases were known at the row's
release time. Unknown dates remain useful for descriptive charts, but cannot
enter forward-return evaluation. Current API values are latest-vintage values;
verified release dates do not turn them into a first-release historical dataset.
"""

import numpy as np
import pandas as pd

from src import db

EVALUATION_VERSION = "release_aware_v1"
SIGNAL_COLUMNS = [
    "report_date", "market", "cot_index_52w", "cot_index_156w",
    "z_score_52w", "momentum_4w", "mgd_money_net", "comm_spec_divergence",
    "positioning_acceleration", "inventory_mismatch", "release_at",
    "release_quality", "inventory_release_at", "inventory_report_date",
    "disagg_release_at", "data_vintage", "analysis_eligible", "evaluation_version",
]


def _read(query: str) -> pd.DataFrame:
    conn = db.get_conn()
    try:
        return conn.execute(query).fetchdf()
    finally:
        conn.close()


def load_legacy_net_positions() -> pd.DataFrame:
    df = _read("SELECT * FROM cot_legacy ORDER BY market, report_date")
    df["net_spec"] = df["noncomm_long"] - df["noncomm_short"]
    df["net_comm"] = df["comm_long"] - df["comm_short"]
    return df


def load_disagg_positions() -> pd.DataFrame:
    df = _read("SELECT * FROM cot_disagg ORDER BY market, report_date")
    df["mgd_money_net"] = df["mgd_money_long"] - df["mgd_money_short"]
    return df


def load_eia_inventory() -> pd.DataFrame:
    return _read("SELECT *, commodity AS market FROM eia_inventory ORDER BY commodity, report_date")


def compute_cot_index(series: pd.Series, window: int) -> pd.Series:
    """Rolling min-max position in [0, 100], NOT an empirical percentile rank.

    ``window`` counts report observations. Half a window of valid observations
    is required. A constant valid window receives 50; missing values stay missing.
    """
    values = pd.to_numeric(series, errors="coerce").astype(float)
    rolling = values.rolling(window, min_periods=max(1, window // 2))
    minimum, maximum = rolling.min(), rolling.max()
    width = maximum - minimum
    result = 100 * (values - minimum) / width
    return result.mask(width.eq(0) & values.notna(), 50.0)


def compute_z_score(series: pd.Series, window: int) -> pd.Series:
    """Index-preserving rolling sample-standard-deviation z-score."""
    values = pd.to_numeric(series, errors="coerce").astype(float)
    rolling = values.rolling(window, min_periods=max(1, window // 2))
    mean, std = rolling.mean(), rolling.std()
    result = (values - mean) / std
    return result.mask(std.eq(0) & values.notna(), 0.0)


def compute_momentum(series: pd.Series, window: int) -> pd.Series:
    """Change over ``window`` observations; missing observations stay missing."""
    return series.diff(window)


def compute_acceleration(series: pd.Series, window: int = 4) -> pd.Series:
    """Change in the observation-based momentum measure."""
    return series.diff(window).diff(window)


def compute_comm_spec_divergence(df: pd.DataFrame) -> pd.Series:
    oi = pd.to_numeric(df["open_interest"], errors="coerce")
    return (df["net_comm"] - df["net_spec"]) / oi.where(oi > 0)


def _utc_time(value):
    """Fail closed on missing/naive timestamps instead of assuming a timezone."""
    if pd.isna(value):
        return pd.NaT
    try:
        timestamp = pd.Timestamp(value)
        return timestamp.tz_convert("UTC") if timestamp.tzinfo is not None else pd.NaT
    except (ValueError, TypeError):
        return pd.NaT


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if frame.empty:
        return frame
    frame["report_date"] = pd.to_datetime(frame["report_date"], errors="raise").dt.normalize()
    if frame["report_date"].isna().any() or frame["market"].isna().any():
        raise ValueError("Signals require nonmissing market and report_date keys")
    if frame.duplicated(["market", "report_date"]).any():
        raise ValueError("Duplicate market/report_date observations must be resolved before signal computation")
    release = frame.get("release_at", pd.Series(pd.NaT, index=frame.index))
    frame["release_at"] = pd.to_datetime(release.map(_utc_time), utc=True)
    quality = frame.get("release_quality", pd.Series("unknown", index=frame.index))
    # A timestamp preceding the observation date is not plausible publication evidence.
    valid = quality.eq("verified") & frame["release_at"].notna()
    valid &= frame["release_at"].dt.tz_convert("America/New_York").dt.tz_localize(None).ge(frame["report_date"])
    frame["release_quality"] = np.where(valid, "verified", "unknown")
    frame.loc[~valid, "release_at"] = pd.NaT
    return frame.sort_values("report_date").reset_index(drop=True)


def _history(frame: pd.DataFrame, report_date, decision) -> pd.DataFrame:
    mask = frame["report_date"].le(report_date)
    if pd.notna(decision):
        mask &= frame["release_quality"].eq("verified") & frame["release_at"].le(decision)
    return frame.loc[mask].sort_values("report_date")


def _calendar_change(history: pd.DataFrame, date, weeks: int) -> float:
    """Require the exact earlier weekly observation rather than crossing gaps."""
    values = history.set_index("report_date")["net_spec"]
    earlier = date - pd.Timedelta(weeks=weeks)
    return values.get(date, np.nan) - values.get(earlier, np.nan)


def build_signals(legacy: pd.DataFrame, disagg: pd.DataFrame, eia: pd.DataFrame) -> pd.DataFrame:
    """Build features without performing I/O or inventing release dates.

    Rolling levels use up to 52/156 available report observations, which can span
    more calendar weeks during gaps. Four-week changes require exact calendar
    observations. Inventory joins run backward on verified publication timestamps.
    """
    legacy, disagg, eia = map(_prepare, (legacy, disagg, eia))
    if legacy.empty:
        return pd.DataFrame(columns=SIGNAL_COLUMNS)
    if "net_spec" not in legacy:
        legacy["net_spec"] = legacy["noncomm_long"] - legacy["noncomm_short"]
    if "net_comm" not in legacy:
        legacy["net_comm"] = legacy["comm_long"] - legacy["comm_short"]
    if not disagg.empty and "mgd_money_net" not in disagg:
        disagg["mgd_money_net"] = disagg["mgd_money_long"] - disagg["mgd_money_short"]
    rows = []
    for market, market_legacy in legacy.groupby("market", sort=True):
        market_disagg = disagg.loc[disagg["market"].eq(market)] if not disagg.empty else disagg
        market_eia = eia.loc[eia["market"].eq(market)] if not eia.empty else eia
        for _, row in market_legacy.iterrows():
            decision = row["release_at"]
            history = _history(market_legacy, row["report_date"], decision)
            positions = history["net_spec"]
            z_score = compute_z_score(positions, 52).iloc[-1]
            momentum = _calendar_change(history, row["report_date"], 4)
            previous_momentum = _calendar_change(history, row["report_date"] - pd.Timedelta(weeks=4), 4)
            result = dict.fromkeys(SIGNAL_COLUMNS, None)
            result.update({
                "report_date": row["report_date"], "market": market,
                "cot_index_52w": compute_cot_index(positions, 52).iloc[-1],
                "cot_index_156w": compute_cot_index(positions, 156).iloc[-1],
                "z_score_52w": z_score, "momentum_4w": momentum,
                "comm_spec_divergence": compute_comm_spec_divergence(history).iloc[-1],
                "positioning_acceleration": momentum - previous_momentum,
                "release_at": decision, "release_quality": row["release_quality"],
                "analysis_eligible": row["release_quality"] == "verified",
                "data_vintage": "latest", "evaluation_version": EVALUATION_VERSION,
            })
            if pd.notna(decision):
                if not market_disagg.empty:
                    match = market_disagg.loc[
                        market_disagg["report_date"].eq(row["report_date"])
                        & market_disagg["release_quality"].eq("verified")
                        & market_disagg["release_at"].le(decision)
                        # Disaggregated data before launch is a retrospective backfill.
                        & market_disagg["release_at"].ge(pd.Timestamp("2009-09-04", tz="UTC"))
                    ]
                    if not match.empty:
                        result["mgd_money_net"] = match.iloc[-1]["mgd_money_net"]
                        result["disagg_release_at"] = match.iloc[-1]["release_at"]
                if not market_eia.empty:
                    available = market_eia.loc[
                        market_eia["release_quality"].eq("verified")
                        & market_eia["release_at"].le(decision)
                    ].sort_values(["release_at", "report_date"])
                    if not available.empty:
                        latest = available.iloc[-1]
                        inv_history = _history(market_eia, latest["report_date"], latest["release_at"])
                        inv_z = compute_z_score(inv_history["inventory_level"], 52).iloc[-1]
                        result["inventory_mismatch"] = inv_z * z_score
                        result["inventory_release_at"] = latest["release_at"]
                        result["inventory_report_date"] = latest["report_date"]
            rows.append(result)
    return pd.DataFrame(rows, columns=SIGNAL_COLUMNS)


def compute_signals() -> pd.DataFrame:
    """Replace signals atomically only after a successful, nonempty computation."""
    result = build_signals(load_legacy_net_positions(), load_disagg_positions(), load_eia_inventory())
    if result.empty:
        print("No legacy observations; existing signals were preserved.")
        return result
    db.write_frame("signals", result, mode="replace")
    eligible = int(result["analysis_eligible"].sum())
    print(f"Computed {len(result)} descriptive signals; {eligible} have verified release timing.")
    print("Latest-vintage data: historical revision bias remains possible.")
    return result


if __name__ == "__main__":
    db.init_schema()
    compute_signals()
