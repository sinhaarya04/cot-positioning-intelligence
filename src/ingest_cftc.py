"""
Ingest CFTC Commitments of Traders data from the public Socrata API.
Pulls Legacy, Disaggregated, and Traders in Financial Futures reports.
"""

import requests
import pandas as pd
from datetime import datetime
from src.db import get_conn, MARKET_CONFIG

# ── CFTC Socrata API endpoints ──────────────────────────────────────
# These are the publicly available datasets on the CFTC website.
# No API key required, but adding an app token raises rate limits.
ENDPOINTS = {
    "legacy": "https://publicreporting.cftc.gov/resource/6dca-aqww.json",       # Legacy Futures-Only
    "disagg": "https://publicreporting.cftc.gov/resource/72hh-3qpy.json",       # Disaggregated Futures-Only
    "tff":    "https://publicreporting.cftc.gov/resource/gpe5-46if.json",        # Traders in Financial Futures
}

# Max rows per request (Socrata default limit is 1000)
PAGE_SIZE = 50000


def fetch_cftc_data(report_type: str, cftc_code: str, limit: int = PAGE_SIZE) -> pd.DataFrame:
    """
    Fetch COT data for a given report type and CFTC contract code.
    Returns a DataFrame with all available history.
    """
    url = ENDPOINTS[report_type]
    params = {
        "$where": f"cftc_contract_market_code='{cftc_code}'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": limit,
    }
    
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    
    if not data:
        print(f"  ⚠️  No data for code {cftc_code} in {report_type}")
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    print(f"  ✅ {report_type}: {len(df)} rows for code {cftc_code}")
    return df


def parse_legacy(df: pd.DataFrame, market: str) -> list[dict]:
    """Parse legacy COT DataFrame into rows for the cot_legacy table."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "report_date":       r.get("report_date_as_yyyy_mm_dd", "")[:10],
            "market":            market,
            "cftc_code":         r.get("cftc_contract_market_code", ""),
            "noncomm_long":      int(r.get("noncomm_positions_long_all", 0) or 0),
            "noncomm_short":     int(r.get("noncomm_positions_short_all", 0) or 0),
            "noncomm_spreading": int(r.get("noncomm_postions_spread_all", 0) or 0),
            "comm_long":         int(r.get("comm_positions_long_all", 0) or 0),
            "comm_short":        int(r.get("comm_positions_short_all", 0) or 0),
            "nonrep_long":       int(r.get("nonrept_positions_long_all", 0) or 0),
            "nonrep_short":      int(r.get("nonrept_positions_short_all", 0) or 0),
            "open_interest":     int(r.get("open_interest_all", 0) or 0),
        })
    return rows


def parse_disagg(df: pd.DataFrame, market: str) -> list[dict]:
    """Parse disaggregated COT DataFrame into rows for the cot_disagg table."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "report_date":         r.get("report_date_as_yyyy_mm_dd", "")[:10],
            "market":              market,
            "cftc_code":           r.get("cftc_contract_market_code", ""),
            "prod_merc_long":      int(r.get("prod_merc_positions_long_all", 0) or 0),
            "prod_merc_short":     int(r.get("prod_merc_positions_short_all", 0) or 0),
            "swap_long":           int(r.get("swap_positions_long_all", 0) or 0),
            "swap_short":          int(r.get("swap__positions_short_all", 0) or 0),
            "swap_spreading":      int(r.get("swap__positions_spread_all", 0) or 0),
            "mgd_money_long":      int(r.get("m_money_positions_long_all", 0) or 0),
            "mgd_money_short":     int(r.get("m_money_positions_short_all", 0) or 0),
            "mgd_money_spreading": int(r.get("m_money_positions_spread_all", 0) or 0),
            "other_long":          int(r.get("other_rept_positions_long_all", 0) or 0),
            "other_short":         int(r.get("other_rept_positions_short_all", 0) or 0),
            "other_spreading":     int(r.get("other_rept_positions_spread_all", 0) or 0),
            "open_interest":       int(r.get("open_interest_all", 0) or 0),
        })
    return rows


