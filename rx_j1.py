from __future__ import annotations

from typing import Dict, Optional

import numpy as np

import dsp
from config import J1Config


def receive_j1(
    rx_iq: np.ndarray, cfg: J1Config, expected_dibits: Optional[np.ndarray] = None
) -> Dict[str, object]:
    x0_raw = np.asarray(rx_iq, dtype=np.complex64).reshape(-1)
    if x0_raw.size > 0:
        # Hardware capture often has strong DC offset / gain mismatch. Normalize early.
        x0_raw = x0_raw - np.mean(x0_raw)
        rms = float(np.sqrt(np.mean(np.abs(x0_raw) ** 2)))
        if rms > 1e-9:
            x0_raw = x0_raw / rms

    x1_rot = dsp.freq_shift(x0_raw, shift_hz=-cfg.j1_shift_hz, sample_rate=cfg.sample_rate)
    lpf_taps = dsp.lowpass_taps(
        sample_rate=cfg.sample_rate, cutoff_hz=cfg.lpf_cutoff_hz, num_taps=cfg.lpf_taps
    )
    x2_lpf = dsp.apply_fir(x1_rot, lpf_taps)

    x3_qd = dsp.quadrature_demod(x2_lpf, sample_rate=cfg.sample_rate)
    x4_norm = x3_qd / cfg.j1_freq_dev_hz

    rrc_taps = dsp.root_raised_cosine_taps(
        sps=cfg.sps, alpha=cfg.rrc_alpha, span_symbols=cfg.rrc_span_symbols
    )
    x5_rrc = dsp.apply_fir(x4_norm, rrc_taps)

    best_offset, offset_scores = dsp.brute_force_symbol_offset(x5_rrc, sps=cfg.sps)
    guard = cfg.rrc_span_symbols
    offset_byte_streams: Dict[int, bytes] = {}
    offset_dibits_map: Dict[int, np.ndarray] = {}
    offset_dibits_norm_map: Dict[int, np.ndarray] = {}
    for offset in range(cfg.sps):
        cand = x5_rrc[offset:: cfg.sps]
        if cand.size > 2 * guard:
            cand = cand[guard:-guard]
        if cand.size > 0:
            cand_norm, _, _ = dsp.normalize_to_4level(cand)
            cand_dibits_raw = dsp.decide_4level_symbols(cand)
            cand_dibits_norm = dsp.decide_4level_symbols(cand_norm)
            offset_dibits_map[offset] = cand_dibits_raw
            offset_dibits_norm_map[offset] = cand_dibits_norm
            offset_byte_streams[offset] = dsp.dibits_to_bytes(cand_dibits_raw)
        else:
            offset_dibits_map[offset] = np.array([], dtype=np.uint8)
            offset_dibits_norm_map[offset] = np.array([], dtype=np.uint8)
            offset_byte_streams[offset] = b""

    x6_downsample = x5_rrc[best_offset:: cfg.sps]
    if x6_downsample.size > 2 * guard:
        x6_steady = x6_downsample[guard:-guard]
    else:
        x6_steady = x6_downsample

    if x6_steady.size > 0:
        x6_norm, level_center, level_scale = dsp.normalize_to_4level(x6_steady)
    else:
        x6_norm = x6_steady.copy()
        level_center = 0.0
        level_scale = 1.0
    rx_dibits = dsp.decide_4level_symbols(x6_steady)
    level_centers = np.array([-3.0, -1.0, 1.0, 3.0], dtype=np.float64)
    rx_levels = dsp.map_dibits_to_levels(rx_dibits)
    rx_bytes = dsp.dibits_to_bytes(rx_dibits)

    out: Dict[str, object] = {
        "x0_raw": x0_raw,
        "x1_rot": x1_rot,
        "x2_lpf": x2_lpf,
        "x3_qd": x3_qd,
        "x4_norm": x4_norm,
        "x5_rrc": x5_rrc,
        "x6_downsample": x6_downsample,
        "x6_steady": x6_steady,
        "x6_norm": x6_norm,
        "rx_dibits": rx_dibits,
        "rx_levels": rx_levels,
        "rx_bytes": np.frombuffer(rx_bytes, dtype=np.uint8),
        "best_offset": best_offset,
        "offset_scores": offset_scores,
        "offset_dibits_map": offset_dibits_map,
        "offset_dibits_norm_map": offset_dibits_norm_map,
        "offset_byte_streams": offset_byte_streams,
        "level_center": level_center,
        "level_scale": level_scale,
        "level_centers": level_centers,
        "lpf_taps": lpf_taps,
        "rx_rrc_taps": rrc_taps,
    }

    if expected_dibits is not None:
        align = dsp.align_dibits(expected_dibits, rx_dibits, max_lag=6 * cfg.sps * cfg.rrc_span_symbols)
        tx_aligned = align["tx_aligned"]
        rx_aligned = align["rx_aligned"]
        ber = dsp.dibit_ber(tx_aligned, rx_aligned)
        out["alignment"] = align
        out["ber"] = ber
        out["tx_dibits_aligned"] = tx_aligned
        out["rx_dibits_aligned"] = rx_aligned
        out["tx_bytes_aligned"] = np.frombuffer(dsp.dibits_to_bytes(tx_aligned), dtype=np.uint8)
        out["rx_bytes_aligned"] = np.frombuffer(dsp.dibits_to_bytes(rx_aligned), dtype=np.uint8)

    return out
