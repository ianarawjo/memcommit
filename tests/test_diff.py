"""Deterministic CLI rendering of staged and locally applied updates."""
from __future__ import annotations

import json
import uuid

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import AutoCheckpoint, Context
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.update.model import plan_update


runner = CliRunner(mix_stderr=False)


class Provider:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        response = self.response(payload)
        if set(response) == {"edits", "additions"}:
            response = {**response, "removals": []}
        return json.dumps(response)


def _stage(store: MemoryStore, *, changes: bool = True):
    source = ops.init("participant/construction-updates")
    source_memory = ops.add(
        source,
        "Lot C now provides temporary visitor parking.",
    )
    target = ops.init("campus-wiki")
    target_memory = ops.add(
        target,
        "Visitor parking is available in Lot A.\nHours remain unchanged.",
    )
    store.save(source)
    store.save(target)
    store.set_current(source.name)

    def response(payload):
        if not changes:
            return {"edits": [], "additions": []}
        source_id = payload["source"]["memories"][0]["source_id"]
        target_id = payload["target"]["memories"][0]["target_id"]
        context_id = payload["target"]["contexts"][0]["context_id"]
        return {
            "edits": [
                {
                    "target_id": target_id,
                    "new_content": (
                        "Visitor parking is available in Lot C.\n"
                        "Hours remain unchanged."
                    ),
                    "source_ids": [source_id],
                    "reason": "The verified update changes the visitor lot.",
                }
            ],
            "additions": [
                {
                    "target_context_id": context_id,
                    "new_content": "Follow temporary parking signs.",
                    "source_ids": [source_id],
                    "reason": "The instruction is missing from the Wiki.",
                }
            ],
        }

    provider = Provider(response)
    session = plan_update(
        source,
        target,
        lambda: provider,
        status="staged",
    )
    store.save_staged_update(session)
    return session, source_memory, target_memory, provider


def test_diff_requires_a_local_update(isolated_store):
    assert not isolated_store.exists()

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert "no local update" in result.stderr
    assert "mem update --to <context>" in result.stderr
    assert not isolated_store.exists()


def test_diff_without_a_target_or_saved_update_has_no_browser_fallback(
    isolated_store,
):
    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert "no local update" in result.stderr


def test_diff_renders_readable_semantic_edit_addition_and_provenance(
    isolated_store,
):
    store = MemoryStore()
    session, source_memory, target_memory, provider = _stage(store)
    addition = session.operations[1]

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 0, result.output
    assert "Staged update:" in result.output
    assert (
        "SOURCE participant/construction-updates → TARGET "
        "campus-wiki"
        in result.output
    )
    assert "STAGED · 1 EDITS · 1 ADDITIONS · 0 REMOVALS · 2 CHANGES" in result.output
    assert "PLANNED CHANGES" in result.output
    assert "EXACT PLANNED CHANGE DETAILS" in result.output
    assert (
        f"EDIT campus-wiki Memory [{target_memory.uid}]"
        in result.output
    )
    assert "BEFORE\n    Visitor parking is available in Lot A." in result.output
    assert "AFTER\n    Visitor parking is available in Lot C." in result.output
    assert "Hours remain unchanged." in result.output
    assert (
        f"ADD campus-wiki Memory [{addition.memory_uid}]"
        in result.output
    )
    assert "Follow temporary parking signs." in result.output
    assert (
        "Context participant/construction-updates "
        f"[{session.source_uid}]"
        in result.output
    )
    assert f"Memory [{source_memory.uid}]" in result.output
    assert "REASON\n    The verified update changes the visitor lot." in result.output
    assert "--- " not in result.output
    assert "@@ " not in result.output
    assert "\\ No newline at end of file" not in result.output
    assert provider.calls == 1


def test_diff_raw_preserves_exact_unified_diff(isolated_store):
    store = MemoryStore()
    session, source_memory, target_memory, _ = _stage(store)
    addition = session.operations[1]

    result = runner.invoke(app, ["diff", "--raw"])

    assert result.exit_code == 0
    assert (
        "diff --mem campus-wiki"
        f"#{target_memory.uid}"
        in result.output
    )
    assert (
        "--- a/campus-wiki"
        f"#{target_memory.uid}"
        in result.output
    )
    assert (
        "+++ b/campus-wiki"
        f"#{target_memory.uid}"
        in result.output
    )
    assert "@@ -1,2 +1,2 @@" in result.output
    assert "-Visitor parking is available in Lot A." in result.output
    assert "+Visitor parking is available in Lot C." in result.output
    assert " Hours remain unchanged." in result.output
    assert (
        "diff --mem campus-wiki"
        f"#{addition.memory_uid}"
        in result.output
    )
    assert "--- /dev/null" in result.output
    assert (
        "+++ b/campus-wiki"
        f"#{addition.memory_uid}"
        in result.output
    )
    assert "+Follow temporary parking signs." in result.output
    assert (
        "Sources: participant/construction-updates"
        f"#{source_memory.uid}"
        in result.output
    )


