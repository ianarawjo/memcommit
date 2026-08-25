from __future__ import annotations

from memcommit.interfaces.cli.resolve import render_resolve_receipt
from memcommit.operations.resolve.application import ResolveReceipt


def test_resolve_receipt_names_exact_checkpoint_review(capsys) -> None:
    checkpoint_uid = "2f7170f7-4754-423d-a7c2-36622a69f575"
    receipt = ResolveReceipt(
        context_uid="context-uid",
        context_name="practice/greetings",
        revision="revision-1",
        candidate_uid="candidate-uid",
        checkpoint_uid=checkpoint_uid,
        created_uids=(),
        updated_uids=("updated-uid",),
        deleted_uids=(),
    )

    render_resolve_receipt(receipt, fit_verdict="YES")

    assert capsys.readouterr().out == (
        "RESOLVE · practice/greetings\n"
        "APPLIED · UPDATE 1 · FIT YES\n"
        f"CHECKPOINT · {checkpoint_uid}\n"
        "REVIEW · mem review resolve --receipt "
        f"{checkpoint_uid}\n"
        "RECOVERY · mem undo\n"
    )
