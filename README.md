<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/DuckDB-1.5-yellow?style=for-the-badge&logo=duckdb&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-1.55-red?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/PyTorch-2.5-orange?style=for-the-badge&logo=pytorch&logoColor=white" />
  <img src="https://img.shields.io/badge/GPU-V100%2032GB-green?style=for-the-badge&logo=nvidia&logoColor=white" />
</p>

<h1 align="center">📊 COT Positioning Intelligence System</h1>

<p align="center">
  <b>Multi-report CFTC analysis with quantitative signal validation across 40 years of commodity futures data</b>
</p>

<p align="center">
  <i>Do CFTC positioning extremes actually predict commodity futures returns?</i><br>
  <i>Short answer: yes, but not the way most people think.</i>
</p>

---

## 🔍 The Question

Every Friday, the CFTC publishes the Commitments of Traders report showing how institutional players are positioned across commodity futures. Most traders glance at it. Some build dashboards around it.

**Nobody backtests it.**

This system ingests 3 CFTC report types across 8 commodity markets, engineers 8 quantitative signals, and rigorously backtests whether positioning extremes predict forward 1-week, 2-week, and 4-week futures returns using 40 years of historical data.

---

## 🚀 Key Findings

### 1. Mean Reversion Works in Precious Metals
When speculators hit extreme bearish positioning in **Gold**, prices rose **69% of the time** over the next month (Sharpe: 0.49). The commercial-speculative divergence signal is the strongest risk-adjusted predictor in the entire dataset.

### 2. Momentum Works in Agriculture
The standard advice is "fade the crowd." But when specs are maximally long **Corn**, prices keep going up: **71% hit rate** over 4 weeks. The crowd isn't speculating blindly; they're reacting to real supply constraints that take weeks to resolve.

### 3. Cross-Dataset Signals Work in Energy
Combining **EIA inventory data** with **CFTC positioning** into a single mismatch score produced a **57% hit rate** and **~4% avg return** in Crude Oil. When physical supply trends contradict speculative sentiment, the mismatch resolves in a tradeable way.

### 4. There Is No Universal COT Rule
The signal that works in Gold fails in Corn. The signal that works in Crude fails in Copper. **Market-specific calibration is everything.**

---

## 📊 Dashboard

<table>
<tr>
<td width="50%">

**Positioning Overview**
- Price + COT Index + Z-Score time series
- Managed Money net position bars
- Commercial-Speculative divergence
- Color-coded latest signals table

</td>
<td width="50%">

**Backtest Results**
- Filterable by market, horizon, min hit rate
- Sharpe ratio heatmap by signal × market
- Signal effectiveness comparison

</td>
</tr>
<tr>
<td width="50%">

**LLM Anomaly Alerts**
- GPU-powered analysis via Qwen 2.5 3B
- Directional bias scoring (-100 to +100)
- Structured JSON output with confidence scores
- Anomaly detection: Z > 1.5 or COT Index extremes

</td>
<td width="50%">

**Signal Table**
- Full historical signal data per market
- 8 signals × 8 markets × 40 years
- Exportable and sortable

</td>
</tr>
</table>

---

## ⚙️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   DATA INGESTION                     │
├──────────────┬──────────────┬───────────────────────┤
│  CFTC API    │  EIA API     │  Yahoo Finance        │
│  Legacy COT  │  Petroleum   │  Futures Prices       │
│  Disagg COT  │  Natural Gas │  8 markets, weekly    │
│  TFF Report  │  Inventories │  2000–2026            │
│  1986–2026   │              │                       │
└──────┬───────┴──────┬───────┴───────────┬───────────┘
       │              │                   │
       ▼              ▼                   ▼
┌─────────────────────────────────────────────────────┐
│                 DuckDB (Local)                        │
│  cot_legacy │ cot_disagg │ eia_inventory │ prices    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              SIGNAL COMPUTATION                      │
│                                                      │
│  COT Index (52w/156w)    │  Managed Money Net        │
│  Z-Score (52w)           │  Comm-Spec Divergence     │
│  4-Week Momentum         │  Positioning Acceleration │
│  Inventory Mismatch *    │                           │
│                          │  * Energy contracts only  │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
┌──────────────────┐  ┌────────────────────┐
│    BACKTESTING   │  │   LLM ANOMALY      │
│                  │  │   DETECTION         │
│  Forward returns │  │                    │
│  1w / 2w / 4w    │  │  Qwen 2.5 3B      │
│  Top/Bot decile  │  │  V100 GPU          │
│  Hit rate, Sharpe│  │  Structured JSON   │
└────────┬─────────┘  └────────┬───────────┘
         │                     │
         ▼                     ▼
