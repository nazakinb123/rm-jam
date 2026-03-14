from __future__ import annotations

import json
import itertools
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

import dsp
import pluto_io
import protocol_rm
import rx_j1
import tx_j1
from config import J1Config, build_red_jam_config, get_red_jam_level_spec

DEFAULT_REPLAY_IQ_PATH = Path("output") / "replay" / "last_hw_capture.npy"


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def get_default_replay_iq_path() -> Path:
    return DEFAULT_REPLAY_IQ_PATH


def build_sim_protocol_payload(key: str, frame_count: int = 240, seed: int = 7) -> bytes:
    rng = np.random.default_rng(seed)
    key_bytes = key.encode("ascii")
    seq = 0
    out = bytearray()

    for i in range(frame_count):
        if i % 11 == 0:
            noise_len = int(rng.integers(1, 6))
            out.extend(rng.integers(0, 256, size=noise_len, dtype=np.uint8).tobytes())

        if i % 9 == 0:
            payload = rng.integers(0, 256, size=8, dtype=np.uint8).tobytes()
            out.extend(protocol_rm.build_frame(0x0A04, payload, seq=seq))
            seq = (seq + 1) & 0xFF

        if i % 17 == 0:
            bad_crc = bytearray(protocol_rm.build_frame(protocol_rm.CMD_ID_KEY, key_bytes, seq=seq))
            bad_crc[-1] ^= 0x55
            out.extend(bad_crc)
            seq = (seq + 1) & 0xFF

        if i % 23 == 0:
            out.extend(protocol_rm.build_frame(protocol_rm.CMD_ID_KEY, b"A1b$%2", seq=seq))
            seq = (seq + 1) & 0xFF

        out.extend(protocol_rm.build_frame(protocol_rm.CMD_ID_KEY, key_bytes, seq=seq))
        seq = (seq + 1) & 0xFF

    return bytes(out)


def _select_best_parse(candidate_streams: Iterable[bytes]) -> protocol_rm.ParseResult:
    best: Optional[protocol_rm.ParseResult] = None
    for stream in candidate_streams:
        current = protocol_rm.parse_stream(stream)
        if best is None:
            best = current
            continue

        current_score = (
            current.stats.valid_frames,
            current.best_key_count,
            -current.stats.crc_fail_frames,
            -current.stats.ascii_fail_frames,
        )
        best_score = (
            best.stats.valid_frames,
            best.best_key_count,
            -best.stats.crc_fail_frames,
            -best.stats.ascii_fail_frames,
        )
        if current_score > best_score:
            best = current

    if best is None:
        return protocol_rm.ParseResult(
            keys=[],
            key_counts={},
            best_key=None,
            best_key_count=0,
            stats=protocol_rm.ParseStats(),
        )
    return best


def _build_candidate_streams(rx: Dict[str, object]) -> List[bytes]:
    candidates: List[bytes] = []

    def _push(stream: bytes) -> None:
        if not stream:
            return
        if stream in candidates:
            return
        candidates.append(stream)

    def _push_permuted_dibits(dibits: np.ndarray) -> None:
        arr = np.asarray(dibits, dtype=np.uint8).reshape(-1)
        if arr.size == 0:
            return
        for perm in itertools.permutations([0, 1, 2, 3]):
            lut = np.asarray(perm, dtype=np.uint8)
            mapped = lut[arr]
            _push(dsp.dibits_to_bytes(mapped))

    rx_bytes = bytes(np.asarray(rx.get("rx_bytes", np.array([], dtype=np.uint8)), dtype=np.uint8))
    _push(rx_bytes)
    if "rx_bytes_aligned" in rx:
        _push(bytes(np.asarray(rx["rx_bytes_aligned"], dtype=np.uint8)))

    offset_byte_streams = rx.get("offset_byte_streams", {})
    if isinstance(offset_byte_streams, dict):
        for s in offset_byte_streams.values():
            if isinstance(s, (bytes, bytearray)):
                _push(bytes(s))
            else:
                _push(bytes(np.asarray(s, dtype=np.uint8)))

    rx_dibits = np.asarray(rx.get("rx_dibits", np.array([], dtype=np.uint8)), dtype=np.uint8).reshape(-1)
    _push_permuted_dibits(rx_dibits)

    offset_dibits_map = rx.get("offset_dibits_map", {})
    if isinstance(offset_dibits_map, dict):
        for d in offset_dibits_map.values():
            _push_permuted_dibits(np.asarray(d, dtype=np.uint8))

    offset_dibits_norm_map = rx.get("offset_dibits_norm_map", {})
    if isinstance(offset_dibits_norm_map, dict):
        for d in offset_dibits_norm_map.values():
            _push_permuted_dibits(np.asarray(d, dtype=np.uint8))

    # Byte-level hypotheses for bit-order/polarity ambiguities in hardware.
    for s in list(candidates):
        b = np.frombuffer(s, dtype=np.uint8)
        _push((255 - b).tobytes())
        bitrev = np.array([int(f"{x:08b}"[::-1], 2) for x in b], dtype=np.uint8)
        _push(bitrev.tobytes())

    return candidates


