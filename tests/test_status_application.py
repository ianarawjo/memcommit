"""Application and runtime contracts for the rebuilt Status operation."""

from __future__ import annotations

import ast
from pathlib import Path

import memcommit.application.capabilities.ops as ops
import memcommit.application.operations.status.application as status_application
from memcommit.source_projection.model import SourceDisplayFacts
from memcommit.application.operations.status.application import (
    FrozenStatusContext,
    FrozenStatusFrame,
    StatusCheckpoint,
    StatusMemory,
    StatusRequest,
    inspect_status,
)
from memcommit.application.operations.status.runtime import execute_status
from memcommit.persistence.store import MemoryStore


class _StaticStatusSource:
    def __init__(self, frame: FrozenStatusFrame) -> None:
        self.frame = frame
        self.requests: list[StatusRequest] = []

    def freeze(self, request: StatusRequest) -> FrozenStatusFrame:
        self.requests.append(request)
        return self.frame


def _frame(*, memory_count: int = 7, checkpoint_count: int = 7) -> FrozenStatusFrame:
    context = FrozenStatusContext(
        uid="context-uid",
        name="task/current",
        source=SourceDisplayFacts(),
        access_grant_uid=None,
        access_grant_revision=None,
        memories=tuple(
            StatusMemory(uid=f"memory-{index}", content=f"Memory {index}")
            for index in range(memory_count)
        ),
        memory_references=(),
        query_views=(),
        embedded_contexts=(),
        grants=(),
        checkpoints=tuple(
            StatusCheckpoint(
                uid=f"checkpoint-{index}",
                timestamp=f"2026-08-{16 - index:02d}T12:00:00",
                command="edit",
                description=f"Change {index}",
                automatic=True,
            )
            for index in range(checkpoint_count)
        ),
    )
    return FrozenStatusFrame(
        current_context_name=context.name,
        profile_name="default",
        contexts=(context,),
    )


def test_application_bounds_first_memory_preview_and_latest_checkpoint_rows():
    source = _StaticStatusSource(_frame())
    request = StatusRequest(include_descendants=True, follow_embeds=True)

    result = inspect_status(request, source=source)

    assert source.requests == [request]
    assert result.current.memory_count == 7
    assert [memory.content for memory in result.current.memory_preview] == [
        "Memory 0",
        "Memory 1",
        "Memory 2",
        "Memory 3",
        "Memory 4",
    ]
    assert result.current.checkpoint_count == 7
    assert [row.description for row in result.current.recent_checkpoints] == [
        "Change 0",
        "Change 1",
        "Change 2",
        "Change 3",
        "Change 4",
    ]


def test_application_has_no_store_command_or_terminal_imports():
    source = Path(status_application.__file__).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    assert not any(
        name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.adapters.console.commands")
        or name == "memcommit.store"
        for name in imported
    )


def test_runtime_returns_typed_status_without_terminal_output(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    context = ops.init("task/current")
    for index in range(7):
        ops.add(context, f"Memory {index}")
    store.save(context)
    store.set_current(context.name)

    result = execute_status(StatusRequest(), store=store)

    assert result.current_context_name == context.name
    assert result.current.memory_count == 7
    assert [memory.content for memory in result.current.memory_preview] == [
        f"Memory {index}" for index in range(5)
    ]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
