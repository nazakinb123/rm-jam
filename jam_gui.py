from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import jam_demo
import pluto_io
from config import get_red_jam_level_spec


class JamDemoApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("RM Jam Demo Console")
        try:
            self.root.tk.call("tk", "scaling", 1.15)
        except Exception:
            pass
        screen_w = max(1280, int(self.root.winfo_screenwidth()))
        screen_h = max(800, int(self.root.winfo_screenheight()))
        win_w = min(2160, max(1760, int(screen_w * 0.92)))
        win_h = min(1320, max(980, int(screen_h * 0.90)))
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(1440, 900)

        self._running = False

        self.level_var = tk.StringVar(value="1")
        self.mode_var = tk.StringVar(value="sim")
        self.uri_var = tk.StringVar(value="auto")
        self.key_var = tk.StringVar(value="")
        self.samples_var = tk.StringVar(value="524288")
        self.tx_gain_var = tk.StringVar(value="-10")
        self.gain_mode_var = tk.StringVar(value="manual")
        self.manual_gain_var = tk.StringVar(value="30")
        self.noise_std_var = tk.StringVar(value="0.0")
        self.pluto_loopback_var = tk.StringVar(value="0")
        self.replay_iq_var = tk.StringVar(value=str(jam_demo.get_default_replay_iq_path()))
        self.auto_retry_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")

        self._build_layout()
        self._sync_default_key()

    def _build_layout(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        controls = ttk.Frame(top)
        controls.pack(side="left", fill="x", expand=True)
        actions = ttk.Frame(top)
        actions.pack(side="right", anchor="n", padx=(10, 0))

        controls.columnconfigure(9, weight=1)

        ttk.Label(controls, text="Level").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        level_box = ttk.Combobox(
            controls, textvariable=self.level_var, values=["1", "2", "3"], width=6, state="readonly"
        )
        level_box.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        level_box.bind("<<ComboboxSelected>>", lambda _: self._sync_default_key())

        ttk.Label(controls, text="Mode").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        ttk.Combobox(
            controls,
            textvariable=self.mode_var,
            values=["sim", "hw-loopback", "rx-only", "replay", "hw-or-replay"],
            width=14,
            state="readonly",
        ).grid(row=0, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(controls, text="URI").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        ttk.Entry(controls, textvariable=self.uri_var, width=22).grid(row=0, column=5, sticky="w", padx=4, pady=2)
        ttk.Button(controls, text="Scan", command=self._scan_uris).grid(row=0, column=6, padx=6, pady=2)

        ttk.Label(controls, text="Key(6)").grid(row=0, column=7, sticky="w", padx=4, pady=2)
        ttk.Entry(controls, textvariable=self.key_var, width=10).grid(row=0, column=8, sticky="w", padx=4, pady=2)

        ttk.Label(controls, text="Samples").grid(row=1, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(controls, textvariable=self.samples_var, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=6)

        ttk.Label(controls, text="TX Gain(dB)").grid(row=1, column=2, sticky="w", padx=4, pady=6)
        ttk.Entry(controls, textvariable=self.tx_gain_var, width=10).grid(row=1, column=3, sticky="w", padx=4, pady=6)

        ttk.Label(controls, text="RX Gain Mode").grid(row=1, column=4, sticky="w", padx=4, pady=6)
        ttk.Combobox(
            controls,
            textvariable=self.gain_mode_var,
            values=["slow_attack", "fast_attack", "manual"],
            width=12,
            state="readonly",
        ).grid(row=1, column=5, sticky="w", padx=4, pady=6)

        ttk.Label(controls, text="Manual RX Gain").grid(row=1, column=6, sticky="w", padx=4, pady=6)
        ttk.Entry(controls, textvariable=self.manual_gain_var, width=10).grid(
            row=1, column=7, sticky="w", padx=4, pady=6
        )

        ttk.Label(controls, text="Noise(sim)").grid(row=1, column=8, sticky="w", padx=4, pady=6)
        ttk.Entry(controls, textvariable=self.noise_std_var, width=10).grid(row=1, column=9, sticky="w", padx=4, pady=6)

        ttk.Label(controls, text="Pluto Loopback").grid(row=1, column=10, sticky="w", padx=4, pady=6)
        ttk.Combobox(
            controls,
            textvariable=self.pluto_loopback_var,
            values=["0", "1", "2"],
            width=4,
            state="readonly",
        ).grid(row=1, column=11, sticky="w", padx=4, pady=6)

        ttk.Checkbutton(controls, text="Auto Retry (HW)", variable=self.auto_retry_var).grid(
            row=1, column=12, sticky="w", padx=8, pady=6
        )

        ttk.Label(controls, text="Replay IQ").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(controls, textvariable=self.replay_iq_var).grid(
            row=2, column=1, columnspan=9, sticky="we", padx=4, pady=4
        )
        ttk.Button(controls, text="Browse", command=self._browse_replay_iq).grid(row=2, column=10, padx=6, pady=4)
        ttk.Button(controls, text="Use Last", command=self._use_default_replay).grid(row=2, column=11, padx=6, pady=4)

        ttk.Button(actions, text="Hardware Preset", command=self._apply_hw_preset).pack(
            fill="x", pady=(0, 8), ipadx=8, ipady=4
        )
        self.run_btn = ttk.Button(actions, text="Start Test", command=self._on_run)
        self.run_btn.pack(fill="x", ipadx=8, ipady=8)

        status_bar = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        status_bar.pack(fill="x")
        ttk.Label(status_bar, textvariable=self.status_var, foreground="#1f4e79").pack(anchor="w")

        middle = ttk.Frame(self.root, padding=8)
        middle.pack(fill="both", expand=True)
        middle.columnconfigure(0, weight=1)
        middle.columnconfigure(1, weight=1)
        middle.columnconfigure(2, weight=1)
        middle.rowconfigure(0, weight=1)

        self.source_frame = ttk.LabelFrame(middle, text="Source Waveform", padding=6)
        self.source_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        self.filtered_frame = ttk.LabelFrame(middle, text="Filtered/Processed Waveform", padding=6)
        self.filtered_frame.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        self.result_frame = ttk.LabelFrame(middle, text="Decode Result (Text)", padding=6)
        self.result_frame.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")

        self.source_fig = Figure(figsize=(5.4, 4.8), dpi=132)
        self.source_ax_time = self.source_fig.add_subplot(211)
        self.source_ax_spec = self.source_fig.add_subplot(212)
        self.source_canvas = FigureCanvasTkAgg(self.source_fig, master=self.source_frame)
        self.source_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.source_toolbar = NavigationToolbar2Tk(self.source_canvas, self.source_frame, pack_toolbar=False)
        self.source_toolbar.update()
        self.source_toolbar.pack(fill="x", side="bottom")

        self.filtered_fig = Figure(figsize=(5.4, 4.8), dpi=132)
        self.filtered_ax_lpf = self.filtered_fig.add_subplot(211)
        self.filtered_ax_post = self.filtered_fig.add_subplot(212)
        self.filtered_canvas = FigureCanvasTkAgg(self.filtered_fig, master=self.filtered_frame)
        self.filtered_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.filtered_toolbar = NavigationToolbar2Tk(self.filtered_canvas, self.filtered_frame, pack_toolbar=False)
        self.filtered_toolbar.update()
        self.filtered_toolbar.pack(fill="x", side="bottom")

        self.result_text = scrolledtext.ScrolledText(self.result_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.result_text.pack(fill="both", expand=True)

        self._reset_plot_axes()

    def _reset_plot_axes(self) -> None:
        for ax in [self.source_ax_time, self.source_ax_spec, self.filtered_ax_lpf, self.filtered_ax_post]:
            ax.clear()
            ax.grid(alpha=0.28)
        self.source_ax_time.set_title("Source IQ (Time)")
        self.source_ax_time.set_xlabel("Time (ms)")
        self.source_ax_time.set_ylabel("Amplitude")
        self.source_ax_spec.set_title("Source Spectrum")
        self.source_ax_spec.set_xlabel("Frequency (kHz)")
        self.source_ax_spec.set_ylabel("Magnitude (dB)")
        self.filtered_ax_lpf.set_title("LPF Output (x2_lpf)")
        self.filtered_ax_lpf.set_xlabel("Time (ms)")
        self.filtered_ax_lpf.set_ylabel("Amplitude")
        self.filtered_ax_post.set_title("Post Demod + RRC (x5_rrc)")
        self.filtered_ax_post.set_xlabel("Time (ms)")
        self.filtered_ax_post.set_ylabel("Amplitude")
        self.source_fig.tight_layout()
        self.filtered_fig.tight_layout()
        self.source_canvas.draw()
        self.filtered_canvas.draw()

    def _scan_uris(self) -> None:
        try:
            uris = pluto_io.scan_pluto_uris()
        except Exception as exc:
            messagebox.showerror("Scan failed", str(exc))
            return
        if not uris:
            messagebox.showwarning("Scan result", "No Pluto devices found.")
            return
        self.uri_var.set(uris[0])
        messagebox.showinfo("Scan result", "Found devices:\n" + "\n".join(uris))

    def _browse_replay_iq(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Replay IQ (.npy)",
            filetypes=[("NumPy files", "*.npy"), ("All files", "*.*")],
        )
        if path:
            self.replay_iq_var.set(path)

    def _use_default_replay(self) -> None:
        self.replay_iq_var.set(str(jam_demo.get_default_replay_iq_path()))

    def _sync_default_key(self) -> None:
        try:
            level = int(self.level_var.get())
            self.key_var.set(get_red_jam_level_spec(level).default_key)
        except Exception:
            pass

    def _apply_hw_preset(self) -> None:
        self.mode_var.set("hw-or-replay")
        self.uri_var.set("auto")
        self.samples_var.set("524288")
        self.tx_gain_var.set("-10")
        self.gain_mode_var.set("manual")
        self.manual_gain_var.set("30")
        self.noise_std_var.set("0.0")
        self.pluto_loopback_var.set("0")
        self.replay_iq_var.set(str(jam_demo.get_default_replay_iq_path()))
        self.auto_retry_var.set(True)

    def _on_run(self) -> None:
        if self._running:
            return
        try:
            params = {
                "level": int(self.level_var.get()),
                "mode": self.mode_var.get(),
                "uri": self.uri_var.get().strip() or "auto",
                "key": self.key_var.get().strip().upper(),
                "samples": int(self.samples_var.get()),
                "tx_gain_db": float(self.tx_gain_var.get()),
                "gain_mode": self.gain_mode_var.get(),
                "manual_gain_db": float(self.manual_gain_var.get()),
                "noise_std": float(self.noise_std_var.get()),
                "pluto_loopback": int(self.pluto_loopback_var.get()),
                "replay_iq_path": self.replay_iq_var.get().strip(),
            }
        except ValueError as exc:
            messagebox.showerror("Invalid parameter", f"Parameter parse error: {exc}")
            return

        if not params["key"]:
            self._sync_default_key()
            params["key"] = self.key_var.get().strip().upper()

        self._running = True
        self.run_btn.configure(state=tk.DISABLED)
        self.status_var.set("Running...")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, "Running...\n")
        self._reset_plot_axes()

        threading.Thread(target=self._run_worker, args=(params,), daemon=True).start()

    def _build_attempts(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        mode = str(params["mode"])
        if mode in {"sim", "replay"}:
            return [dict(params)]
        if mode == "hw-or-replay":
            base = dict(params)
            base["mode"] = "hw-loopback"
            mode = "hw-loopback"
            params = base
        if not self.auto_retry_var.get():
            return [dict(params)]

        attempts: List[Dict[str, Any]] = [dict(params)]

        def add_attempt(**updates: Any) -> None:
            p = dict(params)
            p.update(updates)
            attempts.append(p)

        base_samples = int(params["samples"])

        if mode == "hw-loopback":
            add_attempt(samples=max(base_samples, 524288), gain_mode="manual", manual_gain_db=30.0, tx_gain_db=-10.0, pluto_loopback=0)
            add_attempt(samples=max(base_samples, 524288), gain_mode="manual", manual_gain_db=35.0, tx_gain_db=-8.0, pluto_loopback=0)
            add_attempt(samples=max(base_samples, 524288), gain_mode="manual", manual_gain_db=25.0, tx_gain_db=-5.0, pluto_loopback=0)

            # Internal loopback tries help us verify whether DSP/protocol stack is healthy.
            add_attempt(samples=max(base_samples, 262144), gain_mode="manual", manual_gain_db=10.0, tx_gain_db=-20.0, pluto_loopback=1)
            add_attempt(samples=max(base_samples, 262144), gain_mode="manual", manual_gain_db=15.0, tx_gain_db=-15.0, pluto_loopback=1)
            add_attempt(samples=max(base_samples, 262144), gain_mode="manual", manual_gain_db=20.0, tx_gain_db=-12.0, pluto_loopback=2)
        elif mode == "rx-only":
            add_attempt(samples=max(base_samples, 524288), gain_mode="manual", manual_gain_db=25.0)
            add_attempt(samples=max(base_samples, 524288), gain_mode="manual", manual_gain_db=30.0)
            add_attempt(samples=max(base_samples, 524288), gain_mode="manual", manual_gain_db=35.0)
            add_attempt(samples=max(base_samples, 524288), gain_mode="slow_attack")
            add_attempt(samples=max(base_samples, 1048576), gain_mode="manual", manual_gain_db=30.0)

        unique: List[Dict[str, Any]] = []
        seen: set[Tuple[Any, ...]] = set()
        for a in attempts:
            key = (
                a["mode"],
                a["uri"],
                int(a["samples"]),
                float(a["tx_gain_db"]),
                str(a["gain_mode"]),
                float(a["manual_gain_db"]),
                int(a["pluto_loopback"]),
                float(a["noise_std"]),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(a)
        return unique

    @staticmethod
    def _score_summary(summary: Dict[str, Any], expected_key: str) -> Tuple[int, int, int, int, int, float]:
        decoded = summary.get("decoded_key")
        exact = 1 if decoded == expected_key else 0
        valid = int(summary.get("valid_frames", 0) or 0)
        has_key = 1 if decoded else 0
        conf = int(summary.get("confidence", 0) or 0)
        crc_penalty = -int(summary.get("crc_fail_frames", 0) or 0)
        ber = summary.get("ber")
        ber_score = 0.0 if ber is None else -float(ber)
        return (exact, valid, has_key, conf, crc_penalty, ber_score)

    @staticmethod
    def _is_pass(summary: Dict[str, Any], expected_key: str) -> bool:
        return bool(summary.get("decoded_key") == expected_key and int(summary.get("valid_frames", 0) or 0) > 0)

    def _run_single_attempt(self, params: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
        mode = str(params["mode"])
        return jam_demo.run_jam_demo(
            level=params["level"],
            mode=mode,
            output_dir=out_dir,
            key=params["key"],
            uri=params["uri"],
            tx_gain_db=params["tx_gain_db"],
            samples=params["samples"],
            gain_mode=params["gain_mode"],
            manual_gain_db=params["manual_gain_db"],
            noise_std=params["noise_std"],
            pluto_loopback=params["pluto_loopback"],
            replay_iq_path=params.get("replay_iq_path") or None,
            save_rx_iq=(mode in {"hw-loopback", "rx-only"}),
            save_artifacts=True,
            include_plot_data=True,
        )

    def _run_worker(self, params: Dict[str, Any]) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        requested_mode = str(params["mode"])
        attempts = self._build_attempts(params)
        expected_key = str(params["key"])

        best_summary: Dict[str, Any] | None = None
        best_out_dir: Path | None = None
        best_score: Tuple[int, int, int, int, int, float] | None = None
        logs: List[Dict[str, Any]] = []
        error_messages: List[str] = []
        hw_valid_any = False

        for i, attempt in enumerate(attempts, start=1):
            out_dir = Path("output") / f"gui_level{attempt['level']}_{attempt['mode']}_{timestamp}_try{i}"
            self.root.after(0, lambda n=i, t=len(attempts): self.status_var.set(f"Running attempt {n}/{t} ..."))
            try:
                summary = self._run_single_attempt(attempt, out_dir)
            except Exception as exc:
                msg = f"attempt {i}: {exc}"
                error_messages.append(msg)
                logs.append(
                    {
                        "attempt": i,
                        "error": str(exc),
                        "params": {
                            "mode": attempt["mode"],
                            "samples": attempt["samples"],
                            "tx_gain_db": attempt["tx_gain_db"],
                            "gain_mode": attempt["gain_mode"],
                            "manual_gain_db": attempt["manual_gain_db"],
                            "pluto_loopback": attempt["pluto_loopback"],
                            "uri": attempt["uri"],
                            "replay_iq_path": attempt.get("replay_iq_path"),
                        },
                    }
                )
                continue

            summary["attempt"] = i
            summary["mode_requested"] = requested_mode
            score = self._score_summary(summary, expected_key)
            logs.append(
                {
                    "attempt": i,
                    "mode": attempt["mode"],
                    "data_source": summary.get("data_source"),
                    "decoded_key": summary.get("decoded_key"),
                    "confidence": summary.get("confidence"),
                    "valid_frames": summary.get("valid_frames"),
                    "crc_fail_frames": summary.get("crc_fail_frames"),
                    "ascii_fail_frames": summary.get("ascii_fail_frames"),
                    "ber": summary.get("ber"),
                    "params": {
                        "mode": attempt["mode"],
                        "samples": attempt["samples"],
                        "tx_gain_db": attempt["tx_gain_db"],
                        "gain_mode": attempt["gain_mode"],
                        "manual_gain_db": attempt["manual_gain_db"],
                        "pluto_loopback": attempt["pluto_loopback"],
                        "uri": attempt["uri"],
                        "replay_iq_path": attempt.get("replay_iq_path"),
                    },
                }
            )

            if best_summary is None or (best_score is not None and score > best_score) or best_score is None:
                best_summary = summary
                best_out_dir = out_dir
                best_score = score

            if str(attempt["mode"]) == "hw-loopback" and int(summary.get("valid_frames", 0) or 0) > 0:
                hw_valid_any = True

            if self._is_pass(summary, expected_key):
                break

        if requested_mode == "hw-or-replay" and not hw_valid_any:
            replay_path = (params.get("replay_iq_path") or "").strip() or str(jam_demo.get_default_replay_iq_path())
            replay_attempt = dict(params)
            replay_attempt["mode"] = "replay"
            replay_attempt["replay_iq_path"] = replay_path
            i = len(logs) + 1
            out_dir = Path("output") / f"gui_level{params['level']}_replay_{timestamp}_try{i}"
            self.root.after(0, lambda: self.status_var.set("Hardware failed, trying replay fallback ..."))
            try:
                replay_summary = self._run_single_attempt(replay_attempt, out_dir)
                replay_summary["attempt"] = i
                replay_summary["mode_requested"] = requested_mode
                replay_summary["fallback_used"] = True
                replay_summary["fallback_reason"] = "hardware_no_valid_frame"
                replay_summary["replay_selected_by_gui"] = True
                logs.append(
                    {
                        "attempt": i,
                        "mode": "replay",
                        "data_source": replay_summary.get("data_source"),
                        "decoded_key": replay_summary.get("decoded_key"),
                        "confidence": replay_summary.get("confidence"),
                        "valid_frames": replay_summary.get("valid_frames"),
                        "crc_fail_frames": replay_summary.get("crc_fail_frames"),
                        "ascii_fail_frames": replay_summary.get("ascii_fail_frames"),
                        "ber": replay_summary.get("ber"),
                        "params": {"mode": "replay", "replay_iq_path": replay_path},
                    }
                )
                best_summary = replay_summary
                best_out_dir = out_dir
                best_score = self._score_summary(replay_summary, expected_key)
            except Exception as exc:
                logs.append(
                    {
                        "attempt": i,
                        "mode": "replay",
                        "error": str(exc),
                        "params": {"mode": "replay", "replay_iq_path": replay_path},
                    }
                )
                error_messages.append(f"replay fallback: {exc}")

        if best_summary is None or best_out_dir is None:
            if error_messages:
                err = "All attempts failed:\n" + "\n".join(error_messages)
            else:
                err = "No valid result from all attempts."
            self.root.after(0, lambda: self._on_error(err))
            return

        if "fallback_used" not in best_summary:
            best_summary["fallback_used"] = False
            best_summary["fallback_reason"] = None
        best_summary["attempt_log"] = logs
        best_summary["attempt_count"] = len(logs)
        self.root.after(0, lambda: self._on_success(best_out_dir, best_summary))

    def _render_plots(self, plot_data: Dict[str, Any]) -> None:
        t_src = plot_data["t_source_ms"]
        src_i = plot_data["source_i"]
        src_q = plot_data["source_q"]
        spec_f = plot_data["spec_freq_khz"]
        spec_p = plot_data["spec_power_db"]
        t_x2 = plot_data["t_x2_ms"]
        x2_i = plot_data["x2_i"]
        x2_q = plot_data["x2_q"]
        t_x5 = plot_data["t_x5_ms"]
        x5 = plot_data["x5"]

        self.source_ax_time.clear()
        self.source_ax_time.plot(t_src, src_i, lw=0.9, label="I")
        self.source_ax_time.plot(t_src, src_q, lw=0.9, label="Q", alpha=0.82)
        self.source_ax_time.set_title("Source IQ (Time)")
        self.source_ax_time.set_xlabel("Time (ms)")
        self.source_ax_time.set_ylabel("Amplitude")
        self.source_ax_time.grid(alpha=0.28)
        self.source_ax_time.legend(loc="upper right")

        self.source_ax_spec.clear()
        self.source_ax_spec.plot(spec_f, spec_p, lw=0.9, color="#1f77b4")
        self.source_ax_spec.set_title("Source Spectrum")
        self.source_ax_spec.set_xlabel("Frequency (kHz)")
        self.source_ax_spec.set_ylabel("Magnitude (dB)")
        self.source_ax_spec.grid(alpha=0.28)
        self.source_fig.tight_layout()
        self.source_canvas.draw()

        self.filtered_ax_lpf.clear()
        self.filtered_ax_lpf.plot(t_x2, x2_i, lw=0.9, label="I")
        self.filtered_ax_lpf.plot(t_x2, x2_q, lw=0.9, label="Q", alpha=0.82)
        self.filtered_ax_lpf.set_title("LPF Output (x2_lpf)")
        self.filtered_ax_lpf.set_xlabel("Time (ms)")
        self.filtered_ax_lpf.set_ylabel("Amplitude")
        self.filtered_ax_lpf.grid(alpha=0.28)
        self.filtered_ax_lpf.legend(loc="upper right")

        self.filtered_ax_post.clear()
        self.filtered_ax_post.plot(t_x5, x5, lw=0.9, color="#2ca02c")
        self.filtered_ax_post.set_title("Post Demod + RRC (x5_rrc)")
        self.filtered_ax_post.set_xlabel("Time (ms)")
        self.filtered_ax_post.set_ylabel("Amplitude")
        self.filtered_ax_post.grid(alpha=0.28)
        self.filtered_fig.tight_layout()
        self.filtered_canvas.draw()

    def _build_tips(self, summary_no_plot: Dict[str, Any]) -> List[str]:
        tips: List[str] = []
        decoded = summary_no_plot.get("decoded_key")
        valid_frames = int(summary_no_plot.get("valid_frames", 0) or 0)
        mode = str(summary_no_plot.get("mode"))
        mode_requested = str(summary_no_plot.get("mode_requested", mode))
        data_source = str(summary_no_plot.get("data_source"))
        fallback_used = bool(summary_no_plot.get("fallback_used", False))
        parser_selftest_pass = bool(summary_no_plot.get("parser_selftest_pass", False))
        parser_impl = str(summary_no_plot.get("parser_chain_impl", "software"))
        logs: List[Dict[str, Any]] = summary_no_plot.get("attempt_log", [])

        if fallback_used:
            tips.append("Hardware had no valid frame; GUI switched to replay fallback transparently.")
        if data_source == "replay":
            tips.append("Current result comes from replay IQ file, not live RF.")

        if decoded is None and valid_frames == 0:
            tips.append("No valid protocol frame found.")
            if parser_selftest_pass:
                tips.append(
                    f"Parser chain is implemented in {parser_impl} and self-test passed; issue is on RF/demod path, not parser missing."
                )
            else:
                tips.append("Parser self-test did not pass in this run. Check payload generation / parser integration first.")
            if mode_requested in {"hw-loopback", "hw-or-replay"}:
                any_internal_ok = any(
                    int((x.get("params") or {}).get("pluto_loopback", 0)) > 0 and int(x.get("valid_frames", 0) or 0) > 0
                    for x in logs
                    if "error" not in x
                )
                if any_internal_ok:
                    tips.append("Internal loopback can decode but external cannot: check TX-RX cable path and 30-40 dB attenuator.")
                else:
                    tips.append("Try external RF loopback path with attenuator, then rerun hardware preset.")
                    tips.append("If using network URI, click Scan and prefer auto/usb:* first.")
            elif mode_requested == "rx-only":
                tips.append("RX-only cannot decode target frame yet; check whether transmitter is on and center frequency matches level.")
        else:
            tips.append("Link is healthy. You can move to next level or switch mode for verification.")
        return tips

    def _on_success(self, out_dir: Path, summary: Dict[str, Any]) -> None:
        plot_data = summary.get("plot_data")
        if isinstance(plot_data, dict):
            self._render_plots(plot_data)

        summary_no_plot: Dict[str, Any] = {k: v for k, v in summary.items() if k != "plot_data"}
        tips = self._build_tips(summary_no_plot)
        logs: List[Dict[str, Any]] = summary_no_plot.get("attempt_log", [])

        lines = [
            f"Level: {summary_no_plot.get('level')} ({summary_no_plot.get('mode')})",
            f"Mode Requested: {summary_no_plot.get('mode_requested')}",
            f"Data Source: {summary_no_plot.get('data_source')}",
            f"Decoded Key: {summary_no_plot.get('decoded_key')}",
            f"Expected Key: {summary_no_plot.get('expected_key')}",
            f"Confidence: {summary_no_plot.get('confidence')}%",
            f"Fallback Used: {summary_no_plot.get('fallback_used')} reason={summary_no_plot.get('fallback_reason')}",
            "Parser SelfTest: "
            f"pass={summary_no_plot.get('parser_selftest_pass')} "
            f"best_key={summary_no_plot.get('parser_selftest_best_key')} "
            f"valid={summary_no_plot.get('parser_selftest_valid_frames')} "
            f"bytes={summary_no_plot.get('parser_selftest_bytes')}",
            "Frame Stats: "
            f"valid={summary_no_plot.get('valid_frames')}, "
            f"crc_fail={summary_no_plot.get('crc_fail_frames')}, "
            f"ascii_fail={summary_no_plot.get('ascii_fail_frames')}",
            f"Best Offset: {summary_no_plot.get('best_offset')}",
            f"BER: {summary_no_plot.get('ber')}",
            f"Replay IQ: {summary_no_plot.get('replay_iq_path')}",
            f"Saved RX IQ: {summary_no_plot.get('rx_iq_saved_path')}",
            f"Last Replay IQ: {summary_no_plot.get('replay_last_saved_path')}",
            f"Artifacts: {out_dir.resolve()}",
            "",
            f"Attempts: {summary_no_plot.get('attempt_count', 1)}",
        ]

        for item in logs:
            a = item.get("attempt")
            p = item.get("params", {})
            if "error" in item:
                lines.append(f"  A{a}: ERROR={item['error']} | params={p}")
                continue
            lines.append(
                "  "
                + (
                    f"A{a}: mode={item.get('mode')} source={item.get('data_source')} "
                    f"key={item.get('decoded_key')} conf={item.get('confidence')}% "
                    f"valid={item.get('valid_frames')} crc={item.get('crc_fail_frames')} "
                    f"ascii={item.get('ascii_fail_frames')} ber={item.get('ber')} "
                    f"params={p}"
                )
            )

        lines += ["", "Diagnostic:", *tips, "", json.dumps(summary_no_plot, indent=2, ensure_ascii=False)]

        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, "\n".join(lines))

        self.status_var.set(
            f"Done: source={summary_no_plot.get('data_source')} decoded={summary_no_plot.get('decoded_key')}, confidence={summary_no_plot.get('confidence')}%"
        )
        self._running = False
        self.run_btn.configure(state=tk.NORMAL)

    def _on_error(self, err: str) -> None:
        self.status_var.set("Run failed")
        self._running = False
        self.run_btn.configure(state=tk.NORMAL)
        messagebox.showerror("Run failed", err)


def launch_gui() -> None:
    root = tk.Tk()
    JamDemoApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
