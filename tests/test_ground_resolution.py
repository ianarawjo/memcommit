from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import uuid

import pytest

from memcommit.context import Context, Memory
from memcommit.distill import DistillAnalysis, DistilledRule
from memcommit.distill_application import DistillRequest, DistillResult
from memcommit.elaborate import ElaborateAnalysis, ElaboratedRule, ElaborateMode
from memcommit.elaborate_application import ElaborateRequest, ElaborateResult
from memcommit.fit import FitExample, FitJudgment, FitReport, FitRule
from memcommit.fit_store import GroundFitReceipt
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_example,
    propose_ground_rule,
    upgrade_ground_to_propositions,
)
from memcommit.ground_distill import FrozenGroundDistill, GroundDistillResult
from memcommit.ground_elaborate import FrozenGroundElaborate, GroundElaborateResult
from memcommit.ground_resolution import (
    GroundFitResolutionChoice,
    GroundResolutionError,
)
from memcommit.ground_resolution_application import (
    apply_ground_resolution,
    resolve_distill_rule,
    resolve_elaborate_candidate,
    resolve_fit_issue,
)
from memcommit.store import (
    ConcurrentGroundUpdateError,
    MemoryStore,
    ground_session_record_digest,
)
from memcommit.summarize import collect_summary_scope
from memcommit.summarize_application import FrozenSummarySource


def _uid() -> str:
    return str(uuid.uuid4())


