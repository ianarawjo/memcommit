"""One selected Context row that opens the common Context tree in place."""

from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout import (
    Dimension,
    DynamicContainer,
    FormattedTextControl,
    Window,
)

from memcommit.adapters.console.terminal.components.frame import build_focused_frame
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.source_projection.presentation import normalize_source_display_tokens
from memcommit.source_projection.tui import render_source_display_tokens


class CompactContextSelectorControl:
    """Compose one SINGLE selector with a compact committed-value surface."""

    def __init__(self, selector: ContextSelectorControl) -> None:
        if selector.view.mode != "SINGLE":
            raise ValueError("Compact Context selection requires SINGLE mode.")
        self.selector = selector
        self.is_open = False
        self.summary = FormattedTextControl(
            self._render_summary, focusable=True, show_cursor=False
        )
        self.frame = build_focused_frame(
            Window(self.summary, height=1, wrap_lines=False),
            title=safe_terminal_text(selector.view.label),
            is_focused=lambda: get_app().layout.has_focus(self.summary),
            height=Dimension.exact(3),
        )
        self.container = DynamicContainer(
            lambda: selector.frame if self.is_open else self.frame
        )

    @property
    def control(self):
        return self.selector.control if self.is_open else self.summary

    def _render_summary(self) -> list[tuple[str, str]]:
        name = self.selector.selection.selected_name
        annotation = self.selector.annotations.get(name)
        fragments = [("", f" {safe_terminal_text(name)}")]
        if annotation:
            fragments.append(("", " · "))
            fragments.extend(
                render_source_display_tokens(
                    normalize_source_display_tokens(annotation)
                )
            )
        fragments.append(("", "    Enter change"))
        return fragments

    def open(self) -> None:
        # Reopening follows the committed choice, never a cancelled hover.
        self.selector.select_name(self.selector.selection.selected_name)
        self.is_open = True

    def close(self) -> None:
        self.is_open = False
