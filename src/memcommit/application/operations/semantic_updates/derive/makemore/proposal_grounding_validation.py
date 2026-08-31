"""Validate how Makemore proposals use ambient Target grounding."""

from __future__ import annotations

from memcommit.application.operations.semantic_updates.derive.makemore.model import (
    MakemoreError,
    MakemoreCase,
    MakemoreRule,
    MakemoreTargetContext,
    MakemoreTargetContextItem,
)


def _decode_target_context_refs(
    value: object,
    *,
    target_context: MakemoreTargetContext | None,
) -> tuple[str, ...]:
    if target_context is None:
        if value is not None and value != ():
            raise MakemoreError(
                "Makemore returned Target references without a Target frame."
            )
        return ()
    if (
        not isinstance(value, list)
        or any(not isinstance(alias, str) for alias in value)
        or len(value) != len(set(value))
        or not set(value).issubset(set(target_context.aliases))
    ):
        raise MakemoreError(
            "The Makemore provider returned invalid Target Context references."
        )
    return tuple(value)


def _referenced_target_memories(
    target_context: MakemoreTargetContext | None,
    cases: tuple[MakemoreCase, ...],
) -> tuple[MakemoreTargetContextItem, ...]:
    """Keep only ambient Memories the generated collection says it used."""

    if target_context is None:
        return ()
    referenced = {
        alias
        for case in cases
        for alias in case.target_context_refs
    }
    return tuple(
        item
        for item in target_context.items
        if item.kind == "MEMORY" and item.alias in referenced
    )


def _content_key(value: str) -> str:
    """Compare semantic-add content without insignificant spacing or case."""

    return " ".join(value.split()).casefold()


def _reject_target_restatements(
    *,
    target_context: MakemoreTargetContext | None,
    proposals: tuple[MakemoreRule | MakemoreCase, ...],
) -> None:
    """Fail before publication when a proposal merely repeats its Target."""

    if target_context is None:
        return
    target_alias_by_content = {
        _content_key(item.content): item.alias
        for item in target_context.items
        if item.kind == "MEMORY" and item.content is not None
    }
    restatements: list[str] = []
    label = (
        "Rule"
        if proposals and isinstance(proposals[0], MakemoreRule)
        else "Case"
    )
    for index, proposal in enumerate(proposals, 1):
        content = (
            proposal.content
            if isinstance(proposal, MakemoreRule)
            else proposal.proposition
        )
        alias = target_alias_by_content.get(_content_key(content))
        if alias is not None:
            restatements.append(f"{label} {index}: {alias}")
    if restatements:
        raise MakemoreError(
            "Makemore rejected proposals that repeat existing Target Memories "
            "(" + "; ".join(restatements) + ")."
        )
