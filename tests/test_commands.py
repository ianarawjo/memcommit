"""
CLI command tests — run each command through Typer's CliRunner so we exercise
the full user-facing path (argument parsing, error messages, exit codes).

All tests use the `isolated_store` fixture from conftest.py to avoid touching
the real ~/.mem directory.
"""
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.commands.help_inventory as help_inventory
from memcommit.cli import app
from memcommit.commands.help_inventory import CommandEntry, run_help_selector
from memcommit.store import MemoryStore

runner = CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def invoke(*args):
    """Invoke the CLI with the given arguments and return the result."""
    return runner.invoke(app, list(args))


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

class TestHelp:
    @staticmethod
    def selector_entries():
        return [
            CommandEntry(
                name=name,
                annotation=None,
                description=f"{name} description",
                command=object(),
            )
            for name in ("alpha", "beta", "gamma")
        ]

    def test_lists_commands_with_exception_annotations_and_descriptions(self):
        result = invoke("help")

        assert result.exit_code == 0
        assert "mem command inventory" in result.output
        assert "implemented" not in result.output
        lines = result.output.splitlines()
        assert any(
            line.startswith("impact ")
            and "no Context changes" in line
            for line in lines
        )
        assert any(
            line.startswith("update ")
            and "local target" in line
            and "no shared publication" in line
            for line in lines
        )
        list_row = next(line for line in lines if line.startswith("list "))
        ls_row = next(line for line in lines if line.startswith("ls "))
        assert list_row.split(" - ", 1)[1] == ls_row.split(" - ", 1)[1]
        assert "List child Contexts and direct items" in list_row
        assert any(
            line.startswith("checkout ")
            and "Alias for switch" in line
            and "alias for branch" in line
            for line in lines
        )
        assert any(
            line.startswith("integrate (legacy) ")
            for line in lines
        )
        assert any(line.startswith("config (legacy) ") for line in lines)
        assert any(line.startswith("switch (bare → TUI) ") for line in lines)
        assert any(line.startswith("share (bare → TUI) ") for line in lines)
        assert any(line.startswith("help (bare → TUI) ") for line in lines)
        assert any(
            line.startswith("atomize ")
            and "issue-scoped directional meld" in line
            for line in lines
        )

    def test_meld_help_distinguishes_atomic_and_context_entry_points(self):
        atomize = invoke("atomize", "--help")
        meld = invoke("meld", "--help")

        assert atomize.exit_code == 0
        atomize_help = " ".join(atomize.output.split())
        assert "--evaluate ISSUE" in atomize_help
        assert "issue-scoped directional" in atomize_help
        assert "informally, atomic" in atomize_help

        assert meld.exit_code == 0
        meld_help = " ".join(meld.output.split())
        assert "two equal-authority Contexts" in meld_help
        assert "current empty Context" in meld_help
        assert "--atomic" not in meld_help
        assert "--into" in meld_help
        assert "authoritative BASELINE" in meld_help

    def test_selector_moves_down_and_returns_selected_command(self):
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[B\r")
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )

        assert selected == "beta"

    def test_selector_clamps_at_first_command_and_can_cancel(self):
        with create_pipe_input() as pipe_input:
            pipe_input.send_text("\x1b[A\r")
            selected = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
        assert selected == "alpha"

        with create_pipe_input() as pipe_input:
            pipe_input.send_text("q")
            cancelled = run_help_selector(
                self.selector_entries(),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
        assert cancelled is None

    def test_enter_opens_command_help_without_running_command(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            help_inventory,
            "_interactive_terminal",
            lambda: True,
        )
        monkeypatch.setattr(
            help_inventory,
            "run_help_selector",
            lambda entries: "impact",
        )

        result = invoke("help")

        assert result.exit_code == 0
        assert "Command: mem impact" in result.output
        assert "Usage: mem impact" in result.output
        assert "no Context changes" in result.output



# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_context_and_switches(self, isolated_store):
        result = invoke("init", "myctx")
        assert result.exit_code == 0
        assert "Initialized context 'myctx'" in result.output

        store = MemoryStore()
        assert store.context_exists("myctx")
        assert store.current_context_name() == "myctx"

    def test_fails_if_context_already_exists(self, isolated_store):
        invoke("init", "dup")
        result = invoke("init", "dup")
        assert result.exit_code == 1
        assert "already exists" in result.stderr

    def test_creates_initial_checkpoint(self, isolated_store):
        invoke("init", "ckpt-test")
        store = MemoryStore()
        cps = store.list_checkpoints("ckpt-test")
        assert len(cps) == 1
        assert cps[0]["command"] == "init"


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

class TestAdd:
    def test_adds_memory_to_current_context(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("add", "Remember this fact")
        assert result.exit_code == 0
        assert "Remember this fact" in result.output

        store = MemoryStore()
        ctx = store.load_current()
        contents = [m.content for m in ctx.memories.values()]
        assert "Remember this fact" in contents

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("add", "orphan memory")
        assert result.exit_code == 1

    def test_creates_checkpoint_after_add(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "some info")
        store = MemoryStore()
        cps = store.list_checkpoints("ctx")
        commands = [c["command"] for c in cps]
        assert "add" in commands


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:
    def test_lists_memory_ids_with_atomic_contents(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "fact one")
        invoke("add", "fact two")

        store = MemoryStore()
        uids = list(store.load_current().memories)
        result = invoke("list")

        assert result.exit_code == 0
        assert all(uid[:8] in result.output for uid in uids)
        assert "fact one" in result.output
        assert "fact two" in result.output

    def test_empty_context_shows_no_items(self, isolated_store):
        invoke("init", "empty")
        result = invoke("list")
        assert result.exit_code == 0
        assert "no items" in result.output

    def test_list_explicit_context_name(self, isolated_store):
        invoke("init", "alpha")
        invoke("add", "alpha fact")
        alpha_uid = next(iter(MemoryStore().load_current().memories))
        invoke("init", "beta")  # switches current to beta
        result = invoke("list", "alpha")
        assert result.exit_code == 0
        assert alpha_uid[:8] in result.output
        assert "alpha fact" in result.output

    def test_ls_and_list_have_identical_output(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "listed through either command")
        result = invoke("list")
        alias_result = invoke("ls")
        assert alias_result.exit_code == 0
        assert alias_result.output == result.output

    def test_ls_lists_embedded_context_without_leaking_child_contents(self, isolated_store):
        invoke("init", "building-access")
        invoke("add", "The east entrance is closed until Friday.")
        invoke("init", "task-123")
        invoke("embed", "building-access", "--into", "task-123")

        result = invoke("ls")

        assert result.exit_code == 0
        assert "building-access" in result.output
        assert "The east entrance is closed until Friday." not in result.output

    def test_lists_aaa_slash_ab_context_before_aaa_memory_and_preserves_groups(
        self,
        isolated_store,
    ):
        invoke("init", "source")
        invoke("add", "Referenced atomic name.")
        source_memory_uid = next(
            iter(MemoryStore().load_current().memories)
        )
        invoke("init", "aaa/ab")
        invoke("init", "parent")
        invoke("add", "aaa")
        invoke("embed", "aaa/ab", "--into", "parent")
        invoke("reference", source_memory_uid[:8], "--from", "source")
        invoke("add", "Last atomic name.")

        store = MemoryStore()
        stored_items = list(store.load("parent").iter_items())
        assert stored_items[0].content == "aaa"
        assert stored_items[1].name == "aaa/ab"
        assert stored_items[2].target_context_name == "source"
        assert stored_items[3].content == "Last atomic name."

        result = invoke("ls", "parent")

        assert result.exit_code == 0
        lines = result.output.splitlines()
        context_index = next(
            index
            for index, line in enumerate(lines)
            if "[context " in line and line.endswith("] aaa/ab")
        )
        first_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory  " in line and line.endswith("] aaa")
        )
        reference_index = next(
            index
            for index, line in enumerate(lines)
            if "[ref     " in line and "Referenced atomic name." in line
        )
        last_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory  " in line
            and line.endswith("] Last atomic name.")
        )
        assert context_index < first_memory_index < reference_index < last_memory_index

    def test_recursive_list_descends_contexts_before_listing_memories(
        self,
        isolated_store,
    ):
        invoke("init", "grandchild")
        invoke("add", "Grandchild memory.")
        invoke("init", "child")
        invoke("add", "Child memory.")
        invoke("embed", "grandchild", "--into", "child")
        invoke("init", "parent")
        invoke("add", "Parent memory.")
        invoke("embed", "child", "--into", "parent")

        result = invoke("ls", "-R", "parent")

        assert result.exit_code == 0
        lines = result.output.splitlines()
        child_index = next(
            index
            for index, line in enumerate(lines)
            if "[context " in line and line.endswith("] child")
        )
        grandchild_index = next(
            index
            for index, line in enumerate(lines)
            if "[context " in line and line.endswith("] grandchild")
        )
        grandchild_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory  " in line
            and line.endswith("] Grandchild memory.")
        )
        child_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory  " in line
            and line.endswith("] Child memory.")
        )
        parent_memory_index = next(
            index
            for index, line in enumerate(lines)
            if "[memory  " in line
            and line.endswith("] Parent memory.")
        )
        assert (
            child_index
            < grandchild_index
            < grandchild_memory_index
            < child_memory_index
            < parent_memory_index
        )

    def test_recursive_list_separates_sibling_context_blocks_only(
        self,
        isolated_store,
    ):
        invoke("init", "alpha")
        invoke("add", "Alpha memory.")
        invoke("init", "beta")
        invoke("add", "Beta memory.")
        invoke("init", "parent")
        invoke("add", "Parent memory.")
        invoke("embed", "alpha", "--into", "parent")
        invoke("embed", "beta", "--into", "parent")

        recursive = invoke("ls", "-R", "parent")
        direct = invoke("ls", "parent")

        assert recursive.exit_code == 0
        assert direct.exit_code == 0
        recursive_lines = recursive.output.splitlines()
        alpha_index = next(
            index
            for index, line in enumerate(recursive_lines)
            if "[context " in line and line.endswith("] alpha")
        )
        beta_index = next(
            index
            for index, line in enumerate(recursive_lines)
            if "[context " in line and line.endswith("] beta")
        )
        assert recursive_lines[alpha_index - 1] == ""
        assert recursive_lines[alpha_index - 2] != ""
        assert recursive_lines[beta_index - 1] == ""
        assert recursive_lines[beta_index + 1] != ""
        assert "" not in recursive_lines[beta_index + 1 :]
        direct_lines = direct.output.splitlines()
        direct_beta_index = next(
            index
            for index, line in enumerate(direct_lines)
            if "[context " in line and line.endswith("] beta")
        )
        assert direct_lines[direct_beta_index - 1].endswith("] alpha")

    def test_recursive_long_option_matches_short_option(self, isolated_store):
        invoke("init", "child")
        invoke("add", "Nested memory.")
        invoke("init", "parent")
        invoke("embed", "child", "--into", "parent")

        short_result = invoke("ls", "-R", "parent")
        long_result = invoke("ls", "--recursive", "parent")
        beginner_result = invoke("ls", "--expand", "parent")
        canonical_result = invoke("list", "-R", "parent")
        canonical_beginner_result = invoke("list", "--expand", "parent")
        help_result = invoke("ls", "--help")

        assert short_result.exit_code == 0
        assert long_result.exit_code == 0
        assert beginner_result.exit_code == 0
        assert canonical_result.exit_code == 0
        assert canonical_beginner_result.exit_code == 0
        assert help_result.exit_code == 0
        assert "--expand" in help_result.output
        assert (
            short_result.output
            == long_result.output
            == beginner_result.output
            == canonical_result.output
            == canonical_beginner_result.output
        )

    def test_recursive_list_terminates_for_persisted_indirect_cycle(
        self,
        isolated_store,
    ):
        invoke("init", "cycle/a")
        invoke("init", "cycle/b")
        invoke("embed", "cycle/b", "--into", "cycle/a")
        invoke("embed", "cycle/a", "--into", "cycle/b")

        result = invoke("ls", "-R", "cycle/a")

        assert result.exit_code == 0
        assert len(result.output) < 1_000
        assert result.output.count("cycle/a") == 1
        assert result.output.count("cycle/b") == 1

    def test_recursive_list_visits_shared_context_along_each_embed_path(
        self,
        isolated_store,
    ):
        invoke("init", "graph/shared")
        invoke("add", "Shared atomic memory.")
        invoke("init", "graph/left")
        invoke("embed", "graph/shared", "--into", "graph/left")
        invoke("init", "graph/right")
        invoke("embed", "graph/shared", "--into", "graph/right")
        invoke("init", "graph/root")
        invoke("embed", "graph/left", "--into", "graph/root")
        invoke("embed", "graph/right", "--into", "graph/root")

        result = invoke("ls", "-R", "graph/root")

        assert result.exit_code == 0
        assert result.output.count("graph/shared") == 2
        assert result.output.count("Shared atomic memory.") == 2

    def test_fails_for_nonexistent_context(self, isolated_store):
        result = invoke("list", "ghost")
        assert result.exit_code == 1
        assert "not found" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("list")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

