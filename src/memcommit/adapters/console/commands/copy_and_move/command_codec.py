"""Parse and project the exact editable Copy and Move commands."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.console.terminal.components.command_editor.model import CommandReview
from memcommit.adapters.console.terminal.components.direct_item_placement import DirectItemGap
from memcommit.application.capabilities.memory_transfer.application import (
    CopyMemoriesRequest,
    MoveMemoriesRequest,
    validate_copy_request,
    validate_move_request,
)


def parse_copy_and_move_command_argv(
    argv: Sequence[str],
    *,
    kind: str,
) -> CopyMemoriesRequest | MoveMemoriesRequest:
    """Parse the editable Copy/Move subset without invoking a nested CLI."""

    operation = kind.upper()
    if operation not in {"COPY", "MOVE"}:
        raise ValueError("Copy/Move kind must be COPY or MOVE.")
    expected = ("mem", operation.lower())
    values = tuple(argv)
    if values[:2] != expected:
        raise ValueError(
            f"Editable {operation.title()} commands must start with "
            f"'mem {operation.lower()}'."
        )
    operands: list[str] = []
    memory_options: list[str] = []
    options: dict[str, str] = {}
    switches: set[str] = set()
    value_flags = {"--memory", "-m", "--from", "--into", "--to", "--before", "--after"}
    switch_flags = (
        set()
        if operation == "COPY"
        else {"--retarget-links", "--break-links"}
    )
    index = 2
    while index < len(values):
        value = values[index]
        if value in switch_flags:
            if value in switches:
                raise ValueError(f"{operation.title()} flag '{value}' may be supplied only once.")
            switches.add(value)
            index += 1
            continue
        if value in value_flags:
            if index + 1 >= len(values) or values[index + 1].startswith("--"):
                raise ValueError(f"{operation.title()} flag '{value}' requires one value.")
            next_value = values[index + 1]
            if value in {"--memory", "-m"}:
                memory_options.append(next_value)
            else:
                if value in options:
                    raise ValueError(
                        f"{operation.title()} flag '{value}' may be supplied only once."
                    )
                options[value] = next_value
            index += 2
            continue
        if value.startswith("-"):
            raise ValueError(f"Unknown {operation.title()} flag '{value}'.")
        operands.append(value)
        index += 1

    if operands and memory_options:
        raise ValueError("Use positional MEMORY locators or repeat --memory, not both.")
    locators = tuple(operands or memory_options)
    if not locators:
        raise ValueError("Editable Copy/Move requires one or more Memories.")
    if "--into" in options and "--to" in options:
        raise ValueError("Use only one of --into or --to.")
    into = options.get("--into") or options.get("--to")
    if into is None:
        raise ValueError("Editable Copy/Move requires --into TARGET.")
    if "--before" in options and "--after" in options:
        raise ValueError("Pass only one of --before or --after.")
    if operation == "COPY":
        return validate_copy_request(
            CopyMemoriesRequest(
                memory_locators=locators,
                source_locator=options.get("--from"),
                into_locator=into,
                before=options.get("--before"),
                after=options.get("--after"),
            )
        )
    if "--retarget-links" in switches and "--break-links" in switches:
        raise ValueError("Pass only one of --retarget-links or --break-links.")
    return validate_move_request(
        MoveMemoriesRequest(
            memory_locators=locators,
            source_locator=options.get("--from"),
            into_locator=into,
            before=options.get("--before"),
            after=options.get("--after"),
            # Live Embeds follow ownership by default.  The retained
            # --retarget-links spelling is therefore a compatibility no-op.
            link_policy=("BREAK" if "--break-links" in switches else "RETARGET"),
        )
    )


def _placement_argv(gap: DirectItemGap, *, selector: str | None) -> tuple[str, ...]:
    if gap.next_uid is not None:
        return ("--before", selector or gap.next_uid)
    if gap.previous_uid is not None:
        return ("--after", selector or gap.previous_uid)
    return ()


def _gap_effect(gap: DirectItemGap, item_count: int) -> str:
    if gap.previous_uid is not None and gap.next_uid is not None:
        location = f"between [{gap.previous_uid[:8]}] and [{gap.next_uid[:8]}]"
    elif gap.next_uid is not None:
        location = f"before [{gap.next_uid[:8]}] at the start"
    elif gap.previous_uid is not None:
        location = f"after [{gap.previous_uid[:8]}] at the end"
    else:
        location = "as the only direct item"
    return f"Insert at gap {gap.position + 1}/{item_count + 1}, {location}."


def copy_and_move_exact_command_review(
    request: CopyMemoriesRequest | MoveMemoriesRequest,
    gap: DirectItemGap,
    *,
    item_count: int,
    placement_selector: str | None = None,
) -> CommandReview:
    """Build one exact command and its complete visible effect boundary."""

    if request.into_locator is None:
        raise ValueError("Select one Target Context first.")
    count = len(request.memory_locators)
    noun = "Memory" if count == 1 else "Memories"
    placement = _placement_argv(gap, selector=placement_selector)
    if isinstance(request, CopyMemoriesRequest):
        effects = (
            f"Copy {count} direct Source {noun} into '{request.into_locator}'.",
            (
                "Owned or READ-granted Sources stay unchanged; outputs "
                "receive new independent local UIDs."
            ),
            _gap_effect(gap, item_count),
        )
        argv = (
            "mem",
            "copy",
            *request.memory_locators,
            "--into",
            request.into_locator,
            *placement,
        )
    else:
        effects = (
            f"Move {count} directly owned {noun} into '{request.into_locator}'.",
            (
                "Live Memory Embeds may remain dangling by explicit request; snapshots stay unchanged."
                if request.link_policy == "BREAK"
                else "Every local live Memory Embed follows atomically; snapshots stay unchanged."
            ),
            _gap_effect(gap, item_count),
        )
        argv = (
            "mem",
            "move",
            *request.memory_locators,
            "--into",
            request.into_locator,
            *placement,
            *(("--break-links",) if request.link_policy == "BREAK" else ()),
        )
    return CommandReview(argv=argv, effects=effects)


__all__ = [
    "copy_and_move_exact_command_review",
    "parse_copy_and_move_command_argv",
]
