"""Click/Typer styling for typed Source relationship labels."""

from __future__ import annotations

import typer

from memcommit.adapters.console.theme import (
    semantic_color_rgb,
    semantic_source_role,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
)
from memcommit.source_projection.presentation import (
    source_object_label,
    source_reach_label,
    source_relationship_label,
)


def _style_source_label(
    label: str,
    value: SourceDisplayFacts | SourceForm,
) -> str:
    role = semantic_source_role(value)
    if role is None:
        return label
    return typer.style(label, fg=semantic_color_rgb(role))


def styled_source_object_label(
    value: SourceDisplayFacts | SourceForm,
    *,
    title: bool = False,
) -> str:
    """Color one canonical object label from typed Source facts."""

    return _style_source_label(
        source_object_label(value, title=title),
        value,
    )


def styled_source_relationship_label(
    value: SourceDisplayFacts | SourceForm,
) -> str:
    """Color only one trusted relationship noun; identity stays neutral."""

    return _style_source_label(source_relationship_label(value), value)


def styled_source_reach_label(value: SourceReach) -> str:
    """Color only a typed reach marker; keep the Context identity neutral."""

    if not isinstance(value, SourceReach):
        raise TypeError("Styled Source reach labels require a SourceReach value.")
    return _style_source_label(
        source_reach_label(value),
        SourceDisplayFacts(reach=value),
    )


__all__ = [
    "styled_source_object_label",
    "styled_source_reach_label",
    "styled_source_relationship_label",
]
