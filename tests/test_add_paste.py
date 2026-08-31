"""Interactive paste intake tests."""

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from memcommit.application.capabilities import ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.create_copy_connect.add import command as add
from memcommit.adapters.console.terminal.components import paste_input
from memcommit.adapters.console.terminal.components.paste_input import PasteCancelled, capture_paste
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore

runner = CliRunner()


class RecordingOutput(DummyOutput):
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, data: str) -> None:
        self.writes.append(data)

    def write_raw(self, data: str) -> None:
        self.writes.append(data)


def invoke(*args: str, stdin: str | None = None):
    return runner.invoke(app, list(args), input=stdin)


def direct_memories(context_name: str) -> list[Memory]:
    items = list(MemoryStore().load(context_name).iter_items())
    assert all(isinstance(item, Memory) for item in items)
    return items


def test_capture_paste_collects_bracketed_payload_without_rendering_it():
    output = RecordingOutput()
    secret = "private first line\r\nprivate second line\rprivate third line"

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            f"\x1b[200~{secret}\x1b[201~\x04"
        )
        captured = capture_paste(
            app_input=pipe_input,
            app_output=output,
            require_tty=False,
        )

    assert captured == (
        "private first line\nprivate second line\nprivate third line"
    )
    rendered = "".join(output.writes)
    assert "Paste text" in rendered
    assert "F2/Ctrl-D: add" in rendered
    assert "private first line" not in rendered
    assert "private second line" not in rendered
    assert "private third line" not in rendered


def test_capture_paste_requires_an_interactive_terminal(monkeypatch):
    class NonTerminal:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(paste_input.sys, "stdin", NonTerminal())

    with pytest.raises(ValueError, match="use --input -"):
        capture_paste()


