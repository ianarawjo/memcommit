"""One vocabulary and ordering policy for source facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from memcommit.source_projection.model import (
    SourceAccess,
    SourceDisplayFacts,
    SourceForm,
    SourceReferenceRow,
    SourceReach,
    SourceState,
)


class SourceTokenRole(str, Enum):
    """Presentation role used by terminal adapters without embedding colors."""

    OWNERSHIP = "OWNERSHIP"
    ACCESS = "ACCESS"
    CAPABILITY = "CAPABILITY"
    REACH = "REACH"
    FORM = "FORM"
    STATE = "STATE"
    NOTE = "NOTE"


class SourceReferenceLayout(str, Enum):
    """Supported arrangements of the same typed Source Reference facts."""

    CONTENT_FIRST = "CONTENT_FIRST"
    IDENTITY_FIRST = "IDENTITY_FIRST"


@dataclass(frozen=True)
class SourceDisplayToken:
    text: str
    role: SourceTokenRole

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Source display tokens require nonblank text.")
        if any(character in self.text for character in "\r\n"):
            raise ValueError("Source display tokens must remain one line.")


SourceDisplayValue: TypeAlias = (
    SourceDisplayFacts | SourceDisplayToken | tuple[SourceDisplayToken, ...] | str
)


_ACCESS_LABELS = {
    SourceAccess.READ_GRANT: "READ GRANT",
    SourceAccess.QUERY_GRANT: "QUERY GRANT",
}
_REACH_LABELS = {
    SourceReach.DIRECT: "DIRECT",
    SourceReach.DESCENDANT: "DESCENDANT",
    SourceReach.VIA_EMBED: "VIA EMBED",
}
_OBJECT_LABELS = {
    SourceForm.CONTEXT: "context",
    SourceForm.CONTEXT_REFERENCE: "context reference",
    SourceForm.MEMORY: "memory",
    SourceForm.MEMORY_EMBED: "embedded memory",
    SourceForm.MEMORY_REFERENCE: "reference",
    SourceForm.MEMORY_REF: "memory ref",
    SourceForm.QUERY_VIEW: "query view",
}
_OBJECT_TITLE_LABELS = {
    SourceForm.CONTEXT: "Context",
    SourceForm.CONTEXT_REFERENCE: "Context Reference",
    SourceForm.MEMORY: "Memory",
    SourceForm.MEMORY_EMBED: "Embedded Memory",
    SourceForm.MEMORY_REFERENCE: "Reference",
    SourceForm.MEMORY_REF: "Memory ref",
    SourceForm.QUERY_VIEW: "Query view",
}
_STATE_LABELS = {
    SourceState.READ_ONLY: "READ ONLY",
    SourceState.UNAVAILABLE: "UNAVAILABLE",
    SourceState.DANGLING: "DANGLING",
    SourceState.CYCLE: "CYCLE",
    SourceState.NOT_INCLUDED: "NOT INCLUDED",
}
_STATE_ORDER = {state: index for index, state in enumerate(SourceState)}


def render_source_reference_row(
    row: SourceReferenceRow,
    *,
    uid_prefix_length: int = 8,
    content_character_limit: int | None = None,
    layout: SourceReferenceLayout = SourceReferenceLayout.CONTENT_FIRST,
) -> str:
    """Render one self-contained Source row without operation-specific parsing."""

    if not isinstance(row, SourceReferenceRow):
        raise TypeError("Source Reference rendering requires a SourceReferenceRow.")
    if (
        not isinstance(uid_prefix_length, int)
        or isinstance(uid_prefix_length, bool)
        or uid_prefix_length < 1
    ):
        raise ValueError("Source Reference UID prefix length must be positive.")
    if content_character_limit is not None and (
        not isinstance(content_character_limit, int)
        or isinstance(content_character_limit, bool)
        or content_character_limit < 2
    ):
        raise ValueError(
            "Source Reference content limit must be at least two characters."
        )
    if not isinstance(layout, SourceReferenceLayout):
        raise TypeError("Source Reference layout must be a SourceReferenceLayout.")
    # One logical row keeps stored line breaks from imitating a sibling ordinal
    # or provenance suffix. Terminal control escaping remains adapter-owned.
    content = " ".join(row.content.split())
    if content_character_limit is not None and len(content) > content_character_limit:
        content = content[: content_character_limit - 1].rstrip() + "…"
    owner = f"{row.uid[:uid_prefix_length]}, {row.context_name}"
    if row.alias is not None:
        owner += f", {row.alias}"
    provenance = ""
    if row.source_uid is not None:
        provenance = (
            f" → {row.source_uid[:uid_prefix_length]}, "
            f"{row.source_context_name}"
        )
    if layout is SourceReferenceLayout.IDENTITY_FIRST:
        location = row.context_name
        if row.alias is not None:
            location += f" {row.alias}"
        location_separator = " " if content[-1] in ".,;:!?" else ", "
        source = ""
        if row.source_uid is not None:
            source = (
                f" → [{row.source_uid[:uid_prefix_length]}]"
                f" [{row.source_context_name}]"
            )
        return (
            f"{row.number} [{row.uid[:uid_prefix_length]}] "
            f"{content}{location_separator}[{location}]{source}"
        )
    return f"[{row.number}] {content} — {owner}{provenance}"


def source_display_tokens(
    facts: SourceDisplayFacts,
    *,
    include_permissions: bool = False,
    include_defaults: bool = False,
    include_context_form: bool = False,
) -> tuple[SourceDisplayToken, ...]:
    """Render typed facts in canonical access/reach/form/state order."""

    tokens: list[SourceDisplayToken] = []
    if facts.access is not SourceAccess.OWNED:
        tokens.append(
            SourceDisplayToken(_ACCESS_LABELS[facts.access], SourceTokenRole.ACCESS)
        )
    elif include_defaults:
        tokens.append(SourceDisplayToken("OWNED", SourceTokenRole.ACCESS))
    if include_permissions and facts.permissions:
        tokens.append(
            SourceDisplayToken(
                "PERMISSIONS " + " + ".join(facts.permissions),
                SourceTokenRole.ACCESS,
            )
        )
    if facts.reach is not SourceReach.DIRECT:
        tokens.append(
            SourceDisplayToken(
                source_reach_label(facts.reach),
                SourceTokenRole.REACH,
            )
        )
    elif include_defaults:
        tokens.append(
            SourceDisplayToken(
                source_reach_label(SourceReach.DIRECT),
                SourceTokenRole.REACH,
            )
        )
    if facts.form is not SourceForm.CONTEXT:
        tokens.append(
            SourceDisplayToken(
                source_object_label(facts.form),
                SourceTokenRole.FORM,
            )
        )
    elif include_defaults or include_context_form:
        tokens.append(
            SourceDisplayToken(
                source_object_label(SourceForm.CONTEXT),
                SourceTokenRole.FORM,
            )
        )
    for state in sorted(facts.states, key=_STATE_ORDER.__getitem__):
        tokens.append(SourceDisplayToken(_STATE_LABELS[state], SourceTokenRole.STATE))
    return tuple(tokens)


def source_object_label(
    value: SourceDisplayFacts | SourceForm,
    *,
    title: bool = False,
) -> str:
    """Name one displayed object without turning its kind into a status badge."""

    form = value.form if isinstance(value, SourceDisplayFacts) else value
    if not isinstance(form, SourceForm):
        raise TypeError("Source object labels require a SourceForm value.")
    labels = _OBJECT_TITLE_LABELS if title else _OBJECT_LABELS
    return labels[form]


def source_reach_label(value: SourceReach) -> str:
    """Name one typed reach without mixing it into object identity."""

    if not isinstance(value, SourceReach):
        raise TypeError("Source reach labels require a SourceReach value.")
    return _REACH_LABELS[value]


def source_relationship_label(
    value: SourceDisplayFacts | SourceForm,
) -> str:
    """Name a compact relationship row by its public time semantics.

    Live Memory links are embeds and immutable retained links are references.
    The shorter relationship nouns keep the Source identity beside the link
    UID without repeating ``memory`` before the separate target badge.
    """

    form = value.form if isinstance(value, SourceDisplayFacts) else value
    if not isinstance(form, SourceForm):
        raise TypeError("Source relationship labels require a SourceForm value.")
    if form in {SourceForm.MEMORY_EMBED, SourceForm.MEMORY_REF}:
        return "embedded"
    if form in {
        SourceForm.CONTEXT_REFERENCE,
        SourceForm.MEMORY_REFERENCE,
    }:
        return "reference"
    return source_object_label(form)


def source_annotation_tokens(
    facts: SourceDisplayFacts,
    *,
    include_permissions: bool = False,
    include_defaults: bool = False,
) -> tuple[SourceDisplayToken, ...]:
    """Render access, reach, and state while leaving object kind separate."""

    return tuple(
        token
        for token in source_display_tokens(
            facts,
            include_permissions=include_permissions,
            include_defaults=include_defaults,
        )
        if token.role is not SourceTokenRole.FORM
    )


def source_annotation_text(
    facts: SourceDisplayFacts,
    *,
    include_permissions: bool = False,
    include_defaults: bool = False,
    separator: str = " · ",
) -> str:
    """Render source annotations without repeating the object's kind."""

    return separator.join(
        token.text
        for token in source_annotation_tokens(
            facts,
            include_permissions=include_permissions,
            include_defaults=include_defaults,
        )
    )


