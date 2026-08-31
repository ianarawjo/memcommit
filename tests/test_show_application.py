"""Pure application tests for read-only direct-item selection."""

from __future__ import annotations

import pytest

from memcommit.application.operations.browse_navigate.show.application import (
    ShowContextSnapshot,
    ShowEmbeddedContext,
    ShowInputError,
    ShowMemory,
    ShowQueryView,
    ShowRequest,
    show,
)
from memcommit.source_projection.model import SourceDisplayFacts, SourceForm


def _memory(uid: str, content: str) -> ShowMemory:
    return ShowMemory(
        uid=uid,
        content=content,
        source=SourceDisplayFacts(form=SourceForm.MEMORY),
    )


class _Port:
    def __init__(self, context: ShowContextSnapshot) -> None:
        self.context = context
        self.calls = []

    def load_contexts(
        self,
        context_name,
        *,
        current_context_name,
        include_descendants,
        follow_embeds,
    ):
        self.calls.append(
            (
                context_name,
                current_context_name,
                include_descendants,
                follow_embeds,
            )
        )
        if include_descendants or follow_embeds:
            child = next(
                item.context
                for item in self.context.items
                if isinstance(item, ShowEmbeddedContext)
            )
            assert child is not None
            return (self.context, child)
        return (self.context,)


def _context() -> ShowContextSnapshot:
    child = ShowContextSnapshot(
        uid="child-context",
        name="root/child",
        items=(_memory("child-memory", "child content"),),
        source=SourceDisplayFacts(),
    )
    return ShowContextSnapshot(
        uid="root-context",
        name="root",
        items=(
            _memory("aaaa1111", "first"),
            _memory("aaaa2222", "second"),
            ShowEmbeddedContext(
                uid=child.uid,
                name=child.name,
                source=SourceDisplayFacts(),
                context=child,
            ),
            ShowQueryView(
                uid="query-route",
                name="root/concealed",
                source=SourceDisplayFacts(form=SourceForm.QUERY_VIEW),
            ),
        ),
        source=SourceDisplayFacts(),
    )


def test_whole_context_uses_one_frozen_current_snapshot():
    port = _Port(_context())

    result = show(
        ShowRequest(context_name=None, current_context_name="root"),
        port=port,
    )

    assert isinstance(result.value, ShowContextSnapshot)
    assert result.value.name == port.context.name
    embedded = next(
        item for item in result.value.items if isinstance(item, ShowEmbeddedContext)
    )
    assert embedded.context is None
    assert result.resolved_context_name == "root"
    assert port.calls == [(None, "root", False, False)]


def test_recursive_scope_returns_every_context_as_a_direct_snapshot():
    port = _Port(_context())

    result = show(
        ShowRequest(
            current_context_name="root",
            include_descendants=True,
            follow_embeds=True,
        ),
        port=port,
    )

    assert [context.name for context in result.contexts] == ["root", "root/child"]
    assert result.include_descendants is True
    assert result.follow_embeds is True
    assert all(
        item.context is None
        for context in result.contexts
        for item in context.items
        if isinstance(item, ShowEmbeddedContext)
    )
    assert port.calls == [(None, "root", True, True)]


def test_embedded_context_name_selects_its_direct_snapshot():
    result = show(
        ShowRequest(
            selector="root/child",
            current_context_name="root",
        ),
        port=_Port(_context()),
    )

    assert isinstance(result.value, ShowContextSnapshot)
    assert result.value.name == "root/child"
    assert [item.content for item in result.value.items] == ["child content"]


def test_query_view_selection_contains_metadata_but_no_content_field():
    result = show(
        ShowRequest(
            selector="root/concealed",
            current_context_name="root",
        ),
        port=_Port(_context()),
    )

    assert isinstance(result.value, ShowQueryView)
    assert result.value.uid == "query-route"
    assert not hasattr(result.value, "content")


@pytest.mark.parametrize("selector", ["missing", "aaaa"])
def test_unknown_and_ambiguous_selectors_fail_closed(selector):
    with pytest.raises(ShowInputError):
        show(
            ShowRequest(selector=selector, current_context_name="root"),
            port=_Port(_context()),
        )


def test_non_request_value_is_rejected():
    with pytest.raises(ShowInputError):
        show(object(), port=_Port(_context()))


@pytest.mark.parametrize(
    "arguments",
    [{"context_name": ""}, {"selector": "   "}],
)
def test_blank_request_fields_are_rejected(arguments):
    with pytest.raises(ShowInputError):
        ShowRequest(**arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        {"include_descendants": 1},
        {"follow_embeds": None},
        {"selector": "aaaa1111", "include_descendants": True},
        {"selector": "aaaa1111", "follow_embeds": True},
    ],
)
def test_invalid_scope_requests_fail_closed(arguments):
    with pytest.raises(ShowInputError):
        ShowRequest(**arguments)
