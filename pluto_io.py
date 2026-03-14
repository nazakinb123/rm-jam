from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import numpy as np


def _bootstrap_libiio_windows() -> None:
    if os.name != "nt":
        return

    base = Path(__file__).resolve().parent / "third_party" / "libiio"
    candidates = [
        base / "Windows-VS-2022-x64",
        base / "Windows-VS-2019-x64",
        base / "Windows-MinGW-W64",
    ]

    for folder in candidates:
        dll = folder / "libiio.dll"
        if not dll.exists():
            continue
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(folder))
        os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
        return


_bootstrap_libiio_windows()

try:
    import adi
except Exception:  # pragma: no cover - optional dependency
    adi = None


class PlutoError(RuntimeError):
    pass


def scan_pluto_uris() -> list[str]:
    _ensure_adi()
    import iio

    ctxs = iio.scan_contexts()
    uris = sorted(ctxs.keys())
    return uris


def _pick_uri(uri: str) -> str:
    if uri and uri.lower() != "auto":
        return uri
    uris = scan_pluto_uris()
    if not uris:
        raise PlutoError("No Pluto context found. Check USB/network connection.")
    return uris[0]


def _ensure_adi() -> None:
    if adi is None:
        raise PlutoError("pyadi-iio is not installed. Install with: pip install pyadi-iio")


def create_pluto(uri: str = "auto"):
    _ensure_adi()
    try_uri = _pick_uri(uri)
    return adi.Pluto(uri=try_uri)


def transmit_cyclic(
    iq: np.ndarray,
    sample_rate: float,
    tx_lo_hz: float,
    uri: str = "auto",
    tx_gain_db: float = -30.0,
    duration_s: Optional[float] = None,
) -> None:
    sdr = create_pluto(uri=uri)
    sdr.sample_rate = int(sample_rate)
    sdr.tx_lo = int(tx_lo_hz)
    sdr.tx_rf_bandwidth = int(sample_rate)
    sdr.tx_hardwaregain_chan0 = float(tx_gain_db)
    sdr.tx_cyclic_buffer = True

    sdr.tx(np.asarray(iq, dtype=np.complex64))

    if duration_s is not None and duration_s > 0:
        time.sleep(duration_s)
        sdr.tx_destroy_buffer()


def capture_rx(
    num_samples: int,
    sample_rate: float,
    rx_lo_hz: float,
    uri: str = "auto",
    gain_mode: str = "slow_attack",
    manual_gain_db: float = 40.0,
) -> np.ndarray:
    sdr = create_pluto(uri=uri)
    sdr.sample_rate = int(sample_rate)
    sdr.rx_lo = int(rx_lo_hz)
    sdr.rx_rf_bandwidth = int(sample_rate)
    sdr.gain_control_mode_chan0 = gain_mode
    if gain_mode == "manual":
        sdr.rx_hardwaregain_chan0 = float(manual_gain_db)
    sdr.rx_buffer_size = int(num_samples)

    raw = sdr.rx()
    if isinstance(raw, list):
        raw = raw[0]
    return np.asarray(raw, dtype=np.complex64).reshape(-1)


def txrx_loopback_capture(
    iq: np.ndarray,
    num_samples: int,
    sample_rate: float,
    tx_lo_hz: float,
    rx_lo_hz: float,
    uri: str = "auto",
    tx_gain_db: float = -30.0,
    gain_mode: str = "slow_attack",
    manual_gain_db: float = 40.0,
    settle_s: float = 0.25,
    loopback_mode: int = 0,
) -> np.ndarray:
    sdr = create_pluto(uri=uri)
    sdr.sample_rate = int(sample_rate)
    sdr.tx_lo = int(tx_lo_hz)
    sdr.rx_lo = int(rx_lo_hz)
    sdr.tx_rf_bandwidth = int(sample_rate)
    sdr.rx_rf_bandwidth = int(sample_rate)
    sdr.tx_hardwaregain_chan0 = float(tx_gain_db)
    sdr.gain_control_mode_chan0 = gain_mode
    if gain_mode == "manual":
        sdr.rx_hardwaregain_chan0 = float(manual_gain_db)
    if hasattr(sdr, "loopback"):
        sdr.loopback = int(loopback_mode)
    sdr.tx_cyclic_buffer = True
    sdr.rx_buffer_size = int(num_samples)

    sdr.tx(np.asarray(iq, dtype=np.complex64))
    time.sleep(max(settle_s, 0.05))
    raw = sdr.rx()
    if isinstance(raw, list):
        raw = raw[0]
    if hasattr(sdr, "loopback"):
        sdr.loopback = 0
    sdr.tx_destroy_buffer()
    return np.asarray(raw, dtype=np.complex64).reshape(-1)
