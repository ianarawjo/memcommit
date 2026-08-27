from __future__ import annotations

from types import SimpleNamespace

from memcommit.adapters.interfaces.cli.atomize import render_atomize_apply_result


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
        unresolved_at_apply_count=0,
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
        unresolved_at_apply_count=0,
    )

    output = capsys.readouterr().out
    assert "Source 1, first claim." in output
    assert "Source 3, first claim." in output
    assert "Source 4, first claim." not in output
    assert "… 1 MORE SPLIT · see REVIEW" in output
    assert "REVIEW · mem review atomize --context practice/greetings" in output
