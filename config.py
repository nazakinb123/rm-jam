from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class J1Config:
    sample_rate: float = 2_000_000.0
    j1_symbol_rate: float = 500_000.0
    j1_freq_dev_hz: float = 125_000.0
    # j1 is at 432.2 MHz while LO is 432.7 MHz in your GRC graph.
    j1_shift_hz: float = -500_000.0

    rrc_alpha: float = 0.25
    rrc_span_symbols: int = 11

    lpf_cutoff_hz: float = 650_000.0
    lpf_transition_hz: float = 150_000.0
    lpf_taps: int = 129

    payload: bytes = b"AB12C9"
    payload_repeats: int = 200

    add_awgn: bool = False
    awgn_std: float = 0.015
    random_seed: int = 7

    time_plot_samples: int = 2000
    output_dir: Path = field(default_factory=lambda: Path("output"))
    fixed_sps: int | None = None
    tx_lo_hz: float = 432_700_000.0
    rx_lo_hz: float = 432_700_000.0

    @property
    def sps(self) -> int:
        if self.fixed_sps is not None:
            return int(self.fixed_sps)
        return int(round(self.sample_rate / self.j1_symbol_rate))

    @property
    def symbol_count(self) -> int:
        # 8 bits/byte -> 4 dibits symbols/byte.
        return len(self.payload) * self.payload_repeats * 4


def build_tx_bytes(cfg: J1Config) -> bytes:
    return cfg.payload * cfg.payload_repeats


@dataclass(frozen=True)
class RedJamLevelSpec:
    level: int
    center_freq_hz: float
    symbol_rate: float
    sps: int
    lpf_cutoff_hz: float
    default_key: str


RED_JAM_LEVEL_SPECS: Dict[int, RedJamLevelSpec] = {
    1: RedJamLevelSpec(
        level=1,
        center_freq_hz=432_200_000.0,
        symbol_rate=500_000.0,
        sps=4,
        lpf_cutoff_hz=520_000.0,
        default_key="R1A2B3",
    ),
    2: RedJamLevelSpec(
        level=2,
        center_freq_hz=432_600_000.0,
        symbol_rate=285_000.0,
        sps=7,
        lpf_cutoff_hz=305_000.0,
        default_key="R2C3D4",
    ),
    3: RedJamLevelSpec(
        level=3,
        center_freq_hz=433_200_000.0,
        symbol_rate=200_000.0,
        sps=10,
        lpf_cutoff_hz=220_000.0,
        default_key="R3E4F5",
    ),
}


def get_red_jam_level_spec(level: int) -> RedJamLevelSpec:
    if level not in RED_JAM_LEVEL_SPECS:
        raise ValueError(f"unsupported level: {level}")
    return RED_JAM_LEVEL_SPECS[level]


def build_red_jam_config(
    level: int,
    tx_lo_hz: float = 432_700_000.0,
    rx_lo_hz: float = 432_700_000.0,
) -> J1Config:
    spec = get_red_jam_level_spec(level)
    cfg = J1Config()
    cfg.j1_symbol_rate = spec.symbol_rate
    cfg.fixed_sps = spec.sps
    cfg.j1_freq_dev_hz = spec.symbol_rate / 4.0
    cfg.rrc_span_symbols = 11
    cfg.rrc_alpha = 0.25
    cfg.tx_lo_hz = tx_lo_hz
    cfg.rx_lo_hz = rx_lo_hz
    cfg.j1_shift_hz = spec.center_freq_hz - tx_lo_hz
    cfg.lpf_cutoff_hz = spec.lpf_cutoff_hz
    cfg.lpf_taps = 129
    cfg.payload_repeats = 1
    return cfg
