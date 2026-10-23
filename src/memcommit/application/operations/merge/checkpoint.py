"""One Merge history contract for exact and semantic Resolve results."""

from dataclasses import asdict

from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest

from .lineage import project_merge_lineage
from .receipt import merge_receipt_summary
from .records import LiteralMergeRound

MERGE_CHECKPOINT_VERSION = 4


def item_effects(before, after):
    """Retain exact item records, including metadata and non-Memory changes."""
    return [
        dict(
            kind="ADD"
            if uid not in before["memories"]
            else "REMOVE"
            if uid not in after["memories"]
            else "EDIT",
            item_uid=uid,
            before=before["memories"].get(uid),
            after=after["memories"].get(uid),
        )
        for uid in dict.fromkeys((*before["order"], *after["order"]))
        if before["memories"].get(uid) != after["memories"].get(uid)
    ]


def merge_checkpoint(prepared, result, post_target):
    inputs = prepared.inputs

    def endpoint(context, access):
        return dict(
            context_uid=context.uid,
            context_name=access.context_name,
            access_name=access.access_name,
        )

    rounds = [
        dict(
            **round.to_dict(),
            revision=round.decisions.revision,
            phase="LITERAL" if isinstance(round, LiteralMergeRound) else "RESOLVE",
        )
        for round in result.rounds
    ]
    source, target = inputs.source(), inputs.target()
    record = dict(
        schema_version=MERGE_CHECKPOINT_VERSION,
        operation_uid=inputs.operation_uid,
        method=prepared.request.method,
        review_digest=digest({"prepared": prepared.digest, "result": result.digest}),
        inputs=dict(
            source=endpoint(source, inputs.source_access),
            target=endpoint(target, inputs.target_access),
        ),
        effects=item_effects(target.to_dict(), post_target.to_dict()),
        review_rounds=rounds,
        post_audit=result.post_audit.to_dict() if result.post_audit else None,
        unresolved_audit_keys=list(result.forced_audit_keys),
        summary=asdict(merge_receipt_summary(prepared, result)),
    )
    record["lineage"] = dict(
        local=True,
        edges=project_merge_lineage(result.rounds, source.uid, target.uid),
    )
    return AutoCheckpointRequest(
        command="merge",
        command_details={"merge": record},
    )


def merge_review_round_from_dict(value):
    """Decode each phase with its owner rather than fabricating structural Audits."""
    if value.get("phase") == "LITERAL":
        return LiteralMergeRound.from_dict(value)
    if value.get("phase") == "RESOLVE":
        from memcommit.application.operations.resolve.review_round.review_round_record import (
            ReviewRoundRecord,
        )

        return ReviewRoundRecord.from_dict(
            {k: v for k, v in value.items() if k != "phase"}
        )
    raise ValueError("Unknown Merge review phase.")
