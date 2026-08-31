"""Console projection for immutable applied-checkpoint Review evidence."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.theme import SemanticColorRole
from memcommit.application.capabilities.reviewing.report import (
    ReviewReportController,
    ReviewTextFragment,
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
        f"TARGET · {_line(payload.get('target_context') or '(unknown)')}",
        f"VERIFICATION · {_line(payload.get('verification', 'UNVERIFIED'))}",
        f"QUALITY · {_line(quality_policy)}",
        f"CASE VALIDATION · {_line(case_validation or '(legacy)')}",
    ]
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


def _dedun_fragments(payload: dict[str, object]) -> tuple[ReviewTextFragment, ...]:
    """Project typed cleanup tokens without reparsing rendered Review text."""

    fragments: list[ReviewTextFragment] = []

    def line(*parts: ReviewTextFragment) -> None:
        if fragments:
            fragments.append(ReviewTextFragment("\n"))
        fragments.extend(parts)

    components = payload.get("components")
    exact_item_groups = payload.get("exact_item_groups")
    component_count = len(components) if isinstance(components, list) else 0
    exact_count = len(exact_item_groups) if isinstance(exact_item_groups, list) else 0
    if component_count or exact_count:
        line(ReviewTextFragment(f"RESOLVED GROUPS · {component_count + exact_count}"))
    if isinstance(components, list):
        for index, component in enumerate(components, 1):
            if not isinstance(component, dict):
                continue
            survivor_uid = str(component.get("survivor_uid", ""))
            members = component.get("members")
            survivor: dict[str, object] | None = None
            if isinstance(members, list):
                survivor = next(
                    (
                        member
                        for member in members
                        if isinstance(member, dict)
                        and str(member.get("uid", "")) == survivor_uid
                    ),
                    None,
                )
                if survivor is None:
                    survivor = next(
                        (
                            member
                            for member in members
                            if isinstance(member, dict) and member.get("selected")
                        ),
                        None,
                    )
            survivor_content = (
                _line(survivor.get("content", "")) if survivor is not None else ""
            )
            survivor_suffix = f" {survivor_content}" if survivor_content else ""
            line(
                ReviewTextFragment(f"{index}. "),
                ReviewTextFragment("SURVIVOR", SemanticColorRole.ADD, bold=True),
                ReviewTextFragment(f" · [{_line(survivor_uid[:8])}]" + survivor_suffix),
            )
            if isinstance(members, list):
                for member in members:
                    if isinstance(member, dict) and member is not survivor:
                        line(
                            ReviewTextFragment("   "),
                            ReviewTextFragment(
                                "ABSORB", SemanticColorRole.REMOVE, bold=True
                            ),
                            ReviewTextFragment(
                                f" · [{_line(str(member.get('uid', ''))[:8])}] "
                                + _line(member.get("content", ""))
                            ),
                        )
            evidence = component.get("evidence")
            if isinstance(evidence, list):
                for item in evidence:
                    if isinstance(item, dict):
                        line(
                            ReviewTextFragment(
                                f"   EVIDENCE · {_line(item.get('relation', ''))} · "
                                f"{_line(item.get('reason', ''))}"
                            )
                        )
    if isinstance(exact_item_groups, list):
        for offset, group in enumerate(exact_item_groups, 1):
            if not isinstance(group, dict):
                continue
            index = component_count + offset
            survivor_uid = str(group.get("survivor_uid", ""))
            summary = _line(group.get("summary", ""))
            kind = _line(group.get("item_kind", ""))
            line(
                ReviewTextFragment(f"{index}. "),
                ReviewTextFragment("SURVIVOR", SemanticColorRole.ADD, bold=True),
                ReviewTextFragment(f" · [{_line(survivor_uid[:8])}] {kind} · {summary}"),
            )
            absorbed_uids = group.get("absorbed_uids")
            if isinstance(absorbed_uids, list):
                for uid in absorbed_uids:
                    line(
                        ReviewTextFragment("   "),
                        ReviewTextFragment(
                            "ABSORB", SemanticColorRole.REMOVE, bold=True
                        ),
                        ReviewTextFragment(
                            f" · [{_line(str(uid)[:8])}] {kind} · {summary}"
                        ),
                    )
    return tuple(fragments)


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
    report_fragments: tuple[ReviewTextFragment, ...] = ()
    if record.operation == "distill":
        lines.extend(("", *_distill_lines(payload)))
    elif record.operation == "makemore":
        lines.extend(("", *_makemore_lines(payload)))
    elif record.operation == "dedun":
        dedun_fragments = _dedun_fragments(payload)
        prefix = "\n".join(lines).rstrip()
        report_fragments = (
            ReviewTextFragment(prefix + ("\n\n" if dedun_fragments else "")),
            *dedun_fragments,
        )
    else:
        lines.extend(("", *_effect_lines(payload)))
    report_text = (
        "".join(fragment.text for fragment in report_fragments)
        if report_fragments
        else "\n".join(lines).rstrip()
    )
    return ReviewReportController.from_text(
        operation=record.operation,
        artifact_uid=record.checkpoint_uid,
        revision=record.revision,
        kind="READ_ONLY",
        title=title,
        summary=summary,
        report_text=report_text,
        report_fragments=report_fragments,
    )


__all__ = ["applied_checkpoint_review_controller"]
