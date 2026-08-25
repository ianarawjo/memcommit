"""Application-boundary contracts for terminal-independent Sever execution."""

from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path

import pytest

import memcommit.commands.sever as sever_command
import memcommit.ops as ops
from memcommit.sever import (
    SeverApplication,
    SeverCandidate,
    SeverContextBinding,
    SeverMemory,
    SeverSession,
)
import memcommit.operations.sever.application as sever_application
from memcommit.operations.sever.application import (
    FrozenSeverInputs,
    SeverAnalysisProgress,
    SeverAnalysisRequest,
    SeverAnalysisResult,
    SeverApplicationError,
    SeverApplyRequest,
    SeverDecisionRequest,
    SeverDestinationRequest,
    SeverPersistedApplyRequest,
    SeverPreparedAnalysis,
    SeverPreparedOrigin,
    SeverSessionSnapshot,
    run_sever_analysis,
    run_sever_apply,
    run_sever_session_apply,
    run_sever_session_decision,
    run_sever_session_destination_change,
    run_sever_session_open,
    run_sever_session_start,
)
from memcommit.sever_provider import SEVER_PAYLOAD_MARKER
import memcommit.operations.sever.runtime as sever_runtime
from memcommit.operations.sever.runtime import (
    execute_sever_analysis,
    execute_sever_apply,
    execute_sever_session_apply,
    execute_sever_session_decision,
    execute_sever_session_destination_change,
    execute_sever_session_open,
    execute_sever_session_start,
)
from memcommit.sever_store import SeverSessionStore
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


SOURCE_CONTEXT_UID = "11111111-1111-4111-8111-111111111111"
CRITERIA_CONTEXT_UID = "22222222-2222-4222-8222-222222222222"
SOURCE_MEMORY_UID = "33333333-3333-4333-8333-333333333333"
CRITERIA_MEMORY_UID = "44444444-4444-4444-8444-444444444444"
SESSION_UID = "55555555-5555-4555-8555-555555555555"
CANDIDATE_UID = "66666666-6666-4666-8666-666666666666"


def _binding(
    *,
    context_uid: str,
    memory_uid: str,
    name: str,
    content: str,
) -> SeverContextBinding:
    return SeverContextBinding(
        root_uid=context_uid,
        root_name=name,
        frame_digest="a" * 64,
        contexts=((name, context_uid, "b" * 64),),
        memories=(
            SeverMemory(
                uid=memory_uid,
                context_name=name,
                content=content,
            ),
        ),
        include_descendants=False,
    )


def _inputs() -> FrozenSeverInputs:
    return FrozenSeverInputs(
        source=_binding(
            context_uid=SOURCE_CONTEXT_UID,
            memory_uid=SOURCE_MEMORY_UID,
            name="source",
            content="Keep only the access requirement.",
        ),
        criteria=_binding(
            context_uid=CRITERIA_CONTEXT_UID,
            memory_uid=CRITERIA_MEMORY_UID,
            name="criteria",
            content="Minimize unrelated personal detail.",
        ),
    )


def _review(inputs: FrozenSeverInputs, *, output_name: str = "result") -> SeverSession:
    return SeverSession(
        uid=SESSION_UID,
        revision=1,
        state="REVIEWING",
        source=inputs.source,
        criteria=inputs.criteria,
        output_name=output_name,
        overview="The result retains only the necessary access requirement.",
        candidates=(
            SeverCandidate(
                uid=CANDIDATE_UID,
                source_memory_uid=inputs.source.memories[0].uid,
                recommendation="KEEP_SUMMARY",
                proposed_content="Needs step-free access.",
                rationale="The criterion permits the necessary access requirement.",
                criterion_memory_uids=(inputs.criteria.memories[0].uid,),
            ),
        ),
    )


class _StaticInputPort:
    def __init__(self, inputs: FrozenSeverInputs):
        self.inputs = inputs
        self.requests: list[SeverAnalysisRequest] = []

    def freeze(self, request: SeverAnalysisRequest) -> FrozenSeverInputs:
        self.requests.append(request)
        return self.inputs


