"""Operation-owned normal-form planning for one Atomize publication.

The module deliberately owns no Store writes. It projects the reviewed
structural split, reuses Dedun's typed survivor policy on that unpublished
Context, and validates the affected final Memories before the outer Atomize
command is allowed to publish its sole checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from memcommit.application.operations.atomize.domain import (
    AtomizeAnalysisSession,
    AtomizeApplyResult,
    AtomizeImpactError,
    AtomizeNormalFormAudit,
    AtomizeProvider,
    apply_atomize_analysis,
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.core.context import Context, Memory
from memcommit.application.operations.dedun.application import (
    DedunRequest,
    DedunSelection,
    dedun_projection_record,
    project_dedun,
)
from memcommit.application.operations.dedun.planning import freeze_dedun_plan
from memcommit.application.capabilities.reviewing.quality.findings import DuplicateFinding, DuplicateReport, find_redundancies
from memcommit.application.capabilities.reviewing.quality.workbench import create_quality_find_workbench
from memcommit.application.capabilities.reviewing.quality.handoff import quality_finding_handoffs
from memcommit.application.operations.review.model import direct_context_digest
from memcommit.persistence.store import context_record_digest


@dataclass(frozen=True)
class AtomizeNormalFormProjection:
    """A fully validated, still-unpublished Atomize command effect."""

    context: Context
    result: AtomizeApplyResult

    @property
    def absorbed_uids(self) -> tuple[str, ...]:
        normal_form = self.result.normal_form
        assert normal_form is not None
        return tuple(
            absorbed for absorbed, _survivor in normal_form.absorbed_to_survivor
        )


def _relevant_findings(
    report: DuplicateReport,
    affected_uids: set[str],
) -> tuple[DuplicateFinding, ...]:
    return tuple(
        finding
        for finding in report.findings
        if finding.left.uid in affected_uids or finding.right.uid in affected_uids
    )


def _dedun_projection(
    projected: Context,
    *,
    affected_uids: set[str],
    provider_factory: Callable[[], AtomizeProvider],
) -> tuple[dict[str, object] | None, tuple[tuple[str, str], ...]]:
    report = find_redundancies(projected, provider_factory)
    findings = _relevant_findings(report, affected_uids)
    if not findings:
        return None, ()

    # The finder workbench is the canonical typed bridge into Dedun. Keeping
    # it here means Atomize composes the existing application contract rather
    # than restating what counts as executable redundancy evidence.
    relevant_report = DuplicateReport(
        memory_count=report.memory_count,
        findings=findings,
    )
    workbench = create_quality_find_workbench(
        "duplicates",
        projected,
        relevant_report,
    )
    request = DedunRequest(quality_finding_handoffs(workbench))
    memories = tuple(
        item for item in projected.iter_items() if isinstance(item, Memory)
    )
    plan = freeze_dedun_plan(
        request,
        memories,
        context_uid=projected.uid,
        context_name=projected.name,
        display_name=projected.name,
        context_digest=context_record_digest(projected),
        direct_memory_digest=direct_context_digest(projected),
    )
    selections = tuple(
        DedunSelection(
            component_uid=component.uid,
            # A focused Atomize must not replace an unchanged neighboring UID
            # with a newly generated child merely because the child appeared
            # first inside a filtered component.
            survivor_uid=next(
                (
                    member.uid
                    for member in component.members
                    if member.uid not in affected_uids
                ),
                component.recommended_survivor_uid,
            ),
        )
        for component in plan.components
    )
    projection = project_dedun(plan, selections)
    survivor_by_absorbed = tuple(
        (member.uid, selection.survivor_uid)
        for component, selection in zip(
            plan.components,
            projection.selections,
            strict=True,
        )
        for member in component.members
        if member.uid != selection.survivor_uid
    )
    for absorbed_uid in projection.absorbed_uids:
        projected.remove(absorbed_uid)
    return dedun_projection_record(plan, projection), survivor_by_absorbed


def _final_affected_uids(
    affected_uids: set[str],
    absorbed_to_survivor: tuple[tuple[str, str], ...],
) -> tuple[str, ...]:
    survivor_by_absorbed = dict(absorbed_to_survivor)
    final = {
        survivor_by_absorbed.get(uid, uid)
        for uid in affected_uids
    }
    return tuple(sorted(final))


def project_atomize_normal_form(
    context: Context,
    analysis: AtomizeAnalysisSession,
    provider_factory: Callable[[], AtomizeProvider],
) -> AtomizeNormalFormProjection:
    """Project semantic chunk + Dedun + verification without publishing state."""

    if not isinstance(context, Context) or not isinstance(
        analysis,
        AtomizeAnalysisSession,
    ):
        raise TypeError("Atomize normal-form planning requires typed inputs.")
    projected = Context.from_dict(context.to_dict())
    structural = apply_atomize_analysis(projected, analysis)
    affected_uids = {
        uid for item in structural.items for uid in item.result_uids
    }
    try:
        dedun_record, absorbed_to_survivor = _dedun_projection(
            projected,
            affected_uids=affected_uids,
            provider_factory=provider_factory,
        )
        final_uids = _final_affected_uids(
            affected_uids,
            absorbed_to_survivor,
        )
        validation_report = impact_atomize(
            projected,
            provider_factory,
            _memory_uids=final_uids,
            _normal_form_validation=True,
        )
        invalid = tuple(
            item
            for item in validation_report.items
            if item.classification not in {"ATOMIC", "NON_PROPOSITIONAL"}
        )
        if invalid:
            labels = ", ".join(
                f"{item.memory.uid[:8]}={item.classification}" for item in invalid
            )
            raise AtomizeImpactError(
                "Atomize final validation did not reach semantic chunk normal "
                f"form: {labels}. No Context change was published."
            )

        verification = find_redundancies(projected, provider_factory)
        remaining = _relevant_findings(verification, set(final_uids))
        if remaining:
            raise AtomizeImpactError(
                "Atomize final validation still found redundancy involving "
                "the affected result. No Context change was published."
            )
        validation_analysis = create_atomize_analysis(
            projected,
            validation_report,
        )
    except AtomizeImpactError:
        raise
    except (RuntimeError, TypeError, ValueError) as error:
        raise AtomizeImpactError(
            f"Atomize normal-form planning failed: {error}"
        ) from error

    normal_form = AtomizeNormalFormAudit(
        dedun=dedun_record,
        absorbed_to_survivor=absorbed_to_survivor,
        validation_analysis_uid=validation_analysis.uid,
        validation_context_digest=direct_context_digest(projected),
        validation_memory_uids=tuple(
            item.memory.uid for item in validation_report.items
        ),
        validation_classifications=tuple(
            item.classification for item in validation_report.items
        ),
        redundancy_finding_count=0,
    )
    return AtomizeNormalFormProjection(
        context=projected,
        result=replace(structural, normal_form=normal_form),
    )


__all__ = ["AtomizeNormalFormProjection", "project_atomize_normal_form"]
