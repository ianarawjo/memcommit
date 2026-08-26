"""Canonical argv builders shared by semantic-session TUI adapters."""

from __future__ import annotations

from memcommit.exact_command_review import ExactCommandReview


def meld_start_command_review(
    *,
    mode: str,
    left_name: str,
    right_name: str,
    target_name: str | None = None,
    left_descendants: bool = False,
    right_descendants: bool = False,
    left_memory_uid: str | None = None,
    right_memory_uid: str | None = None,
    incoming_text: str | None = None,
) -> ExactCommandReview:
    if incoming_text is not None:
        if mode.upper() != "DIRECTIONAL":
            raise ValueError("Inline Memory input requires directional Meld.")
        if left_descendants or left_memory_uid is not None:
            raise ValueError(
                "Inline Memory input cannot use INCOMING descendants or focus."
            )
        argv = ["mem", "meld", "--memory", incoming_text, "--into", right_name]
    else:
        argv = ["mem", "meld", left_name, right_name]
    if mode.upper() == "SYMMETRIC":
        if target_name is None:
            raise ValueError("Symmetric Meld requires a result Context.")
        argv.extend(("--to", target_name))
    elif mode.upper() != "DIRECTIONAL":
        raise ValueError("Unsupported Meld command mode.")
    if left_descendants:
        argv.append("--left-descendants")
    if right_descendants:
        argv.append("--right-descendants")
    if left_memory_uid is not None:
        argv.extend(("--incoming-memory", left_memory_uid))
    if right_memory_uid is not None:
        argv.extend(("--baseline-memory", right_memory_uid))
    return ExactCommandReview(
        tuple(argv),
        (
            "Start or resume the exact Meld analysis and saved review session shown.",
            "Do not apply the Meld target; final Apply remains separate.",
        ),
    )


def update_start_command_review(
    *,
    source_name: str,
    target_name: str,
    source_descendants: bool = False,
    target_descendants: bool = False,
    source_memory_uid: str | None = None,
    target_memory_uid: str | None = None,
    inline_source_content: str | None = None,
) -> ExactCommandReview:
    if inline_source_content is not None:
        if source_descendants or source_memory_uid is not None:
            raise ValueError(
                "Inline Update input cannot use Source descendants or focus."
            )
        argv = [
            "mem",
            "update",
            "--memory",
            inline_source_content,
            "--to",
            target_name,
        ]
    else:
        argv = ["mem", "update", "--from", source_name, "--to", target_name]
    if source_descendants:
        argv.append("--source-descendants")
    if target_descendants:
        argv.append("--target-descendants")
    if source_memory_uid is not None:
        argv.extend(("--source-memory", source_memory_uid))
    if target_memory_uid is not None:
        argv.extend(("--target-memory", target_memory_uid))
    return ExactCommandReview(
        tuple(argv),
        (
            "Start or resume the exact Update plan and saved review session shown.",
            "Do not apply target changes; final Apply remains separate.",
        ),
    )


def sever_start_command_review(
    *,
    source_name: str,
    criteria_name: str,
    output_name: str,
    source_descendants: bool = False,
    criteria_descendants: bool = False,
) -> ExactCommandReview:
    argv = ["mem", "sever", source_name, criteria_name]
    if output_name != source_name:
        argv.append(output_name)
    if source_descendants:
        argv.append("--source-descendants")
    if criteria_descendants:
        argv.append("--criteria-descendants")
    return ExactCommandReview(
        tuple(argv),
        (
            "Start or resume the exact Sever analysis and saved review session shown.",
            "Do not save the Result; final self-save or other-save Apply remains separate.",
        ),
    )


def meld_turn_command_review(
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
) -> ExactCommandReview:
    start = meld_start_command_review(
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
    return ExactCommandReview(
        tuple(argv),
        (
            "Submit one semantic Meld turn against the exact displayed session revision.",
            "Rebuild the saved proposal; do not apply the target.",
        ),
    )


def update_turn_command_review(
    *,
    source_name: str,
    target_name: str,
    source_descendants: bool,
    target_descendants: bool,
    source_memory_uid: str | None,
    target_memory_uid: str | None,
    comment: str,
    expected_session: str,
    inline_source_content: str | None = None,
) -> ExactCommandReview:
    start = update_start_command_review(
        source_name=source_name,
        target_name=target_name,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
        source_memory_uid=source_memory_uid,
        target_memory_uid=target_memory_uid,
        inline_source_content=inline_source_content,
    )
    return ExactCommandReview(
        (*start.argv, "--comment", comment, "--expect-session", expected_session),
        (
            "Submit one semantic Update revision against the exact displayed session.",
            "Replace the staged plan; do not apply target changes.",
        ),
    )


def sever_turn_command_review(
    *,
    session_uid: str,
    candidate_uid: str,
    choice: str,
    expected_session: str,
    comment: str = "",
) -> ExactCommandReview:
    argv = [
        "mem",
        "sever",
        "--resume",
        session_uid,
        "--candidate",
        candidate_uid,
        "--choice",
        choice,
    ]
    if comment:
        argv.extend(("--comment", comment))
    argv.extend(("--expect-session", expected_session))
    return ExactCommandReview(
        tuple(argv),
        (
            "Save one Sever candidate decision against the exact displayed session revision.",
            "Do not create the output Context; final Apply remains separate.",
        ),
    )


__all__ = [
    "meld_start_command_review",
    "meld_turn_command_review",
    "sever_start_command_review",
    "sever_turn_command_review",
    "update_start_command_review",
    "update_turn_command_review",
]
