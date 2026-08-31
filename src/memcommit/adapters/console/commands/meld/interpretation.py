"""Interpret Meld CLI forms into one canonical console command."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Literal

from memcommit.application.capabilities.context_operand_classification import (
    classify_context_or_inline_text_operand,
)
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.meld.model import INLINE_MELD_CONTEXT_NAME
from memcommit.core.context_targeting.model import InlineTextOperand
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.persistence.store import MemoryStore

from memcommit.adapters.console.commands.meld.errors import MeldCommandError


MeldCommandAction = Literal[
    "NONE",
    "RESPONSE",
    "PRESERVE_ALL",
    "DEFER_ALL",
    "ACCEPT",
    "RESTART",
]


class MeldCommandInterpretationError(ValueError):
    """Raw Meld options do not form one valid CLI command."""


@dataclass(frozen=True)
class MeldCommandRequest:
    """Raw Typer values at the Meld command-interpretation boundary."""

    left: str | None
    right: str | None
    result: str | None
    into: str | None
    to: str | None
    from_: str | None
    issue: str | None
    choice: int | None
    comment: str | None
    expect_session: str | None
    preserve_all: bool
    defer_all: bool
    accept: bool
    restart: bool
    revision: str | None
    revises_turn: tuple[str, ...]
    expand: str | None
    sessions: bool
    direct: bool
    recursive: bool
    left_descendants: bool | None
    right_descendants: bool | None
    memory: str | None
    incoming_memory: str | None
    baseline_memory: str | None


@dataclass(frozen=True)
class MeldSetupCommand:
    """A bare invocation that enters new-Meld setup."""


@dataclass(frozen=True)
class MeldSessionsCommand:
    """An explicit invocation that browses saved Meld sessions."""


@dataclass(frozen=True)
class InterpretedMeldCommand:
    """One canonical non-launcher Meld command, independent of CLI aliases."""

    mode: Literal["SYMMETRIC", "DIRECTIONAL"]
    left_name: str
    right_name: str
    target_name: str
    current_name: str | None
    start_command: str
    left_descendants: bool
    right_descendants: bool
    incoming_text: str | None
    incoming_memory: str | None
    baseline_memory: str | None
    action: MeldCommandAction
    issue: str | None
    choice: int | None
    comment: str | None
    expect_session: str | None
    revision: str | None
    revises_turn: tuple[str, ...]
    expand: str | None


MeldCommandInterpretation = (
    MeldSetupCommand | MeldSessionsCommand | InterpretedMeldCommand
)


def _usage_error(message: str) -> MeldCommandInterpretationError:
    return MeldCommandInterpretationError(message)


def _is_inline_memory_operand(
    store: MemoryStore,
    value: str,
    *,
    current_name: str | None,
) -> bool:
    """Classify only unambiguously non-Context one-operand text as Memory."""

    return isinstance(
        classify_context_or_inline_text_operand(
            value,
            current=current_name,
            context_exists=store.context_exists,
        ),
        InlineTextOperand,
    )


def _interpret_action(request: MeldCommandRequest) -> MeldCommandAction:
    actions = (
        (request.comment is not None or request.choice is not None, "RESPONSE"),
        (request.preserve_all, "PRESERVE_ALL"),
        (request.defer_all, "DEFER_ALL"),
        (request.accept, "ACCEPT"),
        (request.restart, "RESTART"),
    )
    selected = tuple(label for enabled, label in actions if enabled)
    if len(selected) > 1:
        raise _usage_error(
            "use one comment, preserve, defer, accept, or restart action."
        )
    return selected[0] if selected else "NONE"  # type: ignore[return-value]


def interpret_meld_command(
    request: MeldCommandRequest,
    *,
    store: MemoryStore,
) -> MeldCommandInterpretation:
    """Resolve every Meld CLI spelling against one current-Context snapshot."""

    scope_flags_supplied = (
        request.direct
        or request.recursive
        or request.left_descendants is not None
        or request.right_descendants is not None
    )
    try:
        preset = resolve_scope_preset(
            direct=request.direct,
            recursive=request.recursive,
            default=ContextScopePreset.DIRECT,
        )
        left_descendants, right_descendants = resolve_descendant_scopes(
            preset=preset,
            explicit=(request.left_descendants, request.right_descendants),
        )
    except (TypeError, ValueError) as error:
        raise _usage_error(str(error)) from error

    action = _interpret_action(request)
    if request.expand is not None and action != "NONE":
        raise _usage_error(
            "--expand cannot be combined with a semantic or terminal action."
        )
    if request.choice is not None and request.issue is None:
        raise _usage_error("--choice requires --issue.")
    if request.issue is not None and request.comment is None and request.choice is None:
        raise _usage_error("--issue requires --comment or --choice.")
    if (request.revision is not None or request.revises_turn) and action != "RESPONSE":
        raise _usage_error("--revision and --revises-turn require a comment or choice.")
    if request.expect_session is not None and action not in {
        "RESPONSE",
        "PRESERVE_ALL",
        "DEFER_ALL",
    }:
        raise _usage_error(
            "--expect-session is valid only for a semantic or defer turn."
        )

    to_is_symmetric = (
        request.to is not None
        and request.left is not None
        and request.right is not None
    )
    directional_to = (
        request.to if request.to is not None and not to_is_symmetric else None
    )
    if request.from_ is not None and request.into is not None:
        raise _usage_error(
            "--from and --into are alternative directional spellings and "
            "cannot be combined."
        )
    if request.result is not None and request.to is not None:
        raise _usage_error(
            "supply symmetric RESULT C either positionally or with --to, not both."
        )
    if directional_to is not None and request.into is not None:
        raise _usage_error(
            "directional BASELINE cannot be supplied with both --into and --to."
        )
    if (to_is_symmetric or request.result is not None) and (
        request.into is not None or request.from_ is not None
    ):
        raise _usage_error(
            "symmetric RESULT C/--to cannot be combined with directional "
            "--into or --from."
        )
    if request.from_ is not None and any(
        value is not None for value in (request.left, request.right, request.result)
    ):
        raise _usage_error(
            "--from supplies INCOMING and cannot be combined with positional Contexts."
        )
    if request.memory is not None and any(
        value is not None
        for value in (
            request.left,
            request.right,
            request.result,
            (request.to if to_is_symmetric else None),
            request.from_,
            request.incoming_memory,
        )
    ):
        raise _usage_error(
            "--memory supplies INCOMING content and cannot be combined with "
            "positional sources, symmetric RESULT, --from, or --incoming-memory."
        )

    browse_by_default = (
        request.left is None
        and request.right is None
        and request.result is None
        and request.into is None
        and request.to is None
        and request.from_ is None
        and request.issue is None
        and request.choice is None
        and request.comment is None
        and action == "NONE"
        and not left_descendants
        and not right_descendants
        and request.incoming_memory is None
        and request.baseline_memory is None
        and request.memory is None
        and request.revision is None
        and not request.revises_turn
        and request.expect_session is None
        and request.expand is None
        and not scope_flags_supplied
    )
    if request.sessions and not browse_by_default:
        raise _usage_error(
            "--sessions cannot be combined with source operands or Meld actions."
        )
    if request.sessions:
        return MeldSessionsCommand()
    if browse_by_default:
        return MeldSetupCommand()

    current_name = store.current_context_name()
    explicit_result = (
        request.result
        if request.result is not None
        else (request.to if to_is_symmetric else None)
    )
    directional_baseline = request.into if request.into is not None else directional_to
    incoming_text = request.memory
    if incoming_text is not None:
        mode: Literal["SYMMETRIC", "DIRECTIONAL"] = "DIRECTIONAL"
        if left_descendants:
            raise MeldCommandError(
                "Inline --memory cannot be combined with INCOMING descendants."
            )
        left_name = INLINE_MELD_CONTEXT_NAME
        if directional_baseline is not None:
            right_name = resolve_context_locator(
                directional_baseline,
                current=current_name,
            )
        else:
            if not current_name:
                raise MeldCommandError(
                    "Inline --memory uses the current Context as BASELINE, "
                    "but no current Context is available. Supply --into or "
                    "--to BASELINE."
                )
            right_name = current_name
        target_name = right_name
    elif request.from_ is not None:
        if directional_baseline is None and not current_name:
            raise MeldCommandError(
                "No current BASELINE Context. Switch to the intended baseline "
                "before using --from, or supply --to BASELINE."
            )
        mode = "DIRECTIONAL"
        parsed_from = classify_context_or_inline_text_operand(
            request.from_,
            current=current_name,
            context_exists=store.context_exists,
        )
        if isinstance(parsed_from, InlineTextOperand):
            incoming_text = parsed_from.text
            left_name = INLINE_MELD_CONTEXT_NAME
        else:
            left_name = resolve_context_locator(
                parsed_from.locator,
                current=current_name,
            )
        right_name = (
            resolve_context_locator(
                directional_baseline,
                current=current_name,
            )
            if directional_baseline is not None
            else current_name
        )
        assert right_name is not None
        target_name = right_name
    elif directional_baseline is not None:
        if request.right is not None or request.result is not None:
            raise MeldCommandError(
                "Directional --into/--to accepts at most one positional INCOMING "
                "Context. Use 'mem meld INCOMING BASELINE' instead."
            )
        mode = "DIRECTIONAL"
        if request.left is None:
            if not current_name:
                raise MeldCommandError(
                    "No current INCOMING Context. Supply one explicitly or "
                    "switch to it before using --into/--to."
                )
            left_name = current_name
        else:
            parsed_left = classify_context_or_inline_text_operand(
                request.left,
                current=current_name,
                context_exists=store.context_exists,
            )
            if isinstance(parsed_left, InlineTextOperand):
                incoming_text = parsed_left.text
                left_name = INLINE_MELD_CONTEXT_NAME
            else:
                left_name = resolve_context_locator(
                    parsed_left.locator,
                    current=current_name,
                )
        right_name = resolve_context_locator(
            directional_baseline,
            current=current_name,
        )
        target_name = right_name
    elif explicit_result is not None:
        if request.left is None or request.right is None:
            raise MeldCommandError(
                "Symmetric Meld requires PEER A and PEER B before RESULT C. "
                "Use 'mem meld PEER_A PEER_B --to RESULT_C' or "
                "'mem meld PEER_A PEER_B RESULT_C'."
            )
        mode = "SYMMETRIC"
        left_name = resolve_context_locator(request.left, current=current_name)
        right_name = resolve_context_locator(request.right, current=current_name)
        # RESULT C may be new, so existing-Context relative locator semantics
        # deliberately do not apply to its exact requested name.
        target_name = explicit_result
    elif request.left is not None and request.right is not None:
        mode = "DIRECTIONAL"
        left_name = resolve_context_locator(request.left, current=current_name)
        right_name = resolve_context_locator(request.right, current=current_name)
        target_name = right_name
    elif request.left is not None:
        if not current_name:
            raise MeldCommandError(
                "'mem meld INCOMING' uses the current Context as BASELINE, "
                "but no current Context is available. Supply "
                "'mem meld INCOMING BASELINE'."
            )
        mode = "DIRECTIONAL"
        if _is_inline_memory_operand(
            store,
            request.left,
            current_name=current_name,
        ):
            incoming_text = request.left
            if left_descendants:
                raise MeldCommandError(
                    "Inline Memory input cannot be combined with INCOMING descendants."
                )
            left_name = INLINE_MELD_CONTEXT_NAME
        else:
            left_name = resolve_context_locator(request.left, current=current_name)
        right_name = current_name
        target_name = right_name
    else:
        raise MeldCommandError(
            "Starting Meld requires INCOMING, INCOMING BASELINE, or "
            "PEER_A PEER_B RESULT_C Contexts."
        )

    if mode == "DIRECTIONAL":
        if request.incoming_memory is not None and left_descendants:
            raise MeldCommandError(
                "--incoming-memory cannot be combined with --left-descendants."
            )
        if request.baseline_memory is not None and right_descendants:
            raise MeldCommandError(
                "--baseline-memory cannot be combined with --right-descendants."
            )
        start_parts = (
            ["mem", "meld", "--memory", incoming_text, "--into", right_name]
            if incoming_text is not None
            else ["mem", "meld", left_name, right_name]
        )
        if left_descendants:
            start_parts.append("--left-descendants")
        if right_descendants:
            start_parts.append("--right-descendants")
        if request.incoming_memory is not None:
            start_parts.extend(("--incoming-memory", request.incoming_memory))
        if request.baseline_memory is not None:
            start_parts.extend(("--baseline-memory", request.baseline_memory))
    else:
        if request.incoming_memory is not None or request.baseline_memory is not None:
            raise MeldCommandError(
                "Memory scope flags are supported only by directional Meld."
            )
        start_parts = ["mem", "meld", left_name]
        if left_descendants:
            start_parts.append("--left-descendants")
        start_parts.append(right_name)
        if right_descendants:
            start_parts.append("--right-descendants")
        start_parts.extend(("--to", target_name))
    start_command = shlex.join(start_parts)

    if left_name == right_name:
        if mode == "DIRECTIONAL":
            raise MeldCommandError(
                "Directional Meld requires different INCOMING and BASELINE "
                f"Contexts; both resolved to '{left_name}'."
            )
        raise MeldCommandError("The two PEER source Contexts must be distinct.")
    if mode == "SYMMETRIC" and target_name in {left_name, right_name}:
        raise MeldCommandError(
            "Symmetric Meld requires PEER A, PEER B, and RESULT C to be "
            f"distinct; RESULT '{target_name}' is also a PEER source."
        )

    return InterpretedMeldCommand(
        mode=mode,
        left_name=left_name,
        right_name=right_name,
        target_name=target_name,
        current_name=current_name,
        start_command=start_command,
        left_descendants=left_descendants,
        right_descendants=right_descendants,
        incoming_text=incoming_text,
        incoming_memory=request.incoming_memory,
        baseline_memory=request.baseline_memory,
        action=action,
        issue=request.issue,
        choice=request.choice,
        comment=request.comment,
        expect_session=request.expect_session,
        revision=request.revision,
        revises_turn=request.revises_turn,
        expand=request.expand,
    )


__all__ = [
    "InterpretedMeldCommand",
    "MeldCommandAction",
    "MeldCommandInterpretation",
    "MeldCommandInterpretationError",
    "MeldCommandRequest",
    "MeldSessionsCommand",
    "MeldSetupCommand",
    "interpret_meld_command",
]
