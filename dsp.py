from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from scipy import signal


LEVEL_TABLE = np.array([-3.0, -1.0, 1.0, 3.0], dtype=np.float64)


def repack_bytes_to_dibits(payload: bytes) -> np.ndarray:
    raw = np.frombuffer(payload, dtype=np.uint8)
    bits = np.unpackbits(raw, bitorder="big")
    bit_pairs = bits.reshape(-1, 2)
    dibits = (bit_pairs[:, 0] << 1) | bit_pairs[:, 1]
    return dibits.astype(np.uint8)


def dibits_to_bytes(dibits: np.ndarray) -> bytes:
    dibits = np.asarray(dibits, dtype=np.uint8).reshape(-1)
    bits = np.empty(dibits.size * 2, dtype=np.uint8)
    bits[0::2] = (dibits >> 1) & 1
    bits[1::2] = dibits & 1
    usable = (bits.size // 8) * 8
    packed = np.packbits(bits[:usable], bitorder="big")
    return packed.tobytes()


def map_dibits_to_levels(dibits: np.ndarray) -> np.ndarray:
    dibits = np.asarray(dibits, dtype=np.uint8)
    return LEVEL_TABLE[dibits]


def decide_4level_symbols(samples: np.ndarray) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float64)
    # bins -> 0..3, mapping to [-3, -1, 1, 3] symbol indices.
    return np.digitize(samples, bins=np.array([-2.0, 0.0, 2.0], dtype=np.float64)).astype(
        np.uint8
    )


def normalize_to_4level(samples: np.ndarray) -> Tuple[np.ndarray, float, float]:
    samples = np.asarray(samples, dtype=np.float64)
    center = float(np.median(samples))
    p10, p90 = np.percentile(samples, [10, 90])
    scale = float((p90 - p10) / 6.0)
    if scale < 1e-9:
        scale = 1.0
    normalized = (samples - center) / scale
    return normalized, center, scale


def kmeans_1d(samples: np.ndarray, k: int = 4, max_iter: int = 25) -> Tuple[np.ndarray, np.ndarray]:
    x = np.asarray(samples, dtype=np.float64).reshape(-1)
    if x.size < k:
        raise ValueError("not enough samples for k-means")

    quantiles = np.linspace(0.0, 1.0, k)
    centers = np.quantile(x, quantiles)

    for _ in range(max_iter):
        dist = np.abs(x[:, None] - centers[None, :])
        labels = np.argmin(dist, axis=1)

        new_centers = centers.copy()
        for i in range(k):
            members = x[labels == i]
            if members.size > 0:
                new_centers[i] = np.mean(members)
        if np.allclose(new_centers, centers, rtol=1e-5, atol=1e-7):
            centers = new_centers
            break
        centers = new_centers

    order = np.argsort(centers)
    centers_sorted = centers[order]
    remap = np.empty(k, dtype=np.int32)
    remap[order] = np.arange(k)
    labels_sorted = remap[labels]
    return centers_sorted, labels_sorted.astype(np.uint8)


def adaptive_4level_decision(samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float, float]:
    x = np.asarray(samples, dtype=np.float64).reshape(-1)
    centers, labels = kmeans_1d(x, k=4, max_iter=30)
    scale = float((centers[-1] - centers[0]) / 6.0)
    if scale < 1e-9:
        scale = 1.0
    center = float(np.mean(centers))
    norm = (x - center) / scale
    return labels.astype(np.uint8), centers, center, scale


def root_raised_cosine_taps(sps: int, alpha: float, span_symbols: int) -> np.ndarray:
    if sps <= 0:
        raise ValueError("sps must be positive")
    if span_symbols <= 0:
        raise ValueError("span_symbols must be positive")
    if not (0.0 <= alpha <= 1.0):
        raise ValueError("alpha must be in [0, 1]")

    n = span_symbols * sps
    t = np.arange(-n / 2, n / 2 + 1, dtype=np.float64) / sps
    taps = np.zeros_like(t)

    for i, ti in enumerate(t):
        if np.isclose(ti, 0.0):
            taps[i] = 1.0 + alpha * (4.0 / np.pi - 1.0)
            continue

        if alpha > 0 and np.isclose(abs(ti), 1.0 / (4.0 * alpha), atol=1e-12):
            taps[i] = (alpha / np.sqrt(2.0)) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * alpha))
                + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * alpha))
            )
            continue

        numerator = np.sin(np.pi * ti * (1.0 - alpha)) + 4.0 * alpha * ti * np.cos(
            np.pi * ti * (1.0 + alpha)
        )
        denominator = np.pi * ti * (1.0 - (4.0 * alpha * ti) ** 2)
        taps[i] = numerator / denominator

    taps = taps / np.sqrt(np.sum(taps * taps))
    return taps


def lowpass_taps(sample_rate: float, cutoff_hz: float, num_taps: int) -> np.ndarray:
    num_taps = int(num_taps)
    if num_taps % 2 == 0:
        num_taps += 1
    return signal.firwin(num_taps, cutoff=cutoff_hz, window="hamming", fs=sample_rate)


def upsample_and_rrc(symbols: np.ndarray, sps: int, taps: np.ndarray) -> np.ndarray:
    return signal.upfirdn(taps, np.asarray(symbols, dtype=np.float64), up=sps)


def apply_fir(samples: np.ndarray, taps: np.ndarray) -> np.ndarray:
    return signal.lfilter(taps, [1.0], samples)


