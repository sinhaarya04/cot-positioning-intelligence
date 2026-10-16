"""Streamlit research dashboard: streamlit run src/dashboard.py."""

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db import MARKET_CONFIG, get_conn, init_schema
from src.llm_anomaly import PROMPT_VERSION, validate_response

EVALUATION_VERSION = "release_aware_v1"
STALE_AFTER_DAYS = 14


def _load_table(table):
    if table not in {"signals", "futures_prices", "backtest_results", "llm_anomalies"}:
        raise ValueError("Unsupported dashboard table")
    conn = get_conn()
    try:
        return conn.execute(f"SELECT * FROM {table}").fetchdf()
    finally:
        conn.close()


def load_signals():
    frame = _load_table("signals")
    frame["report_date"] = pd.to_datetime(frame["report_date"])
    frame = frame[frame["evaluation_version"].eq(EVALUATION_VERSION)]
    return frame.sort_values(["market", "report_date"])


def load_prices():
    frame = _load_table("futures_prices")
    frame["price_date"] = pd.to_datetime(frame["price_date"])
    # Old Monday-labelled weekly bars cannot be presented as daily prices.
    if "price_kind" not in frame:
        return frame.iloc[:0].copy()
    frame = frame[frame["price_kind"].isin(["daily_close_proxy", "contract_settlement"])]
    return frame.sort_values(["market", "price_date"])


def validated_backtest_results(frame):
    """Never present legacy hit-rate/Sharpe fields as corrected evaluation."""
    if "evaluation_version" not in frame:
        return frame.iloc[:0].copy()
    return frame[frame["evaluation_version"].eq(EVALUATION_VERSION)].copy()


def load_backtest():
    return validated_backtest_results(_load_table("backtest_results"))


def load_anomalies():
    frame = _load_table("llm_anomalies")
    return frame.sort_values(["report_date", "market"], ascending=[False, True])


def latest_per_market(frame):
    if frame.empty:
        return frame.copy()
    return frame.sort_values("report_date").drop_duplicates("market", keep="last").sort_values("market")


def load_latest_signals():
    return latest_per_market(load_signals())


def add_freshness(frame, now=None):
    """Expose calendar age and relative ingestion lag; age >14 days is flagged."""
    frame = frame.copy()
    dates = pd.to_datetime(frame["report_date"], utc=True).dt.normalize()
    current = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    current = current.tz_localize("UTC") if current.tzinfo is None else current.tz_convert("UTC")
    frame["report_age_days"] = (current.normalize() - dates).dt.days
    frame["lag_vs_latest_days"] = (dates.max() - dates).dt.days
    frame["freshness"] = "Recent observation"
    frame.loc[frame["lag_vs_latest_days"].gt(0), "freshness"] = "Lagging other markets"
    frame.loc[frame["report_age_days"].gt(STALE_AFTER_DAYS), "freshness"] = "Stale observation"
    frame.loc[frame["report_age_days"].lt(0), "freshness"] = "Future observation date"
    return frame


def valid_anomaly_rows(frame):
    """Hide unvalidated legacy and malformed stored model output."""
    valid = []
    for _, row in frame.iterrows():
        if not isinstance(row.get("prompt_version"), str) or row["prompt_version"] != PROMPT_VERSION:
            continue
        try:
            payload = {
                "market": row["market"],
                "report_date": pd.Timestamp(row["report_date"]).date().isoformat(),
                "signal_type": row["signal_type"],
                "directional_bias": row["directional_bias"],
                "confidence": row["confidence"],
                "narrative": row["narrative"],
            }
            # DuckDB integer columns yield numpy integer scalars, unlike JSON.
            bias = payload["directional_bias"]
            if pd.notna(bias) and not isinstance(bias, bool) and int(bias) == bias:
                payload["directional_bias"] = int(bias)
            validate_response(json.dumps(payload), row["market"], row["report_date"])
            valid.append(row)
        except (ValueError, TypeError, OverflowError):
            continue
    return pd.DataFrame(valid, columns=frame.columns)


