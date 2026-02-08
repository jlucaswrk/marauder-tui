# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Marauder TUI — a hacker-style terminal UI for controlling an ESP32 running Marauder firmware. Python 3.9+ with Textual (TUI framework) and PySerial (serial communication).

## Commands

```bash
# Install in editable mode
pip install -e .

# Run the app
marauder

# Run directly without installing
python -m marauder.app
```

No test suite exists yet. No linter or formatter is configured.

## Architecture

Three-layer event-driven architecture:

1. **SerialBridge** (`serial_bridge.py`) — Background thread reads serial port, parses Marauder firmware output with regex, emits frozen dataclass events (`APFound`, `StationFound`, `BLEDeviceFound`, `ScanStarted`, `ScanStopped`, `Disconnected`, `RawLine`). Thread-safe command sending.

2. **MarauderEngine** (`engine.py`) — Central state holder. Manages scan results with BSSID/MAC deduplication indices, activity log (deque of 200), session recording (JSONL to `~/.marauder-tui/sessions/`). Translates high-level actions (start_wifi_scan, attack_deauth, etc.) into Marauder CLI commands. Notifies TUI via registered callbacks.

3. **Textual TUI** (`app.py` + `screens/` + `widgets/`) — Tabbed interface (Dashboard, Attacks, Logs, Serial). Receives state updates via callbacks, uses `call_from_thread()` for thread-safe UI updates. Zero business logic.

Data flows: `SerialBridge → events → MarauderEngine → callbacks → TUI`

## Key Conventions

- **Serial port auto-detection** is macOS-centric: globs `/dev/cu.usbserial-*`. Cross-platform support would need extending this.
- **RSSI color thresholds**: >= -50 dBm green, -50 to -70 dBm yellow, < -70 dBm red. Used consistently across WiFiTable, BLETable, and RSSIBar.
- **All styling** is done via Textual CSS (no inline widget styling). Theme is green-on-black hacker aesthetic.
- **Confirmation dialogs** are required before any attack action.
- **Session format**: JSONL files with `{timestamp, event_type, ...event_fields}` per line. CSV export flattens these.
- **Hotkeys**: F1 (WiFi scan), F2 (BLE scan), F3 (stop scan), F4 (attacks tab), F5 (logs tab), Ctrl+Q (quit).

## Module Map

| Module | Role |
|--------|------|
| `engine.py` | State + command dispatch (~370 lines) |
| `serial_bridge.py` | Serial I/O + parsing (~434 lines) |
| `screens/dashboard.py` | Live WiFi/BLE tables + activity feed |
| `screens/attacks.py` | WiFi deauth/beacon/probe/rickroll + BLE spam UI |
| `screens/logs.py` | Session recording, listing, CSV export |
| `screens/serial_raw.py` | Raw serial terminal with manual input |
| `widgets/device_table.py` | WiFiTable and BLETable (DataTable subclasses) |
| `widgets/rssi_bar.py` | Unicode block-char signal bar (reactive) |
| `widgets/activity_feed.py` | Timestamped RichLog with color categories |
