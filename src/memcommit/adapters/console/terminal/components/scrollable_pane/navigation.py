"""Wrapped visual-row navigation for read-only terminal panes."""

from __future__ import annotations

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


def move_wrapped_read_cursor(event: object, *, direction: int) -> bool:
    """Move one visual row and anchor it in a wrapped read-only viewport."""

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

    line_heights = tuple(
        max(1, render_info.get_height_for_line(line_number))
        for line_number in range(render_info.content_height)
    )
    total_height = sum(line_heights)
    viewport_height = min(total_height, render_info.window_height)
    current_offset = (
        sum(line_heights[: window.vertical_scroll]) + window.vertical_scroll_2
    )
    maximum_offset = max(0, total_height - viewport_height)
    target_offset = max(0, min(current_offset + direction, maximum_offset))
    if target_offset == current_offset:
        return False

    row = 0
    row_offset = target_offset
    for line_number, line_height in enumerate(line_heights):
        if row_offset < line_height:
            row = line_number
            break
        row_offset -= line_height

    document = buffer.document
    column = 0
    if render_info.wrap_lines and row_offset and render_info.window_width > 0:
        visual_row = 0
        visual_width = 0
        for index, character in enumerate(document.lines[row]):
            character_width = terminal_cell_width(character)
            if visual_width + character_width > render_info.window_width:
                visual_row += 1
                visual_width = 0
                if visual_row == row_offset:
                    column = index
                    break
            visual_width += character_width
        else:
            column = len(document.lines[row])

    buffer.cursor_position = document.translate_row_col_to_index(row, column)
    window.vertical_scroll = row
    window.vertical_scroll_2 = row_offset if render_info.wrap_lines else 0
    app.invalidate()
    return True
