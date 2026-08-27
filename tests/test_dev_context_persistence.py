"""Persistence and current-state boundaries for hidden developer commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import memcommit.config as config_module
import memcommit.application.ops as ops
import memcommit.semantic.llm as llm_module
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Context, Memory, QueryContextRef
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _patch_fake_generator(
    monkeypatch,
    *,
    before_response=None,
    items: tuple[str, ...] = ("generated fact",),
) -> None:
    class FakeConfig:
        def require_llm_model(self) -> str:
            return "fake-model"

    class FakeClient:
        def __init__(self, *, model: str):
            assert model == "fake-model"

        def chat(self, _messages) -> str:
            if before_response is not None:
                before_response()
            return json.dumps({"memories": list(items)})

    monkeypatch.setattr(config_module, "Config", FakeConfig)
    monkeypatch.setattr(llm_module, "LLMClient", FakeClient)


def test_query_source_install_freezes_relative_target_and_preserves_pointer(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store = MemoryStore()
    child = ops.init("team/child")
    store.save(child)
    target = ops.init("team/reference")
    ops.embed(child, target)
    store.save(target)
    active = ops.init("team/active")
    store.save(active)
    elsewhere = ops.init("elsewhere")
    store.save(elsewhere)
    store.set_current(active.name)
    store.delete(child.name)

    source_path = tmp_path / "source.md"
    source_path.write_text("concealed source", encoding="utf-8")
    original_read_text = Path.read_text

    def switch_then_read(path, *args, **kwargs):
        if path == source_path:
            store.set_current(elsewhere.name)
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", switch_then_read)

    result = runner.invoke(
        app,
        [
            "dev",
            "query-source",
            "install",
            "concealed",
            "--from",
            str(source_path),
            "--into",
            "../reference",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "in 'team/reference'" in result.output
    assert store.current_context_name() == elsewhere.name
    persisted = store.load_direct(target.name)
    assert isinstance(persisted.memories[child.uid], Context)
    query_refs = [
        item
        for item in persisted.iter_items()
        if isinstance(item, QueryContextRef)
    ]
    assert len(query_refs) == 1
    checkpoint = store.list_checkpoints(target.name)[0]
    assert checkpoint["args"]["into"] == target.name
    assert checkpoint["snapshot"]["memories"][child.uid]["type"] == (
        "context_ref"
    )


def test_dev_fake_rejects_concurrent_destination_owner(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current = ops.init("current")
    store.save(current)
    store.set_current(current.name)
    rival = ops.init("generated")
    rival.add("rival fact")

    def publish_rival() -> None:
        store.create_context(rival)

    _patch_fake_generator(monkeypatch, before_response=publish_rival)

    result = runner.invoke(
        app,
        ["dev", "fake", "generated", "test prompt"],
    )

    assert result.exit_code == 1
    assert "already exists" in result.stderr
    persisted = store.load_direct(rival.name)
    assert persisted.uid == rival.uid
    assert [
        item.content
        for item in persisted.iter_items()
        if isinstance(item, Memory)
    ] == ["rival fact"]
    assert store.current_context_name() == current.name


def test_dev_fake_creates_exclusively_and_switches(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    initial = ops.init("initial")
    store.save(initial)
    store.set_current(initial.name)
    _patch_fake_generator(monkeypatch, items=("first", "second"))

    result = runner.invoke(
        app,
        ["dev", "fake", "generated", "test prompt"],
    )

    assert result.exit_code == 0, result.output
    assert store.current_context_name() == "generated"
    generated = store.load_direct("generated")
    assert [
        item.content
        for item in generated.iter_items()
        if isinstance(item, Memory)
    ] == ["first", "second"]


def test_dev_fake_preserves_created_context_when_current_changes(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    initial = ops.init("initial")
    store.save(initial)
    elsewhere = ops.init("elsewhere")
    store.save(elsewhere)
    store.set_current(initial.name)

    def switch_current() -> None:
        store.set_current(elsewhere.name)

    _patch_fake_generator(monkeypatch, before_response=switch_current)

    result = runner.invoke(
        app,
        ["dev", "fake", "generated", "test prompt"],
    )

    assert result.exit_code == 1
    assert "could not switch" in result.stderr
    assert "preserved" in result.stderr
    assert store.current_context_name() == elsewhere.name
    generated = store.load_direct("generated")
    assert [
        item.content
        for item in generated.iter_items()
        if isinstance(item, Memory)
    ] == ["generated fact"]
