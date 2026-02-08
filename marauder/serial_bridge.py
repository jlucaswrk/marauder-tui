"""Serial communication bridge for ESP32 Marauder firmware.

Connects via pyserial, reads Marauder text output in a background thread,
and parses lines into structured event dataclasses.
"""

from __future__ import annotations

import glob
import logging
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Union

import serial

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class APFound:
    """Access point discovered during ``scanap``."""

    ssid: str
    bssid: str
    channel: int
    rssi: int


@dataclass(frozen=True)
class StationFound:
    """Station discovered during ``scansta``."""

    mac: str
    rssi: int
    associated_bssid: str


@dataclass(frozen=True)
class BLEDeviceFound:
    """Bluetooth LE device discovered during ``sniffbt``."""

    name: str
    mac: str
    rssi: int


@dataclass(frozen=True)
class ScanStarted:
    """Emitted when a scan command is acknowledged by the device."""

    scan_type: str


@dataclass(frozen=True)
class ScanStopped:
    """Emitted when a scan is stopped (either by command or device)."""


@dataclass(frozen=True)
class Disconnected:
    """Emitted when the serial connection is lost."""

    reason: str = ""


@dataclass(frozen=True)
class RawLine:
    """Catch-all for any line that does not match a known pattern."""

    text: str


Event = Union[
    APFound,
    StationFound,
    BLEDeviceFound,
    ScanStarted,
    ScanStopped,
    Disconnected,
    RawLine,
]

# ---------------------------------------------------------------------------
# Regex patterns for Marauder output
# ---------------------------------------------------------------------------

# AP scan line:  -42 ESSID: MyNetwork Ch: 6 BSSID: AA:BB:CC:DD:EE:FF
_RE_AP = re.compile(
    r"^(-?\d+)\s+ESSID:\s*(.*?)\s+Ch:\s*(\d+)\s+BSSID:\s*"
    r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s*$"
)

# Station scan line:  -55 Station: AA:BB:CC:DD:EE:FF Associated: 11:22:33:44:55:66
_RE_STATION = re.compile(
    r"^(-?\d+)\s+Station:\s*([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})"
    r"\s+Associated:\s*([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s*$"
)

# BLE device with name:  -80 Device: [LG] webOS TV UP7550PSF
# BLE device without name:  -73 Device: 63:C6:BB:7B:D1:1C
_RE_BLE_NAMED = re.compile(
    r"^(-?\d+)\s+Device:\s*\[(.+?)\]\s*(.*?)\s*$"
)
_RE_BLE_MAC = re.compile(
    r"^(-?\d+)\s+Device:\s*([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s*$"
)

# Scan started indicators
_RE_SCAN_STARTED_WIFI = re.compile(r"Starting WiFi scan", re.IGNORECASE)
_RE_SCAN_STARTED_BT = re.compile(r"Starting Bluetooth scan", re.IGNORECASE)
_RE_SCAN_STARTED_AP = re.compile(r"Started AP Scan", re.IGNORECASE)