def _show_history(signals, prices, market, lookback):
    st.header(f"{market} - Positioning History")
    sample = signals[signals["market"].eq(market)].copy()
    if sample.empty:
        st.info("No signals for this market. Ingest source data and run python -m src.signals.")
        return
    cutoff = sample["report_date"].max() - pd.Timedelta(weeks=lookback)
    sample = sample[sample["report_date"].ge(cutoff)]
    price_sample = prices[prices["market"].eq(market) & prices["price_date"].ge(cutoff)]
    if price_sample.empty:
        st.info("No current daily price data for this period. Legacy bars with unknown timing are hidden; run price ingestion.")
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        subplot_titles=("Daily price proxy", "COT index (52-report min-max)", "Z-score (52-report)"))
    fig.add_trace(go.Scatter(x=price_sample["price_date"], y=price_sample["close_price"], name="Price proxy"), row=1, col=1)
    fig.add_trace(go.Scatter(x=sample["report_date"], y=sample["cot_index_52w"], name="COT index"), row=2, col=1)
    fig.add_trace(go.Bar(x=sample["report_date"], y=sample["z_score_52w"], name="Z-score"), row=3, col=1)
    fig.update_layout(height=650, showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.caption("Positioning is plotted on its observation date. That date is earlier than publication; charts are descriptive.")
    st.subheader("Managed money and commercial-speculative divergence")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True)
    fig.add_trace(go.Bar(x=sample["report_date"], y=sample["mgd_money_net"], name="Managed-money net contracts"), row=1, col=1)
    fig.add_trace(go.Scatter(x=sample["report_date"], y=sample["comm_spec_divergence"], name="Commercial-speculative divergence"), row=2, col=1)
    fig.update_layout(height=450)
    st.plotly_chart(fig, width="stretch")


def _show_backtest(markets):
    st.header("Conditional underlying-return statistics")
    st.caption("These are exploratory forward returns conditioned on past-defined signal thresholds. "
               "They are not a trading strategy, a strategy hit rate, or a portfolio Sharpe ratio. "
               "Overlapping horizons and multiple comparisons require further inference.")
    raw = _load_table("backtest_results")
    results = validated_backtest_results(raw)
    if len(raw) > len(results):
        st.warning(f"Hidden {len(raw) - len(results)} legacy evaluation rows. Recompute with python -m src.backtest.")
    if results.empty:
        st.info("No corrected evaluations available. Release metadata and daily prices are required before running python -m src.backtest.")
        return
    left, right = st.columns(2)
    market = left.selectbox("Market", ["ALL"] + markets, key="bt_market")
    horizon = right.selectbox("Horizon", ["ALL", "1w", "2w", "4w"], key="bt_horizon")
    if market != "ALL":
        results = results[results["market"].eq(market)]
    if horizon != "ALL":
        results = results[results["horizon"].eq(horizon)]
    columns = ["market", "signal_name", "horizon", "threshold", "n_signals", "positive_return_rate",
               "baseline_positive_rate", "avg_return", "baseline_avg_return", "mean_over_std",
               "evaluation_start", "evaluation_end", "evaluation_version"]
    display = results[[col for col in columns if col in results]].rename(columns={
        "positive_return_rate": "Positive underlying-return fraction",
        "baseline_positive_rate": "Baseline positive-return fraction (eligible dates)",
        "avg_return": "Mean underlying return",
        "baseline_avg_return": "Baseline mean return (eligible dates)",
        "mean_over_std": "Mean / standard deviation (unannualized)",
    })
    st.dataframe(display, width="stretch", hide_index=True)


