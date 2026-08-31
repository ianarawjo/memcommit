"""Provider-free deterministic Find application contracts."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from memcommit.application.operations.find.application import (
    FrozenFindSource,
    FindError,
    FindInputError,
    FindRequest,
    FindSourceItem,
    run_find,
)


class _Source:
    def __init__(self, items):
        self.items = tuple(items)
        self.requests = []

    def freeze(self, request):
        self.requests.append(request)
        return FrozenFindSource(self.items)


def _memory(content: str, *, uid: str = "memory-1") -> FindSourceItem:
    return FindSourceItem(
        context_name="scope",
        context_uid="context-1",
        kind="memory",
        item_uid=uid,
        source_position=1,
        content=content,
    )


def test_find_returns_every_nonoverlapping_exact_span():
    request = FindRequest(
        pattern="Cafe",
        target_names=("scope",),
    )
    source = _Source((_memory("Cafe, café, and Cafe."),))

    result = run_find(request, source_port=source)

    assert source.requests == [request]
    assert result.scanned_item_count == 1
    assert result.occurrence_count == 2
    assert [(span.start, span.end, span.text) for span in result.matches[0].spans] == [
        (0, 4, "Cafe"),
        (16, 20, "Cafe"),
    ]


def test_ignore_case_and_regex_are_explicit_independent_modes():
    literal = run_find(
        FindRequest(
            pattern="cafe",
            target_names=("scope",),
            ignore_case=True,
        ),
        source_port=_Source((_memory("Cafe CAFE"),)),
    )
    regex = run_find(
        FindRequest(
            pattern=r"C[a-z]+",
            target_names=("scope",),
            mode="REGEX",
        ),
        source_port=_Source((_memory("Cafe CAFE"),)),
    )

    assert literal.occurrence_count == 2
    assert [span.text for span in regex.matches[0].spans] == ["Cafe"]


def test_frozen_source_positions_cover_the_complete_searchable_frame():
    request = FindRequest(pattern="needle", target_names=("scope",))
    source = _Source(
        (
            _memory("haystack", uid="memory-1"),
            FindSourceItem(
                context_name="scope",
                context_uid="context-1",
                kind="memory",
                item_uid="memory-2",
                source_position=2,
                content="needle",
            ),
        )
    )

    result = run_find(request, source_port=source)

    assert result.matches[0].source.source_position == 2


def test_literal_uid_selects_the_authorized_item_without_fabricating_a_text_span():
    uid = "11111111-1111-4111-8111-111111111111"
    request = FindRequest(pattern=uid[:8], target_names=("scope",))

    result = run_find(
        request,
        source_port=_Source((_memory("content without its identity", uid=uid),)),
    )

    assert result.occurrence_count == 0
    assert result.identity_match_count == 1
    assert result.matches[0].matched_uids == (uid,)
    assert result.matches[0].spans == ()


def test_literal_source_uid_selects_an_authorized_memory_reference_row():
    source_uid = "22222222-2222-4222-8222-222222222222"
    item = FindSourceItem(
        context_name="scope",
        context_uid="context-1",
        kind="memory_ref",
        item_uid="11111111-1111-4111-8111-111111111111",
        source_position=1,
        content="Referenced content without either identity.",
        source_context_name="source",
        source_context_uid="context-2",
        source_memory_uid=source_uid,
    )

    result = run_find(
        FindRequest(pattern=source_uid[:8], target_names=("scope",)),
        source_port=_Source((item,)),
    )

    assert result.identity_match_count == 1
    assert result.matches[0].source is item
    assert result.matches[0].matched_uids == (source_uid,)
    assert result.matches[0].spans == ()


def test_frozen_source_rejects_result_relative_positions():
    with pytest.raises(FindError, match="cover the frozen frame"):
        FrozenFindSource(
            (
                FindSourceItem(
                    context_name="scope",
                    context_uid="context-1",
                    kind="memory",
                    item_uid="memory-2",
                    source_position=2,
                    content="needle",
                ),
            )
        )


@pytest.mark.parametrize("pattern", ["", "a" * 2001])
def test_invalid_pattern_fails_before_source_freeze(pattern):
    source = _Source((_memory("anything"),))

    with pytest.raises(FindInputError):
        run_find(
            FindRequest(pattern=pattern, target_names=("scope",)),
            source_port=source,
        )

    assert source.requests == []


@pytest.mark.parametrize("pattern", ["(", r"^", r"a*"])
def test_invalid_or_zero_width_regex_fails_before_source_freeze(pattern):
    source = _Source((_memory("anything"),))
    request = FindRequest(
        pattern=pattern,
        target_names=("scope",),
        mode="REGEX",
    )

    with pytest.raises(FindInputError):
        run_find(request, source_port=source)

    assert source.requests == []


def test_find_application_does_not_depend_on_reference_presentation():
    root = Path(__file__).parents[1]

    def imported_modules(path: Path) -> tuple[str, ...]:
        tree = ast.parse(path.read_text())
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        return tuple(modules)

    application_imports = imported_modules(
        root / "src/memcommit/application/operations/find/application.py"
    )
    projection_imports = imported_modules(
        root / "src/memcommit/adapters/console/commands/find/source_row.py"
    )

    assert not any(
        name.startswith(
            ("memcommit.adapters.interfaces", "memcommit.source_projection")
        )
        for name in application_imports
    )
    assert "memcommit.application.operations.find.application" in projection_imports
    assert "memcommit.source_projection.model" in projection_imports
    assert not any(
        name.startswith(
            (
                "memcommit.adapters.console.commands",
                "memcommit.adapters.interfaces.cli",
                "memcommit.adapters.interfaces.tui",
            )
        )
        for name in projection_imports
    )
