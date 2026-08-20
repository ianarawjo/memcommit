from __future__ import annotations

from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.resolution_workbench_shell import (
    RESOLUTION_WORKBENCH_STYLE,
    _seeded_report_lines,
    resolution_report_fragments,
    run_resolution_workbench_shell,
)
from memcommit.impact_controller import ImpactController
from memcommit.memory_diff import MemoryChange
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
                rules=("Retain reviewed additions.",),
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
        "APPLY CONFIRMATION"
    )
    assert "PROPOSED EFFECTS" not in rendered
    assert "[ADD] [result-1] Add the reviewed Memory." in rendered
    assert "RULE · Retain reviewed additions." not in rendered
    assert "WHY ·" not in rendered
    assert "It passed the operation-owned review." not in rendered

    expanded = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            review_and_apply=True,
            impact_controller=impact,
            expanded_impact_section_uid="REPORT:IMPACT:result-1",
        )
    )
    assert "RULE · Retain reviewed additions." in expanded
    assert "WHY · It passed the operation-owned review." in expanded


def test_located_memory_changes_render_as_compact_before_after_diff():
    view = replace(_view(operation="UPDATE"), results=())
    impact = ImpactController.from_memory_changes(
        operation=view.operation,
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT · UPDATE",
        summary="Exact located changes.",
        changes=(
            MemoryChange(
                marker="~",
                treatment="EDIT",
                location="campus-wiki/route-changes",
                memory_uid="12345678-1234-4234-8234-123456789abc",
                before="Use the north route.",
                after="Use the south route.",
                reason="The verified route changed.",
            ),
            MemoryChange(
                marker="+",
                treatment="ADD",
                location="campus-wiki/route-changes",
                memory_uid="abcdefab-1234-4234-8234-123456789abc",
                before=None,
                after="Follow the temporary signs.",
            ),
        ),
    )

    rendered = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            impact_controller=impact,
        )
    )

    assert "APPLICATION · 0" not in rendered
    assert "[EDIT] campus-wiki/route-changes [12345678]" in rendered
    assert "- Use the north route." in rendered
    assert "+ Use the south route." in rendered
    assert "[ADD]  campus-wiki/route-changes [abcdefab]" in rendered
    assert "+ Follow the temporary signs." in rendered
    assert "The verified route changed." not in rendered

    fragments = resolution_report_fragments(view, impact_controller=impact)
    assert next(style for style, text in fragments if text == "north") == (
        "class:memory-diff.remove.changed"
    )
    assert next(style for style, text in fragments if text == "south") == (
        "class:memory-diff.add.changed"
    )
    assert any(
        style == "class:memory-diff.remove" and text == "Use the "
        for style, text in fragments
    )

    for side, changed_color in (("remove", "ed8796"), ("add", "a6da95")):
        neutral_style = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
            f"class:memory-diff.{side}"
        )
        changed_style = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
            f"class:memory-diff.{side}.changed"
        )
        assert neutral_style.color == "ffffff"
        assert neutral_style.underline is False
        assert changed_style.color == changed_color
        assert changed_style.bold is False
        assert changed_style.underline is True

    equal_style = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
        "class:memory-diff.equal"
    )
    assert equal_style.color == "ffffff"

    assert next(style for style, text in fragments if "[EDIT]" in text) == (
        "class:impact.edit"
    )
    assert next(style for style, text in fragments if "[ADD]" in text) == (
        "class:impact.add"
    )
    assert next(
        style
        for style, text in fragments
        if "campus-wiki/route-changes [12345678]" in text
    ) == "class:memory-object"

    assert RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
        "class:impact.edit"
    ).color == "a6da95"
    assert RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
        "class:impact.add"
    ).color == "8aadf4"
    assert RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
        "class:impact.remove"
    ).color == "ed8796"

    addition_index = next(
        index
        for index, (_style, text) in enumerate(fragments)
        if text == "Follow the temporary signs."
    )
    assert [text for _style, text in fragments[addition_index + 1 : addition_index + 3]] == [
        "\n",
        "\n",
    ]


