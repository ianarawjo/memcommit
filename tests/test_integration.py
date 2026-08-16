"""
Integration tests — multi-command user sessions.

Each scenario class represents a realistic workflow a user might follow.
Commands are invoked through the Typer CliRunner just as a real user would
type them, and we assert on the observable outcomes: exit codes, output text,
and the resulting store state.

All scenarios use the `isolated_store` fixture from conftest.py so they never
touch the real ~/.mem directory.
"""
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.store import MemoryStore

runner = CliRunner(mix_stderr=False)


def mem(*args, input: str | None = None):
    """Thin wrapper so tests read like shell commands: mem("add", "hello")."""
    return runner.invoke(app, list(args), input=input)


# ---------------------------------------------------------------------------
# Scenario 1: Research notes — add, review, correct
# ---------------------------------------------------------------------------

class TestResearchNotesWorkflow:
    """
    User captures research notes, reviews them, spots a mistake, removes it,
    and adds a corrected fact.
    """

    def test_full_research_session(self, isolated_store):
        # Start a new context for a research topic.
        r = mem("init", "climate-notes")
        assert r.exit_code == 0

        # Add several facts.
        mem("add", "CO2 levels are rising due to fossil fuel combustion")
        mem("add", "Global average temperature has risen ~1.1°C since pre-industrial times")
        mem("add", "Arctic sea ice extent is declining at 13% per decade")
        mem("add", "The ozone layer is in the stratosphere")  # not a mistake, just unrelated

        # Show confirms all four memories are present.
        r = mem("show")
        assert r.exit_code == 0
        assert "CO2 levels" in r.output
        assert "Arctic sea ice" in r.output

        # User realises the sea-ice figure was for a specific period; remove it.
        store = MemoryStore()
        ctx = store.load_current()
        arctic_uid = next(
            uid for uid, m in ctx.memories.items()
            if "Arctic" in getattr(m, "content", "")
        )
        r = mem("remove", arctic_uid[:8])
        assert r.exit_code == 0
        assert "Removed" in r.output

        # Add a corrected, more precise fact.
        mem("add", "Arctic sea ice minimum extent declined ~13% per decade from 1979–2023 (NSIDC)")

        # Final state: 4 memories (one removed, one added back).
        ctx2 = store.load_current()
        assert len(ctx2.memories) == 4
        contents = [getattr(m, "content", "") for m in ctx2.memories.values()]
        assert any("1979–2023" in c for c in contents)
        assert not any("per decade" in c and "1979" not in c for c in contents)


# ---------------------------------------------------------------------------
# Scenario 2: Feature branch — branch, work, merge back
# ---------------------------------------------------------------------------

