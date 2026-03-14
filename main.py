from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

import numpy as np

import jam_demo
import jam_gui
import plots
import pluto_io
import rx_j1
import sim_loopback
import tx_j1
from config import J1Config


def build_cfg_from_args(args: argparse.Namespace) -> J1Config:
    cfg = J1Config()
    cfg.output_dir = Path(args.output_dir)
    cfg.payload_repeats = args.repeats
    cfg.add_awgn = args.noise_std > 0.0
    cfg.awgn_std = args.noise_std

    if args.payload is not None:
        cfg.payload = args.payload.encode("utf-8")
    return cfg


def cmd_sim(args: argparse.Namespace) -> None:
    cfg = build_cfg_from_args(args)
    summary = sim_loopback.run_simulation(cfg)

    print("=== SIM SUMMARY ===")
    print(f"BER: {summary['ber']:.6f}")
    print(f"Symbol match: {summary['symbol_match_rate']:.6f}")
    print(f"Best offset: {summary['best_offset']}")
    print(f"Alignment lag (symbols): {summary['alignment_lag_symbols']}")
    print(f"TX head: {summary['tx_bytes_head']}")
    print(f"RX head: {summary['rx_bytes_head']}")
    print(f"Plots saved to: {summary['output_dir']}")


def cmd_tx_only(args: argparse.Namespace) -> None:
    cfg = build_cfg_from_args(args)
    tx = tx_j1.generate_j1_tx(cfg)
    tx_iq = tx["x_tx_iq"]

    print("Starting Pluto TX...")
    pluto_io.transmit_cyclic(
        iq=tx_iq,
        sample_rate=cfg.sample_rate,
        tx_lo_hz=args.tx_lo,
        uri=args.uri,
        tx_gain_db=args.tx_gain_db,
        duration_s=args.duration_s,
    )
    print("TX done.")


def cmd_rx_only(args: argparse.Namespace) -> None:
    cfg = build_cfg_from_args(args)
    rx_iq = pluto_io.capture_rx(
        num_samples=args.samples,
        sample_rate=cfg.sample_rate,
        rx_lo_hz=args.rx_lo,
        uri=args.uri,
        gain_mode=args.gain_mode,
        manual_gain_db=args.manual_gain_db,
    )
    rx = rx_j1.receive_j1(rx_iq, cfg, expected_dibits=None)
    plots.save_stage_plots(
        stages={
            "x0_raw": rx["x0_raw"],
            "x1_rot": rx["x1_rot"],
            "x2_lpf": rx["x2_lpf"],
            "x3_qd": rx["x3_qd"],
            "x4_norm": rx["x4_norm"],
            "x5_rrc": rx["x5_rrc"],
            "x6_downsample": rx["x6_downsample"],
            "x6_norm": rx["x6_norm"],
        },
        sample_rate=cfg.sample_rate,
        out_dir=cfg.output_dir,
        max_samples=cfg.time_plot_samples,
        sps=cfg.sps,
    )
    rx_bytes = bytes(np.asarray(rx["rx_bytes"][:32], dtype=np.uint8))
    print("=== RX SUMMARY ===")
    print(f"Best offset: {rx['best_offset']}")
    print(f"RX head: {rx_bytes}")
    print(f"Plots saved to: {cfg.output_dir.resolve()}")


def cmd_hw_loopback(args: argparse.Namespace) -> None:
    cfg = build_cfg_from_args(args)
    tx = tx_j1.generate_j1_tx(cfg)
    tx_iq = tx["x_tx_iq"]

    tx_exc = []

    def _tx_task() -> None:
        try:
            pluto_io.transmit_cyclic(
                iq=tx_iq,
                sample_rate=cfg.sample_rate,
                tx_lo_hz=args.tx_lo,
                uri=args.uri,
                tx_gain_db=args.tx_gain_db,
                duration_s=args.duration_s,
            )
        except Exception as exc:  # pragma: no cover - hardware path
            tx_exc.append(exc)

    thread = threading.Thread(target=_tx_task, daemon=True)
    thread.start()
    time.sleep(0.25)

    rx_iq = pluto_io.capture_rx(
        num_samples=args.samples,
        sample_rate=cfg.sample_rate,
        rx_lo_hz=args.rx_lo,
        uri=args.uri,
        gain_mode=args.gain_mode,
        manual_gain_db=args.manual_gain_db,
    )
    thread.join(timeout=max(1.0, args.duration_s + 0.5))
    if tx_exc:
        raise tx_exc[0]

    rx = rx_j1.receive_j1(rx_iq, cfg, expected_dibits=tx["tx_dibits"])
    plots.save_stage_plots(
        stages={
            "x0_raw": rx["x0_raw"],
            "x1_rot": rx["x1_rot"],
            "x2_lpf": rx["x2_lpf"],
            "x3_qd": rx["x3_qd"],
            "x4_norm": rx["x4_norm"],
            "x5_rrc": rx["x5_rrc"],
            "x6_downsample": rx["x6_downsample"],
            "x6_norm": rx["x6_norm"],
        },
        sample_rate=cfg.sample_rate,
        out_dir=cfg.output_dir,
        max_samples=cfg.time_plot_samples,
        sps=cfg.sps,
    )
    rx_bytes = bytes(np.asarray(rx["rx_bytes"][:32], dtype=np.uint8))
    print("=== HW LOOPBACK SUMMARY ===")
    print(f"BER: {float(rx.get('ber', 1.0)):.6f}")
    print(f"Symbol match: {float(rx.get('alignment', {}).get('symbol_match_rate', 0.0)):.6f}")
    print(f"Best offset: {rx['best_offset']}")
    print(f"RX head: {rx_bytes}")
    print(f"Plots saved to: {cfg.output_dir.resolve()}")


