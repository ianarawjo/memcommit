"""Checked Search result materialization contracts."""

import pytest

import memcommit.application.ops as ops
from memcommit.adapters.console.commands.search.materialization import (
    SearchMaterializationError,
    materialize_search_results,
)
from memcommit.adapters.console.commands.search.search_workbench import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from memcommit.application.authority.access import resolve_context_access
from memcommit.adapters.console.shared.readable_context_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.core.context import Memory, MemoryRef
from memcommit.adapters.console.selection import (
    FlatMultiSelectionState,
    SelectionOption,
)
from memcommit.adapters.console.selection.tui.multiple import (
    render_vertical_multi_choice_rows,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


def _catalog(store: MemoryStore, context_name: str):
    access = resolve_context_access(
        store,
        context_name,
        current_name=context_name,
        required_permission="READ",
    )
    return freeze_readable_context_catalog(store, access)


def _response(source, memory, *, kind="memory") -> SearchResponse:
    request = SearchRequest("accessibility", (source.name,))
    return SearchResponse(
        request,
        "CURRENT",
        (
            SearchResult(
                context_name=source.name,
                kind=kind,
                uid=memory.uid,
                content=memory.content,
                source_context_name=source.name,
                source_context_uid=source.uid,
                source_memory_uid=memory.uid,
            ),
        ),
    )


def test_copy_creates_fresh_memory_values_and_leaves_source_unchanged(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("task-3/local/source")
    memory = ops.add(source, "Accessible entrance is on the east side.")
    store.save(source)
    source_before = context_record_digest(store.load_direct(source.name))

    result = materialize_search_results(
        store,
        _catalog(store, source.name),
        _response(source, memory),
        selected_result_indices=(0,),
        mode="COPY",
        destination_name="task-3/local/results/accessibility",
    )

    output = store.load_direct(result.context_name)
    copied = tuple(output.iter_items())
    assert len(copied) == 1
    assert isinstance(copied[0], Memory)
    assert copied[0].content == memory.content
    assert copied[0].uid != memory.uid
    assert result.item_uids == (copied[0].uid,)
    assert context_record_digest(store.load_direct(source.name)) == source_before
    checkpoint = store.list_checkpoints(result.context_name)[0]
    assert checkpoint["command"] == "search"
    assert checkpoint["args"]["search_materialization"]["mode"] == "COPY"
    assert checkpoint["description"].startswith(
        "Saved 1 checked Search result(s) as COPY"
    )


def test_reference_reuses_the_existing_live_reference_primitive(isolated_store):
    store = MemoryStore()
    source = ops.init("task-3/local/source")
    memory = ops.add(source, "Accessible entrance is on the east side.")
    store.save(source)
    source_before = context_record_digest(store.load_direct(source.name))

    result = materialize_search_results(
        store,
        _catalog(store, source.name),
        _response(source, memory),
        selected_result_indices=(0,),
        mode="REFERENCE",
        destination_name="task-3/local/results/accessibility",
    )

    direct_output = store.load_direct(result.context_name)
    ref = tuple(direct_output.iter_items())[0]
    assert isinstance(ref, MemoryRef)
    assert ref.target_context_uid == source.uid
    assert ref.target_context_name == source.name
    assert ref.target_memory_uid == memory.uid
    loaded_ref = tuple(store.load(result.context_name).iter_items())[0]
    assert isinstance(loaded_ref, MemoryRef)
    assert loaded_ref.target is not None
    assert loaded_ref.target.content == memory.content
    assert context_record_digest(store.load_direct(source.name)) == source_before


def test_materialization_fails_closed_when_visible_source_changed(isolated_store):
    store = MemoryStore()
    source = ops.init("task-3/local/source")
    memory = ops.add(source, "Original accessibility detail")
    store.save(source)
    response = _response(source, memory)
    current = store.load_direct(source.name)
    current.replace(Memory(uid=memory.uid, content="Changed accessibility detail"))
    store.save(current, expected_context_digest=current._store_digest)

    with pytest.raises(SearchMaterializationError, match="changed after search"):
        materialize_search_results(
            store,
            _catalog(store, source.name),
            response,
            selected_result_indices=(0,),
            mode="COPY",
            destination_name="task-3/local/results/accessibility",
        )

    assert not store.context_exists("task-3/local/results/accessibility")


def test_non_memory_search_results_cannot_be_materialized(isolated_store):
    store = MemoryStore()
    source = ops.init("task-3")
    store.save(source)
    response = SearchResponse(
        SearchRequest("activity", (source.name,)),
        "CURRENT",
        (
            SearchResult(
                context_name=source.name,
                kind="artifact",
                uid="artifact-one",
                content="A retained activity record",
            ),
        ),
    )

    with pytest.raises(SearchMaterializationError, match="artifact results"):
        materialize_search_results(
            store,
            _catalog(store, source.name),
            response,
            selected_result_indices=(0,),
            mode="COPY",
            destination_name="task-3/results/activity",
        )

    assert not store.context_exists("task-3/results/activity")


def test_flat_result_selection_keeps_order_and_renders_every_check():
    state = FlatMultiSelectionState(
        (
            SelectionOption("one", "First", "First content"),
            SelectionOption("two", "Second", "Second content"),
            SelectionOption("three", "Third"),
        ),
        cursor_uid="two",
        selected_uids=("three", "one"),
    )

    assert state.selected_uids == ("one", "three")
    assert state.toggle_cursor() is True
    assert state.selected_uids == ("one", "two", "three")
    state.move(1)
    assert state.toggle_cursor() is False
    fragments = render_vertical_multi_choice_rows(
        state,
        focused=True,
        content_width=36,
    )
    rendered = "".join(text for _style, text in fragments)
    assert "✓ 1. First" in rendered
    assert "✓ 2. Second" in rendered
    assert "✓ 3. Third" not in rendered
    assert any(style == "[SetCursorPosition]" for style, _ in fragments)
