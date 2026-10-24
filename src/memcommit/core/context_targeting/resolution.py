"""Parse Context and Memory locator operands without reading storage."""

from __future__ import annotations


from memcommit.core.context_targeting.uid_locator import is_memory_uid_selector
from memcommit.core.context_targeting.model import DirectMemoryLocator


DIRECT_MEMORY_LOCATOR_SEPARATOR = ":"


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
        DIRECT_MEMORY_LOCATOR_SEPARATOR in operand or is_memory_uid_selector(operand)
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
) -> str | DirectMemoryLocator:
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
    return operand