def test_impact_treatment_uid_content_and_detail_columns_align():
    view = replace(
        _view(),
        results=(
            ResolutionResult(
                uid="keep-uid",
                marker="+",
                label="KEEP",
                text="Kept content.",
                reason="Keep reason.",
                rules=("Keep rule.",),
            ),
            ResolutionResult(
                uid="summary-uid",
                marker="~",
                label="SUMMARIZE",
                text="Summarized content.",
            ),
        ),
    )
    impact = ImpactController.from_resolution(
        view,
        title="IMPACT · ALIGNED",
        summary="Aligned effects.",
    )

    rendered = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            impact_controller=impact,
            expanded_impact_section_uid="REPORT:IMPACT:keep-uid",
        )
    )
    lines = rendered.splitlines()
    keep = next(line for line in lines if "[keep-uid]" in line)
    summary = next(line for line in lines if "[summary" in line)
    rule = next(line for line in lines if "RULE · Keep rule." in line)
    why = next(line for line in lines if "WHY · Keep reason." in line)

    assert keep.index("[keep-uid]") == summary.index("[summary")
    assert keep.index("Kept content.") == summary.index("Summarized content.")
    assert rule.index("RULE ·") == keep.index("Kept content.")
    assert why.index("WHY ·") == keep.index("Kept content.")


def test_impact_treatments_and_markers_use_distinct_semantic_styles():
    labels = (
        "KEEP",
        "REDACT",
        "SUMMARIZE",
        "REFRAME",
        "FORGET",
        "EDIT",
        "ADD",
        "REMOVE",
    )
    view = replace(
        _view(),
        results=tuple(
            ResolutionResult(
                uid=f"uid-{index}",
                marker="−" if label == "FORGET" else "+",
                label=label,
                text=f"{label.title()} content.",
            )
            for index, label in enumerate(labels)
        ),
    )
    impact = ImpactController.from_resolution(
        view,
        title="IMPACT · COLORS",
        summary="Colored treatments.",
    )

    fragments = resolution_report_fragments(view, impact_controller=impact)
    styles = {
        label: next(style for style, text in fragments if f"[{label}]" in text)
        for label in labels
    }

    assert styles == {
        "KEEP": "class:impact.keep",
        "REDACT": "class:impact.redact",
        "SUMMARIZE": "class:impact.summarize",
        "REFRAME": "class:impact.reframe",
        "FORGET": "class:impact.forget",
        "EDIT": "class:impact.edit",
        "ADD": "class:impact.add",
        "REMOVE": "class:impact.remove",
    }


def test_focused_impact_memory_content_follows_its_treatment_color():
    view = replace(
        _view(),
        results=(
            ResolutionResult(
                uid="keep-focus",
                marker="+",
                label="KEEP",
                text="Focused retained content.",
                reason="Keep it.",
                rules=("Retention rule.",),
            ),
        ),
    )
    impact = ImpactController.from_resolution(
        view,
        title="IMPACT · FOCUS",
        summary="Focused effect.",
    )

    fragments = resolution_report_fragments(
        view,
        impact_controller=impact,
        focused_section=2,
        expanded_impact_section_uid="REPORT:IMPACT:keep-focus",
    )

    assert next(
        style for style, text in fragments if "Focused retained content." in text
    ) == "class:impact.keep.focused"
    assert next(
        style for style, text in fragments if "RULE · Retention rule." in text
    ) == "class:impact.keep.focused"
    assert next(
        style for style, text in fragments if "WHY · Keep it." in text
    ) == "class:impact.keep.focused"
    assert all(style != "class:memory-object.focused" for style, _text in fragments)


def test_impact_hanging_wrap_tracks_the_supplied_frame_width():
    view = replace(
        _view(),
        results=(
            ResolutionResult(
                uid="wrap-uid",
                marker="+",
                label="KEEP",
                text=(
                    "One two three four five six seven eight nine ten eleven "
                    "twelve thirteen fourteen."
                ),
            ),
        ),
    )
    impact = ImpactController.from_resolution(
        view,
        title="IMPACT · WRAP",
        summary="Wrapped effect.",
    )

    rendered = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            impact_controller=impact,
            content_width=48,
        )
    )
    lines = rendered.splitlines()
    first_index = next(index for index, line in enumerate(lines) if "[wrap-uid]" in line)
    first = lines[first_index]
    continuation = lines[first_index + 1]

    assert first.index("One") == continuation.index("five")
    assert len(first) <= 48
    assert len(continuation) <= 48


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

    assert lines.index("IMPACT · COMPARE") < lines.index("APPLY CONFIRMATION")
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
        # To Do opens the final review; End reaches its Apply action.
        pipe_input.send_text("\x1b[Z\r\x1b[F\r")
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
