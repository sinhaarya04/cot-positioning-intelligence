"""
Backtest engine: test whether COT positioning extremes predict forward returns.
For each signal, compute forward 1w/2w/4w returns conditioned on signal extremes.
"""

import pandas as pd
import numpy as np
from src.db import get_conn, MARKET_CONFIG


def load_signals_with_prices() -> pd.DataFrame:
    """Join signals with futures prices to get forward returns."""
    conn = get_conn()
    
    # Load signals
    signals = conn.execute("""
        SELECT * FROM signals ORDER BY market, report_date
    """).fetchdf()
    
    # Load prices
    prices = conn.execute("""
        SELECT price_date, market, close_price
        FROM futures_prices
        ORDER BY market, price_date
    """).fetchdf()
    
    conn.close()
    
    signals["report_date"] = pd.to_datetime(signals["report_date"])
    prices["price_date"] = pd.to_datetime(prices["price_date"])
    
    # For each signal date, find the closest price and forward prices
    all_rows = []
    
    for market in MARKET_CONFIG.keys():
        mkt_sig = signals[signals["market"] == market].copy().sort_values("report_date")
        mkt_px = prices[prices["market"] == market].copy().sort_values("price_date")
        
        if mkt_sig.empty or mkt_px.empty:
            continue
        
        px_renamed = mkt_px.rename(columns={"price_date": "report_date", "close_price": "price_t0"})
        px_renamed = px_renamed[["report_date", "price_t0"]]  # drop market column to avoid conflict
        
        merged = pd.merge_asof(
            mkt_sig, px_renamed,
            on="report_date",
            direction="nearest",
            tolerance=pd.Timedelta(days=5)

        )
        
        # Get forward prices at 1w, 2w, 4w
        for idx, row in merged.iterrows():
            d = row["report_date"]
            p0 = row.get("price_t0")
            
            if pd.isna(p0) or p0 is None or p0 == 0:
                continue
            
            fwd = {}
            for weeks, label in [(1, "fwd_1w"), (2, "fwd_2w"), (4, "fwd_4w")]:
                target_date = d + pd.Timedelta(weeks=weeks)
                # Find closest price within 5 days of target
                mask = abs(mkt_px["price_date"] - target_date) <= pd.Timedelta(days=5)
                nearby = mkt_px[mask]
                if not nearby.empty:
                    fwd_price = nearby.iloc[0]["close_price"]
                    fwd[label] = (fwd_price - p0) / p0  # percentage return
                else:
                    fwd[label] = None
            
            row_dict = row.to_dict()
            row_dict.update(fwd)
            all_rows.append(row_dict)
    
    return pd.DataFrame(all_rows)


def backtest_signal(df: pd.DataFrame, signal_col: str, market: str,
                    top_pct: float = 0.1, bot_pct: float = 0.1) -> list[dict]:
    """
    Backtest a single signal for a single market.
    Splits into top/bottom decile of the signal, computes forward return stats.
    """
    mkt = df[(df["market"] == market) & df[signal_col].notna()].copy()
    
    if len(mkt) < 50:  # need enough data
        return []
    
    results = []
    
    top_thresh = mkt[signal_col].quantile(1 - top_pct)
    bot_thresh = mkt[signal_col].quantile(bot_pct)
    
    for horizon in ["fwd_1w", "fwd_2w", "fwd_4w"]:
        horizon_data = mkt[mkt[horizon].notna()]
        
        if horizon_data.empty:
            continue
        
        # Top decile (high signal → expect bullish?)
        top = horizon_data[horizon_data[signal_col] >= top_thresh]
        if len(top) >= 10:
            avg_ret = top[horizon].mean()
            hit_rate = (top[horizon] > 0).mean()
            std_ret = top[horizon].std()
            sharpe = avg_ret / std_ret if std_ret > 0 else 0
            
            results.append({
                "market": market,
                "signal_name": signal_col,
                "horizon": horizon.replace("fwd_", ""),
                "threshold": "top_decile",
                "n_signals": len(top),
                "hit_rate": round(hit_rate, 4),
                "avg_return": round(avg_ret, 6),
                "sharpe": round(sharpe, 4),
            })
        
        # Bottom decile (low signal → expect bearish?)
        bot = horizon_data[horizon_data[signal_col] <= bot_thresh]
        if len(bot) >= 10:
            avg_ret = bot[horizon].mean()
            hit_rate = (bot[horizon] > 0).mean()
            std_ret = bot[horizon].std()
            sharpe = avg_ret / std_ret if std_ret > 0 else 0
            
            results.append({
                "market": market,
                "signal_name": signal_col,
                "horizon": horizon.replace("fwd_", ""),
                "threshold": "bot_decile",
                "n_signals": len(bot),
                "hit_rate": round(hit_rate, 4),
                "avg_return": round(avg_ret, 6),
                "sharpe": round(sharpe, 4),
            })
    
    return results