class _SessionRepository:
    def __init__(self):
        self.current: SeverSessionSnapshot | None = None

    @staticmethod
    def _snapshot(session: SeverSession) -> SeverSessionSnapshot:
        return SeverSessionSnapshot(
            session=session,
            version_token=f"revision-{session.revision}",
        )

    def create(self, session: SeverSession) -> SeverSessionSnapshot:
        if self.current is not None:
            raise RuntimeError("duplicate session")
        self.current = self._snapshot(session)
        return self.current

    def load(self, uid: str) -> SeverSessionSnapshot:
        if self.current is None or self.current.session.uid != uid:
            raise RuntimeError("missing session")
        return self.current

    def replace(
        self,
        session: SeverSession,
        *,
        expected_version: str,
    ) -> SeverSessionSnapshot:
        if self.current is None or self.current.version_token != expected_version:
            raise RuntimeError("stale session")
        self.current = self._snapshot(session)
        return self.current


class _DestinationPort:
    def __init__(self, *taken: str):
        self.taken = frozenset(taken)
        self.calls: list[tuple[str, str]] = []

    def validate(self, output_name: str, *, current_output_name: str) -> None:
        self.calls.append((output_name, current_output_name))
        if output_name != current_output_name and output_name in self.taken:
            raise SeverApplicationError("destination already exists")


class _OutputPort:
    def __init__(self):
        self.materialized: list[SeverSession] = []
        self.rolled_back: list[SeverSession] = []

    def recover_materialization(self, review: SeverSession) -> SeverSession | None:
        return None

    def materialize(self, review: SeverSession) -> SeverSession:
        self.materialized.append(review)
        return review.with_application(
            SeverApplication(
                output_context_uid="77777777-7777-4777-8777-777777777777",
                checkpoint_uid="88888888-8888-4888-8888-888888888888",
                result_memory_uids=("99999999-9999-4999-8999-999999999999",),
            )
        )

    def rollback_materialization(self, applied: SeverSession) -> None:
        self.rolled_back.append(applied)


class _Provider:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert operation == "sever_context"
        payload = json.loads(prompt.split(SEVER_PAYLOAD_MARKER, 1)[1])
        source_id = payload["source"]["memories"][0]["memory_id"]
        criterion_id = payload["criteria"]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": "The result retains only the necessary access requirement.",
                "application_summary": {
                    "text": "The access requirement was condensed under minimization.",
                    "source_memory_ids": [source_id],
                    "criterion_memory_ids": [criterion_id],
                },
                "candidates": [
                    {
                        "source_memory_id": source_id,
                        "decision": "KEEP_SUMMARY",
                        "proposed_content": "Needs step-free access.",
                        "rationale": (
                            "The criterion permits the necessary access requirement."
                        ),
                        "criterion_memory_ids": [criterion_id],
                    }
                ],
            }
        )


def test_run_sever_analysis_converges_on_one_typed_request_without_terminal():
    inputs = _inputs()
    input_port = _StaticInputPort(inputs)
    provider = _Provider()
    provider_calls = 0
    stages: list[SeverAnalysisProgress] = []
    request = SeverAnalysisRequest(
        source_locator="source",
        criteria_locator="criteria",
        output_name="result",
        source_include_descendants=False,
        criteria_include_descendants=False,
    )

    def provider_factory():
        nonlocal provider_calls
        provider_calls += 1
        return provider

    result = run_sever_analysis(
        request,
        input_port=input_port,
        provider_factory=provider_factory,
        progress_observer=stages.append,
    )

    assert input_port.requests == [request]
    assert provider_calls == 1
    assert provider.calls == 1
    assert [event.stage for event in stages] == [
        "INPUTS_FROZEN",
        "CONNECTING_PROVIDER",
        "ANALYZING",
    ]
    assert result.origin == "PROVIDER"
    assert result.session.source == inputs.source
    assert result.session.criteria == inputs.criteria
    assert result.session.output_name == "result"


@pytest.mark.parametrize(
    "origin",
    (
        "EXACT_PREWARM",
        "EQUIVALENT_SCOPE_PREWARM",
        "PROJECTED_PREWARM",
    ),
)
def test_prepared_review_retains_origin_and_never_constructs_provider(
    origin: SeverPreparedOrigin,
):
    inputs = _inputs()
    stages: list[SeverAnalysisProgress] = []

    result = run_sever_analysis(
        SeverAnalysisRequest("source", "criteria", "result", False, False),
        input_port=_StaticInputPort(inputs),
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("an exact prepared review must not construct a provider")
        ),
        prepared_lookup=lambda frozen, output: SeverPreparedAnalysis(
            session=_review(frozen, output_name=output),
            origin=origin,
        ),
        progress_observer=stages.append,
    )

    assert result.origin == origin
    assert [event.stage for event in stages] == [
        "INPUTS_FROZEN",
        "PREPARED_REUSED",
    ]


