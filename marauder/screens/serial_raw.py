"""Raw serial terminal screen -- direct communication with the ESP32 Marauder.

Presents a full-screen terminal log of every line received from the serial
bridge, plus an input field for sending arbitrary commands.  Intended for
use inside a ``TabPane``.
"""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Input, RichLog, Static

from marauder.engine import MarauderEngine


class SerialTerminal(Widget):
    """Raw serial monitor with manual command entry.

    Call :meth:`set_engine` to bind to a :class:`MarauderEngine` and
    :meth:`add_line` to append incoming serial text.
    """

    DEFAULT_CSS = """
    SerialTerminal {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: #000000;
    }

    SerialTerminal #serial-header {
        dock: top;
        width: 100%;
        height: 1;
        background: #001a00;
        color: #00ff00;
        text-style: bold;
        padding: 0 1;
        border-bottom: solid #003300;
    }

    SerialTerminal #serial-log {
        width: 100%;
        height: 1fr;
        background: #000000;
        color: #00ff00;
        border: solid #003300;
        scrollbar-color: #00ff00;
        scrollbar-background: #001a00;
    }

    SerialTerminal #input-row {
        dock: bottom;
        width: 100%;
        height: 3;
        background: #000a00;
        border-top: solid #004400;
        padding: 0 1;
    }

    SerialTerminal #serial-prompt {
        width: 4;
        height: 1;
        color: #00ff00;
        text-style: bold;
        margin-top: 1;
    }

    SerialTerminal #serial-input {
        width: 1fr;
        height: 3;
        background: #000a00;
        color: #00ff00;
        border: solid #003300;
    }

    SerialTerminal #serial-input:focus {
        border: solid #00ff00;
    }

    SerialTerminal #btn-send {
        width: 12;
        height: 3;
        background: #003300;
        color: #00ff00;
        border: solid #00ff00;
        text-style: bold;
        margin-left: 1;
    }

    SerialTerminal #btn-send:hover {
        background: #005500;
    }

    SerialTerminal #btn-clear-log {
        width: 12;
        height: 3;
        background: #1a0000;
        color: #ff4444;
        border: solid #660000;
        text-style: bold;
        margin-left: 1;
    }

    SerialTerminal #btn-clear-log:hover {
        background: #330000;
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
        self._log: RichLog | None = None

    # ------------------------------------------------------------------
    # Engine link
    # ------------------------------------------------------------------

    def set_engine(self, engine: MarauderEngine) -> None:
        """Bind the terminal to *engine* for sending commands."""
        self._engine = engine

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(
            "[b][ RAW SERIAL MONITOR ][/b]  --  "
            "Direct ESP32 Marauder communication",
            id="serial-header",
        )
        yield RichLog(
            highlight=True,
            markup=True,
            wrap=True,
            id="serial-log",
        )
        with Horizontal(id="input-row"):
            yield Static("[#00ff00]>_ [/]", id="serial-prompt")
            yield Input(
                placeholder="type marauder command...",
                id="serial-input",
            )
            yield Button("[TX]", id="btn-send")
            yield Button("[CLR]", id="btn-clear-log")

    # ------------------------------------------------------------------
    # Post-mount wiring
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._log = self.query_one("#serial-log", RichLog)
        # Write a boot banner
        self._log.write(
            "[#004400]========================================"
            "========================================[/]"
        )
        self._log.write(
            "[#00ff00][b]  MARAUDER RAW SERIAL TERMINAL[/b][/]"
        )
        self._log.write(
            "[#004400]  Type commands below. Output appears here in real-time.[/]"
        )
        self._log.write(
            "[#004400]========================================"
            "========================================[/]"
        )
        self._log.write("")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_line(self, text: str) -> None:
        """Append a raw serial line to the terminal log."""
        if self._log is None:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.write(f"[#006600]{ts}[/] [#00ff00]{text}[/]")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-send":
            self._send_command()
        elif btn_id == "btn-clear-log":
            self._clear_log()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Send the command when the user presses Enter in the input field."""
        if event.input.id == "serial-input":
            self._send_command()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_command(self) -> None:
        """Read the input field, send the command via engine bridge, and echo it."""
        try:
            input_widget = self.query_one("#serial-input", Input)
        except Exception:
            return

        cmd = input_widget.value.strip()
        if not cmd:
            return

        # Echo the command locally
        ts = datetime.now().strftime("%H:%M:%S")
        if self._log is not None:
            self._log.write(
                f"[#006600]{ts}[/] [#ffaa00][b]TX >>>[/b] {cmd}[/]"
            )

        # Send via engine bridge
        if self._engine is not None:
            try:
                self._engine._bridge.send_command(cmd)
            except Exception as exc:
                if self._log is not None:
                    self._log.write(
                        f"[#ff4444][b]ERROR:[/b] {exc}[/]"
                    )

        # Clear the input field
        input_widget.value = ""
        input_widget.focus()

    def _clear_log(self) -> None:
        """Clear all lines from the serial log."""
        if self._log is not None:
            self._log.clear()
