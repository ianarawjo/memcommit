"""Wrapped visual-row navigation for read-only terminal panes."""

from __future__ import annotations

from bisect import bisect_right

from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down, scroll_page_up

from memcommit.adapters.console.terminal.core.text_layout import terminal_cell_width


def scroll_wrapped_page(event: object, *, direction: int) -> None:
    """Move one visual page in the currently focused wrapped read pane."""

    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    app = getattr(event, "app")
    window = app.layout.current_window
    buffer = app.current_buffer
    render_info = window.render_info if window is not None else None
    if render_info is None:
        return

    page_height = max(1, render_info.window_height)
    mapping = render_info.visible_line_to_row_col
    if direction > 0:
        candidates = [row for row in mapping if row >= page_height]
        visual_row = min(candidates) if candidates else None
    else:
        candidates = [row for row in mapping if row <= -page_height]
        visual_row = max(candidates) if candidates else None

    if visual_row is not None:
        row, column = mapping[visual_row]
        target = buffer.document.translate_row_col_to_index(row, column)
        if target != buffer.cursor_position:
            buffer.cursor_position = target
            app.invalidate()
            return

    if direction > 0:
        scroll_page_down(event)
    else:
        scroll_page_up(event)
    app.invalidate()


def _wrapped_row_start_columns(line: str, width: int) -> tuple[int, ...]:
    """Map terminal wrapping to document columns, including an end cursor row."""

    starts = [0]
    occupied_cells = 0
    for column, character in enumerate(line):
        character_cells = terminal_cell_width(character)
        if occupied_cells and occupied_cells + character_cells > width:
            starts.append(column)
            occupied_cells = 0
        occupied_cells += character_cells
    # prompt-toolkit renders a cursor cell after the line. An exactly full
    # final row therefore puts the end cursor on the next visual row.
    if occupied_cells >= width:
        starts.append(len(line))
    return tuple(starts)


def move_wrapped_read_cursor(event: object, *, direction: int) -> bool:
    """Move from the actual cursor by one visual row in a read-only pane."""

    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    app = getattr(event, "app")
    window = app.layout.current_window
    buffer = app.current_buffer
    render_info = window.render_info if window is not None else None
    if render_info is None or window is None:
        before = buffer.cursor_position
        if direction > 0:
            buffer.cursor_down(count=1)
        else:
            buffer.cursor_up(count=1)
        moved = buffer.cursor_position != before
        if moved:
            app.invalidate()
        return moved

    document = buffer.document
    wrapped_columns = tuple(
        _wrapped_row_start_columns(line, render_info.window_width)
        if render_info.wrap_lines and render_info.window_width > 0
        else (0,)
        for line in document.lines
    )
    # A wide character can leave an unused cell before wrapping. Counting
    # total cells alone can undercount those rows at an odd viewport width.
    line_heights = tuple(
        max(1, render_info.get_height_for_line(row), len(starts))
        for row, starts in enumerate(wrapped_columns)
    )
    total_height = sum(line_heights)
    current_row = document.cursor_position_row
    current_visual_row = 0
    if render_info.wrap_lines and render_info.window_width > 0:
        starts = wrapped_columns[current_row]
        current_visual_row = min(
            bisect_right(starts, document.cursor_position_col) - 1,
            line_heights[current_row] - 1,
        )
    # The viewport can be bottom-aligned or stale after Home/End/PageDown.
    # It is presentation state, never the origin or boundary of cursor movement.
    current_offset = sum(line_heights[:current_row]) + current_visual_row
    target_offset = max(0, min(current_offset + direction, total_height - 1))
    if target_offset == current_offset:
        return False

    row = 0
    row_offset = target_offset
    for line_number, line_height in enumerate(line_heights):
        if row_offset < line_height:
            row = line_number
            break
        row_offset -= line_height

    column = 0
    if render_info.wrap_lines and row_offset and render_info.window_width > 0:
        starts = wrapped_columns[row]
        column = starts[min(row_offset, len(starts) - 1)]

    target_position = document.translate_row_col_to_index(row, column)
    if target_position == buffer.cursor_position:
        return False
    buffer.cursor_position = target_position
    # Let the shared Window follow its cursor with its normal scroll offsets.
    app.invalidate()
    return True
