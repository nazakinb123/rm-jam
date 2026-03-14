from __future__ import annotations

from typing import Dict

import numpy as np

import dsp
from config import J1Config, build_tx_bytes


def generate_j1_tx(cfg: J1Config) -> Dict[str, np.ndarray]:
    tx_bytes = build_tx_bytes(cfg)
    tx_dibits = dsp.repack_bytes_to_dibits(tx_bytes)
    tx_symbols = dsp.map_dibits_to_levels(tx_dibits)

    rrc_taps = dsp.root_raised_cosine_taps(
        sps=cfg.sps, alpha=cfg.rrc_alpha, span_symbols=cfg.rrc_span_symbols
    )
    x_tx_rrc = dsp.upsample_and_rrc(tx_symbols, sps=cfg.sps, taps=rrc_taps)
    x_tx_fdev = x_tx_rrc * cfg.j1_freq_dev_hz
    x_tx_fm = dsp.fm_modulate(x_tx_fdev, sample_rate=cfg.sample_rate)
    x_tx_iq = dsp.freq_shift(x_tx_fm, shift_hz=cfg.j1_shift_hz, sample_rate=cfg.sample_rate)

    return {
        "tx_bytes": np.frombuffer(tx_bytes, dtype=np.uint8),
        "tx_dibits": tx_dibits,
        "tx_symbols": tx_symbols,
        "rrc_taps": rrc_taps,
        "x_tx_rrc": x_tx_rrc,
        "x_tx_fdev": x_tx_fdev,
        "x_tx_fm": x_tx_fm,
        "x_tx_iq": x_tx_iq,
    }