def fm_modulate(inst_freq_hz: np.ndarray, sample_rate: float) -> np.ndarray:
    inst_freq_hz = np.asarray(inst_freq_hz, dtype=np.float64)
    phase = np.cumsum(2.0 * np.pi * inst_freq_hz / sample_rate, dtype=np.float64)
    return np.exp(1j * phase).astype(np.complex64)


def quadrature_demod(iq: np.ndarray, sample_rate: float) -> np.ndarray:
    iq = np.asarray(iq, dtype=np.complex64).reshape(-1)
    if iq.size == 0:
        return np.zeros(0, dtype=np.float64)
    if iq.size == 1:
        return np.zeros(1, dtype=np.float64)

    dphi = np.angle(iq[1:] * np.conj(iq[:-1]))
    hz = dphi * (sample_rate / (2.0 * np.pi))
    out = np.empty(iq.size, dtype=np.float64)
    out[0] = hz[0]
    out[1:] = hz
    return out


def freq_shift(iq: np.ndarray, shift_hz: float, sample_rate: float) -> np.ndarray:
    iq = np.asarray(iq, dtype=np.complex64).reshape(-1)
    n = np.arange(iq.size, dtype=np.float64)
    rot = np.exp(1j * 2.0 * np.pi * shift_hz * n / sample_rate)
    return (iq * rot).astype(np.complex64)


def add_awgn(iq: np.ndarray, noise_std: float, rng: np.random.Generator) -> np.ndarray:
    iq = np.asarray(iq, dtype=np.complex64)
    n_i = rng.normal(loc=0.0, scale=noise_std, size=iq.size)
    n_q = rng.normal(loc=0.0, scale=noise_std, size=iq.size)
    noise = (n_i + 1j * n_q).astype(np.complex64) / np.sqrt(2.0)
    return iq + noise


def brute_force_symbol_offset(samples: np.ndarray, sps: int) -> Tuple[int, Dict[int, float]]:
    samples = np.asarray(samples, dtype=np.float64).reshape(-1)
    if sps <= 0:
        raise ValueError("sps must be positive")

    scores: Dict[int, float] = {}
    for offset in range(sps):
        cand = samples[offset::sps]
        if cand.size < 64:
            scores[offset] = float("inf")
            continue

        trim = min(24, cand.size // 10)
        if trim > 0:
            cand = cand[trim:-trim] if cand.size > 2 * trim else cand

        dibits = decide_4level_symbols(cand)
        decided_levels = LEVEL_TABLE[dibits]
        mse = float(np.mean((cand - decided_levels) ** 2))
        variance_penalty = 1.0 / (float(np.var(cand)) + 1e-9)

        counts = np.bincount(dibits, minlength=4).astype(np.float64)
        balance_penalty = float(np.std(counts) / (np.mean(counts) + 1e-12))
        scores[offset] = mse + 0.03 * balance_penalty + 0.02 * variance_penalty

    best_offset = min(scores, key=scores.get)
    return best_offset, scores


def align_dibits(
    tx_dibits: np.ndarray, rx_dibits: np.ndarray, max_lag: int = 200
) -> Dict[str, object]:
    tx = np.asarray(tx_dibits, dtype=np.uint8).reshape(-1)
    rx = np.asarray(rx_dibits, dtype=np.uint8).reshape(-1)

    best = {
        "lag": 0,
        "symbol_match_rate": 0.0,
        "tx_aligned": np.array([], dtype=np.uint8),
        "rx_aligned": np.array([], dtype=np.uint8),
    }

    for lag in range(-max_lag, max_lag + 1):
        tx_start = max(0, -lag)
        rx_start = max(0, lag)
        n = min(tx.size - tx_start, rx.size - rx_start)
        if n <= 0:
            continue

        tx_view = tx[tx_start : tx_start + n]
        rx_view = rx[rx_start : rx_start + n]

        if tx_view.size < 32:
            continue

        match = float(np.mean(tx_view == rx_view))
        if match > best["symbol_match_rate"]:
            best = {
                "lag": lag,
                "symbol_match_rate": match,
                "tx_aligned": tx_view.copy(),
                "rx_aligned": rx_view.copy(),
            }

    return best


def dibit_ber(tx_dibits: np.ndarray, rx_dibits: np.ndarray) -> float:
    tx = np.asarray(tx_dibits, dtype=np.uint8).reshape(-1)
    rx = np.asarray(rx_dibits, dtype=np.uint8).reshape(-1)
    n = min(tx.size, rx.size)
    if n == 0:
        return 1.0
    diff = np.bitwise_xor(tx[:n], rx[:n])
    # XOR value -> bit errors in 2-bit symbol.
    err_lut = np.array([0, 1, 1, 2], dtype=np.int32)
    bit_errors = int(np.sum(err_lut[diff]))
    return bit_errors / float(2 * n)


def power_spectrum_db(samples: np.ndarray, sample_rate: float) -> Tuple[np.ndarray, np.ndarray]:
    x = np.asarray(samples)
    if x.size == 0:
        return np.array([]), np.array([])
    nfft = 1 << int(np.ceil(np.log2(max(256, x.size))))
    spec = np.fft.fftshift(np.fft.fft(x, n=nfft))
    power = 20.0 * np.log10(np.maximum(np.abs(spec), 1e-12))
    freqs = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / sample_rate))
    return freqs, power
