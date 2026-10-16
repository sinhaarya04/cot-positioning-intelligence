"""Release-aware descriptive forward-return analysis, not a trading backtest.

Daily Yahoo prices are continuous-series close proxies with unknown intraday
availability. Entry therefore excludes the entire New York release date. Returns
omit contract rolls, costs, margin, and portfolio construction. Latest-vintage
input data and overlapping outcomes prevent causal or investment conclusions.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src import db
from src.signals import EVALUATION_VERSION, _utc_time

HORIZONS = {"fwd_1w": 5, "fwd_2w": 10, "fwd_4w": 20}
SIGNAL_NAMES = [
    "cot_index_52w", "cot_index_156w", "z_score_52w", "momentum_4w",
    "mgd_money_net", "comm_spec_divergence", "positioning_acceleration",
    "inventory_mismatch",
]
MAX_PRICE_GAP_DAYS = 4
DEFAULT_AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "forward_return_events.csv"


def _time_column(frame, name):
    values = frame.get(name, pd.Series(pd.NaT, index=frame.index))
    return pd.to_datetime(values.map(_utc_time), utc=True)


def build_forward_returns(signals: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Attach first permissible entry and 5/10/20 later observed-session exits.

    Timestamped settlements must occur strictly after disclosure. Proxy entry
    uses the first date strictly after the New York release date. Unknown bars
    are excluded. Four-day maximum calendar gaps reject stale/weekly series;
    this is a gap safeguard, not an exchange trading-calendar verification.
    Rejected rows are retained with reasons for the event-level audit.
    """
    if signals.empty:
        return signals.copy()
    signals, prices = signals.copy(), prices.copy()
    signals["release_at"] = _time_column(signals, "release_at")
    if not prices.empty:
        prices["price_date"] = pd.to_datetime(prices["price_date"], errors="raise").dt.normalize()
        prices["price_at"] = _time_column(prices, "price_at")
        prices["price_kind"] = prices.get("price_kind", "legacy_unknown")
        prices["source"] = prices.get("source", "unknown")
        prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
        if prices.duplicated(["market", "price_date"]).any():
            raise ValueError("Duplicate market/price_date observations must be resolved")
    rows = []
    for _, signal in signals.iterrows():
        row = signal.to_dict()
        row.update({"entry_date": pd.NaT, "entry_price_at": pd.NaT,
                    "price_t0": np.nan, "price_kind": None, "price_source": None,
                    "evaluation_engine_version": EVALUATION_VERSION, "return_status": "unknown_release"})
        for horizon in HORIZONS:
            row.update({horizon: np.nan, f"{horizon}_exit_date": pd.NaT,
                        f"{horizon}_exit_price_at": pd.NaT,
                        f"{horizon}_exit_price": np.nan, f"{horizon}_status": "no_entry"})
        release = signal["release_at"]
        signal_version = signal.get("evaluation_version")
        if not isinstance(signal_version, str) or signal_version != EVALUATION_VERSION:
            row["return_status"] = "stale_or_unversioned_signal"
            rows.append(row)
            continue
        eligible = signal.get("analysis_eligible", False)
        if (pd.isna(release) or signal.get("release_quality") != "verified"
                or pd.isna(eligible) or not bool(eligible)):
            rows.append(row)
            continue
        market_prices = prices.loc[prices["market"].eq(signal["market"])].copy() if not prices.empty else prices
        if market_prices.empty:
            row["return_status"] = "no_prices"
            rows.append(row)
            continue
        release_date = release.tz_convert("America/New_York").tz_localize(None).normalize()
        proxy = market_prices["price_kind"].eq("daily_close_proxy") & market_prices["price_date"].gt(release_date)
        settlement_dates = market_prices["price_at"].dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
        settled = (market_prices["price_kind"].eq("contract_settlement")
                   & market_prices["price_at"].gt(release)
                   & settlement_dates.eq(market_prices["price_date"]))
        candidates = market_prices.loc[proxy | settled].sort_values(["price_date", "price_at"], na_position="last")
        if candidates.empty:
            row["return_status"] = "no_price_after_release"
            rows.append(row)
            continue
        entry = candidates.iloc[0]
        row.update({"entry_date": entry["price_date"], "entry_price_at": entry["price_at"],
                    "price_t0": entry["close_price"], "price_kind": entry["price_kind"],
                    "price_source": entry["source"]})
        if (entry["price_date"] - release_date).days > MAX_PRICE_GAP_DAYS:
            row["return_status"] = "stale_entry"
            rows.append(row)
            continue
        if not np.isfinite(entry["close_price"]) or entry["close_price"] <= 0:
            row["return_status"] = "nonpositive_or_missing_entry"
            rows.append(row)
            continue
        # Never splice a proxy entry to a settlement exit or change price source.
        path = market_prices.loc[
            market_prices["price_kind"].eq(entry["price_kind"])
            & market_prices["source"].fillna("unknown").eq(entry["source"] if pd.notna(entry["source"]) else "unknown")
            & market_prices["price_date"].ge(entry["price_date"])
        ].sort_values("price_date").reset_index(drop=True)
        row["return_status"] = "eligible"
        for horizon, sessions in HORIZONS.items():
            if len(path) <= sessions:
                row[f"{horizon}_status"] = "insufficient_future_prices"
                continue
            window = path.iloc[:sessions + 1]
            exit_price = window.iloc[-1]
            row[f"{horizon}_exit_date"] = exit_price["price_date"]
            row[f"{horizon}_exit_price_at"] = exit_price["price_at"]
            row[f"{horizon}_exit_price"] = exit_price["close_price"]
            if window["price_date"].diff().dt.days.gt(MAX_PRICE_GAP_DAYS).any():
                row[f"{horizon}_status"] = "price_gap"
                continue
            if (not np.isfinite(window["close_price"].to_numpy(dtype=float)).all()
                    or window["close_price"].le(0).any()):
                row[f"{horizon}_status"] = "nonpositive_or_missing_price"
                continue
            if entry["price_kind"] == "contract_settlement":
                timestamps = window["price_at"]
                settlement_dates = timestamps.dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
                if (timestamps.isna().any() or not timestamps.is_monotonic_increasing
                        or timestamps.duplicated().any()
                        or not settlement_dates.eq(window["price_date"]).all()):
                    row[f"{horizon}_status"] = "invalid_settlement_times"
                    continue
            row[horizon] = (exit_price["close_price"] / entry["close_price"]) - 1
            row[f"{horizon}_status"] = "valid"
        rows.append(row)
    return pd.DataFrame(rows)


