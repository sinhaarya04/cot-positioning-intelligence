"""
Signal computation engine.
Computes COT Index, Z-scores, momentum, divergence, and inventory mismatch
from the raw COT and EIA data stored in DuckDB.
"""

import pandas as pd
import numpy as np
from src.db import get_conn, MARKET_CONFIG


def load_legacy_net_positions() -> pd.DataFrame:
    """Load legacy COT data and compute net speculative positioning."""
    conn = get_conn()
    df = conn.execute("""
        SELECT report_date, market,
               noncomm_long, noncomm_short, noncomm_spreading,
               comm_long, comm_short,
               open_interest
        FROM cot_legacy
        ORDER BY market, report_date
    """).fetchdf()
    conn.close()
    
    df["report_date"] = pd.to_datetime(df["report_date"])
    df["net_spec"] = df["noncomm_long"] - df["noncomm_short"]
    df["net_comm"] = df["comm_long"] - df["comm_short"]
    return df


def load_disagg_positions() -> pd.DataFrame:
    """Load disaggregated COT data with managed money positions."""
    conn = get_conn()
    df = conn.execute("""
        SELECT report_date, market,
               mgd_money_long, mgd_money_short, mgd_money_spreading,
               prod_merc_long, prod_merc_short,
               swap_long, swap_short,
               open_interest
        FROM cot_disagg
        ORDER BY market, report_date
    """).fetchdf()
    conn.close()
    
    df["report_date"] = pd.to_datetime(df["report_date"])
    df["mgd_money_net"] = df["mgd_money_long"] - df["mgd_money_short"]
    df["prod_merc_net"] = df["prod_merc_long"] - df["prod_merc_short"]
    return df


def load_eia_inventory() -> pd.DataFrame:
    """Load EIA inventory data."""
    conn = get_conn()
    df = conn.execute("""
        SELECT report_date, commodity AS market, inventory_level, weekly_change
        FROM eia_inventory
        ORDER BY market, report_date
    """).fetchdf()
    conn.close()
    
    df["report_date"] = pd.to_datetime(df["report_date"])
    return df


