"""Optional, uncalibrated LLM explanations of observed positioning anomalies.

The model is imported/downloaded only when this module is explicitly run with
anomalous data. Its scores are explanatory opinions, not trading forecasts.
"""

import json
import math
import os
from datetime import date, datetime, timezone

import pandas as pd

from src.db import MARKET_CONFIG, get_conn, init_schema, write_frame

PROMPT_VERSION = "positioning_explanation_v1"
SIGNAL_EVALUATION_VERSION = "release_aware_v1"
SIGNAL_TYPES = frozenset({
    "EXTREME_BULLISH", "EXTREME_BEARISH", "DIVERGENCE", "MOMENTUM_SHIFT", "NEUTRAL"
})
OUTPUT_FIELDS = frozenset({
    "market", "report_date", "signal_type", "directional_bias", "confidence", "narrative"
})
GENERATION_PARAMETERS = {"do_sample": False, "max_new_tokens": 400}


def get_latest_anomalies() -> tuple[pd.DataFrame, date | None]:
    """Return each market's latest report, including markets lagging the panel."""
    init_schema()
    conn = get_conn()
    try:
        latest = conn.execute("""
            SELECT * EXCLUDE (row_num) FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY market ORDER BY report_date DESC
                ) AS row_num FROM signals WHERE evaluation_version = ?
            ) WHERE row_num = 1 ORDER BY market
        """, [SIGNAL_EVALUATION_VERSION]).fetchdf()
    finally:
        conn.close()
    latest["is_anomaly"] = (
        latest["z_score_52w"].abs().gt(1.5)
        | latest["cot_index_52w"].gt(85)
        | latest["cot_index_52w"].lt(15)
    ).fillna(False)
    latest_date = None if latest.empty else pd.Timestamp(latest["report_date"].max()).date()
    return latest, latest_date


def _number(value, fmt=".2f") -> str:
    if value is None or pd.isna(value):
        return "unavailable"
    return format(value, fmt)


