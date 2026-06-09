"""
CLI command tests — run each command through Typer's CliRunner so we exercise
the full user-facing path (argument parsing, error messages, exit codes).

All tests use the `isolated_store` fixture from conftest.py to avoid touching
the real ~/.mem directory.
"""
import pytest
from typer.testing import CliRunner

from memcommit.cli import app
import memcommit.ops as ops
from memcommit.store import MemoryStore

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def invoke(*args):
    """Invoke the CLI with the given arguments and return the result."""
    return runner.invoke(app, list(args))



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
    def test_lists_memories_in_current_context(self, isolated_store):
        invoke("init", "ctx")
        invoke("add", "fact one")
        invoke("add", "fact two")
        result = invoke("list")
        assert result.exit_code == 0
        assert "fact one" in result.output
        assert "fact two" in result.output

    def test_empty_context_shows_no_memories(self, isolated_store):
        invoke("init", "empty")
        result = invoke("list")
        assert result.exit_code == 0
        assert "no memories" in result.output

    def test_list_explicit_context_name(self, isolated_store):
        invoke("init", "alpha")
        invoke("add", "alpha fact")
        invoke("init", "beta")  # switches current to beta
        result = invoke("list", "alpha")
        assert result.exit_code == 0
        assert "alpha fact" in result.output

    def test_fails_for_nonexistent_context(self, isolated_store):
        result = invoke("list", "ghost")
        assert result.exit_code == 1
        assert "not found" in result.stderr

    def test_fails_with_no_current_context(self, isolated_store):
        result = invoke("list")
        assert result.exit_code == 1


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
        assert "sourced fact" in invoke("list").output

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

        store = MemoryStore()
        assert not store.context_exists("to-delete")

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
