"""Application and runtime contracts for the Trace operation boundary."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

import memcommit.application.capabilities.ops as ops
import memcommit.application.operations.trace.application as trace_application
import memcommit.application.operations.trace.runtime as trace_runtime
from memcommit.application.operations.trace.application import (
    ContextHistorySlice,
    MemoryHistory,
    FrozenTraceSubject,
    TraceContextTarget,
    TraceError,
    TraceMemoryTarget,
    TraceRequest,
    TraceTargetCandidate,
    TraceTargetCatalog,
    TraceTargetCatalogRequest,
    list_trace_targets,
    run_trace,
)
from memcommit.application.operations.trace.runtime import (
    execute_trace,
    load_trace_target_catalog,
)
from memcommit.persistence.store import MemoryStore


def _context_report(
    *,
    context_uid: str = "context-uid",
    context_name: str = "notes",
) -> ContextHistorySlice:
    return ContextHistorySlice(
        context_uid=context_uid,
        context_name=context_name,
        events=(),
        current=(),
        warnings=(),
    )


class _StaticTraceSource:
    def __init__(self) -> None:
        self.subject = FrozenTraceSubject(
            kind="CONTEXT",
            context_uid="context-uid",
            context_name="notes",
            selected_uid=None,
            token="frozen-context",
        )
        self.report = _context_report()
        self.catalog = TraceTargetCatalog(
            root_context_name="notes",
            context_names=("notes",),
            candidates=(
                TraceTargetCandidate(
                    context_name="notes",
                    uid="memory-uid",
                    content="Remember this.",
                    position=0,
                    status="CURRENT",
                    change_count=1,
                ),
            ),
        )
        self.requests: list[TraceRequest] = []
        self.catalog_requests: list[TraceTargetCatalogRequest] = []

    def target_catalog(self, request: TraceTargetCatalogRequest):
        self.catalog_requests.append(request)
        return self.catalog

    def freeze(self, request: TraceRequest):
        self.requests.append(request)
        return self.subject

    def reconstruct(self, subject: FrozenTraceSubject):
        assert subject is self.subject
        return self.report


def test_trace_application_owns_typed_request_freeze_and_result_dispatch():
    source = _StaticTraceSource()
    request = TraceRequest(
        target=TraceContextTarget("notes"),
        current_context_name="notes",
    )

    result = run_trace(request, source=source)

    assert source.requests == [request]
    assert result.subject.kind == "CONTEXT"
    assert result.report is source.report
    assert result.to_dict() == source.report.to_dict()


def test_trace_application_owns_the_picker_catalog_boundary():
    source = _StaticTraceSource()
    request = TraceTargetCatalogRequest(
        context_locator="notes",
        current_context_name="notes",
        include_descendants=True,
    )

    catalog = list_trace_targets(request, source=source)

    assert source.catalog_requests == [request]
    assert catalog.root_context_name == "notes"
    assert catalog.candidates[0].uid == "memory-uid"


def test_trace_application_rejects_a_report_for_another_frozen_subject():
    source = _StaticTraceSource()
    source.report = _context_report(context_name="other")

    with pytest.raises(TraceError, match="frozen Context identity"):
        run_trace(
            TraceRequest(target=TraceContextTarget("notes")),
            source=source,
        )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: TraceContextTarget(""),
        lambda: TraceMemoryTarget(""),
        lambda: TraceRequest(target=object()),
        lambda: TraceTargetCatalogRequest(include_descendants=1),
    ],
)
def test_trace_requests_reject_invalid_semantic_inputs(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()


def _direct_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    return tuple(imported)


def test_trace_application_and_runtime_have_no_console_or_terminal_imports():
    imported = (
        *_direct_imports(Path(trace_application.__file__)),
        *_direct_imports(Path(trace_runtime.__file__)),
    )

    assert not any(
        name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.adapters.console")
        for name in imported
    )


def test_trace_lineage_values_have_one_history_owner():
    from memcommit.application.capabilities.history.model.topology import HistoryGraph

    assert ContextHistorySlice.__module__ == (
        "memcommit.application.capabilities.history.query.context_history_slicing"
    )
    assert MemoryHistory.__module__ == (
        "memcommit.application.capabilities.history.query.memory_history_slicing"
    )
    assert HistoryGraph.__module__ == (
        "memcommit.application.capabilities.history.model.topology"
    )


def test_memory_history_slice_is_importable_from_its_history_owner():
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from memcommit.application.capabilities.history.query.memory_history_slicing "
                "import MemoryHistory; "
                "assert MemoryHistory.__module__.startswith("
                "'memcommit.application.capabilities.history.query')"
            ),
        ],
        check=True,
    )


def test_rationale_consumes_history_without_importing_trace_application():
    rationale_root = (
        Path(trace_application.__file__).parents[1]
        / "rationale"
    )
    imports = tuple(
        name
        for filename in ("context.py", "model.py", "rules.py", "scope.py", "semantic.py")
        for name in _direct_imports(rationale_root / filename)
    )

    assert "memcommit.application.operations.trace.application" not in imports
    assert any(
        name.startswith("memcommit.application.capabilities.history")
        for name in imports
    )
    assert not any(
        name.startswith("memcommit.application.operations.trace")
        for name in imports
    )


def test_store_runtime_lists_and_executes_memory_trace_without_terminal_output(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    context = ops.init("trace-application")
    memory = ops.add(context, "A retained application boundary.")
    store.save(context)
    store.set_current(context.name)

    catalog = load_trace_target_catalog(
        TraceTargetCatalogRequest(
            context_locator=context.name,
            current_context_name=context.name,
        ),
        store=store,
    )
    result = execute_trace(
        TraceRequest(
            target=TraceMemoryTarget(
                memory.uid,
                context_locator=context.name,
            ),
            current_context_name=context.name,
        ),
        store=store,
    )

    assert catalog.root_context_name == context.name
    assert [candidate.uid for candidate in catalog.candidates] == [memory.uid]
    assert result.subject.kind == "MEMORY"
    assert result.subject.selected_uid == memory.uid
    assert isinstance(result.report, MemoryHistory)
    assert result.report.selected_uid == memory.uid
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_store_runtime_executes_context_trace_through_the_same_boundary(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("context-trace-application")
    store.save(context)
    store.set_current(context.name)

    result = execute_trace(
        TraceRequest(
            target=TraceContextTarget(context.name),
            current_context_name=context.name,
        ),
        store=store,
    )

    assert result.subject.kind == "CONTEXT"
    assert result.subject.context_uid == context.uid
    assert isinstance(result.report, ContextHistorySlice)
