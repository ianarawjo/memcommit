"""Terminal-independent Add application and Store adapter contracts."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import memcommit.add_application as add_application
import memcommit.ops as ops
from memcommit.add_application import (
    AddedMemory,
    AddError,
    AddRequest,
    AddResult,
    AddSource,
    FrozenAddTarget,
    run_add,
)
from memcommit.add_runtime import MemoryStoreAddTargetPort, execute_add
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


def _request(*contents: str, mode: str = "TUI_DRAFTS") -> AddRequest:
    return AddRequest(
        contents=contents,
        source=AddSource(
            mode=mode,
            kind="test",
            parser="exact-test-v1",
            raw_text="\n---\n".join(contents),
        ),
        context_locator="target",
    )


class _RecordingPort:
    def __init__(self) -> None:
        self.frozen: list[str | None] = []
        self.appended: list[tuple[FrozenAddTarget, AddRequest]] = []

    def freeze(self, locator: str | None) -> FrozenAddTarget:
        self.frozen.append(locator)
        return FrozenAddTarget("target", "context-uid", token=self)

    def append(
        self,
        target: FrozenAddTarget,
        request: AddRequest,
    ) -> AddResult:
        self.appended.append((target, request))
        return AddResult(
            context_name=target.context_name,
            context_uid=target.context_uid,
            memories=tuple(
                AddedMemory(uid=f"memory-{index}", content=content)
                for index, content in enumerate(request.contents, start=1)
            ),
            checkpoint_uid="checkpoint-uid",
        )


def test_application_adds_one_validated_batch_through_one_port_call() -> None:
    request = _request("First line.\nSecond line.", "Another Memory.")
    port = _RecordingPort()

    result = run_add(request, target_port=port)

    assert result.count == 2
    assert [memory.content for memory in result.memories] == list(request.contents)
    assert port.frozen == ["target"]
    assert port.appended == [(port.appended[0][0], request)]


@pytest.mark.parametrize("contents", [(), ("",), ("  \n",), ("valid", "")])
def test_application_rejects_incomplete_batches_before_opening_target(
    contents: tuple[str, ...],
) -> None:
    port = _RecordingPort()

    with pytest.raises(AddError):
        run_add(_request(*contents), target_port=port)

    assert port.frozen == []
    assert port.appended == []


def test_application_layer_has_no_store_command_or_terminal_imports() -> None:
    source = Path(add_application.__file__).read_text(encoding="utf-8")
    imports: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module)

    assert not any(
        name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
        or name == "memcommit.store"
        for name in imports
    )


def test_store_adapter_saves_multiline_batch_in_one_checkpoint(isolated_store) -> None:
    store = MemoryStore()
    context = ops.init("target")
    store.save(context)
    store.set_current(context.name)
    before = len(store.list_checkpoints("target"))

    result = execute_add(
        _request("First line.\nSecond line.", "Another Memory."),
        store=store,
    )

    saved = store.load_direct("target")
    assert [memory.content for memory in saved.memories.values()] == [
        "First line.\nSecond line.",
        "Another Memory.",
    ]
    checkpoints = store.list_checkpoints("target")
    assert len(checkpoints) == before + 1
    assert checkpoints[0]["uid"] == result.checkpoint_uid
    assert checkpoints[0]["command"] == "add"
    assert checkpoints[0]["args"]["mode"] == "tui-drafts"
    assert checkpoints[0]["args"]["memory_uids"] == [
        memory.uid for memory in result.memories
    ]


def test_store_adapter_rejects_replaced_target_before_writing(isolated_store) -> None:
    store = MemoryStore()
    original = ops.init("target")
    store.save(original)
    store.set_current(original.name)
    port = MemoryStoreAddTargetPort.capture(store)
    frozen = port.freeze("target")

    store.delete("target")
    replacement = ops.init("target")
    store.save(replacement)

    with pytest.raises(ConcurrentContextUpdateError, match="was replaced"):
        run_add(_request("Must not be added."), target_port=port, frozen_target=frozen)

    assert MemoryStore().load_direct("target").memories == {}