def _compute_confidence(rx: Dict[str, object], parsed: protocol_rm.ParseResult) -> Dict[str, float]:
    x6 = np.asarray(rx.get("x6_norm", rx.get("x6_steady", np.array([]))), dtype=np.float64)
    if x6.size == 0:
        wave_mse = 1.0
    else:
        decided = dsp.map_dibits_to_levels(dsp.decide_4level_symbols(x6))
        wave_mse = float(np.mean((x6 - decided) ** 2))

    confidence_wave = _clip01(1.0 - wave_mse / 0.8)

    offset_match_scores = rx.get("offset_match_scores", {})
    if isinstance(offset_match_scores, dict) and offset_match_scores:
        best_match = float(max(offset_match_scores.values()))
        confidence_sync = _clip01(best_match)
    else:
        offset_scores = rx.get("offset_scores", {})
        best_offset = int(rx.get("best_offset", 0))
        if isinstance(offset_scores, dict) and offset_scores:
            best_score = float(offset_scores.get(best_offset, min(offset_scores.values())))
            worst_score = float(max(offset_scores.values()))
            if worst_score <= 1e-12:
                confidence_sync = 1.0
            else:
                confidence_sync = _clip01(1.0 - best_score / worst_score)
        else:
            confidence_sync = 0.0

    total_keys = len(parsed.keys)
    if total_keys <= 0:
        confidence_key = 0.0
    else:
        confidence_key = float(parsed.best_key_count / total_keys)

    confidence = int(round(100.0 * (0.5 * confidence_wave + 0.2 * confidence_sync + 0.3 * confidence_key)))
    return {
        "wave_mse": wave_mse,
        "confidence_wave": confidence_wave,
        "confidence_sync": confidence_sync,
        "confidence_key": confidence_key,
        "confidence": confidence,
    }


def _plot_complex_time(ax, samples: np.ndarray, sample_rate: float, title: str, max_samples: int = 2000) -> None:
    x = np.asarray(samples).reshape(-1)[:max_samples]
    t_ms = np.arange(x.size, dtype=np.float64) * 1000.0 / sample_rate
    if np.iscomplexobj(x):
        ax.plot(t_ms, x.real, lw=0.8, label="I")
        ax.plot(t_ms, x.imag, lw=0.8, label="Q", alpha=0.8)
        ax.legend(loc="upper right")
    else:
        ax.plot(t_ms, x, lw=0.8)
    ax.set_title(title)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Amplitude")
    ax.grid(alpha=0.25)