def normalize_source_display_tokens(
    value: SourceDisplayValue | None,
    *,
    include_permissions: bool = False,
    include_defaults: bool = False,
    include_context_form: bool = False,
) -> tuple[SourceDisplayToken, ...]:
    """Adapt typed annotations plus a temporary raw-string compatibility form."""

    if value is None or value == "":
        return ()
    if isinstance(value, SourceDisplayFacts):
        return source_display_tokens(
            value,
            include_permissions=include_permissions,
            include_defaults=include_defaults,
            include_context_form=include_context_form,
        )
    if isinstance(value, SourceDisplayToken):
        return (value,)
    if isinstance(value, str):
        return (SourceDisplayToken(value, SourceTokenRole.NOTE),)
    if isinstance(value, tuple) and all(
        isinstance(token, SourceDisplayToken) for token in value
    ):
        return value
    raise TypeError("Unsupported source display annotation.")


def combine_source_display_tokens(
    *values: SourceDisplayValue | None,
    include_permissions: bool = False,
) -> tuple[SourceDisplayToken, ...]:
    """Combine independent source and operation annotations without text parsing."""

    return tuple(
        token
        for value in values
        for token in normalize_source_display_tokens(
            value,
            include_permissions=include_permissions,
        )
    )


def source_display_text(
    value: SourceDisplayValue | None,
    *,
    include_permissions: bool = False,
    include_defaults: bool = False,
    include_context_form: bool = False,
    separator: str = " · ",
) -> str:
    """Render the same canonical tokens for non-TUI and compact text callers."""

    return separator.join(
        token.text
        for token in normalize_source_display_tokens(
            value,
            include_permissions=include_permissions,
            include_defaults=include_defaults,
            include_context_form=include_context_form,
        )
    )
