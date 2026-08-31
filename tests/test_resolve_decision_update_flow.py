from __future__ import annotations

import copy
import json

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.commands.resolve.workbench.screen import run_resolve_tui
from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.application.operations.audit.application import create_quality_audit
from memcommit.application.operations.audit.model import (
    QUALITY_AUDIT_RULESETS,
    QualityAuditCheck,
    QualityAuditProvenance,
    QualityAuditSession,
)
from memcommit.application.operations.check_conformance.model import (
    ConformanceReport,
    ConformanceRule,
    ConformanceSubject,
    ContextConformanceJudgment,
    ContextNonconformingCase,
)
from memcommit.application.operations.resolve.application import (
    FrozenResolveFrame,
    ResolveAnalysis,
    ResolveError,
    ResolveFrameMemory,
    ResolveIssue,
    ResolveReceipt,
    ResolveRequest,
)
from memcommit.application.operations.resolve.decisions import (
    ResolveDecision,
    ResolveFinalizedInput,
    apply_resolve_update,
    build_resolution_source,
    finalize_resolve_decisions,
    plan_resolve_update,
)
from memcommit.application.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.application.operations.resolve.semantic import (
    RESOLVE_OPERATION,
    ProviderResolveSemanticPort,
)
from memcommit.application.operations.update.model import UpdatePlan
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore
from memcommit.providers.types import ProviderIdentity


CONTEXT_UID = "00000000-0000-4000-8000-000000000001"
LEFT_UID = "00000000-0000-4000-8000-000000000002"
RIGHT_UID = "00000000-0000-4000-8000-000000000003"
THIRD_UID = "00000000-0000-4000-8000-000000000004"
RULE_UID = "00000000-0000-4000-8000-000000000005"


def _context(*, third: bool = False) -> Context:
    value = Context(CONTEXT_UID, "notes")
    value.add(Memory(LEFT_UID, "Always use a period."))
    value.add(Memory(RIGHT_UID, "Named greetings may omit punctuation."))
    if third:
        value.add(Memory(THIRD_UID, "Use commas."))
    return value


def _frame(*, third: bool = False) -> FrozenResolveFrame:
    context = _context(third=third)
    memories = tuple(
        ResolveFrameMemory(f"m{index}", item.uid, item.content)
        for index, item in enumerate(context.memories.values(), 1)
    )
    return FrozenResolveFrame(
        request=ResolveRequest("notes"),
        context_uid=CONTEXT_UID,
        context_name="notes",
        display_name="notes",
        context_digest="0" * 64,
        revision="1" * 64,
        memories=memories,
        actionable_uids=(LEFT_UID, RIGHT_UID),
        allowed_effects=("CREATE", "UPDATE"),
        denied_effects=(),
    )


def _checks(
    context: Context,
    *,
    duplicate_pair: tuple[str, str] | None = None,
    ambiguity_uid: str | None = None,
    conflict_pair: tuple[str, str] | None = None,
) -> tuple[QualityAuditCheck, ...]:
    memories = context.memories
    duplicate_findings = (
        ()
        if duplicate_pair is None
        else (
            DuplicateFinding(
                memories[duplicate_pair[0]],
                memories[duplicate_pair[1]],
                "SEMANTIC_EQUIVALENT",
                "The pair stores the same practical instruction.",
            ),
        )
    )
    ambiguity_findings = (
        ()
        if ambiguity_uid is None
        else (
            AmbiguityFinding(
                memories[ambiguity_uid],
                "COMPETING",
                "REQUIRED",
                ("All greetings.", "Named greetings only."),
                "The scope has two operational readings.",
                "Which greetings are in scope?",
            ),
        )
    )
    conflict_findings = (
        ()
        if conflict_pair is None
        else (
            ConflictFinding(
                memories[conflict_pair[0]],
                memories[conflict_pair[1]],
                "YES",
                "The punctuation instructions cannot both govern the same case.",
                "Which instruction governs named greetings?",
            ),
        )
    )
    def provenance(operation):
        return QualityAuditProvenance(operation, False)
    return (
        QualityAuditCheck(
            "duplicates",
            QUALITY_AUDIT_RULESETS["duplicates"],
            DuplicateReport(len(memories), duplicate_findings),
            provenance("find_duplicates"),
        ),
        QualityAuditCheck(
            "ambiguities",
            QUALITY_AUDIT_RULESETS["ambiguities"],
            AmbiguityReport(len(memories), ambiguity_findings),
            provenance("find_ambiguities"),
        ),
        QualityAuditCheck(
            "conflicts",
            QUALITY_AUDIT_RULESETS["conflicts"],
            ConflictReport(
                len(memories),
                len(memories) * (len(memories) - 1) // 2,
                conflict_findings,
            ),
            provenance("find_conflicts"),
        ),
    )


