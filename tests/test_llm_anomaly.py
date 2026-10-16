import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src import db, llm_anomaly


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("COT_DB_PATH", str(tmp_path / "research.duckdb"))
    db.init_schema()


def payload(**updates):
    result = {
        "market": "GOLD", "report_date": "2024-01-09", "signal_type": "EXTREME_BULLISH",
        "directional_bias": 40, "confidence": 0.5, "narrative": "Positioning is high. Interpretation is unvalidated.",
    }
    result.update(updates)
    return result


def seed_signals():
    conn = db.get_conn()
    try:
        conn.execute("""INSERT INTO signals (report_date, market, cot_index_52w, z_score_52w, evaluation_version)
                        VALUES ('2024-01-02', 'GOLD', 50, 0, 'release_aware_v1'),
                               ('2024-01-09', 'GOLD', 95, 2, 'release_aware_v1'),
                               ('2024-01-02', 'SILVER', 5, -2, 'release_aware_v1')""")
    finally:
        conn.close()


@pytest.mark.parametrize("updates", [
    {"market": "SILVER"}, {"report_date": "2024-01-02"}, {"report_date": None},
    {"signal_type": "NOT_A_SIGNAL"}, {"signal_type": []},
    {"directional_bias": -101}, {"directional_bias": 101}, {"directional_bias": 40.5},
    {"directional_bias": "40"}, {"directional_bias": True}, {"directional_bias": None},
    {"confidence": -0.1}, {"confidence": 1.01}, {"confidence": float("inf")},
    {"confidence": float("nan")}, {"confidence": "0.5"}, {"confidence": True},
    {"confidence": 10 ** 400},
    {"narrative": "  "}, {"narrative": []}, {"narrative": "x" * 2001},
    {"extra": "not allowed"},
])
def test_rejects_invalid_model_output(updates):
    with pytest.raises(ValueError):
        llm_anomaly.validate_response(json.dumps(payload(**updates)), "GOLD", "2024-01-09")


@pytest.mark.parametrize("response", ["not json", "[]", "{}", "null", '{"market":"GOLD","market":"SILVER"}'])
def test_rejects_malformed_missing_or_duplicate_fields(response):
    with pytest.raises(ValueError):
        llm_anomaly.validate_response(response, "GOLD", "2024-01-09")


def test_valid_boundaries():
    for bias in [-100, 100]:
        for confidence in [0, 1]:
            result = llm_anomaly.validate_response(json.dumps(payload(directional_bias=bias, confidence=confidence)),
                                                   "GOLD", "2024-01-09")
            assert result["directional_bias"] == bias
            assert result["confidence"] == float(confidence)


def test_latest_selection_keeps_lagging_markets(database):
    seed_signals()
    latest, latest_date = llm_anomaly.get_latest_anomalies()
    assert latest_date.isoformat() == "2024-01-09"
    assert latest.set_index("market")["report_date"].dt.strftime("%Y-%m-%d").to_dict() == {
        "GOLD": "2024-01-09", "SILVER": "2024-01-02"
    }
    assert latest["is_anomaly"].all()


def test_prompt_uses_row_date_without_invalid_return_context():
    row = pd.Series({"market": "SILVER", "report_date": "2024-01-02", "cot_index_52w": 50,
                     "z_score_52w": 2, "idx_hit_rate": 0.99, "idx_avg_return": 0.8})
    prompt = llm_anomaly.build_prompt(row, "2024-01-09")
    assert "2024-01-02" in prompt
    assert "2024-01-09" not in prompt
    assert "99%" not in prompt
    assert "hit rate" not in prompt
    assert "min-max normalization" in prompt
    assert "not prediction accuracy" in prompt


def test_empty_database_does_not_load_model(database, monkeypatch):
    monkeypatch.setattr(llm_anomaly, "_load_generator", lambda: pytest.fail("No model should load"))
    assert llm_anomaly.run_llm_analysis() == 0


def test_stale_signals_do_not_trigger_inference(database, monkeypatch):
    seed_signals()
    with db.get_conn() as conn:
        conn.execute("UPDATE signals SET evaluation_version = 'stale'")
    monkeypatch.setattr(llm_anomaly, "_load_generator", lambda: pytest.fail("Stale signals cannot trigger inference"))
    assert llm_anomaly.run_llm_analysis() == 0


def test_failure_isolated_to_one_market_and_previous_output_preserved(database, monkeypatch):
    seed_signals()
    conn = db.get_conn()
    conn.execute("""INSERT INTO llm_anomalies (report_date, market, narrative)
                    VALUES ('2024-01-09', 'GOLD', 'Existing explanation')""")
    conn.close()

    def generator(prompt):
        if "for GOLD" in prompt:
            raise RuntimeError("Mock inference failed")
        return json.dumps(payload(market="SILVER", report_date="2024-01-02"))

    monkeypatch.setattr(llm_anomaly, "_load_generator", lambda: (generator, {
        "model_name": "mock", "model_revision": "test-revision"
    }))
    assert llm_anomaly.run_llm_analysis() == 1
    conn = db.get_conn()
    saved = conn.execute("SELECT * FROM llm_anomalies ORDER BY market").fetchdf()
    conn.close()
    assert saved.iloc[0]["narrative"] == "Existing explanation"
    assert saved.iloc[1]["market"] == "SILVER"
    assert str(saved.iloc[1]["report_date"].date()) == "2024-01-02"
    assert saved.iloc[1]["model_revision"] == "test-revision"
    assert saved.iloc[1]["prompt_version"] == llm_anomaly.PROMPT_VERSION
    assert pd.isna(saved.iloc[1]["historical_hit_rate"])
    assert json.loads(saved.iloc[1]["generation_parameters"])["do_sample"] is False


def test_misidentified_output_never_persisted(database, monkeypatch):
    seed_signals()
    monkeypatch.setattr(llm_anomaly, "_load_generator", lambda: (
        lambda _: json.dumps(payload(market="COPPER")), {"model_name": "mock", "model_revision": "test"}
    ))
    assert llm_anomaly.run_llm_analysis() == 0
    conn = db.get_conn()
    assert conn.execute("SELECT COUNT(*) FROM llm_anomalies").fetchone()[0] == 0
    conn.close()


def test_module_import_does_not_import_optional_model_libraries():
    code = "import sys; import src.llm_anomaly; assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], check=True)
