"""
DuckDB schema and helper functions for COT Intelligence System.
All data lives in data/cot_intelligence.duckdb
"""

import duckdb
import os
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "cot_intelligence.duckdb"


def get_conn() -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection, creating the DB file if needed."""
    path = Path(os.environ.get("COT_DB_PATH") or DB_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


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
            cot_index_52w             DOUBLE,    -- rolling min-max index over 52 observations
            cot_index_156w            DOUBLE,    -- rolling min-max index over 156 observations
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

    # Additive migrations preserve old databases. Old rows are deliberately
    # unknown/legacy, never silently promoted to release-aware observations.
    raw_metadata = {
        "release_at": "TIMESTAMPTZ", "release_source": "VARCHAR",
        "release_quality": "VARCHAR DEFAULT 'unknown'",
        "vintage": "VARCHAR DEFAULT 'latest'", "ingested_at": "TIMESTAMPTZ",
    }
    additions = {table: dict(raw_metadata) for table in
                 ("cot_legacy", "cot_disagg", "cot_tff", "eia_inventory")}
    additions.update({
        "futures_prices": {"price_at": "TIMESTAMPTZ", "price_kind": "VARCHAR DEFAULT 'legacy_unknown'",
                           "source": "VARCHAR", "ingested_at": "TIMESTAMPTZ"},
        "signals": {"release_at": "TIMESTAMPTZ", "release_quality": "VARCHAR DEFAULT 'unknown'",
                    "inventory_release_at": "TIMESTAMPTZ", "disagg_release_at": "TIMESTAMPTZ",
                    "inventory_report_date": "DATE", "data_vintage": "VARCHAR DEFAULT 'latest'",
                    "analysis_eligible": "BOOLEAN DEFAULT FALSE", "evaluation_version": "VARCHAR DEFAULT 'legacy'"},
        "backtest_results": {"positive_return_rate": "DOUBLE", "mean_over_std": "DOUBLE",
                             "baseline_positive_rate": "DOUBLE", "baseline_avg_return": "DOUBLE",
                             "evaluation_version": "VARCHAR DEFAULT 'legacy'",
                             "evaluation_start": "DATE", "evaluation_end": "DATE"},
        "llm_anomalies": {"model_name": "VARCHAR", "model_revision": "VARCHAR",
                          "prompt_version": "VARCHAR", "generated_at": "TIMESTAMPTZ",
                          "generation_parameters": "VARCHAR"},
    })
    try:
        conn.execute("BEGIN TRANSACTION")
        for table, fields in additions.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}
            for name, sql_type in fields.items():
                if name not in existing:
                    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}')
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


TABLE_KEYS = {
    "cot_legacy": ["report_date", "market"],
    "cot_disagg": ["report_date", "market"],
    "cot_tff": ["report_date", "market"],
    "eia_inventory": ["report_date", "commodity"],
    "futures_prices": ["price_date", "market"],
    "signals": ["report_date", "market"],
    "backtest_results": ["market", "signal_name", "horizon", "threshold"],
    "llm_anomalies": ["report_date", "market"],
}


def write_frame(table: str, frame: pd.DataFrame, mode: str = "upsert", keys=None) -> int:
    """Validate and atomically replace keys (or a complete derived table).

    Empty input is a no-op, never a destructive replacement. All columns are
    named explicitly; an insert error rolls the preceding deletion back.
    """
    if table not in TABLE_KEYS or mode not in {"upsert", "replace"}:
        raise ValueError("Unsupported table or write mode")
    if frame.empty:
        return 0
    keys = TABLE_KEYS[table] if keys is None else list(keys)
    if keys != TABLE_KEYS[table]:
        raise ValueError(f"Keys must match the primary key for {table}")
    if not frame.columns.is_unique or not set(keys).issubset(frame.columns):
        raise ValueError("Missing keys or duplicate input columns")
    if frame[keys].isna().any().any() or frame.duplicated(keys).any():
        raise ValueError("Null or duplicate primary keys")
    conn = get_conn()
    try:
        allowed = {row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}
        unknown = set(frame.columns) - allowed
        if unknown:
            raise ValueError(f"Unknown columns for {table}: {sorted(unknown)}")
        columns = ", ".join(f'"{name}"' for name in frame.columns)
        conn.register("incoming_rows", frame)
        conn.execute("BEGIN TRANSACTION")
        try:
            incoming = "incoming_rows"
            metadata = {"release_at", "release_quality", "release_source"}
            if table in {"cot_legacy", "cot_disagg", "cot_tff", "eia_inventory"} and metadata.issubset(frame.columns):
                # A normal refresh must not erase a calendar applied previously.
                # This preserves dates, not first-vintage claims: incoming values
                # and their vintage/retrieval metadata are still replaced.
                predicate = " AND ".join(f't."{key}" = s."{key}"' for key in keys)
                preserve = ("s.release_at IS NULL AND COALESCE(s.release_quality, 'unknown') = 'unknown' "
                            "AND t.release_quality = 'verified' AND t.release_at IS NOT NULL")
                selected = ", ".join(
                    f'CASE WHEN {preserve} THEN t."{name}" ELSE CAST(s."{name}" AS '
                    f'{"TIMESTAMPTZ" if name == "release_at" else "VARCHAR"}) END AS "{name}"'
                    if name in metadata else f's."{name}"' for name in frame.columns)
                conn.execute(f'CREATE TEMP TABLE staged_rows AS SELECT {selected} FROM incoming_rows AS s '
                             f'LEFT JOIN "{table}" AS t ON {predicate}')
                incoming = "staged_rows"
            if table == "futures_prices" and "price_kind" in frame.columns:
                conflict = conn.execute("""
                    SELECT COUNT(*) FROM futures_prices AS t JOIN incoming_rows AS s
                    ON t.market = s.market WHERE t.price_kind = 'contract_settlement'
                    AND s.price_kind = 'daily_close_proxy'
                """).fetchone()[0]
                if conflict:
                    raise ValueError("Refusing to replace contract settlements with Yahoo proxies")
                # Old weekly bars have ambiguous timestamps. Remove only these
                # legacy rows; a truncated new response cannot erase good daily history.
                conn.execute("""
                    DELETE FROM futures_prices AS t USING incoming_rows AS s
                    WHERE t.market = s.market AND s.price_kind = 'daily_close_proxy'
                    AND t.price_kind = 'legacy_unknown'
                """)
            if mode == "replace":
                conn.execute(f'DELETE FROM "{table}"')
            else:
                predicate = " AND ".join(f't."{key}" = s."{key}"' for key in keys)
                conn.execute(f'DELETE FROM "{table}" AS t USING {incoming} AS s WHERE {predicate}')
            conn.execute(f'INSERT INTO "{table}" ({columns}) SELECT {columns} FROM {incoming}')
            raw_table = table in {"cot_legacy", "cot_disagg", "cot_tff", "eia_inventory"}
            if raw_table:
                conn.execute("UPDATE signals SET evaluation_version = 'stale', analysis_eligible = FALSE")
            if raw_table or table in {"signals", "futures_prices"}:
                conn.execute("UPDATE backtest_results SET evaluation_version = 'stale'")
            if raw_table or table == "signals":
                conn.execute("UPDATE llm_anomalies SET prompt_version = 'stale'")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return len(frame)


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

