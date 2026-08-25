"""Application-boundary contracts for TUI-independent Summarize execution."""

from __future__ import annotations

import ast
from contextlib import contextmanager
import json
from pathlib import Path

import pytest

import memcommit.ops as ops
from memcommit.context import Context, Memory
from memcommit.summarize import SummarizeError, collect_summary_frame
import memcommit.operations.summarize.application as summarize_application
from memcommit.operations.summarize.application import (
    FrozenSummarySource,
    SummarizeRequest,
    run_summarize,
)
from memcommit.operations.summarize.runtime import execute_summarize
import memcommit.operations.summarize.runtime as summarize_runtime
from memcommit.store import MemoryStore
from memcommit.understanding import UnderstandingSummary


def _context(*contents: str) -> Context:
    context = Context(uid="context-uid", name="summary")
    for index, content in enumerate(contents, 1):
        context.add(Memory(uid=f"memory-{index}", content=content))
    return context


class _StaticSummarySource:
    def __init__(self, frame, *, current_frame=None):
        self.frame = frame
        self.current_frame = current_frame or frame
        self.requests: list[SummarizeRequest] = []
        self.revalidations = 0

    def freeze(self, request: SummarizeRequest) -> FrozenSummarySource:
        self.requests.append(request)
        return FrozenSummarySource(frame=self.frame, token="frozen-source")

    def revalidate(self, source: FrozenSummarySource):
        assert source.token == "frozen-source"
        self.revalidations += 1
        return self.current_frame


class _SummaryProvider:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        payload = json.loads(prompt.split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1])
        return json.dumps(
            {
                "text": "The Context records one source-grounded commitment.",
                "source_ids": [item["source_id"] for item in payload["memories"]],
            }
        )


def test_run_summarize_returns_typed_result_without_cli_or_tui():
    frame = collect_summary_frame(_context("Keep the source commitment."))
    source = _StaticSummarySource(frame)
    provider = _SummaryProvider()
    lifecycle: list[str] = []

    @contextmanager
    def provider_session():
        lifecycle.append("opened")
        try:
            yield provider
        finally:
            lifecycle.append("closed")

    request = SummarizeRequest(
        context_locator="summary",
        include_descendants=False,
        follow_embeds=False,
    )
    result = run_summarize(
        request,
        source_port=source,
        provider_session_factory=provider_session,
    )

    assert source.requests == [request]
    assert source.revalidations == 1
    assert provider.calls == 1
    assert lifecycle == ["opened", "closed"]
    assert result.context_name == "summary"
    assert result.include_descendants is False
    assert result.follow_embeds is False
    assert result.source_digest == frame.digest
    assert result.source_count == 1
    assert result.understanding.source_uids == ("memory-1",)


def test_run_summarize_empty_frame_never_opens_provider_session():
    frame = collect_summary_frame(_context())
    source = _StaticSummarySource(frame)

    def forbidden_provider_session():
        raise AssertionError("empty summarize must not open a provider session")

    result = run_summarize(
        SummarizeRequest(context_locator="summary"),
        source_port=source,
        provider_session_factory=forbidden_provider_session,
    )

    assert source.revalidations == 1
    assert result.source_count == 0
    assert "contains no ordinary Memories" in result.understanding.text


def test_run_summarize_rejects_prepared_evidence_outside_frozen_frame():
    frame = collect_summary_frame(_context("Bounded evidence."))
    source = _StaticSummarySource(frame)

    with pytest.raises(SummarizeError, match="outside the frozen frame"):
        run_summarize(
            SummarizeRequest(context_locator="summary"),
            source_port=source,
            provider_session_factory=lambda: (_ for _ in ()).throw(
                AssertionError("invalid prepared result must not open provider")
            ),
            prepared_lookup=lambda _frame: UnderstandingSummary(
                text="An invalid prepared claim.",
                source_uids=("outside-memory",),
            ),
        )


def test_run_summarize_rejects_source_change_before_returning_result():
    frame = collect_summary_frame(_context("Initial evidence."))
    current_frame = collect_summary_frame(
        _context("Initial evidence.", "Concurrent evidence.")
    )
    source = _StaticSummarySource(frame, current_frame=current_frame)
    provider = _SummaryProvider()

    @contextmanager
    def provider_session():
        yield provider

    with pytest.raises(SummarizeError, match="changed while summarization was running"):
        run_summarize(
            SummarizeRequest(context_locator="summary"),
            source_port=source,
            provider_session_factory=provider_session,
        )

    assert source.revalidations == 1
    assert provider.calls == 1


def test_summarize_application_has_no_command_typer_or_tui_imports():
    source = Path(summarize_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
    )
    assert forbidden == ()


def test_execute_summarize_runs_against_real_store_without_terminal(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    child = ops.init("runtime-summary/child")
    ops.add(child, "The child retains its explicit exception.")
    root = ops.init("runtime-summary")
    ops.add(root, "The root records the primary commitment.")
    ops.embed(child, root)
    store.save(child)
    store.save(root)
    store.set_current(root.name)
    provider = _SummaryProvider()

    result = execute_summarize(
        SummarizeRequest(include_descendants=True, follow_embeds=True),
        store=store,
        provider_factory=lambda: provider,
    )

    assert result.context_name == root.name
    assert result.source_count == 2
    assert result.understanding.source_uids == (
        next(iter(root.memories)),
        next(iter(child.memories)),
    )
    assert provider.calls == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_execute_summarize_empty_real_store_is_provider_free(isolated_store):
    store = MemoryStore()
    empty = ops.init("runtime-empty")
    store.save(empty)
    store.set_current(empty.name)

    def forbidden_provider():
        raise AssertionError("empty production summarize must not connect")

    result = execute_summarize(
        SummarizeRequest(),
        store=store,
        provider_factory=forbidden_provider,
    )

    assert result.context_name == empty.name
    assert result.source_count == 0


def test_execute_summarize_resolves_source_before_connecting_provider(isolated_store):
    store = MemoryStore()
    calls = 0

    def forbidden_provider():
        nonlocal calls
        calls += 1
        raise AssertionError("an unresolved source must not connect")

    with pytest.raises(FileNotFoundError, match="missing-summary"):
        execute_summarize(
            SummarizeRequest(context_locator="missing-summary"),
            store=store,
            provider_factory=forbidden_provider,
        )

    assert calls == 0


def test_summarize_runtime_has_no_typer_or_tui_imports():
    source = Path(summarize_runtime.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer" or name.startswith("prompt_toolkit")
    )
    assert forbidden == ()
