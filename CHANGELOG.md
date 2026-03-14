# Changelog

## 2026-03-15

### Changed
- Improved GUI waveform rendering clarity in `jam_gui.py`.
- Switched time-domain plots to a "clarity view" with decimation and trend overlays.
- Added default short time-window zoom to reduce dense waveform clutter on first render.
- Added smart Y-axis limits based on percentiles for better readability.
- Added smoothed spectrum overlay while keeping a light raw-spectrum trace.

### Notes
- Plot zoom/pan controls are still available via the built-in matplotlib toolbar.
