"""
DuckDB schema and helper functions for COT Intelligence System.
All data lives in data/cot_intelligence.duckdb
"""

import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "cot_intelligence.duckdb"


def get_conn() -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection, creating the DB file if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init_schema():
    """Create all tables. Safe to run multiple times (IF NOT EXISTS)."""
    conn = get_conn()

    # ── 1. Legacy COT ──────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cot_legacy (
            report_date       DATE NOT NULL,
            market            VARCHAR NOT NULL,   -- e.g. 'GOLD', 'CRUDE_OIL'
            cftc_code         VARCHAR,            -- CFTC contract code
            -- Non-commercial (speculators)
            noncomm_long      BIGINT,
            noncomm_short     BIGINT,
            noncomm_spreading BIGINT,
            -- Commercial (hedgers)
            comm_long         BIGINT,
            comm_short        BIGINT,
            -- Non-reportable
            nonrep_long       BIGINT,
            nonrep_short      BIGINT,
            -- Open interest
            open_interest     BIGINT,
            PRIMARY KEY (report_date, market)
        );
    """)

    # ── 2. Disaggregated COT ───────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cot_disagg (
            report_date           DATE NOT NULL,
            market                VARCHAR NOT NULL,
            cftc_code             VARCHAR,
            -- Producer/Merchant
            prod_merc_long        BIGINT,
            prod_merc_short       BIGINT,
            -- Swap Dealers
            swap_long             BIGINT,
            swap_short            BIGINT,
            swap_spreading        BIGINT,
            -- Managed Money
            mgd_money_long        BIGINT,
            mgd_money_short       BIGINT,
            mgd_money_spreading   BIGINT,
            -- Other Reportables
            other_long            BIGINT,
            other_short           BIGINT,
            other_spreading       BIGINT,
            open_interest         BIGINT,
            PRIMARY KEY (report_date, market)
        );
    """)

    # ── 3. Traders in Financial Futures (TFF) ──────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cot_tff (
            report_date           DATE NOT NULL,
            market                VARCHAR NOT NULL,
            cftc_code             VARCHAR,
            -- Dealer/Intermediary
            dealer_long           BIGINT,
            dealer_short          BIGINT,
            dealer_spreading      BIGINT,
            -- Asset Manager/Institutional
            asset_mgr_long        BIGINT,
            asset_mgr_short       BIGINT,
            asset_mgr_spreading   BIGINT,
            -- Leveraged Funds
            lev_money_long        BIGINT,
            lev_money_short       BIGINT,
            lev_money_spreading   BIGINT,
            -- Other Reportables
            other_long            BIGINT,
            other_short           BIGINT,
            other_spreading       BIGINT,
            open_interest         BIGINT,
            PRIMARY KEY (report_date, market)
        );
    """)

    # ── 4. EIA Inventory Data ──────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eia_inventory (
            report_date       DATE NOT NULL,
            commodity         VARCHAR NOT NULL,   -- 'CRUDE_OIL', 'NATURAL_GAS'
            series_id         VARCHAR,            -- EIA series identifier
            inventory_level   DOUBLE,             -- absolute level (barrels/bcf)
            weekly_change     DOUBLE,             -- week-over-week change
            PRIMARY KEY (report_date, commodity)
        );
    """)

    # ── 5. Futures Prices ──────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS futures_prices (
            price_date        DATE NOT NULL,
            market            VARCHAR NOT NULL,
            close_price       DOUBLE,
            volume            BIGINT,
            PRIMARY KEY (price_date, market)
        );
    """)

    # ── 6. Computed Signals ────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            report_date               DATE NOT NULL,
            market                    VARCHAR NOT NULL,
            -- Core signals
            cot_index_52w             DOUBLE,    -- percentile rank over 52 weeks
            cot_index_156w            DOUBLE,    -- percentile rank over 156 weeks (3yr)
            z_score_52w               DOUBLE,    -- rolling z-score
            momentum_4w               DOUBLE,    -- 4-week net position change
            -- Advanced signals
            mgd_money_net             BIGINT,    -- managed money net positioning
            comm_spec_divergence      DOUBLE,    -- commercial vs speculative spread
            positioning_acceleration  DOUBLE,    -- 2nd derivative of net positioning
            inventory_mismatch        DOUBLE,    -- only for energy contracts
            PRIMARY KEY (report_date, market)
        );
    """)

    # ── 7. Backtest Results ────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_results (
            market              VARCHAR NOT NULL,
            signal_name         VARCHAR NOT NULL,
            horizon             VARCHAR NOT NULL,   -- '1w', '2w', '4w'
            threshold           VARCHAR NOT NULL,   -- 'top_decile', 'bot_decile', etc.
            n_signals           INTEGER,
            hit_rate            DOUBLE,
            avg_return          DOUBLE,
            sharpe              DOUBLE,
            PRIMARY KEY (market, signal_name, horizon, threshold)
        );
    """)

    # ── 8. LLM Anomaly Outputs ─────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_anomalies (
            report_date         DATE NOT NULL,
            market              VARCHAR NOT NULL,
            signal_type         VARCHAR,
            directional_bias    INTEGER,    -- -100 to +100
            confidence          DOUBLE,     -- 0 to 1
            historical_hit_rate DOUBLE,
            narrative           VARCHAR,
            PRIMARY KEY (report_date, market)
        );
    """)

    conn.close()
    print("✅ Schema initialized.")


# ── Lookup table: market name → CFTC codes ─────────────────────────
MARKET_CONFIG = {
    "GOLD":        {"cftc_code": "088691", "yf_ticker": "GC=F", "eia_series": None},
    "SILVER":      {"cftc_code": "084691", "yf_ticker": "SI=F", "eia_series": None},
    "CRUDE_OIL":   {"cftc_code": "067651", "yf_ticker": "CL=F", "eia_series": "PET.WCESTUS1.W"},
    "NATURAL_GAS": {"cftc_code": "023651", "yf_ticker": "NG=F", "eia_series": "NG.NW2_EPG0_SWO_R48_BCF.W"},
    "CORN":        {"cftc_code": "002602", "yf_ticker": "ZC=F", "eia_series": None},
    "WHEAT":       {"cftc_code": "001602", "yf_ticker": "ZW=F", "eia_series": None},
    "SOYBEANS":    {"cftc_code": "005602", "yf_ticker": "ZS=F", "eia_series": None},
    "COPPER":      {"cftc_code": "085692", "yf_ticker": "HG=F", "eia_series": None},
}


if __name__ == "__main__":
    init_schema()
    