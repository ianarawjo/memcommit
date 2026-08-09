from types import SimpleNamespace

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import set_app
from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.utils import get_cwidth

from memcommit.commands.tui_text_layout import (
    AdaptiveColumn,
    allocate_adaptive_columns,
    elide_terminal_text,
    live_window_content_width,
    pad_terminal_text,
    single_line_terminal_text,
)


class _SizedDummyOutput(DummyOutput):
    def get_size(self) -> Size:
        return Size(rows=24, columns=132)


def test_elision_uses_terminal_cells_for_wide_text():
    rendered = elide_terminal_text("가나다라마바사", 7)

    assert rendered == "가나다…"
    assert get_cwidth(rendered) == 7


def test_middle_elision_preserves_both_ends_within_cell_budget():
    rendered = elide_terminal_text("source/very-long-name/output", 15, position="middle")

    assert rendered.startswith("source/")
    assert rendered.endswith("/output")
    assert get_cwidth(rendered) <= 15


def test_text_that_fits_is_never_marked_as_omitted():
    assert elide_terminal_text("complete", 20) == "complete"
    assert pad_terminal_text("한", 4) == "한  "
    assert single_line_terminal_text(" one\n two\tthree ") == "one two three"


def test_adaptive_columns_follow_caller_priorities_and_expand():
    columns = (
        AdaptiveColumn(
            "title",
            minimum=8,
            preferred=18,
            maximum=18,
            shrink_order=1,
            grow_order=0,
        ),
        AdaptiveColumn(
            "summary",
            minimum=8,
            preferred=20,
            shrink_order=0,
            grow_order=1,
            expand=True,
        ),
    )

    assert allocate_adaptive_columns(50, columns) == {
        "title": 18,
        "summary": 32,
    }
    assert allocate_adaptive_columns(12, columns) == {
        "title": 8,
        "summary": 4,
    }


def test_live_width_uses_first_render_fallback_then_exact_window_content():
    assert live_window_content_width(fallback=90, fallback_reserved=3) == 87

    app = Application(output=_SizedDummyOutput())
    with set_app(app):
        assert live_window_content_width(fallback_reserved=3) == 129

    window = SimpleNamespace(render_info=SimpleNamespace(window_width=77))
    assert live_window_content_width(window, fallback_reserved=3) == 77
