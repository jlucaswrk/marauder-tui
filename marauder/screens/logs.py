"""Session logging screen -- recording control and session file browser.

Provides start/stop controls for session recording, a scrollable list of
past session files, and CSV export.  Intended for use inside a ``TabPane``.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Label, ListItem, ListView, Static

from marauder.engine import MarauderEngine


class LogsPanel(Widget):
    """Session recording and history panel.

    Call :meth:`set_engine` to bind to a :class:`MarauderEngine` and
    :meth:`refresh_sessions` to reload the file listing.
    """

    DEFAULT_CSS = """
    LogsPanel {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: #000000;
    }

    LogsPanel #logs-header {
        dock: top;
        width: 100%;
        height: 3;
        background: #001a00;
        color: #00ff00;
        text-style: bold;
        padding: 1 2;
        border-bottom: solid #004400;
    }

    LogsPanel #rec-controls {
        width: 100%;
        height: auto;
        padding: 1 2;
        background: #000a00;
        border-bottom: solid #003300;
    }

    LogsPanel #rec-controls-row {
        width: 100%;
        height: 3;
        align-vertical: middle;
    }

    LogsPanel #rec-status {
        width: auto;
        min-width: 30;
        height: 1;
        color: #00ff00;
        text-style: bold;
        margin-left: 2;
        margin-top: 1;
    }

    LogsPanel #btn-rec-start {
        background: #003300;
        color: #00ff00;
        border: solid #00ff00;
        text-style: bold;
        min-width: 20;
        margin-right: 1;
    }

    LogsPanel #btn-rec-start:hover {
        background: #005500;
    }

    LogsPanel #btn-rec-stop {
        background: #330000;
        color: #ff4444;
        border: solid #ff0000;
        text-style: bold;
        min-width: 20;
        margin-right: 1;
    }

    LogsPanel #btn-rec-stop:hover {
        background: #550000;
    }

    LogsPanel #sessions-section {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    LogsPanel #sessions-title {
        width: 100%;
        height: 1;
        color: #00ff00;
        text-style: bold;
        margin-bottom: 1;
    }

    LogsPanel #sessions-list {
        width: 100%;
        height: 1fr;
        background: #000a00;
        color: #00cc00;
        border: solid #003300;
    }

    LogsPanel #sessions-list ListItem {
        color: #00cc00;
        background: #000000;
        padding: 0 1;
    }

    LogsPanel #sessions-list ListItem:hover {
        background: #001a00;
    }

    LogsPanel #export-bar {
        dock: bottom;
        width: 100%;
        height: 3;
        padding: 0 2;
        background: #000a00;
        border-top: solid #003300;
        align-vertical: middle;
    }

    LogsPanel #btn-export-csv {
        background: #002200;
        color: #00ff00;
        border: solid #00aa00;
        text-style: bold;
        min-width: 22;
        margin-top: 0;
        margin-right: 1;
    }

    LogsPanel #btn-export-csv:hover {
        background: #004400;
    }

    LogsPanel #btn-refresh-list {
        background: #001a00;
        color: #00ff00;
        border: solid #006600;
        text-style: bold;
        min-width: 16;
        margin-top: 0;
    }

    LogsPanel #btn-refresh-list:hover {
        background: #003300;
    }

    LogsPanel #export-status {
        width: auto;
        height: 1;
        color: #00cc00;
        margin-left: 2;
        margin-top: 1;
    }

    LogsPanel .separator-line {
        width: 100%;
        height: 1;
        color: #003300;
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
        self._engine: MarauderEngine | None = None
        self._sessions: list[Path] = []
        self._selected_index: int | None = None

    # ------------------------------------------------------------------
    # Engine link
    # ------------------------------------------------------------------

    def set_engine(self, engine: MarauderEngine) -> None:
        """Bind the panel to *engine*."""
        self._engine = engine

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(
            "[b]//////  SESSION LOGGER  //////[/b]\n"
            "[#00cc00]Record, review, and export session data.[/]",
            id="logs-header",
        )

        with Vertical(id="rec-controls"):
            with Horizontal(id="rec-controls-row"):
                yield Button("[ REC START ]", id="btn-rec-start")
                yield Button("[ REC STOP ]", id="btn-rec-stop")
                yield Static(
                    "[#666666]REC: STOPPED[/]",
                    id="rec-status",
                )

        with VerticalScroll(id="sessions-section"):
            yield Static("[#00ff00]> Saved Sessions[/]", id="sessions-title")
            yield ListView(id="sessions-list")

        with Horizontal(id="export-bar"):
            yield Button("[ EXPORT AS CSV ]", id="btn-export-csv")
            yield Button("[ REFRESH ]", id="btn-refresh-list")
            yield Static("", id="export-status")

    # ------------------------------------------------------------------
    # Session list
    # ------------------------------------------------------------------

    def refresh_sessions(self) -> None:
        """Reload the session file listing from engine."""
        if self._engine is None:
            return
        self._sessions = self._engine.list_sessions()
        self._selected_index = None
        try:
            lv = self.query_one("#sessions-list", ListView)
            lv.clear()
            if not self._sessions:
                lv.append(ListItem(Label("[#666666]-- no sessions found --[/]")))
            else:
                for idx, path in enumerate(self._sessions):
                    stat = path.stat()
                    size_kb = stat.st_size / 1024
                    name = path.name
                    info = f"[{idx}] {name}  ({size_kb:.1f} KB)"
                    lv.append(ListItem(Label(info), id=f"sess-{idx}"))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        # Populate the list once mounted (engine may not be set yet).
        self.call_later(self.refresh_sessions)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-rec-start":
            self._start_recording()
        elif btn_id == "btn-rec-stop":
            self._stop_recording()
        elif btn_id == "btn-export-csv":
            self._export_selected()
        elif btn_id == "btn-refresh-list":
            self.refresh_sessions()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id: str | None = event.item.id
        if item_id and item_id.startswith("sess-"):
            self._selected_index = int(item_id.removeprefix("sess-"))
            path = self._sessions[self._selected_index]
            self._set_export_status(f"Selected: {path.name}")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _start_recording(self) -> None:
        if self._engine is None:
            self._set_rec_status("[#ff4444]Engine not connected[/]")
            return
        if self._engine.is_recording:
            self._set_rec_status("[#ffaa00]Already recording![/]")
            return
        path = self._engine.start_session()
        self._set_rec_status(f"[#ff0000]REC: RECORDING[/]  [#00cc00]{path.name}[/]")

    def _stop_recording(self) -> None:
        if self._engine is None:
            return
        if not self._engine.is_recording:
            self._set_rec_status("[#666666]REC: STOPPED[/]")
            return
        self._engine.stop_session()
        self._set_rec_status("[#666666]REC: STOPPED[/]")
        self.refresh_sessions()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_selected(self) -> None:
        if self._selected_index is None or self._selected_index >= len(self._sessions):
            self._set_export_status("[#ffaa00]Select a session first.[/]")
            return
        path = self._sessions[self._selected_index]
        try:
            MarauderEngine.export_session_csv(path)
            csv_path = path.with_suffix(".csv")
            self._set_export_status(f"[#00ff00]Exported: {csv_path.name}[/]")
        except Exception as exc:
            self._set_export_status(f"[#ff4444]Export error: {exc}[/]")

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _set_rec_status(self, text: str) -> None:
        try:
            self.query_one("#rec-status", Static).update(text)
        except Exception:
            pass

    def _set_export_status(self, text: str) -> None:
        try:
            self.query_one("#export-status", Static).update(text)
        except Exception:
            pass
