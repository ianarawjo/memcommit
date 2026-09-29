"""Issue details for the decision screen."""

from __future__ import annotations


from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.theme import semantic_quality_role
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    semantic_role_style,
)


def render_issue_details(state) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    item = state.current_issue()
    if item is not None:
        question_first = item.kind == "CONFLICT"
        role = semantic_quality_role(item.kind)
        fragments.append(
            (
                semantic_role_style(role) if role is not None else "class:section",
                f" {safe_terminal_text(item.display_kind.upper())}"
                + ("" if question_first else "\n"),
            )
        )
        if question_first:
            if item.question.strip():
                fragments.append(
                    ("class:report-neutral", f"  {safe_terminal_text(item.question)}")
                )
            fragments.append(("", "\n\n"))
            if item.blocks:
                fragments.append(("class:report-label", " Memories\n"))
        for block in item.blocks:
            fragments.append(
                ("class:report-neutral", f" {safe_terminal_text(block.heading)} ")
            )
            fragments.append(
                ("class:memory-object", safe_terminal_text(block.text) + "\n")
            )
        if not item.blocks:
            fragments.append(
                ("class:report-neutral", safe_terminal_text(item.title) + "\n")
            )
        if (
            not question_first
            and item.question.strip()
            and item.question.strip() != item.title.strip()
        ):
            fragments.append(
                ("class:report-neutral", f" {safe_terminal_text(item.question)}\n")
            )
    return fragments
