import numpy as np
import pandas as pd
import pytest

from src import backtest


def signal_rows(n=1):
    dates = pd.date_range("2024-01-02", periods=n, freq="7D")
    return pd.DataFrame({
        "market": "GOLD", "report_date": dates,
        "release_at": (dates + pd.Timedelta(days=3, hours=20, minutes=30)).tz_localize("UTC"),
        "release_quality": "verified", "analysis_eligible": True,
        "evaluation_version": "release_aware_v1",
        "z_score_52w": np.arange(n, dtype=float),
    })


def daily_prices():
    dates = pd.bdate_range("2024-01-05", periods=35)
    return pd.DataFrame({
        "market": "GOLD", "price_date": dates,
        "close_price": np.arange(len(dates), dtype=float) + 100,
        "price_kind": "daily_close_proxy", "source": "test", "price_at": pd.NaT,
    })


def test_proxy_excludes_release_day_and_exits_five_later_sessions():
    result = backtest.build_forward_returns(signal_rows(), daily_prices()).iloc[0]
    assert result["entry_date"] == pd.Timestamp("2024-01-08")
    assert result["fwd_1w_exit_date"] == pd.Timestamp("2024-01-15")
    assert result["fwd_1w"] == pytest.approx(106 / 101 - 1)
    assert result["fwd_2w_exit_date"] == pd.Timestamp("2024-01-22")
    assert result["fwd_4w_exit_date"] == pd.Timestamp("2024-02-05")


def test_proxy_uses_new_york_release_date_not_utc_date():
    signals = signal_rows()
    signals["release_at"] = pd.to_datetime(["2024-01-09T01:00:00Z"])
    result = backtest.build_forward_returns(signals, daily_prices()).iloc[0]
    # 01:00 UTC Tuesday is Monday evening in New York.
    assert result["entry_date"] == pd.Timestamp("2024-01-09")


def test_timestamped_settlement_must_be_strictly_after_release():
    prices = daily_prices()
    prices["price_kind"] = "contract_settlement"
    prices["price_at"] = (prices["price_date"] + pd.Timedelta(hours=20, minutes=30)).dt.tz_localize("UTC")
    equal = backtest.build_forward_returns(signal_rows(), prices).iloc[0]
    assert equal["entry_date"] == pd.Timestamp("2024-01-08")
    prices.loc[0, "price_at"] += pd.Timedelta(seconds=1)
    later = backtest.build_forward_returns(signal_rows(), prices).iloc[0]
    assert later["entry_date"] == pd.Timestamp("2024-01-05")


def test_unknown_releases_and_unknown_price_provenance_are_excluded():
    signals = signal_rows()
    signals["release_quality"] = "unknown"
    assert backtest.build_forward_returns(signals, daily_prices()).iloc[0]["return_status"] == "unknown_release"
    prices = daily_prices()
    prices["price_kind"] = "legacy_unknown"
    assert backtest.build_forward_returns(signal_rows(), prices)["fwd_1w"].isna().all()


@pytest.mark.parametrize("version", [None, "legacy", "stale"])
def test_stale_or_unversioned_signals_cannot_be_promoted(version):
    signals = signal_rows(60)
    signals["evaluation_version"] = version
    returns = backtest.build_forward_returns(signals, daily_prices())
    assert returns["return_status"].eq("stale_or_unversioned_signal").all()
    assert returns["fwd_1w"].isna().all()
    thresholds = backtest.assign_expanding_thresholds(returns, "z_score_52w")
    assert thresholds["threshold_status"].eq("ineligible").all()
    assert thresholds["threshold_history_n"].eq(0).all()


def test_weekly_price_series_cannot_be_mistaken_for_daily_sessions():
    prices = daily_prices().iloc[1::5].copy()
    result = backtest.build_forward_returns(signal_rows(), prices).iloc[0]
    assert result["fwd_1w_status"] == "price_gap"
    assert pd.isna(result["fwd_1w"])


def test_nonpositive_price_path_is_not_percentage_pnl():
    prices = daily_prices()
    prices.loc[3, "close_price"] = -1
    result = backtest.build_forward_returns(signal_rows(), prices).iloc[0]
    assert result["fwd_1w_status"] == "nonpositive_or_missing_price"
    assert pd.isna(result["fwd_1w"])
    prices.loc[1, "close_price"] = 0
    result = backtest.build_forward_returns(signal_rows(), prices).iloc[0]
    assert result["return_status"] == "nonpositive_or_missing_entry"


def test_future_values_cannot_change_historical_thresholds():
    signals = signal_rows(70)
    earlier = backtest.assign_expanding_thresholds(signals.iloc[:60], "z_score_52w")
    signals.loc[60:, "z_score_52w"] = -1_000_000
    expanded = backtest.assign_expanding_thresholds(signals, "z_score_52w")
    pd.testing.assert_frame_equal(
        earlier[["top_threshold", "bottom_threshold", "tail"]],
        expanded.iloc[:60][["top_threshold", "bottom_threshold", "tail"]],
    )
    assert expanded.iloc[50]["top_threshold"] == pytest.approx(pd.Series(range(50)).quantile(.9))
    assert expanded.iloc[50]["threshold_history_n"] == 50