class TestBranchAndMergeWorkflow:
    """
    User maintains a main context of project facts, branches to experiment,
    then merges the experiment back into main.
    """

    def test_branch_isolates_work_then_merge_combines(self, isolated_store):
        # Set up main context with shared project facts.
        mem("init", "main")
        mem("add", "Project uses Python 3.12")
        mem("add", "Deployment target: AWS Lambda")

        # Branch to try out a new approach.
        r = mem("branch", "experiment")
        assert r.exit_code == 0
        assert MemoryStore().current_context_name() == "experiment"

        # Add experiment-specific notes on the branch.
        mem("add", "Testing Rust extension for hot path — 3× speedup observed")
        mem("add", "Rust build adds ~30s to CI pipeline")

        # The experiment branch has 4 memories (2 inherited + 2 new).
        store = MemoryStore()
        exp_ctx = store.load("experiment")
        assert len(exp_ctx.memories) == 4

        # Main still only has 2.
        main_ctx = store.load("main")
        assert len(main_ctx.memories) == 2

        # Decision: merge the findings back.
        mem("switch", "main")
        r = mem("merge", "experiment")
        assert r.exit_code == 0
        assert "2 memories" in r.output  # only the 2 new ones are added

        # Main now has all 4 memories.
        merged_ctx = store.load("main")
        assert len(merged_ctx.memories) == 4
        contents = [getattr(m, "content", "") for m in merged_ctx.memories.values()]
        assert any("Rust" in c for c in contents)

    def test_branch_status_shows_parent_checkpoint_count(self, isolated_store):
        mem("init", "main")
        mem("add", "memory one")
        mem("add", "memory two")

        parent_cp_count = len(MemoryStore().list_checkpoints("main"))

        mem("branch", "feature")

        r = mem("status")
        assert r.exit_code == 0
        assert f"Checkpoints {parent_cp_count}" in r.output

    def test_branch_log_shows_parent_history(self, isolated_store):
        mem("init", "main")
        mem("add", "initial memory")

        mem("branch", "feature")

        r = mem("log")
        assert r.exit_code == 0
        assert "No checkpoints" not in r.output
        # The inherited log must contain the add and init operations.
        assert "add" in r.output
        assert "init" in r.output

    def test_branch_changes_do_not_affect_origin(self, isolated_store):
        mem("init", "stable")
        mem("add", "Stable fact")

        mem("branch", "risky")
        mem("add", "Risky experiment note")

        # Switch back; stable should be unchanged.
        mem("switch", "stable")
        stable = MemoryStore().load("stable")
        contents = [getattr(m, "content", "") for m in stable.memories.values()]
        assert len(contents) == 1
        assert "Stable fact" in contents[0]


# ---------------------------------------------------------------------------
# Scenario 3: Multiple projects — context isolation
# ---------------------------------------------------------------------------

class TestMultiProjectIsolation:
    """
    User tracks two separate projects; memories must stay isolated.
    """

    def test_contexts_do_not_share_memories(self, isolated_store):
        mem("init", "project-alpha")
        mem("add", "Alpha uses React 18")
        mem("add", "Alpha backend: Django")

        mem("init", "project-beta")
        mem("add", "Beta uses Vue 3")
        mem("add", "Beta backend: FastAPI")

        # Showing Alpha contains only its own memories.
        r = mem("show", "--context", "project-alpha")
        assert "Alpha uses React" in r.output
        assert "Beta" not in r.output

        # Showing Beta contains only its own memories.
        r = mem("show", "--context", "project-beta")
        assert "Beta uses Vue" in r.output
        assert "Alpha" not in r.output

    def test_switching_changes_which_context_add_targets(self, isolated_store):
        mem("init", "ctx-a")
        mem("init", "ctx-b")

        mem("switch", "ctx-a")
        mem("add", "Memory for A")

        mem("switch", "ctx-b")
        mem("add", "Memory for B")

        store = MemoryStore()
        a_contents = [getattr(m, "content", "") for m in store.load("ctx-a").memories.values()]
        b_contents = [getattr(m, "content", "") for m in store.load("ctx-b").memories.values()]

        assert any("Memory for A" in c for c in a_contents)
        assert not any("Memory for B" in c for c in a_contents)
        assert any("Memory for B" in c for c in b_contents)
        assert not any("Memory for A" in c for c in b_contents)


# ---------------------------------------------------------------------------
# Scenario 4: Chunking a long note
# ---------------------------------------------------------------------------