def run_backtest():
    """Run full backtest across all signals, markets, and horizons."""
    print("=" * 60)
    print("Backtest Engine")
    print("=" * 60)
    
    print("\n⏳ Loading signals and prices (this may take a minute)...")
    df = load_signals_with_prices()
    print(f"  ✅ {len(df)} signal-price rows loaded")
    
    # Signals to test
    signal_cols = [
        "cot_index_52w",
        "cot_index_156w",
        "z_score_52w",
        "momentum_4w",
        "comm_spec_divergence",
        "positioning_acceleration",
        "inventory_mismatch",
    ]
    
    all_results = []
    
    for market in MARKET_CONFIG.keys():
        print(f"\n📊 {market}")
        
        for sig in signal_cols:
            results = backtest_signal(df, sig, market)
            if results:
                all_results.extend(results)
                # Print best result for this signal/market
                best = max(results, key=lambda x: abs(x["avg_return"]))
                direction = "📈" if best["avg_return"] > 0 else "📉"
                print(f"  {sig:30s} | {best['threshold']:12s} {best['horizon']:3s} | "
                      f"hit={best['hit_rate']:.1%} avg={best['avg_return']:+.4f} "
                      f"sharpe={best['sharpe']:+.3f} n={best['n_signals']} {direction}")
    
    # ── Write results to DB ──
    conn = get_conn()
    conn.execute("DELETE FROM backtest_results")
    
    if all_results:
        res_df = pd.DataFrame(all_results)
        conn.execute("INSERT INTO backtest_results SELECT * FROM res_df")
    
    total = conn.execute("SELECT COUNT(*) FROM backtest_results").fetchone()[0]
    
    # ── Summary: best signals across all markets ──
    print("\n" + "=" * 60)
    print("TOP 15 SIGNALS BY ABSOLUTE AVERAGE RETURN")
    print("=" * 60)
    
    top_signals = conn.execute("""
        SELECT market, signal_name, horizon, threshold,
               n_signals, hit_rate, avg_return, sharpe
        FROM backtest_results
        WHERE n_signals >= 20
        ORDER BY ABS(avg_return) DESC
        LIMIT 15
    """).fetchdf()
    
    print(top_signals.to_string(index=False))
    
    # ── Signals with hit rate > 55% ──
    print("\n" + "=" * 60)
    print("SIGNALS WITH HIT RATE > 55% (n >= 20)")
    print("=" * 60)
    
    high_hit = conn.execute("""
        SELECT market, signal_name, horizon, threshold,
               n_signals, hit_rate, avg_return, sharpe
        FROM backtest_results
        WHERE hit_rate > 0.55 AND n_signals >= 20
        ORDER BY hit_rate DESC
        LIMIT 15
    """).fetchdf()
    
    print(high_hit.to_string(index=False))
    
    conn.close()
    print(f"\n📊 backtest_results: {total} total rows")
    print("✅ Backtest complete.")


if __name__ == "__main__":
    run_backtest()
    