def test_prepared_review_cannot_change_frozen_source_or_output():
    inputs = _inputs()
    other_source = replace(inputs.source, root_name="other-source")
    invalid = replace(
        _review(inputs),
        source=other_source,
        output_name="other-result",
    )

    with pytest.raises(SeverApplicationError, match="outside the frozen request"):
        run_sever_analysis(
            SeverAnalysisRequest("source", "criteria", "result", False, False),
            input_port=_StaticInputPort(inputs),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("invalid prepared review must not reach provider")
            ),
            prepared_lookup=lambda _inputs, _output: SeverPreparedAnalysis(
                session=invalid,
                origin="PROJECTED_PREWARM",
            ),
        )


def test_run_sever_apply_validates_receipt_and_is_idempotent():
    session = _review(_inputs())
    materialized: list[SeverSession] = []

    class OutputPort:
        def materialize(self, review: SeverSession) -> SeverSession:
            materialized.append(review)
            return review.with_application(
                SeverApplication(
                    output_context_uid="77777777-7777-4777-8777-777777777777",
                    checkpoint_uid="88888888-8888-4888-8888-888888888888",
                    result_memory_uids=(
                        "99999999-9999-4999-8999-999999999999",
                    ),
                )
            )

    first = run_sever_apply(
        SeverApplyRequest(session),
        output_port=OutputPort(),
    )
    second = run_sever_apply(
        SeverApplyRequest(first.session),
        output_port=OutputPort(),
    )

    assert materialized == [session]
    assert first.created is True
    assert first.session.state == "APPLIED"
    assert second.created is False
    assert second.session is first.session


def test_saved_session_lifecycle_owns_start_review_destination_and_apply():
    review = _review(_inputs())
    repository = _SessionRepository()
    destination = _DestinationPort()
    output = _OutputPort()

    started = run_sever_session_start(
        SeverAnalysisResult(session=review, origin="PROVIDER"),
        repository=repository,
    )
    opened = run_sever_session_open(review.uid, repository=repository)
    decided = run_sever_session_decision(
        SeverDecisionRequest(
            snapshot=opened,
            candidate_uid=CANDIDATE_UID,
            selection="AS_WRITTEN",
        ),
        repository=repository,
    )
    relocated = run_sever_session_destination_change(
        SeverDestinationRequest(
            snapshot=decided,
            output_name="relocated-result",
        ),
        repository=repository,
        destination_port=destination,
    )
    applied = run_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=relocated),
        repository=repository,
        output_port=output,
    )
    repeated = run_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=applied.snapshot),
        repository=repository,
        output_port=output,
    )

    assert started.origin == "PROVIDER"
    assert opened == started.snapshot
    assert decided.session.revision == 2
    assert decided.session.candidates[0].selection == "AS_WRITTEN"
    assert relocated.session.revision == 3
    assert relocated.session.output_name == "relocated-result"
    assert destination.calls == [("relocated-result", "result")]
    assert applied.created is True
    assert applied.snapshot.session.state == "APPLIED"
    assert repeated.created is False
    assert repeated.snapshot == applied.snapshot
    assert output.materialized == [relocated.session]
    assert repository.current == applied.snapshot


def test_saved_session_lifecycle_rejects_stale_and_invalid_review_requests():
    repository = _SessionRepository()
    started = run_sever_session_start(
        SeverAnalysisResult(session=_review(_inputs()), origin="PROVIDER"),
        repository=repository,
    )
    first = run_sever_session_decision(
        SeverDecisionRequest(
            snapshot=started.snapshot,
            candidate_uid=CANDIDATE_UID,
            selection="FORGET",
        ),
        repository=repository,
    )

    with pytest.raises(RuntimeError, match="stale session"):
        run_sever_session_decision(
            SeverDecisionRequest(
                snapshot=started.snapshot,
                candidate_uid=CANDIDATE_UID,
                selection="AS_WRITTEN",
            ),
            repository=repository,
        )
    stale_output = _OutputPort()
    with pytest.raises(SeverApplicationError, match="changed before Apply"):
        run_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            repository=repository,
            output_port=stale_output,
        )
    assert stale_output.materialized == []
    with pytest.raises(SeverApplicationError, match="requires nonempty"):
        run_sever_session_decision(
            SeverDecisionRequest(
                snapshot=first,
                candidate_uid=CANDIDATE_UID,
                selection="CUSTOM",
            ),
            repository=repository,
        )
    with pytest.raises(SeverApplicationError, match="destination already exists"):
        run_sever_session_destination_change(
            SeverDestinationRequest(snapshot=first, output_name="taken"),
            repository=repository,
            destination_port=_DestinationPort("taken"),
        )

    class WrongIdentityRepository:
        def load(self, _uid: str) -> SeverSessionSnapshot:
            return SeverSessionSnapshot(
                session=replace(
                    first.session,
                    uid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                ),
                version_token=first.version_token,
            )

    with pytest.raises(SeverApplicationError, match="different session identity"):
        run_sever_session_open(
            first.session.uid,
            repository=WrongIdentityRepository(),  # type: ignore[arg-type]
        )

    assert repository.current == first

    applied = run_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=first),
        repository=repository,
        output_port=stale_output,
    )
    application = applied.snapshot.session.application
    assert application is not None
    after_undo = applied.snapshot.session.clear_application(
        output_context_uid=application.output_context_uid,
        checkpoint_uid=application.checkpoint_uid,
    )
    repository.current = repository._snapshot(after_undo)

    with pytest.raises(SeverApplicationError, match="changed before Apply"):
        run_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=applied.snapshot),
            repository=repository,
            output_port=stale_output,
        )
    assert stale_output.materialized == [first.session]