def _ground():
    description = Context(uid=_uid(), name="resolve/description")
    examples = Context(uid=_uid(), name="resolve/examples")
    output = Context(uid=_uid(), name="resolve/output")
    contexts = (description, examples, output)
    session = bind_ground_workbench(
        create_ground_session(
            "resolve-ground",
            goal="티커가 어떻게 만들어지는지 규칙을 알고 싶어",
        ),
        description="Resolve semantic proposals one reviewed action at a time.",
        raw_context=description,
        derived_context=examples,
        target_contexts=(output,),
        target_requirements=(
            GroundTargetSpec(
                context_name=output.name,
                description="Retain separately reviewed synthetic ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    session = propose_ground_rule(
        session,
        rule="Use one initial from each meaningful company-name token.",
        rationale="Start with one deliberately incomplete candidate Rule.",
        current_contexts=contexts,
    )
    rule = session.items_of_kind("RULE")[0]
    session = propose_ground_example(
        session,
        proposition=(
            'Applying the synthetic ticker Rules to "Redwood Inc." '
            'produces "RED".'
        ),
        rationale="A single-word boundary Example.",
        current_contexts=contexts,
        input_text="Redwood Inc.",
        expected_output="RED",
        case_role="BOUNDARY",
    )
    return session, contexts, rule, session.items_of_kind("CASE")[0]


def _elaborate_result(session, *, rule_content: str) -> GroundElaborateResult:
    analysis = ElaborateAnalysis(
        uid=_uid(),
        mode=ElaborateMode.GOAL_TO_RULES,
        inputs=(session.goal,),
        overview="One possible normalization direction.",
        rules=(
            ElaboratedRule(
                uid=_uid(),
                content=rule_content,
                rationale="This is a hypothesis generated from the vague Goal.",
            ),
        ),
    )
    frozen = FrozenGroundElaborate(
        ground_name=session.contract_name,
        ground_uid=session.uid,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        direction="GOAL_TO_RULES",
        request=ElaborateRequest(goal=session.goal),
    )
    return GroundElaborateResult(
        frozen=frozen,
        elaborate=ElaborateResult(analysis=analysis),
    )


def _distill_result(session, example, *, rule_content: str) -> GroundDistillResult:
    working = next(
        frame for frame in session.frames if frame.role == "WORKING_CANDIDATES"
    )
    projected = Context(uid=working.context_uid, name=working.context_name)
    projected.add(Memory(uid=example.uid, content=example.proposition))
    frame = collect_summary_scope(
        (projected,),
        root_context_uid=projected.uid,
        root_context_name=projected.name,
        include_descendants=False,
        follow_embeds=False,
    )
    analysis = DistillAnalysis(
        uid=_uid(),
        source=frame,
        goal=session.goal,
        overview="The boundary Example supports a single-word Rule.",
        rules=(
            DistilledRule(
                uid=_uid(),
                content=rule_content,
                rationale="The exact Example supplies the boundary.",
                support_memory_uids=(example.uid,),
                boundary_memory_uids=(),
            ),
        ),
        outside_memory_uids=(),
    )
    frozen = FrozenGroundDistill(
        ground_name=session.contract_name,
        ground_uid=session.uid,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        candidate_frame=working,
        request=DistillRequest(
            context_locator=working.context_name,
            goal=session.goal,
        ),
        source_kind="GROUND_EXAMPLES",
        example_frame=frame,
    )
    return GroundDistillResult(
        frozen=frozen,
        distill=DistillResult(
            analysis=analysis,
            frozen_source=FrozenSummarySource(
                frame=frame,
                token=frozen.ground_digest,
            ),
        ),
    )


def _fit_receipt(session, rule, example, *, status="UNDERDETERMINED"):
    report = FitReport(
        uid=_uid(),
        ground_uid=session.uid,
        ground_name=session.contract_name,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        rules=(FitRule(uid=rule.uid, alias="r1", statement=rule.content),),
        examples=(
            FitExample(
                uid=example.uid,
                alias="e1",
                statement=example.proposition,
                projection="PROPOSITION",
                rule_uids=(rule.uid,),
            ),
        ),
        judgments=(
            FitJudgment(
                example_uid=example.uid,
                status=status,
                rule_uids=(rule.uid,),
                reason="The Rule does not specify a single-word algorithm.",
            ),
        ),
        overview="One unresolved ticker boundary.",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return GroundFitReceipt(report=report, current=True)


def _persist_ground(store: MemoryStore):
    session, contexts, rule, example = _ground()
    for context in contexts:
        store.create_context(context)
    store.save_ground_session(session)
    return session, contexts, rule, example


def test_resolve_elaborate_keeps_candidate_unverified_and_nonmutating() -> None:
    session, _contexts, _rule, _example = _ground()
    result = _elaborate_result(
        session,
        rule_content="Remove legal-form suffixes before generating a ticker.",
    )

    plan = resolve_elaborate_candidate(
        session,
        result,
        candidate_uid=result.elaborate.analysis.rules[0].uid,
    )

    assert plan.source.verification == "UNVERIFIED"
    assert plan.candidate_verification == "UNVERIFIED"
    assert plan.action.kind == "PROPOSE_RULE"
    assert plan.action.content == result.elaborate.analysis.rules[0].content
    assert plan.action.rule_provenance == "DISTILLED_FROM_GOAL"
    assert session.revision == plan.source.identity.ground_revision


def test_resolve_distill_preserves_exact_evidence_bound_rule() -> None:
    session, _contexts, _rule, example = _ground()
    result = _distill_result(
        session,
        example,
        rule_content=(
            "For a normalized single-word name, use its first three alphabetic "
            "characters in uppercase."
        ),
    )

    plan = resolve_distill_rule(
        session,
        result,
        rule_uid=result.distill.analysis.rules[0].uid,
    )

    assert plan.source.verification == "EVIDENCE_BOUND"
    assert plan.candidate_verification == "EVIDENCE_BOUND"
    assert plan.action.content == result.distill.analysis.rules[0].content
    assert plan.action.source_item_uid == result.distill.analysis.rules[0].uid
    assert plan.action.rule_provenance == "INDUCED_FROM_CASES"


def test_resolve_rejects_semantic_artifact_after_ground_revision() -> None:
    session, contexts, _rule, _example = _ground()
    result = _elaborate_result(
        session,
        rule_content="Remove legal suffixes before ticker generation.",
    )
    changed = propose_ground_rule(
        session,
        rule="A concurrent Rule proposal.",
        rationale="Simulate another reviewed turn.",
        current_contexts=contexts,
    )

    with pytest.raises(GroundResolutionError, match="changed after"):
        resolve_elaborate_candidate(
            changed,
            result,
            candidate_uid=result.elaborate.analysis.rules[0].uid,
        )


def test_resolve_fit_refines_only_a_rule_cited_by_the_issue() -> None:
    session, _contexts, rule, example = _ground()
    receipt = _fit_receipt(session, rule, example)

    plan = resolve_fit_issue(
        session,
        receipt,
        choice=GroundFitResolutionChoice(
            example_uid=example.uid,
            action="REFINE_RULE",
            rule_uid=rule.uid,
            content=(
                "For a normalized single-word name, use its first three "
                "alphabetic characters in uppercase."
            ),
            rationale="The Redwood boundary requires a deterministic algorithm.",
        ),
    )

    assert plan.source.verification == "REVISION_BOUND_JUDGMENT"
    assert plan.candidate_verification == "UNVERIFIED"
    assert plan.action.kind == "REFINE_RULE"
    assert plan.action.selector == rule.uid
    assert plan.action.source_item_uid == example.uid


def test_resolve_fit_rejects_stale_or_already_fit_receipts() -> None:
    session, _contexts, rule, example = _ground()
    receipt = _fit_receipt(session, rule, example)
    choice = GroundFitResolutionChoice(
        example_uid=example.uid,
        action="DEFER",
    )

    with pytest.raises(GroundResolutionError, match="stale Fit receipt"):
        resolve_fit_issue(
            session,
            GroundFitReceipt(report=receipt.report, current=False),
            choice=choice,
        )

    with pytest.raises(GroundResolutionError, match="non-FIT"):
        resolve_fit_issue(
            session,
            _fit_receipt(session, rule, example, status="FIT"),
            choice=choice,
        )


def test_resolve_fit_defer_is_an_explicit_nonmutating_plan() -> None:
    session, _contexts, rule, example = _ground()
    before = ground_session_record_digest(session)

    plan = resolve_fit_issue(
        session,
        _fit_receipt(session, rule, example),
        choice=GroundFitResolutionChoice(
            example_uid=example.uid,
            action="DEFER",
            rationale="Wait for an approved policy instead of guessing.",
        ),
    )

    assert plan.action.kind == "DEFER"
    assert plan.candidate_verification == "REVISION_BOUND_JUDGMENT"
    assert ground_session_record_digest(session) == before


def test_apply_resolve_elaborate_creates_exactly_one_ground_revision(
    isolated_store,
) -> None:
    store = MemoryStore()
    session, _contexts, _rule, _example = _persist_ground(store)
    result = _elaborate_result(
        session,
        rule_content="Remove legal-form suffixes before generating a ticker.",
    )
    plan = resolve_elaborate_candidate(
        session,
        result,
        candidate_uid=result.elaborate.analysis.rules[0].uid,
    )

    receipt = apply_ground_resolution(store, plan, artifact=result)

    saved = store.load_ground_session(session.contract_name)
    assert saved is not None
    assert receipt.mutated is True
    assert receipt.previous_identity.ground_revision == session.revision
    assert receipt.resulting_identity.ground_revision == session.revision + 1
    assert saved.revision == session.revision + 1
    assert saved.items_of_kind("RULE")[-1].content == plan.action.content
    assert saved.items_of_kind("RULE")[-1].status == "PROPOSED"
    assert saved.items_of_kind("RULE")[-1].origin == "AGENT"


def test_apply_resolve_fit_refinement_stales_the_exact_source(
    isolated_store,
) -> None:
    store = MemoryStore()
    session, _contexts, rule, example = _persist_ground(store)
    artifact = _fit_receipt(session, rule, example)
    plan = resolve_fit_issue(
        session,
        artifact,
        choice=GroundFitResolutionChoice(
            example_uid=example.uid,
            action="REFINE_RULE",
            rule_uid=rule.uid,
            content=(
                "For a normalized single-word name, use its first three "
                "alphabetic characters in uppercase."
            ),
            rationale="The Redwood boundary requires a deterministic algorithm.",
        ),
    )

    receipt = apply_ground_resolution(store, plan, artifact=artifact)

    saved = store.load_ground_session(session.contract_name)
    assert saved is not None
    assert receipt.mutated is True
    assert saved.revision == session.revision + 1
    assert saved.items_of_kind("RULE")[0].content == plan.action.content
    with pytest.raises(GroundResolutionError, match="changed after"):
        apply_ground_resolution(store, plan, artifact=artifact)


def test_apply_resolve_defer_writes_nothing(isolated_store) -> None:
    store = MemoryStore()
    session, _contexts, rule, example = _persist_ground(store)
    artifact = _fit_receipt(session, rule, example)
    plan = resolve_fit_issue(
        session,
        artifact,
        choice=GroundFitResolutionChoice(
            example_uid=example.uid,
            action="DEFER",
            rationale="Wait for an explicit transliteration policy.",
        ),
    )

    receipt = apply_ground_resolution(store, plan, artifact=artifact)

    assert receipt.mutated is False
    assert receipt.previous_identity == receipt.resulting_identity
    assert store.load_ground_session(session.contract_name) == session


def test_apply_resolve_rejects_a_hand_built_action_change(isolated_store) -> None:
    store = MemoryStore()
    session, _contexts, _rule, _example = _persist_ground(store)
    result = _elaborate_result(
        session,
        rule_content="Remove legal-form suffixes before generating a ticker.",
    )
    plan = resolve_elaborate_candidate(
        session,
        result,
        candidate_uid=result.elaborate.analysis.rules[0].uid,
    )
    forged = replace(
        plan,
        action=replace(plan.action, content="A different uncited Rule."),
    )

    with pytest.raises(GroundResolutionError, match="does not exactly match"):
        apply_ground_resolution(store, forged, artifact=result)

    assert store.load_ground_session(session.contract_name) == session


def test_apply_resolve_rejects_a_changed_bound_context(isolated_store) -> None:
    store = MemoryStore()
    session, contexts, _rule, _example = _persist_ground(store)
    result = _elaborate_result(
        session,
        rule_content="Remove legal-form suffixes before generating a ticker.",
    )
    plan = resolve_elaborate_candidate(
        session,
        result,
        candidate_uid=result.elaborate.analysis.rules[0].uid,
    )
    changed = store.load_direct(contexts[1].name)
    changed.add(Memory(uid=_uid(), content="A concurrent Context change."))
    store.save(changed)

    with pytest.raises(ValueError, match="stale|changed|match"):
        apply_ground_resolution(store, plan, artifact=result)

    assert store.load_ground_session(session.contract_name) == session


def test_apply_resolve_store_cas_rejects_a_concurrent_ground_turn(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    session, contexts, _rule, _example = _persist_ground(store)
    result = _elaborate_result(
        session,
        rule_content="Remove legal-form suffixes before generating a ticker.",
    )
    plan = resolve_elaborate_candidate(
        session,
        result,
        candidate_uid=result.elaborate.analysis.rules[0].uid,
    )
    original_save = store.save_ground_session
    concurrent = propose_ground_rule(
        session,
        rule="A separately reviewed concurrent Rule.",
        rationale="Land another exact Ground action before Resolve CAS.",
        current_contexts=contexts,
    )

    def save_after_concurrent_turn(revised, **kwargs):
        original_save(
            concurrent,
            replace=True,
            expected_uid=session.uid,
            expected_revision=session.revision,
            expected_digest=ground_session_record_digest(session),
            verify_bound_frames=True,
        )
        original_save(revised, **kwargs)

    monkeypatch.setattr(store, "save_ground_session", save_after_concurrent_turn)

    with pytest.raises(ConcurrentGroundUpdateError, match="changed"):
        apply_ground_resolution(store, plan, artifact=result)

    saved = store.load_ground_session(session.contract_name)
    assert saved == concurrent
    assert all(item.content != plan.action.content for item in saved.items)
