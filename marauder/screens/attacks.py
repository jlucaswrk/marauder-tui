"""Attack selection screen -- WiFi and BLE offensive operations.

Provides a two-column layout with categorised attack buttons.  Every
attack displays a confirmation dialog before execution.  This widget is
designed to live inside a ``TabPane``, not as a standalone ``Screen``.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Label, ListItem, ListView, Static

from marauder.engine import MarauderEngine


# ======================================================================
# Confirmation overlay
# ======================================================================

class _ConfirmDialog(Widget):
    """Inline yes/no confirmation prompt rendered over the attack panel."""

    DEFAULT_CSS = """
    _ConfirmDialog {
        layout: vertical;
        width: 60;
        height: auto;
        max-height: 12;
        border: double #ff0000;
        background: #0a0000;
        padding: 1 2;
        layer: dialog;
        align: center middle;
    }

    _ConfirmDialog #confirm-msg {
        width: 100%;
        color: #ff4444;
        text-style: bold;
        margin-bottom: 1;
    }

    _ConfirmDialog #confirm-buttons {
        width: 100%;
        height: 3;
        align-horizontal: center;
    }

    _ConfirmDialog .confirm-btn {
        margin: 0 2;
        min-width: 14;
    }

    _ConfirmDialog #btn-yes {
        background: #880000;
        color: #ff4444;
        border: solid #ff0000;
        text-style: bold;
    }

    _ConfirmDialog #btn-yes:hover {
        background: #cc0000;
    }

    _ConfirmDialog #btn-no {
        background: #003300;
        color: #00ff00;
        border: solid #00ff00;
        text-style: bold;
    }

    _ConfirmDialog #btn-no:hover {
        background: #005500;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        yield Static(self._message, id="confirm-msg")
        with Horizontal(id="confirm-buttons"):
            yield Button("[EXECUTE]", id="btn-yes", variant="error", classes="confirm-btn")
            yield Button("[ABORT]", id="btn-no", variant="success", classes="confirm-btn")


# ======================================================================
# AP selection overlay (for deauth)
# ======================================================================

class _APSelector(Widget):
    """Overlay listing discovered APs for target selection."""

    DEFAULT_CSS = """
    _APSelector {
        layout: vertical;
        width: 70;
        height: auto;
        max-height: 20;
        border: double #ffaa00;
        background: #0a0a00;
        padding: 1 2;
        layer: dialog;
        align: center middle;
    }

    _APSelector #ap-title {
        width: 100%;
        color: #ffaa00;
        text-style: bold;
        margin-bottom: 1;
    }

    _APSelector ListView {
        height: auto;
        max-height: 12;
        background: #000000;
        color: #ffaa00;
        border: solid #444400;
    }

    _APSelector ListItem {
        color: #ffaa00;
        background: #000000;
        padding: 0 1;
    }

    _APSelector ListItem:hover {
        background: #222200;
    }

    _APSelector #ap-cancel {
        margin-top: 1;
        background: #003300;
        color: #00ff00;
        border: solid #00ff00;
        min-width: 14;
    }
    """

    def __init__(self, aps: list) -> None:
        super().__init__()
        self._aps = aps

    def compose(self) -> ComposeResult:
        yield Static("[#ffaa00]> SELECT TARGET AP[/]", id="ap-title")
        items: list[ListItem] = []
        for idx, ap in enumerate(self._aps):
            label = f"[{idx}] {ap.ssid or '<hidden>'}  BSSID:{ap.bssid}  ch{ap.channel}  {ap.rssi}dBm"
            items.append(ListItem(Label(label), id=f"ap-item-{idx}"))
        yield ListView(*items, id="ap-list")
        yield Button("[CANCEL]", id="ap-cancel")


# ======================================================================
# Main attacks panel
# ======================================================================

