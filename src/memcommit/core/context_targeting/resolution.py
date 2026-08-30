"""Pure namespace resolution shared by Context scope loaders."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.core.context_targeting.uid_locator import is_memory_uid_selector
from memcommit.core.context_targeting.model import (
    ContextScope,
    DirectMemoryLocator,
    ExistingContextOperand,
)


DIRECT_MEMORY_LOCATOR_SEPARATOR = ":"


AutoTypedContextMemoryOperand = ExistingContextOperand | DirectMemoryLocator


def is_direct_memory_locator_operand(
    operand: object,
    *,
    explicit_context: str | None = None,
) -> bool:
    """Return whether one overloaded CLI operand explicitly selects Memory.

    A Context option or the reserved ``CONTEXT:UID`` separator is an explicit
    type marker. A bare operand enters Memory mode only when it has the public
    eight-or-more-character UUID-prefix shape reserved from new Context names.
    """

    if explicit_context is not None:
        return True
    return isinstance(operand, str) and (
        DIRECT_MEMORY_LOCATOR_SEPARATOR in operand
        or is_memory_uid_selector(operand)
    )


def parse_direct_memory_locator(
    operand: object,
    *,
    explicit_context: str | None = None,
) -> DirectMemoryLocator:
    """Parse ``UID`` or ``CONTEXT:UID`` without consulting storage.

    Context names have always forbidden ``:``, so one separator provides a
    stable owner boundary for portable and legacy stores. An operation's
    existing Context option remains a compatibility spelling, but the two
    owner forms cannot be combined.
    """

    if not isinstance(operand, str) or not operand:
        raise ValueError("A direct Memory locator must be nonempty text.")
    separator_count = operand.count(DIRECT_MEMORY_LOCATOR_SEPARATOR)
    if separator_count == 0:
        return DirectMemoryLocator(
            memory_selector=operand,
            context_locator=explicit_context,
        )
    if separator_count != 1:
        raise ValueError(
            "A qualified Memory locator must use exactly one CONTEXT:UID separator."
        )
    context_locator, memory_selector = operand.split(
        DIRECT_MEMORY_LOCATOR_SEPARATOR,
        1,
    )
    if not context_locator or not memory_selector:
        raise ValueError("A qualified Memory locator must be CONTEXT:UID.")
    if explicit_context is not None:
        raise ValueError(
            "Use either CONTEXT:UID or an explicit Context option, not both."
        )
    return DirectMemoryLocator(
        memory_selector=memory_selector,
        context_locator=context_locator,
    )


def parse_auto_typed_context_memory_operand(
    operand: object,
    *,
    explicit_memory_context: str | None = None,
) -> AutoTypedContextMemoryOperand:
    """Classify one shared positional Context/direct-Memory operand.

    New Context roots reserve the public UUID-prefix shape and Context names
    cannot contain ``:``, so classification is storage-independent.  An
    explicit Memory owner makes even a short selector unambiguously Memory.
    Callers canonicalize the returned Context locator or resolve the returned
    Memory locator under their own authority and loading rules.
    """

    if not isinstance(operand, str) or not operand:
        raise ValueError("An automatic Context/Memory operand must be nonempty text.")
    if is_direct_memory_locator_operand(
        operand,
        explicit_context=explicit_memory_context,
    ):
        return parse_direct_memory_locator(
            operand,
            explicit_context=explicit_memory_context,
        )
    return ExistingContextOperand(operand)


def order_context_names_by_hierarchy(
    catalog_names: Sequence[str],
) -> tuple[str, ...]:
    """Project a frozen public catalog in depth-first namespace order.

    Siblings retain catalog order. This lets a caller append virtual Grant
    rows after ordinary local rows while still placing both beneath their
    nearest real public-name parent, matching the shared Context tree without
    importing terminal state into a static command.
    """

    catalog = tuple(catalog_names)
    if len(set(catalog)) != len(catalog) or any(
        not isinstance(name, str) or not name for name in catalog
    ):
        raise ValueError("Context hierarchy catalog must contain distinct names.")
    catalog_set = frozenset(catalog)
    children: dict[str | None, list[str]] = {None: []}
    for name in catalog:
        segments = name.split("/")
        parent = next(
            (
                "/".join(segments[:length])
                for length in range(len(segments) - 1, 0, -1)
                if "/".join(segments[:length]) in catalog_set
            ),
            None,
        )
        children.setdefault(parent, []).append(name)
        children.setdefault(name, [])

    ordered: list[str] = []
    pending = list(reversed(children[None]))
    while pending:
        name = pending.pop()
        ordered.append(name)
        pending.extend(reversed(children[name]))
    return tuple(ordered)


def expand_lexical_context_names(
    scope: ContextScope,
    catalog_names: Sequence[str],
) -> tuple[str, ...]:
    """Expand targets to canonical lexical descendants in catalog order.

    This function resolves only public Context names.  It neither follows
    embedded graph edges nor interprets Grant attachments as hierarchy edges.
    Callers retain their own authority checks and loading semantics.
    """

    catalog = tuple(catalog_names)
    if len(set(catalog)) != len(catalog) or any(
        not isinstance(name, str) or not name for name in catalog
    ):
        raise ValueError("Context scope catalog must contain distinct names.")
    expanded: list[str] = []
    for target_name in scope.target_names:
        expanded.append(target_name)
        if scope.include_descendants:
            prefix = target_name + "/"
            expanded.extend(name for name in catalog if name.startswith(prefix))
    return tuple(dict.fromkeys(expanded))
