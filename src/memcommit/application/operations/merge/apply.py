"""Validate reviewed Merge results and publish their exact Target and checkpoint."""

from memcommit.models.context import Context

from .inputs import PreparedMerge
from .receipt import MergeReceipt, merge_receipt_summary
from .result import MergeResult


def validate_merge_result(prepared: PreparedMerge, result: MergeResult) -> None:
    """Validate phase bindings and destination authority without recalculation."""
    if not isinstance(prepared, PreparedMerge):
        raise TypeError("Merge requires its prepared inputs.")
    if not isinstance(result, MergeResult):
        raise ValueError("Merge requires a composed, verified Merge result.")
    result.validate(prepared)


def apply_merge(prepared: PreparedMerge, result: MergeResult) -> MergeReceipt:
    """Save the exact reviewed Target; the Store rejects repeated operation IDs."""
    validate_merge_result(prepared, result)
    inputs = prepared.inputs
    source_access, target_access = inputs.source_access, inputs.target_access
    target_store = target_access.store
    source = source_access.store.load_direct(source_access.context_name)
    if (
        source.uid != inputs.source().uid
    ):
        raise ValueError("The Merge Source changed after review.")
    target = target_store.load_direct(target_access.context_name)
    if (
        target.uid != inputs.target().uid
    ):
        raise ValueError("The Merge Target changed after review.")
    target.name = target_access.access_name
    if target.to_dict() != inputs.target().to_dict():
        raise ValueError("Merge Preview no longer matches the frozen Target baseline.")

    # Resolve may use a temporary Context identity. Only that envelope changes;
    # every item value, identity and position is exactly the reviewed result.
    record = result.post_image.to_dict()
    record.update(uid=target.uid, name=target_access.context_name)
    post_target = Context.from_dict(record)
    bindings = (
        (
            source_access.context_name,
            source.uid,
        ),
    )
    from .checkpoint import merge_checkpoint

    saved = target_store.save_merge_target(
        post_target,
        merge_checkpoint(prepared, result, post_target),
        source_bindings=bindings,
    )
    if saved is None:
        raise RuntimeError("Merge Apply produced no checkpoint.")
    return MergeReceipt(
        inputs.operation_uid,
        target.uid,
        saved.uid,
        merge_receipt_summary(prepared, result),
    )