def build_prompt(row: pd.Series, latest_date=None) -> str:
    """Describe the source row without mismatched retrospective return buckets."""
    report_date = pd.Timestamp(row.get("report_date", latest_date)).date().isoformat()
    cot_index = row.get("cot_index_52w")
    z_score = row.get("z_score_52w")
    if pd.notna(cot_index) and cot_index > 85:
        positioning = "HIGH relative to the rolling minimum and maximum"
    elif pd.notna(cot_index) and cot_index < 15:
        positioning = "LOW relative to the rolling minimum and maximum"
    elif pd.notna(z_score) and abs(z_score) > 1.5:
        positioning = "UNUSUAL relative to the rolling mean"
    else:
        positioning = "NO FLAGGED EXTREME"
    return f"""Explain the observed CFTC positioning for {row['market']}.
Observation date: {report_date}
Publication timestamp: {row.get('release_at', 'unknown')}
Publication quality: {row.get('release_quality', 'unknown')}
Data vintage: {row.get('data_vintage', 'unknown')}

POSITIONING DATA:
- COT index (52-report min-max normalization, NOT a percentile): {_number(cot_index)}
- COT index (156-report min-max normalization): {_number(row.get('cot_index_156w'))}
- Z-score (52-report): {_number(z_score)}
- Positioning: {positioning}
- Four-week net-position change in contracts: {_number(row.get('momentum_4w'), '+,.0f')}
- Managed-money net contracts: {_number(row.get('mgd_money_net'), '+,.0f')}
- Commercial-speculative divergence: {_number(row.get('comm_spec_divergence'), '.4f')}
- Inventory-positioning interaction (unvalidated, no directional interpretation): {_number(row.get('inventory_mismatch'))}

Explain the observations and missing-data limitations. Do not claim causation,
trading profitability, a calibrated probability, or a validated future return.
The directional_bias is an unvalidated interpretation of positioning, not a trade
recommendation. Confidence is a subjective self-rating, not prediction accuracy.
Respond with ONLY a JSON object with exactly these fields:
- "market": "{row['market']}"
- "report_date": "{report_date}"
- "signal_type": one of "EXTREME_BULLISH", "EXTREME_BEARISH", "DIVERGENCE", "MOMENTUM_SHIFT", "NEUTRAL"
- "directional_bias": integer from -100 to 100
- "confidence": finite number from 0 to 1
- "narrative": nonempty string of 2-3 explanatory sentences, at most 2000 characters
"""


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def validate_response(response: str, market: str, report_date) -> dict:
    """Reject malformed or misidentified output before logging or persistence."""
    if not isinstance(response, str):
        raise ValueError("Model response must be JSON text")
    result = json.loads(response, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    if not isinstance(result, dict) or set(result) != OUTPUT_FIELDS:
        raise ValueError("Model response must contain exactly the documented fields")
    expected_date = pd.Timestamp(report_date).date().isoformat()
    if market not in MARKET_CONFIG or result["market"] != market:
        raise ValueError("Model market does not match the source row")
    if result["report_date"] != expected_date:
        raise ValueError("Model report_date does not match the source row")
    if not isinstance(result["signal_type"], str) or result["signal_type"] not in SIGNAL_TYPES:
        raise ValueError("Unknown signal_type")
    bias = result["directional_bias"]
    if type(bias) is not int or not -100 <= bias <= 100:
        raise ValueError("directional_bias must be an integer in [-100, 100]")
    confidence = result["confidence"]
    if type(confidence) not in (int, float) or not 0 <= confidence <= 1 or not math.isfinite(confidence):
        raise ValueError("confidence must be a finite number in [0, 1]")
    narrative = result["narrative"]
    if not isinstance(narrative, str) or not narrative.strip() or len(narrative) > 2000:
        raise ValueError("narrative must contain 1-2000 nonblank characters")
    result["narrative"] = narrative.strip()
    result["confidence"] = float(confidence)
    return result


def _load_generator():
    """Load optional dependencies on demand; return generator and provenance."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_name = os.environ.get("COT_LLM_MODEL", "Qwen/Qwen2.5-3B-Instruct")
    revision = os.environ.get("COT_LLM_MODEL_REVISION") or None
    tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
    use_cuda = torch.cuda.is_available()
    model_kwargs = {"revision": revision, "torch_dtype": torch.float16 if use_cuda else torch.float32}
    if use_cuda:
        model_kwargs["device_map"] = "cuda"
    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
    model.eval()
    resolved_revision = getattr(model.config, "_commit_hash", None) or revision or "unresolved"

    def generate(prompt):
        messages = [
            {"role": "system", "content": "Explain observations without forecasting claims. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to(model.device)
        with torch.inference_mode():
            output = model.generate(**inputs, **GENERATION_PARAMETERS)
        return tokenizer.decode(output[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)

    return generate, {"model_name": model_name, "model_revision": resolved_revision}


def run_llm_analysis() -> int:
    """Generate explanations; a failed market never removes earlier saved rows."""
    latest, _ = get_latest_anomalies()
    anomalies = latest[latest["is_anomaly"]]
    if anomalies.empty:
        print("No observed positioning anomalies; no model loaded.")
        return 0
    try:
        generate, provenance = _load_generator()
    except Exception as exc:
        print(f"Optional LLM unavailable: {type(exc).__name__}: {exc}")
        return 0

    results = []
    failures = []
    for _, row in anomalies.iterrows():
        market = row["market"]
        try:
            response = generate(build_prompt(row))
            result = validate_response(response, market, row["report_date"])
            result.update(provenance)
            result.update({
                "prompt_version": PROMPT_VERSION,
                "generated_at": datetime.now(timezone.utc),
                "generation_parameters": json.dumps(GENERATION_PARAMETERS, sort_keys=True),
            })
            results.append(result)
            print(f"{market} ({result['report_date']}): explanation validated")
        except Exception as exc:
            failures.append(market)
            print(f"{market}: explanation skipped ({type(exc).__name__}: {exc})")
    if results:
        write_frame("llm_anomalies", pd.DataFrame(results), mode="upsert", keys=["report_date", "market"])
    if failures:
        print(f"Incomplete LLM run; failed markets: {', '.join(failures)}")
    return len(results)


if __name__ == "__main__":
    run_llm_analysis()
