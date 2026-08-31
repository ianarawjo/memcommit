"""Validate and replay mechanical Chunk boundaries."""

from __future__ import annotations

from memcommit.application.operations.direct_changes.chunk.domain import chunk_content


def _checkpoint_chunk_options(args: dict) -> dict[str, object] | None:
    options: dict[str, object] = {}
    if "break_on" in args:
        break_on = args.get("break_on")
        if not isinstance(break_on, str) or not break_on:
            return None
        options["break_on"] = break_on
    for key in ("min_chars", "max_chars"):
        if key not in args:
            continue
        value = args.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None
        options[key] = value
    min_chars = options.get("min_chars")
    max_chars = options.get("max_chars")
    if (
        isinstance(min_chars, int)
        and isinstance(max_chars, int)
        and min_chars > max_chars
    ):
        return None
    return options


def _replay_checkpoint_chunk(
    content: str,
    method: str,
    args: dict,
) -> list[str]:
    """Replay every authored mechanical boundary recorded by Chunk."""

    return chunk_content(
        content,
        method,
        break_on=args.get("break_on"),
        min_chars=args.get("min_chars"),
        max_chars=args.get("max_chars"),
    )
