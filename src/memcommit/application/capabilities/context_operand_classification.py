"""Application classification for Context-or-inline-text operands."""

from __future__ import annotations

from collections.abc import Callable

from memcommit.application.capabilities.context_locator import resolve_context_locator
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
    validation would reject. Relative locator spellings and portable-looking
    absent names remain Context operands so a typo cannot silently become a
    provider-visible semantic statement. Explicit operation options such as
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


__all__ = [
    "ContextOrInlineTextOperand",
    "classify_context_or_inline_text_operand",
]