class AttacksPanel(Widget):
    """Two-column attack launcher with WiFi and BLE categories.

    Call :meth:`set_engine` to link the panel to a
    :class:`MarauderEngine` instance before use.
    """

    DEFAULT_CSS = """
    AttacksPanel {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: #000000;
    }

    AttacksPanel #attacks-header {
        dock: top;
        width: 100%;
        height: 3;
        background: #0a0000;
        color: #ff4444;
        text-style: bold;
        padding: 1 2;
        border-bottom: solid #330000;
    }

    AttacksPanel #attacks-columns {
        width: 100%;
        height: 1fr;
    }

    AttacksPanel .attack-col {
        width: 1fr;
        height: 100%;
        padding: 1 2;
    }

    AttacksPanel .col-title {
        width: 100%;
        height: 1;
        color: #ff4444;
        text-style: bold;
        margin-bottom: 1;
    }

    AttacksPanel .col-title-ble {
        width: 100%;
        height: 1;
        color: #aa00ff;
        text-style: bold;
        margin-bottom: 1;
    }

    AttacksPanel .wifi-attack-btn {
        width: 100%;
        margin-bottom: 1;
        min-width: 30;
        background: #220000;
        color: #ff4444;
        border: solid #660000;
        text-style: bold;
    }

    AttacksPanel .wifi-attack-btn:hover {
        background: #440000;
        border: solid #ff0000;
    }

    AttacksPanel .ble-attack-btn {
        width: 100%;
        margin-bottom: 1;
        min-width: 30;
        background: #110022;
        color: #cc66ff;
        border: solid #440066;
        text-style: bold;
    }

    AttacksPanel .ble-attack-btn:hover {
        background: #220044;
        border: solid #aa00ff;
    }

    AttacksPanel #attacks-status {
        dock: bottom;
        width: 100%;
        height: 1;
        background: #0a0000;
        color: #ff4444;
        padding: 0 2;
    }

    AttacksPanel .attack-separator {
        width: 100%;
        height: 1;
        color: #330000;
        margin-bottom: 1;
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
        self._pending_action: str | None = None
        self._pending_arg: int | None = None

    # ------------------------------------------------------------------
    # Engine link
    # ------------------------------------------------------------------

    def set_engine(self, engine: MarauderEngine) -> None:
        """Bind the panel to *engine* so attack commands can be issued."""
        self._engine = engine

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(
            "[b]//////  ATTACK MODULES  //////[/b]\n"
            "[#ff6666]WARNING: Use only on networks you own or have authorisation to test.[/]",
            id="attacks-header",
        )
        with Horizontal(id="attacks-columns"):
            # ---- WiFi attacks ----
            with VerticalScroll(classes="attack-col"):
                yield Static("[#ff4444]>>> WiFi ATTACKS <<<[/]", classes="col-title")
                yield Static("[#330000]" + "-" * 36 + "[/]", classes="attack-separator")
                yield Button(
                    "[ DEAUTH ATTACK ]",
                    id="btn-deauth",
                    classes="wifi-attack-btn",
                )
                yield Button(
                    "[ BEACON FLOOD ]",
                    id="btn-beacon",
                    classes="wifi-attack-btn",
                )
                yield Button(
                    "[ RICKROLL ]",
                    id="btn-rickroll",
                    classes="wifi-attack-btn",
                )
                yield Button(
                    "[ PROBE FLOOD ]",
                    id="btn-probe",
                    classes="wifi-attack-btn",
                )

            # ---- BLE attacks ----
            with VerticalScroll(classes="attack-col"):
                yield Static("[#aa00ff]>>> BLE SPAM <<<[/]", classes="col-title-ble")
                yield Static("[#330033]" + "-" * 36 + "[/]", classes="attack-separator")
                yield Button(
                    "[ Apple ]",
                    id="btn-ble-apple",
                    classes="ble-attack-btn",
                )
                yield Button(
                    "[ Samsung ]",
                    id="btn-ble-samsung",
                    classes="ble-attack-btn",
                )
                yield Button(
                    "[ Google ]",
                    id="btn-ble-google",
                    classes="ble-attack-btn",
                )
                yield Button(
                    "[ Windows ]",
                    id="btn-ble-windows",
                    classes="ble-attack-btn",
                )
                yield Button(
                    "[ Flipper ]",
                    id="btn-ble-flipper",
                    classes="ble-attack-btn",
                )
                yield Button(
                    "[ ALL TARGETS ]",
                    id="btn-ble-all",
                    classes="ble-attack-btn",
                )

        yield Static(
            "[#ff4444]STATUS:[/] Idle  --  select an attack module",
            id="attacks-status",
        )

    # ------------------------------------------------------------------
    # Button press dispatcher
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route button presses to the appropriate action or dialog."""
        btn_id = event.button.id

        # -- Confirmation dialog responses --
        if btn_id == "btn-yes":
            self._execute_pending()
            self._dismiss_overlay()
            return
        if btn_id == "btn-no":
            self._pending_action = None
            self._pending_arg = None
            self._dismiss_overlay()
            self._set_status("Aborted.")
            return
        if btn_id == "ap-cancel":
            self._dismiss_overlay()
            self._set_status("Target selection cancelled.")
            return

        # -- WiFi attacks --
        if btn_id == "btn-deauth":
            self._show_ap_selector()
            return
        if btn_id == "btn-beacon":
            self._request_confirm("beacon_flood", "Launch BEACON FLOOD attack?")
            return
        if btn_id == "btn-rickroll":
            self._request_confirm("rickroll", "Launch RICKROLL beacon attack?")
            return
        if btn_id == "btn-probe":
            self._request_confirm("probe", "Launch PROBE FLOOD attack?")
            return

        # -- BLE attacks --
        ble_map: dict[str, str] = {
            "btn-ble-apple": "apple",
            "btn-ble-samsung": "samsung",
            "btn-ble-google": "google",
            "btn-ble-windows": "windows",
            "btn-ble-flipper": "flipper",
            "btn-ble-all": "all",
        }
        if btn_id in ble_map:
            target = ble_map[btn_id]
            self._request_confirm(
                f"ble_spam_{target}",
                f"Launch BLE SPAM attack (target: {target.upper()})?",
            )
            return

    # ------------------------------------------------------------------
    # ListView selection (AP selector)
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle AP selection from the target list."""
        item_id: str | None = event.item.id
        if item_id and item_id.startswith("ap-item-"):
            idx = int(item_id.removeprefix("ap-item-"))
            self._dismiss_overlay()
            self._request_confirm(
                "deauth",
                f"Execute DEAUTH attack on AP index {idx}?",
                arg=idx,
            )

    # ------------------------------------------------------------------
    # Dialog helpers
    # ------------------------------------------------------------------

    def _request_confirm(self, action: str, message: str, *, arg: int | None = None) -> None:
        """Show a confirmation dialog for *action*."""
        self._pending_action = action
        self._pending_arg = arg
        self._dismiss_overlay()
        dialog = _ConfirmDialog(f"[#ff4444]{message}[/]")
        self.mount(dialog)

    def _show_ap_selector(self) -> None:
        """Show the AP target selection overlay."""
        if self._engine is None:
            self._set_status("Engine not connected.")
            return
        if not self._engine.aps:
            self._set_status("No APs discovered. Run a WiFi scan first.")
            return
        self._dismiss_overlay()
        selector = _APSelector(self._engine.aps)
        self.mount(selector)

    def _dismiss_overlay(self) -> None:
        """Remove any mounted overlay dialogs."""
        for overlay in self.query(_ConfirmDialog):
            overlay.remove()
        for overlay in self.query(_APSelector):
            overlay.remove()

    def _execute_pending(self) -> None:
        """Execute the pending attack action via the engine."""
        if self._engine is None:
            self._set_status("Engine not connected!")
            return
        action = self._pending_action
        arg = self._pending_arg
        self._pending_action = None
        self._pending_arg = None

        if action == "deauth" and arg is not None:
            self._engine.attack_deauth(arg)
            self._set_status(f"DEAUTH launched on AP index {arg}")
        elif action == "beacon_flood":
            self._engine.attack_beacon_flood()
            self._set_status("BEACON FLOOD launched")
        elif action == "rickroll":
            self._engine.attack_rickroll()
            self._set_status("RICKROLL launched")
        elif action == "probe":
            # Probe uses the beacon flood mechanism with probe frames
            self._engine.attack_beacon_flood()
            self._set_status("PROBE FLOOD launched")
        elif action and action.startswith("ble_spam_"):
            target = action.removeprefix("ble_spam_")
            self._engine.ble_spam(target)
            self._set_status(f"BLE SPAM launched (target={target})")
        else:
            self._set_status(f"Unknown action: {action}")

    def _set_status(self, message: str) -> None:
        """Update the bottom status bar."""
        try:
            bar = self.query_one("#attacks-status", Static)
            bar.update(f"[#ff4444]STATUS:[/] {message}")
        except Exception:
            pass
