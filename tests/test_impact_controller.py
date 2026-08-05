from __future__ import annotations

from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.resolution_workbench_shell import (
    _seeded_report_lines,
    resolution_report_fragments,
    run_resolution_workbench_shell,
)
from memcommit.impact_controller import ImpactController
from memcommit.resolution_workbench import (
    ResolutionResult,
    ResolutionWorkbenchView,
)


def _view(*, operation: str = "SEVER", revision: str = "revision-1"):
    return ResolutionWorkbenchView(
        operation=operation,
        artifact_uid="artifact-1",
        revision=revision,
        title=f"MEM {operation}",
        route="source → target",
        status="READY",
        metrics=(),
        overview="Review the exact proposal.",
        list_label="ITEMS",
        items=(),
        empty_message="No items.",
        results_label="PROPOSED EFFECTS",
        results=(
            ResolutionResult(
                uid="result-1",
                marker="+",
                label="ADD",
                text="Add the reviewed Memory.",
                reason="It passed the operation-owned review.",
            ),
        ),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )


def test_resolution_impact_is_rendered_immediately_before_operation_apply():
    view = _view()
    impact = ImpactController.from_resolution(
        view,
        title="IMPACT · LOCAL OUTBOUND DRAFT · NOT SENT",
        summary="Exact local effect.",
    )

    rendered = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            review_and_apply=True,
            impact_controller=impact,
        )
    )

    assert rendered.index("IMPACT · LOCAL OUTBOUND DRAFT · NOT SENT") < rendered.index(
        "REVIEW & APPLY SEVER"
    )
    assert "[ADD] Add the reviewed Memory." in rendered


def test_seeded_compare_impact_precedes_meld_apply():
    view = _view(operation="MELD")
    impact = ImpactController.from_text(
        operation="MELD",
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT · COMPARE",
        summary="Saved equal-authority analysis.",
        detail="WHAT DIFFERS\nOne exact difference.",
    )

    lines = _seeded_report_lines(
        view,
        "MEM COMPARE · SAVED",
        (),
        True,
        False,
        impact,
    )

    assert lines.index("IMPACT · COMPARE") < lines.index("REVIEW & APPLY MELD")
    assert "WHAT DIFFERS\nOne exact difference." in lines


def test_controller_rejects_a_stale_artifact_revision():
    view = _view()
    impact = ImpactController.from_resolution(
        replace(view, revision="older"),
        title="IMPACT · SEVER",
        summary="Stale effect.",
    )

    with pytest.raises(ValueError, match="active artifact revision"):
        resolution_report_fragments(view, impact_controller=impact)


def test_split_apply_row_accepts_without_whole_set_strategies():
    view = _view(operation="UPDATE")
    impact = ImpactController.from_resolution(
        view,
        title="IMPACT · UPDATE",
        summary="Exact staged effects.",
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        action = run_resolution_workbench_shell(
            view,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            split_viewer_items=True,
            review_and_apply=True,
            impact_controller=impact,
        )

    assert action.kind == "ACCEPT"
