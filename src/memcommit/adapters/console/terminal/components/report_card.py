"""Width-aware neutral text cards for terminal report surfaces."""

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    pad_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
)


def boxed_lines(title: str, body: str, *, width: int = 72) -> list[str]:
    """Return one width-aware neutral report card for terminal surfaces."""
    if width < 6:
        raise ValueError("Terminal card width must be at least 6 cells.")
    inner_width = width - 2
    body_width = width - 4
    safe_title = single_line_terminal_text(safe_terminal_text(title))
    label = f"─ {elide_terminal_text(safe_title, inner_width - 3)} "
    lines = [f"╭{label}{'─' * max(0, inner_width - terminal_cell_width(label))}╮"]
    lines.extend(
        f"│ {pad_terminal_text(line, body_width)} │"
        for line in wrap_terminal_text(safe_terminal_text(body), body_width)
    )
    lines.append(f"╰{'─' * inner_width}╯")
    return lines