def _audit(
    context: Context | None = None,
    *,
    duplicate_pair: tuple[str, str] | None = None,
    ambiguity_uid: str | None = None,
    conflict_pair: tuple[str, str] | None = (LEFT_UID, RIGHT_UID),
    conformance: bool = False,
) -> QualityAuditSession:
    target = context or _context()
    conformance_report = None
    if conformance:
        rule = ConformanceRule(RULE_UID, "r1", "Every instruction is explicit.")
        subjects = tuple(
            ConformanceSubject(
                memory.uid,
                f"m{index}",
                memory.content,
                linked_rule_uids=(RULE_UID,),
            )
            for index, memory in enumerate(target.memories.values(), 1)
        )
        conformance_report = ConformanceReport(
            uid="00000000-0000-4000-8000-000000000006",
            source_label=target.name,
            rules_label="rules",
            rules=(rule,),
            subjects=subjects,
            overview="One example violates the Rule.",
            context_judgments=(
                ContextConformanceJudgment(
                    RULE_UID,
                    "PARTIALLY_CONFORMS",
                    tuple(subject.uid for subject in subjects),
                    "One instruction leaves its scope implicit.",
                    (
                        ContextNonconformingCase(
                            LEFT_UID,
                            "The instruction omits its greeting scope.",
                        ),
                    ),
                ),
            ),
            provider_identity=ProviderIdentity("test", "audit"),
        )
    return create_quality_audit(
        target,
        _checks(
            target,
            duplicate_pair=duplicate_pair,
            ambiguity_uid=ambiguity_uid,
            conflict_pair=conflict_pair,
        ),
        conformance=conformance_report,
    )


def _issue(audit: QualityAuditSession, uid: str = "audit-item-one") -> ResolveIssue:
    return ResolveIssue(
        uid=uid,
        audit_key=f"CONFLICT:{LEFT_UID}:{RIGHT_UID}",
        audit_snapshot_digest=audit.snapshot_digest,
        kind="CONFLICT",
        classification="YES",
        memory_uids=(LEFT_UID, RIGHT_UID),
        proposed_direction="Named greetings remain exceptions.",
        reason="The punctuation rule does not state whether greetings are in scope.",
        question="Which instruction governs named greetings?",
    )


def _analysis(*issues: ResolveIssue) -> ResolveAnalysis:
    audit = _audit()
    values = issues or (_issue(audit),)
    if issues:
        values = tuple(
            ResolveIssue(
                uid=item.uid,
                audit_key=item.audit_key,
                audit_snapshot_digest=audit.snapshot_digest,
                kind=item.kind,
                classification=item.classification,
                memory_uids=item.memory_uids,
                proposed_direction=item.proposed_direction,
                reason=item.reason,
                question=item.question,
            )
            for item in issues
        )
    return ResolveAnalysis(
        frame=_frame(),
        status="NEEDS_INPUT",
        audit=audit,
        question="Finalize one decision for every Audit item.",
        issues=values,
    )


class _FramePort:
    def __init__(self, *, third: bool = False) -> None:
        self.target = _context(third=third)
        self.applied = None
        self.revalidations = 0

    def revalidate(self, frame) -> None:
        assert frame.revision == "1" * 64
        self.revalidations += 1

    def load_target(self, frame) -> Context:
        assert frame.context_uid == self.target.uid
        return copy.deepcopy(self.target)

    def apply_update_plan(
        self,
        frame,
        plan,
        *,
        unresolved_issue_uids=(),
        finalized_inputs=(),
    ):
        self.applied = plan
        self.finalized_inputs = finalized_inputs
        return ResolveReceipt(
            context_uid=frame.context_uid,
            context_name=frame.display_name,
            revision=frame.revision,
            plan_uid=plan.uid,
            checkpoint_uid="checkpoint",
            created_uids=(),
            updated_uids=tuple(operation.memory_uid for operation in plan.operations),
            deleted_uids=(),
            unresolved_issue_uids=unresolved_issue_uids,
        )


class _UpdateProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "update planning"
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target = next(
            value
            for value in payload["target"]["memories"]
            if value["content"] == "Always use a period."
        )
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": target["target_id"],
                        "new_content": (
                            "Use a period except that named greetings may omit "
                            "punctuation."
                        ),
                        "source_ids": [source_id],
                        "reason": "The accepted direction states the exception.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