class TestShow:
    def test_without_selector_shows_all_memory_contents(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "fact one")
        invoke("add", "fact two")

        result = invoke("show")

        assert result.exit_code == 0
        assert "fact one" in result.output
        assert "fact two" in result.output

    def test_shows_one_memory_by_uid_prefix(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "First line.\nSecond line.")
        invoke("add", "another memory")
        uid = next(iter(MemoryStore().load_current().memories))

        result = invoke("show", uid[:8])

        assert result.exit_code == 0
        assert uid in result.output
        assert "First line.\nSecond line." in result.output
        assert "another memory" not in result.output

    def test_shows_contents_of_explicit_context(self, isolated_store):
        invoke("init", "alpha")
        invoke("add", "alpha fact")
        invoke("init", "beta")
        invoke("add", "beta fact")

        result = invoke("show", "--context", "alpha")

        assert result.exit_code == 0
        assert "alpha fact" in result.output
        assert "beta fact" not in result.output

    def test_shows_embedded_context_by_exact_name(self, isolated_store):
        invoke("init", "child")
        invoke("add", "child-only fact")
        invoke("init", "parent")
        invoke("add", "parent-only fact")
        invoke("embed", "child", "--into", "parent")

        result = invoke("show", "child")

        assert result.exit_code == 0
        assert "Context: child" in result.output
        assert "child-only fact" in result.output
        assert "parent-only fact" not in result.output

    def test_fails_for_unknown_selector(self, isolated_store):
        invoke("init", "ctx")

        result = invoke("show", "missing")

        assert result.exit_code == 1
        assert "No direct item matching" in result.stderr

    def test_fails_for_ambiguous_uid_prefix(self, isolated_store):
        from memcommit.context import Memory as Mem

        invoke("init", "ctx")
        store = MemoryStore()
        ctx = store.load_current()
        ctx.add(Mem(uid="aaaa1111-1111-1111-1111-111111111111", content="first"))
        ctx.add(Mem(uid="aaaa2222-2222-2222-2222-222222222222", content="second"))
        store.save(ctx)

        result = invoke("show", "aaaa")

        assert result.exit_code == 1
        assert "Ambiguous selector" in result.stderr


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