def _show_anomalies():
    st.header("Optional LLM positioning explanations")
    st.caption("Model interpretations and self-rated confidence are unvalidated. They are not calibrated probabilities or return forecasts.")
    raw = load_anomalies()
    frame = valid_anomaly_rows(raw)
    if len(frame) < len(raw):
        st.warning(f"Hidden {len(raw) - len(frame)} older or invalid model outputs. Regenerate explanations with the current validator.")
    if frame.empty:
        st.info("No validated explanations available. Optional command: python -m src.llm_anomaly (requires the LLM dependencies and model).")
        return
    show_history = st.checkbox("Show historical explanations", value=False)
    if not show_history:
        frame = latest_per_market(frame)
    frame = add_freshness(frame)
    for _, row in frame.iterrows():
        report_date = pd.Timestamp(row["report_date"]).date().isoformat()
        title = f"{row['market']} | observed {report_date} | {row['freshness']} ({row['report_age_days']} days old)"
        with st.expander(title, expanded=False):
            st.write(f"Positioning interpretation: {int(row['directional_bias']):+d}; self-rated confidence: {row['confidence']:.0%}; classification: {row['signal_type']}")
            st.write(row["narrative"])
            st.caption(f"Generated: {row.get('generated_at', 'unknown')} | Model: {row.get('model_name', 'unknown')} | Revision: {row.get('model_revision', 'unknown')}")


def main():
    st.set_page_config(page_title="COT Positioning Research", page_icon="📊", layout="wide")
    init_schema()
    st.title("COT Positioning Research")
    st.caption("Exploratory public-data research; corrected evaluation is still subject to data quality and vintage limitations.")
    st.warning("Yahoo daily futures prices are proxies without explicit contract rolls or trading costs. "
               "Current API history can contain revisions; unknown publication times and unknown original vintages do not establish point-in-time research validity.")
    signals = load_signals()
    hidden_signals = len(_load_table("signals")) - len(signals)
    if hidden_signals:
        st.warning(f"Hidden {hidden_signals} legacy or stale signal rows. Recompute with python -m src.signals after source updates.")
    prices = load_prices()
    markets = list(MARKET_CONFIG)
    st.sidebar.header("Controls")
    market = st.sidebar.selectbox("Select Market", markets)
    lookback = st.sidebar.slider("Lookback (weeks)", 52, 520, 156, step=52)
    tabs = st.tabs(["Positioning Overview", "Conditional Returns", "LLM Explanations", "Signal Table"])
    with tabs[0]:
        _show_history(signals, prices, market, lookback)
        st.subheader("Latest observation for every available market")
        latest = add_freshness(latest_per_market(signals))
        missing = sorted(set(markets) - set(latest["market"]))
        if missing:
            st.info("No observations available: " + ", ".join(missing))
        columns = ["market", "report_date", "release_at", "release_quality", "data_vintage", "analysis_eligible",
                   "report_age_days", "lag_vs_latest_days", "freshness", "cot_index_52w", "z_score_52w",
                   "mgd_money_net", "disagg_release_at", "inventory_report_date", "inventory_release_at"]
        st.dataframe(latest[[col for col in columns if col in latest]], width="stretch", hide_index=True)
        st.caption(f"Stale means observation age exceeds {STALE_AFTER_DAYS} calendar days. Lag is relative to the newest market in this database; neither guarantees successful ingestion.")
        if not latest.empty and "release_at" in latest:
            st.caption(f"Publication timestamps known for {latest['release_at'].notna().sum()} of {len(latest)} latest market observations. Inspect release quality and vintage before research use.")
    with tabs[1]:
        _show_backtest(markets)
    with tabs[2]:
        _show_anomalies()
    with tabs[3]:
        st.header("Full signal history")
        selected = st.selectbox("Market", markets, key="signal_market")
        st.dataframe(signals[signals["market"].eq(selected)].sort_values("report_date", ascending=False).head(100),
                     width="stretch", hide_index=True)
    st.sidebar.caption("Sources: CFTC legacy and disaggregated reports; EIA inventories; Yahoo Finance price proxies. LLM explanations are optional.")


if __name__ == "__main__":
    main()