def test_diff_snapshot_uses_the_plain_common_update_structure(isolated_store):
    store = MemoryStore()
    _stage(store)

    result = runner.invoke(app, ["diff"], color=True)

    assert result.exit_code == 0
    assert "\x1b[" not in result.output
    assert "PLANNED CHANGES" in result.output
    assert "EXACT PLANNED CHANGE DETAILS" in result.output


def test_diff_is_read_only_and_does_not_depend_on_current_context(
    isolated_store,
):
    store = MemoryStore()
    _stage(store)
    unrelated = ops.init("unrelated-current")
    store.save(unrelated)
    store.set_current(unrelated.name)
    before = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(app, ["diff"])

    after = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    }
    assert result.exit_code == 0
    assert (
        "SOURCE participant/construction-updates → TARGET "
        "campus-wiki"
        in result.output
    )
    assert store.current_context_name() == "unrelated-current"
    assert after == before


def test_diff_returns_the_saved_update_without_a_tty_browser(
    isolated_store,
):
    store = MemoryStore()
    _stage(store)

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 0, result.output
    assert "STAGED" in result.output
    assert "PLANNED CHANGES" in result.output


def test_diff_context_operand_returns_latest_checkpoint_without_selection(
    isolated_store,
):
    store = MemoryStore()
    _stage(store)
    checkpoint = store.checkpoint(
        store.load("campus-wiki"),
        command="checkpoint",
    )

    result = runner.invoke(app, ["diff", "campus-wiki"])

    assert result.exit_code == 0, result.output
    assert "UNIT        CHECKPOINT · THIS CHECKPOINT VS PREVIOUS" in result.output
    assert f"CHECKPOINT  {checkpoint.uid}" in result.output
    assert "CONTEXT     campus-wiki" in result.output


def test_diff_context_operand_accepts_context_uid(isolated_store):
    store = MemoryStore()
    _stage(store)
    target = store.load_direct("campus-wiki")
    checkpoint = store.checkpoint(target, command="checkpoint")

    result = runner.invoke(app, ["diff", target.uid[:8], "--stat"])

    assert result.exit_code == 0, result.output
    assert f"CHECKPOINT  {checkpoint.uid}" in result.output
    assert "CONTEXT     campus-wiki" in result.output


def test_diff_context_operand_renders_latest_checkpoint_stat_noninteractively(
    isolated_store,
):
    store = MemoryStore()
    _stage(store)
    store.checkpoint(store.load("campus-wiki"), command="checkpoint")

    latest = store.list_checkpoints("campus-wiki")[0]
    result = runner.invoke(app, ["diff", "campus-wiki", "--stat"])

    assert result.exit_code == 0, result.output
    assert f"CHECKPOINT  {latest['uid']}" in result.output
    assert "CONTEXT     campus-wiki" in result.output
    assert "SUMMARY" in result.output


def test_diff_checkpoint_and_context_form_reopens_exact_revision(isolated_store):
    store = MemoryStore()
    _stage(store)
    store.checkpoint(store.load("campus-wiki"), command="checkpoint")
    checkpoint_uid = store.list_checkpoints("campus-wiki")[0]["uid"]

    result = runner.invoke(
        app,
        ["diff", checkpoint_uid[:8], "--context", "campus-wiki"],
    )

    assert result.exit_code == 0, result.output
    assert f"CHECKPOINT  {checkpoint_uid}" in result.output
    assert "CONTEXT     campus-wiki" in result.output
    assert "REVISION DIFF" in result.output