class TestRemove:
    def test_removes_memory_by_uid_prefix(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "to be removed")

        store = MemoryStore()
        ctx = store.load_current()
        uid = next(iter(ctx.memories))

        result = invoke("remove", uid[:8])
        assert result.exit_code == 0
        assert "Removed" in result.output

        ctx2 = store.load_current()
        assert uid not in ctx2.memories

    def test_fails_on_nonexistent_uid(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("remove", "deadbeef")
        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_fails_on_ambiguous_prefix(self, isolated_store):
        from memcommit.context import Memory as Mem
        invoke("init", "ctx")
        # Insert two memories that share a prefix directly.
        store = MemoryStore()
        ctx = store.load_current()
        ctx.add(Mem(uid="aaaa1111-1111-1111-1111-111111111111", content="first"))
        ctx.add(Mem(uid="aaaa2222-2222-2222-2222-222222222222", content="second"))
        store.save(ctx)

        result = invoke("remove", "aaaa")
        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("remove", "anything")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# switch
# ---------------------------------------------------------------------------

class TestSwitch:
    def test_switches_to_existing_context(self, isolated_store):
        invoke("init", "alpha")
        invoke("init", "beta")
        result = invoke("switch", "alpha")
        assert result.exit_code == 0
        assert "Switched to context 'alpha'" in result.output

        store = MemoryStore()
        assert store.current_context_name() == "alpha"

    def test_fails_for_nonexistent_context(self, isolated_store):
        result = invoke("switch", "ghost")
        assert result.exit_code == 1
        assert "does not exist" in result.stderr

    def test_no_op_when_already_on_context(self, isolated_store):
        invoke("init", "same")
        result = invoke("switch", "same")
        assert result.exit_code == 0
        assert "Already on" in result.output


# ---------------------------------------------------------------------------
# branch
# ---------------------------------------------------------------------------

class TestBranch:
    def test_creates_branch_and_switches(self, isolated_store):
        invoke("init", "main")
        invoke("add", "shared memory")
        result = invoke("branch", "feature")
        assert result.exit_code == 0
        assert "Branched 'main' → 'feature'" in result.output

        store = MemoryStore()
        assert store.current_context_name() == "feature"
        assert store.context_exists("feature")

    def test_branch_inherits_memories(self, isolated_store):
        invoke("init", "main")
        invoke("add", "important fact")
        invoke("branch", "feature")

        store = MemoryStore()
        ctx = store.load("feature")
        contents = [m.content for m in ctx.memories.values()]
        assert "important fact" in contents

    def test_fails_if_branch_name_exists(self, isolated_store):
        invoke("init", "main")
        invoke("init", "existing")
        invoke("switch", "main")
        result = invoke("branch", "existing")
        assert result.exit_code == 1
        assert "already exists" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("branch", "orphan")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

class TestMerge:
    def test_merges_memories_from_other_context(self, isolated_store):
        invoke("init", "source")
        invoke("add", "sourced fact")
        invoke("init", "target")
        result = invoke("merge", "source")
        assert result.exit_code == 0
        assert "sourced fact" in invoke("show").output

    def test_merge_reports_added_count(self, isolated_store):
        invoke("init", "src")
        invoke("add", "fact A")
        invoke("add", "fact B")
        invoke("init", "tgt")
        result = invoke("merge", "src")
        assert result.exit_code == 0
        assert "2 memories" in result.output

    def test_merge_nothing_new_when_already_merged(self, isolated_store):
        invoke("init", "src")
        invoke("add", "fact")
        invoke("init", "tgt")
        invoke("merge", "src")
        result = invoke("merge", "src")
        assert result.exit_code == 0
        assert "nothing new" in result.output

    def test_fails_merging_nonexistent_context(self, isolated_store):
        invoke("init", "tgt")
        result = invoke("merge", "ghost")
        assert result.exit_code == 1
        assert "does not exist" in result.stderr

    def test_fails_merging_into_itself(self, isolated_store):
        invoke("init", "self")
        result = invoke("merge", "self")
        assert result.exit_code == 1

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("merge", "anything")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# contexts
# ---------------------------------------------------------------------------

class TestContexts:
    def test_lists_all_contexts(self, isolated_store):
        invoke("init", "alpha")
        invoke("init", "beta")
        result = invoke("contexts")
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output

    def test_marks_current_context(self, isolated_store):
        invoke("init", "alpha")
        invoke("init", "beta")
        invoke("switch", "alpha")
        result = invoke("contexts")
        assert result.exit_code == 0
        # Current context has the * prefix; others don't.
        assert "* alpha" in result.output
        assert "* beta" not in result.output


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_removes_all_memories(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "gone soon")
        result = invoke("clear", "--force")
        assert result.exit_code == 0

        store = MemoryStore()
        ctx = store.load_current()
        assert ctx.memories == {}

    def test_clear_fails_with_no_current_context(self, isolated_store):
        result = invoke("clear", "--force")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_removes_context(self, isolated_store):
        invoke("init", "to-delete")
        invoke("init", "keep")
        result = invoke("delete", "to-delete", "--force")
        assert result.exit_code == 0
        assert "ledger [" in result.output

        store = MemoryStore()
        assert not store.context_exists("to-delete")
        event = store.list_context_lifecycle_events(context_name="to-delete")[0]
        assert f"ledger [{event.event_uid[:8]}]" in result.output

    def test_post_commit_cleanup_failure_reports_deletion_as_committed(
        self,
        isolated_store,
        monkeypatch,
    ):
        invoke("init", "to-delete")

        def fail_state_write(self, state):
            raise OSError("injected state cleanup failure")

        monkeypatch.setattr(MemoryStore, "_write_state", fail_state_write)

        result = invoke("delete", "to-delete", "--force")

        assert result.exit_code == 1
        assert "Deleted context 'to-delete'" in result.stderr
        assert "post-delete cleanup was incomplete" in result.stderr
        store = MemoryStore()
        assert not store.context_exists("to-delete")
        assert len(
            store.list_context_lifecycle_events(context_name="to-delete")
        ) == 1

    def test_delete_fails_for_nonexistent_context(self, isolated_store):
        result = invoke("delete", "ghost", "--force")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_shows_context_name_and_memory_count(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "fact one")
        invoke("add", "fact two")
        result = invoke("status")
        assert result.exit_code == 0
        assert "On context: ctx" in result.output
        assert "2 memories" in result.output

    def test_shows_checkpoint_count(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "a memory")
        result = invoke("status")
        # init + add = 2 auto-checkpoints
        assert "2 checkpoints" in result.output

    def test_shows_no_memories_message_when_empty(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("status")
        assert "no memories yet" in result.output

    def test_no_current_context_exits_cleanly(self, isolated_store):
        result = invoke("status")
        assert result.exit_code == 0  # status uses secho+return, not Exit(1)


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

class TestLog:
    def test_shows_checkpoint_entries(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "a memory")
        result = invoke("log")
        assert result.exit_code == 0
        assert "Log for 'ctx'" in result.output
        assert "init" in result.output
        assert "add" in result.output

    def test_no_checkpoints_message_on_fresh_context(self, isolated_store):
        # Bypass the CLI to create a context with no checkpoints.
        from memcommit.store import MemoryStore
        import memcommit.ops as ops
        store = MemoryStore()
        ctx = ops.init("bare")
        store.save(ctx)          # save without AutoCheckpoint
        store.set_current("bare")

        result = invoke("log")
        assert result.exit_code == 0
        assert "No checkpoints" in result.output

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("log")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# checkpoint
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def test_saves_manual_checkpoint_with_message(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("checkpoint", "stable baseline")
        assert result.exit_code == 0
        assert "stable baseline" in result.output

        store = MemoryStore()
        cps = store.list_checkpoints("ctx")
        messages = [c.get("message", "") for c in cps]
        assert "stable baseline" in messages

    def test_saves_manual_checkpoint_without_message(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("checkpoint")
        assert result.exit_code == 0
        assert "(no message)" in result.output

    def test_manual_checkpoint_is_not_auto(self, isolated_store):
        invoke("init", "ctx")
        invoke("checkpoint", "manual one")
        store = MemoryStore()
        cps = store.list_checkpoints("ctx")
        manual = [c for c in cps if c.get("message") == "manual one"]
        assert len(manual) == 1
        assert manual[0].get("auto") is False

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("checkpoint", "orphan")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# revert
# ---------------------------------------------------------------------------

class TestRevert:
    def test_reverts_to_earlier_checkpoint(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "keep this")

        # Capture the uid of the current head checkpoint.
        store = MemoryStore()
        head_uid = store.list_checkpoints("ctx")[0]["uid"]

        invoke("add", "remove this")
        assert len(store.load_current().memories) == 2

        result = invoke("revert", head_uid[:8])
        assert result.exit_code == 0
        assert "Reverted" in result.output

        ctx = store.load_current()
        assert len(ctx.memories) == 1
        assert next(iter(ctx.memories.values())).content == "keep this"

    def test_output_includes_undo_hint(self, isolated_store):
        invoke("init", "ctx")
        store = MemoryStore()
        init_uid = store.list_checkpoints("ctx")[0]["uid"]

        result = invoke("revert", init_uid[:8])
        assert "mem revert" in result.output

    def test_fails_on_unknown_uid(self, isolated_store):
        invoke("init", "ctx")
        result = invoke("revert", "deadbeef")
        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("revert", "anything")
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# embed (error paths — happy path covered in integration tests)
# ---------------------------------------------------------------------------

class TestEmbed:
    def test_fails_when_child_does_not_exist(self, isolated_store):
        invoke("init", "parent")
        result = invoke("embed", "ghost", "--into", "parent")
        assert result.exit_code == 1
        assert "does not exist" in result.stderr

    def test_fails_when_parent_does_not_exist(self, isolated_store):
        invoke("init", "child")
        result = invoke("embed", "child", "--into", "ghost")
        assert result.exit_code == 1
        assert "does not exist" in result.stderr

    def test_fails_when_already_embedded(self, isolated_store):
        invoke("init", "child")
        invoke("init", "parent")
        invoke("embed", "child", "--into", "parent")
        result = invoke("embed", "child", "--into", "parent")
        assert result.exit_code == 1
        assert "already embedded" in result.stderr


# ---------------------------------------------------------------------------
# checkout (alias)
# ---------------------------------------------------------------------------

class TestCheckout:
    def test_checkout_switches_context(self, isolated_store):
        invoke("init", "alpha")
        invoke("init", "beta")
        result = invoke("checkout", "alpha")
        assert result.exit_code == 0
        assert MemoryStore().current_context_name() == "alpha"

    def test_checkout_b_creates_branch(self, isolated_store):
        invoke("init", "main")
        result = invoke("checkout", "-b", "feature")
        assert result.exit_code == 0
        assert MemoryStore().context_exists("feature")
        assert MemoryStore().current_context_name() == "feature"