def test_same_publication_batch_is_not_its_own_training_history():
    signals = signal_rows(55)
    signals.loc[50:54, "release_at"] = signals.iloc[50]["release_at"]
    result = backtest.assign_expanding_thresholds(signals, "z_score_52w")
    assert result.iloc[50:]["threshold_history_n"].eq(50).all()
    assert result.iloc[50:]["top_threshold"].nunique() == 1


def test_unknown_past_signals_do_not_train_thresholds():
    signals = signal_rows(60)
    signals.loc[:20, "release_quality"] = "unknown"
    result = backtest.assign_expanding_thresholds(signals, "z_score_52w")
    assert result.iloc[-1]["threshold_status"] == "warmup"
    assert result.iloc[-1]["threshold_history_n"] == 38


def test_summary_uses_baseline_and_does_not_claim_sharpe_or_accuracy():
    signals = signal_rows(75)
    for horizon in backtest.HORIZONS:
        signals[horizon] = np.linspace(-.02, .02, len(signals))
    results = backtest.backtest_signal(signals, "z_score_52w", "GOLD")
    assert len(results) == 3
    result = results[0]
    assert "hit_rate" not in result and "sharpe" not in result
    assert result["positive_return_rate"] == result["baseline_positive_rate"]
    assert result["avg_return"] == result["baseline_avg_return"]
    assert result["evaluation_version"] == "release_aware_v1"


def test_constant_thresholds_cannot_place_every_row_in_both_tails():
    signals = signal_rows(60)
    signals["z_score_52w"] = 0
    result = backtest.assign_expanding_thresholds(signals, "z_score_52w")
    assert result["tail"].eq("none").all()
    assert result.iloc[-1]["threshold_status"] == "nonseparating_thresholds"


def test_empty_or_insufficient_run_preserves_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(backtest.db, "write_frame", lambda *args, **kwargs: pytest.fail("unexpected write"))
    monkeypatch.setattr(backtest, "load_signals_with_prices", lambda: pd.DataFrame())
    assert backtest.run_backtest(tmp_path / "events.csv").empty
    frame = backtest.build_forward_returns(signal_rows(), daily_prices())
    monkeypatch.setattr(backtest, "load_signals_with_prices", lambda: frame)
    assert backtest.run_backtest(tmp_path / "events.csv").empty
    audit = pd.read_csv(tmp_path / "events.csv")
    assert "entry_date" in audit and "top_threshold" in audit
    assert len(audit) == 1


def test_database_pipeline_persists_auditable_results_and_rollback(monkeypatch, tmp_path):
    from src import db, signals as signal_engine

    monkeypatch.setenv("COT_DB_PATH", str(tmp_path / "pipeline.duckdb"))
    db.init_schema()
    observations = signal_rows(100)
    raw = observations[["report_date", "market", "release_at", "release_quality"]].copy()
    raw["noncomm_long"] = np.arange(len(raw)) + 100
    raw["noncomm_short"] = 50
    raw["comm_long"] = 50
    raw["comm_short"] = np.arange(len(raw)) + 100
    raw["open_interest"] = 1000
    db.write_frame("cot_legacy", raw)
    computed = signal_engine.compute_signals()
    assert len(computed) == 100 and computed["analysis_eligible"].all()
    dates = pd.bdate_range(raw["report_date"].min(), raw["report_date"].max() + pd.Timedelta(days=40))
    prices = pd.DataFrame({"price_date": dates, "market": "GOLD", "close_price": 100 + np.arange(len(dates)),
                           "price_kind": "daily_close_proxy", "source": "test"})
    db.write_frame("futures_prices", prices)
    results = backtest.run_backtest(tmp_path / "events.csv")
    assert not results.empty
    with db.get_conn() as connection:
        saved = connection.execute("SELECT * FROM backtest_results").fetchdf()
    assert saved["hit_rate"].isna().all() and saved["sharpe"].isna().all()
    assert saved["evaluation_version"].eq("release_aware_v1").all()
    # A failed replacement must roll back its preceding DELETE.
    invalid = computed.copy()
    invalid["cot_index_52w"] = "not-a-number"
    with pytest.raises(Exception):
        db.write_frame("signals", invalid, mode="replace")
    with db.get_conn() as connection:
        assert connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 100
    # Refreshing source data preserves old derived records, but invalidates them.
    raw["noncomm_long"] += 1
    db.write_frame("cot_legacy", raw)
    with db.get_conn() as connection:
        assert connection.execute("SELECT COUNT(*) FROM signals WHERE evaluation_version = 'stale'").fetchone()[0] == 100
        assert connection.execute("SELECT COUNT(*) FROM signals WHERE analysis_eligible").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM backtest_results WHERE evaluation_version = 'stale'").fetchone()[0] == len(saved)
    # Running the evaluator without rebuilding features must not re-promote them.
    assert backtest.run_backtest(tmp_path / "stale_events.csv").empty
    with db.get_conn() as connection:
        assert connection.execute("SELECT COUNT(*) FROM backtest_results WHERE evaluation_version = 'release_aware_v1'").fetchone()[0] == 0
