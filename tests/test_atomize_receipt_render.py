from __future__ import annotations

from types import SimpleNamespace

from memcommit.adapters.console.commands.atomize.receipt import render_atomize_apply_result
from memcommit.application.operations.atomize.application import (
    AtomizeApplicationAudit,
)


_EMPTY_AUDIT = AtomizeApplicationAudit(
    application_mode="REVIEWED",
    unresolved_at_apply=(),
    workbench_uid=None,
    workbench_response_digest=None,
)


def _split(index: int) -> tuple[SimpleNamespace, SimpleNamespace]:
    source_uid = f"source-{index:04d}"
    source = SimpleNamespace(
        memory_uid=source_uid,
        content=f"Source {index}, first claim.\nSource {index}, second claim.",
    )
    applied = SimpleNamespace(
        source_uid=source_uid,
        classification="COMPOSITE",
        result_uids=(f"child-{index:04d}-a", f"child-{index:04d}-b"),
        result_contents=(f"Child {index} A.", f"Child {index} B."),
    )
    return source, applied


def test_atomize_receipt_shows_exact_split_effects(capsys) -> None:
    source, applied = _split(1)
    session = SimpleNamespace(uid="analysis-uid", items=(source,))
    result = SimpleNamespace(
        split_count=1,
        child_count=2,
        preserved_count=7,
        items=(applied,),
    )

    render_atomize_apply_result(
        session=session,
        context_name="practice/greetings",
        result=result,
        checkpoint_uid="checkpoint-uid",
        created=False,
        audit=_EMPTY_AUDIT,
    )

    assert capsys.readouterr().out == (
        "ATOMIZE APPLIED · practice/greetings\n"
        "EFFECTS · SPLIT 1 · CHILDREN 2 · KEEP 7\n"
        "\n"
        "SPLIT 1\n"
        "  REMOVE · [source-0] Source 1, first claim.\n"
        "                      Source 1, second claim.\n"
        "  ADD    · [child-00] Child 1 A.\n"
        "  ADD    · [child-00] Child 1 B.\n"
        "\n"
        "RECEIPT · analysis-uid\n"
        "CHECKPOINT · checkpoint-uid\n"
        "REVIEW · mem review atomize --context practice/greetings\n"
        "RECOVERY · mem undo\n"
    )


def test_atomize_receipt_bounds_split_proof_and_names_review(capsys) -> None:
    pairs = tuple(_split(index) for index in range(1, 5))
    session = SimpleNamespace(
        uid="analysis-uid",
        items=tuple(source for source, _applied in pairs),
    )
    result = SimpleNamespace(
        split_count=4,
        child_count=8,
        preserved_count=0,
        items=tuple(applied for _source, applied in pairs),
    )

    render_atomize_apply_result(
        session=session,
        context_name="practice/greetings",
        result=result,
        checkpoint_uid="checkpoint-uid",
        created=False,
        audit=_EMPTY_AUDIT,
    )

    output = capsys.readouterr().out
    assert "Source 1, first claim." in output
    assert "Source 3, first claim." in output
    assert "Source 4, first claim." not in output
    assert "… 1 MORE SPLIT · see REVIEW" in output
    assert "REVIEW · mem review atomize --context practice/greetings" in output


def test_atomize_receipt_presents_each_unresolved_issue_as_one_logical_line(
    capsys,
) -> None:
    first = SimpleNamespace(
        memory_uid="memory-0001",
        content="The access window may begin at eight.\nLocal time is unstated.",
        position=0,
    )
    second = SimpleNamespace(
        memory_uid="memory-0002",
        content="The access window begins at nine.",
        position=1,
    )
    session = SimpleNamespace(
        uid="analysis-uid",
        context_name="practice/greetings",
        items=(first, second),
    )
    result = SimpleNamespace(
        split_count=0,
        child_count=0,
        preserved_count=2,
        items=(),
    )
    audit = AtomizeApplicationAudit(
        application_mode="AS_IS",
        unresolved_at_apply=(
            {
                "issue_uid": "uncertainty-1",
                "kind": "ATOMIZE_UNCERTAINTY",
                "source_uids": [first.memory_uid],
                "classification": "UNCERTAIN · REQUIRES CONTEXT",
                "reason": "The time zone is not explicit.\nNo split was inferred.",
                "response_state": "OPEN",
            },
            {
                "issue_uid": "conflict-1",
                "kind": "CONFLICT",
                "source_uids": [first.memory_uid, second.memory_uid],
                "classification": "YES",
                "reason": "Both opening times cannot govern the same window.",
                "response_state": "OPEN",
            },
        ),
        workbench_uid="workbench-uid",
        workbench_response_digest="response-digest",
    )

    render_atomize_apply_result(
        session=session,
        context_name=session.context_name,
        result=result,
        checkpoint_uid="checkpoint-uid",
        created=False,
        audit=audit,
    )

    output = capsys.readouterr().out
    assert "UNRESOLVED ISSUES · 2 · APPLIED AS-IS" in output
    assert (
        "? AMBIGUOUS · [MEMORY memory-0001] “The access window may begin at eight. "
        "Local time is unstated.” · WHY · The time zone is not explicit. "
        "No split was inferred."
    ) in output
    assert (
        "! CONFLICT · [MEMORY memory-0001] “The access window may begin at eight. "
        "Local time is unstated.” ↔ [MEMORY memory-0002] "
        "“The access window begins at nine.” · WHY · Both opening times cannot "
        "govern the same window."
    ) in output
    assert "JUDGMENTS ·" not in output