# Scan stopped indicators
_RE_SCAN_STOPPED = re.compile(
    r"(Shutting down BLE|Stopping WiFi|stopscan)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Default port detection
# ---------------------------------------------------------------------------

_MACOS_SERIAL_GLOB = "/dev/cu.usbserial-*"


def _auto_detect_port() -> str | None:
    """Return the first matching macOS USB-serial port, or ``None``."""
    ports = sorted(glob.glob(_MACOS_SERIAL_GLOB))
    if ports:
        logger.info("Auto-detected serial port: %s", ports[0])
        return ports[0]
    return None


# ---------------------------------------------------------------------------
# SerialBridge
# ---------------------------------------------------------------------------


class SerialBridge:
    """Manages a serial connection to an ESP32 running Marauder firmware.

    Parameters
    ----------
    baudrate:
        Serial baud rate. Marauder defaults to 115200.
    reconnect_delay:
        Seconds to wait before attempting reconnection after disconnect.
    raw_history_size:
        Maximum number of raw lines to keep in the history deque.
    """

    def __init__(
        self,
        baudrate: int = 115200,
        reconnect_delay: float = 3.0,
        raw_history_size: int = 500,
    ) -> None:
        self._baudrate: int = baudrate
        self._reconnect_delay: float = reconnect_delay

        self._port: str | None = None
        self._serial: serial.Serial | None = None
        self._running: bool = False
        self._reader_thread: threading.Thread | None = None

        self._callbacks: list[Callable[[Event], None]] = []
        self._callbacks_lock: threading.Lock = threading.Lock()

        self._write_lock: threading.Lock = threading.Lock()

        self.raw_lines: deque[str] = deque(maxlen=raw_history_size)

    # -- public API ---------------------------------------------------------

    @property
    def port(self) -> str | None:
        """The currently configured serial port path."""
        return self._port

    def on_event(self, callback: Callable[[Event], None]) -> None:
        """Register a *callback* that will receive every parsed event."""
        with self._callbacks_lock:
            self._callbacks.append(callback)

    def remove_event(self, callback: Callable[[Event], None]) -> None:
        """Remove a previously registered callback."""
        with self._callbacks_lock:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

    def connect(self, port: str | None = None) -> None:
        """Open the serial port and start the reader thread.

        Parameters
        ----------
        port:
            Explicit serial port path. If ``None``, auto-detection is attempted.

        Raises
        ------
        serial.SerialException
            If the port cannot be opened.
        RuntimeError
            If no port is found during auto-detection.
        """
        if self._running:
            logger.warning("Already connected — disconnect first.")
            return

        resolved_port = port or _auto_detect_port()
        if resolved_port is None:
            raise RuntimeError(
                "No serial port specified and auto-detection found nothing. "
                f"Looked for: {_MACOS_SERIAL_GLOB}"
            )

        self._port = resolved_port
        logger.info("Opening serial port %s @ %d baud", self._port, self._baudrate)
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=1.0,
        )

        self._running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="marauder-serial-reader",
            daemon=True,
        )
        self._reader_thread.start()

    def disconnect(self) -> None:
        """Stop the reader thread and close the serial port."""
        self._running = False
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=5.0)
            self._reader_thread = None
        self._close_serial()

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the serial port is open and the reader is running."""
        return self._running and self._serial is not None and self._serial.is_open

    def send_command(self, cmd: str) -> None:
        """Send a command string to the Marauder device.

        A newline is appended automatically. Thread-safe.

        Raises
        ------
        RuntimeError
            If the bridge is not connected.
        """
        with self._write_lock:
            if self._serial is None or not self._serial.is_open:
                raise RuntimeError("Serial port is not open.")
            payload = cmd if cmd.endswith("\n") else cmd + "\n"
            self._serial.write(payload.encode("utf-8", errors="replace"))
            self._serial.flush()
            logger.debug("TX >>> %s", cmd)

    # -- internal -----------------------------------------------------------

    def _emit(self, event: Event) -> None:
        """Dispatch *event* to all registered callbacks."""
        with self._callbacks_lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                logger.exception("Exception in event callback %r", cb)

    def _close_serial(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    def _reader_loop(self) -> None:
        """Background loop that reads lines and dispatches events."""
        buffer: str = ""

        while self._running:
            try:
                if self._serial is None or not self._serial.is_open:
                    raise serial.SerialException("Port closed")

                raw: bytes = self._serial.read(self._serial.in_waiting or 1)
                if not raw:
                    continue

                buffer += raw.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.rstrip("\r")
                    self._handle_line(line)

            except (serial.SerialException, OSError) as exc:
                if not self._running:
                    break
                logger.warning("Serial error: %s", exc)
                self._close_serial()
                self._emit(Disconnected(reason=str(exc)))
                self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        """Try to reopen the same port until success or shutdown."""
        while self._running:
            time.sleep(self._reconnect_delay)
            if not self._running:
                return
            port = self._port or _auto_detect_port()
            if port is None:
                logger.debug("Reconnect: no port found, retrying...")
                continue
            try:
                logger.info("Reconnecting to %s ...", port)
                self._serial = serial.Serial(
                    port=port,
                    baudrate=self._baudrate,
                    timeout=1.0,
                )
                self._port = port
                logger.info("Reconnected to %s", port)
                return
            except (serial.SerialException, OSError) as exc:
                logger.debug("Reconnect failed: %s", exc)

    def _handle_line(self, line: str) -> None:
        """Parse a single line and emit the corresponding event."""
        self.raw_lines.append(line)

        if not line.strip():
            return

        # --- AP scan line ---
        m = _RE_AP.match(line)
        if m:
            self._emit(
                APFound(
                    rssi=int(m.group(1)),
                    ssid=m.group(2),
                    channel=int(m.group(3)),
                    bssid=m.group(4).upper(),
                )
            )
            return

        # --- Station scan line ---
        m = _RE_STATION.match(line)
        if m:
            self._emit(
                StationFound(
                    rssi=int(m.group(1)),
                    mac=m.group(2).upper(),
                    associated_bssid=m.group(3).upper(),
                )
            )
            return

        # --- BLE device (named) ---
        m = _RE_BLE_NAMED.match(line)
        if m:
            brand = m.group(2).strip()
            model = m.group(3).strip()
            name = f"[{brand}] {model}" if model else f"[{brand}]"
            self._emit(
                BLEDeviceFound(
                    rssi=int(m.group(1)),
                    name=name,
                    mac="",
                )
            )
            return

        # --- BLE device (MAC only) ---
        m = _RE_BLE_MAC.match(line)
        if m:
            self._emit(
                BLEDeviceFound(
                    rssi=int(m.group(1)),
                    name="",
                    mac=m.group(2).upper(),
                )
            )
            return

        # --- Scan started ---
        if _RE_SCAN_STARTED_WIFI.search(line):
            self._emit(ScanStarted(scan_type="wifi"))
            return
        if _RE_SCAN_STARTED_BT.search(line):
            self._emit(ScanStarted(scan_type="bluetooth"))
            return
        if _RE_SCAN_STARTED_AP.search(line):
            self._emit(ScanStarted(scan_type="ap"))
            return

        # --- Scan stopped ---
        if _RE_SCAN_STOPPED.search(line):
            self._emit(ScanStopped())
            return

        # --- Fallback ---
        self._emit(RawLine(text=line))
