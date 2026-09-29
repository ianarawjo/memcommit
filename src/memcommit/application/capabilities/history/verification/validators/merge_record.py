"""Validate the common Merge record against retained snapshots and decisions."""

from uuid import UUID

from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.operations.merge.analysis.candidate import (
    encode,
)
from memcommit.application.operations.merge.checkpoint import (
    MERGE_CHECKPOINT_VERSION,
    item_effects,
    merge_review_round_from_dict,
)
from memcommit.application.operations.merge.lineage import project_merge_lineage
from memcommit.application.operations.merge.records import LiteralMergeRound
from memcommit.application.operations.resolve.issues import all_audit_issue_keys
from memcommit.persistence.store import context_record_digest


def validated_merge_record(entry):
    record = entry["args"]["merge"]
    if (
        entry.get("command") != "merge"
        or entry.get("auto") is not True
        or record["schema_version"] != MERGE_CHECKPOINT_VERSION
        or record["method"] not in {"LITERAL", "SEMANTIC"}
        or str(UUID(record["operation_uid"])) != record["operation_uid"]
    ):
        raise ValueError("Invalid Merge record identity.")
    before, after = entry["command_before"], entry["snapshot"]
    source, target = record["inputs"]["source"], record["inputs"]["target"]
    if (
        not isinstance(record["review_digest"], str)
        or len(record["review_digest"]) != 64
        or any(c not in "0123456789abcdef" for c in record["review_digest"])
    ):
        raise ValueError("Invalid Merge review digest.")
    if (
        before["uid"] != target["context_uid"]
        or after["uid"] != before["uid"]
        or before["name"] != target["context_name"]
        or after["name"] != before["name"]
        or context_record_digest(before) != target["context_digest"]
        or item_effects(before, after) != record["effects"]
    ):
        raise ValueError("Merge effects do not match the Target snapshots.")
    rounds = record["review_rounds"]
    if not rounds:
        raise ValueError("Merge requires retained review evidence.")
    decoded_rounds = tuple(merge_review_round_from_dict(round) for round in rounds)
    if not isinstance(decoded_rounds[0], LiteralMergeRound) or any(
        isinstance(round, LiteralMergeRound) for round in decoded_rounds[1:]
    ):
        raise ValueError("Merge must begin with exactly one structural round.")
    candidate = decoded_rounds[0].candidate
    if len(candidate.frame_order) != 2:
        raise ValueError("Merge requires two input frames.")
    for frame, endpoint in zip(candidate.frame_order, (target, source), strict=True):
        if any(
            origin.context_uid != endpoint["context_uid"]
            or origin.context_name != endpoint["access_name"]
            for origin in candidate.origins
            if origin.frame == frame
        ):
            raise ValueError("Merge origins do not match the declared endpoints.")
    baseline = {
        origin.item_uid: origin.record()
        for origin in candidate.origins
        if origin.frame == candidate.frame_order[0]
    }
    if baseline != before["memories"] or list(baseline) != before["order"]:
        raise ValueError("Merge review belongs to another Target baseline.")
    previous = None
    for round, decoded in zip(rounds, decoded_rounds, strict=True):
        source_context = (
            decoded.candidate.context()
            if isinstance(decoded, LiteralMergeRound)
            else decoded.audit.source.context()
        )
        if source_context.to_dict() != round["before"]:
            raise ValueError("Merge review Audit belongs to another input.")
        if previous is not None and previous != round["before"]:
            raise ValueError("Merge review rounds are not consecutive.")
        issues = {issue["uid"]: issue for issue in round["issues"]}
        decisions = decoded.decisions.decisions
        decision_uids = {decision.issue_uid for decision in decisions}
        # Structural Merge remains exhaustive. Semantic rounds retain all shown
        # issues but may submit a subset, then re-Audit the resulting Context.
        if (
            len(decision_uids) != len(decisions)
            or not decision_uids <= set(issues)
            or (issues and not decisions)
            or (isinstance(decoded, LiteralMergeRound) and decision_uids != set(issues))
        ):
            raise ValueError("Merge choices do not match the reviewed issues.")
        mapping = dict(round["input_result_uids"] or ())
        for decision in decisions:
            issue = issues[decision.issue_uid]
            allowed = (
                {choice["uid"] for choice in issue["choices"]}
                if issue["choices"]
                else {"CONFIRM", "INTENT", "FORCE", "KEEP_BOTH", "KEEP_AS_IS"}
            )
            if decision.kind not in allowed:
                raise ValueError("Merge choice was not available for this issue.")
            if decision.kind in {"KEEP_BOTH", "KEEP_AS_IS"}:
                # Exact retention must include both bodies and distinct occurrences.
                destinations = [mapping.get(uid, uid) for uid in issue["item_uids"]]
                if len(set(destinations)) != len(destinations):
                    raise ValueError("Keep Both collapsed separate occurrences.")
                for uid, dest in zip(issue["item_uids"], destinations, strict=True):
                    old = round["before"]["memories"][uid]
                    if round["after"]["memories"].get(dest) != dict(old, uid=dest):
                        raise ValueError("Keep Both did not retain both originals.")
        previous = round["after"]
    if previous["memories"] != after["memories"] or previous["order"] != after["order"]:
        raise ValueError("Merge saved a different result than the final review.")
    if record["post_audit"] is not None:
        audit = QualityAuditSession.from_dict(record["post_audit"])
        if audit.source.context().to_dict() != previous:
            raise ValueError("Merge final Audit belongs to another result.")
        if not set(record["unresolved_audit_keys"]) <= set(all_audit_issue_keys(audit)):
            raise ValueError(
                "Merge unresolved issues are not present in the final Audit."
            )
    elif record["method"] != "LITERAL" or record["unresolved_audit_keys"]:
        raise ValueError("Semantic Merge requires a final Audit.")
    expected_summary = dict(
        method="LITERAL" if record["method"] == "LITERAL" else "SEMANTIC + LITERAL",
        sources=[
            (
                source["access_name"],
                sum(
                    origin.record()["type"] == "memory"
                    for origin in candidate.origins
                    if origin.frame == candidate.frame_order[1]
                ),
            )
        ],
        targets=[
            (
                target["access_name"],
                sum(item["type"] == "memory" for item in before["memories"].values()),
                sum(item["type"] == "memory" for item in after["memories"].values()),
            )
        ],
        decisions_applied=sum(
            decision["kind"] != "FORCE"
            for round in rounds
            for decision in round["decisions"]
        ),
        issues_left_unresolved=len(record["unresolved_audit_keys"]),
    )
    if encode(record["summary"]) != encode(expected_summary):
        raise ValueError("Merge summary does not match the retained result.")
    local = not record["inputs"]["cross_profile_memory_only"] and not any(
        endpoint["grant"] is not None for endpoint in (source, target)
    )
    if record["lineage"]["local"] != local or record["lineage"]["edges"] != (
        project_merge_lineage(
            decoded_rounds, source["context_uid"], target["context_uid"]
        )
        if local
        else []
    ):
        raise ValueError("Merge lineage is not supported by the reviewed choices.")
    return record


def merge_change_evidence(entry):
    try:
        record = validated_merge_record(entry)
        details = {
            effect["item_uid"]: dict(
                operation_uid=record["operation_uid"],
                change_set_digest=record["review_digest"],
                reason="Verified Merge review",
            )
            for effect in record["effects"]
            if any(
                value is not None and value["type"] == "memory"
                for value in (effect["before"], effect["after"])
            )
        }
        return details, None
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, StopIteration):
        return {}, "has invalid Merge review evidence"
