"""Compose the Find screen and dispatch its explicit selection-save outcome."""

from memcommit.adapters.console.commands.search import execution
from memcommit.adapters.console.commands.search.preparation import PreparedSearch
from memcommit.adapters.console.commands.search.receipt import render_save_receipt
from memcommit.adapters.console.commands.search.workbench.screen import (
    run_search_workbench,
)
from memcommit.application.operations.search.save_context import (
    save_context_request_from_search,
)
from memcommit.application.capabilities.save_context_from_selection.runtime import (
    execute_save_context_from_selection,
)
from memcommit.persistence.store import MemoryStore


def open_search_workbench(
    store: MemoryStore,
    prepared: PreparedSearch,
    *,
    include_descendants: bool,
    limit: int,
) -> None:
    """Open a blank, query-focused Find over one frozen readable catalog."""

    catalog = prepared.catalog
    current_name = prepared.current_name
    names = tuple(catalog.list_context_names())
    initial_target = prepared.initial_access.access_name
    if initial_target not in names:
        raise RuntimeError("The selected Context is outside the readable catalog.")
    displayed_current = current_name if current_name in names else initial_target
    workbench_result = run_search_workbench(
        names,
        current=displayed_current,
        initial_target=initial_target,
        initial_targets=prepared.target_names,
        initial_include_descendants=include_descendants,
        limit=limit,
        run_search=lambda request: execution.run_search_request(
            store,
            catalog,
            request,
        ),
        local_context_names=tuple(store.list_context_names()),
        validate_save_location=store.assert_context_creatable,
    )
    # Compatibility capture stubs used by read-only callers historically
    # returned None; only the typed SAVE result crosses the write edge.
    if workbench_result is None or workbench_result.status != "SAVE":
        return
    assert workbench_result.response is not None
    assert workbench_result.save_as is not None
    assert workbench_result.save_location is not None
    saved = execute_save_context_from_selection(
        save_context_request_from_search(
            workbench_result.response,
            workbench_result.selected_result_indices,
            mode=workbench_result.save_as,
            destination_name=workbench_result.save_location,
            catalog=catalog,
        ),
        store=store,
        catalog=catalog,
    )
    render_save_receipt(saved)