def test_saved_session_apply_rolls_back_output_when_session_cas_fails():
    review = _review(_inputs())
    repository = _SessionRepository()
    started = run_sever_session_start(
        SeverAnalysisResult(session=review, origin="PROVIDER"),
        repository=repository,
    )
    output = _OutputPort()

    class FailingReplaceRepository(_SessionRepository):
        def replace(
            self,
            session: SeverSession,
            *,
            expected_version: str,
        ) -> SeverSessionSnapshot:
            raise RuntimeError("session receipt write failed")

    failing = FailingReplaceRepository()
    failing.current = repository.current

    with pytest.raises(RuntimeError, match="session receipt write failed"):
        run_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            repository=failing,
            output_port=output,
        )

    assert output.materialized == [review]
    assert len(output.rolled_back) == 1
    assert output.rolled_back[0].state == "APPLIED"
    assert failing.current == started.snapshot


def test_saved_session_apply_recovers_receipt_committed_before_reported_error():
    review = _review(_inputs())
    repository = _SessionRepository()
    started = run_sever_session_start(
        SeverAnalysisResult(session=review, origin="PROVIDER"),
        repository=repository,
    )
    output = _OutputPort()

    class CommitThenFailRepository(_SessionRepository):
        def replace(
            self,
            session: SeverSession,
            *,
            expected_version: str,
        ) -> SeverSessionSnapshot:
            super().replace(session, expected_version=expected_version)
            raise RuntimeError("late persistence report")

    committing = CommitThenFailRepository()
    committing.current = repository.current

    applied = run_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=started.snapshot),
        repository=committing,
        output_port=output,
    )

    assert applied.created is True
    assert applied.snapshot.session.state == "APPLIED"
    assert output.rolled_back == []
    assert committing.current == applied.snapshot


def test_sever_application_has_no_command_typer_or_tui_imports():
    source = Path(sever_application.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer"
        or name.startswith("prompt_toolkit")
        or name.startswith("memcommit.commands")
    )
    assert forbidden == ()


