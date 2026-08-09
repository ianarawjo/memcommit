"""Shared terminal text geometry and adaptive column allocation.

This module owns display-cell mechanics only.  Callers retain semantic control
over which fields are important, whether a row may wrap, and the minimum or
preferred width of each field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.application.current import get_app_or_none
from prompt_toolkit.utils import get_cwidth


EllipsisPosition = Literal["end", "middle"]


def terminal_cell_width(value: str) -> int:
    """Return rendered terminal cells rather than Python code-point count."""

    return get_cwidth(value)


def single_line_terminal_text(value: str) -> str:
    """Fold whitespace into one presentation line without discarding content."""

    return " ".join(value.split())


def elide_terminal_text(
    value: str,
    max_cells: int,
    *,
    position: EllipsisPosition = "end",
    marker: str = "…",
) -> str:
    """Fit text to a terminal-cell budget and mark only actual omission."""

    if max_cells <= 0:
        return ""
    if terminal_cell_width(value) <= max_cells:
        return value
    marker_width = terminal_cell_width(marker)
    if marker_width >= max_cells:
        return _take_terminal_cells(marker, max_cells)
    available = max_cells - marker_width
    if position == "end":
        return _take_terminal_cells(value, available).rstrip() + marker
    if position != "middle":
        raise ValueError("ellipsis position must be 'end' or 'middle'")
    head_cells = (available + 1) // 2
    tail_cells = available - head_cells
    head = _take_terminal_cells(value, head_cells).rstrip()
    tail = _take_terminal_cells(value, tail_cells, from_end=True).lstrip()
    return head + marker + tail


def pad_terminal_text(value: str, width: int) -> str:
    """Pad an already fitted value to an exact terminal-cell width."""

    if width < 0:
        raise ValueError("terminal text width cannot be negative")
    return value + (" " * max(0, width - terminal_cell_width(value)))


def _take_terminal_cells(
    value: str,
    max_cells: int,
    *,
    from_end: bool = False,
) -> str:
    if max_cells <= 0:
        return ""
    source = reversed(value) if from_end else iter(value)
    kept: list[str] = []
    used = 0
    for character in source:
        character_width = get_cwidth(character)
        if used + character_width > max_cells:
            break
        kept.append(character)
        used += character_width
    if from_end:
        kept.reverse()
    return "".join(kept)


@dataclass(frozen=True)
class AdaptiveColumn:
    """One caller-owned field policy within a shared width allocator.

    ``shrink_order`` identifies which fields yield space first on narrow
    screens. ``grow_order`` identifies which fields reach their preferred
    content width first. An expanding field receives any space left after all
    preferred widths are satisfied.
    """

    key: str
    minimum: int
    preferred: int
    maximum: int | None = None
    shrink_order: int = 0
    grow_order: int = 0
    expand: bool = False

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("adaptive column key must be non-empty")
        if self.minimum < 0:
            raise ValueError("adaptive column minimum cannot be negative")
        if self.preferred < self.minimum:
            raise ValueError("adaptive column preferred width is below minimum")
        if self.maximum is not None and self.maximum < self.preferred:
            raise ValueError("adaptive column maximum is below preferred width")


def allocate_adaptive_columns(
    available_cells: int,
    columns: tuple[AdaptiveColumn, ...],
) -> dict[str, int]:
    """Allocate one live width budget according to per-field declarations."""

    if available_cells < 0:
        raise ValueError("available terminal cells cannot be negative")
    if len({column.key for column in columns}) != len(columns):
        raise ValueError("adaptive column keys must be unique")
    widths = {column.key: column.minimum for column in columns}

    # Narrow terminals compress declared minima rather than overflowing. The
    # calling surface decides the semantic order in which fields yield space.
    excess = sum(widths.values()) - available_cells
    if excess > 0:
        for column in sorted(columns, key=lambda item: item.shrink_order):
            removable = min(excess, widths[column.key])
            widths[column.key] -= removable
            excess -= removable
            if excess == 0:
                break
        return widths

    remaining = available_cells - sum(widths.values())
    for column in sorted(columns, key=lambda item: item.grow_order):
        growth = min(remaining, column.preferred - widths[column.key])
        widths[column.key] += growth
        remaining -= growth
        if remaining == 0:
            return widths

    expandable = [column for column in columns if column.expand]
    while remaining and expandable:
        grew = False
        for column in expandable:
            maximum = column.maximum
            if maximum is not None and widths[column.key] >= maximum:
                continue
            widths[column.key] += 1
            remaining -= 1
            grew = True
            if remaining == 0:
                break
        if not grew:
            break
    return widths


def live_window_content_width(
    window=None,
    *,
    fallback: int = 80,
    fallback_reserved: int = 0,
    minimum: int = 1,
) -> int:
    """Read a Window's exact content width, with a first-render fallback.

    ``WindowRenderInfo.window_width`` already excludes margins. Before the first
    render there is no render info, so callers declare only the chrome that the
    terminal-wide fallback must reserve. Re-evaluating this function from a
    render callback makes terminal resize a presentation-only reflow.
    """

    render_info = getattr(window, "render_info", None)
    if render_info is not None:
        return max(minimum, int(render_info.window_width))
    try:
        app = get_app_or_none()
        columns = (
            int(app.output.get_size().columns)
            if app is not None
            else fallback
        )
    except (AttributeError, RuntimeError):
        columns = fallback
    return max(minimum, columns - fallback_reserved)
