"""Shared Retrieve & Answer SAVE presentation and operation contracts."""

from __future__ import annotations

from pathlib import Path
import threading
import time
from types import SimpleNamespace

from prompt_toolkit.data_structures import Size
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.commands.search_explain.retrieve_answer.components.save_panel import (
    RetrieveAnswerSavePanel,
)
from memcommit.adapters.console.commands.search_explain.retrieve_answer.find.workbench import (
    FindTuiSetup,
    run_find_workbench,
)
from memcommit.adapters.console.commands.search_explain.retrieve_answer.query.workbench import (
    run_query_workbench,
)
from memcommit.application.capabilities.authority.context_access import (
    resolve_context_access,
)
from memcommit.application.capabilities.authority.readable_contexts import (
    freeze_readable_context_catalog,
)
from memcommit.application.capabilities.save_context_from_selection.runtime import (
    execute_save_context_from_selection,
)
from memcommit.application.operations.search_explain.retrieve_answer.find.application import (
    FindRequest,
)
from memcommit.application.operations.search_explain.retrieve_answer.find.runtime import (
    execute_find,
)
from memcommit.application.operations.search_explain.retrieve_answer.find.save_context import (
    save_context_request_from_find,
)
from memcommit.application.operations.search_explain.retrieve_answer.query.ordinary_application import (
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)
from memcommit.application.operations.search_explain.retrieve_answer.query.save_answer import (
    SaveQueryAnswerRequest,
)
from memcommit.application.operations.search_explain.retrieve_answer.query.save_answer_runtime import (
    execute_save_query_answer,
)
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class Terminal180x52(DummyOutput):
    def get_size(self) -> Size:
        return Size(rows=52, columns=180)


def _catalog(store: MemoryStore, name: str):
    access = resolve_context_access(
        store,
        name,
        current_name=name,
        required_permission="READ",
    )
    return freeze_readable_context_catalog(store, access)


def test_find_checked_match_uses_shared_selection_save(isolated_store) -> None:
    store = MemoryStore()
    source = ops.init("task")
    memory = ops.add(source, "Needle in one exact Memory.")
    store.save(source)
    catalog = _catalog(store, source.name)
    result = execute_find(
        FindRequest("Needle", (source.name,)),
        catalog=catalog,
    )

    saved = execute_save_context_from_selection(
        save_context_request_from_find(
            result,
            (0,),
            mode="COPY",
            destination_name="task/results/needle",
            catalog=catalog,
        ),
        store=store,
        catalog=catalog,
    )

    output = tuple(store.load_direct(saved.context_name).iter_items())
    assert len(output) == 1
    assert isinstance(output[0], Memory)
    assert output[0].content == memory.content
    checkpoint = store.list_checkpoints(saved.context_name)[0]
    assert checkpoint["args"]["save_context_from_selection"]["source_operation"] == "find"


def test_query_answer_save_creates_one_answer_memory_without_reopening_sources(
    isolated_store,
) -> None:
    store = MemoryStore()
    request = OrdinaryQueryRequest("What changed?", ("task",))
    response = OrdinaryQueryResponse(request, "The schedule changed.", True)

    saved = execute_save_query_answer(
        SaveQueryAnswerRequest(response, "task/answers/schedule"),
        store=store,
    )

    output = tuple(store.load_direct(saved.context_name).iter_items())
    assert len(output) == 1
    assert isinstance(output[0], Memory)
    assert output[0].uid == saved.memory_uid
    assert output[0].content == response.answer
    checkpoint = store.list_checkpoints(saved.context_name)[0]
    assert checkpoint["args"]["save_query_answer"]["question"] == request.question


def test_find_workbench_returns_one_reviewed_shared_save_request(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = ops.init("alpha")
    ops.add(source, "Alpha needle.")
    store.save(source)
    catalog = _catalog(store, source.name)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\r\r\t\t\x15alpha/results/needle\t\t\r"
        )
        outcome = run_find_workbench(
            FindRequest("needle", ("alpha",)),
            setup=FindTuiSetup(
                names=("alpha",),
                current_name="alpha",
                initial_targets=("alpha",),
            ),
            execute=lambda request: execute_find(request, catalog=catalog),
            local_context_names=("alpha",),
            validate_save_location=lambda value: value,
            app_input=pipe_input,
            app_output=Terminal180x52(),
            require_tty=False,
        )

    assert outcome is not None
    assert outcome.status == "SAVE"
    assert outcome.selected_match_indices == (0,)
    assert outcome.save_as == "COPY"
    assert outcome.save_location == "alpha/results/needle"


def test_query_workbench_returns_answer_save_request_after_answer() -> None:
    def ordinary(request: OrdinaryQueryRequest) -> OrdinaryQueryResponse:
        return OrdinaryQueryResponse(request, "Grounded answer.", True)

    with create_pipe_input() as pipe_input:

        def send_after_query() -> None:
            pipe_input.send_text("What changed?\r")
            time.sleep(0.15)
            pipe_input.send_text(
                "\t\x15task/answers/what-changed\t\t\r"
            )

        sender = threading.Thread(target=send_after_query)
        sender.start()
        outcome = run_query_workbench(
            ("task",),
            current_context="task",
            initial_context="task",
            query_targets=(),
            run_ordinary=ordinary,
            run_granted=lambda _request: None,  # type: ignore[return-value]
            local_context_names=("task",),
            validate_save_location=lambda value: value,
            app_input=pipe_input,
            app_output=Terminal180x52(),
            require_tty=False,
        )
        sender.join(timeout=3)

    assert not sender.is_alive()
    assert outcome.status == "SAVE"
    assert outcome.response is not None
    assert outcome.save_location == "task/answers/what-changed"


def test_shared_save_panel_has_one_visible_location_vocabulary() -> None:
    relative_paths = (
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/components/save_panel.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/find/workbench/screen.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/search/search_workbench.py",
        "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/query/workbench/screen.py",
    )
    sources = "\n".join(
        (REPOSITORY_ROOT / path).read_text(encoding="utf-8")
        for path in relative_paths
    )

    assert "PARENT CONTEXT" not in sources
    assert "REPARENT" not in sources
    assert sources.count("RetrieveAnswerSavePanel(") == 3
    panel = (REPOSITORY_ROOT / relative_paths[0]).read_text(encoding="utf-8")
    assert 'title="SAVE"' in panel
    assert '" CONTENT · "' in panel
    assert 'FormattedTextControl(" LOCATION · ")' in panel
    assert '" ACTION · ' in panel


def test_browse_explicitly_reparents_a_directly_edited_save_location() -> None:
    panel = RetrieveAnswerSavePanel(
        content_summary=lambda: "ONE RESULT",
        action_label=lambda _mode: "SAVE RESULT",
        initial_location="task/source/result",
        context_names=("task", "task/archive", "task/source"),
        current_context="task/source",
        validate_location=lambda value: value,
        input_name="test-save-location",
        on_status=lambda _message: None,
    )
    panel.name.set_text("draft/result")
    assert panel.locator is not None
    panel.locator.tree.move(-1)
    focused: list[object] = []
    event = SimpleNamespace(
        app=SimpleNamespace(layout=SimpleNamespace(focus=focused.append))
    )

    assert panel._choose_tree_location(event) == "HANDLED"

    assert panel.location == "task/archive/result"
    assert focused == [panel.name.input]
