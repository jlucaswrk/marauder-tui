"""RSSI signal strength bar widget with hacker-aesthetic color coding."""
from __future__ import annotations

from rich.text import Text
from textual.widget import Widget
from textual.reactive import reactive


# Block characters from full to 1/8 — used to render sub-character precision.
_BLOCKS: list[str] = ["█", "▉", "▊", "▋", "▌", "▍", "▎", "▏"]

# RSSI boundaries for color thresholds.
_RSSI_MIN: int = -100
_RSSI_MAX: int = -30


def _rssi_color(rssi: int) -> str:
    """Return a Rich color name based on signal strength.

    >= -50 dBm  -> green  (strong)
    -50 to -70  -> yellow (moderate)
    < -70 dBm   -> red    (weak)
    """
    if rssi >= -50:
        return "green"
    if rssi >= -70:
        return "yellow"
    return "red"


def _build_bar(rssi: int, width: int) -> Text:
    """Build a Rich Text bar representing *rssi* in *width* character cells.

    The bar maps the RSSI range [_RSSI_MIN .. _RSSI_MAX] onto [0 .. width]
    using full-block and fractional-block Unicode characters for smooth
    rendering.
    """
    # Clamp RSSI into the expected range.
    clamped: int = max(_RSSI_MIN, min(_RSSI_MAX, rssi))

    # Fraction in [0.0 .. 1.0] where 1.0 == best signal.
    fraction: float = (clamped - _RSSI_MIN) / (_RSSI_MAX - _RSSI_MIN)

    # How many character cells the bar should fill (float).
    bar_float: float = fraction * width
    full_blocks: int = int(bar_float)
    remainder: float = bar_float - full_blocks

    color: str = _rssi_color(rssi)

    # Build the visible bar string.
    bar_chars: str = "█" * full_blocks

    # Add a fractional block if there is leftover space.
    if remainder > 0 and full_blocks < width:
        # Map the remainder [0..1) to one of the 8 partial-block glyphs.
        idx: int = max(0, min(len(_BLOCKS) - 1, int((1.0 - remainder) * len(_BLOCKS))))
        bar_chars += _BLOCKS[idx]
        full_blocks += 1

    # Pad the rest with spaces so the widget occupies exactly *width* cells.
    bar_chars += " " * (width - full_blocks)

    return Text.assemble(
        (bar_chars, f"bold {color}"),
    )


class RSSIBar(Widget):
    """Horizontal RSSI signal-strength bar.

    Set the ``rssi`` reactive attribute (int, dBm) to update the visual.
    Typical values range from -30 (excellent) to -100 (no signal).
    """

    DEFAULT_CSS = """
    RSSIBar {
        height: 1;
        min-width: 16;
        background: $background;
        color: #00ff00;
    }
    """

    rssi: reactive[int] = reactive(-100)

    def __init__(
        self,
        rssi: int = -100,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.rssi = rssi

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> Text:
        """Render the bar + dBm label into the available width."""
        # Reserve space for the label, e.g. " -42dBm" (7-8 chars).
        label: str = f" {self.rssi}dBm"
        bar_width: int = max(1, self.size.width - len(label))
        bar: Text = _build_bar(self.rssi, bar_width)
        color: str = _rssi_color(self.rssi)
        bar.append(label, style=f"bold {color}")
        return bar

    # ------------------------------------------------------------------
    # Reactive watchers
    # ------------------------------------------------------------------

    def watch_rssi(self, _old_value: int, _new_value: int) -> None:  # noqa: D401
        """Refresh the widget whenever rssi changes."""
        self.refresh()
