"""Terminal-independent Forget application and runtime contracts."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.operations.forget.application import (
    ForgetAnalysisRequest,
    ForgetApplicationError,
    ForgetApplyReceipt,
    ForgetApplyRequest,
    ForgetRevisionRequest,
    ForgetSelectionRequest,
    FrozenForgetSource,
    run_forget_analysis,
    run_forget_apply,
    run_forget_revision,
    run_forget_selection,
)
from memcommit.operations.forget.runtime import (
    MemoryStoreForgetSourcePort,
    execute_forget_analysis,
)
from memcommit.forget_resolution_adapter import (
    ForgetResolutionWorkbenchAdapter as LegacyForgetResolutionWorkbenchAdapter,
)
from memcommit.commands.forget.setup_workbench import (
    ForgetSetupReceipt as LegacyForgetSetupReceipt,
)
from memcommit.interfaces.tui.operations.forget.resolution import (
    ForgetResolutionWorkbenchAdapter,
)
from memcommit.interfaces.tui.operations.forget.setup import ForgetSetupReceipt
from memcommit.semantic.changes import ProposedChange
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


def _context(name: str = "forget/source") -> Context:
    context = Context(uid=str(uuid.uuid4()), name=name)
    context.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="The service desk used to be beside the west entrance.",
        )
    )
    context.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="Step-free access remains available through the north entrance.",
        )
    )
    return context


class _Provider:
    def __init__(self, *, keep_all: bool = False) -> None:
        self.keep_all = keep_all
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert operation == "forget"
        assert output_schema["properties"]["candidates"]["minItems"] == 2
        messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(
            messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
        )
        candidates = []
        for index, source in enumerate(payload["source"]["memories"]):
            drops = index == 0 and not self.keep_all
            candidates.append(
                {
                    "source_memory_id": source["item_id"],
                    "decision": "DELETE" if drops else "KEEP",
                    "proposed_content": "" if drops else source["content"],
                    "rationale": "Compared with the complete instruction.",
                    "criterion_item_ids": ["k1"],
                }
            )
        return json.dumps(
            {
                "overview": "Reviewed the complete Source frame.",
                "candidates": candidates,
            }
        )


class _SourcePort:
    def __init__(self, context: Context, events: list[str] | None = None) -> None:
        self.context = context
        self.events = events if events is not None else []
        self.apply_calls: list[tuple[str, tuple[ProposedChange, ...]]] = []
        self.source = FrozenForgetSource(
            context=context,
            display_name=context.name,
            granted=False,
            _runtime_token=self,
        )

    def freeze(self, request: ForgetAnalysisRequest) -> FrozenForgetSource:
        self.events.append("freeze")
        assert request.source_locator == self.context.name
        return self.source

    def apply(self, source, instruction, changes):
        assert source is self.source
        frozen = tuple(changes)
        self.apply_calls.append((instruction, frozen))
        return ForgetApplyReceipt(
            source_name=source.display_name,
            source_context_uid=source.context.uid,
            removed_count=1,
            edited_count=0,
            checkpoint_uid="checkpoint-1",
            undo_available=True,
            granted=False,
        )


def _analysis(
    *,
    port: _SourcePort | None = None,
    provider: _Provider | None = None,
):
    source_port = port or _SourcePort(_context())
    semantic_provider = provider or _Provider()
    result = run_forget_analysis(
        ForgetAnalysisRequest(source_port.context.name, "Forget the old desk."),
        source_port=source_port,
        provider_factory=lambda: semantic_provider,
    )
    return source_port, semantic_provider, result


def test_forget_application_has_no_command_or_terminal_dependency() -> None:
    relative_paths = (
        "operations/forget/application.py",
        "operations/forget/runtime.py",
        "operations/forget/provider.py",
    )
    for relative_path in relative_paths:
        path = Path(__file__).parents[1] / "memcommit" / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert not any(name.startswith("memcommit.commands") for name in imports)
        assert "typer" not in imports
        assert not any(name.startswith("prompt_toolkit") for name in imports)


def test_forget_tui_modules_own_the_legacy_component_identities() -> None:
    assert LegacyForgetSetupReceipt is ForgetSetupReceipt
    assert (
        LegacyForgetResolutionWorkbenchAdapter
        is ForgetResolutionWorkbenchAdapter
    )
    root = Path(__file__).parents[1] / "memcommit" / "interfaces" / "tui"
    for name in ("setup.py", "resolution.py", "workbench.py"):
        path = root / "operations" / "forget" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert not any(module.startswith("memcommit.commands") for module in imports)


def test_forget_freezes_source_before_provider_construction() -> None:
    events: list[str] = []
    port = _SourcePort(_context(), events)
    provider = _Provider()

    def provider_factory():
        events.append("provider")
        return provider

    result = run_forget_analysis(
        ForgetAnalysisRequest(port.context.name, "Forget the old desk."),
        source_port=port,
        provider_factory=provider_factory,
    )

    assert events == ["freeze", "provider"]
    assert result.provider_used is True
    assert len(result.snapshot.review.candidates) == 2
    assert result.snapshot.review.changes()[0].uid == next(
        iter(port.context.memories)
    )


def test_empty_forget_source_does_not_construct_provider() -> None:
    port = _SourcePort(Context(uid=str(uuid.uuid4()), name="forget/empty"))

    result = run_forget_analysis(
        ForgetAnalysisRequest(port.context.name, "Forget nothing."),
        source_port=port,
        provider_factory=lambda: pytest.fail("provider must remain unconstructed"),
    )

    assert result.provider_used is False
    assert result.snapshot.review.candidates == ()


def test_forget_selection_and_provider_revision_advance_one_review_identity() -> None:
    _port, _provider, analyzed = _analysis()
    original = analyzed.snapshot
    candidate = original.review.candidates[0]

    selected = run_forget_selection(
        ForgetSelectionRequest(
            snapshot=original,
            candidate_uid=candidate.uid,
            selection="KEEP",
        )
    )
    revised_provider = _Provider(keep_all=True)
    revised = run_forget_revision(
        ForgetRevisionRequest(
            snapshot=selected,
            feedback="Keep every reviewed Memory.",
        ),
        provider_factory=lambda: revised_provider,
    )

    assert selected.review.uid == original.review.uid
    assert selected.review.revision == original.review.revision + 1
    assert selected.version_token != original.version_token
    assert revised.review.uid == original.review.uid
    assert revised.review.revision == selected.review.revision + 1
    assert revised.version_token not in {original.version_token, selected.version_token}
    assert revised.review.changes() == []


def test_forget_noop_skips_apply_port_and_has_no_checkpoint() -> None:
    port = _SourcePort(_context())
    _port, _provider, analyzed = _analysis(
        port=port,
        provider=_Provider(keep_all=True),
    )

    result = run_forget_apply(
        ForgetApplyRequest(analyzed.snapshot),
        source_port=port,
    )

    assert result.applied is False
    assert result.receipt.changed_count == 0
    assert result.receipt.checkpoint_uid is None
    assert port.apply_calls == []


def test_forget_apply_accepts_only_the_exact_reviewed_effect_receipt() -> None:
    port, _provider, analyzed = _analysis()

    result = run_forget_apply(
        ForgetApplyRequest(analyzed.snapshot),
        source_port=port,
    )

    assert result.applied is True
    assert result.receipt.removed_count == 1
    assert result.receipt.checkpoint_uid == "checkpoint-1"
    assert len(port.apply_calls) == 1

    class _WrongReceiptPort(_SourcePort):
        def apply(self, source, instruction, changes):
            receipt = super().apply(source, instruction, changes)
            return ForgetApplyReceipt(
                source_name="another/source",
                source_context_uid=receipt.source_context_uid,
                removed_count=receipt.removed_count,
                edited_count=receipt.edited_count,
                checkpoint_uid=receipt.checkpoint_uid,
                undo_available=receipt.undo_available,
                granted=receipt.granted,
            )

    wrong = _WrongReceiptPort(analyzed.snapshot.source.context)
    wrong.source = analyzed.snapshot.source
    with pytest.raises(ForgetApplicationError, match="outside the reviewed"):
        run_forget_apply(
            ForgetApplyRequest(analyzed.snapshot),
            source_port=wrong,
        )


def test_real_store_forget_apply_creates_one_checkpoint_and_preserves_other_memory(
    isolated_store,
) -> None:
    store = MemoryStore()
    context = _context("forget/runtime")
    store.create_context(context)
    store.set_current(context.name)
    source_uids = tuple(context.memories)
    provider = _Provider()

    analyzed = execute_forget_analysis(
        ForgetAnalysisRequest(None, "Forget the old desk."),
        store=store,
        provider_factory=lambda: provider,
    )
    result = run_forget_apply(
        ForgetApplyRequest(analyzed.snapshot),
        source_port=MemoryStoreForgetSourcePort(store),
    )

    current = store.load_direct(context.name)
    assert source_uids[0] not in current.memories
    assert source_uids[1] in current.memories
    assert result.receipt.checkpoint_uid is not None
    assert result.receipt.undo_available is True
    assert [entry["command"] for entry in store.list_checkpoints(context.name)].count(
        "forget"
    ) == 1


def test_real_store_forget_rejects_stale_source_without_partial_publication(
    isolated_store,
) -> None:
    store = MemoryStore()
    context = _context("forget/stale-runtime")
    store.create_context(context)
    store.set_current(context.name)
    original_uids = tuple(context.memories)
    analyzed = execute_forget_analysis(
        ForgetAnalysisRequest(None, "Forget the old desk."),
        store=store,
        provider_factory=_Provider,
    )

    concurrent = store.load_direct(context.name)
    added = ops.add(concurrent, "A concurrent note must survive.")
    store.save(
        concurrent,
        AutoCheckpoint(
            command="add",
            args={},
            description="Concurrent test change.",
        ),
    )

    with pytest.raises(ConcurrentContextUpdateError):
        run_forget_apply(
            ForgetApplyRequest(analyzed.snapshot),
            source_port=MemoryStoreForgetSourcePort(store),
        )

    current = store.load_direct(context.name)
    assert set(original_uids) <= set(current.memories)
    assert added.uid in current.memories
    assert [entry["command"] for entry in store.list_checkpoints(context.name)].count(
        "forget"
    ) == 0
