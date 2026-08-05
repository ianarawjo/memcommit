"""Read-only interaction contracts for the Compare analysis workbench."""

from __future__ import annotations

import io
import json
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.compare_workbench import (
    _display_multiline,
    _focused_section_line,
    _next_viewer_section_index,
    _reader_section_offsets,
    _rows,
    run_compare_workbench,
)
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation
from memcommit.comparison import ComparisonInput
from memcommit.comparison_provider import analyze_comparison
from memcommit.comparison_provider import COMPARISON_PAYLOAD_MARKER
from memcommit.context import Context, Memory


class _ConflictProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        del output_schema
        assert operation == "compare_contexts"
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        reference_id = payload["frames"][0]["memories"][0]["memory_id"]
        compared_id = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps({
            "overview": "The advisors disagree about one accessible choice.",
            "reports": {
                "both": "",
                "differences": "They recommend different visible formats.",
                "reference_only": "",
                "compared_only": "",
            },
            "relations": [
                {
                    "relation_key": "format_conflict",
                    "reference_memory_ids": [reference_id],
                    "compared_memory_ids": [compared_id],
                    "kind": "CONFLICT",
                    "status": "UNRESOLVED",
                    "summary": "One prefers headings and one prefers flow.",
                    "reason": "Both formats cannot govern the same passage.",
                }
            ],
            "issues": [
                {
                    "issue_key": "heading_format",
                    "relation_keys": ["format_conflict"],
                    "priority": "REQUIRED",
                    "title": "Heading format",
                    "question": "Should the page use headings or transitions?",
                    "why_it_matters": "The choice changes how readers navigate.",
                    "options": [
                        {
                            "label": "Headings",
                            "text": "Make sections easy to revisit.",
                        },
                        {
                            "label": "Transitions",
                            "text": "Preserve one continuous argument.",
                        },
                    ],
                }
            ],
        })


def _analysis():
    reference = Context(uid=str(uuid.uuid4()), name="task-2/advisor1")
    left = Memory(uid=str(uuid.uuid4()), content="Use descriptive headings.")
    reference.add(left)
    compared = Context(uid=str(uuid.uuid4()), name="task-2/advisor2")
    right = Memory(uid=str(uuid.uuid4()), content="Use paragraph transitions.")
    compared.add(right)
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(reference, compared),
        _ConflictProvider(),
    )
    return analysis, left, right


def test_issue_can_choose_either_exact_source_for_rationale():
    analysis, _left, right = _analysis()
    with create_pipe_input() as pipe_input:
        # Items owns initial focus. Report sections precede the issue; Enter
        # opens that row in Viewer after choosing its second exact source.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[B\x1b[B\x1b[C\rr")
        receipt = run_compare_workbench(
            analysis,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "rationale"
    assert receipt.context_name == "task-2/advisor2"
    assert receipt.memory_uid == right.uid


@pytest.mark.parametrize(
    ("key", "action"),
    [("l", "ledger"), ("m", "meld"), ("q", "close"), ("\x1b", "close")],
)
def test_workbench_returns_explicit_read_only_actions(key: str, action: str):
    analysis, _left, _right = _analysis()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(key)
        receipt = run_compare_workbench(
            analysis,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == action
    assert receipt.context_name is None
    assert receipt.memory_uid is None


def test_overview_has_no_synthetic_rationale_target():
    analysis, _left, _right = _analysis()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("rq")
        receipt = run_compare_workbench(
            analysis,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "close"


def test_report_sections_precede_issues_and_relation_ledger():
    analysis, _left, _right = _analysis()

    rows = _rows(analysis)

    assert [row.kind for row in rows] == [
        "REPORT",
        "SECTION",
        "SECTION",
        "SECTION",
        "ISSUE",
        "LEDGER",
        "RELATION",
    ]
    assert rows[0].label == "Complete Compare report"
    assert rows[-2].label == "Relation ledger · 1"


def test_item_selection_does_not_replace_viewer_until_enter():
    analysis, _left, _right = _analysis()
    navigation = SessionWorkbenchNavigation()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Bq")
        receipt = run_compare_workbench(
            analysis,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            workbench_navigation=navigation,
        )

    assert receipt.action == "close"
    assert navigation.row_index == 1
    assert navigation.viewer_row_index == 0


def test_multiline_report_preserves_layout_and_escapes_controls_per_line():
    rendered = _display_multiline("WHAT BOTH CONTAIN\nunsafe\tvalue\nWHAT DIFFERS")

    assert rendered == "WHAT BOTH CONTAIN\nunsafe\\tvalue\nWHAT DIFFERS"


def test_viewer_marks_the_current_section_with_a_focus_line():
    assert _focused_section_line("POTENTIAL CONFLICTS · 5") == (
        "── POTENTIAL CONFLICTS · 5 ──"
    )


def test_reader_arrows_move_between_semantic_section_boundaries():
    report = "\n".join(
        (
            "MEM COMPARE · SYMMETRIC PEERS",
            "Reference: advisor1",
            "METRICS · RELATIONS 1",
            "",
            "WHAT MEM UNDERSTOOD",
            "Overview text.",
            "",
            "WHAT BOTH CONTAIN · 1",
            "Shared text.",
            "",
            "WHAT DIFFERS · 1",
            "Different text.",
        )
    )

    assert _reader_section_offsets(report) == (0, 4, 7, 10)
    assert _next_viewer_section_index(report, 0, 1) == 1
    assert _next_viewer_section_index(report, 1, 1) == 2
    assert _next_viewer_section_index(report, 2, -1) == 1
    assert _next_viewer_section_index(report, 3, 1) == 3


def test_report_detail_can_scroll_without_changing_selection():
    analysis, _left, _right = _analysis()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r\x1b[6~q")
        receipt = run_compare_workbench(
            analysis,
            report_text="\n".join(f"line {index}" for index in range(30)),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "close"


def test_tab_switches_to_item_navigation_and_back_to_reader():
    analysis, _left, _right = _analysis()
    with create_pipe_input() as pipe_input:
        # Items starts focused. Tab opens Viewer navigation, another Tab
        # returns to Items, and the final Tab restores semantic scrolling.
        pipe_input.send_text("\t\x1b[B\t\x1b[B\t\x1b[Bq")
        receipt = run_compare_workbench(
            analysis,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "close"


@pytest.mark.parametrize("back_key", ["b", "\x1b"])
def test_detail_back_key_returns_to_complete_report(back_key: str):
    analysis, _left, _right = _analysis()
    with create_pipe_input() as pipe_input:
        # Select and open a report section, return to REPORT, then R must remain
        # a no-op because the aggregate report has no synthetic Memory target.
        pipe_input.send_text(f"\x1b[B\r{back_key}rq")
        receipt = run_compare_workbench(
            analysis,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt.action == "close"


def test_workbench_requires_a_terminal_by_default(monkeypatch):
    analysis, _left, _right = _analysis()
    monkeypatch.setattr(
        "memcommit.commands.compare_workbench.sys.stdin",
        io.StringIO(),
    )
    monkeypatch.setattr(
        "memcommit.commands.compare_workbench.sys.stdout",
        io.StringIO(),
    )

    with pytest.raises(ValueError, match="requires a terminal"):
        run_compare_workbench(analysis)
