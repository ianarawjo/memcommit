"""Plain-text system clipboard tests for `mem list` and `mem ls`."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import click
import pytest
from typer.testing import CliRunner

import memcommit.adapters.console.clipboard as clipboard
from memcommit.adapters.console.commands.list import command as list_command
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.clipboard import ClipboardError
from memcommit.core.context import Context, Memory, QueryContextRef
from memcommit.application.capabilities.context_snapshot import ContextSnapshotRef, context_snapshot_digest
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def invoke(*args: str):
    return runner.invoke(app, list(args))


@pytest.fixture()
def fake_system_clipboard(monkeypatch):
    state = {"text": ""}

    def write(text: str) -> None:
        state["text"] = text

    monkeypatch.setattr(list_command, "write_system_clipboard", write)
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
        "  1 memory\n"
        "  0 subcontexts\n"
        "\n"
        "  Café north entrance. Closed through Friday.\n"
    )
    assert (
        f"  [memory {memory.uid[:8]}] "
        "Café north entrance. Closed through Friday.\n"
    ) in result.stdout
    assert "[memory " in result.stdout
    assert "[memory " not in fake_system_clipboard["text"]
    assert "Copied 1 memory and 0 subcontexts" in result.stderr
    assert "clean text" in result.stderr
    assert "Copied 1 memory" not in fake_system_clipboard["text"]
    assert store.current_context_name() == "source"
    assert len(store.list_checkpoints("source")) == checkpoint_count


def test_list_uses_profile_readable_uid_prefixes_beyond_the_visible_snapshot(
    isolated_store,
    fake_system_clipboard,
):
    store = MemoryStore()
    visible = Context(uid="visible-context-uid", name="notes")
    visible_collision = Memory(
        uid="deadbeef-1111-1111-1111-111111111111",
        content="Visible colliding Memory.",
    )
    hidden = Context(uid="hidden-context-uid", name="archive")
    hidden_collision = Memory(
        uid="deadbeef-2222-2222-2222-222222222222",
        content="Unlisted colliding Memory.",
    )
    unique = Memory(
        uid="cafebabe-3333-3333-3333-333333333333",
        content="Already unique Memory.",
    )
    visible.add(visible_collision)
    visible.add(unique)
    hidden.add(hidden_collision)
    store.save(visible)
    store.save(hidden)
    store.set_current(visible.name)

    copied = invoke("list", "--copy", "--with-ids")

    assert copied.exit_code == 0, copied.output
    assert "[memory deadbeef-1] Visible colliding Memory." in copied.stdout
    assert "Unlisted colliding Memory." not in copied.stdout
    assert "Unlisted colliding Memory." not in fake_system_clipboard["text"]
    assert "[memory cafebabe] Already unique Memory." in copied.stdout
    assert "[memory deadbeef]" not in copied.stdout
    assert fake_system_clipboard["text"] == copied.stdout


def test_list_uid_prefixes_include_retained_snapshot_descendants(isolated_store):
    store = MemoryStore()
    visible = Context(uid="visible-context-uid", name="notes")
    visible.add(
        Memory(
            uid="deadbeef-1111-1111-1111-111111111111",
            content="Visible colliding Memory.",
        )
    )
    retained_record = {
        "uid": "retained-source-context-uid",
        "name": "retired/source",
        "memories": {
            "deadbeef-2222-2222-2222-222222222222": {
                "type": "memory",
                "uid": "deadbeef-2222-2222-2222-222222222222",
                "content": "Retained colliding Memory.",
            }
        },
        "order": ["deadbeef-2222-2222-2222-222222222222"],
    }
    package = {
        "schema_version": 1,
        "root": {
            "uid": retained_record["uid"],
            "name": retained_record["name"],
        },
        "recursive": False,
        "lexical_context_names": [retained_record["name"]],
        "contexts": [retained_record],
    }
    archive = Context(uid="archive-context-uid", name="archive")
    archive.add(
        ContextSnapshotRef(
            uid="snapshot-reference-uid",
            target_context_uid=retained_record["uid"],
            target_context_name=retained_record["name"],
            snapshot_package=package,
            snapshot_content_sha256=context_snapshot_digest(package),
        )
    )
    store.save(visible)
    store.save(archive)
    store.set_current(visible.name)

    listed = invoke("list")

    assert listed.exit_code == 0, listed.stderr or listed.output
    assert "[memory deadbeef-1] Visible colliding Memory." in listed.stdout
    assert "Retained colliding Memory." not in listed.stdout


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
        "  1 memory\n"
        "  0 subcontexts\n"
        "\n"
        f"  [memory {memory.uid[:8]}] "
        "Keep this object's visible identifier.\n"
    )

    copied = invoke("list", "--copy", "--with-ids")

    assert copied.exit_code == 0
    assert copied.stdout == expected.stdout
    assert expected.stdout == (
        "Context: source\n"
        "  1 memory\n"
        "  0 subcontexts\n"
        "\n"
        f"  [memory {memory.uid[:8]}] "
        "Keep this object's visible identifier.\n"
    )
    assert fake_system_clipboard["text"] == inline
    assert "[memory " in fake_system_clipboard["text"]
    assert "text with IDs" in copied.stderr


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
        "  1 memory\n"
        "  0 subcontexts\n"
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


def test_recursive_copy_writes_the_visible_tree_as_plain_text(
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
        "  1 memory\n"
        "  1 subcontext\n"
        "\n"
        "  VIA EMBED · child/\n"
        "    Nested fact.\n"
        "\n"
        "  Parent fact.\n"
    )
    assert "Copied 2 memories and 1 subcontext" in copied.stderr


def test_copy_renders_a_namespace_child_as_plain_text(
    isolated_store,
    fake_system_clipboard,
):
    invoke("init", "parent/child")
    invoke("add", "Child-only fact.")
    invoke("init", "parent")
    invoke("add", "Parent fact.")

    copied = invoke("ls", "parent", "--copy")

    assert copied.exit_code == 0
    assert "Child-only fact." not in copied.stdout
    assert fake_system_clipboard["text"] == (
        "Context: parent\n"
        "  1 memory\n"
        "  1 subcontext\n"
        "\n"
        "  DESCENDANT · parent/child/\n"
        "\n"
        "  Parent fact.\n"
    )


def test_list_leads_context_identity_with_typed_reach_in_plain_and_color(
    isolated_store,
):
    invoke("init", "parent/descendant")
    invoke("init", "parent/embedded")
    invoke("init", "parent")
    invoke("embed", "parent/embedded", "--into", "parent")

    plain = invoke("list", "parent")

    assert plain.exit_code == 0, plain.output
    assert "  0 memories\n" in plain.stdout
    assert "  2 subcontexts\n" in plain.stdout
    assert "  DESCENDANT · [context " in plain.stdout
    assert "] parent/descendant\n" in plain.stdout
    assert "  VIA EMBED · [context " in plain.stdout
    assert "] parent/embedded\n" in plain.stdout

    colored = runner.invoke(app, ["list", "parent"], color=True)

    embed_rgb = ";".join(map(str, semantic_color_rgb(SemanticColorRole.EMBED)))
    assert colored.exit_code == 0, colored.output
    assert f"\x1b[38;2;{embed_rgb}mVIA EMBED\x1b[0m · [context " in (colored.stdout)
    assert f"\x1b[38;2;{embed_rgb}mcontext\x1b[0m" not in colored.stdout
    assert click.unstyle(colored.stdout) == plain.stdout


def test_copy_renders_query_pointer_without_hidden_source_content(
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


def test_list_places_memory_source_identity_before_content_for_embed_and_reference(
    isolated_store,
):
    invoke("init", "practice/3")
    invoke("add", "Write each proposition in the exact three-token pattern.")
    store = MemoryStore()
    source = store.load_current()
    source_uid = next(iter(source.memories))
    invoke("init", "practice/4")
    invoke(
        "embed",
        source_uid[:8],
        "--from",
        "practice/3",
        "--into",
        "practice/4",
    )
    invoke("reference", source_uid[:8], "--from", "practice/3")
    target = store.load_current()
    embedded, reference = tuple(target.iter_items())

    result = invoke("list")

    assert result.exit_code == 0, result.output
    assert (
        f"[embedded {embedded.uid[:8]}] [practice/3][memory {source_uid[:8]}] "
        "Write each proposition in the exact three-token pattern.  READ ONLY"
        in result.stdout
    )
    assert (
        f"[reference {reference.uid[:8]}] [practice/3][memory {source_uid[:8]}] "
        "Write each proposition in the exact three-token pattern.  READ ONLY"
        in result.stdout
    )
    assert "practice/3#" not in result.stdout

    colored = runner.invoke(app, ["list"], color=True)
    assert colored.exit_code == 0, colored.output
    assert "\x1b[38;2;238;212;159membedded\x1b[0m" in colored.stdout
    assert "\x1b[38;2;198;160;246mreference\x1b[0m" in colored.stdout
    assert click.unstyle(colored.stdout) == result.stdout


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


def test_list_rejects_with_ids_without_copy(isolated_store):
    result = invoke("ls", "--with-ids")

    assert result.exit_code == 1
    assert result.stdout == ""


def test_list_paste_option_is_removed(isolated_store):
    result = invoke("ls", "--paste")

    assert result.exit_code == 2
    assert "No such option: --paste" in result.stderr


def test_failed_copy_reports_error_without_creating_a_structured_stage(
    isolated_store,
    fake_system_clipboard,
    monkeypatch,
):
    invoke("init", "source")
    invoke("add", "Same visible text.")
    assert invoke("ls", "--copy").exit_code == 0
    stage_path = isolated_store / "clipboard.json"
    assert not stage_path.exists()

    def fail_write(_text: str) -> None:
        raise ClipboardError("simulated clipboard failure")

    monkeypatch.setattr(list_command, "write_system_clipboard", fail_write)
    result = invoke("ls", "--copy")

    assert result.exit_code == 1
    assert "simulated clipboard failure" in result.stderr
    assert not stage_path.exists()


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