def test_diff_context_and_checkpoint_option_support_raw_output(isolated_store):
    store = MemoryStore()
    _stage(store)
    store.checkpoint(store.load("campus-wiki"), command="checkpoint")
    checkpoint_uid = store.list_checkpoints("campus-wiki")[0]["uid"]

    result = runner.invoke(
        app,
        [
            "diff",
            "campus-wiki",
            "--checkpoint",
            checkpoint_uid[:8],
            "--raw",
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"CHECKPOINT  {checkpoint_uid}" in result.output
    assert "diff --mem campus-wiki#" in result.output
    assert "--- " in result.output
    assert "+++ " in result.output


def test_diff_accepts_two_checkpoint_uids_and_compares_their_result_states(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("checkpoint-pair")
    memory = ops.add(context, "Before wording")
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="First state"),
    )
    from_uid = store.list_checkpoints(context.name)[0]["uid"]
    ops.edit(context, memory.uid, "After wording")
    store.save(
        context,
        AutoCheckpoint(command="edit", args={}, description="Second state"),
    )
    to_uid = store.list_checkpoints(context.name)[0]["uid"]

    result = runner.invoke(app, ["diff", from_uid[:8], to_uid[:8]])

    assert result.exit_code == 0, result.output
    assert "UNIT        CHECKPOINT · CHECKPOINT VS CHECKPOINT" in result.output
    assert f"FROM        {from_uid}" in result.output
    assert f"TO          {to_uid}" in result.output
    assert "CONTEXT     checkpoint-pair" in result.output
    assert "- [EDIT]" in result.output
    assert "Before wording" in result.output
    assert "+ [EDIT]" in result.output
    assert "After wording" in result.output


def test_diff_two_checkpoint_uids_require_one_owner_context(isolated_store):
    store = MemoryStore()
    checkpoint_uids = []
    for name in ("pair/one", "pair/two"):
        context = ops.init(name)
        ops.add(context, name)
        store.save(
            context,
            AutoCheckpoint(command="add", args={}, description=name),
        )
        checkpoint_uids.append(store.list_checkpoints(name)[0]["uid"])

    result = runner.invoke(
        app,
        ["diff", checkpoint_uids[0][:8], checkpoint_uids[1][:8]],
    )

    assert result.exit_code == 1
    assert "same Context" in result.stderr


def test_diff_bare_checkpoint_prefix_infers_its_unique_context(isolated_store):
    store = MemoryStore()
    _stage(store)
    checkpoint = store.checkpoint(
        store.load("campus-wiki"),
        command="checkpoint",
    )

    result = runner.invoke(app, ["diff", checkpoint.uid[:8], "--stat"])

    assert result.exit_code == 0, result.output
    assert f"CHECKPOINT  {checkpoint.uid}" in result.output
    assert "CONTEXT     campus-wiki" in result.output


def test_diff_checkpoint_option_infers_unique_owner_without_context(isolated_store):
    store = MemoryStore()
    _stage(store)
    checkpoint = store.checkpoint(
        store.load("campus-wiki"),
        command="checkpoint",
    )

    result = runner.invoke(
        app,
        ["diff", "--checkpoint", checkpoint.uid[:8], "--stat"],
    )

    assert result.exit_code == 0, result.output
    assert f"CHECKPOINT  {checkpoint.uid}" in result.output


def test_diff_bare_operand_rejects_context_checkpoint_collision(isolated_store):
    store = MemoryStore()
    _stage(store)
    checkpoint = store.checkpoint(
        store.load("campus-wiki"),
        command="checkpoint",
    )
    # Existing legacy names may predate the portable-name rule that reserves
    # the visible UUID-prefix shape for typed CLI operands.
    collision = Context(uid=str(uuid.uuid4()), name=checkpoint.uid[:8])
    collision_path = store._context_file(collision.name)
    collision_path.parent.mkdir(parents=True)
    collision_path.write_text(json.dumps(collision.to_dict()), encoding="utf-8")

    result = runner.invoke(app, ["diff", checkpoint.uid[:8]])

    assert result.exit_code == 1
    assert "matches both Context" in result.stderr
    assert "--context or --checkpoint" in result.stderr


def test_diff_renders_empty_fresh_stage(isolated_store):
    store = MemoryStore()
    _stage(store, changes=False)

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 0
    assert "0 EDITS · 0 ADDITIONS · 0 REMOVALS · 0 CHANGES" in result.output
    assert "(no changes needed)" in result.output
    assert "EXACT PLANNED CHANGE DETAILS" not in result.output


def test_diff_renders_applied_local_update_from_recorded_base_read_only(
    isolated_store,
):
    store = MemoryStore()
    staged, _, target_memory, provider = _stage(store)
    applied = store.apply_staged_update(staged)
    assert applied.application is not None
    assert provider.calls == 1
    assert (
        store.load("campus-wiki")
        .memories[target_memory.uid]
        .content
        == "Visitor parking is available in Lot C.\nHours remain unchanged."
    )
    before = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(app, ["diff", "--verbose"])

    after = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    }
    assert result.exit_code == 0, result.output
    assert "Applied local update" in result.output
    assert (
        "participant/construction-updates → "
        "campus-wiki"
        in result.output
    )
    assert f"Update  {applied.uid}" in result.output
    assert (
        f"Base    {applied.target_uid}  {applied.target_digest}"
        in result.output
    )
    assert (
        f"Result  {applied.target_uid}  "
        f"{applied.application.target_digest}"
        in result.output
    )
    assert "  - Visitor parking is available in Lot A." in result.output
    assert "  + Visitor parking is available in Lot C." in result.output
    assert "STALE" not in result.stderr
    assert after == before