def _plot_spectrum(ax, samples: np.ndarray, sample_rate: float, title: str) -> None:
    freq_hz, power_db = dsp.power_spectrum_db(samples, sample_rate)
    ax.plot(freq_hz / 1e3, power_db, lw=0.8)
    ax.set_title(title)
    ax.set_xlabel("Frequency (kHz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.grid(alpha=0.25)


def _save_source_waveform(
    source_samples: np.ndarray, sample_rate: float, path: Path, max_samples: int = 2500
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    _plot_complex_time(
        axes[0],
        source_samples,
        sample_rate,
        "Source Waveform (info/interference source)",
        max_samples=max_samples,
    )
    _plot_spectrum(axes[1], source_samples, sample_rate, "Source Spectrum")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_filtered_waveform(
    filtered_samples: np.ndarray,
    post_samples: np.ndarray,
    sample_rate: float,
    path: Path,
    max_samples: int = 2500,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    _plot_complex_time(
        axes[0],
        filtered_samples,
        sample_rate,
        "After Filter Circuit (LPF output)",
        max_samples=max_samples,
    )
    _plot_complex_time(
        axes[1],
        post_samples,
        sample_rate,
        "After Demod + RRC",
        max_samples=max_samples,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_result_panel(summary: Dict[str, object], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.axis("off")
    ax.set_title("Processing Result", fontsize=15, pad=10)

    lines = [
        f"Level: {summary['level']} ({summary['mode']})",
        f"Data Source: {summary.get('data_source')}",
        f"Decoded Key: {summary['decoded_key']}",
        f"Expected Key: {summary['expected_key']}",
        f"Confidence: {summary['confidence']}%",
        f"Valid Frames: {summary['valid_frames']} | CRC Fails: {summary['crc_fail_frames']} | ASCII Fails: {summary['ascii_fail_frames']}",
        f"Best Offset: {summary['best_offset']} | BER: {summary['ber']}",
    ]

    y = 0.88
    for line in lines:
        ax.text(0.03, y, line, fontsize=12, va="top", family="monospace")
        y -= 0.13

    pass_flag = bool(summary["decoded_key"] and summary["decoded_key"] == summary["expected_key"])
    status_text = "PASS" if pass_flag else "CHECK"
    status_color = "#1f8f4e" if pass_flag else "#c27b00"
    ax.text(0.88, 0.15, status_text, fontsize=24, color=status_color, weight="bold", ha="center")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _write_summary_json(summary: Dict[str, object], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump({k: v for k, v in summary.items() if k != "plot_data"}, f, indent=2, ensure_ascii=False)


def _downsample(samples: np.ndarray, max_points: int) -> np.ndarray:
    x = np.asarray(samples).reshape(-1)
    if x.size <= max_points:
        return x
    idx = np.linspace(0, x.size - 1, num=max_points, dtype=np.int64)
    return x[idx]


def _build_plot_data(
    source_samples: np.ndarray,
    rx: Dict[str, object],
    sample_rate: float,
) -> Dict[str, object]:
    source_ds = _downsample(np.asarray(source_samples), max_points=3200)
    x2_ds = _downsample(np.asarray(rx["x2_lpf"]), max_points=3200)
    x5_ds = _downsample(np.asarray(rx["x5_rrc"]), max_points=3200)

    sf, sp = dsp.power_spectrum_db(source_samples, sample_rate)
    sf_ds = _downsample(sf, max_points=4096)
    sp_ds = _downsample(sp, max_points=4096)

    t_source_ms = (np.arange(source_ds.size, dtype=np.float64) / sample_rate) * 1e3
    t_x2_ms = (np.arange(x2_ds.size, dtype=np.float64) / sample_rate) * 1e3
    t_x5_ms = (np.arange(x5_ds.size, dtype=np.float64) / sample_rate) * 1e3

    return {
        "t_source_ms": t_source_ms.tolist(),
        "source_i": source_ds.real.astype(np.float64).tolist(),
        "source_q": source_ds.imag.astype(np.float64).tolist(),
        "spec_freq_khz": (sf_ds / 1e3).astype(np.float64).tolist(),
        "spec_power_db": sp_ds.astype(np.float64).tolist(),
        "t_x2_ms": t_x2_ms.tolist(),
        "x2_i": x2_ds.real.astype(np.float64).tolist(),
        "x2_q": x2_ds.imag.astype(np.float64).tolist(),
        "t_x5_ms": t_x5_ms.tolist(),
        "x5": x5_ds.astype(np.float64).tolist(),
    }


def _normalize_key(key: str) -> str:
    k = key.strip().upper()
    if not protocol_rm.KEY_PATTERN.fullmatch(k):
        raise ValueError("key must match [A-Z0-9]{6}")
    return k


def _run_hw_loopback(
    cfg: J1Config,
    tx_iq: np.ndarray,
    uri: str,
    tx_lo_hz: float,
    rx_lo_hz: float,
    tx_gain_db: float,
    duration_s: float,
    samples: int,
    gain_mode: str,
    manual_gain_db: float,
    pluto_loopback: int,
) -> np.ndarray:
    settle_s = min(max(duration_s * 0.2, 0.2), 0.8)
    rx_iq = pluto_io.txrx_loopback_capture(
        iq=tx_iq,
        num_samples=samples,
        sample_rate=cfg.sample_rate,
        tx_lo_hz=tx_lo_hz,
        rx_lo_hz=rx_lo_hz,
        uri=uri,
        tx_gain_db=tx_gain_db,
        gain_mode=gain_mode,
        manual_gain_db=manual_gain_db,
        settle_s=settle_s,
        loopback_mode=pluto_loopback,
    )
    return rx_iq


def _load_replay_iq(path: Optional[str]) -> Tuple[np.ndarray, Path]:
    replay_path = Path(path).expanduser() if path else get_default_replay_iq_path()
    if not replay_path.exists():
        raise FileNotFoundError(f"Replay IQ file not found: {replay_path}")
    arr = np.load(replay_path, allow_pickle=False)
    return np.asarray(arr, dtype=np.complex64).reshape(-1), replay_path


def _save_replay_iq(rx_iq: np.ndarray, output_dir: Path) -> Tuple[Path, Path]:
    run_path = output_dir / "00_rx_iq.npy"
    np.save(run_path, np.asarray(rx_iq, dtype=np.complex64))
    last_path = get_default_replay_iq_path()
    last_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(last_path, np.asarray(rx_iq, dtype=np.complex64))
    return run_path, last_path


def _build_parser_selftest(expected_key: str) -> protocol_rm.ParseResult:
    payload = expected_key.encode("ascii")
    frame = protocol_rm.build_frame(protocol_rm.CMD_ID_KEY, payload, seq=0)
    noisy_stream = b"\x13\x37" + frame + b"\x00"
    return protocol_rm.parse_stream(noisy_stream)


def run_jam_demo(
    level: int,
    mode: str,
    output_dir: Path,
    key: Optional[str] = None,
    uri: str = "auto",
    tx_lo_hz: float = 432_700_000.0,
    rx_lo_hz: float = 432_700_000.0,
    tx_gain_db: float = -30.0,
    duration_s: float = 2.0,
    samples: int = 262_144,
    gain_mode: str = "slow_attack",
    manual_gain_db: float = 40.0,
    noise_std: float = 0.0,
    pluto_loopback: int = 1,
    replay_iq_path: Optional[str] = None,
    save_rx_iq: bool = False,
    save_artifacts: bool = True,
    include_plot_data: bool = False,
) -> Dict[str, object]:
    spec = get_red_jam_level_spec(level)
    expected_key = _normalize_key(key if key is not None else spec.default_key)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = build_red_jam_config(level=level, tx_lo_hz=tx_lo_hz, rx_lo_hz=rx_lo_hz)
    cfg.output_dir = output_dir
    cfg.add_awgn = noise_std > 0.0
    cfg.awgn_std = float(max(0.0, noise_std))

    tx = None
    expected_dibits = None
    data_source = "unknown"
    replay_path_used: Optional[Path] = None
    rx_iq_saved_path: Optional[Path] = None
    replay_last_saved_path: Optional[Path] = None

    parser_selftest = _build_parser_selftest(expected_key)
    parser_selftest_bytes = len(
        protocol_rm.build_frame(protocol_rm.CMD_ID_KEY, expected_key.encode("ascii"), seq=0)
    )

    if mode == "sim":
        cfg.payload = build_sim_protocol_payload(expected_key, frame_count=240, seed=100 + level)
        cfg.payload_repeats = 1
        tx = tx_j1.generate_j1_tx(cfg)
        tx_iq = tx["x_tx_iq"]

        if cfg.add_awgn and cfg.awgn_std > 0:
            rng = np.random.default_rng(cfg.random_seed)
            rx_iq = dsp.add_awgn(tx_iq, cfg.awgn_std, rng)
        else:
            rx_iq = tx_iq
        expected_dibits = tx["tx_dibits"]
        data_source = "simulation"

    elif mode == "hw-loopback":
        cfg.payload = build_sim_protocol_payload(expected_key, frame_count=260, seed=200 + level)
        cfg.payload_repeats = 1
        if pluto_loopback > 0:
            # In Pluto internal loopback paths, effective center is near baseband.
            cfg.j1_shift_hz = 0.0
        tx = tx_j1.generate_j1_tx(cfg)
        expected_dibits = tx["tx_dibits"]
        rx_iq = _run_hw_loopback(
            cfg=cfg,
            tx_iq=tx["x_tx_iq"],
            uri=uri,
            tx_lo_hz=tx_lo_hz,
            rx_lo_hz=rx_lo_hz,
            tx_gain_db=tx_gain_db,
            duration_s=duration_s,
            samples=samples,
            gain_mode=gain_mode,
            manual_gain_db=manual_gain_db,
            pluto_loopback=pluto_loopback,
        )
        data_source = "hardware"

    elif mode == "rx-only":
        rx_iq = pluto_io.capture_rx(
            num_samples=samples,
            sample_rate=cfg.sample_rate,
            rx_lo_hz=rx_lo_hz,
            uri=uri,
            gain_mode=gain_mode,
            manual_gain_db=manual_gain_db,
        )
        data_source = "hardware"
    elif mode == "replay":
        rx_iq, replay_path_used = _load_replay_iq(replay_iq_path)
        data_source = "replay"
    else:
        raise ValueError(f"unsupported mode: {mode}")

    if save_rx_iq and data_source == "hardware":
        rx_iq_saved_path, replay_last_saved_path = _save_replay_iq(rx_iq, output_dir)

    rx = rx_j1.receive_j1(rx_iq, cfg, expected_dibits=expected_dibits)

    streams = _build_candidate_streams(rx)
    parsed = _select_best_parse(streams)

    conf = _compute_confidence(rx, parsed)
    ber = float(rx.get("ber", -1.0)) if "ber" in rx else None
    symbol_match = float(rx.get("alignment", {}).get("symbol_match_rate", -1.0)) if "alignment" in rx else None

    parser_selftest_valid = int(parser_selftest.stats.valid_frames) if parser_selftest is not None else 0
    parser_selftest_key = parser_selftest.best_key if parser_selftest is not None else None
    parser_selftest_pass = bool(
        parser_selftest is not None
        and parser_selftest_valid > 0
        and parser_selftest_key == expected_key
    )

    summary: Dict[str, object] = {
        "level": int(level),
        "mode": mode,
        "mode_requested": mode,
        "data_source": data_source,
        "expected_key": expected_key,
        "decoded_key": parsed.best_key,
        "confidence": int(conf["confidence"]),
        "confidence_wave": float(conf["confidence_wave"]),
        "confidence_sync": float(conf["confidence_sync"]),
        "confidence_key": float(conf["confidence_key"]),
        "wave_mse": float(conf["wave_mse"]),
        "parser_chain_impl": "software",
        "parser_selftest_bytes": int(parser_selftest_bytes),
        "parser_selftest_valid_frames": int(parser_selftest_valid),
        "parser_selftest_best_key": parser_selftest_key,
        "parser_selftest_pass": parser_selftest_pass,
        "replay_iq_path": None if replay_path_used is None else str(replay_path_used.resolve()),
        "rx_iq_saved_path": None if rx_iq_saved_path is None else str(rx_iq_saved_path.resolve()),
        "replay_last_saved_path": (
            None if replay_last_saved_path is None else str(replay_last_saved_path.resolve())
        ),
        "valid_frames": int(parsed.stats.valid_frames),
        "crc_fail_frames": int(parsed.stats.crc_fail_frames),
        "ascii_fail_frames": int(parsed.stats.ascii_fail_frames),
        "non_target_frames": int(parsed.stats.non_target_frames),
        "parsed_frames": int(parsed.stats.parsed_frames),
        "length_fail_frames": int(parsed.stats.length_fail_frames),
        "best_offset": int(rx["best_offset"]),
        "offset_scores": {str(k): float(v) for k, v in dict(rx["offset_scores"]).items()},
        "ber": None if ber is None else float(ber),
        "symbol_match_rate": None if symbol_match is None else float(symbol_match),
        "tx_lo_hz": float(tx_lo_hz),
        "rx_lo_hz": float(rx_lo_hz),
        "center_freq_hz": float(spec.center_freq_hz),
        "symbol_rate": float(spec.symbol_rate),
        "sps": int(spec.sps),
    }

    source_samples = tx["x_tx_iq"] if tx is not None else rx["x0_raw"]
    if include_plot_data:
        summary["plot_data"] = _build_plot_data(source_samples=source_samples, rx=rx, sample_rate=cfg.sample_rate)

    if save_artifacts:
        _save_source_waveform(source_samples, cfg.sample_rate, output_dir / "01_source_waveform.png")
        _save_filtered_waveform(rx["x2_lpf"], rx["x5_rrc"], cfg.sample_rate, output_dir / "02_filtered_waveform.png")
        _save_result_panel(summary, output_dir / "03_result_panel.png")
        _write_summary_json(summary, output_dir / "summary.json")

    return summary