def test_resolve_derives_exact_directions_for_all_four_audit_sections():
    audit = _audit(
        duplicate_pair=(LEFT_UID, RIGHT_UID),
        ambiguity_uid=LEFT_UID,
        conflict_pair=(LEFT_UID, RIGHT_UID),
        conformance=True,
    )

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == RESOLVE_OPERATION
            assert "do not repeat" in prompt
            assert "Do not propose exact edits, additions, removals" in prompt
            payload = json.loads(prompt.split("RESOLVE AUDIT PAYLOAD:\n", 1)[1])
            items = payload["audit"]["items"]
            assert {item["kind"] for item in items} == {
                "REDUNDANCY",
                "AMBIGUITY",
                "CONFLICT",
                "CONFORMANCE",
            }
            return json.dumps(
                {
                    "directions": [
                        {
                            "item_id": item["item_id"],
                            "direction": f"Conservatively handle {item['kind']}.",
                        }
                        for item in items
                    ]
                }
            )

    analysis = ProviderResolveSemanticPort().analyze(
        _frame(),
        audit,
        provider=Provider(),
    )

    assert analysis.audit is audit
    assert [issue.kind for issue in analysis.review_issues] == [
        "REDUNDANCY",
        "AMBIGUITY",
        "CONFLICT",
        "CONFORMANCE",
    ]
    assert all(issue.proposed_direction for issue in analysis.review_issues)


def test_finalized_decisions_become_one_process_local_update_source():
    analysis = _analysis()
    decisions = finalize_resolve_decisions(
        analysis,
        (ResolveDecision("audit-item-one", "CONFIRM"),),
    )

    source = build_resolution_source(analysis, decisions)

    assert source.uid != analysis.frame.context_uid
    contents = [memory.content for memory in source.iter_items()]
    assert len(contents) == 1
    assert "Named greetings remain exceptions." in contents[0]
    assert "complete target Context" in contents[0]


def test_update_plans_once_and_audits_detached_post_image(monkeypatch):
    analysis = _analysis()
    port = _FramePort()
    captured: dict[str, Context] = {}

    def clean_post_audit(context, provider_factory, *, conformance_rules=None):
        captured["context"] = copy.deepcopy(context)
        return _audit(context, conflict_pair=None)

    monkeypatch.setattr(
        "memcommit.application.operations.resolve.decisions.run_quality_audit",
        clean_post_audit,
    )
    proposal = plan_resolve_update(
        analysis,
        (ResolveDecision("audit-item-one", "CONFIRM"),),
        frame_port=port,
        update_provider_factory=_UpdateProvider,
        audit_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("post Audit is stubbed")
        ),
    )

    assert proposal.ready_to_apply
    assert len(proposal.plan.operations) == 1
    assert port.target.memories[LEFT_UID].content == "Always use a period."
    assert captured["context"].memories[LEFT_UID].content.startswith(
        "Use a period except"
    )
    assert proposal.blocking_audit_keys == ()
    assert port.revalidations == 2

    receipt = apply_resolve_update(proposal, frame_port=port)
    assert port.applied is proposal.plan
    assert receipt.updated_uids == (LEFT_UID,)
    assert port.finalized_inputs[0].content == "Named greetings remain exceptions."


def test_force_is_control_and_never_enters_update_source():
    analysis = _analysis()
    decisions = finalize_resolve_decisions(
        analysis,
        (ResolveDecision("audit-item-one", "FORCE"),),
    )

    assert tuple(build_resolution_source(analysis, decisions).iter_items()) == ()
    assert decisions.forced_issue_uids == ("audit-item-one",)


def test_force_allows_only_the_same_audit_item(monkeypatch):
    analysis = _analysis()
    port = _FramePort()
    monkeypatch.setattr(
        "memcommit.application.operations.resolve.decisions.run_quality_audit",
        lambda context, provider_factory, **kwargs: _audit(context),
    )

    proposal = plan_resolve_update(
        analysis,
        (ResolveDecision("audit-item-one", "FORCE"),),
        frame_port=port,
        update_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("FORCE must not start Update planning")
        ),
        audit_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("post Audit is stubbed")
        ),
    )

    assert proposal.ready_to_apply
    assert proposal.plan.operations == ()
    assert proposal.unresolved_issue_uids == ("audit-item-one",)