def test_diff_shows_captured_content_but_fails_when_target_is_stale(
    isolated_store,
):
    store = MemoryStore()
    _stage(store)
    target = store.load("campus-wiki")
    ops.add(target, "A concurrent Wiki edit.")
    store.save(target)

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert "BEFORE\n    Visitor parking is available in Lot A." in result.output
    assert "AFTER\n    Visitor parking is available in Lot C." in result.output
    assert "STALE — source or target changed" in result.stderr
    assert (
        "Review the local fork and re-run impact/update before contributing."
        in result.stderr
    )


def test_diff_fails_stale_when_source_is_missing_but_still_renders(
    isolated_store,
):
    store = MemoryStore()
    _stage(store)
    store.delete("participant/construction-updates")

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert (
        "SOURCE participant/construction-updates → TARGET "
        "campus-wiki"
        in result.output
    )
    assert "STALE — source or target changed" in result.stderr


def test_diff_rejects_an_impact_plan_saved_in_the_update_slot(isolated_store):
    store = MemoryStore()
    session, _, _, _ = _stage(store)
    store.save_staged_update(session.with_status("impact"))

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert "not an update result" in result.stderr
    assert "Update preview" not in result.output


def test_diff_rejects_invalid_staged_session_json(isolated_store):
    MemoryStore()
    (isolated_store / "staged-update.json").write_text(
        '{"status": "staged", "status": "impact"}'
    )

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert "invalid JSON" in result.stderr


def test_diff_renders_a_terminal_newline_only_change(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "Canonical formatting requires a terminal newline.")
    target = ops.init("target")
    target_memory = ops.add(target, "same text")
    store.save(source)
    store.save(target)

    def response(payload):
        return {
            "edits": [
                {
                    "target_id": payload["target"]["memories"][0]["target_id"],
                    "new_content": "same text\n",
                    "source_ids": [
                        payload["source"]["memories"][0]["source_id"]
                    ],
                    "reason": "Canonicalize the terminal newline.",
                }
            ],
            "additions": [],
        }

    session = plan_update(
        source,
        target,
        lambda: Provider(response),
        status="staged",
    )
    store.save_staged_update(session)

    semantic = runner.invoke(app, ["diff"])
    raw = runner.invoke(app, ["diff", "--raw"])

    assert semantic.exit_code == 0
    assert "BEFORE\n    same text" in semantic.output
    assert "AFTER\n    same text" in semantic.output
    assert "\\ No newline at end of file" not in semantic.output
    assert raw.exit_code == 0
    assert f"--- a/target#{target_memory.uid}" in raw.output
    assert f"+++ b/target#{target_memory.uid}" in raw.output
    assert "-same text" in raw.output
    assert "+same text" in raw.output
    assert raw.output.count("\\ No newline at end of file") == 1


def test_diff_stat_and_verbose_modes(isolated_store):
    store = MemoryStore()
    session, source_memory, target_memory, _ = _stage(store)

    stat = runner.invoke(app, ["diff", "--stat"])
    verbose = runner.invoke(app, ["diff", "--verbose"])

    assert stat.exit_code == 0
    assert "2 changes · 1 edited · 1 added" in stat.output
    assert "EDIT  " not in stat.output
    assert "ADD   " not in stat.output

    assert verbose.exit_code == 0
    assert f"Update  {session.uid}" in verbose.output
    assert session.source_digest in verbose.output
    assert session.target_digest in verbose.output
    assert f"[{target_memory.uid}]" in verbose.output
    assert f"[{source_memory.uid}]" in verbose.output


def test_diff_rejects_raw_and_stat_together_without_touching_store(
    isolated_store,
):
    store = MemoryStore()
    _stage(store)
    before = (isolated_store / "staged-update.json").read_bytes()

    result = runner.invoke(app, ["diff", "--raw", "--stat"])

    assert result.exit_code == 2
    assert "cannot be used together" in result.stderr
    assert (isolated_store / "staged-update.json").read_bytes() == before
