"""Encode and decode Merge's exact public command forms."""

from __future__ import annotations


from memcommit.adapters.console.terminal.components.command_editor import (
    CommandReview,
)


def build_start_review(
    *,
    mode: str,
    left_name: str | None,
    right_name: str,
    target_name: str | None = None,
    left_descendants: bool = False,
    right_descendants: bool = False,
    left_memory_uid: str | None = None,
    right_memory_uid: str | None = None,
    incoming_text: str | None = None,
) -> CommandReview:
    if incoming_text is not None:
        if mode.upper() != "DIRECTIONAL":
            raise ValueError("Inline Memory input requires directional Merge.")
        if left_descendants or left_memory_uid is not None:
            raise ValueError(
                "Inline Memory input cannot use INCOMING descendants or focus."
            )
        argv = ["mem", "merge", "--memory", incoming_text, "--into", right_name]
    else:
        if left_name is None:
            raise ValueError("Context Merge input requires one Source Context.")
        argv = ["mem", "merge", left_name, right_name]
    if mode.upper() == "SYMMETRIC":
        if target_name is None:
            raise ValueError("Symmetric Merge requires a result Context.")
        argv.extend(("--to", target_name))
    elif mode.upper() != "DIRECTIONAL":
        raise ValueError("Unsupported Merge command mode.")
    if left_descendants:
        argv.append("--left-descendants")
    if right_descendants:
        argv.append("--right-descendants")
    if left_memory_uid is not None:
        argv.extend(("--incoming-memory", left_memory_uid))
    if right_memory_uid is not None:
        argv.extend(("--baseline-memory", right_memory_uid))
    return CommandReview(
        tuple(argv),
        (
            "Start or resume the exact Merge analysis and saved review session shown.",
            "Do not apply the Merge target; final Apply remains separate.",
        ),
    )


def build_turn_review(
    *,
    left_name: str,
    right_name: str,
    target_name: str | None,
    left_descendants: bool,
    right_descendants: bool,
    left_memory_uid: str | None,
    right_memory_uid: str | None,
    incoming_text: str | None = None,
    expected_session: str,
    issue_uid: str | None = None,
    option_number: int | None = None,
    comment: str = "",
    preserve_all: bool = False,
    defer_all: bool = False,
) -> CommandReview:
    start = build_start_review(
        mode="SYMMETRIC" if target_name is not None else "DIRECTIONAL",
        left_name=left_name,
        right_name=right_name,
        target_name=target_name,
        left_descendants=left_descendants,
        right_descendants=right_descendants,
        left_memory_uid=left_memory_uid,
        right_memory_uid=right_memory_uid,
        incoming_text=incoming_text,
    )
    argv = list(start.argv)
    if preserve_all:
        argv.append("--preserve-all")
    elif defer_all:
        argv.append("--defer-all")
    else:
        if issue_uid is not None:
            argv.extend(("--issue", issue_uid))
        if option_number is not None:
            argv.extend(("--choice", str(option_number)))
        if comment:
            argv.extend(("--comment", comment))
    argv.extend(("--expect-session", expected_session))
    return CommandReview(
        tuple(argv),
        (
            "Submit one semantic Merge turn against the exact displayed session revision.",
            "Rebuild the saved proposal; do not apply the target.",
        ),
    )


__all__ = [
    "build_start_review",
    "build_turn_review",
]