def cmd_jam_demo(args: argparse.Namespace) -> None:
    if args.output_dir == "output":
        out_dir = Path("output") / f"jam_level{args.level}_{args.mode}"
    else:
        out_dir = Path(args.output_dir)

    summary = jam_demo.run_jam_demo(
        level=args.level,
        mode=args.mode,
        output_dir=out_dir,
        key=args.key,
        uri=args.uri,
        tx_lo_hz=args.tx_lo,
        rx_lo_hz=args.rx_lo,
        tx_gain_db=args.tx_gain_db,
        duration_s=args.duration_s,
        samples=args.samples,
        gain_mode=args.gain_mode,
        manual_gain_db=args.manual_gain_db,
        noise_std=args.noise_std,
        pluto_loopback=args.pluto_loopback,
        replay_iq_path=args.replay_iq,
        save_rx_iq=args.save_rx_iq,
    )

    print("=== JAM DEMO SUMMARY ===")
    print(f"Level: {summary['level']} ({summary['mode']})")
    print(f"Data source: {summary.get('data_source')}")
    print(f"Decoded key: {summary['decoded_key']}")
    print(f"Expected key: {summary['expected_key']}")
    print(f"Confidence: {summary['confidence']}%")
    print(
        "Parser self-test: "
        f"pass={summary.get('parser_selftest_pass')} "
        f"best_key={summary.get('parser_selftest_best_key')} "
        f"valid={summary.get('parser_selftest_valid_frames')}"
    )
    print(
        "Frames: "
        f"valid={summary['valid_frames']}, "
        f"crc_fail={summary['crc_fail_frames']}, "
        f"ascii_fail={summary['ascii_fail_frames']}"
    )
    if summary.get("replay_iq_path"):
        print(f"Replay IQ: {summary.get('replay_iq_path')}")
    if summary.get("rx_iq_saved_path"):
        print(f"Saved RX IQ: {summary.get('rx_iq_saved_path')}")
    print(f"Best offset: {summary['best_offset']}")
    print(f"Artifacts saved to: {out_dir.resolve()}")


def cmd_pluto_scan(args: argparse.Namespace) -> None:
    uris = pluto_io.scan_pluto_uris()
    print("=== PLUTO CONTEXTS ===")
    if not uris:
        print("No Pluto contexts found.")
        return
    for u in uris:
        print(u)


