"""Shared direct-item diff rows for checkpoint reports and Merge previews."""

from __future__ import annotations

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    semantic_action_style,
)
from memcommit.application.capabilities.reviewing.context_diff import (
    ContextItemChange,
    context_item_text,
)
from memcommit.application.capabilities.reviewing.memory_diff import (
    MemoryChange,
    memory_diff_lines,
)


def render_context_item_change(
    change: ContextItemChange,
    *,
    location: str,
    verbose_uid: bool = False,
    show_treatment: bool = True,
) -> StyleAndTextTuples:
    """Render inline item identities, with optional treatment labels."""

    treatment = change.treatment
    fragments: StyleAndTextTuples = []
    memory_change = MemoryChange(
        marker={"KEEP": "=", "ADD": "+", "REMOVE": "−", "EDIT": "~"}[treatment],
        treatment=treatment,
        location=location,
        memory_uid=change.uid,
        before=context_item_text(change.before),
        after=context_item_text(change.after),
    )
    for line in memory_diff_lines(memory_change):
        style_key = {
            "-": "remove",
            "+": "add",
            "=": "equal",
            " ": "equal",
        }[line.marker]
        visible_marker = line.marker if line.marker in {"-", "+"} else " "
        marker_style = {
            "-": "class:memory-diff.before-marker",
            "+": "class:memory-diff.after-marker",
        }.get(line.marker, "class:memory-diff.equal")
        label = f"[{treatment}]"
        fragments.append((marker_style, f" {visible_marker} "))
        if show_treatment:
            fragments.append(("class:report-neutral", "["))
            fragments.append(
                (
                    semantic_action_style(treatment, fallback="class:report-neutral"),
                    treatment,
                )
            )
            fragments.append(
                (
                    "class:report-neutral",
                    "]"
                    + " " * (9 - len(label)),
                )
            )
        fragments.append(
            (
                "class:report-neutral",
                f"[{display_escape_text(change.uid if verbose_uid else change.uid[:8])}] ",
            )
        )
        fragments.extend(
            (
                (
                    f"class:memory-diff.{style_key}"
                    + (".changed" if span.changed else "")
                ),
                display_escape_text(span.text),
            )
            for span in line.spans
        )
        fragments.append(("", "\n"))
    return fragments
