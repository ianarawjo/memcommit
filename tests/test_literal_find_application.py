"""Provider-free deterministic Find application contracts."""

from __future__ import annotations

import pytest

from memcommit.literal_find_application import (
    FrozenLiteralFindSource,
    LiteralFindInputError,
    LiteralFindRequest,
    LiteralFindSourceItem,
    run_literal_find,
)


class _Source:
    def __init__(self, items):
        self.items = tuple(items)
        self.requests = []

    def freeze(self, request):
        self.requests.append(request)
        return FrozenLiteralFindSource(self.items)


def _memory(content: str, *, uid: str = "memory-1") -> LiteralFindSourceItem:
    return LiteralFindSourceItem(
        context_name="scope",
        context_uid="context-1",
        kind="memory",
        item_uid=uid,
        content=content,
    )


def test_literal_find_returns_every_nonoverlapping_exact_span():
    request = LiteralFindRequest(
        pattern="Cafe",
        target_names=("scope",),
    )
    source = _Source((_memory("Cafe, café, and Cafe."),))

    result = run_literal_find(request, source_port=source)

    assert source.requests == [request]
    assert result.scanned_item_count == 1
    assert result.occurrence_count == 2
    assert [
        (span.start, span.end, span.text)
        for span in result.matches[0].spans
    ] == [(0, 4, "Cafe"), (16, 20, "Cafe")]


def test_ignore_case_and_regex_are_explicit_independent_modes():
    literal = run_literal_find(
        LiteralFindRequest(
            pattern="cafe",
            target_names=("scope",),
            ignore_case=True,
        ),
        source_port=_Source((_memory("Cafe CAFE"),)),
    )
    regex = run_literal_find(
        LiteralFindRequest(
            pattern=r"C[a-z]+",
            target_names=("scope",),
            mode="REGEX",
        ),
        source_port=_Source((_memory("Cafe CAFE"),)),
    )

    assert literal.occurrence_count == 2
    assert [span.text for span in regex.matches[0].spans] == ["Cafe"]


@pytest.mark.parametrize("pattern", ["", "a" * 2001])
def test_invalid_pattern_fails_before_source_freeze(pattern):
    source = _Source((_memory("anything"),))

    with pytest.raises(LiteralFindInputError):
        run_literal_find(
            LiteralFindRequest(pattern=pattern, target_names=("scope",)),
            source_port=source,
        )

    assert source.requests == []


@pytest.mark.parametrize("pattern", ["(", r"^", r"a*"])
def test_invalid_or_zero_width_regex_fails_before_source_freeze(pattern):
    source = _Source((_memory("anything"),))
    request = LiteralFindRequest(
        pattern=pattern,
        target_names=("scope",),
        mode="REGEX",
    )

    with pytest.raises(LiteralFindInputError):
        run_literal_find(request, source_port=source)

    assert source.requests == []
