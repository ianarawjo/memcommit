"""Plain terminal projection for provider-free deterministic Find."""

from __future__ import annotations

from memcommit.interfaces.literal_find import render_literal_find_reference_row
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.literal_find_application import LiteralFindMatch, LiteralFindResult


DEFAULT_LITERAL_FIND_PREVIEW_MATCHES = 10


def literal_find_result_header_lines(
    result: LiteralFindResult,
    *,
    visible_range: tuple[int, int] | None = None,
) -> tuple[str, str, str, str]:
    """Project stable Find chrome with an optional zero-based visible range."""

    if not isinstance(result, LiteralFindResult):
        raise TypeError("Find result presentation requires a LiteralFindResult.")
    if visible_range is not None:
        start, stop = visible_range
        if not 0 <= start < stop <= len(result.matches):
            raise ValueError("Find visible range is outside the result set.")
        showing = f" · SHOWING {start + 1}–{stop} OF {len(result.matches)}"
    else:
        showing = ""
    scope = " + ".join(result.request.target_names)
    return (
        "FIND RESULTS",
        (
            f"PATTERN · {safe_terminal_text(result.request.pattern)}"
            f" · {result.request.mode}"
            f" · {'IGNORE CASE' if result.request.ignore_case else 'CASE SENSITIVE'}"
        ),
        (
            f"SCOPE · {safe_terminal_text(scope)}"
            f" · {'DESCENDANTS' if result.request.include_descendants else 'EXACT'}"
            f" · {'FOLLOW EMBEDS' if result.request.follow_embeds else 'EXCLUDE EMBEDS'}"
        ),
        (
            f"STATUS · READ-ONLY · PROVIDER-FREE"
            f" · SCANNED {result.scanned_item_count}"
            f" · MATCHED {len(result.matches)}"
            f" · OCCURRENCES {result.occurrence_count}"
            f"{showing}"
        ),
    )


def render_literal_find_result(
    result: LiteralFindResult,
    *,
    match_limit: int | None = None,
) -> str:
    """Render the complete result without reparsing an interface string."""

    if match_limit is not None and (
        not isinstance(match_limit, int)
        or isinstance(match_limit, bool)
        or match_limit < 1
    ):
        raise ValueError("Find result limit must be a positive integer.")

    shown_matches = (
        result.matches if match_limit is None else result.matches[:match_limit]
    )
    visible_range = (
        (0, len(shown_matches))
        if len(shown_matches) < len(result.matches)
        else None
    )
    lines = list(
        literal_find_result_header_lines(result, visible_range=visible_range)
    )
    if not result.matches:
        empty_message = (
            "(scope contains no searchable Memories)"
            if result.scanned_item_count == 0
            else "(no matching Memories)"
        )
        lines.extend(("", empty_message))
        return "\n".join(lines)
    lines.append("")
    lines.extend(
        safe_terminal_text(
            render_literal_find_reference_row(match, number=index)
        )
        for index, match in enumerate(shown_matches, start=1)
    )
    hidden_count = len(result.matches) - len(shown_matches)
    if hidden_count:
        noun = "match" if hidden_count == 1 else "matches"
        lines.append(
            f"{hidden_count} more {noun} not shown; "
            "rerun with --all to show every result."
        )
    return "\n".join(lines)


def project_literal_find_match(match: LiteralFindMatch, *, number: int = 1) -> str:
    """Project one focused result for the shared lowercase-y copy contract."""

    return safe_terminal_text(
        render_literal_find_reference_row(match, number=number)
    )


__all__ = [
    "DEFAULT_LITERAL_FIND_PREVIEW_MATCHES",
    "literal_find_result_header_lines",
    "project_literal_find_match",
    "render_literal_find_result",
]
