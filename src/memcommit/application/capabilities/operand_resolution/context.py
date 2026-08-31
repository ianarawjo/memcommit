"""Resolve existing Context operands against one caller-authorized catalog.

This module owns interpretation order, not authority discovery.  A caller
freezes the Context identities that its operation may disclose and supplies
them here.  Exact or relative public names win, then an exact or unique public
UID prefix may select one identity.  Only operations whose grammar explicitly
allows prose may use the final inline-text fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from memcommit.application.capabilities.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)
from memcommit.application.capabilities.durable_uid_resolution import (
    DurableUidAmbiguityError,
    DurableUidCandidate,
    is_unresolved_uid_selector,
    try_resolve_durable_uid,
)
from memcommit.core.context import Context
from memcommit.core.context_targeting.model import ContextTarget, InlineTextOperand
from memcommit.core.context_targeting.naming import validate_portable_context_name


T = TypeVar("T")


class ContextOperandResolutionError(ValueError):
    """An existing Context operand cannot be resolved safely."""


class ContextOperandNotFoundError(ContextOperandResolutionError, FileNotFoundError):
    """No Context in the frozen candidate catalog matches the operand."""


class ContextOperandAmbiguityError(ContextOperandResolutionError):
    """One operand names more than one public Context route or identity."""


@dataclass(frozen=True, slots=True)
class ContextOperandCandidate(Generic[T]):
    """One authorized public Context identity and its caller-owned value."""

    uid: str
    name: str
    value: T

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise ContextOperandResolutionError(
                "Context operand candidates require a UID."
            )
        if not isinstance(self.name, str) or not self.name:
            raise ContextOperandResolutionError(
                "Context operand candidates require a canonical public name."
            )


@dataclass(frozen=True, slots=True)
class ResolvedExistingContextOperand(Generic[T]):
    """One raw selector bound to an exact Context UID and public name."""

    selector: str
    uid: str
    name: str
    value: T


class LocalContextOperandStore(Protocol):
    """Strict ordinary-local Context catalog used by local-only operations."""

    def load_direct_context_graph_strict(self) -> tuple[Context, ...]: ...


def _frozen_candidates(
    candidates: tuple[ContextOperandCandidate[T], ...],
) -> tuple[ContextOperandCandidate[T], ...]:
    frozen = tuple(candidates)
    names = tuple(candidate.name for candidate in frozen)
    if len(names) != len(set(names)):
        raise ContextOperandResolutionError(
            "Context operand candidate public names must be distinct."
        )
    return frozen


def _resolved(
    selector: str,
    candidate: ContextOperandCandidate[T],
) -> ResolvedExistingContextOperand[T]:
    return ResolvedExistingContextOperand(
        selector=selector,
        uid=candidate.uid,
        name=candidate.name,
        value=candidate.value,
    )


def try_resolve_existing_context_operand(
    candidates: tuple[ContextOperandCandidate[T], ...],
    operand: str,
    *,
    current: str | None,
) -> ResolvedExistingContextOperand[T] | None:
    """Resolve name first, then one UID inside the frozen candidate frame.

    Missing values return ``None`` so a caller with a typed multi-kind grammar
    may continue into its Memory or artifact candidate frame.  A caller whose
    only remaining fallback is prose or a new name must use one of this
    module's required wrappers, which fails an unmatched UUID-shaped value
    closed instead of changing its semantic kind.
    """

    if not isinstance(operand, str) or not operand:
        raise ContextOperandResolutionError(
            "An existing Context operand must be nonempty text."
        )
    frozen = _frozen_candidates(candidates)
    canonical_name = resolve_context_locator(operand, current=current)
    named = tuple(
        candidate for candidate in frozen if candidate.name == canonical_name
    )
    if len(named) == 1:
        return _resolved(operand, named[0])
    if len(named) > 1:
        raise ContextOperandAmbiguityError(
            f"Context name {canonical_name!r} has multiple authorized identities."
        )

    if not is_unresolved_uid_selector(operand):
        return None
    try:
        identity = try_resolve_durable_uid(
            tuple(
                DurableUidCandidate(
                    uid=candidate.uid,
                    kind="context",
                    value=candidate,
                )
                for candidate in frozen
            ),
            operand,
        )
    except DurableUidAmbiguityError as error:
        raise ContextOperandAmbiguityError(str(error)) from error
    if identity is None:
        return None
    routes = tuple(dict.fromkeys(candidate.name for candidate in identity.values))
    if len(routes) != 1:
        rendered = ", ".join(repr(name) for name in routes)
        raise ContextOperandAmbiguityError(
            f"Context UID {operand!r} is available through multiple public "
            f"routes ({rendered}); pass one exact Context name."
        )
    candidate = identity.values[0]
    return _resolved(operand, candidate)


def resolve_existing_context_operand(
    candidates: tuple[ContextOperandCandidate[T], ...],
    operand: str,
    *,
    current: str | None,
) -> ResolvedExistingContextOperand[T]:
    """Require one existing Context selected by name, relative locator, or UID."""

    resolved = try_resolve_existing_context_operand(
        candidates,
        operand,
        current=current,
    )
    if resolved is not None:
        return resolved
    canonical_name = resolve_context_locator(operand, current=current)
    if is_unresolved_uid_selector(operand):
        raise ContextOperandNotFoundError(
            f"Context UID {operand!r} is unavailable in this authorized view."
        )
    raise ContextOperandNotFoundError(
        f"Context {canonical_name!r} does not exist in this authorized view."
    )


def resolve_context_or_inline_text_operand(
    candidates: tuple[ContextOperandCandidate[T], ...],
    operand: str,
    *,
    current: str | None,
) -> ResolvedExistingContextOperand[T] | InlineTextOperand:
    """Use inline text only after existing Context name and UID interpretation.

    Relative locators and portable-looking names are explicit Context syntax.
    Their absence therefore remains a Context error.  Nonportable prose may be
    returned as inline text, while an operation-specific ``--memory`` or
    ``text:`` route remains the unambiguous way to force short literal content.
    """

    resolved = try_resolve_existing_context_operand(
        candidates,
        operand,
        current=current,
    )
    if resolved is not None:
        return resolved
    if is_unresolved_uid_selector(operand):
        return resolve_existing_context_operand(
            candidates,
            operand,
            current=current,
        )
    if is_relative_context_locator(operand):
        return resolve_existing_context_operand(
            candidates,
            operand,
            current=current,
        )
    try:
        validate_portable_context_name(operand)
    except ValueError:
        return InlineTextOperand(operand)
    return resolve_existing_context_operand(
        candidates,
        operand,
        current=current,
    )


def freeze_local_context_operand_candidates(
    store: LocalContextOperandStore,
) -> tuple[ContextOperandCandidate[ContextTarget], ...]:
    """Freeze every strict ordinary-local Context as one typed target catalog."""

    return tuple(
        ContextOperandCandidate(
            uid=context.uid,
            name=context.name,
            value=ContextTarget(context.name),
        )
        for context in store.load_direct_context_graph_strict()
    )


__all__ = [
    "ContextOperandAmbiguityError",
    "ContextOperandCandidate",
    "ContextOperandNotFoundError",
    "ContextOperandResolutionError",
    "ResolvedExistingContextOperand",
    "freeze_local_context_operand_candidates",
    "resolve_context_or_inline_text_operand",
    "resolve_existing_context_operand",
    "try_resolve_existing_context_operand",
]
