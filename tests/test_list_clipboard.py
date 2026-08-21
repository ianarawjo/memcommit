"""Dual text/structured clipboard tests for `mem list` and `mem ls`."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace

import click
import pytest
from typer.testing import CliRunner

import memcommit.clipboard as clipboard
from memcommit.cli import app
from memcommit.clipboard import ClipboardError, ClipboardPayload
from memcommit.context import QueryContextRef
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def invoke(*args: str):
    return runner.invoke(app, list(args))


@pytest.fixture()
def fake_system_clipboard(monkeypatch):
    state = {"text": ""}

    def write(text: str) -> None:
        state["text"] = text

    def read() -> str:
        return state["text"]

    monkeypatch.setattr(clipboard, "write_system_clipboard", write)
    monkeypatch.setattr(clipboard, "read_system_clipboard", read)
    return state


def test_ls_copy_uses_clean_text_while_preserving_output_and_full_objects(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "source")
    invoke("add", "Café north entrance.\nClosed through Friday.")
    store = MemoryStore()
    context = store.load_current()
    memory = next(iter(context.memories.values()))
    checkpoint_count = len(store.list_checkpoints("source"))
    expected = invoke("ls")

    result = invoke("ls", "--copy")

    assert result.exit_code == 0
    assert result.stdout == expected.stdout
    assert fake_system_clipboard["text"] == (
        "Context: source\n"
        "  1 item\n"
        "\n"
        "  Café north entrance. Closed through Friday.\n"
    )
    assert (
        f"  [memory {memory.uid[:8]}] "
        "Café north entrance. Closed through Friday.\n"
    ) in result.stdout
    assert "[memory " in result.stdout
    assert "[memory " not in fake_system_clipboard["text"]
    assert "Copied 1 item" in result.stderr
    assert "clean text" in result.stderr
    assert "Copied 1 item" not in fake_system_clipboard["text"]
    assert store.current_context_name() == "source"
    assert len(store.list_checkpoints("source")) == checkpoint_count

    stage_path = Path(isolated_store) / "clipboard.json"
    record = json.loads(stage_path.read_text(encoding="utf-8"))
    assert record["producer"] == "list"
    assert record["plain_text"] == fake_system_clipboard["text"]
    assert record["selection"]["context"] == {
        "uid": context.uid,
        "name": "source",
    }
    assert record["selection"]["items"] == [
        {
            "kind": "memory",
            "uid": memory.uid,
            "content": "Café north entrance.\nClosed through Friday.",
        }
    ]
    assert os.stat(stage_path).st_mode & 0o777 == 0o600


def test_list_copy_with_ids_uses_inline_clipboard_and_hanging_stdout(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "source")
    invoke("add", "Keep this object's visible identifier.")
    memory = next(iter(MemoryStore().load_current().memories.values()))
    expected = invoke("ls")
    inline = (
        "Context: source\n"
        "  1 item\n"
        "\n"
        f"  [memory {memory.uid[:8]}] "
        "Keep this object's visible identifier.\n"
    )

    copied = invoke("list", "--copy", "--with-ids")

    assert copied.exit_code == 0
    assert copied.stdout == expected.stdout
    assert expected.stdout == (
        "Context: source\n"
        "  1 item\n"
        "\n"
        f"  [memory {memory.uid[:8]}] "
        "Keep this object's visible identifier.\n"
    )
    assert fake_system_clipboard["text"] == inline
    assert "[memory " in fake_system_clipboard["text"]
    assert "text with IDs" in copied.stderr
    record = json.loads(
        (Path(isolated_store) / "clipboard.json").read_text(encoding="utf-8")
    )
    assert record["plain_text"] == inline

    pasted = invoke("ls", "--paste")

    assert pasted.exit_code == 0
    assert pasted.stdout == inline


def test_list_long_memory_uses_hanging_indent_but_clipboard_stays_one_line(
    isolated_store,
    fake_system_clipboard,
    monkeypatch,
):
    monkeypatch.setenv("COLUMNS", "88")
    invoke("init", "source")
    content = (
        "Use the term formative evaluation for studies seeking design "
        "modification evidence, and distinguish it from final efficacy judgments."
    )
    invoke("add", content)
    memory = next(iter(MemoryStore().load_current().memories.values()))

    copied = invoke("ls", "--copy", "--with-ids")

    label = f"  [memory {memory.uid[:8]}]"
    visible_lines = copied.stdout.splitlines()
    first = next(line for line in visible_lines if line.startswith(label))
    continuation = visible_lines[visible_lines.index(first) + 1]
    assert first.startswith(f"{label} Use the term")
    assert continuation.startswith(" " * (len(label) + 1) + "modification")
    assert fake_system_clipboard["text"] == (
        "Context: source\n"
        "  1 item\n"
        "\n"
        f"{label} {content}\n"
    )


def test_recursive_list_uses_same_hanging_and_inline_clipboard_contract(
    isolated_store,
    fake_system_clipboard,
    monkeypatch,
):
    monkeypatch.setenv("COLUMNS", "88")
    content = (
        "The agent can approve contribution labels such as principles, models, "
        "or guidelines only if they align with the abstraction level of the "
        "actual deliverables."
    )
    invoke("init", "child")
    invoke("add", content)
    memory = next(iter(MemoryStore().load_current().memories.values()))
    invoke("init", "parent")
    invoke("embed", "child", "--into", "parent")

    copied = invoke("ls", "-R", "parent", "--copy", "--with-ids")

    label = f"    [memory {memory.uid[:8]}]"
    visible_lines = copied.stdout.splitlines()
    first = next(line for line in visible_lines if line.startswith(label))
    continuation = visible_lines[visible_lines.index(first) + 1]
    assert first.startswith(f"{label} The agent can approve")
    assert continuation.startswith(" " * (len(label) + 1))
    assert continuation.strip()
    assert f"{label} {content}\n" in fake_system_clipboard["text"]


def test_list_copy_and_ls_paste_are_coequal_and_snapshot_based(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "source")
    invoke("add", "Original source fact.")
    annotated = invoke("list")
    copied = invoke("list", "--copy")
    assert copied.exit_code == 0
    copied_text = fake_system_clipboard["text"]
    assert copied.stdout == annotated.stdout
    assert "[memory " in copied.stdout
    assert "[memory " not in copied_text

    store = MemoryStore()
    source = store.load("source")
    memory = next(iter(source.memories.values()))
    memory.content = "Changed after copy."
    store.save(source)
    store.delete("source")
    assert store.current_context_name() is None

    pasted = invoke("ls", "--paste")

    assert pasted.exit_code == 0
    assert pasted.stdout == copied_text
    assert "Original source fact." in pasted.stdout
    assert "Changed after copy." not in pasted.stdout
    assert "no Context changes" in pasted.stderr
    assert not store.context_exists("source")


def test_recursive_copy_freezes_visible_tree_and_paste_replays_it(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "child")
    invoke("add", "Nested fact.")
    invoke("init", "parent")
    invoke("add", "Parent fact.")
    invoke("embed", "child", "--into", "parent")
    annotated = invoke("ls", "-R", "parent")

    copied = invoke("ls", "-R", "parent", "--copy")
    assert copied.exit_code == 0
    copied_text = fake_system_clipboard["text"]
    assert copied.stdout == annotated.stdout
    assert copied_text == (
        "Context: parent\n"
        "  2 items\n"
        "\n"
        "  child/ · VIA EMBED\n"
        "    Nested fact.\n"
        "  Parent fact.\n"
    )
    MemoryStore().delete("parent")
    MemoryStore().delete("child")

    pasted = invoke("list", "--paste")

    assert pasted.exit_code == 0
    assert pasted.stdout == copied_text
    assert "Nested fact." in pasted.stdout
    assert "Copied 3 items" in copied.stderr


def test_copy_freezes_a_typed_namespace_child_for_later_paste(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "parent/child")
    child = MemoryStore().load_current()
    invoke("add", "Child-only fact.")
    invoke("init", "parent")
    invoke("add", "Parent fact.")

    copied = invoke("ls", "parent", "--copy")

    assert copied.exit_code == 0
    assert "Child-only fact." not in copied.stdout
    assert fake_system_clipboard["text"] == (
        "Context: parent\n"
        "  2 items\n"
        "\n"
        "  parent/child/ · DESCENDANT\n"
        "  Parent fact.\n"
    )
    record = json.loads(
        (Path(isolated_store) / "clipboard.json").read_text(encoding="utf-8")
    )
    assert record["selection"]["schema_version"] == 2
    assert record["selection"]["items"][0] == {
        "kind": "namespace_context",
        "uid": child.uid,
        "name": "parent/child",
        "cycle": False,
        "children": None,
    }

    store = MemoryStore()
    store.delete("parent")
    store.delete("parent/child")

    pasted = invoke("list", "--paste")

    assert pasted.exit_code == 0
    assert pasted.stdout == fake_system_clipboard["text"]
    assert "parent/child/" in pasted.stdout
    assert not store.context_exists("parent")
    assert not store.context_exists("parent/child")


def test_copy_stages_query_pointer_without_hidden_source_content(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "wiki")
    store = MemoryStore()
    source = store.create_query_source(
        "contracts/private",
        "SECRET QUERY-ONLY CONTRACT TEXT",
    )
    context = store.load_current()
    context.add(
        QueryContextRef(
            uid="query-ref-uid",
            name="contracts/private",
            target_source_uid=source.uid,
            provider="test-provider",
        )
    )
    store.save(context)

    result = invoke("ls", "--copy")

    assert result.exit_code == 0
    stage_text = (
        Path(isolated_store) / "clipboard.json"
    ).read_text(encoding="utf-8")
    assert "contracts/private" in stage_text
    assert source.uid in stage_text
    assert "SECRET QUERY-ONLY CONTRACT TEXT" not in stage_text
    assert "SECRET QUERY-ONLY CONTRACT TEXT" not in fake_system_clipboard["text"]
    assert "contracts/private/ · query view" in fake_system_clipboard["text"]
    assert "[query view " not in fake_system_clipboard["text"]


def test_clean_copy_keeps_reference_meaning_without_object_ids(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "source")
    invoke("add", "Referenced atomic name.")
    source = MemoryStore().load_current()
    source_memory_uid = next(iter(source.memories))
    invoke("init", "target")
    invoke("reference", source_memory_uid[:8], "--from", "source")

    result = invoke("ls", "--copy")

    assert result.exit_code == 0
    assert "[reference " in result.stdout
    assert "READ ONLY" in result.stdout
    assert (
        "Referenced atomic name. -> source"
        in fake_system_clipboard["text"]
    )
    assert "[memory ref " not in fake_system_clipboard["text"]
    assert f"#{source_memory_uid[:8]}" not in fake_system_clipboard["text"]
    record = json.loads(
        (Path(isolated_store) / "clipboard.json").read_text(encoding="utf-8")
    )
    assert record["selection"]["items"][0]["target_memory_uid"] == (
        source_memory_uid
    )


def test_list_places_colored_relationship_and_source_identity_before_content(
    isolated_store,
):
    invoke("init", "practice/3")
    invoke("add", "Write each proposition exactly.")
    store = MemoryStore()
    source = store.load_current()
    source_memory_uid = next(iter(source.memories))
    invoke("init", "practice/4")
    invoke(
        "embed",
        source_memory_uid[:8],
        "--from",
        "practice/3",
        "--into",
        "practice/4",
    )
    invoke("reference", source_memory_uid[:8], "--from", "practice/3")
    target = store.load("practice/4")
    embedded, reference = list(target.iter_items())

    result = runner.invoke(app, ["list", "practice/4"], color=True)

    assert result.exit_code == 0
    plain = click.unstyle(result.stdout)
    assert plain == (
        "Context: practice/4\n"
        "  2 items\n"
        "\n"
        f"  [embedded {embedded.uid[:8]}] "
        f"[practice/3][memory {source_memory_uid[:8]}] "
        "Write each proposition exactly.  READ ONLY\n"
        f"  [reference {reference.uid[:8]}] "
        f"[practice/3][memory {source_memory_uid[:8]}] "
        "Write each proposition exactly.  READ ONLY\n"
    )
    assert "\x1b[38;2;238;212;159membedded\x1b[0m" in result.stdout
    assert "\x1b[38;2;198;160;246mreference\x1b[0m" in result.stdout


def test_clean_copy_keeps_user_authored_bracket_text_literal(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "source")
    invoke("add", "[memory literal] This is user-authored text.")

    result = invoke("ls", "--copy")

    assert result.exit_code == 0
    assert "[memory " in result.stdout
    assert (
        "  [memory literal] This is user-authored text.\n"
        in fake_system_clipboard["text"]
    )
    assert fake_system_clipboard["text"].count("[memory") == 1


def test_clean_copy_keeps_a_snapshot_after_its_source_is_deleted(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "source")
    invoke("add", "Fact that will become unavailable.")
    source_memory_uid = next(iter(MemoryStore().load_current().memories))
    invoke("init", "target")
    invoke("reference", source_memory_uid[:8], "--from", "source")
    MemoryStore().delete("source")

    result = invoke("ls", "target", "--copy")

    assert result.exit_code == 0
    assert "reference · Fact that will become unavailable." in fake_system_clipboard[
        "text"
    ]
    assert "READ ONLY" in fake_system_clipboard["text"]
    assert source_memory_uid[:8] not in fake_system_clipboard["text"]


def test_ls_paste_rejects_overwritten_system_clipboard(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "source")
    invoke("add", "Copied fact.")
    assert invoke("ls", "--copy").exit_code == 0
    fake_system_clipboard["text"] = "Text copied in another application."

    result = invoke("ls", "--paste")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "system clipboard changed" in result.stderr


def test_ls_paste_without_stage_fails_without_creating_store(
    isolated_store,
    fake_system_clipboard,
):
    fake_system_clipboard["text"] = "arbitrary external text"

    result = invoke("ls", "--paste")

    assert result.exit_code == 1
    assert "run 'mem ls --copy' first" in result.stderr
    assert not Path(isolated_store).exists()


def test_missing_store_race_never_accepts_an_unlocked_payload(
    isolated_store,
    fake_system_clipboard,
    monkeypatch,
):
    raced_payload = ClipboardPayload.create(
        producer="wrong-producer",
        plain_text="raced text",
        selection={"source": "raced"},
    )
    monkeypatch.setattr(clipboard, "_read_stage", lambda: raced_payload)
    fake_system_clipboard["text"] = raced_payload.plain_text

    with pytest.raises(ClipboardError, match="run 'mem ls --copy' first"):
        clipboard.load_payload(expected_producer="list")

    assert not Path(isolated_store).exists()


@pytest.mark.parametrize(
    "arguments",
    [
        ("ls", "--copy", "--paste"),
        ("ls", "source", "--paste"),
        ("list", "-R", "--paste"),
        ("list", "-d", "--paste"),
        ("ls", "--with-ids"),
        ("ls", "--paste", "--with-ids"),
    ],
)
def test_list_clipboard_rejects_ambiguous_inputs(
    isolated_store,
    fake_system_clipboard,
    arguments,
):
    result = invoke(*arguments)

    assert result.exit_code == 1
    assert result.stdout == ""


def test_failed_copy_invalidates_previous_structured_stage(
    isolated_store,
    fake_system_clipboard,
    monkeypatch,
):
    invoke("init", "source")
    invoke("add", "Same visible text.")
    assert invoke("ls", "--copy").exit_code == 0
    stage_path = Path(isolated_store) / "clipboard.json"
    assert stage_path.exists()

    def fail_write(_text: str) -> None:
        raise ClipboardError("simulated clipboard failure")

    monkeypatch.setattr(clipboard, "write_system_clipboard", fail_write)
    result = invoke("ls", "--copy")

    assert result.exit_code == 1
    assert "simulated clipboard failure" in result.stderr
    assert not stage_path.exists()


def test_concurrent_copies_keep_one_coherent_text_and_stage_pair(
    isolated_store,
    monkeypatch,
):
    state = {"text": ""}
    first_read_started = threading.Event()
    release_first_read = threading.Event()
    second_started = threading.Event()
    second_write_started = threading.Event()
    failures: list[BaseException] = []

    first = ClipboardPayload.create(
        producer="list",
        plain_text="first text",
        selection={"source": "first"},
    )
    second = ClipboardPayload.create(
        producer="list",
        plain_text="second text",
        selection={"source": "second"},
    )

    def write(text: str) -> None:
        if text == second.plain_text:
            second_write_started.set()
        state["text"] = text

    def read() -> str:
        text = state["text"]
        if text == first.plain_text:
            first_read_started.set()
            assert release_first_read.wait(timeout=2)
        return state["text"]

    def run_copy(payload: ClipboardPayload, *, mark_second: bool = False) -> None:
        if mark_second:
            second_started.set()
        try:
            clipboard.copy_payload(payload)
        except BaseException as error:
            failures.append(error)

    monkeypatch.setattr(clipboard, "write_system_clipboard", write)
    monkeypatch.setattr(clipboard, "read_system_clipboard", read)

    first_thread = threading.Thread(target=run_copy, args=(first,))
    second_thread = threading.Thread(
        target=run_copy,
        args=(second,),
        kwargs={"mark_second": True},
    )
    first_thread.start()
    assert first_read_started.wait(timeout=2)
    second_thread.start()
    assert second_started.wait(timeout=2)
    assert not second_write_started.wait(timeout=0.2)

    release_first_read.set()
    first_thread.join(timeout=2)
    second_thread.join(timeout=2)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert failures == []
    assert state["text"] == second.plain_text
    record = json.loads(
        (Path(isolated_store) / "clipboard.json").read_text(encoding="utf-8")
    )
    assert record["plain_text"] == second.plain_text
    assert record["selection"] == second.selection


def test_corrupt_structured_stage_fails_closed(
    isolated_store,
    fake_system_clipboard,
):
    store_dir = Path(isolated_store)
    store_dir.mkdir(parents=True)
    (store_dir / "clipboard.json").write_text(
        '{"schema_version": 999}',
        encoding="utf-8",
    )

    result = invoke("ls", "--paste")

    assert result.exit_code == 1
    assert "structured clipboard" in result.stderr


def test_paste_rejects_validly_hashed_text_that_matches_neither_renderer(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "source")
    invoke("add", "Canonical source fact.")
    assert invoke("ls", "--copy").exit_code == 0
    stage_path = Path(isolated_store) / "clipboard.json"
    record = json.loads(stage_path.read_text(encoding="utf-8"))
    arbitrary_text = "Validly hashed but not a list rendering.\n"
    replacement = ClipboardPayload.create(
        producer="list",
        plain_text=arbitrary_text,
        selection=record["selection"],
    )
    stage_path.write_text(
        json.dumps(replacement.to_dict()),
        encoding="utf-8",
    )
    fake_system_clipboard["text"] = arbitrary_text

    result = invoke("ls", "--paste")

    assert result.exit_code == 1
    assert "object snapshot disagree" in result.stderr


def test_paste_rejects_a_namespace_row_outside_its_frozen_parent(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "parent/child")
    invoke("init", "parent")
    assert invoke("ls", "parent", "--copy").exit_code == 0
    stage_path = Path(isolated_store) / "clipboard.json"
    record = json.loads(stage_path.read_text(encoding="utf-8"))
    record["selection"]["items"][0]["name"] = "other/child"
    forged_text = fake_system_clipboard["text"].replace(
        "parent/child/",
        "other/child/",
    )
    replacement = ClipboardPayload.create(
        producer="list",
        plain_text=forged_text,
        selection=record["selection"],
    )
    stage_path.write_text(
        json.dumps(replacement.to_dict()),
        encoding="utf-8",
    )
    fake_system_clipboard["text"] = forged_text

    result = invoke("ls", "--paste")

    assert result.exit_code == 1
    assert "staged list snapshot is invalid" in result.stderr


def test_system_clipboard_adapter_uses_fixed_macos_commands():
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        if command == ["/usr/bin/pbpaste"]:
            return SimpleNamespace(
                returncode=0,
                stdout="안녕\n".encode(),
                stderr=b"",
            )
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    clipboard.write_system_clipboard(
        "안녕\n",
        runner=fake_runner,
        platform_name="darwin",
    )
    text = clipboard.read_system_clipboard(
        runner=fake_runner,
        platform_name="darwin",
    )

    assert text == "안녕\n"
    assert calls[0][0] == ["/usr/bin/pbcopy"]
    assert calls[0][1]["input"] == "안녕\n".encode()
    assert calls[1][0] == ["/usr/bin/pbpaste"]


def test_system_clipboard_adapter_rejects_unsupported_platform():
    calls = []

    with pytest.raises(ClipboardError, match="only on macOS"):
        clipboard.write_system_clipboard(
            "text",
            runner=lambda *args, **kwargs: calls.append((args, kwargs)),
            platform_name="linux",
        )

    assert calls == []


@pytest.mark.parametrize(
    "operation",
    ["write", "read"],
)
def test_system_clipboard_adapter_wraps_process_failures(operation):
    def failed_runner(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=b"",
            stderr=b"failed",
        )

    with pytest.raises(ClipboardError):
        if operation == "write":
            clipboard.write_system_clipboard(
                "text",
                runner=failed_runner,
                platform_name="darwin",
            )
        else:
            clipboard.read_system_clipboard(
                runner=failed_runner,
                platform_name="darwin",
            )


def test_payload_rejects_mismatched_text_digest():
    payload = ClipboardPayload.create(
        producer="list",
        plain_text="visible",
        selection={"items": []},
    ).to_dict()
    payload["plain_text"] = "tampered"

    with pytest.raises(ClipboardError, match="invalid"):
        ClipboardPayload.from_dict(payload)


def test_payload_rejects_mismatched_structured_selection_digest():
    payload = ClipboardPayload.create(
        producer="list",
        plain_text="same visible text",
        selection={
            "items": [
                {
                    "uid": "visible12-hidden-identity",
                    "provider": "original-provider",
                }
            ]
        },
    ).to_dict()
    payload["selection"]["items"][0]["provider"] = "tampered-provider"

    with pytest.raises(ClipboardError, match="invalid"):
        ClipboardPayload.from_dict(payload)
