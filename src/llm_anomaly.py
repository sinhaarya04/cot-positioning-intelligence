"""
LLM-based anomaly detection layer.
Identifies statistically unusual positioning configs and generates
structured analysis using Qwen 2.5 3B via HuggingFace transformers.

Requires GPU node: srun --partition courses-gpu --gres=gpu:1 --mem=32Gb --time=01:00:00
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from src.db import get_conn, MARKET_CONFIG


def get_latest_anomalies() -> pd.DataFrame:
    """Find markets with statistically unusual positioning this week."""
    conn = get_conn()
    
    latest_date = conn.execute(
        "SELECT MAX(report_date) FROM signals"
    ).fetchone()[0]
    
    # Get latest signals + backtest context
    latest = conn.execute("""
        SELECT s.*,
               b_idx.hit_rate AS idx_hit_rate,
               b_idx.avg_return AS idx_avg_return,
               b_div.hit_rate AS div_hit_rate,
               b_div.avg_return AS div_avg_return
        FROM signals s
        LEFT JOIN backtest_results b_idx 
            ON s.market = b_idx.market 
            AND b_idx.signal_name = 'cot_index_52w' 
            AND b_idx.horizon = '4w'
            AND b_idx.threshold = CASE 
                WHEN s.cot_index_52w > 80 THEN 'top_decile'
                WHEN s.cot_index_52w < 20 THEN 'bot_decile'
                ELSE 'top_decile' END
        LEFT JOIN backtest_results b_div
            ON s.market = b_div.market
            AND b_div.signal_name = 'comm_spec_divergence'
            AND b_div.horizon = '4w'
            AND b_div.threshold = CASE
                WHEN s.comm_spec_divergence > 0 THEN 'top_decile'
                ELSE 'bot_decile' END
        WHERE s.report_date = ?
        ORDER BY ABS(s.z_score_52w) DESC
    """, [latest_date]).fetchdf()
    
    conn.close()
    
    # Flag anomalies: Z-score beyond 1.5σ or COT index in extremes
    latest["is_anomaly"] = (
        (latest["z_score_52w"].abs() > 1.5) |
        (latest["cot_index_52w"] > 85) |
        (latest["cot_index_52w"] < 15)
    )
    
    return latest, latest_date


def build_prompt(row: pd.Series, latest_date: str) -> str:
    """Build a structured prompt for the LLM to analyze one market."""
    
    # Determine positioning context
    if row["cot_index_52w"] > 80:
        positioning = "EXTREMELY BULLISH (top quintile over 52 weeks)"
    elif row["cot_index_52w"] < 20:
        positioning = "EXTREMELY BEARISH (bottom quintile over 52 weeks)"
    elif row["z_score_52w"] > 1.5:
        positioning = "UNUSUALLY BULLISH (Z-score > 1.5)"
    elif row["z_score_52w"] < -1.5:
        positioning = "UNUSUALLY BEARISH (Z-score < -1.5)"
    else:
        positioning = "NEUTRAL"
    
    # Momentum context
    mom = row.get("momentum_4w")
    if pd.notna(mom):
        mom_dir = "INCREASING" if mom > 0 else "DECREASING"
        mom_str = f"4-week momentum: {mom_dir} ({mom:+,.0f} contracts)"
    else:
        mom_str = "4-week momentum: N/A"
    
    # Managed money
    mgd = row.get("mgd_money_net")
    mgd_str = f"Managed money net: {mgd:+,.0f} contracts" if pd.notna(mgd) else "Managed money: N/A"
    
    # Backtest context
    idx_hr = row.get("idx_hit_rate")
    idx_ret = row.get("idx_avg_return")
    bt_str = ""
    if pd.notna(idx_hr) and pd.notna(idx_ret):
        bt_str = f"\nHistorical backtest at this positioning extreme: {idx_hr:.1%} hit rate, {idx_ret:+.2%} avg 4-week return"
    
    # Inventory (energy only)
    inv = row.get("inventory_mismatch")
    inv_str = ""
    if pd.notna(inv):
        inv_str = f"\nInventory-positioning mismatch score: {inv:.2f} ({'CROWDED' if abs(inv) > 1 else 'NORMAL'})"
    
    prompt = f"""You are a quantitative commodity analyst. Analyze the following CFTC positioning data for {row['market']} as of {latest_date}.