def test_sever_runtime_has_no_typer_or_tui_imports():
    source = Path(sever_runtime.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    forbidden = tuple(
        name
        for name in imported
        if name == "typer" or name.startswith("prompt_toolkit")
    )
    assert forbidden == ()


def test_sever_command_does_not_own_session_mutation_or_persistence():
    source = Path(sever_command.__file__).read_text(encoding="utf-8")

    assert "session_store.save(" not in source
    assert "session_store.load(" not in source
    assert "sessions.save(" not in source
    assert ".select(" not in source
    assert ".with_output_name(" not in source
    assert "sever_record_digest" not in source


def test_real_store_analysis_and_apply_are_terminal_free_and_preserve_source(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    source = ops.init("application/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("application/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    provider = _Provider()

    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="application/result",
            source_include_descendants=False,
            criteria_include_descendants=False,
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    assert analysis.origin == "PROVIDER"
    assert provider.calls == 1
    assert not store.context_exists("application/result")
    before = store.load_direct(source.name).to_dict()

    applied = execute_sever_apply(
        SeverApplyRequest(analysis.session),
        store=store,
    )

    assert applied.created is True
    assert applied.session.application is not None
    assert store.load_direct(source.name).to_dict() == before
    result = store.load_direct("application/result")
    assert [item.content for item in result.iter_items()] == [
        "Needs step-free access."
    ]
    [checkpoint] = store.list_checkpoints("application/result")
    assert checkpoint["command"] == "sever"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_real_store_saved_lifecycle_persists_cas_and_source_invariants(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    source = ops.init("lifecycle/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("lifecycle/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    source_before = store.load_direct(source.name).to_dict()

    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="lifecycle/result",
            source_include_descendants=False,
            criteria_include_descendants=False,
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)
    opened = execute_sever_session_open(analysis.session.uid, store=store)
    decided = execute_sever_session_decision(
        SeverDecisionRequest(
            snapshot=opened,
            candidate_uid=opened.session.candidates[0].uid,
            selection="AS_WRITTEN",
        ),
        store=store,
    )
    relocated = execute_sever_session_destination_change(
        SeverDestinationRequest(
            snapshot=decided,
            output_name="lifecycle/final",
        ),
        store=store,
    )

    with pytest.raises(
        ConcurrentContextUpdateError,
        match="changed before it could be saved",
    ):
        execute_sever_session_decision(
            SeverDecisionRequest(
                snapshot=opened,
                candidate_uid=opened.session.candidates[0].uid,
                selection="FORGET",
            ),
            store=store,
        )

    applied = execute_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=relocated),
        store=store,
    )
    repeated = execute_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=applied.snapshot),
        store=store,
    )

    assert opened == started.snapshot
    assert applied.created is True
    assert repeated.created is False
    assert SeverSessionStore(store).load(analysis.session.uid) == applied.snapshot.session
    assert store.load_direct(source.name).to_dict() == source_before
    result = store.load_direct("lifecycle/final")
    assert [item.content for item in result.iter_items()] == [
        "Keep only the access requirement."
    ]
    [checkpoint] = store.list_checkpoints("lifecycle/final")
    assert checkpoint["args"]["sever"]["session_digest"] == relocated.version_token
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize("changed_input", ("source", "criteria"))
def test_real_store_apply_rejects_changed_local_inputs_before_output_creation(
    isolated_store,
    changed_input,
):
    store = MemoryStore()
    source = ops.init("freshness/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("freshness/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="freshness/result",
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)
    changed = store.load_direct(
        source.name if changed_input == "source" else criteria.name
    )
    ops.add(changed, f"Changed {changed_input} after review.")
    store.save(changed)

    with pytest.raises(
        ConcurrentContextUpdateError,
        match="changed before the result could be saved",
    ):
        execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            store=store,
        )

    assert not store.context_exists("freshness/result")
    assert SeverSessionStore(store).load(analysis.session.uid) == analysis.session


def test_real_store_apply_rolls_back_result_when_session_receipt_save_fails(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("rollback/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("rollback/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="rollback/result",
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)

    def fail_replace(self, session, *, expected_version):
        raise RuntimeError("session receipt write failed")

    monkeypatch.setattr(
        sever_runtime.MemoryStoreSeverSessionRepository,
        "replace",
        fail_replace,
    )

    with pytest.raises(RuntimeError, match="session receipt write failed"):
        execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            store=store,
        )

    assert not store.context_exists("rollback/result")
    assert SeverSessionStore(store).load(analysis.session.uid) == analysis.session


def test_real_store_destination_change_selects_self_save_but_rejects_other_existing(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("destination/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("destination/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="destination/result",
            source_include_descendants=False,
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)

    self_save = execute_sever_session_destination_change(
        SeverDestinationRequest(
            snapshot=started.snapshot,
            output_name=source.name,
        ),
        store=store,
    )

    assert self_save.session.save_mode == "SELF_SAVE"
    with pytest.raises(SeverApplicationError, match="already exists"):
        execute_sever_session_destination_change(
            SeverDestinationRequest(
                snapshot=self_save,
                output_name=criteria.name,
            ),
            store=store,
        )


def test_real_store_self_save_rolls_back_source_when_session_receipt_save_fails(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("rollback-self/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("rollback-self/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    original = store.load_direct(source.name).to_dict()
    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name=source.name,
            source_include_descendants=False,
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)

    def fail_replace(self, session, *, expected_version):
        raise RuntimeError("self-save receipt write failed")

    monkeypatch.setattr(
        sever_runtime.MemoryStoreSeverSessionRepository,
        "replace",
        fail_replace,
    )

    with pytest.raises(RuntimeError, match="self-save receipt write failed"):
        execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            store=store,
        )

    assert store.load_direct(source.name).to_dict() == original
    assert store.list_checkpoints(source.name) == []
    assert SeverSessionStore(store).load(analysis.session.uid) == analysis.session


def test_real_store_recovers_exact_result_left_before_session_receipt(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("recovery/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("recovery/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="recovery/result",
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)
    orphaned = execute_sever_apply(
        SeverApplyRequest(started.snapshot.session),
        store=store,
    )
    orphaned_application = orphaned.session.application
    assert orphaned_application is not None

    recovered = execute_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=started.snapshot),
        store=store,
    )

    assert recovered.created is False
    assert recovered.snapshot.session.state == "APPLIED"
    assert recovered.snapshot.session.application == orphaned_application
    assert store.load_direct("recovery/result").uid == (
        orphaned_application.output_context_uid
    )


