"""Header for the decision screen."""

from __future__ import annotations


from memcommit.adapters.console.terminal.core.text import safe_terminal_text


def render_header(state, header_label=None) -> list[tuple[str, str]]:
    view = state.supplier()
    if header_label is not None:
        return [
            (
                "class:report-label",
                f" {safe_terminal_text(header_label).strip()}\n",
            )
        ]
    if state.items:
        state = "NEEDS INPUT"
    else:
        state = "READY TO APPLY"
    return [
        (
            "class:report-label",
            f" {safe_terminal_text(view.operation.upper())} {state}\n",
        )
    ]