def load_signals_with_prices() -> pd.DataFrame:
    conn = db.get_conn()
    try:
        signals = conn.execute("SELECT * FROM signals ORDER BY market, report_date").fetchdf()
        prices = conn.execute("SELECT * FROM futures_prices ORDER BY market, price_date").fetchdf()
    finally:
        conn.close()
    return build_forward_returns(signals, prices)


def assign_expanding_thresholds(df: pd.DataFrame, signal_col: str, *, top_pct=0.1,
                                bot_pct=0.1, min_history=50) -> pd.DataFrame:
    """Use strictly earlier publication events, excluding the current release batch.

    Thresholds are fitted to past signal observations without looking at whether
    their forward outcomes exist. Future signals/outcomes cannot alter old bins.
    """
    if not (0 < top_pct < 0.5 and 0 < bot_pct < 0.5):
        raise ValueError("Tail fractions must be between zero and one half")
    if min_history < 1:
        raise ValueError("min_history must be positive")
    result = df.copy().reset_index(drop=True)
    result["top_threshold"] = np.nan
    result["bottom_threshold"] = np.nan
    result["threshold_history_n"] = 0
    result["threshold_status"] = "ineligible"
    result["tail"] = "none"
    if result.empty:
        return result
    result["release_at"] = _time_column(result, "release_at")
    values = pd.to_numeric(result[signal_col], errors="coerce")
    current_version = result.get("evaluation_version", pd.Series("legacy", index=result.index)).eq(EVALUATION_VERSION)
    eligible = (result["release_at"].notna() & result["release_quality"].eq("verified")
                & result["analysis_eligible"].fillna(False).astype(bool)
                & current_version.fillna(False)
                & np.isfinite(values))
    for _, group in result.groupby("market"):
        for idx in group.index[eligible.loc[group.index]]:
            previous = group.index[eligible.loc[group.index] & group["release_at"].lt(result.at[idx, "release_at"])]
            history = values.loc[previous]
            result.at[idx, "threshold_history_n"] = len(history)
            if len(history) < min_history:
                result.at[idx, "threshold_status"] = "warmup"
                continue
            bottom, top = history.quantile([bot_pct, 1 - top_pct]).tolist()
            result.at[idx, "bottom_threshold"], result.at[idx, "top_threshold"] = bottom, top
            if bottom >= top:
                result.at[idx, "threshold_status"] = "nonseparating_thresholds"
                continue
            result.at[idx, "threshold_status"] = "ready"
            if values.at[idx] >= top:
                result.at[idx, "tail"] = "top_decile"
            elif values.at[idx] <= bottom:
                result.at[idx, "tail"] = "bot_decile"
    return result


