"""Append-only contracts for the new Elaborate operation."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.adapters.console.commands.elaborate.command as elaborate_command
import memcommit.adapters.console.commands.elaborate.impact as elaborate_impact
from memcommit.adapters.console.entrypoint import app
from memcommit.application.operations.elaborate.application import (
    ElaborateError,
    ElaborateRequest,
    FrozenElaborateSource,
    elaborate_frame,
    prepare_elaborate,
)
from memcommit.application.operations.elaborate.model import (
    ELABORATE_SEPARATOR,
    ElaborateFrame,
    ElaborateSource,
)
from memcommit.application.operations.elaborate.runtime import (
    execute_elaborate,
    prepare_elaborate_with_store,
)
from memcommit.application.operations.review.applied_checkpoint import (
    list_applied_checkpoint_reviews,
)
from memcommit.adapters.console.commands.elaborate.impact import (
    render_elaborate_impact,
)
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _frame(content: str = "Original statement.") -> ElaborateFrame:
    return ElaborateFrame(
        context_uid="context-uid",
        context_name="notes",
        context_digest="context-digest",
        target_alias="m000001",
        sources=(
            ElaborateSource("m000001", "memory-1", content),
            ElaborateSource("m000002", "memory-2", "Supporting detail."),
        ),
    )


class _Provider:
    def __init__(
        self,
        *,
        disposition: str = "EXPAND",
        continuation: str = "This makes the existing condition explicit.",
    ):
        self.disposition = disposition
        self.continuation = continuation
        self.calls = 0
        self.payload = None
        self.output_schema = None

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert operation == "elaborate_memory"
        assert output_schema is not None
        self.output_schema = output_schema
        self.payload = json.loads(prompt.split("ELABORATE PAYLOAD:\n", 1)[1])
        return json.dumps(
            {
                "disposition": self.disposition,
                "continuation": self.continuation,
                "reason": "The target and its direct Context support this wording.",
                "source_ids": ["m000001", "m000002"],
            }
        )


def test_elaborate_builds_result_by_appending_after_unchanged_original():
    frame = _frame()
    provider = _Provider()
    revision = elaborate_frame(frame, provider)

    assert revision.original_content == "Original statement."
    assert revision.continuation == "This makes the existing condition explicit."
    assert revision.content == (
        revision.original_content
        + ELABORATE_SEPARATOR
        + revision.continuation
    )
    assert revision.content.startswith(revision.original_content)
    assert revision.memory_uid == "memory-1"
    assert revision.changed is True
    assert "uniqueItems" not in json.dumps(provider.output_schema)


def test_elaborate_rejects_duplicate_source_ids_after_provider_return():
    class DuplicateSourceProvider(_Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            return json.dumps(
                {
                    "disposition": "EXPAND",
                    "continuation": "Unsupported continuation.",
                    "reason": "Invalid test result.",
                    "source_ids": ["m000001", "m000001"],
                }
            )

    with pytest.raises(ElaborateError, match="distinct source aliases"):
        elaborate_frame(_frame(), DuplicateSourceProvider())


def test_elaborate_keep_never_changes_or_appends_content():
    revision = elaborate_frame(
        _frame(),
        _Provider(disposition="KEEP", continuation=""),
    )

    assert revision.changed is False
    assert revision.continuation == ""
    assert revision.content == revision.original_content


def test_elaborate_rejects_a_missing_target_citation():
    class MissingTargetProvider(_Provider):
        def complete(self, prompt, *, operation, output_schema=None):
            super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            return json.dumps(
                {
                    "disposition": "EXPAND",
                    "continuation": "Unsupported continuation.",
                    "reason": "Invalid test result.",
                    "source_ids": ["m000002"],
                }
            )

    with pytest.raises(ElaborateError, match="cite the target"):
        elaborate_frame(_frame(), MissingTargetProvider())


def test_prepare_elaborate_rejects_context_drift_after_provider_turn():
    initial = _frame()
    changed = ElaborateFrame(
        context_uid=initial.context_uid,
        context_name=initial.context_name,
        context_digest="changed-digest",
        target_alias=initial.target_alias,
        sources=initial.sources,
    )

    class SourcePort:
        def freeze(self, request):
            return FrozenElaborateSource(initial, token="source")

        def revalidate(self, source):
            assert source.token == "source"
            return changed

    with pytest.raises(ElaborateError, match="changed while Elaborate was running"):
        prepare_elaborate(
            ElaborateRequest("memory-1", "notes"),
            source_port=SourcePort(),
            provider_factory=_Provider,
        )


def test_execute_elaborate_preserves_uid_and_position_and_saves_one_checkpoint(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("append-notes")
    target = ops.add(context, "Original statement.")
    support = ops.add(context, "Supporting detail.")
    store.save(context)
    store.set_current(context.name)
    original_order = context.ordered_uids()

    receipt = execute_elaborate(
        ElaborateRequest(target.uid),
        store=store,
        provider_factory=_Provider,
    )

    saved = store.load_direct(context.name)
    assert saved.ordered_uids() == original_order
    assert saved.memories[target.uid].content == (
        "Original statement."
        + ELABORATE_SEPARATOR
        + "This makes the existing condition explicit."
    )
    assert saved.memories[support.uid].content == "Supporting detail."
    assert receipt.memory_uid == target.uid
    assert receipt.checkpoint_uid is not None
    checkpoints = store.list_checkpoints(context.name)
    assert len(checkpoints) == 1
    assert checkpoints[0]["command"] == "elaborate"
    assert checkpoints[0]["args"]["effects"][0]["kind"] == "APPEND"


def test_prepare_elaborate_impact_path_does_not_mutate_or_checkpoint(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("impact-notes")
    target = ops.add(context, "Original statement.")
    ops.add(context, "Supporting detail.")
    store.save(context)
    store.set_current(context.name)

    _port, prepared = prepare_elaborate_with_store(
        ElaborateRequest(target.uid),
        store=store,
        provider_factory=_Provider,
    )

    assert prepared.revision.changed is True
    saved = store.load_direct(context.name)
    assert saved.memories[target.uid].content == "Original statement."
    assert store.list_checkpoints(context.name) == []


def test_elaborate_impact_renders_original_continuation_and_result():
    revision = elaborate_frame(_frame(), _Provider())

    rendered = render_elaborate_impact(revision)

    assert "ORIGINAL\n" + revision.original_content in rendered
    assert "APPENDED ELABORATION\n" + revision.continuation in rendered
    assert "RESULT\n" + revision.content in rendered
    assert "EFFECTS · NONE" in rendered


def test_execute_elaborate_keep_saves_no_checkpoint(isolated_store):
    store = MemoryStore()
    context = ops.init("keep-notes")
    target = ops.add(context, "Original statement.")
    ops.add(context, "Supporting detail.")
    store.save(context)
    store.set_current(context.name)

    receipt = execute_elaborate(
        ElaborateRequest(target.uid),
        store=store,
        provider_factory=lambda: _Provider(disposition="KEEP", continuation=""),
    )

    assert receipt.changed is False
    assert receipt.checkpoint_uid is None
    assert store.load_direct(context.name).memories[target.uid].content == (
        "Original statement."
    )
    assert store.list_checkpoints(context.name) == []


def test_applied_elaborate_checkpoint_is_not_misclassified_as_legacy_makemore(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("review-notes")
    target = ops.add(context, "Original statement.")
    ops.add(context, "Supporting detail.")
    store.save(context)
    store.set_current(context.name)
    receipt = execute_elaborate(
        ElaborateRequest(target.uid),
        store=store,
        provider_factory=_Provider,
    )

    checkpoint = store.list_checkpoints(context.name)[0]

    assert checkpoint["uid"] == receipt.checkpoint_uid
    assert checkpoint["args"]["contract"] == "append-only-v1"
    assert checkpoint["args"]["effects"][0]["kind"] == "APPEND"
    assert list_applied_checkpoint_reviews(store, "makemore") == ()


def test_mem_elaborate_applies_the_append_only_revision(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("cli-notes")
    target = ops.add(context, "Original statement.")
    ops.add(context, "Supporting detail.")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(elaborate_command, "connect_semantic_provider", _Provider)

    result = runner.invoke(app, ["elaborate", target.uid])

    assert result.exit_code == 0, result.output
    assert "ELABORATE APPLIED" in result.output
    assert "SAME UID · SAME POSITION" in result.output
    assert store.load_direct(context.name).memories[target.uid].content.endswith(
        "This makes the existing condition explicit."
    )


def test_mem_impact_elaborate_is_plain_and_non_mutating(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("cli-impact-notes")
    target = ops.add(context, "Original statement.")
    ops.add(context, "Supporting detail.")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(elaborate_impact, "connect_semantic_provider", _Provider)

    result = runner.invoke(app, ["impact", "elaborate", target.uid])

    assert result.exit_code == 0, result.output
    assert "ORIGINAL\nOriginal statement." in result.output
    assert "APPENDED ELABORATION" in result.output
    assert "RESULT" in result.output
    assert "EFFECTS · NONE" in result.output
    assert store.load_direct(context.name).memories[target.uid].content == (
        "Original statement."
    )
    assert store.list_checkpoints(context.name) == []
