"""Scrolling activity-feed log widget with timestamped, color-coded entries."""
from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.widgets import RichLog


# ---------------------------------------------------------------------------
# Category -> color mapping
# ---------------------------------------------------------------------------

_CATEGORY_STYLES: dict[str, str] = {
    "WiFi": "bold green",
    "BLE":  "bold cyan",
    "ATK":  "bold red",
    "SYS":  "bold yellow",
}

_DEFAULT_STYLE: str = "bold #00ff00"

# Maximum number of lines kept in the log buffer.
_MAX_LINES: int = 200


class ActivityFeed(RichLog):
    """Real-time scrolling event log with hacker-terminal aesthetics.

    Each entry is timestamped and color-coded by category.

    Supported categories: ``WiFi`` (green), ``BLE`` (cyan), ``ATK`` (red),
    ``SYS`` (yellow).  Unknown categories fall back to neon green.

    Example rendered line::

        19:42:03 [WiFi] Found AP: VIVOFIBRA-68AC ch6 -42dBm
    """

    DEFAULT_CSS = """
    ActivityFeed {
        height: 1fr;
        border: solid #00ff00;
        background: #000000;
        scrollbar-color: #00ff00;
        scrollbar-color-active: #00ff00;
        scrollbar-color-hover: #33ff33;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        *,
        max_lines: int = _MAX_LINES,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(
            max_lines=max_lines,
            highlight=False,
            markup=False,
            wrap=True,
            name=name,
            id=id,
            classes=classes,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_entry(self, category: str, message: str) -> None:
        """Append a timestamped, color-coded entry to the feed.

        Parameters
        ----------
        category:
            Short tag such as ``"WiFi"``, ``"BLE"``, ``"ATK"``, or
            ``"SYS"``.  Controls the bracket color in the rendered line.
        message:
            Free-form message text displayed after the category tag.
        """
        now: str = datetime.now().strftime("%H:%M:%S")
        cat_style: str = _CATEGORY_STYLES.get(category, _DEFAULT_STYLE)

        line = Text.assemble(
            (now, "dim #00aa00"),
            " ",
            ("[", "dim white"),
            (category, cat_style),
            ("]", "dim white"),
            " ",
            (message, "#00ff00"),
        )

        self.write(line)
