"""Console projection for immutable applied-checkpoint Review evidence."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.capabilities.reviewing.report import (
    ReviewReportController,
)
from memcommit.application.operations.review.applied_checkpoint import (
    AppliedCheckpointReview,
)


def _line(value: object) -> str:
    return safe_terminal_text(str(value))


def _effect_lines(payload: dict[str, object]) -> list[str]:
    effects = payload.get("effects")
    if not isinstance(effects, list):
        return []
    lines: list[str] = []
    for index, effect in enumerate(effects, 1):
        if not isinstance(effect, dict):
            continue
        kind = effect.get("kind") or effect.get("action") or "EFFECT"
        uid = effect.get("memory_uid") or effect.get("uid") or ""
        lines.append(f"{index}. {_line(kind)} · [{_line(str(uid)[:8])}]")
        before = effect.get("before") or effect.get("old_content")
        after = effect.get("after") or effect.get("new_content")
        if before is not None:
            lines.append(f"   BEFORE · {_line(before)}")
        if after is not None:
            lines.append(f"   AFTER · {_line(after)}")
        reason = effect.get("reason") or effect.get("rationale")
        if reason:
            lines.append(f"   WHY · {_line(reason)}")
    return lines


def _distill_lines(payload: dict[str, object]) -> list[str]:
    lines = [
        f"SOURCE · {_line(payload.get('source_context') or payload.get('source_name') or '(unknown)')}",
        f"TARGET · {_line(payload.get('target_context') or '(unknown)')}",
    ]
    overview = payload.get("overview")
    if overview:
        lines.extend(("", "SOURCE OVERVIEW", _line(overview)))
    rules = payload.get("rules")
    if isinstance(rules, list):
        lines.extend(("", f"APPLIED RULES · {len(rules)}"))
        for index, rule in enumerate(rules, 1):
            if not isinstance(rule, dict):
                continue
            lines.append(f"{index}. {_line(rule.get('content', ''))}")
            lines.append(f"   WHY · {_line(rule.get('rationale', ''))}")
            support = rule.get("support_memory_uids")
            if isinstance(support, list):
                lines.append("   SUPPORT · " + ", ".join(_line(uid) for uid in support))
    return lines


def _makemore_lines(payload: dict[str, object]) -> list[str]:
    case_validation = payload.get("case_validation")
    quality_policy = payload.get("quality_policy")
    if quality_policy is None:
        quality_policy = "STRICT" if case_validation else "LEGACY"
    lines = [
        f"MODE · {_line(payload.get('mode', '(unknown)'))}",
        f"SOURCE · {_line(payload.get('source_context') or '(inline)')}",
        f"TARGET · {_line(payload.get('target_context') or '(unknown)')}",
        f"VERIFICATION · {_line(payload.get('verification', 'UNVERIFIED'))}",
        f"QUALITY · {_line(quality_policy)}",
        f"CASE VALIDATION · {_line(case_validation or '(legacy)')}",
    ]
    distillation = payload.get("distillation")
    if payload.get("source_mode") == "DISTILL_THEN_MAKEMORE" and isinstance(
        distillation,
        dict,
    ):
        lines.extend(("", "PIPELINE · DISTILL → MAKEMORE"))
        distill_overview = distillation.get("overview")
        if distill_overview:
            lines.extend(("DISTILL OVERVIEW", _line(distill_overview)))
        rules = distillation.get("rules")
        if isinstance(rules, list):
            lines.extend(("", f"TRANSIENT DISTILLED RULES · {len(rules)}"))
            for index, rule in enumerate(rules, 1):
                if not isinstance(rule, dict):
                    continue
                lines.append(f"{index}. {_line(rule.get('content', ''))}")
                lines.append(f"   WHY · {_line(rule.get('rationale', ''))}")
                support = rule.get("support_memory_uids")
                if isinstance(support, list):
                    lines.append(
                        "   SUPPORT · "
                        + (", ".join(_line(uid) for uid in support) or "NONE")
                    )
                boundary = rule.get("boundary_memory_uids")
                if isinstance(boundary, list) and boundary:
                    lines.append(
                        "   BOUNDARY · " + ", ".join(_line(uid) for uid in boundary)
                    )
    overview = payload.get("overview")
    if overview:
        lines.extend(("", "PROPOSAL OVERVIEW", _line(overview)))
    proposals = payload.get("proposals")
    if isinstance(proposals, list):
        lines.extend(("", f"APPLIED MEMORIES · {len(proposals)}"))
        for index, proposal in enumerate(proposals, 1):
            if not isinstance(proposal, dict):
                continue
            lines.append(f"{index}. {_line(proposal.get('content', ''))}")
            lines.append(f"   WHY · {_line(proposal.get('rationale', ''))}")
    return lines


def applied_checkpoint_review_controller(
    record: AppliedCheckpointReview,
) -> ReviewReportController:
    """Project one terminal checkpoint as a provider-free read-only Review."""

    payload = record.payload
    title = f"MEM REVIEW · {record.operation.upper()}"
    summary = (
        "Completed operation evidence. This Review is read-only and cannot "
        "change or apply the recorded result."
    )
    lines = [
        f"STATUS · APPLIED · RECEIPT {_line(record.checkpoint_uid)}",
        f"CONTEXT · {_line(record.context_name)}",
        f"COMPLETED · {_line(record.timestamp)}",
    ]
    if record.description:
        lines.append(f"OUTCOME · {_line(record.description)}")
    if record.operation == "distill":
        lines.extend(("", *_distill_lines(payload)))
    elif record.operation == "makemore":
        lines.extend(("", *_makemore_lines(payload)))
    else:
        lines.extend(("", *_effect_lines(payload)))
    return ReviewReportController.from_text(
        operation=record.operation,
        artifact_uid=record.checkpoint_uid,
        revision=record.revision,
        kind="READ_ONLY",
        title=title,
        summary=summary,
        report_text="\n".join(lines).rstrip(),
    )


__all__ = ["applied_checkpoint_review_controller"]
