from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np

import dsp


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def plot_time(
    samples: np.ndarray,
    sample_rate: float,
    path: Path,
    title: str,
    max_samples: int = 2000,
) -> None:
    x = np.asarray(samples).reshape(-1)[:max_samples]
    t = np.arange(x.size, dtype=np.float64) / sample_rate

    fig, ax = plt.subplots(figsize=(10, 4))
    if np.iscomplexobj(x):
        ax.plot(t * 1e3, x.real, lw=0.8, label="I")
        ax.plot(t * 1e3, x.imag, lw=0.8, label="Q", alpha=0.8)
        ax.legend(loc="upper right")
    else:
        ax.plot(t * 1e3, x, lw=0.8)

    ax.set_title(title)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Amplitude")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_spectrum(samples: np.ndarray, sample_rate: float, path: Path, title: str) -> None:
    freqs, power_db = dsp.power_spectrum_db(samples, sample_rate=sample_rate)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(freqs / 1e3, power_db, lw=0.8)
    ax.set_title(title)
    ax.set_xlabel("Frequency (kHz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_histogram(
    samples: np.ndarray,
    path: Path,
    title: str,
    bins: int = 100,
    value_range: tuple = (-4, 4),
) -> None:
    x = np.asarray(samples).reshape(-1)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(x, bins=bins, range=value_range, alpha=0.85)
    ax.set_title(title)
    ax.set_xlabel("Value")
    ax.set_ylabel("Count")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def save_stage_plots(
    stages: Dict[str, np.ndarray],
    sample_rate: float,
    out_dir: Path,
    max_samples: int,
    sps: int = 4,
) -> None:
    ensure_dir(out_dir)

    if "x0_raw" in stages:
        plot_time(stages["x0_raw"], sample_rate, out_dir / "x0_raw_time.png", "x0_raw (RX input)", max_samples)
        plot_spectrum(stages["x0_raw"], sample_rate, out_dir / "x0_raw_spectrum.png", "x0_raw Spectrum")
    if "x1_rot" in stages:
        plot_time(stages["x1_rot"], sample_rate, out_dir / "x1_rot_time.png", "x1_rot (Frequency shifted)", max_samples)
        plot_spectrum(stages["x1_rot"], sample_rate, out_dir / "x1_rot_spectrum.png", "x1_rot Spectrum")
    if "x2_lpf" in stages:
        plot_time(stages["x2_lpf"], sample_rate, out_dir / "x2_lpf_time.png", "x2_lpf (After LPF)", max_samples)
        plot_spectrum(stages["x2_lpf"], sample_rate, out_dir / "x2_lpf_spectrum.png", "x2_lpf Spectrum")
    if "x3_qd" in stages:
        plot_time(stages["x3_qd"], sample_rate, out_dir / "x3_qd_time.png", "x3_qd (Quadrature Demod)", max_samples)
    if "x4_norm" in stages:
        plot_time(stages["x4_norm"], sample_rate, out_dir / "x4_norm_time.png", "x4_norm (Normalized)", max_samples)
    if "x5_rrc" in stages:
        plot_time(stages["x5_rrc"], sample_rate, out_dir / "x5_rrc_time.png", "x5_rrc (RX RRC)", max_samples)
    if "x6_downsample" in stages:
        plot_time(
            stages["x6_downsample"],
            sample_rate / float(max(sps, 1)),
            out_dir / "x6_downsample_time.png",
            "x6_downsample (Symbol-rate)",
            max_samples,
        )
        plot_histogram(
            stages["x6_downsample"],
            out_dir / "x6_downsample_hist.png",
            "x6_downsample Histogram",
            bins=100,
            value_range=(-4, 4),
        )
    if "x6_norm" in stages:
        plot_histogram(
            stages["x6_norm"],
            out_dir / "x6_norm_hist.png",
            "x6_norm Histogram",
            bins=100,
            value_range=(-4.5, 4.5),
        )