def parse_tff(df: pd.DataFrame, market: str) -> list[dict]:
    """Parse TFF DataFrame into rows for the cot_tff table."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "report_date":          r.get("report_date_as_yyyy_mm_dd", "")[:10],
            "market":               market,
            "cftc_code":            r.get("cftc_contract_market_code", ""),
            "dealer_long":          int(r.get("dealer_positions_long_all", 0) or 0),
            "dealer_short":         int(r.get("dealer_positions_short_all", 0) or 0),
            "dealer_spreading":     int(r.get("dealer_positions_spread_all", 0) or 0),
            "asset_mgr_long":       int(r.get("asset_mgr_positions_long_all", 0) or 0),
            "asset_mgr_short":      int(r.get("asset_mgr_positions_short_all", 0) or 0),
            "asset_mgr_spreading":  int(r.get("asset_mgr_positions_spread_all", 0) or 0),
            "lev_money_long":       int(r.get("lev_money_positions_long_all", 0) or 0),
            "lev_money_short":      int(r.get("lev_money_positions_short_all", 0) or 0),
            "lev_money_spreading":  int(r.get("lev_money_positions_spread_all", 0) or 0),
            "other_long":           int(r.get("other_rept_positions_long_all", 0) or 0),
            "other_short":          int(r.get("other_rept_positions_short_all", 0) or 0),
            "other_spreading":      int(r.get("other_rept_positions_spread_all", 0) or 0),
            "open_interest":        int(r.get("open_interest_all", 0) or 0),
        })
    return rows


def upsert_rows(table: str, rows: list[dict]):
    """Insert rows into DuckDB, replacing on conflict."""
    if not rows:
        return
    conn = get_conn()
    df = pd.DataFrame(rows)
    
    # Drop existing rows for these dates/markets, then insert
    for (date, market) in df[["report_date", "market"]].drop_duplicates().values:
        conn.execute(
            f"DELETE FROM {table} WHERE report_date = ? AND market = ?",
            [date, market]
        )
    
    conn.execute(f"INSERT INTO {table} SELECT * FROM df")
    conn.close()


def ingest_all():
    """Main ingestion: pull all three report types for all markets."""
    print("=" * 60)
    print(f"CFTC COT Data Ingestion — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    for market, config in MARKET_CONFIG.items():
        code = config["cftc_code"]
        print(f"\n📡 {market} (CFTC code: {code})")
        
        # ── Legacy COT ──
        try:
            df_legacy = fetch_cftc_data("legacy", code)
            if not df_legacy.empty:
                rows = parse_legacy(df_legacy, market)
                upsert_rows("cot_legacy", rows)
        except Exception as e:
            print(f"  ❌ Legacy failed: {e}")
        
        # ── Disaggregated COT ──
        try:
            df_disagg = fetch_cftc_data("disagg", code)
            if not df_disagg.empty:
                rows = parse_disagg(df_disagg, market)
                upsert_rows("cot_disagg", rows)
        except Exception as e:
            print(f"  ❌ Disagg failed: {e}")
        
        # ── TFF (only for financial contracts — gold, silver, copper) ──
        # TFF uses different contract codes; skip for ags/energy
        # We'll attempt it and gracefully handle empty results
        try:
            df_tff = fetch_cftc_data("tff", code)
            if not df_tff.empty:
                rows = parse_tff(df_tff, market)
                upsert_rows("cot_tff", rows)
        except Exception as e:
            print(f"  ❌ TFF failed: {e}")
    
    # ── Summary ──
    conn = get_conn()
    for table in ["cot_legacy", "cot_disagg", "cot_tff"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        markets = conn.execute(f"SELECT DISTINCT market FROM {table}").fetchall()
        market_list = [m[0] for m in markets]
        print(f"\n📊 {table}: {count} total rows across {market_list}")
    
    date_range = conn.execute(
        "SELECT MIN(report_date), MAX(report_date) FROM cot_legacy"
    ).fetchone()
    print(f"\n📅 Date range: {date_range[0]} to {date_range[1]}")
    conn.close()
    
    print("\n✅ Ingestion complete.")


if __name__ == "__main__":
    ingest_all()
    