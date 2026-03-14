from __future__ import annotations

from typing import Dict

import numpy as np

import dsp
import plots
import rx_j1
import tx_j1
from config import J1Config


def run_simulation(cfg: J1Config) -> Dict[str, object]:
    tx = tx_j1.generate_j1_tx(cfg)
    tx_iq = tx["x_tx_iq"]

    rng = np.random.default_rng(cfg.random_seed)
    if cfg.add_awgn and cfg.awgn_std > 0.0:
        ch_iq = dsp.add_awgn(tx_iq, noise_std=cfg.awgn_std, rng=rng)
    else:
        ch_iq = tx_iq

    rx = rx_j1.receive_j1(ch_iq, cfg, expected_dibits=tx["tx_dibits"])

    stage_data = {
        "x0_raw": rx["x0_raw"],
        "x1_rot": rx["x1_rot"],
        "x2_lpf": rx["x2_lpf"],
        "x3_qd": rx["x3_qd"],
        "x4_norm": rx["x4_norm"],
        "x5_rrc": rx["x5_rrc"],
        "x6_downsample": rx["x6_downsample"],
        "x6_norm": rx["x6_norm"],
    }
    plots.save_stage_plots(
        stages=stage_data,
        sample_rate=cfg.sample_rate,
        out_dir=cfg.output_dir,
        max_samples=cfg.time_plot_samples,
        sps=cfg.sps,
    )

    tx_head = np.asarray(rx.get("tx_bytes_aligned", tx["tx_bytes"]), dtype=np.uint8)
    rx_head = np.asarray(rx.get("rx_bytes_aligned", rx["rx_bytes"]), dtype=np.uint8)

    summary: Dict[str, object] = {
        "tx_bytes_head": bytes(tx_head[:32]),
        "rx_bytes_head": bytes(rx_head[:32]),
        "best_offset": int(rx["best_offset"]),
        "offset_scores": rx["offset_scores"],
        "ber": float(rx.get("ber", 1.0)),
        "symbol_match_rate": float(rx.get("alignment", {}).get("symbol_match_rate", 0.0)),
        "alignment_lag_symbols": int(rx.get("alignment", {}).get("lag", 0)),
        "output_dir": str(cfg.output_dir.resolve()),
    }
    return summary