def test_new_post_audit_issue_blocks_apply(monkeypatch):
    source_audit = _audit(_context(third=True))
    issue = _issue(source_audit)
    analysis = ResolveAnalysis(
        frame=_frame(third=True),
        status="NEEDS_INPUT",
        audit=source_audit,
        issues=(issue,),
    )
    port = _FramePort(third=True)
    monkeypatch.setattr(
        "memcommit.application.operations.resolve.decisions.run_quality_audit",
        lambda context, provider_factory, **kwargs: _audit(
            context,
            conflict_pair=(RIGHT_UID, THIRD_UID),
        ),
    )

    proposal = plan_resolve_update(
        analysis,
        (ResolveDecision("audit-item-one", "FORCE"),),
        frame_port=port,
        update_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("FORCE must not start Update planning")
        ),
        audit_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("post Audit is stubbed")
        ),
    )

    assert not proposal.ready_to_apply
    assert len(proposal.blocking_audit_keys) == 1
    assert proposal.unresolved_issue_uids == ()
    with pytest.raises(ResolveError, match="unforced Audit issue"):
        apply_resolve_update(proposal, frame_port=port)


def test_force_only_apply_retains_an_unresolved_checkpoint(isolated_store):
    store = MemoryStore()
    store.save(_context())
    port = MemoryStoreResolvePort(store, current_name="notes")
    frame = port.freeze(ResolveRequest("notes"))
    plan = UpdatePlan("force-plan", frame.context_uid, frame.context_name, ())

    receipt = port.apply_update_plan(
        frame,
        plan,
        unresolved_issue_uids=("audit-item-one",),
        finalized_inputs=(ResolveFinalizedInput("audit-item-one", "FORCE", ""),),
    )

    assert receipt.unresolved_issue_uids == ("audit-item-one",)
    checkpoint = store.list_checkpoints("notes")[-1]
    assert checkpoint["args"]["unresolved_issue_uids"] == ["audit-item-one"]


def test_resolve_tui_collects_accept_then_finalizes():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r\x1b[B\x1b[B\x1b[B\r")
        decisions = run_resolve_tui(
            _analysis(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert decisions == (ResolveDecision("audit-item-one", "CONFIRM"),)


def test_resolve_tui_enter_on_two_edits_without_adding_a_focus_row():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[B\r"
            "Named greetings never require punctuation.\r"
            "\x1b[B\r\x1b[B\r"
        )
        decisions = run_resolve_tui(
            _analysis(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    # After editing, one Down reaches option 3 rather than a separate input row.
    assert decisions == (ResolveDecision("audit-item-one", "FORCE"),)


def test_resolve_tui_freezes_intent_draft_when_accept_is_selected():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[B\r"
            "Named greetings never require punctuation.\r"
            "\x1b[A\r"
            "\x1b[B\x1b[B\x1b[B\r"
        )
        decisions = run_resolve_tui(
            _analysis(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert decisions == (ResolveDecision("audit-item-one", "CONFIRM"),)


def test_resolve_tui_does_not_count_blank_intent_as_ready():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[B\r"
            "\r"
            "\x1b[B\x1b[B\r"
            "\x1b[A\x1b[A\r"
            "Named greetings never require punctuation.\r"
            "\x1b[B\x1b[B\r"
        )
        decisions = run_resolve_tui(
            _analysis(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert decisions == (
        ResolveDecision(
            "audit-item-one",
            "INTENT",
            "Named greetings never require punctuation.",
        ),
    )


def test_resolve_tui_prev_next_rows_navigate_multiple_audit_items():
    first_analysis = _analysis()
    second = ResolveIssue(
        uid="audit-item-two",
        audit_key=f"AMBIGUITY:{LEFT_UID}",
        audit_snapshot_digest=first_analysis.audit.snapshot_digest,
        kind="AMBIGUITY",
        classification="COMPETING · REQUIRED",
        memory_uids=(LEFT_UID,),
        proposed_direction="The exception applies only to named greetings.",
        reason="The note does not establish which greeting class is in scope.",
        question="Which greetings are in scope?",
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\r"
            "\x1b[B\x1b[B\x1b[B\x1b[B\r"
            "\x1b[B\x1b[B\r"
            "\x1b[B\x1b[B\x1b[B\r"
        )
        decisions = run_resolve_tui(
            _analysis(first_analysis.review_issues[0], second),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert decisions == (
        ResolveDecision("audit-item-one", "CONFIRM"),
        ResolveDecision("audit-item-two", "FORCE"),
    )
