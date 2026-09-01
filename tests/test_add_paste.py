"""System-clipboard intake tests for ``mem add --paste``."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from memcommit.adapters.console.clipboard import ClipboardError
from memcommit.adapters.console.commands.add import command as add
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def invoke(*args: str, stdin: str | None = None):
    return runner.invoke(app, list(args), input=stdin)


def direct_memories(context_name: str) -> list[Memory]:
    items = list(MemoryStore().load(context_name).iter_items())
    assert all(isinstance(item, Memory) for item in items)
    return items


def test_add_paste_reads_clipboard_and_renders_the_complete_saved_batch(
    isolated_store,
    monkeypatch,
):
    invoke("init", "intake")
    store = MemoryStore()
    checkpoint_count = len(store.list_checkpoints("intake"))
    payload = "  first private fact  \n\n* second private fact\n세 번째 사실"
    reads: list[None] = []

    def read_clipboard() -> str:
        reads.append(None)
        return payload

    monkeypatch.setattr(add, "read_system_clipboard", read_clipboard)

    result = invoke("add", "--paste")

    assert result.exit_code == 0
    assert reads == [None]
    assert "lines pasted" not in result.output
    assert "F2/Ctrl-D" not in result.output
    assert "[y/N]" not in result.output
    assert "Added 3 Memories to 'intake'." in result.output
    memories = direct_memories("intake")
    assert [memory.content for memory in memories] == [
        "first private fact",
        "* second private fact",
        "세 번째 사실",
    ]
    for memory in memories:
        assert f"  [{memory.uid[:8]}] {memory.content}" in result.output
    checkpoints = store.list_checkpoints("intake")
    assert len(checkpoints) == checkpoint_count + 1
    assert f"Checkpoint [{checkpoints[0]['uid'][:8]}]." in result.output
    assert checkpoints[0]["command"] == "add"
    args = checkpoints[0]["args"]
    assert {key: args[key] for key in ("mode", "count", "contents")} == {
        "mode": "paste",
        "count": 3,
        "contents": [
            "first private fact",
            "* second private fact",
            "세 번째 사실",
        ],
    }
    assert args["memory_uids"] == [memory.uid for memory in memories]
    assert args["source"]["kind"] == "system-clipboard"
    assert args["source"]["raw_text"] == payload
    assert args["source"]["parser"] == ("stripped-nonempty-physical-lines-v1")
    assert len(args["source"]["sha256"]) == 64


def test_add_paste_uses_latest_context_contents_after_clipboard_read(
    isolated_store,
    monkeypatch,
):
    invoke("init", "intake")

    def read_after_concurrent_update() -> str:
        concurrent_store = MemoryStore()
        concurrent_context = concurrent_store.load("intake")
        concurrent_context.add("concurrent fact")
        concurrent_store.save(concurrent_context)
        return "clipboard fact"

    monkeypatch.setattr(add, "read_system_clipboard", read_after_concurrent_update)

    result = invoke("add", "--paste")

    assert result.exit_code == 0
    assert [memory.content for memory in direct_memories("intake")] == [
        "concurrent fact",
        "clipboard fact",
    ]


@pytest.mark.parametrize(
    ("clipboard_result", "error_text"),
    [
        (" \n\t\n", "no non-empty lines"),
        (
            ClipboardError("The system clipboard does not contain valid UTF-8 text."),
            "valid UTF-8 text",
        ),
    ],
)
def test_add_paste_invalid_clipboard_does_not_mutate(
    isolated_store,
    monkeypatch,
    clipboard_result,
    error_text,
):
    invoke("init", "intake")
    store = MemoryStore()
    checkpoint_count = len(store.list_checkpoints("intake"))

    def read_clipboard() -> str:
        if isinstance(clipboard_result, Exception):
            raise clipboard_result
        return clipboard_result

    monkeypatch.setattr(add, "read_system_clipboard", read_clipboard)

    result = invoke("add", "--paste")

    assert result.exit_code == 1
    assert error_text in result.output
    assert direct_memories("intake") == []
    assert len(store.list_checkpoints("intake")) == checkpoint_count


@pytest.mark.parametrize(
    "arguments",
    [
        ("inline", "--paste"),
        ("first", "second", "--paste"),
    ],
)
def test_add_paste_is_mutually_exclusive_with_other_sources(
    isolated_store,
    arguments,
):
    invoke("init", "intake")

    result = invoke("add", *arguments)

    assert result.exit_code == 1
    assert "positional MEMORY values or --paste, not both" in result.output
    assert direct_memories("intake") == []
