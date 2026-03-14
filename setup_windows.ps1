param(
    [switch]$Hardware
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

if ($Hardware) {
    winget install --id AnalogDevices.Libiio -e --accept-package-agreements --accept-source-agreements
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run GUI with:"
Write-Host ".\.venv\Scripts\python.exe main.py jam-gui"
