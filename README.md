# J1 Minimal Python Chain

This project provides a minimal, debuggable Python pipeline for:

- `j1` TX baseband generation
- software loopback RX demodulation
- optional PlutoSDR TX/RX hooks
- stage-by-stage plots (`x0` to `x6`)

## Install

```bash
pip install -r requirements.txt
```

Windows quick setup:

```powershell
.\setup_windows.ps1
```

Windows hardware setup (Pluto/NanoSDR + libiio):

```powershell
.\setup_windows.ps1 -Hardware
```

## Run Software Loopback

```bash
python main.py sim
```

Optional noise:

```bash
python main.py sim --noise-std 0.02
```

Plots are saved under `output/` by default.

## Pluto Modes

TX only:

```bash
python main.py tx-only --uri ip:192.168.2.1
```

RX only:

```bash
python main.py rx-only --uri ip:192.168.2.1
```

HW loopback:

```bash
python main.py hw-loopback --uri ip:192.168.2.1
```

## Protocol-Valid Jam Demo (0x0A06)

Run red-side level demo with protocol parsing (`SOF/CRC8/CRC16/cmd_id`):

```bash
python main.py jam-demo --level 1 --mode sim
python main.py jam-demo --level 2 --mode sim
python main.py jam-demo --level 3 --mode sim
```

Scan available Pluto contexts:

```bash
python main.py pluto-scan
```

Launch window UI (recommended for quick testing):

```bash
python main.py jam-gui
```

Or on Windows:

```powershell
.\run_gui.ps1
```

In GUI:

- Select level `1/2/3`
- Select mode `sim / hw-loopback / rx-only / replay / hw-or-replay`
- Click `Start Test`
- Source and filtered waveforms are plotted directly in UI (not image preview)
- Decoding result is shown as plain text with transparent source labels
- `Replay IQ` supports selecting a saved `.npy` capture
- `hw-or-replay` tries hardware first and transparently falls back to replay if hardware has no valid frame

Hardware/replay modes:

```bash
python main.py jam-demo --level 1 --mode rx-only --uri auto --save-rx-iq
python main.py jam-demo --level 1 --mode hw-loopback --uri auto --pluto-loopback 0 --save-rx-iq
python main.py jam-demo --level 1 --mode replay --replay-iq output/replay/last_hw_capture.npy
```

Pluto URI notes:

- `--uri auto`: auto-select first scanned context (USB or IP).
- `--uri usb:x.y.z`: force USB context.
- `--uri ip:192.168.2.1`: force network context.

Hardware loopback notes:

- `--pluto-loopback 0`: external RF path (recommended for realistic decode).
- `--pluto-loopback 1/2`: Pluto internal loopback modes for device diagnostics.
- For one-board RF loopback, connect TX to RX with proper attenuation.
- Add `--save-rx-iq` in hardware modes to save IQ for replay (`output/replay/last_hw_capture.npy`).

Artifacts per run:

- `01_source_waveform.png`
- `02_filtered_waveform.png`
- `03_result_panel.png`
- `summary.json`
- `00_rx_iq.npy` (hardware modes when saved)

## Files

- `config.py`: parameters and defaults
- `dsp.py`: core DSP blocks
- `protocol_rm.py`: protocol framing/CRC/key parser (`0x0A06`)
- `jam_demo.py`: level demo pipeline and acceptance artifacts
- `tx_j1.py`: TX chain
- `rx_j1.py`: RX chain
- `sim_loopback.py`: software loopback orchestration
- `plots.py`: time/spectrum/hist plotting
- `pluto_io.py`: optional Pluto I/O
- `jam_gui.py`: GUI with transparent hardware/replay flow
- `main.py`: CLI entrypoint

## Other Device Local Deployment (Windows)

This is the recommended workflow to run the same project on another laptop/PC.

### 1) Prerequisites on the new device

- Install Python 3.10+ (enable `Add Python to PATH`)
- Install Git for Windows
- (Optional) If you will use NanoSDR/Pluto hardware mode, keep internet available for dependency install

### 2) Clone repository

```powershell
git clone https://github.com/nazakinb123/rm-jam.git
cd rm-jam
```

### 3) Create environment and install dependencies

```powershell
.\setup_windows.ps1
```

### 4) Start GUI

```powershell
.\run_gui.ps1
```

### 5) Enable hardware mode (optional)

```powershell
.\setup_windows.ps1 -Hardware
```

Then in GUI:

- Use `sim` first for quick validation
- Use `hw-or-replay` for robust live demo
- If hardware decode is unstable, save IQ and switch to `replay`

### 6) Quick CLI validation (optional)

```powershell
.\.venv\Scripts\python.exe main.py jam-demo --level 1 --mode sim
.\.venv\Scripts\python.exe main.py pluto-scan
```

### 7) One-click sync to GitHub (optional)

```powershell
.\sync.ps1
```

Custom commit message:

```powershell
.\sync.ps1 -Message "feat: update gui"
```

Commit only, do not push:

```powershell
.\sync.ps1 -NoPush
```

### Common issues

- `fatal: not a git repository`: run commands inside `rm-jam` folder
- `403 denied` on push: GitHub account has no write permission to repository
- `No Pluto contexts found`: check USB/network link and rerun `python main.py pluto-scan`
