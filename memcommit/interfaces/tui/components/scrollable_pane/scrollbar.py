"""Visual-row-aware scrollbar for wrapped read-only panes."""

from __future__ import annotations

from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.layout.containers import WindowRenderInfo
from prompt_toolkit.layout.margins import ScrollbarMargin


class WrappedScrollbarMargin(ScrollbarMargin):
    """A scrollbar whose thumb follows wrapped visual rows."""

    def __init__(self, *, display_arrows: bool = True) -> None:
        super().__init__(display_arrows=display_arrows)
        self._revision = 0
        self._height_cache: dict[tuple[int, int, int], tuple[int, ...]] = {}

    def invalidate(self) -> None:
        """Forget cached visual heights after trusted pane text changes."""

        self._revision += 1
        self._height_cache.clear()

    def _line_heights(self, render_info: WindowRenderInfo) -> tuple[int, ...]:
        key = (
            self._revision,
            render_info.window_width,
            render_info.content_height,
        )
        cached = self._height_cache.get(key)
        if cached is not None:
            return cached
        heights = tuple(
            max(1, render_info.get_height_for_line(line_number))
            for line_number in range(render_info.content_height)
        )
        self._height_cache[key] = heights
        return heights

    def create_margin(
        self,
        window_render_info: WindowRenderInfo,
        width: int,
        height: int,
    ) -> StyleAndTextTuples:
        """Render a visual-row-aware thumb for wrapped read-only prose."""

        del width, height
        display_arrows = self.display_arrows()
        track_height = window_render_info.window_height
        if display_arrows:
            track_height -= 2
        if track_height <= 0:
            return []

        line_heights = self._line_heights(window_render_info)
        total_height = sum(line_heights)
        viewport_height = min(total_height, window_render_info.window_height)
        logical_start = window_render_info.vertical_scroll
        visual_offset = (
            sum(line_heights[:logical_start])
            + window_render_info.window.vertical_scroll_2
        )
        scrollable_height = max(0, total_height - viewport_height)
        visual_offset = min(max(0, visual_offset), scrollable_height)
        thumb_height = min(
            track_height,
            max(1, int(track_height * viewport_height / total_height)),
        )
        thumb_top = (
            0
            if scrollable_height == 0
            else round(
                (track_height - thumb_height) * visual_offset / scrollable_height
            )
        )

        result: StyleAndTextTuples = []
        if display_arrows:
            result.extend(
                [
                    ("class:scrollbar.arrow", self.up_arrow_symbol),
                    ("class:scrollbar", "\n"),
                ]
            )
        for row in range(track_height):
            in_thumb = thumb_top <= row < thumb_top + thumb_height
            next_in_thumb = thumb_top <= row + 1 < thumb_top + thumb_height
            if in_thumb:
                style = (
                    "class:scrollbar.button"
                    if next_in_thumb
                    else "class:scrollbar.button,scrollbar.end"
                )
            else:
                style = (
                    "class:scrollbar.background,scrollbar.start"
                    if next_in_thumb
                    else "class:scrollbar.background"
                )
            result.extend([(style, " "), ("", "\n")])
        if display_arrows:
            result.append(("class:scrollbar.arrow", self.down_arrow_symbol))
        return result
