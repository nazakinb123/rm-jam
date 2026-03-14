$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "No virtual environment found. Run .\setup_windows.ps1 first."
    exit 1
}

& .\.venv\Scripts\python.exe main.py jam-gui