class TestChunkWorkflow:
    """
    User adds a long multi-paragraph note, then splits it into atomic memories.
    """

    LONG_NOTE = (
        "The mitochondria is the powerhouse of the cell.\n\n"
        "It produces ATP via the citric acid cycle and oxidative phosphorylation.\n\n"
        "Mitochondria have their own DNA, inherited maternally in most animals."
    )

    def test_chunk_replaces_original_with_parts(self, isolated_store):
        mem("init", "bio-notes")
        mem("add", self.LONG_NOTE)

        store = MemoryStore()
        ctx = store.load_current()
        assert len(ctx.memories) == 1
        original_uid = next(iter(ctx.memories))

        # Chunk by paragraphs, confirm the split (input "y" to the prompt).
        r = mem("chunk", original_uid[:8], "--method", "paragraphs", input="y\n")
        assert r.exit_code == 0
        assert "3 memories added" in r.output

        ctx2 = store.load_current()
        # Original gone, replaced by 3 chunks.
        assert original_uid not in ctx2.memories
        assert len(ctx2.memories) == 3
        contents = [getattr(m, "content", "") for m in ctx2.memories.values()]
        assert any("powerhouse" in c for c in contents)
        assert any("ATP" in c for c in contents)
        assert any("maternal" in c for c in contents)

    def test_chunk_aborted_leaves_context_unchanged(self, isolated_store):
        mem("init", "notes")
        mem("add", "Para one.\n\nPara two.\n\nPara three.")

        store = MemoryStore()
        ctx = store.load_current()
        uid = next(iter(ctx.memories))

        r = mem("chunk", uid[:8], "--method", "paragraphs", input="n\n")
        assert r.exit_code == 0
        assert "Aborted" in r.output

        ctx2 = store.load_current()
        assert len(ctx2.memories) == 1
        assert uid in ctx2.memories


# ---------------------------------------------------------------------------
# Scenario 5: Checkpoint and revert
# ---------------------------------------------------------------------------

class TestCheckpointAndRevertWorkflow:
    """
    User makes a series of changes, realises the last one was a mistake,
    and reverts to an earlier checkpoint.
    """

    def test_revert_to_earlier_state(self, isolated_store):
        mem("init", "journal")
        mem("add", "Day 1: project kicked off")
        mem("add", "Day 2: first prototype done")

        # Capture the uid of the "after Day 2" checkpoint — the current head.
        store = MemoryStore()
        cps = store.list_checkpoints("journal")  # newest first
        day2_uid = cps[0]["uid"]

        # Add an erroneous entry.
        mem("add", "Day 2: project cancelled")  # mistake

        ctx_before = store.load_current()
        assert len(ctx_before.memories) == 3

        # Revert to right after Day 2 was added.
        r = mem("revert", day2_uid[:8])
        assert r.exit_code == 0
        assert "Reverted" in r.output

        ctx_after = store.load_current()
        assert len(ctx_after.memories) == 2
        contents = [getattr(m, "content", "") for m in ctx_after.memories.values()]
        assert not any("cancelled" in c for c in contents)
        assert any("Day 2: first prototype" in c for c in contents)

    def test_undo_a_revert(self, isolated_store):
        """Reverting a revert (undo) restores the reverted state."""
        mem("init", "scratchpad")
        mem("add", "Important note")

        # Get the uid of the "after add" checkpoint.
        store = MemoryStore()
        cps = store.list_checkpoints("scratchpad")
        # Revert past it — back to empty.
        init_cp = cps[-1]["uid"]
        mem("revert", init_cp[:8])

        ctx_empty = store.load_current()
        assert len(ctx_empty.memories) == 0

        # The revert itself was checkpointed; grab it and undo it.
        cps2 = store.list_checkpoints("scratchpad")
        pre_revert_uid = cps2[0]["uid"]
        mem("revert", pre_revert_uid[:8])

        ctx_restored = store.load_current()
        assert len(ctx_restored.memories) == 1
        content = next(iter(ctx_restored.memories.values())).content
        assert "Important note" in content


# ---------------------------------------------------------------------------
# Scenario 6: Embed a sub-context
# ---------------------------------------------------------------------------

