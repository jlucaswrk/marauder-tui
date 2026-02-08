"""Dashboard screen -- main overview with WiFi table, BLE table, and activity feed.

This widget is designed to be mounted inside a ``TabPane``, not used as a
standalone ``Screen``.  It composes the three primary data-display widgets
into a split layout: two device tables on top and a live activity feed on
the bottom.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from marauder.engine import MarauderEngine
from marauder.widgets.activity_feed import ActivityFeed
from marauder.widgets.device_table import BLETable, WiFiTable


class _SectionHeader(Static):
    """Tiny styled header label for a panel section."""

    DEFAULT_CSS = """
    _SectionHeader {
        width: 100%;
        height: 1;
        background: #003300;
        color: #00ff00;
        text-style: bold;
        padding: 0 1;
    }
    """


class Dashboard(Widget):
    """Main dashboard panel displaying scan results and live activity.

    Mount this inside a ``TabPane``.  Call :meth:`refresh_data` with a
    :class:`MarauderEngine` instance to push the latest state into all
    child widgets.
    """

    DEFAULT_CSS = """
    Dashboard {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: #000000;
    }

    Dashboard #tables-row {
        height: 1fr;
        min-height: 10;
    }

    Dashboard #wifi-panel {
        width: 1fr;
        height: 100%;
        border: solid #00ff00;
        background: #000000;
    }

    Dashboard #ble-panel {
        width: 1fr;
        height: 100%;
        border: solid #00ff00;
        background: #000000;
    }

    Dashboard #feed-panel {
        height: 1fr;
        min-height: 6;
        border: solid #004400;
        background: #000000;
    }

    Dashboard WiFiTable {
        height: 1fr;
        background: #000000;
        color: #00ff00;
    }

    Dashboard BLETable {
        height: 1fr;
        background: #000000;
        color: #00ff00;
    }

    Dashboard ActivityFeed {
        height: 1fr;
        background: #000000;
        color: #00cc00;
    }

    Dashboard #scan-status {
        dock: top;
        width: 100%;
        height: 1;
        background: #001a00;
        color: #00ff00;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._wifi_table: WiFiTable | None = None
        self._ble_table: BLETable | None = None
        self._activity_feed: ActivityFeed | None = None
        self._status_bar: Static | None = None

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(
            "[b][ MARAUDER DASHBOARD ][/b]  --  "
            "Waiting for data...",
            id="scan-status",
        )
        with Horizontal(id="tables-row"):
            with Vertical(id="wifi-panel"):
                yield _SectionHeader("[#00ff00]> WiFi Access Points[/]")
                yield WiFiTable(id="wifi-table")
            with Vertical(id="ble-panel"):
                yield _SectionHeader("[#00ff00]> BLE Devices[/]")
                yield BLETable(id="ble-table")
        with Vertical(id="feed-panel"):
            yield _SectionHeader("[#00cc00]> Activity Feed[/]")
            yield ActivityFeed(id="activity-feed")

    # ------------------------------------------------------------------
    # Post-mount wiring
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._wifi_table = self.query_one("#wifi-table", WiFiTable)
        self._ble_table = self.query_one("#ble-table", BLETable)
        self._activity_feed = self.query_one("#activity-feed", ActivityFeed)
        self._status_bar = self.query_one("#scan-status", Static)

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def refresh_data(self, engine: MarauderEngine) -> None:
        """Pull the latest data from *engine* and update all child widgets."""
        if self._wifi_table is not None:
            self._wifi_table.update_devices(engine.aps)

        if self._ble_table is not None:
            self._ble_table.update_devices(engine.ble_devices)

        if self._activity_feed is not None:
            # Push any new log entries.  We write them all; the feed's
            # RichLog will handle dedup / scrollback internally.
            for _ts, msg in engine.activity_log:
                self._activity_feed.add_entry("SYS", msg)

        # Status bar
        if self._status_bar is not None:
            conn = "[#00ff00]ONLINE[/]" if engine.is_connected else "[#ff0000]OFFLINE[/]"
            scan = engine.current_scan or "idle"
            aps = len(engine.aps)
            ble = len(engine.ble_devices)
            sta = len(engine.stations)
            self._status_bar.update(
                f"[b][ MARAUDER ][/b]  "
                f"Link: {conn}  |  "
                f"Scan: [#00ff00]{scan}[/]  |  "
                f"APs: [#00ff00]{aps}[/]  "
                f"STAs: [#00ff00]{sta}[/]  "
                f"BLE: [#00ff00]{ble}[/]"
            )
