"""Deterministic CLI rendering of staged and locally applied updates."""
from __future__ import annotations

import json

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.store import MemoryStore
from memcommit.update import plan_update


runner = CliRunner(mix_stderr=False)


class Provider:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        return json.dumps(self.response(payload))


def _stage(store: MemoryStore, *, changes: bool = True):
    source = ops.init("participant/construction-updates")
    source_memory = ops.add(
        source,
        "Lot C now provides temporary visitor parking.",
    )
    target = ops.init("participant/campus-wiki-fork")
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


def test_diff_renders_readable_semantic_edit_addition_and_provenance(
    isolated_store,
):
    store = MemoryStore()
    session, source_memory, target_memory, provider = _stage(store)
    addition = session.operations[1]

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 0, result.output
    assert "Update preview" in result.output
    assert (
        "participant/construction-updates → "
        "participant/campus-wiki-fork"
        in result.output
    )
    assert "2 changes · 1 edited · 1 added" in result.output
    assert (
        f"EDIT  participant/campus-wiki-fork  "
        f"[{target_memory.uid[:8]}]"
        in result.output
    )
    assert "  - Visitor parking is available in Lot A." in result.output
    assert "  + Visitor parking is available in Lot C." in result.output
    assert "    Hours remain unchanged." in result.output
    assert (
        "ADD   participant/campus-wiki-fork  "
        f"[new:{addition.memory_uid[:8]}]"
        in result.output
    )
    assert "  + Follow temporary parking signs." in result.output
    assert (
        "Source  participant/construction-updates "
        f"[{source_memory.uid[:8]}]"
        in result.output
    )
    assert "Reason  The verified update changes the visitor lot." in result.output
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
        "diff --mem participant/campus-wiki-fork"
        f"#{target_memory.uid}"
        in result.output
    )
    assert (
        "--- a/participant/campus-wiki-fork"
        f"#{target_memory.uid}"
        in result.output
    )
    assert (
        "+++ b/participant/campus-wiki-fork"
        f"#{target_memory.uid}"
        in result.output
    )
    assert "@@ -1,2 +1,2 @@" in result.output
    assert "-Visitor parking is available in Lot A." in result.output
    assert "+Visitor parking is available in Lot C." in result.output
    assert " Hours remain unchanged." in result.output
    assert (
        "diff --mem participant/campus-wiki-fork"
        f"#{addition.memory_uid}"
        in result.output
    )
    assert "--- /dev/null" in result.output
    assert (
        "+++ b/participant/campus-wiki-fork"
        f"#{addition.memory_uid}"
        in result.output
    )
    assert "+Follow temporary parking signs." in result.output
    assert (
        "Sources: participant/construction-updates"
        f"#{source_memory.uid}"
        in result.output
    )


def test_diff_color_palette_is_present_for_a_terminal(isolated_store):
    store = MemoryStore()
    _stage(store)

    result = runner.invoke(app, ["diff"], color=True)

    assert result.exit_code == 0
    assert "\x1b[31m" in result.output
    assert "\x1b[32m" in result.output
    assert "\x1b[33m" in result.output
    assert "\x1b[36m" in result.output


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
        "participant/construction-updates → "
        "participant/campus-wiki-fork"
        in result.output
    )
    assert store.current_context_name() == "unrelated-current"
    assert after == before


def test_diff_renders_empty_fresh_stage(isolated_store):
    store = MemoryStore()
    _stage(store, changes=False)

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 0
    assert "0 changes · 0 edited · 0 added" in result.output
    assert "No staged changes." in result.output
    assert "EDIT  " not in result.output


def test_diff_renders_applied_local_update_from_recorded_base_read_only(
    isolated_store,
):
    store = MemoryStore()
    staged, _, target_memory, provider = _stage(store)
    applied = store.apply_staged_update(staged)
    assert applied.application is not None
    assert provider.calls == 1
    assert (
        store.load("participant/campus-wiki-fork")
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
        "participant/campus-wiki-fork"
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
    target = store.load("participant/campus-wiki-fork")
    ops.add(target, "A concurrent Wiki edit.")
    store.save(target)

    result = runner.invoke(app, ["diff"])

    assert result.exit_code == 1
    assert "  - Visitor parking is available in Lot A." in result.output
    assert "  + Visitor parking is available in Lot C." in result.output
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
        "participant/construction-updates → "
        "participant/campus-wiki-fork"
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
    store = MemoryStore()
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
    assert "terminal newline added" in semantic.output
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
