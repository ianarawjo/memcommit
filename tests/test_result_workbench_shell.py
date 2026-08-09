from __future__ import annotations

from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.result_workbench_shell import (
    render_result_workbench_snapshot,
    run_result_workbench_shell,
)
from memcommit.result_workbench import (
    ResultCase,
    ResultCaseDetail,
    ResultDetailBlock,
    ResultMetric,
    ResultRef,
    ResultSection,
    ResultWorkbenchError,
    ResultWorkbenchView,
)


ARTIFACT_DIGEST = "a" * 64


class RecordingAdapter:
    def __init__(
        self,
        view: ResultWorkbenchView,
        details: dict[str, ResultCaseDetail],
    ) -> None:
        self._view = view
        self._details = details
        self.calls: list[str] = []

    def view(self) -> ResultWorkbenchView:
        self.calls.append("view")
        return self._view

    def case_detail(self, case_uid: str) -> ResultCaseDetail:
        self.calls.append(f"detail:{case_uid}")
        return self._details[case_uid]


def _fixture() -> tuple[
    ResultWorkbenchView,
    dict[str, ResultCaseDetail],
]:
    source = ResultRef("memory", "source-1")
    second_source = ResultRef("memory", "source-2")
    judgment = ResultRef("finding", "finding-1")
    second_judgment = ResultRef("finding", "finding-2")
    outcome = ResultRef("memory", "result-1")
    unresolved = ResultRef("issue", "issue-1")
    representative = ResultCase(
        uid="representative-1",
        role="REPRESENTATIVE",
        title="Ordinary preserved rule",
        summary="A clear source commitment remains available in the result.",
        why_selected=(
            "It demonstrates the operation's normal evidence-to-result path."
        ),
    )
    boundary = ResultCase(
        uid="boundary-1",
        role="BOUNDARY",
        title="Unresolved local referent",
        summary="The source says “that door” without a safe local referent.",
        why_selected=(
            "A guessed referent would change which entrance is restricted."
        ),
    )
    view = ResultWorkbenchView(
        operation="atomize",
        artifact_uid="analysis-1",
        artifact_digest=ARTIFACT_DIGEST,
        title="campus/construction-updates",
        status="PREVIEW",
        metrics=(
            ResultMetric("source_count", "sources", 51),
            ResultMetric("result_count", "projected", 61),
        ),
        understood=ResultSection(
            "PRESENT",
            (
                "The source describes closures, continuing access, and "
                "replacement services."
            ),
            (source, second_source),
        ),
        happened=ResultSection(
            "PRESENT",
            "Clear commitments were preserved or split into atomic results.",
            (outcome,),
        ),
        unresolved=ResultSection(
            "PRESENT",
            "One local referent remains unresolved and was not guessed.",
            (unresolved,),
        ),
        cases=(representative, boundary),
    )
    details = {
        representative.uid: ResultCaseDetail(
            case_uid=representative.uid,
            artifact_digest=ARTIFACT_DIGEST,
            blocks=(
                ResultDetailBlock(
                    "SOURCE EVIDENCE",
                    "The staff entrance remains open.",
                    (source,),
                ),
                ResultDetailBlock(
                    "OPERATION JUDGMENT",
                    "The sentence is already one scoped commitment.",
                    (judgment,),
                ),
                ResultDetailBlock(
                    "RESULT",
                    "The source Memory is preserved without a split.",
                    (outcome,),
                ),
            ),
            evidence_refs=(source,),
            judgment_refs=(judgment,),
            outcome_refs=(outcome,),
        ),
        boundary.uid: ResultCaseDetail(
            case_uid=boundary.uid,
            artifact_digest=ARTIFACT_DIGEST,
            blocks=(
                ResultDetailBlock(
                    "SOURCE EVIDENCE",
                    "Do not use that door.",
                    (second_source,),
                ),
                ResultDetailBlock(
                    "OPERATION JUDGMENT",
                    "No unique local referent can be recovered safely.",
                    (second_judgment,),
                ),
                ResultDetailBlock(
                    "UNRESOLVED",
                    "The source is retained for clarification.",
                    (unresolved,),
                ),
            ),
            evidence_refs=(second_source,),
            judgment_refs=(second_judgment,),
            unresolved_refs=(unresolved,),
        ),
    }
    return view, details


def test_snapshot_uses_shared_information_hierarchy_and_compact_cases():
    view, _ = _fixture()

    snapshot = render_result_workbench_snapshot(view)

    assert snapshot.startswith(
        " RESULT · atomize · campus/construction-updates\n"
        " STATUS · PREVIEW · sources=51 · projected=61\n"
    )
    headings = [
        "WHAT MEM UNDERSTOOD",
        "WHAT HAPPENED",
        "WHAT REMAINS UNRESOLVED",
        "REPRESENTATIVE / BOUNDARY CASES",
    ]
    assert [snapshot.index(heading) for heading in headings] == sorted(
        snapshot.index(heading) for heading in headings
    )
    assert "›  1. [REPRESENTATIVE] Ordinary preserved rule" in snapshot
    assert "   2. [BOUNDARY] Unresolved local referent" in snapshot
    assert "WHY SELECTED" not in snapshot
    assert "CASE DETAIL" not in snapshot


