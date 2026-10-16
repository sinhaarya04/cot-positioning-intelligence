from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src import dashboard, db
from src.llm_anomaly import PROMPT_VERSION


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.duckdb"
    monkeypatch.setenv("COT_DB_PATH", str(path))
    return path


def test_fresh_install_creates_schema_and_renders(database):
    assert not database.exists()
    app = AppTest.from_file(str(Path(dashboard.__file__))).run(timeout=30)
    assert not app.exception
    assert database.exists()
    assert any("No signals" in element.value for element in app.info)
    assert any("No corrected evaluations" in element.value for element in app.info)


def test_latest_market_and_freshness_labels():
    signals = pd.DataFrame({"market": ["GOLD", "GOLD", "SILVER"],
                            "report_date": pd.to_datetime(["2024-01-16", "2024-01-23", "2024-01-02"])})
    latest = dashboard.add_freshness(dashboard.latest_per_market(signals), now="2024-01-30").set_index("market")
    assert len(latest) == 2
    assert latest.loc["GOLD", "report_age_days"] == 7
    assert latest.loc["SILVER", "report_age_days"] == 28
    assert latest.loc["SILVER", "lag_vs_latest_days"] == 21
    assert latest.loc["SILVER", "freshness"] == "Stale observation"


def test_legacy_results_are_never_validated():
    old = pd.DataFrame({"market": ["GOLD"], "hit_rate": [0.99], "sharpe": [9.0]})
    assert dashboard.validated_backtest_results(old).empty
    mixed = pd.DataFrame({"market": ["GOLD", "SILVER"], "evaluation_version": [None, "release_aware_v1"]})
    assert dashboard.validated_backtest_results(mixed)["market"].tolist() == ["SILVER"]


def test_legacy_weekly_prices_are_hidden(database):
    db.init_schema()
    conn = db.get_conn()
    conn.execute("""INSERT INTO futures_prices (price_date, market, close_price, price_kind)
                    VALUES ('2024-01-08', 'GOLD', 100, 'legacy_unknown'),
                           ('2024-01-09', 'GOLD', 101, 'daily_close_proxy')""")
    conn.close()
    assert dashboard.load_prices()["close_price"].tolist() == [101]


def test_populated_dashboard_hides_old_metrics_and_dates_old_alerts(database):
    db.init_schema()
    conn = db.get_conn()
    conn.execute("""INSERT INTO signals (report_date, market, cot_index_52w, z_score_52w, evaluation_version)
                    VALUES ('2024-01-09', 'GOLD', 95, 2, 'release_aware_v1'),
                           ('2024-01-02', 'SILVER', 5, -2, 'release_aware_v1')""")
    conn.execute("""INSERT INTO backtest_results
                    (market, signal_name, horizon, threshold, hit_rate, sharpe)
                    VALUES ('GOLD', 'cot_index_52w', '4w', 'top_decile', 0.99, 9)""")
    conn.execute("""INSERT INTO backtest_results
                    (market, signal_name, horizon, threshold, positive_return_rate, mean_over_std,
                     n_signals, avg_return, evaluation_version)
                    VALUES ('SILVER', 'cot_index_52w', '4w', 'top_decile', 0.51, 0.01, 100, 0.001, 'release_aware_v1')""")
    conn.execute("""INSERT INTO llm_anomalies
                    (report_date, market, signal_type, directional_bias, confidence, narrative, prompt_version)
                    VALUES ('2024-01-02', 'SILVER', 'EXTREME_BEARISH', -40, 0.5, 'Observed positioning is low.', ?)""", [PROMPT_VERSION])
    conn.close()
    app = AppTest.from_file(str(Path(dashboard.__file__))).run(timeout=30)
    assert not app.exception
    assert any("Hidden 1 legacy evaluation rows" in element.value for element in app.warning)
    assert any("SILVER | observed 2024-01-02 | Stale" in element.label for element in app.expander)
    assert not any("hit_rate" in element.value.columns or "sharpe" in element.value.columns for element in app.dataframe)
    latest = dashboard.load_latest_signals()
    assert set(latest["market"]) == {"GOLD", "SILVER"}


def test_stale_signals_hidden_with_recompute_instruction(database):
    db.init_schema()
    with db.get_conn() as conn:
        conn.execute("""INSERT INTO signals (report_date, market, cot_index_52w, evaluation_version)
                        VALUES ('2024-01-09', 'GOLD', 95, 'stale')""")
    assert dashboard.load_signals().empty
    app = AppTest.from_file(str(Path(dashboard.__file__))).run(timeout=30)
    assert not app.exception
    assert any("legacy or stale signal rows" in element.value and "python -m src.signals" in element.value
               for element in app.warning)
