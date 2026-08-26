"""Deterministic direct-Memory editing contracts."""

import shlex

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory
from memcommit.context_targeting.tui.picker import ContextMemoryRow
from memcommit.edit_application import EditRequest, FrozenEditPlan
from memcommit.interfaces.tui.components.exact_command_review import (
    format_exact_command,
)
from memcommit.interfaces.tui.operations.edit import (
    EditTuiSetup,
    parse_edit_command_argv,
    run_edit_tui,
)
from memcommit.interfaces.tui.operations.edit.screen import (
    edit_exact_command_review,
)
from memcommit.store import MemoryStore


runner = CliRunner()
TUI_MEMORY_UID = "abcd1234-0000-0000-0000-000000000000"
TUI_OTHER_MEMORY_UID = "ef567890-0000-0000-0000-000000000000"


def invoke(*args: str):
    return runner.invoke(app, list(args))


def current_memory() -> Memory:
    item = next(iter(MemoryStore().load_current().iter_items()))
    assert isinstance(item, Memory)
    return item


def _tui_memory_rows(name: str):
    if name == "source":
        return (
            ContextMemoryRow(
                "abcd1234",
                "old content",
                selector=TUI_MEMORY_UID,
            ),
        )
    if name == "other":
        return (
            ContextMemoryRow(
                "ef567890",
                "other old content",
                selector=TUI_OTHER_MEMORY_UID,
            ),
        )
    return ()


def test_ops_edit_preserves_uid_and_explicit_order():
    ctx = ops.init("ordered")
    first = ops.add(ctx, "first")
    target = ops.add(ctx, "before")
    last = ops.add(ctx, "last")
    order_before = ctx.ordered_uids()

    original = ops.edit(ctx, target.uid[:8], "after")

    assert original.uid == target.uid
    assert original.content == "before"
    assert ctx.ordered_uids() == order_before == [first.uid, target.uid, last.uid]
    edited = ctx.memories[target.uid]
    assert isinstance(edited, Memory)
    assert edited.uid == target.uid
    assert edited.content == "after"


def test_ops_edit_rejects_non_memory_direct_item():
    parent = ops.init("parent")
    child = ops.init("child")
    ops.embed(child, parent)

    with pytest.raises(TypeError, match="not a Memory directly owned"):
        ops.edit(parent, child.uid[:8], "replacement")


def test_ops_edit_uid_prefix_ignores_colliding_context_name():
    parent = ops.init("parent")
    memory = Memory(
        uid="aaaa1111-0000-0000-0000-000000000000",
        content="before",
    )
    child = ops.init("aaaa")
    parent.add(memory)
    ops.embed(child, parent)

    ops.edit(parent, "aaaa", "after")

    assert parent.memories[memory.uid].content == "after"
    assert parent.memories[child.uid] is child


def test_cli_edit_replaces_content_and_renders_before_after(isolated_store):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "old content").exit_code == 0
    memory = current_memory()

    result = invoke("edit", memory.uid[:8], "new content")

    assert result.exit_code == 0
    assert f"Edited [{memory.uid[:8]}]" in result.output
    assert "- old content" in result.output
    assert "+ new content" in result.output
    stored = MemoryStore().load_current().memories[memory.uid]
    assert isinstance(stored, Memory)
    assert stored.content == "new content"


