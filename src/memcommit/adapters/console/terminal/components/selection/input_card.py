"""A writable body inside the same checked-card chrome as fixed choices."""

from collections.abc import Callable
from prompt_toolkit.filters import FilterOrBool
from prompt_toolkit.layout import (
    ConditionalContainer,
    FormattedTextControl,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.containers import AnyContainer
from memcommit.adapters.console.terminal.components.frame import horizontal_rule
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.text_layout import (
    single_line_terminal_text,
)
from .rendering import choice_marker, choice_visual_state, render_choice_card_rows


def build_choice_input_card(
    body: AnyContainer,
    *,
    label: str,
    selected: Callable[[], bool],
    focused: Callable[[], bool],
    width: Callable[[], int],
    detail: AnyContainer | None = None,
    detail_title: Callable[[], str] = lambda: "",
    detail_visible: FilterOrBool = True,
):
    """Keep an editable choice and optional detail under one focus border."""

    def rows():
        return render_choice_card_rows(
            ("",),
            visual=choice_visual_state(
                cursor=True, selected=selected(), focused=focused()
            ),
            width=width(),
            title=f"{choice_marker(selected=selected())} {label}".strip(),
        )

    def edge(*, junction: bool = False, right: bool = False):
        def char():
            if not junction:
                return rows()[1][0][1]
            if focused():
                return "┨" if right else "┠"
            return "┤" if right else "├"

        return Window(
            width=1,
            char=char,
            style=lambda: rows()[1][0][0],
        )

    def bordered(content):
        return VSplit([edge(), content, edge(right=True)])

    children = [
        Window(FormattedTextControl(lambda: list(rows()[0])), height=1),
        bordered(body),
    ]
    if detail is not None:
        # The divider labels evidence inside this choice, not another choice or
        # focus stop. Its text and rule stay neutral when the outer card focuses.
        divider = VSplit(
            [
                edge(junction=True),
                Window(char="─", width=1),
                Window(
                    FormattedTextControl(
                        lambda: [
                            (
                                "class:report-label",
                                " "
                                + single_line_terminal_text(
                                    safe_terminal_text(detail_title())
                                )
                                + " ",
                            )
                        ]
                    ),
                    dont_extend_width=True,
                ),
                horizontal_rule(),
                edge(junction=True, right=True),
            ],
            height=1,
        )
        children.append(
            ConditionalContainer(
                HSplit([divider, bordered(detail)]),
                filter=detail_visible,
            )
        )
    children.append(Window(FormattedTextControl(lambda: list(rows()[-1])), height=1))
    card = HSplit(children, width=width)
    return VSplit([card, Window()])
