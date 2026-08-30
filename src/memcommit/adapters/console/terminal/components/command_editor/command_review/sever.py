"""Project Sever setup and saved-session turns to reviewable commands."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.command_editor.command_review.model import CommandReview


def build_start_review(
    *,
    source_name: str,
    criteria_name: str,
    output_name: str,
    source_descendants: bool = False,
    criteria_descendants: bool = False,
) -> CommandReview:
    argv = ["mem", "sever", source_name, criteria_name]
    if output_name != source_name:
        argv.append(output_name)
    if source_descendants:
        argv.append("--source-descendants")
    if criteria_descendants:
        argv.append("--criteria-descendants")
    return CommandReview(
        tuple(argv),
        (
            "Start or resume the exact Sever analysis and saved review session shown.",
            "Do not save the Result; final self-save or other-save Apply remains separate.",
        ),
    )


def build_turn_review(
    *,
    session_uid: str,
    candidate_uid: str,
    choice: str,
    expected_session: str,
    comment: str = "",
) -> CommandReview:
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
    return CommandReview(
        tuple(argv),
        (
            "Save one Sever candidate decision against the exact displayed session revision.",
            "Do not create the output Context; final Apply remains separate.",
        ),
    )


__all__ = ["build_start_review", "build_turn_review"]