def test_real_store_recovers_exact_self_save_left_before_session_receipt(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("recovery-self/source")
    source_memory = ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("recovery-self/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name=source.name,
            source_include_descendants=False,
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)
    orphaned = execute_sever_apply(
        SeverApplyRequest(started.snapshot.session),
        store=store,
    )
    orphaned_application = orphaned.session.application
    assert orphaned_application is not None

    recovered = execute_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=started.snapshot),
        store=store,
    )

    assert recovered.created is False
    assert recovered.snapshot.session.application == orphaned_application
    self_saved = store.load_direct(source.name)
    assert self_saved.uid == source.uid
    assert tuple(self_saved.memories) == (source_memory.uid,)


def test_real_store_all_keep_review_still_creates_result_and_checkpoint(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("all-keep/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("all-keep/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="all-keep/result",
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)

    applied = execute_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=started.snapshot),
        store=store,
    )

    assert applied.created is True
    result = store.load_direct("all-keep/result")
    assert [memory.content for memory in result.iter_items()] == [
        "Needs step-free access."
    ]
    [checkpoint] = store.list_checkpoints("all-keep/result")
    assert checkpoint["command"] == "sever"


def test_real_store_apply_name_race_leaves_review_and_existing_owner_unchanged(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("collision/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("collision/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="collision/result",
        ),
        store=store,
        provider_factory=_Provider,
    )
    started = execute_sever_session_start(analysis, store=store)
    owner = ops.init("collision/result")
    ops.add(owner, "Concurrent owner.")
    store.create_context(owner)

    with pytest.raises(FileExistsError, match="already exists"):
        execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            store=store,
        )

    assert store.load_direct(owner.name).to_dict() == owner.to_dict()
    assert SeverSessionStore(store).load(analysis.session.uid) == analysis.session


def test_runtime_retains_projected_cache_origin_and_skips_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("projection/source")
    ops.add(source, "Keep only the access requirement.")
    criteria = ops.init("projection/criteria")
    ops.add(criteria, "Minimize unrelated personal detail.")
    store.create_context(source)
    store.create_context(criteria)
    lookups = []

    def projected_lookup(*, store, source, criteria, output_name):
        lookups.append((store, source, criteria, output_name))

        class Match:
            session = _review(
                FrozenSeverInputs(source=source, criteria=criteria),
                output_name=output_name,
            )
            origin = "PROJECTED_PREWARM"

        return Match()

    monkeypatch.setattr(
        sever_runtime,
        "find_installed_projectable_sever_prewarm",
        projected_lookup,
    )

    result = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator=source.name,
            criteria_locator=criteria.name,
            output_name="projection/result",
            source_include_descendants=False,
            criteria_include_descendants=False,
        ),
        store=store,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("projected prepared analysis must not construct provider")
        ),
    )

    assert result.origin == "PROJECTED_PREWARM"
    assert len(lookups) == 1
    assert lookups[0][3] == "projection/result"
    assert not store.context_exists("projection/result")


def test_real_store_rejects_missing_source_before_provider_construction(
    isolated_store,
):
    store = MemoryStore()
    criteria = ops.init("criteria")
    ops.add(criteria, "Criterion")
    store.create_context(criteria)
    provider_calls = 0

    def forbidden_provider():
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("missing input must fail before provider construction")

    with pytest.raises(FileNotFoundError, match="missing-source"):
        execute_sever_analysis(
            SeverAnalysisRequest(
                source_locator="missing-source",
                criteria_locator=criteria.name,
                output_name="result",
            ),
            store=store,
            provider_factory=forbidden_provider,
        )

    assert provider_calls == 0
