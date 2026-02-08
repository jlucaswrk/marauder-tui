"""Styled DataTable subclasses for WiFi AP and BLE device listings."""
from __future__ import annotations

from typing import Any, Sequence

from rich.text import Text
from textual.widgets import DataTable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rssi_color(rssi: int) -> str:
    """Return a Rich color name based on RSSI signal strength.

    >= -50 dBm  -> green  (strong)
    -50 to -70  -> yellow (moderate)
    < -70 dBm   -> red    (weak)
    """
    if rssi >= -50:
        return "green"
    if rssi >= -70:
        return "yellow"
    return "red"


def _styled_rssi(rssi: int) -> Text:
    """Return a Rich Text object for an RSSI value with color coding."""
    color: str = _rssi_color(rssi)
    return Text(f"{rssi} dBm", style=f"bold {color}")


# ---------------------------------------------------------------------------
# WiFiTable
# ---------------------------------------------------------------------------

class WiFiTable(DataTable):
    """DataTable for WiFi access-point scan results.

    Columns: RSSI | SSID | BSSID | Channel

    Call :meth:`update_devices` with a sequence of objects that expose at
    least ``.rssi``, ``.ssid``, ``.bssid``, and ``.channel`` attributes
    (duck-typed).
    """

    DEFAULT_CSS = """
    WiFiTable {
        height: 1fr;
        border: solid #00ff00;
        scrollbar-color: #00ff00;
        scrollbar-color-active: #00ff00;
        scrollbar-color-hover: #33ff33;
    }

    WiFiTable > .datatable--header {
        background: #001a00;
        color: #00aa00;
        text-style: dim bold;
    }

    WiFiTable > .datatable--cursor {
        background: #003300;
        color: #00ff00;
    }

    WiFiTable > .datatable--header-cursor {
        background: #003300;
        color: #00ff00;
    }

    WiFiTable > .datatable--even-row {
        background: #000a00;
    }

    WiFiTable > .datatable--odd-row {
        background: #000000;
    }
    """

    def on_mount(self) -> None:
        """Set up columns when the widget is mounted."""
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("RSSI", "SSID", "BSSID", "Channel")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_devices(self, devices: Sequence[Any]) -> None:
        """Clear the table and repopulate from *devices*.

        Each element is expected to have ``.rssi`` (int), ``.ssid`` (str),
        ``.bssid`` (str), and ``.channel`` (int) attributes.  Rows are
        sorted by RSSI descending (strongest signal first).
        """
        self.clear()

        # Sort strongest signal first.
        sorted_devices = sorted(devices, key=lambda d: d.rssi, reverse=True)

        for dev in sorted_devices:
            rssi: int = int(dev.rssi)
            ssid: str = str(getattr(dev, "ssid", ""))
            bssid: str = str(getattr(dev, "bssid", ""))
            channel: str = str(getattr(dev, "channel", ""))
            self.add_row(
                _styled_rssi(rssi),
                Text(ssid, style="bold #00ff00"),
                Text(bssid, style="#00cc00"),
                Text(channel, style="#00cc00"),
            )


# ---------------------------------------------------------------------------
# BLETable
# ---------------------------------------------------------------------------

class BLETable(DataTable):
    """DataTable for BLE device scan results.

    Columns: RSSI | Name | MAC Address

    Call :meth:`update_devices` with a sequence of objects that expose at
    least ``.rssi``, ``.name``, and ``.mac`` attributes (duck-typed).
    """

    DEFAULT_CSS = """
    BLETable {
        height: 1fr;
        border: solid #00ccff;
        scrollbar-color: #00ccff;
        scrollbar-color-active: #00ccff;
        scrollbar-color-hover: #33ddff;
    }

    BLETable > .datatable--header {
        background: #001a1a;
        color: #00aacc;
        text-style: dim bold;
    }

    BLETable > .datatable--cursor {
        background: #003333;
        color: #00ccff;
    }

    BLETable > .datatable--header-cursor {
        background: #003333;
        color: #00ccff;
    }

    BLETable > .datatable--even-row {
        background: #000a0a;
    }

    BLETable > .datatable--odd-row {
        background: #000000;
    }
    """

    def on_mount(self) -> None:
        """Set up columns when the widget is mounted."""
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("RSSI", "Name", "MAC Address")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_devices(self, devices: Sequence[Any]) -> None:
        """Clear the table and repopulate from *devices*.

        Each element is expected to have ``.rssi`` (int), ``.name`` (str),
        and ``.mac`` (str) attributes.  Rows are sorted by RSSI descending
        (strongest signal first).
        """
        self.clear()

        sorted_devices = sorted(devices, key=lambda d: d.rssi, reverse=True)

        for dev in sorted_devices:
            rssi: int = int(dev.rssi)
            name: str = str(getattr(dev, "name", "Unknown"))
            mac: str = str(getattr(dev, "mac", ""))
            self.add_row(
                _styled_rssi(rssi),
                Text(name, style="bold #00ccff"),
                Text(mac, style="#00aacc"),
            )