def test_case_rows_preserve_complete_text_for_window_owned_wrapping():
    view, _ = _fixture()
    long_summary = (
        "This complete result summary remains available to a wide viewport and "
        "is wrapped by the Window only when the actual terminal width requires it. "
        "No fixed one-hundred-and-twenty-character omission is applied first."
    )
    first = replace(view.cases[0], summary=long_summary)
    view = replace(view, cases=(first, *view.cases[1:]))

    snapshot = render_result_workbench_snapshot(view)

    assert long_summary in snapshot
    assert "…" not in snapshot


def test_snapshot_distinguishes_none_reported_from_not_recorded():
    view, _ = _fixture()
    view = replace(
        view,
        unresolved=ResultSection("NONE_REPORTED", ""),
        happened=ResultSection(
            "NOT_RECORDED",
            "This legacy artifact predates aggregate outcome narration.",
        ),
    )

    snapshot = render_result_workbench_snapshot(view)

    assert "(none reported under this operation's bounded contract)" in (
        snapshot
    )
    assert "(not recorded by this result artifact)" in snapshot
    assert "This legacy artifact predates aggregate outcome narration." in (
        snapshot
    )


def test_expanded_snapshot_preserves_operation_detail_and_canonical_trace():
    view, details = _fixture()
    detail = details["boundary-1"]

    snapshot = render_result_workbench_snapshot(
        view,
        selected_case_uid="boundary-1",
        detail=detail,
    )

    assert "▾  2. [BOUNDARY] Unresolved local referent" in snapshot
    assert "CASE DETAIL · 2/2 · BOUNDARY" in snapshot
    assert "WHY SELECTED" in snapshot
    assert "Do not use that door." in snapshot
    assert "No unique local referent can be recovered safely." in snapshot
    assert "The source is retained for clarification." in snapshot
    evidence_at = snapshot.index("EVIDENCE   · memory:source-2")
    judgment_at = snapshot.index("→ JUDGMENT · finding:finding-2")
    unresolved_at = snapshot.index("→ UNRESOLVED · issue:issue-1")
    assert evidence_at < judgment_at < unresolved_at


def test_representative_trace_reaches_its_supported_outcome():
    view, details = _fixture()

    snapshot = render_result_workbench_snapshot(
        view,
        detail=details["representative-1"],
    )

    evidence_at = snapshot.index("EVIDENCE   · memory:source-1")
    judgment_at = snapshot.index("→ JUDGMENT · finding:finding-1")
    outcome_at = snapshot.index("→ OUTCOME  · memory:result-1")
    assert evidence_at < judgment_at < outcome_at


def test_expanded_snapshot_rejects_stale_or_mismatched_detail():
    view, details = _fixture()
    stale = replace(details["boundary-1"], artifact_digest="b" * 64)

    with pytest.raises(ResultWorkbenchError, match="stale"):
        render_result_workbench_snapshot(view, detail=stale)
    with pytest.raises(ResultWorkbenchError, match="does not match"):
        render_result_workbench_snapshot(
            view,
            selected_case_uid="representative-1",
            detail=details["boundary-1"],
        )


def test_snapshot_neutralizes_terminal_controls_without_rewriting_content():
    view, _ = _fixture()
    view = replace(
        view,
        understood=ResultSection(
            "PRESENT",
            "Line one\nLine two\x1b[31m\u202ereversed",
            view.understood.refs,
        ),
    )

    snapshot = render_result_workbench_snapshot(view)

    assert "Line one\nLine two�[31m�reversed" in snapshot
    assert "\x1b" not in snapshot
    assert "\u202e" not in snapshot


def test_tty_navigation_fetches_only_the_case_explicitly_expanded():
    view, details = _fixture()
    adapter = RecordingAdapter(view, details)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\rq")
        result = run_result_workbench_shell(
            adapter,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is view
    assert adapter.calls == ["view", "detail:boundary-1"]


@pytest.mark.parametrize("collapse_key", ["\x1b", "\x7f"])
def test_tty_escape_and_backspace_collapse_without_another_detail_lookup(
    collapse_key,
):
    view, details = _fixture()
    adapter = RecordingAdapter(view, details)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(f"\r{collapse_key}q")
        run_result_workbench_shell(
            adapter,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert adapter.calls == ["view", "detail:representative-1"]


def test_tty_navigation_and_quit_remain_read_only_without_detail_lookup():
    view, details = _fixture()
    adapter = RecordingAdapter(view, details)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\x1b[Aq")
        run_result_workbench_shell(
            adapter,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert adapter.calls == ["view"]


def test_snapshot_handles_an_artifact_without_selected_cases():
    view, _ = _fixture()
    view = replace(view, cases=())

    snapshot = render_result_workbench_snapshot(view)

    assert "(no inspection cases recorded)" in snapshot
    assert "CASE DETAIL" not in snapshot
