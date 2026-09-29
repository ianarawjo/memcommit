"""One logical Memory line using the shared display-cleaned word diff."""

from __future__ import annotations

import typer
from prompt_toolkit.formatted_text import StyleAndTextTuples

from memcommit.application.capabilities.reviewing.memory_diff import (
    MemoryChange,
    word_diff_spans,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)


def inline_diff_parts(before: str, after: str, *, color: bool = True):
    """Return safe tokens; textual brackets preserve differences without color."""
    spans = word_diff_spans(before, after)
    for index, span in enumerate(spans):
        value = display_escape_text(span.text)
        if not color and span.kind != "equal":
            value = f"[-{value}-]" if span.kind == "remove" else f"[+{value}+]"
        elif (
            color
            and index
            and spans[index - 1].kind == "remove"
            and span.kind == "add"
            and not spans[index - 1].text[-1:].isspace()
            and not span.text[:1].isspace()
        ):
            # Adjacent replacement tokens need separation when color replaces brackets.
            yield "equal", " "
        yield span.kind, value


def inline_diff_text(before: str, after: str, *, color: bool) -> str:
    parts = []
    for kind, text in inline_diff_parts(before, after, color=color):
        if color and kind != "equal":
            role = (
                SemanticColorRole.REMOVE if kind == "remove" else SemanticColorRole.EDIT
            )
            text = typer.style(text, fg=semantic_color_rgb(role), underline=True)
        parts.append(text)
    return "".join(parts)


def render_inline_memory_change(
    change: MemoryChange,
    *,
    identity: str | None = None,
    color: bool = True,
) -> StyleAndTextTuples:
    """Render actual before/after bytes with the caller's frozen location mapping."""
    marker = (
        "+"
        if change.before is None
        else "-"
        if change.after is None
        else " "
        if change.before == change.after
        else "~"
    )
    kind = {"+": "add", "-": "remove", "~": "add", " ": "equal"}[marker]
    marker_style = f"class:memory-diff.{kind}"
    if marker == "-":
        marker_style = "class:memory-diff.before-marker"
    elif marker in {"+", "~"}:
        marker_style = "class:memory-diff.after-marker"
    label = identity or f"[{change.location}:{change.memory_uid[:8]}]"
    fragments = [
        (marker_style, marker + " "),
        ("class:report-neutral", display_escape_text(label) + " "),
    ]
    if change.before is None or change.after is None:
        fragments.append(
            (
                f"class:memory-diff.{kind}.changed",
                display_escape_text(
                    change.after if change.before is None else change.before
                ),
            )
        )
    else:
        for part_kind, text in inline_diff_parts(
            change.before, change.after, color=color
        ):
            style = f"class:memory-diff.{part_kind}" + (
                ".changed" if part_kind != "equal" else ""
            )
            fragments.append((style, text))
    fragments.append(("", "\n"))
    return fragments