def test_capture_paste_separates_multiple_paste_blocks():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[200~first block\x1b[201~"
            "\x1b[200~second block\x1b[201~"
            "\x04"
        )
        captured = capture_paste(
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert captured == "first block\nsecond block"


def test_capture_paste_ctrl_c_cancels():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x03")
        with pytest.raises(PasteCancelled):
            capture_paste(
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )


def test_capture_paste_escape_cancels():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        with pytest.raises(PasteCancelled):
            capture_paste(
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )


def test_add_paste_saves_in_order_with_one_checkpoint_and_no_echo(
    isolated_store,
    monkeypatch,
):
    invoke("init", "intake")
    store = MemoryStore()
    checkpoint_count = len(store.list_checkpoints("intake"))
    payload = "  first private fact  \n\n* second private fact\n세 번째 사실"
    monkeypatch.setattr(add, "capture_paste", lambda: payload)

    result = invoke("add", "--paste")

    assert result.exit_code == 0
    assert "[3 lines pasted]" in result.output
    assert "[y/N]" not in result.output
    assert "Added 3 Memories to 'intake'." in result.output
    assert "first private fact" not in result.output
    assert "second private fact" not in result.output
    assert "세 번째 사실" not in result.output
    memories = direct_memories("intake")
    assert [memory.content for memory in memories] == [
        "first private fact",
        "* second private fact",
        "세 번째 사실",
    ]
    checkpoints = store.list_checkpoints("intake")
    assert len(checkpoints) == checkpoint_count + 1
    assert checkpoints[0]["command"] == "add"
    args = checkpoints[0]["args"]
    assert {
        key: args[key]
        for key in ("mode", "count", "contents")
    } == {
        "mode": "paste",
        "count": 3,
        "contents": [
            "first private fact",
            "* second private fact",
            "세 번째 사실",
        ],
    }
    assert args["memory_uids"] == [memory.uid for memory in memories]
    assert args["source"]["kind"] == "interactive-paste"
    assert args["source"]["raw_text"] == payload
    assert args["source"]["parser"] == (
        "stripped-nonempty-physical-lines-v1"
    )
    assert len(args["source"]["sha256"]) == 64


def test_add_paste_reloads_context_before_saving(
    isolated_store,
    monkeypatch,
):
    invoke("init", "intake")

    def capture_after_concurrent_update():
        concurrent_store = MemoryStore()
        concurrent_context = concurrent_store.load("intake")
        concurrent_context.add("concurrent fact")
        concurrent_store.save(concurrent_context)
        return "pasted fact"

    monkeypatch.setattr(add, "capture_paste", capture_after_concurrent_update)

    result = invoke("add", "--paste")

    assert result.exit_code == 0
    assert [
        memory.content for memory in direct_memories("intake")
    ] == ["concurrent fact", "pasted fact"]


def test_add_paste_rejects_context_recreated_during_capture(
    isolated_store,
    monkeypatch,
):
    invoke("init", "intake")

    def capture_after_context_replacement():
        concurrent_store = MemoryStore()
        concurrent_store.delete("intake")
        concurrent_store.save(ops.init("intake"))
        return "must not be stored"

    monkeypatch.setattr(
        add,
        "capture_paste",
        capture_after_context_replacement,
    )

    result = invoke("add", "--paste")

    assert result.exit_code == 1
    assert "was replaced while paste mode was open" in result.output
    assert direct_memories("intake") == []


def test_add_paste_finish_commits_without_a_second_confirmation(
    isolated_store,
    monkeypatch,
):
    invoke("init", "intake")
    store = MemoryStore()
    checkpoint_count = len(store.list_checkpoints("intake"))
    monkeypatch.setattr(
        add,
        "capture_paste",
        lambda: "store this immediately",
    )

    result = invoke("add", "--paste")

    assert result.exit_code == 0
    assert "[y/N]" not in result.output
    assert "store this immediately" not in result.output
    assert [memory.content for memory in direct_memories("intake")] == [
        "store this immediately"
    ]
    assert len(store.list_checkpoints("intake")) == checkpoint_count + 1


@pytest.mark.parametrize(
    ("capture_result", "error_text"),
    [
        (" \n\t\n", "no non-empty lines"),
        (
            ValueError("--paste requires an interactive terminal."),
            "requires an interactive terminal",
        ),
    ],
)
def test_add_paste_invalid_input_does_not_mutate(
    isolated_store,
    monkeypatch,
    capture_result,
    error_text,
):
    invoke("init", "intake")
    store = MemoryStore()
    checkpoint_count = len(store.list_checkpoints("intake"))

    def fake_capture():
        if isinstance(capture_result, Exception):
            raise capture_result
        return capture_result

    monkeypatch.setattr(add, "capture_paste", fake_capture)

    result = invoke("add", "--paste")

    assert result.exit_code == 1
    assert error_text in result.output
    assert direct_memories("intake") == []
    assert len(store.list_checkpoints("intake")) == checkpoint_count


def test_add_paste_cancellation_does_not_mutate(
    isolated_store,
    monkeypatch,
):
    invoke("init", "intake")
    store = MemoryStore()
    checkpoint_count = len(store.list_checkpoints("intake"))

    def cancel():
        raise PasteCancelled

    monkeypatch.setattr(add, "capture_paste", cancel)

    result = invoke("add", "--paste")

    assert result.exit_code == 0
    assert "Aborted — no changes made." in result.output
    assert direct_memories("intake") == []
    assert len(store.list_checkpoints("intake")) == checkpoint_count


@pytest.mark.parametrize(
    "arguments",
    [
        ("inline", "--paste"),
        ("--input", "-", "--paste"),
        ("inline", "--input", "-", "--paste"),
    ],
)
def test_add_paste_is_mutually_exclusive_with_other_sources(
    isolated_store,
    arguments,
):
    invoke("init", "intake")

    result = invoke("add", *arguments)

    assert result.exit_code == 1
    assert "exactly one of INFO, --input, or --paste" in result.output
    assert direct_memories("intake") == []