def cmd_jam_gui(args: argparse.Namespace) -> None:
    jam_gui.launch_gui()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="J1 minimal TX/RX project (sim + Pluto)")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--payload", type=str, default=None, help="ASCII payload, default AB12C9")
        sp.add_argument("--repeats", type=int, default=200, help="Payload repeats")
        sp.add_argument("--noise-std", type=float, default=0.0, help="Complex AWGN std (sim path)")
        sp.add_argument("--output-dir", type=str, default="output", help="Figure output directory")

    sim_p = sub.add_parser("sim", help="Pure software loopback")
    add_common(sim_p)
    sim_p.set_defaults(func=cmd_sim)

    tx_p = sub.add_parser("tx-only", help="Generate and TX j1 through Pluto")
    add_common(tx_p)
    tx_p.add_argument("--uri", type=str, default="auto", help="Pluto URI (e.g. auto, usb:2.9.5, ip:192.168.2.1)")
    tx_p.add_argument("--tx-lo", type=float, default=432_700_000.0, help="TX LO frequency (Hz)")
    tx_p.add_argument("--tx-gain-db", type=float, default=-30.0, help="TX gain (dB)")
    tx_p.add_argument("--duration-s", type=float, default=2.0, help="TX duration in seconds")
    tx_p.set_defaults(func=cmd_tx_only)

    rx_p = sub.add_parser("rx-only", help="Capture from Pluto and run RX chain")
    add_common(rx_p)
    rx_p.add_argument("--uri", type=str, default="auto", help="Pluto URI (e.g. auto, usb:2.9.5, ip:192.168.2.1)")
    rx_p.add_argument("--rx-lo", type=float, default=432_700_000.0, help="RX LO frequency (Hz)")
    rx_p.add_argument("--samples", type=int, default=262_144, help="RX sample count")
    rx_p.add_argument(
        "--gain-mode",
        type=str,
        default="slow_attack",
        choices=["slow_attack", "fast_attack", "manual"],
        help="RX gain mode",
    )
    rx_p.add_argument("--manual-gain-db", type=float, default=40.0, help="Manual RX gain (dB)")
    rx_p.set_defaults(func=cmd_rx_only)

    hw_p = sub.add_parser("hw-loopback", help="TX and RX with Pluto for debugging")
    add_common(hw_p)
    hw_p.add_argument("--uri", type=str, default="auto", help="Pluto URI (e.g. auto, usb:2.9.5, ip:192.168.2.1)")
    hw_p.add_argument("--tx-lo", type=float, default=432_700_000.0, help="TX LO frequency (Hz)")
    hw_p.add_argument("--rx-lo", type=float, default=432_700_000.0, help="RX LO frequency (Hz)")
    hw_p.add_argument("--tx-gain-db", type=float, default=-30.0, help="TX gain (dB)")
    hw_p.add_argument("--duration-s", type=float, default=2.0, help="TX duration in seconds")
    hw_p.add_argument("--samples", type=int, default=262_144, help="RX sample count")
    hw_p.add_argument(
        "--gain-mode",
        type=str,
        default="slow_attack",
        choices=["slow_attack", "fast_attack", "manual"],
        help="RX gain mode",
    )
    hw_p.add_argument("--manual-gain-db", type=float, default=40.0, help="Manual RX gain (dB)")
    hw_p.set_defaults(func=cmd_hw_loopback)

    jam_p = sub.add_parser("jam-demo", help="Protocol-valid red jam decoding demo (0x0A06)")
    jam_p.add_argument("--level", type=int, choices=[1, 2, 3], required=True, help="Red jam level")
    jam_p.add_argument(
        "--mode",
        type=str,
        default="sim",
        choices=["sim", "rx-only", "hw-loopback", "replay"],
        help="Demo mode",
    )
    jam_p.add_argument("--key", type=str, default=None, help="Expected 6-char [A-Z0-9] key")
    jam_p.add_argument("--output-dir", type=str, default="output", help="Artifact output directory")
    jam_p.add_argument("--noise-std", type=float, default=0.0, help="AWGN std for sim")
    jam_p.add_argument("--uri", type=str, default="auto", help="Pluto URI (e.g. auto, usb:2.9.5, ip:192.168.2.1)")
    jam_p.add_argument("--tx-lo", type=float, default=432_700_000.0, help="TX LO frequency (Hz)")
    jam_p.add_argument("--rx-lo", type=float, default=432_700_000.0, help="RX LO frequency (Hz)")
    jam_p.add_argument("--tx-gain-db", type=float, default=-30.0, help="TX gain (dB)")
    jam_p.add_argument("--duration-s", type=float, default=2.0, help="TX duration in seconds")
    jam_p.add_argument("--samples", type=int, default=262_144, help="RX sample count")
    jam_p.add_argument(
        "--gain-mode",
        type=str,
        default="slow_attack",
        choices=["slow_attack", "fast_attack", "manual"],
        help="RX gain mode",
    )
    jam_p.add_argument("--manual-gain-db", type=float, default=40.0, help="Manual RX gain (dB)")
    jam_p.add_argument(
        "--pluto-loopback",
        type=int,
        default=1,
        choices=[0, 1, 2],
        help="Pluto internal loopback mode for hw-loopback (0=off)",
    )
    jam_p.add_argument("--replay-iq", type=str, default=None, help="Path to .npy IQ capture for replay mode")
    jam_p.add_argument(
        "--save-rx-iq",
        action="store_true",
        help="Save hardware RX IQ to output and update output/replay/last_hw_capture.npy",
    )
    jam_p.set_defaults(func=cmd_jam_demo)

    scan_p = sub.add_parser("pluto-scan", help="List discovered Pluto contexts")
    scan_p.set_defaults(func=cmd_pluto_scan)

    gui_p = sub.add_parser("jam-gui", help="Launch window UI for jam demo testing")
    gui_p.set_defaults(func=cmd_jam_gui)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
