"""Marauder TUI — Main application."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Header, TabbedContent, TabPane, Static

from marauder.serial_bridge import SerialBridge
from marauder.engine import MarauderEngine
from marauder.screens.dashboard import Dashboard
from marauder.screens.attacks import AttacksPanel
from marauder.screens.logs import LogsPanel
from marauder.screens.serial_raw import SerialTerminal

BANNER = r"""[green]
  ╔══════════════════════════════════════════════╗
  ║  ███╗   ███╗ █████╗ ██████╗  █████╗ ██╗   ██║
  ║  ████╗ ████║██╔══██╗██╔══██╗██╔══██╗██║   ██║
  ║  ██╔████╔██║███████║██████╔╝███████║██║   ██║
  ║  ██║╚██╔╝██║██╔══██║██╔══██╗██╔══██║██║   ██║
  ║  ██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██║╚██████║
  ║  ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════║
  ╠══════════════════════════════════════════════╣
  ║        ESP32 Marauder TUI  v0.1.0           ║
  ╚══════════════════════════════════════════════╝
[/green]"""


class MarauderApp(App):
    """ESP32 Marauder terminal UI."""

    TITLE = "Marauder TUI"
    SUB_TITLE = "ESP32 Hacking Toolkit"

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        background: #001100;
        color: #00ff00;
    }

    Footer {
        background: #001100;
        color: #00ff41;
    }

    TabbedContent {
        height: 1fr;
        background: #000000;
    }

    ContentSwitcher {
        height: 1fr;
        background: #000000;
    }

    TabPane {
        height: 1fr;
        background: #000000;
        padding: 0;
    }

    Tabs {
        background: #001100;
    }

    Tab {
        color: #00ff41;
        background: #001100;
    }

    Tab.-active {
        color: #000000;
        background: #00ff41;
    }

    Tab:hover {
        color: #000000;
        background: #00aa2a;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: #001100;
        color: #00ff41;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("f1", "wifi_scan", "Scan WiFi", show=True),
        Binding("f2", "ble_scan", "Scan BLE", show=True),
        Binding("f3", "stop_scan", "Stop", show=True),
        Binding("f4", "focus_attacks", "Attacks", show=True),
        Binding("f5", "toggle_session", "Log", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.bridge = SerialBridge()
        self.engine = MarauderEngine(self.bridge)
        self._session_active = False
        self._thread_id: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent("Dashboard", "Attacks", "Logs", "Serial"):
            with TabPane("Dashboard", id="tab-dashboard"):
                yield Dashboard(id="dashboard")
            with TabPane("Attacks", id="tab-attacks"):
                yield AttacksPanel(id="attacks")
            with TabPane("Logs", id="tab-logs"):
                yield LogsPanel(id="logs")
            with TabPane("Serial", id="tab-serial"):
                yield SerialTerminal(id="serial-raw")
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        import threading
        self._thread_id = threading.get_ident()
        self._dashboard = self.query_one("#dashboard", Dashboard)
        self._attacks = self.query_one("#attacks", AttacksPanel)
        self._logs = self.query_one("#logs", LogsPanel)
        self._serial = self.query_one("#serial-raw", SerialTerminal)

        self._attacks.set_engine(self.engine)
        self._logs.set_engine(self.engine)
        self._serial.set_engine(self.engine)

        self.engine.on_state_change(self._on_engine_update)
        self._set_status(" [yellow]Connecting to ESP32...[/yellow]")
        self.run_worker(self._try_connect, thread=True)

    def _try_connect(self) -> None:
        """Attempt to connect to ESP32 (runs in worker thread)."""
        try:
            self.bridge.connect()
            self.call_from_thread(self._on_connected)
        except Exception as e:
            self.call_from_thread(self._on_connect_failed, str(e))

    def _on_connected(self) -> None:
        self.engine.is_connected = True
        self._update_status()

    def _on_connect_failed(self, error: str) -> None:
        self.engine.is_connected = False
        self._set_status(f"[red]No device found: {error}[/red]")

    def _on_engine_update(self, event_type: str, data: object) -> None:
        """Called by engine on state changes (may be from serial or main thread)."""
        import threading
        if self._thread_id == threading.get_ident():
            self._apply_update(event_type, data)
        else:
            self.call_from_thread(self._apply_update, event_type, data)

    def _apply_update(self, event_type: str, data: object) -> None:
        """Apply engine update on the main thread."""
        self._dashboard.refresh_data(self.engine)
        self._update_status()

        if event_type == "activity" and isinstance(data, tuple):
            category, message = data
            try:
                feed = self._dashboard.query_one("#activity-feed")
                feed.add_entry(category, message)
            except Exception:
                pass

        if event_type == "raw_line":
            self._serial.add_line(str(data))

    def _update_status(self) -> None:
        scan = self.engine.current_scan or "idle"
        conn = "[green]● CONNECTED[/green]" if self.engine.is_connected else "[red]● DISCONNECTED[/red]"
        port = self.bridge.port or "no port"
        aps = len(self.engine.aps)
        ble = len(self.engine.ble_devices)
        session = " [yellow]● REC[/yellow]" if self._session_active else ""
        self._set_status(
            f" {conn}  {port}  │  scan: {scan}  │  APs: {aps}  BLE: {ble}{session}"
        )

    def _set_status(self, text: str) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
            bar.update(text)
        except Exception:
            pass

    def action_wifi_scan(self) -> None:
        self.engine.start_wifi_scan()

    def action_ble_scan(self) -> None:
        self.engine.start_ble_scan()

    def action_stop_scan(self) -> None:
        self.engine.stop_scan()

    def action_focus_attacks(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-attacks"

    def action_toggle_session(self) -> None:
        if self._session_active:
            self.engine.stop_session()
            self._session_active = False
        else:
            self.engine.start_session()
            self._session_active = True
        self._update_status()

    def on_unmount(self) -> None:
        if self._session_active:
            self.engine.stop_session()
        self.bridge.disconnect()


def run() -> None:
    app = MarauderApp()
    app.run()


if __name__ == "__main__":
    run()
