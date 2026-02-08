"""MarauderEngine — state management and logic layer for the Marauder TUI.

Sits between the SerialBridge (serial I/O) and the Textual TUI, holding all
scan results, managing sessions, and translating high-level actions into
Marauder CLI commands.
"""

from __future__ import annotations

import csv
import io
import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from marauder.serial_bridge import (
    APFound,
    BLEDeviceFound,
    Disconnected,
    RawLine,
    ScanStarted,
    ScanStopped,
    SerialBridge,
    StationFound,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_SESSIONS_DIR: Path = Path.home() / ".marauder-tui" / "sessions"
_ACTIVITY_LOG_MAX: int = 200


class MarauderEngine:
    """Central state holder and command dispatcher for the Marauder TUI."""

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, bridge: SerialBridge) -> None:
        self._bridge: SerialBridge = bridge

        # Scan results
        self.aps: list[APFound] = []
        self.stations: list[StationFound] = []
        self.ble_devices: list[BLEDeviceFound] = []

        # Indices for fast dedup lookups
        self._ap_index: dict[str, int] = {}        # bssid -> list index
        self._sta_index: dict[str, int] = {}        # mac   -> list index
        self._ble_index: dict[str, int] = {}        # mac   -> list index

        # Activity log (human-readable feed)
        self.activity_log: deque[tuple[datetime, str]] = deque(maxlen=_ACTIVITY_LOG_MAX)

        # Scan state
        self.current_scan: str | None = None
        self.is_connected: bool = False

        # Session recording
        self._session_file: io.TextIOWrapper | None = None
        self._session_path: Path | None = None

        # Callbacks registered by the TUI
        self._state_callbacks: list[Callable[[str, Any], None]] = []

        # Register ourselves as the event handler for the bridge
        self._bridge.on_event(self._handle_event)

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def on_state_change(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback invoked on state changes. Receives (event_type, data)."""
        self._state_callbacks.append(callback)

    def _notify(self, event_type: str = "update", data: Any = None) -> None:
        """Call every registered state-change callback with event info."""
        for cb in self._state_callbacks:
            cb(event_type, data)

    # ------------------------------------------------------------------
    # Activity log helpers
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        """Append a timestamped message to the activity log."""
        now = datetime.now()
        self.activity_log.append((now, message))

    # ------------------------------------------------------------------
    # Event handling (called by the SerialBridge)
    # ------------------------------------------------------------------

    def _handle_event(self, event: Any) -> None:  # noqa: ANN401
        """Dispatch an event emitted by the SerialBridge."""
        if isinstance(event, APFound):
            self._on_ap_found(event)
        elif isinstance(event, StationFound):
            self._on_station_found(event)
        elif isinstance(event, BLEDeviceFound):
            self._on_ble_device_found(event)
        elif isinstance(event, ScanStarted):
            self._on_scan_started(event)
        elif isinstance(event, ScanStopped):
            self._on_scan_stopped()
        elif isinstance(event, RawLine):
            self._on_raw_line(event)
        elif isinstance(event, Disconnected):
            self._on_disconnected()

        # Session recording
        self._record_event(event)

        # Notify the TUI
        self._notify()

    # -- individual event handlers --

    def _on_ap_found(self, event: APFound) -> None:
        bssid = event.bssid
        if bssid in self._ap_index:
            idx = self._ap_index[bssid]
            self.aps[idx] = event
        else:
            self._ap_index[bssid] = len(self.aps)
            self.aps.append(event)
        msg = f"Found AP: {event.ssid} ch{event.channel} {event.rssi}dBm"
        self._log(msg)
        self._notify("activity", ("WiFi", msg))

    def _on_station_found(self, event: StationFound) -> None:
        mac = event.mac
        if mac in self._sta_index:
            idx = self._sta_index[mac]
            self.stations[idx] = event
        else:
            self._sta_index[mac] = len(self.stations)
            self.stations.append(event)
        msg = f"Station: {mac} {event.rssi}dBm -> {event.associated_bssid}"
        self._log(msg)
        self._notify("activity", ("WiFi", msg))

    def _on_ble_device_found(self, event: BLEDeviceFound) -> None:
        mac = event.mac
        if mac in self._ble_index:
            idx = self._ble_index[mac]
            self.ble_devices[idx] = event
        else:
            self._ble_index[mac] = len(self.ble_devices)
            self.ble_devices.append(event)
        name = event.name or mac
        msg = f"Device: {name} {event.rssi}dBm"
        self._log(msg)
        self._notify("activity", ("BLE", msg))

    def _on_scan_started(self, event: ScanStarted) -> None:
        self.current_scan = event.scan_type
        self._log(f"Scan started: {event.scan_type}")

    def _on_scan_stopped(self) -> None:
        prev = self.current_scan
        self.current_scan = None
        self._log(f"Scan stopped (was: {prev})")

    def _on_raw_line(self, event: RawLine) -> None:
        self._notify("raw_line", event.text)

    def _on_disconnected(self) -> None:
        self.is_connected = False
        self.current_scan = None
        self._log("Device disconnected")

    # ------------------------------------------------------------------
    # Scan commands
    # ------------------------------------------------------------------

    def start_wifi_scan(self) -> None:
        """Start a WiFi access-point scan (``scanap``)."""
        self._bridge.send_command("scanap")
        self.current_scan = "wifi_ap"
        self._log("Requested WiFi AP scan")
        self._notify()

    def start_station_scan(self) -> None:
        """Start a WiFi station scan (``scansta``)."""
        self._bridge.send_command("scansta")
        self.current_scan = "wifi_sta"
        self._log("Requested WiFi station scan")
        self._notify()

    def start_ble_scan(self) -> None:
        """Start a BLE device scan (``sniffbt``)."""
        self._bridge.send_command("sniffbt")
        self.current_scan = "ble"
        self._log("Requested BLE scan")
        self._notify()

    def stop_scan(self) -> None:
        """Stop whatever scan is currently running (``stopscan``)."""
        self._bridge.send_command("stopscan")
        self._log("Requested scan stop")
        self._notify()

    # ------------------------------------------------------------------
    # Result management
    # ------------------------------------------------------------------

    def clear_results(self) -> None:
        """Wipe all collected scan results."""
        self.aps.clear()
        self.stations.clear()
        self.ble_devices.clear()
        self._ap_index.clear()
        self._sta_index.clear()
        self._ble_index.clear()
        self._log("Results cleared")
        self._notify()

    # ------------------------------------------------------------------
    # Attack commands
    # ------------------------------------------------------------------

    def attack_deauth(self, ap_index: int) -> None:
        """Select an AP by *ap_index* and launch a deauth attack."""
        if ap_index < 0 or ap_index >= len(self.aps):
            self._log(f"Invalid AP index: {ap_index}")
            self._notify()
            return
        ap = self.aps[ap_index]
        self._bridge.send_command(f"select -a {ap_index}")
        self._bridge.send_command("attack -t deauth")
        self.current_scan = "attack_deauth"
        self._log(f"Deauth attack on AP {ap.ssid} ({ap.bssid})")
        self._notify()

    def attack_beacon_flood(self) -> None:
        """Launch a random beacon flood attack."""
        self._bridge.send_command("attack -t beacon -r")
        self.current_scan = "attack_beacon"
        self._log("Beacon flood attack started")
        self._notify()

    def attack_rickroll(self) -> None:
        """Launch the rickroll beacon attack."""
        self._bridge.send_command("attack -t rickroll")
        self.current_scan = "attack_rickroll"
        self._log("Rickroll beacon attack started")
        self._notify()

    def ble_spam(self, target: str) -> None:
        """Launch BLE spam attack against *target*.

        Parameters
        ----------
        target:
            One of ``"apple"``, ``"samsung"``, ``"google"``, ``"windows"``,
            ``"flipper"``, or ``"all"``.
        """
        valid_targets = {"apple", "samsung", "google", "windows", "flipper", "all"}
        if target not in valid_targets:
            self._log(f"Invalid BLE spam target: {target!r} (valid: {valid_targets})")
            self._notify()
            return
        self._bridge.send_command(f"blespam -t {target}")
        self.current_scan = f"ble_spam_{target}"
        self._log(f"BLE spam started (target={target})")
        self._notify()

    # ------------------------------------------------------------------
    # Session recording
    # ------------------------------------------------------------------

    def start_session(self) -> Path:
        """Begin recording events to a JSONL file.

        Returns the path of the new session file.
        """
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = _SESSIONS_DIR / f"{stamp}.jsonl"
        self._session_path = path
        self._session_file = open(path, "a", encoding="utf-8")  # noqa: SIM115
        self._log(f"Session recording started: {path.name}")
        self._notify()
        return path

    def stop_session(self) -> None:
        """Stop recording and close the session file."""
        if self._session_file is not None:
            self._session_file.close()
            self._session_file = None
            name = self._session_path.name if self._session_path else "unknown"
            self._session_path = None
            self._log(f"Session recording stopped: {name}")
            self._notify()

    @property
    def is_recording(self) -> bool:
        """Whether a session is currently being recorded."""
        return self._session_file is not None

    def _record_event(self, event: Any) -> None:  # noqa: ANN401
        """Append an event as a JSON line to the active session file."""
        if self._session_file is None:
            return
        record: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "event_type": type(event).__name__,
        }
        # Serialise dataclass fields
        if hasattr(event, "__dataclass_fields__"):
            for field_name in event.__dataclass_fields__:
                record[field_name] = getattr(event, field_name)
        self._session_file.write(json.dumps(record) + "\n")
        self._session_file.flush()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def list_sessions(self) -> list[Path]:
        """Return a sorted list of past session JSONL files."""
        if not _SESSIONS_DIR.exists():
            return []
        return sorted(_SESSIONS_DIR.glob("*.jsonl"), reverse=True)

    @staticmethod
    def export_session_csv(session_path: Path) -> str:
        """Convert a JSONL session file to CSV and return the CSV text.

        The CSV is also written alongside the original file with a ``.csv``
        extension.
        """
        rows: list[dict[str, Any]] = []
        fieldnames_set: set[str] = set()

        with open(session_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record: dict[str, Any] = json.loads(line)
                rows.append(record)
                fieldnames_set.update(record.keys())

        # Deterministic column order: timestamp first, then event_type, rest sorted
        priority = ["timestamp", "event_type"]
        fieldnames: list[str] = [f for f in priority if f in fieldnames_set]
        fieldnames += sorted(fieldnames_set - set(priority))

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        csv_text = output.getvalue()

        # Write CSV file next to the JSONL
        csv_path = session_path.with_suffix(".csv")
        csv_path.write_text(csv_text, encoding="utf-8")

        return csv_text
