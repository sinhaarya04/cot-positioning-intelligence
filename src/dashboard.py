"""
Streamlit dashboard for COT Positioning Intelligence System.
Run: streamlit run src/dashboard.py --server.port 8501
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import get_conn, MARKET_CONFIG

st.set_page_config(
    page_title="COT Positioning Intelligence",
    page_icon="📊",
    layout="wide"
)

st.title("📊 COT Positioning Intelligence System")
st.caption("Multi-report CFTC positioning analysis with signal validation")


@st.cache_data(ttl=300)
def load_signals():
    conn = get_conn()
    df = conn.execute("SELECT * FROM signals ORDER BY market, report_date").fetchdf()
    conn.close()
    df["report_date"] = pd.to_datetime(df["report_date"])
    return df


@st.cache_data(ttl=300)
def load_prices():
    conn = get_conn()
    df = conn.execute("SELECT * FROM futures_prices ORDER BY market, price_date").fetchdf()
    conn.close()
    df["price_date"] = pd.to_datetime(df["price_date"])
    return df


@st.cache_data(ttl=300)
def load_backtest():
    conn = get_conn()
    df = conn.execute("SELECT * FROM backtest_results").fetchdf()
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_anomalies():
    conn = get_conn()
    df = conn.execute("SELECT * FROM llm_anomalies ORDER BY report_date DESC, market").fetchdf()
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_latest_signals():
    conn = get_conn()
    df = conn.execute("""
        SELECT * FROM signals
        WHERE report_date = (SELECT MAX(report_date) FROM signals)
        ORDER BY market
    """).fetchdf()
    conn.close()
    return df


# ── Sidebar ──
st.sidebar.header("Controls")
signals = load_signals()
markets = list(MARKET_CONFIG.keys())
selected_market = st.sidebar.selectbox("Select Market", markets, index=0)

lookback = st.sidebar.slider("Lookback (weeks)", 52, 520, 156, step=52)

# ── Tab Layout ──
tab1, tab2, tab3, tab4 = st.tabs([
    "📡 Positioning Overview",
    "📊 Backtest Results", 
    "🤖 LLM Anomaly Alerts",
    "📋 Signal Table"
])


# ══════════════════════════════════════════════════════════════
# TAB 1: Positioning Overview
# ══════════════════════════════════════════════════════════════
with tab1:
    st.header(f"{selected_market} — Positioning History")
    
    mkt_sig = signals[signals["market"] == selected_market].copy()
    mkt_sig = mkt_sig[mkt_sig["report_date"] >= mkt_sig["report_date"].max() - pd.Timedelta(weeks=lookback)]
    
    prices = load_prices()
    mkt_px = prices[prices["market"] == selected_market].copy()
    mkt_px = mkt_px[mkt_px["price_date"] >= mkt_sig["report_date"].min()]
    
    # ── Price + COT Index Chart ──
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.4, 0.3, 0.3],
        vertical_spacing=0.05,
        subplot_titles=("Price", "COT Index (52w)", "Z-Score (52w)")
    )
    
    # Price
    fig.add_trace(go.Scatter(
        x=mkt_px["price_date"], y=mkt_px["close_price"],
        name="Price", line=dict(color="#2196F3", width=1.5)
    ), row=1, col=1)
    
    # COT Index
    fig.add_trace(go.Scatter(
        x=mkt_sig["report_date"], y=mkt_sig["cot_index_52w"],
        name="COT Index 52w", line=dict(color="#4CAF50", width=1.5)
    ), row=2, col=1)
    
    fig.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
    fig.add_hline(y=20, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)
    
    # Z-Score
    fig.add_trace(go.Bar(
        x=mkt_sig["report_date"], y=mkt_sig["z_score_52w"],
        name="Z-Score 52w",
        marker_color=mkt_sig["z_score_52w"].apply(
            lambda x: "#EF5350" if x > 1.5 else "#66BB6A" if x < -1.5 else "#90A4AE"
        )
    ), row=3, col=1)
    
    fig.add_hline(y=1.5, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
    fig.add_hline(y=-1.5, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
    
    fig.update_layout(height=700, showlegend=False, margin=dict(t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)
    
    # ── Managed Money + Commercial Divergence ──
    st.subheader("Managed Money & Commercial-Speculative Divergence")
    
    fig2 = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.5, 0.5],
        vertical_spacing=0.08,
        subplot_titles=("Managed Money Net Position", "Commercial-Speculative Divergence")
    )
    
    mgd_data = mkt_sig[mkt_sig["mgd_money_net"].notna()]
    fig2.add_trace(go.Bar(
        x=mgd_data["report_date"], y=mgd_data["mgd_money_net"],
        name="Managed Money Net",
        marker_color=mgd_data["mgd_money_net"].apply(
            lambda x: "#2196F3" if x > 0 else "#EF5350"
        )
    ), row=1, col=1)
    
    div_data = mkt_sig[mkt_sig["comm_spec_divergence"].notna()]
    fig2.add_trace(go.Scatter(
        x=div_data["report_date"], y=div_data["comm_spec_divergence"],
        name="Comm-Spec Divergence", line=dict(color="#FF9800", width=1.5),
        fill="tozeroy", fillcolor="rgba(255, 152, 0, 0.1)"
    ), row=2, col=1)
    
    fig2.update_layout(height=500, showlegend=False, margin=dict(t=30, b=30))
    st.plotly_chart(fig2, use_container_width=True)
    
    # ── Latest Signals Summary ──
    st.subheader("Latest Signals — All Markets")
    latest = load_latest_signals()
    
    # Color-code the dataframe
    st.dataframe(
        latest[[
            "market", "report_date", "cot_index_52w", "cot_index_156w",
            "z_score_52w", "momentum_4w", "mgd_money_net",
            "comm_spec_divergence", "inventory_mismatch"
        ]].style.background_gradient(
            subset=["cot_index_52w"], cmap="RdYlGn", vmin=0, vmax=100
        ).background_gradient(
            subset=["z_score_52w"], cmap="RdYlGn_r", vmin=-3, vmax=3
        ).format({
            "cot_index_52w": "{:.1f}",
            "cot_index_156w": "{:.1f}",
            "z_score_52w": "{:+.2f}",
            "momentum_4w": "{:+,.0f}",
            "mgd_money_net": "{:+,.0f}",
            "comm_spec_divergence": "{:+.4f}",
            "inventory_mismatch": "{:.2f}",
        }),
        use_container_width=True,
        hide_index=True
    )


# ══════════════════════════════════════════════════════════════
# TAB 2: Backtest Results
# ══════════════════════════════════════════════════════════════
with tab2:
    st.header("Backtest Results — Do COT Signals Predict Returns?")
    
    bt = load_backtest()
    
    if bt.empty:
        st.warning("No backtest results found. Run `python -m src.backtest` first.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            bt_market = st.selectbox("Market", ["ALL"] + markets, key="bt_market")
        with col2:
            bt_horizon = st.selectbox("Horizon", ["ALL", "1w", "2w", "4w"], key="bt_horizon")
        with col3:
            min_hit = st.slider("Min Hit Rate", 0.4, 0.75, 0.55, step=0.05)
        
        filtered = bt.copy()
        if bt_market != "ALL":
            filtered = filtered[filtered["market"] == bt_market]
        if bt_horizon != "ALL":
            filtered = filtered[filtered["horizon"] == bt_horizon]
        filtered = filtered[filtered["hit_rate"] >= min_hit]
        filtered = filtered.sort_values("sharpe", ascending=False)
        
        st.dataframe(
            filtered.style.background_gradient(
                subset=["hit_rate"], cmap="Greens", vmin=0.4, vmax=0.75
            ).background_gradient(
                subset=["sharpe"], cmap="RdYlGn", vmin=-0.5, vmax=0.5
            ).format({
                "hit_rate": "{:.1%}",
                "avg_return": "{:+.4f}",
                "sharpe": "{:+.3f}",
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # ── Heatmap: Signal effectiveness by market ──
        st.subheader("Signal Sharpe Ratio Heatmap (4-week horizon, top decile)")
        
        heatmap_data = bt[
            (bt["horizon"] == "4w") & (bt["threshold"] == "top_decile")
        ].pivot_table(
            values="sharpe", index="market", columns="signal_name", aggfunc="first"
        )
        
        if not heatmap_data.empty:
            fig_heat = go.Figure(data=go.Heatmap(
                z=heatmap_data.values,
                x=heatmap_data.columns,
                y=heatmap_data.index,
                colorscale="RdYlGn",
                zmid=0,
                text=heatmap_data.values.round(3),
                texttemplate="%{text}",
                textfont={"size": 11},
            ))
            fig_heat.update_layout(height=400, margin=dict(t=10, b=10))
            st.plotly_chart(fig_heat, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# TAB 3: LLM Anomaly Alerts
# ══════════════════════════════════════════════════════════════
with tab3:
    st.header("🤖 LLM Anomaly Alerts")
    
    anomalies = load_anomalies()
    
    if anomalies.empty:
        st.warning("No anomaly analyses found. Run `python -m src.llm_anomaly` on a GPU node first.")
    else:
        for _, row in anomalies.iterrows():
            bias = row.get("directional_bias", 0)
            confidence = row.get("confidence", 0)
            
            if bias > 50:
                emoji, color = "📈", "green"
            elif bias < -50:
                emoji, color = "📉", "red"
            else:
                emoji, color = "➡️", "orange"
            
            with st.expander(
                f"{emoji} {row['market']} — Bias: {bias:+d} | "
                f"Confidence: {confidence:.0%} | {row.get('signal_type', 'N/A')}",
                expanded=True
            ):
                col1, col2, col3 = st.columns(3)
                col1.metric("Directional Bias", f"{bias:+d}")
                col2.metric("Confidence", f"{confidence:.0%}")
                col3.metric("Historical Hit Rate", f"{row.get('historical_hit_rate', 0):.1%}")
                
                st.markdown(f"**Analysis:** {row.get('narrative', 'N/A')}")


# ══════════════════════════════════════════════════════════════
# TAB 4: Raw Signal Table
# ══════════════════════════════════════════════════════════════
with tab4:
    st.header("📋 Full Signal History")
    
    mkt_filter = st.selectbox("Market", markets, key="sig_table_market")
    
    mkt_data = signals[signals["market"] == mkt_filter].sort_values("report_date", ascending=False)
    
    st.dataframe(
        mkt_data.head(100).style.format({
            "cot_index_52w": "{:.1f}",
            "cot_index_156w": "{:.1f}",
            "z_score_52w": "{:+.2f}",
            "momentum_4w": "{:+,.0f}",
            "mgd_money_net": "{:+,.0f}",
            "comm_spec_divergence": "{:+.4f}",
            "positioning_acceleration": "{:+,.0f}",
            "inventory_mismatch": "{:.2f}",
        }),
        use_container_width=True,
        hide_index=True
    )


# ── Footer ──
st.sidebar.markdown("---")
st.sidebar.markdown("**Data Sources**")
st.sidebar.markdown("- CFTC Commitments of Traders")
st.sidebar.markdown("- EIA Petroleum & Natural Gas")
st.sidebar.markdown("- Yahoo Finance (prices)")
st.sidebar.markdown(f"- LLM: Qwen 2.5 3B Instruct")