def compute_cot_index(series: pd.Series, window: int) -> pd.Series:
    """
    COT Index: percentile rank of current net position over a rolling window.
    Returns 0-100 where 100 = most bullish positioning in the window.
    """
    rolling_min = series.rolling(window, min_periods=max(1, window // 2)).min()
    rolling_max = series.rolling(window, min_periods=max(1, window // 2)).max()
    denom = rolling_max - rolling_min
    return np.where(denom == 0, 50.0, ((series - rolling_min) / denom) * 100)


def compute_z_score(series: pd.Series, window: int) -> pd.Series:
    """Rolling Z-score of a series."""
    rolling_mean = series.rolling(window, min_periods=max(1, window // 2)).mean()
    rolling_std = series.rolling(window, min_periods=max(1, window // 2)).std()
    return np.where(rolling_std == 0, 0.0, (series - rolling_mean) / rolling_std)


def compute_momentum(series: pd.Series, window: int) -> pd.Series:
    """N-week change in positioning."""
    return series.diff(window)


def compute_acceleration(series: pd.Series, window: int = 4) -> pd.Series:
    """Second derivative of positioning: change in momentum."""
    momentum = series.diff(window)
    return momentum.diff(window)


def compute_comm_spec_divergence(df: pd.DataFrame) -> pd.Series:
    """
    Divergence between commercial and speculative positioning.
    When commercials are heavily short and specs heavily long (or vice versa),
    this captures the spread. Normalized by open interest.
    """
    spread = df["net_comm"] - df["net_spec"]
    oi = df["open_interest"].replace(0, np.nan)
    return spread / oi


def compute_signals():
    """Main signal computation pipeline."""
    print("=" * 60)
    print("Signal Computation")
    print("=" * 60)
    
    # Load raw data
    legacy = load_legacy_net_positions()
    disagg = load_disagg_positions()
    eia = load_eia_inventory()
    
    all_signals = []
    
    for market in MARKET_CONFIG.keys():
        print(f"\n⚙️  {market}")
        
        # ── Legacy-based signals ──
        mkt_legacy = legacy[legacy["market"] == market].copy().sort_values("report_date")
        
        if mkt_legacy.empty:
            print(f"  ⚠️  No legacy data, skipping")
            continue
        
        net_spec = mkt_legacy["net_spec"]
        
        cot_index_52w = compute_cot_index(net_spec, 52)
        cot_index_156w = compute_cot_index(net_spec, 156)
        z_score_52w = compute_z_score(net_spec, 52)
        momentum_4w = compute_momentum(net_spec, 4)
        positioning_accel = compute_acceleration(net_spec, 4)
        comm_spec_div = compute_comm_spec_divergence(mkt_legacy)
        
        # ── Disagg-based signals ──
        mkt_disagg = disagg[disagg["market"] == market].copy().sort_values("report_date")
        
        # Merge managed money net onto legacy dates
        if not mkt_disagg.empty:
            disagg_lookup = mkt_disagg.set_index("report_date")["mgd_money_net"]
            mgd_money_net = mkt_legacy["report_date"].map(disagg_lookup).values
        else:
            mgd_money_net = [None] * len(mkt_legacy)
        
        # ── Inventory mismatch (energy only) ──
        inv_mismatch = pd.Series([None] * len(mkt_legacy), index=mkt_legacy.index)
        
        if MARKET_CONFIG[market]["eia_series"] is not None:
            mkt_eia = eia[eia["market"] == market].copy().sort_values("report_date")
            
            if not mkt_eia.empty:
                # Compute inventory Z-score
                inv_z = compute_z_score(mkt_eia["inventory_level"], 52)
                mkt_eia = mkt_eia.copy()
                mkt_eia["inv_z"] = inv_z
                
                # Merge onto COT dates (nearest weekly match)
                mkt_eia_lookup = mkt_eia.set_index("report_date")["inv_z"]
                
                # For each COT date, find nearest EIA date
                for idx, row in mkt_legacy.iterrows():
                    cot_date = row["report_date"]
                    # Find closest EIA date within 7 days
                    mask = abs(mkt_eia["report_date"] - cot_date) <= pd.Timedelta(days=7)
                    nearby = mkt_eia[mask]
                    if not nearby.empty:
                        inv_z_val = nearby.iloc[0]["inv_z"]
                        spec_z = z_score_52w[mkt_legacy.index.get_loc(idx)]
                        # Mismatch: inventory building (positive z) + specs long (positive z)
                        # = crowded trade. Sign indicates direction.
                        inv_mismatch.at[idx] = float(inv_z_val) * float(spec_z)
        
        # ── Assemble signal rows ──
        for i, (idx, row) in enumerate(mkt_legacy.iterrows()):
            all_signals.append({
                "report_date":              row["report_date"].strftime("%Y-%m-%d"),
                "market":                   market,
                "cot_index_52w":            round(float(cot_index_52w[i]), 2),
                "cot_index_156w":           round(float(cot_index_156w[i]), 2),
                "z_score_52w":              round(float(z_score_52w[i]), 4),
                "momentum_4w":              float(momentum_4w.iloc[i]) if pd.notna(momentum_4w.iloc[i]) else None,
                "mgd_money_net":            int(mgd_money_net[i]) if mgd_money_net[i] is not None and pd.notna(mgd_money_net[i]) else None,
                "comm_spec_divergence":     round(float(comm_spec_div.iloc[i]), 4) if pd.notna(comm_spec_div.iloc[i]) else None,
                "positioning_acceleration":  float(positioning_accel.iloc[i]) if pd.notna(positioning_accel.iloc[i]) else None,
                "inventory_mismatch":       float(inv_mismatch.at[idx]) if inv_mismatch.at[idx] is not None and pd.notna(inv_mismatch.at[idx]) else None,
            })
        
        print(f"  ✅ {len(mkt_legacy)} signal rows computed")
    
    # ── Write to DB ──
    conn = get_conn()
    conn.execute("DELETE FROM signals")  # fresh recompute each time
    
    sig_df = pd.DataFrame(all_signals)
    conn.execute("INSERT INTO signals SELECT * FROM sig_df")
    
    total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    non_null_inv = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE inventory_mismatch IS NOT NULL"
    ).fetchone()[0]
    
    print(f"\n📊 signals: {total} total rows")
    print(f"📊 inventory_mismatch populated: {non_null_inv} rows (energy contracts only)")
    
    # Quick sanity check: latest signals
    print("\n📋 Latest signals (most recent week):")
    latest = conn.execute("""
        SELECT market, report_date, 
               ROUND(cot_index_52w, 1) AS idx_52w,
               ROUND(z_score_52w, 2) AS z_52w,
               momentum_4w AS mom_4w,
               mgd_money_net AS mgd_net
        FROM signals
        WHERE report_date = (SELECT MAX(report_date) FROM signals)
        ORDER BY market
    """).fetchdf()
    print(latest.to_string(index=False))
    
    conn.close()
    print("\n✅ Signal computation complete.")


if __name__ == "__main__":
    compute_signals()
