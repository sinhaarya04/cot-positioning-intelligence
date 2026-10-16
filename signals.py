"""Compatibility entry point; the single implementation lives in src.signals."""

from src.signals import (
    build_signals,
    compute_acceleration,
    compute_comm_spec_divergence,
    compute_cot_index,
    compute_momentum,
    compute_signals,
    compute_z_score,
    load_disagg_positions,
    load_eia_inventory,
    load_legacy_net_positions,
)

__all__ = [
    "build_signals", "compute_acceleration", "compute_comm_spec_divergence",
    "compute_cot_index", "compute_momentum", "compute_signals", "compute_z_score",
    "load_disagg_positions", "load_eia_inventory", "load_legacy_net_positions",
]

if __name__ == "__main__":
    from src.db import init_schema

    init_schema()
    compute_signals()
