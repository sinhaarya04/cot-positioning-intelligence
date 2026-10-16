import numpy as np
import pandas as pd
import pytest

from src import signals


def legacy_rows(n=35):
    dates = pd.date_range("2021-01-05", periods=n, freq="7D")
    return pd.DataFrame({
        "market": "CRUDE_OIL", "report_date": dates,
        "release_at": (dates + pd.Timedelta(days=3, hours=20, minutes=30)).tz_localize("UTC"),
        "release_quality": "verified", "net_spec": np.arange(n, dtype=float),
        "net_comm": -np.arange(n, dtype=float), "open_interest": 1000,
    })


def test_minmax_is_not_percentile_and_preserves_index():
    values = pd.Series([0, 1, 2, 100, 3], index=[8, 10, 12, 14, 16])
    result = signals.compute_cot_index(values, 5)
    assert result.index.equals(values.index)
    assert result.iloc[-1] == 3
    assert signals.compute_z_score(values, 5).index.equals(values.index)


def test_missing_values_are_not_neutral_positions():
    values = pd.Series([1.0, 1.0, np.nan])
    assert signals.compute_cot_index(values, 2).iloc[1] == 50
    assert signals.compute_z_score(values, 2).iloc[1] == 0
    assert pd.isna(signals.compute_cot_index(values, 2).iloc[-1])
    assert pd.isna(signals.compute_z_score(values, 2).iloc[-1])


def test_delayed_historical_report_cannot_change_earlier_known_feature():
    legacy = legacy_rows()
    legacy.loc[5, "release_at"] = legacy.iloc[-1]["release_at"] + pd.Timedelta(days=10)
    original = signals.build_signals(legacy, pd.DataFrame(), pd.DataFrame())
    changed = legacy.copy()
    changed.loc[5, "net_spec"] = 10_000_000
    updated = signals.build_signals(changed, pd.DataFrame(), pd.DataFrame())
    assert original.iloc[-1]["z_score_52w"] == updated.iloc[-1]["z_score_52w"]
    assert original.iloc[-1]["cot_index_52w"] == updated.iloc[-1]["cot_index_52w"]
    # The delayed observation itself is evaluated at its own later release.
    assert original.iloc[5]["release_at"] > original.iloc[-1]["release_at"]


def test_unknown_or_naive_release_is_descriptive_only():
    legacy = legacy_rows()
    legacy["release_at"] = legacy["release_at"].dt.tz_localize(None)
    result = signals.build_signals(legacy, pd.DataFrame(), pd.DataFrame())
    assert not result["analysis_eligible"].any()
    assert result["release_at"].isna().all()
    assert result.iloc[-1]["cot_index_52w"] == 100


def test_disaggregated_join_never_uses_later_release():
    legacy = legacy_rows()
    disagg = legacy[["market", "report_date", "release_at", "release_quality"]].copy()
    disagg["mgd_money_net"] = 500
    disagg.loc[len(disagg) - 1, "release_at"] += pd.Timedelta(minutes=1)
    result = signals.build_signals(legacy, disagg, pd.DataFrame())
    assert result.iloc[-2]["mgd_money_net"] == 500
    assert pd.isna(result.iloc[-1]["mgd_money_net"])
    assert pd.isna(result.iloc[-1]["disagg_release_at"])


def test_inventory_join_uses_publication_not_nearest_period():
    legacy = legacy_rows()
    eia = legacy[["market", "report_date", "release_at", "release_quality"]].copy()
    eia["release_at"] -= pd.Timedelta(days=1)
    eia["inventory_level"] = np.arange(len(eia), dtype=float) + 100
    # Same-period inventory is unavailable until after the final COT event.
    eia.loc[len(eia) - 1, "release_at"] = legacy.iloc[-1]["release_at"] + pd.Timedelta(days=1)
    eia.loc[len(eia) - 1, "inventory_level"] = 999999
    result = signals.build_signals(legacy, pd.DataFrame(), eia)
    assert result.iloc[-1]["inventory_report_date"] == eia.iloc[-2]["report_date"]
    assert result.iloc[-1]["inventory_release_at"] == eia.iloc[-2]["release_at"]
    assert result.iloc[-1]["inventory_mismatch"] > 0
    assert result.iloc[-1]["data_vintage"] == "latest"


def test_unverified_inventory_is_not_used_even_when_timestamp_present():
    legacy = legacy_rows()
    eia = legacy[["market", "report_date", "release_at", "release_quality"]].copy()
    eia["inventory_level"] = 10
    eia["release_quality"] = "unknown"
    result = signals.build_signals(legacy, pd.DataFrame(), eia)
    assert result["inventory_mismatch"].isna().all()


def test_momentum_requires_exact_calendar_week_and_positive_oi():
    legacy = legacy_rows(10).drop(index=5).reset_index(drop=True)
    legacy.loc[len(legacy) - 1, "open_interest"] = 0
    result = signals.build_signals(legacy, pd.DataFrame(), pd.DataFrame())
    assert pd.isna(result.iloc[-1]["momentum_4w"])
    assert pd.isna(result.iloc[-1]["comm_spec_divergence"])


def test_duplicate_reports_are_rejected():
    legacy = legacy_rows(1)
    with pytest.raises(ValueError, match="Duplicate"):
        signals.build_signals(pd.concat([legacy, legacy]), pd.DataFrame(), pd.DataFrame())


def test_empty_signal_run_does_not_write(monkeypatch):
    for name in ("load_legacy_net_positions", "load_disagg_positions", "load_eia_inventory"):
        monkeypatch.setattr(signals, name, lambda: pd.DataFrame())
    monkeypatch.setattr(signals.db, "write_frame", lambda *args, **kwargs: pytest.fail("unexpected write"))
    assert signals.compute_signals().empty
