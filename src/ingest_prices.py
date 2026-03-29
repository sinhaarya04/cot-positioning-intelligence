"""
Ingest futures prices (via yfinance) and EIA inventory data.
Prices are needed for the backtest module; EIA for inventory-positioning mismatch signals.
"""

import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
from src.db import get_conn, MARKET_CONFIG


# ── EIA API (free, requires key from https://www.eia.gov/opendata/register.php) ──
# If you don't have a key yet, set this to None and we'll skip EIA
EIA_API_KEY = "KpcYX7axCFV8Lzjgqzzpc5kn0zLwdPypGwvGYDZh"  # Replace with your key: "your_key_here"


def ingest_futures_prices():
    """Pull weekly futures close prices for all markets via yfinance."""
    print("\n" + "=" * 60)
    print("Futures Price Ingestion")
    print("=" * 60)
    
    conn = get_conn()
    
    for market, config in MARKET_CONFIG.items():
        ticker = config["yf_ticker"]
        print(f"\n📈 {market} ({ticker})")
        
        try:
            # Pull max history, weekly frequency
            df = yf.download(ticker, period="max", interval="1wk", progress=False)
            
            if df.empty:
                print(f"  ⚠️  No price data for {ticker}")
                continue
            
            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df = df.reset_index()
            df["market"] = market
            
            # Rename columns to match schema
            price_df = pd.DataFrame({
                "price_date": pd.to_datetime(df["Date"]).dt.date,
                "market": market,
                "close_price": df["Close"].astype(float),
                "volume": df["Volume"].fillna(0).astype(int),
            })
            
            # Remove existing rows for this market, then insert
            conn.execute("DELETE FROM futures_prices WHERE market = ?", [market])
            conn.execute("INSERT INTO futures_prices SELECT * FROM price_df")
            
            print(f"  ✅ {len(price_df)} weekly bars ({price_df['price_date'].min()} to {price_df['price_date'].max()})")
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
    
    # Summary
    total = conn.execute("SELECT COUNT(*) FROM futures_prices").fetchone()[0]
    print(f"\n📊 futures_prices: {total} total rows")
    conn.close()


def ingest_eia_inventory():
    """Pull EIA petroleum and natural gas inventory data."""
    print("\n" + "=" * 60)
    print("EIA Inventory Ingestion")
    print("=" * 60)
    
    if EIA_API_KEY is None:
        print("  ⚠️  No EIA API key set. Skipping EIA ingestion.")
        print("  📝 Get a free key at: https://www.eia.gov/opendata/register.php")
        print("  Then set EIA_API_KEY in src/ingest_prices.py")
        return
    
    conn = get_conn()
    
    eia_markets = {
        k: v for k, v in MARKET_CONFIG.items() if v["eia_series"] is not None
    }
    
    for market, config in eia_markets.items():
        series_id = config["eia_series"]
        print(f"\n🛢️  {market} (EIA: {series_id})")
        
        try:
            # EIA API v2
            url = "https://api.eia.gov/v2/seriesid/" + series_id
            params = {
                "api_key": EIA_API_KEY,
                "frequency": "weekly",
                "data[0]": "value",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 5000,
            }
            
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            
            records = data.get("response", {}).get("data", [])
            if not records:
                print(f"  ⚠️  No EIA data for {series_id}")
                continue
            
            rows = []
            for i, rec in enumerate(records):
                val = float(rec.get("value", 0) or 0)
                prev_val = float(records[i + 1].get("value", 0) or 0) if i + 1 < len(records) else 0
                rows.append({
                    "report_date": rec["period"],
                    "commodity": market,
                    "series_id": series_id,
                    "inventory_level": val,
                    "weekly_change": val - prev_val,
                })
            
            eia_df = pd.DataFrame(rows)
            conn.execute("DELETE FROM eia_inventory WHERE commodity = ?", [market])
            conn.execute("INSERT INTO eia_inventory SELECT * FROM eia_df")
            
            print(f"  ✅ {len(eia_df)} weeks of inventory data")
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
    
    total = conn.execute("SELECT COUNT(*) FROM eia_inventory").fetchone()[0]
    print(f"\n📊 eia_inventory: {total} total rows")
    conn.close()


def ingest_all():
    """Run both price and EIA ingestion."""
    ingest_futures_prices()
    ingest_eia_inventory()
    print("\n✅ All price/inventory ingestion complete.")


if __name__ == "__main__":
    ingest_all()