class TestEmbedWorkflow:
    """
    User organises knowledge hierarchically by embedding one context inside
    another, then verifies the embedded context appears in the parent listing.
    """

    def test_embedded_context_appears_in_parent_list(self, isolated_store):
        # Build a sub-topic context.
        mem("init", "python-tips")
        mem("add", "Use list comprehensions over map/filter for readability")
        mem("add", "Prefer f-strings over .format() in Python 3.6+")

        # Build a parent context.
        mem("init", "dev-notes")
        mem("add", "Always write tests before shipping")

        # Embed the sub-topic into the parent.
        r = mem("embed", "python-tips", "--into", "dev-notes")
        assert r.exit_code == 0
        assert "Embedded 'python-tips' into 'dev-notes'" in r.output

        # The parent listing shows the embedded context.
        r = mem("list", "dev-notes")
        assert r.exit_code == 0
        assert "python-tips" in r.output

        # The embedded context is tracked as a nested context, not a flat memory.
        store = MemoryStore()
        from memcommit.context import Context
        parent = store.load("dev-notes")
        embedded = [v for v in parent.memories.values() if isinstance(v, Context)]
        assert len(embedded) == 1
        assert embedded[0].name == "python-tips"

    def test_embed_same_context_twice_fails(self, isolated_store):
        mem("init", "child")
        mem("init", "parent")
        mem("embed", "child", "--into", "parent")

        # Second embed of the same child should fail gracefully.
        r = mem("embed", "child", "--into", "parent")
        assert r.exit_code == 1
        assert "already embedded" in r.stderr


# ---------------------------------------------------------------------------
# Scenario 7: Clear and rebuild
# ---------------------------------------------------------------------------

class TestClearAndRebuildWorkflow:
    """
    User clears a context to start fresh without losing the context itself,
    then repopulates it.
    """

    def test_clear_then_repopulate(self, isolated_store):
        mem("init", "meeting-notes")
        mem("add", "Agenda: Q3 planning")
        mem("add", "Action: Ian to review PRs")
        mem("add", "Action: Team to prepare demos")

        store = MemoryStore()
        assert len(store.load_current().memories) == 3

        # Clear the context (force, no prompt).
        r = mem("clear", "--force")
        assert r.exit_code == 0
        assert len(store.load_current().memories) == 0

        # The context itself still exists and can be repopulated.
        mem("add", "New agenda: Q4 planning")
        mem("add", "Action: Launch retrospective")

        ctx = store.load_current()
        assert len(ctx.memories) == 2
        contents = [getattr(m, "content", "") for m in ctx.memories.values()]
        assert any("Q4" in c for c in contents)
        assert not any("Q3" in c for c in contents)


# ---------------------------------------------------------------------------
# Scenario 8: Delete and recreate a context
# ---------------------------------------------------------------------------

class TestDeleteAndRecreateWorkflow:
    """
    User deletes an old context, then recreates it with a clean slate.
    """

    def test_delete_and_reinit_same_name(self, isolated_store):
        mem("init", "scratch")
        mem("add", "Old data that should be gone")

        store = MemoryStore()
        old_uid = next(iter(store.load("scratch").memories))

        # Delete needs us to be on a different context first (or just force-delete).
        mem("init", "other")
        r = mem("delete", "scratch", "--force")
        assert r.exit_code == 0
        assert not store.context_exists("scratch")

        # Re-init with the same name gives a clean slate.
        mem("switch", "other")  # ensure we're not on scratch
        r = mem("init", "scratch")
        assert r.exit_code == 0

        new_ctx = store.load("scratch")
        assert len(new_ctx.memories) == 0
        assert old_uid not in new_ctx.memories

    def test_remaining_contexts_unaffected_after_delete(self, isolated_store):
        mem("init", "keep-a")
        mem("add", "Data in A")
        mem("init", "keep-b")
        mem("add", "Data in B")
        mem("init", "trash")
        mem("add", "Data to delete")

        mem("switch", "keep-a")
        mem("delete", "trash", "--force")

        store = MemoryStore()
        assert store.context_exists("keep-a")
        assert store.context_exists("keep-b")
        assert not store.context_exists("trash")

        a_contents = [getattr(m, "content", "") for m in store.load("keep-a").memories.values()]
        assert any("Data in A" in c for c in a_contents)
