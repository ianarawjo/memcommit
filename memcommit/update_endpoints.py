"""Resolve the two ordinary-Context endpoints of a directional update."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.context_locator import resolve_context_locator


@dataclass(frozen=True)
class UpdateEndpoints:
    """Canonical source and target names for one directional operation."""

    source_name: str
    target_name: str


def choose_update_endpoint_operands(
    operands: list[str] | tuple[str, ...] | None,
    *,
    source_option: str | None,
    target_option: str | None,
    allow_single_source: bool = False,
) -> tuple[str | None, str | None]:
    """Normalize the positional pair and legacy directional options.

    The legacy/default form requires a complete positional pair.  Commands
    that opt into ``allow_single_source`` define one positional operand as the
    Source and use ``--to`` or the command-start current Context as Target.
    """
    positional = tuple(operands or ())
    allowed_lengths = {0, 1, 2} if allow_single_source else {0, 2}
    if len(positional) not in allowed_lengths:
        raise ValueError(
            (
                "expected zero, SOURCE, or SOURCE TARGET operands."
                if allow_single_source
                else "expected either no positional Contexts or exactly SOURCE TARGET."
            )
        )
    if len(positional) == 2 and (
        source_option is not None or target_option is not None
    ):
        raise ValueError("positional Contexts cannot be combined with --from or --to.")
    if len(positional) == 2:
        return positional[0], positional[1]
    if len(positional) == 1:
        if source_option is not None:
            raise ValueError("Source was supplied both positionally and with --from.")
        return positional[0], target_option
    return source_option, target_option


def resolve_update_endpoints(
    *,
    source_locator: str | None,
    target_locator: str | None,
    current: str | None,
) -> UpdateEndpoints:
    """Resolve explicit or current-filled endpoints against one snapshot."""
    if source_locator is None and target_locator is None:
        raise ValueError("At least one directional endpoint locator is required.")

    if source_locator is None:
        if not current:
            raise ValueError("No current source Context. Supply '--from SOURCE'.")
        source_name = current
    else:
        source_name = resolve_context_locator(
            source_locator,
            current=current,
        )

    if target_locator is None:
        if not current:
            raise ValueError("No current target Context. Supply '--to TARGET'.")
        target_name = current
    else:
        target_name = resolve_context_locator(
            target_locator,
            current=current,
        )

    # Reject after canonicalization so aliases such as '.' cannot bypass the
    # directional operation's distinct-endpoint invariant.
    if source_name == target_name:
        raise ValueError("Source and target Contexts must be distinct.")

    return UpdateEndpoints(
        source_name=source_name,
        target_name=target_name,
    )
