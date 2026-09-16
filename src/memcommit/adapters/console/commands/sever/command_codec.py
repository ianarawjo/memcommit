"""Encode and decode Sever's exact public command forms."""

from __future__ import annotations


from memcommit.adapters.console.terminal.components.command_editor import (
    CommandReview,
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
            "Do not update Source owners; final Apply remains separate.",
        ),
    )


__all__ = [
    "build_turn_review",
]
