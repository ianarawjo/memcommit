"""Plain terminal projection for provider-free deterministic Find."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.literal_find_application import LiteralFindMatch, LiteralFindResult


def _match_label(match: LiteralFindMatch) -> str:
    source = match.source
    label = (
        f"{source.context_name} · {source.kind.upper()} · {source.item_uid[:8]}"
    )
    if source.kind == "memory_ref":
        label += (
            f" -> {source.source_context_name}"
            f"/{(source.source_memory_uid or '')[:8]}"
        )
    return label


def render_literal_find_result(result: LiteralFindResult) -> str:
    """Render the complete result without reparsing an interface string."""

    scope = " + ".join(result.request.target_names)
    lines = [
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
        ),
    ]
    if not result.matches:
        lines.extend(("", "(no matching Memories)"))
        return "\n".join(lines)
    for index, match in enumerate(result.matches, start=1):
        spans = ", ".join(f"{span.start}:{span.end}" for span in match.spans)
        lines.extend(
            (
                "",
                f"[{index}] {safe_terminal_text(_match_label(match))}",
                f"SPANS · {spans}",
                safe_terminal_text(match.source.content),
            )
        )
    return "\n".join(lines)


def project_literal_find_match(match: LiteralFindMatch) -> str:
    """Project one focused result for the shared lowercase-y copy contract."""

    spans = ", ".join(f"{span.start}:{span.end}" for span in match.spans)
    return "\n".join(
        (
            _match_label(match),
            f"SPANS · {spans}",
            match.source.content,
        )
    )


__all__ = ["project_literal_find_match", "render_literal_find_result"]
