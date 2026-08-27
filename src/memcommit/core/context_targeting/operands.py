"""Operation-neutral syntax helpers for Context endpoint operands."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.context_locator import resolve_context_locator
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.core.context_targeting.model import (
    ExistingContextOperand,
    InlineTextOperand,
)


ContextOrInlineTextOperand = ExistingContextOperand | InlineTextOperand


def classify_context_or_inline_text_operand(
    value: str,
    *,
    current: str | None,
    context_exists: Callable[[str], bool],
) -> ContextOrInlineTextOperand:
    """Classify only unambiguous non-Context text as process-local input.

    Existing names win even if a legacy store contains a name that current
    validation would reject.  Relative locator spellings and portable-looking
    absent names remain Context operands so a typo cannot silently become a
    provider-visible semantic statement.  Explicit operation options such as
    ``--memory`` remain the escape hatch for ambiguous one-word text.
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError("A Context or inline-text operand must be nonblank.")
    resolved = resolve_context_locator(value, current=current)
    if context_exists(resolved):
        return ExistingContextOperand(value)
    if value in {".", ".."} or value.startswith(("./", "../")):
        return ExistingContextOperand(value)
    try:
        validate_portable_context_name(value)
    except ValueError:
        return InlineTextOperand(value)
    return ExistingContextOperand(value)


def choose_endpoint_operand(
    positional: str | None,
    *,
    role: str,
    options: tuple[tuple[str, str | None], ...],
) -> str | None:
    """Choose one endpoint spelling without allowing silent precedence.

    Directional commands may expose both positional operands and explicit
    compatibility options. Mutation-capable adapters reject duplicate
    spellings before capturing current Context state so argv order cannot
    silently select a different Source, Target, Criteria, or Result.
    """

    supplied: list[tuple[str, str]] = []
    if positional is not None:
        supplied.append(("positionally", positional))
    supplied.extend((label, value) for label, value in options if value is not None)
    if len(supplied) > 1:
        labels = [label for label, _value in supplied]
        if labels[0] == "positionally":
            option_labels = " and ".join(labels[1:])
            raise ValueError(
                f"{role} was supplied both positionally and with " f"{option_labels}."
            )
        raise ValueError(
            f"{role} was supplied with more than one option: "
            + " and ".join(labels)
            + "."
        )
    return supplied[0][1] if supplied else None


__all__ = [
    "ContextOrInlineTextOperand",
    "choose_endpoint_operand",
    "classify_context_or_inline_text_operand",
]