POSITIONING DATA:
- COT Index (52-week percentile): {row['cot_index_52w']:.1f}
- COT Index (156-week percentile): {row['cot_index_156w']:.1f}
- Z-Score (52-week): {row['z_score_52w']:+.2f}
- Positioning: {positioning}
- {mom_str}
- {mgd_str}
- Commercial-Speculative Divergence: {row.get('comm_spec_divergence', 'N/A')}{bt_str}{inv_str}

Respond with ONLY a JSON object (no markdown, no backticks) with these fields:
- "market": "{row['market']}"
- "signal_type": one of "EXTREME_BULLISH", "EXTREME_BEARISH", "DIVERGENCE", "MOMENTUM_SHIFT", "NEUTRAL"
- "directional_bias": integer from -100 (max bearish) to +100 (max bullish) for the NEXT 4 WEEKS
- "confidence": float from 0.0 to 1.0
- "narrative": 2-3 sentence analysis explaining the positioning and expected direction
"""
    return prompt


def run_llm_analysis():
    """Run LLM anomaly detection on latest signals."""
    print("=" * 60)
    print("LLM Anomaly Detection")
    print("=" * 60)
    
    latest, latest_date = get_latest_anomalies()
    anomalies = latest[latest["is_anomaly"]]
    
    print(f"\n📅 Report date: {latest_date}")
    print(f"📊 {len(anomalies)} anomalous markets out of {len(latest)} total")
    
    if anomalies.empty:
        print("  No anomalies detected this week.")
        return
    
    # Load model
    print("\n⏳ Loading Qwen 2.5 3B model...")
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        model_name = "Qwen/Qwen2.5-3B-Instruct"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(
            model_name, dtype=torch.float16, device_map="cuda"
        )
        print("  ✅ Model loaded on GPU")
    except Exception as e:
        print(f"  ❌ GPU model failed: {e}")
        print("  Falling back to CPU (slower)...")
        try:
            model = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.float32)
            print("  ✅ Model loaded on CPU")
        except Exception as e2:
            print(f"  ❌ CPU also failed: {e2}")
            print("  Skipping LLM analysis.")
            return
    
    # Analyze each anomalous market
    results = []
    
    for _, row in anomalies.iterrows():
        market = row["market"]
        print(f"\n🤖 Analyzing {market}...")
        
        prompt = build_prompt(row, latest_date)
        
        messages = [
            {"role": "system", "content": "You are a quantitative commodity analyst. Respond only in valid JSON."},
            {"role": "user", "content": prompt}
        ]
        
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to(model.device)
        
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=300,
                temperature=0.3,
                do_sample=True,
                top_p=0.9,
            )
        
        response = tokenizer.decode(output[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
        
        # Parse JSON response
        try:
            # Clean up response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            result = json.loads(response)
            result["report_date"] = latest_date
            result["historical_hit_rate"] = float(row.get("idx_hit_rate", 0) or 0)
            results.append(result)
            
            bias = result.get("directional_bias", 0)
            arrow = "📈" if bias > 0 else "📉" if bias < 0 else "➡️"
            print(f"  {arrow} Bias: {bias:+d} | Confidence: {result.get('confidence', 0):.0%}")
            print(f"  💬 {result.get('narrative', 'N/A')}")
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ⚠️  Failed to parse LLM response: {e}")
            print(f"  Raw: {response[:200]}")
    
    # ── Write to DB ──
    if results:
        conn = get_conn()
        conn.execute(f"DELETE FROM llm_anomalies WHERE report_date = '{latest_date}'")
        
        for r in results:
            conn.execute("""
                INSERT INTO llm_anomalies VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                r.get("report_date", latest_date),
                r.get("market", ""),
                r.get("signal_type", ""),
                r.get("directional_bias", 0),
                r.get("confidence", 0.0),
                r.get("historical_hit_rate", 0.0),
                r.get("narrative", ""),
            ])
        
        conn.close()
        print(f"\n📊 Saved {len(results)} anomaly analyses to DB")
    
    print("\n✅ LLM anomaly detection complete.")


if __name__ == "__main__":
    run_llm_analysis()