def summarize_signal(events: pd.DataFrame, signal_col: str, market: str, *, min_events=10) -> list[dict]:
    """Describe tail-conditioned underlying returns and the same-period baseline.

    Positive-return rate is not directional trading accuracy. Mean/std is not a
    strategy Sharpe ratio. Observations overlap; these summaries do not provide
    standard errors or significance claims.
    """
    results = []
    market_events = events.loc[events["market"].eq(market) & events["threshold_status"].eq("ready")]
    for horizon in HORIZONS:
        baseline = market_events.loc[market_events[horizon].notna()]
        if baseline.empty:
            continue
        for tail in ("top_decile", "bot_decile"):
            selected = baseline.loc[baseline["tail"].eq(tail)]
            if len(selected) < min_events:
                continue
            mean, std = selected[horizon].mean(), selected[horizon].std()
            results.append({
                "market": market, "signal_name": signal_col,
                "horizon": horizon.removeprefix("fwd_"), "threshold": tail,
                "n_signals": len(selected), "avg_return": float(mean),
                "positive_return_rate": float(selected[horizon].gt(0).mean()),
                "mean_over_std": float(mean / std) if std > 0 else None,
                "baseline_positive_rate": float(baseline[horizon].gt(0).mean()),
                "baseline_avg_return": float(baseline[horizon].mean()),
                "evaluation_version": EVALUATION_VERSION,
                "evaluation_start": baseline["release_at"].min(),
                "evaluation_end": baseline["release_at"].max(),
            })
    return results


def backtest_signal(df: pd.DataFrame, signal_col: str, market: str,
                    top_pct: float = 0.1, bot_pct: float = 0.1) -> list[dict]:
    if df.empty:
        return []
    events = assign_expanding_thresholds(df, signal_col, top_pct=top_pct, bot_pct=bot_pct)
    return summarize_signal(events, signal_col, market)


def run_backtest(audit_path: Path | str = DEFAULT_AUDIT_PATH) -> pd.DataFrame:
    """Save auditable events and replace summaries only when new results exist."""
    df = load_signals_with_prices()
    if df.empty:
        print("No signals; existing forward-return summaries were preserved.")
        return pd.DataFrame()
    all_results, audits = [], []
    for signal_name in SIGNAL_NAMES:
        if signal_name not in df:
            continue
        events = assign_expanding_thresholds(df, signal_name)
        events["signal_name"] = signal_name
        events["signal_value"] = pd.to_numeric(events[signal_name], errors="coerce")
        audits.append(events)
        for market in sorted(df["market"].unique()):
            all_results.extend(summarize_signal(events, signal_name, market))
    if audits:
        audit_path = Path(audit_path)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(audits, ignore_index=True).to_csv(audit_path, index=False)
        print(f"Event audit: {audit_path}")
    result = pd.DataFrame(all_results)
    if result.empty:
        print("Insufficient verified observations/outcomes; existing summaries were preserved.")
    else:
        db.write_frame("backtest_results", result, mode="replace")
        print(f"Saved {len(result)} descriptive forward-return summaries.")
    print("Latest-vintage data and daily close proxies are exploratory. No contract roll, cost, "
          "or portfolio accounting is implemented; nonpositive prices are excluded.")
    return result


if __name__ == "__main__":
    db.init_schema()
    run_backtest()