┌─────────────────────────────────────────────────────┐
│              STREAMLIT DASHBOARD                     │
│  Positioning Charts │ Backtest Tables │ LLM Alerts  │
└─────────────────────────────────────────────────────┘
```

---

## 📈 Backtest Results (Top Signals)

| Market | Signal | Horizon | Threshold | Hit Rate | Avg Return | Sharpe | n |
|--------|--------|---------|-----------|----------|------------|--------|---|
| Gold | Comm-Spec Divergence | 4w | Bot Decile | **70.2%** | +2.33% | **0.494** | 134 |
| Corn | COT Index 52w | 4w | Top Decile | **71.0%** | +3.52% | 0.396 | 131 |
| Natural Gas | Momentum 4w | 4w | Bot Decile | 60.2% | **+4.34%** | 0.309 | 133 |
| Crude Oil | Inventory Mismatch | 4w | Top Decile | 57.2% | **+3.96%** | 0.256 | 131 |
| Soybeans | COT Index 156w | 4w | Top Decile | 65.2% | +2.53% | 0.381 | 132 |
| Silver | COT Index 52w | 4w | Bot Decile | 66.7% | +2.33% | 0.225 | 132 |
| Gold | COT Index 52w | 4w | Bot Decile | **68.7%** | +1.72% | 0.375 | 131 |

---

## 🛠️ Quick Start

### Prerequisites
- Python 3.12+
- NVIDIA GPU (for LLM layer; optional)
- EIA API key ([free registration](https://www.eia.gov/opendata/register.php))

### Installation

```bash
git clone https://github.com/sinhaarya04/cot-positioning-intelligence.git
cd cot-positioning-intelligence

# Create environment
conda create -p ./env python=3.12 -y
conda activate ./env

# Install dependencies
pip install requests pandas numpy duckdb yfinance streamlit plotly scipy \
            matplotlib transformers torch accelerate sentencepiece python-dotenv
```

### Run the Pipeline

```bash
# Step 1: Initialize database schema
python src/db.py

# Step 2: Ingest CFTC data (3 report types, 8 markets, ~2 min)
python -m src.ingest_cftc

# Step 3: Ingest futures prices + EIA inventory data
# Set your EIA API key in src/ingest_prices.py first
python -m src.ingest_prices

# Step 4: Compute signals (8 signals × 8 markets)
python -m src.signals

# Step 5: Run backtest (forward return analysis)
python -m src.backtest

# Step 6: LLM anomaly detection (requires GPU)
python -m src.llm_anomaly

# Step 7: Launch dashboard
streamlit run src/dashboard.py --server.port 8501
```

---

## 📁 Project Structure

```
cot-positioning-intelligence/
├── data/
│   └── cot_intelligence.duckdb      # All data (auto-generated)
├── src/
│   ├── __init__.py
│   ├── db.py                        # Schema + market config
│   ├── ingest_cftc.py               # CFTC Socrata API ingestion
│   ├── ingest_prices.py             # Yahoo Finance + EIA API
│   ├── signals.py                   # Signal computation engine
│   ├── backtest.py                  # Forward return backtesting
│   ├── llm_anomaly.py              # Qwen 2.5 3B anomaly detection
│   └── dashboard.py                 # Streamlit dashboard
├── output/
├── .gitignore
└── README.md
```

---

## 🔬 Signal Definitions

| Signal | Source | Description |
|--------|--------|-------------|
| **COT Index (52w/156w)** | Legacy COT | Percentile rank of net speculative position over rolling window (0–100) |
| **Z-Score (52w)** | Legacy COT | Standard deviations from rolling mean of net speculative position |
| **Momentum (4w)** | Legacy COT | 4-week change in net speculative contracts |
| **Comm-Spec Divergence** | Legacy COT | Commercial vs speculative net position spread, normalized by open interest |
| **Positioning Acceleration** | Legacy COT | Second derivative of net positioning (change in momentum) |
| **Managed Money Net** | Disagg COT | Hedge fund/CTA net position from disaggregated report |
| **Inventory Mismatch** | EIA + CFTC | Product of inventory Z-score and positioning Z-score (energy only) |

---

## ⚠️ Limitations

- **No transaction costs**: Returns are gross of trading costs, slippage, and roll costs
- **Look-ahead in thresholds**: Top/bottom decile computed over full sample (walk-forward would be more rigorous)
- **Weekly granularity**: COT data is as-of Tuesday, released Friday; intraweek moves not captured
- **No regime adjustment**: All market environments treated equally
- **LLM narratives**: Qwen 2.5 3B occasionally produces inconsistent reasoning; use quantitative signals as primary

---

## 🗺️ Future Work

- Walk-forward backtest to eliminate look-ahead bias
- Cross-commodity positioning correlation matrix
- TFF report integration (Treasury bonds, S&P 500, EUR/USD)
- Automated weekly email digest via cron
- Alpha decay analysis (how fast do COT signals degrade after publication?)

---

## 🏗️ Built With

| Component | Technology |
|-----------|-----------|
| Database | DuckDB 1.5 (columnar, local) |
| Data | CFTC Socrata API, EIA API v2, Yahoo Finance |
| Signals | Pandas, NumPy, SciPy |
| LLM | Qwen 2.5 3B Instruct (HuggingFace Transformers) |
| GPU | NVIDIA Tesla V100 32GB |
| Dashboard | Streamlit + Plotly |
| Compute | Northeastern University Explorer HPC Cluster |

---

<p align="center">
  Built by <a href="https://linkedin.com/in/sinhaarya04">Aryan Sinha</a> · Northeastern University
</p>
