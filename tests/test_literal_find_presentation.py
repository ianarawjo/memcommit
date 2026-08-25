"""Compact plain projection contracts for provider-free literal Find."""

from __future__ import annotations

from memcommit.interfaces.cli.find import (
    DEFAULT_LITERAL_FIND_PREVIEW_MATCHES,
    literal_find_result_header_lines,
    project_literal_find_match,
    render_literal_find_result,
)
from memcommit.operations.find.literal_application import (
    FrozenLiteralFindSource,
    LiteralFindRequest,
    LiteralFindSourceItem,
    run_literal_find,
)


class _Source:
    def __init__(self, items: tuple[LiteralFindSourceItem, ...]) -> None:
        self.items = items

    def freeze(self, _request: LiteralFindRequest) -> FrozenLiteralFindSource:
        return FrozenLiteralFindSource(self.items)


def _result(*items: LiteralFindSourceItem, pattern: str = "needle"):
    return run_literal_find(
        LiteralFindRequest(pattern=pattern, target_names=("scope",)),
        source_port=_Source(tuple(items)),
    )


def test_find_result_uses_compact_source_rows_without_exposing_raw_spans():
    result = _result(
        LiteralFindSourceItem(
            context_name="scope",
            context_uid="context-1",
            kind="memory",
            item_uid="memory-12345678",
            source_position=1,
            content="First needle.\nSecond line.",
        )
    )

    rendered = render_literal_find_result(result)

    assert "1 [memory-1] First needle. Second line. [scope m1]" in rendered
    assert "SPANS" not in rendered
    assert project_literal_find_match(result.matches[0], number=1) in rendered


def test_find_all_readable_scope_hides_frozen_context_enumeration() -> None:
    result = _result()

    header = literal_find_result_header_lines(
        result,
        all_readable_contexts=True,
    )

    assert header[2] == (
        "SCOPE · ALL READABLE CONTEXTS · EXACT · EXCLUDE EMBEDS"
    )
    assert "SCOPE · scope ·" not in header[2]


def test_find_memory_ref_row_keeps_owner_before_referenced_source():
    result = _result(
        LiteralFindSourceItem(
            context_name="target/context",
            context_uid="target-context-uid",
            kind="memory_ref",
            item_uid="owner-ref-uid",
            source_position=1,
            content="Referenced needle.",
            source_context_name="source/context",
            source_context_uid="source-context-uid",
            source_memory_uid="source-memory-uid",
        )
    )

    assert (
        "1 [owner-re] Referenced needle. [target/context m1] "
        "→ [source-m] [source/context]"
    ) in render_literal_find_result(result)


def test_find_preview_is_explicit_about_hidden_rows_and_complete_counts():
    items = tuple(
        LiteralFindSourceItem(
            context_name="scope",
            context_uid="context-1",
            kind="memory",
            item_uid=f"memory-{index:08d}",
            source_position=index + 1,
            content=f"needle row {index}",
        )
        for index in range(DEFAULT_LITERAL_FIND_PREVIEW_MATCHES + 2)
    )
    result = _result(*items)

    preview = render_literal_find_result(
        result,
        match_limit=DEFAULT_LITERAL_FIND_PREVIEW_MATCHES,
    )
    complete = render_literal_find_result(result)

    assert "MATCHED 12 · OCCURRENCES 12 · SHOWING 1–10 OF 12" in preview
    assert "10 [memory-0] needle row 9, [scope m10]" in preview
    assert "11 [memory-0] needle row 10, [scope m11]" not in preview
    assert (
        "2 more matches not shown; rerun with --all-results to show every result."
        in preview
    )
    assert "SHOWING" not in complete
    assert "12 [memory-0] needle row 11, [scope m12]" in complete


def test_find_human_row_retains_complete_folded_content_without_ellipsis():
    long_content = "needle " + ("supporting detail " * 12)
    result = _result(
        LiteralFindSourceItem(
            context_name="scope",
            context_uid="context-1",
            kind="memory",
            item_uid="memory-1",
            source_position=1,
            content=long_content,
        )
    )

    human = render_literal_find_result(result)

    assert "…" not in human
    assert " ".join(long_content.split()) in human


def test_find_empty_scope_and_no_match_have_distinct_messages():
    empty_scope = _result()
    no_match = _result(
        LiteralFindSourceItem(
            context_name="scope",
            context_uid="context-1",
            kind="memory",
            item_uid="memory-1",
            source_position=1,
            content="haystack",
        )
    )

    assert "(scope contains no searchable Memories)" in render_literal_find_result(
        empty_scope
    )
    assert "(no matching Memories)" in render_literal_find_result(no_match)
