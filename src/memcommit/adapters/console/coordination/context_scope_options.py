"""Console DIRECT and RECURSIVE Context-scope option presets.

The presets are interface conveniences, not a replacement for an operation's
precise scope fields. A command or TUI may expose role-specific descendant or
embedded-Context controls and use those explicit values to refine the preset.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class ContextScopePreset(str, Enum):
    """The common narrow-versus-broad Context-scope vocabulary."""

    DIRECT = "DIRECT"
    RECURSIVE = "RECURSIVE"


@dataclass(frozen=True)
class ContextTraversal:
    """The two independent read axes used by operations that expose both."""

    include_descendants: bool
    follow_embeds: bool


def legacy_root_only_option_alias(role: str) -> str:
    """Return Click's extra-negative-alias declaration for one scope role.

    Click uses a leading space to attach an additional spelling to the negative
    side of a boolean pair. Keeping that parser-specific convention here lets
    commands present ``--<role>-root-only`` as canonical while continuing to
    accept the historical ``--<role>-only`` input.
    """

    if not role or any(part == "" for part in role.split("-")):
        raise ValueError("Context scope role must be a nonempty dashed name.")
    return f" /--{role}-only"


def resolve_scope_preset(
    *,
    direct: bool,
    recursive: bool,
    default: ContextScopePreset = ContextScopePreset.DIRECT,
) -> ContextScopePreset:
    """Resolve the common flags without assigning operation-specific meaning."""

    if type(direct) is not bool or type(recursive) is not bool:
        raise TypeError("Context scope flags must be booleans.")
    if not isinstance(default, ContextScopePreset):
        raise TypeError("Context scope default must be a ContextScopePreset.")
    if direct and recursive:
        raise ValueError("Choose either --direct/-d or --recursive/-r, not both.")
    if direct:
        return ContextScopePreset.DIRECT
    if recursive:
        return ContextScopePreset.RECURSIVE
    return default


def resolve_descendant_scopes(
    *,
    preset: ContextScopePreset,
    explicit: Sequence[bool | None],
) -> tuple[bool, ...]:
    """Apply one preset to roles, retaining every explicit role override."""

    if not isinstance(preset, ContextScopePreset):
        raise TypeError("Context scope preset is invalid.")
    values = tuple(explicit)
    if any(value is not None and type(value) is not bool for value in values):
        raise TypeError("Context descendant overrides must be booleans or None.")
    fallback = preset is ContextScopePreset.RECURSIVE
    return tuple(fallback if value is None else value for value in values)


def resolve_context_traversal(
    *,
    preset: ContextScopePreset,
    include_descendants: bool | None = None,
    follow_embeds: bool | None = None,
) -> ContextTraversal:
    """Resolve independent lexical and embedded axes from one common preset."""

    if not isinstance(preset, ContextScopePreset):
        raise TypeError("Context scope preset is invalid.")
    if include_descendants is not None and type(include_descendants) is not bool:
        raise TypeError("Context descendant override must be a boolean or None.")
    if follow_embeds is not None and type(follow_embeds) is not bool:
        raise TypeError("Embedded Context override must be a boolean or None.")
    fallback = preset is ContextScopePreset.RECURSIVE
    return ContextTraversal(
        include_descendants=(
            fallback if include_descendants is None else include_descendants
        ),
        follow_embeds=fallback if follow_embeds is None else follow_embeds,
    )