def test_bare_selector_finds_one_direct_memory_in_another_local_context(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("practice/3")
    memory = ops.add(source, "source content")
    current = ops.init("practice/4")
    store.save(source)
    store.save(current)
    store.set_current(current.name)

    result = invoke("edit", memory.uid[:8], "edited through profile search")

    assert result.exit_code == 0, result.output
    assert f"Edited [{memory.uid[:8]}] in 'practice/3'" in result.output
    assert store.current_context_name() == "practice/4"
    assert store.load_direct("practice/3").memories[memory.uid].content == (
        "edited through profile search"
    )


def test_context_qualified_selector_resolves_canonical_and_relative_owner(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("practice/3")
    first = ops.add(source, "first")
    second = ops.add(source, "second")
    current = ops.init("practice/4")
    store.save(source)
    store.save(current)
    store.set_current(current.name)

    canonical = invoke("edit", f"practice/3:{first.uid[:8]}", "canonical")
    relative = invoke("edit", f"../3:{second.uid[:8]}", "relative")

    assert canonical.exit_code == 0, canonical.output
    assert relative.exit_code == 0, relative.output
    reloaded = store.load_direct("practice/3")
    assert reloaded.memories[first.uid].content == "canonical"
    assert reloaded.memories[second.uid].content == "relative"
    assert store.current_context_name() == "practice/4"


def test_profile_search_requires_context_qualified_locator_when_uid_is_duplicated(
    isolated_store,
):
    store = MemoryStore()
    shared_uid = "aaaaaaaa-0000-0000-0000-000000000000"
    for name in ("branch/a", "branch/b"):
        context = ops.init(name)
        context.add(Memory(uid=shared_uid, content=name))
        store.save(context)
    store.set_current("branch/a")

    result = invoke("edit", shared_uid[:8], "replacement")

    assert result.exit_code == 1
    assert "multiple local matches" in result.output
    assert f'  branch/a:{shared_uid} "branch/a"' in result.output
    assert f'  branch/b:{shared_uid} "branch/b"' in result.output
    assert (
        "To select one, rerun with its CONTEXT:UID value shown above."
        in result.output
    )
    assert store.load_direct("branch/a").memories[shared_uid].content == "branch/a"
    assert store.load_direct("branch/b").memories[shared_uid].content == "branch/b"


def test_eight_character_collision_requires_a_longer_unique_prefix(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    first = Memory(
        uid="deadbeef-1111-1111-1111-111111111111",
        content='first "quoted" line\nsecond line',
    )
    second = Memory(
        uid="deadbeef-2222-2222-2222-222222222222",
        content="두 번째 메모리",
    )
    context.add(first)
    context.add(second)
    store.save(context)

    ambiguous = invoke("edit", "deadbeef", "replacement")

    assert ambiguous.exit_code == 1
    assert (
        f'  notes:{first.uid} "first \\"quoted\\" line\\nsecond line"'
        in ambiguous.output
    )
    assert f'  notes:{second.uid} "두 번째 메모리"' in ambiguous.output
    assert store.load_direct("notes").memories[first.uid].content == first.content
    assert store.load_direct("notes").memories[second.uid].content == second.content

    resolved = invoke("edit", "deadbeef-1", "replacement")

    assert resolved.exit_code == 0, resolved.output
    assert store.load_direct("notes").memories[first.uid].content == "replacement"
    assert store.load_direct("notes").memories[second.uid].content == second.content


def test_qualified_selector_cannot_be_combined_with_context_option(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    memory = ops.add(context, "before")
    store.save(context)
    store.set_current(context.name)

    result = invoke(
        "edit",
        f"notes:{memory.uid[:8]}",
        "after",
        "--context",
        "notes",
    )

    assert result.exit_code == 1
    assert "either CONTEXT:UID or an explicit Context option" in result.output
    assert store.load_direct("notes").memories[memory.uid].content == "before"


def test_bare_cli_edit_enters_and_can_cancel_interactive_setup(
    isolated_store,
    monkeypatch,
):
    import memcommit.commands.edit.command as edit_command

    monkeypatch.setattr(edit_command, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        edit_command, "choose_edit_setup", lambda *_args, **_kwargs: None
    )

    result = invoke("edit")

    assert result.exit_code == 0
    assert "Edit cancelled" in result.output


def test_edit_tui_prefills_selected_memory_and_freezes_replacement() -> None:
    requests: list[EditRequest] = []

    def prepare(request: EditRequest) -> FrozenEditPlan:
        requests.append(request)
        return FrozenEditPlan(
            request=request,
            context_name="source",
            context_uid="context-uid",
            context_digest="context-digest",
            memory_uid=TUI_MEMORY_UID,
            original_content="old content",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r\t\x15new content\t\r")
        result = run_edit_tui(
            EditTuiSetup(
                names=("source",),
                selectable_names=frozenset({"source"}),
                selected_context="source",
                current_context="source",
            ),
            memory_loader=_tui_memory_rows,
            content_loader=lambda _target: "old content",
            prepare=prepare,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [EditRequest(TUI_MEMORY_UID, "new content", "source")]


def test_edit_review_projects_only_the_exact_proposed_command() -> None:
    request = EditRequest(
        TUI_MEMORY_UID,
        "new content\nwith a second line",
        "source",
    )

    rendered = format_exact_command(edit_exact_command_review(request))

    assert rendered == (
        "mem edit abcd1234-0000-0000-0000-000000000000 "
        "'new content\\nwith a second line' --context source"
    )
    assert "EFFECTS" not in rendered
    assert "Approval applies" not in rendered
    assert "TO DO" not in rendered


def test_edit_command_parser_round_trips_multiline_and_literal_escapes() -> None:
    request = EditRequest(
        TUI_MEMORY_UID,
        "--context\nactual tab\tand literal \\n plus bidi \u202e",
        "source",
    )
    line = format_exact_command(edit_exact_command_review(request))

    assert parse_edit_command_argv(tuple(shlex.split(line))) == request


def test_edit_proposed_command_updates_memory_and_content_before_freeze() -> None:
    requests: list[EditRequest] = []
    content = "from command\nsecond line"
    command = format_exact_command(
        edit_exact_command_review(
            EditRequest(TUI_OTHER_MEMORY_UID, content, "other")
        )
    )
    arguments = command.removeprefix("mem edit ")

    def prepare(request: EditRequest) -> FrozenEditPlan:
        requests.append(request)
        return FrozenEditPlan(
            request=request,
            context_name="other",
            context_uid="other-context-uid",
            context_digest="other-context-digest",
            memory_uid=TUI_OTHER_MEMORY_UID,
            original_content="other old content",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\x15" + arguments + "\r")
        result = run_edit_tui(
            EditTuiSetup(
                names=("source", "other"),
                selectable_names=frozenset({"source", "other"}),
                selected_context="source",
                current_context="source",
            ),
            memory_loader=_tui_memory_rows,
            content_loader=lambda _target: "unused",
            prepare=prepare,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [EditRequest(TUI_OTHER_MEMORY_UID, content, "other")]


def test_cli_edit_creates_one_post_edit_checkpoint(isolated_store):
    invoke("init", "notes")
    invoke("add", "old content")
    store = MemoryStore()
    memory = current_memory()
    checkpoint_count = len(store.list_checkpoints("notes"))

    result = invoke("edit", memory.uid, "new content")

    assert result.exit_code == 0
    checkpoints = store.list_checkpoints("notes")
    assert len(checkpoints) == checkpoint_count + 1
    checkpoint = checkpoints[0]
    assert checkpoint["command"] == "edit"
    assert checkpoint["args"] == {
        "uid": memory.uid,
        "content": "new content",
    }
    assert checkpoint["snapshot"]["memories"][memory.uid]["content"] == "new content"


def test_exact_edit_rejects_drift_after_interactive_freeze(isolated_store):
    from memcommit.edit_application import EditRequest, run_edit
    from memcommit.edit_runtime import MemoryStoreEditPort

    invoke("init", "notes")
    invoke("add", "old content")
    store = MemoryStore()
    memory = current_memory()
    port = MemoryStoreEditPort.capture(store)
    request = EditRequest(memory.uid[:8], "reviewed replacement")
    plan = port.freeze(request)

    changed = store.load_direct("notes")
    ops.edit(changed, memory.uid, "concurrent replacement")
    store.save(changed)

    with pytest.raises(RuntimeError, match="changed while Edit was open"):
        run_edit(request, port=port, frozen_plan=plan)
    assert store.load_direct("notes").memories[memory.uid].content == (
        "concurrent replacement"
    )


def test_revert_to_add_checkpoint_restores_pre_edit_content(isolated_store):
    invoke("init", "notes")
    invoke("add", "old content")
    store = MemoryStore()
    memory = current_memory()
    add_checkpoint = next(
        checkpoint
        for checkpoint in store.list_checkpoints("notes")
        if checkpoint["command"] == "add"
    )
    invoke("edit", memory.uid[:8], "new content")

    result = invoke("revert", add_checkpoint["uid"][:8])

    assert result.exit_code == 0
    restored = store.load("notes").memories[memory.uid]
    assert isinstance(restored, Memory)
    assert restored.content == "old content"


def test_same_content_is_noop_without_checkpoint(isolated_store):
    invoke("init", "notes")
    invoke("add", "unchanged content")
    store = MemoryStore()
    memory = current_memory()
    checkpoint_count = len(store.list_checkpoints("notes"))

    result = invoke("edit", memory.uid[:8], "unchanged content")

    assert result.exit_code == 0
    assert "unchanged" in result.output
    assert len(store.list_checkpoints("notes")) == checkpoint_count


def test_whitespace_replacement_is_preserved_and_checkpointed(isolated_store):
    invoke("init", "notes")
    invoke("add", "keep this")
    store = MemoryStore()
    memory = current_memory()
    checkpoint_count = len(store.list_checkpoints("notes"))

    result = invoke("edit", memory.uid[:8], "   ")

    assert result.exit_code == 0
    assert len(store.list_checkpoints("notes")) == checkpoint_count + 1
    stored = store.load("notes").memories[memory.uid]
    assert isinstance(stored, Memory)
    assert stored.content == "   "


def test_memory_reference_cannot_be_edited(isolated_store):
    invoke("init", "source")
    invoke("add", "source content")
    store = MemoryStore()
    source_memory = current_memory()

    invoke("init", "parent")
    invoke("reference", source_memory.uid[:8], "--from", "source")
    parent = store.load("parent")
    reference = next(iter(parent.iter_items()))
    checkpoint_count = len(store.list_checkpoints("parent"))

    result = invoke("edit", reference.uid[:8], "mutated through reference")

    assert result.exit_code == 1
    assert "No directly owned Memory" in result.output
    assert len(store.list_checkpoints("parent")) == checkpoint_count
    source = store.load("source").memories[source_memory.uid]
    assert isinstance(source, Memory)
    assert source.content == "source content"


def test_ambiguous_prefix_and_missing_memory_do_not_mutate(isolated_store):
    store = MemoryStore()
    ctx = Context(uid="context-uid", name="notes")
    first = Memory(
        uid="aaaa1111-0000-0000-0000-000000000000",
        content="first",
    )
    second = Memory(
        uid="aaaa2222-0000-0000-0000-000000000000",
        content="second",
    )
    ctx.add(first)
    ctx.add(second)
    store.save(ctx)
    store.set_current("notes")

    ambiguous = invoke("edit", "aaaa", "replacement")
    missing = invoke("edit", "bbbb", "replacement")

    assert ambiguous.exit_code == 1
    assert "multiple local matches" in ambiguous.output
    assert missing.exit_code == 1
    assert "No directly owned Memory with uid starting" in missing.output
    reloaded = store.load("notes")
    assert reloaded.memories[first.uid].content == "first"
    assert reloaded.memories[second.uid].content == "second"
    assert store.list_checkpoints("notes") == []


def test_edit_without_current_context_searches_local_owners(isolated_store):
    store = MemoryStore()
    context = ops.init("notes")
    memory = ops.add(context, "before")
    store.save(context)

    result = invoke("edit", memory.uid[:8], "after")

    assert result.exit_code == 0, result.output
    assert store.current_context_name() is None
    assert store.load_direct("notes").memories[memory.uid].content == "after"


def test_edit_fails_without_current_or_matching_local_context(isolated_store):
    result = invoke("edit", "abcd1234", "replacement")

    assert result.exit_code == 1
    assert "No directly owned Memory" in result.output
