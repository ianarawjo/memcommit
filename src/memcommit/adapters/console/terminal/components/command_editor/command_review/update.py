"""Project Update setup and saved-session turns to reviewable commands."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.command_editor.command_review.model import CommandReview


def build_start_review(
    *,
    source_name: str,
    target_name: str,
    source_descendants: bool = False,
    target_descendants: bool = False,
    source_memory_uid: str | None = None,
    target_memory_uid: str | None = None,
    inline_source_content: str | None = None,
) -> CommandReview:
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
    return CommandReview(
        tuple(argv),
        (
            "Start or resume the exact Update plan and saved review session shown.",
            "Do not apply target changes; final Apply remains separate.",
        ),
    )


def build_turn_review(
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
) -> CommandReview:
    start = build_start_review(
        source_name=source_name,
        target_name=target_name,
        source_descendants=source_descendants,
        target_descendants=target_descendants,
        source_memory_uid=source_memory_uid,
        target_memory_uid=target_memory_uid,
        inline_source_content=inline_source_content,
    )
    return CommandReview(
        (*start.argv, "--comment", comment, "--expect-session", expected_session),
        (
            "Submit one semantic Update revision against the exact displayed session.",
            "Replace the staged plan; do not apply target changes.",
        ),
    )


__all__ = ["build_start_review", "build_turn_review"]
