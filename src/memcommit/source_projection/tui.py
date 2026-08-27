"""Prompt-toolkit fragments for shared source display tokens."""

from __future__ import annotations

from memcommit.adapters.console.text import (
    display_escape_text,
)
from memcommit.source_projection.presentation import (
    SourceDisplayToken,
    SourceTokenRole,
)


_TOKEN_STYLES = {
    SourceTokenRole.OWNERSHIP: "class:source-ownership",
    SourceTokenRole.ACCESS: "class:source-access",
    SourceTokenRole.CAPABILITY: "class:source-capability",
    SourceTokenRole.REACH: "class:source-reach",
    SourceTokenRole.FORM: "class:reference",
    SourceTokenRole.STATE: "class:source-state",
    SourceTokenRole.NOTE: "class:report-neutral",
}


def render_source_display_tokens(
    tokens: tuple[SourceDisplayToken, ...],
    *,
    override_style: str = "",
    separator: str = " · ",
) -> list[tuple[str, str]]:
    """Render tokens with one semantic palette, or one owning focus style."""

    fragments: list[tuple[str, str]] = []
    for index, token in enumerate(tokens):
        if index:
            fragments.append((override_style, separator))
        fragments.append(
            (
                override_style or _TOKEN_STYLES[token.role],
                display_escape_text(token.text),
            )
        )
    return fragments
