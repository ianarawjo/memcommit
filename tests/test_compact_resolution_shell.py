from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.exact_command_review import ExactCommandReview
from memcommit.interfaces.tui.workbenches.resolution.compact_shell import (
    run_compact_resolution_decisions,
)
from memcommit.interfaces.tui.components.save_location import SaveLocationView
from memcommit.resolution_workbench import (
    ResolutionItem,
    ResolutionOption,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)


def _item(uid: str, title: str) -> ResolutionItem:
    return ResolutionItem(
        uid=uid,
        kind="CONFLICT",
        status="OPEN",
        priority="REQUIRED",
        title=title,
        summary=f"Choose the policy for {title}.",
        obligation="REQUIRED",
        question=f"Which reading should {title} use?",
        options=(
            ResolutionOption(f"{uid}:a", "A", "Keep records for 30 days."),
            ResolutionOption(f"{uid}:b", "B", "Keep records for 90 days."),
            ResolutionOption(
                f"{uid}:both",
                "Preserve both",
                "Retain both scoped readings.",
            ),
        ),
    )


def _view() -> ResolutionWorkbenchView:
    return ResolutionWorkbenchView(
        operation="MELD",
        artifact_uid="meld-session",
        revision="revision-1",
        title="Resolve Meld",
        route="incoming → baseline",
        status="OPEN",
        metrics=(),
        overview="The complete report is retained for Impact review.",
        list_label="CONFLICTS",
        items=(
            _item("retention", "Retention period"),
            _item("access", "Access policy"),
        ),
        empty_message="No conflicts.",
        results_label="CHANGES",
        results=(),
        capabilities=frozenset({"SUBMIT_ALL", "DEFER"}),
    )


def _run(keys: str):
    selected: dict[str, str] = {}
    actions: list[ResolutionWorkbenchAction] = []

    def continue_action(_focused_uid: str | None):
        if set(selected) != {"retention", "access"}:
            return None
        action = ResolutionWorkbenchAction(kind="SUBMIT_ALL")
        actions.append(action)
        return action

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        result = run_compact_resolution_decisions(
            _view,
            selected_option=selected.get,
            stage_option=selected.__setitem__,
            build_continue_action=continue_action,
            build_simple_action=lambda kind: ResolutionWorkbenchAction(kind=kind),
            continue_label=lambda: "Continue",
            app_input=pipe_input,
            app_output=DummyOutput(),
        )
    return result, selected, actions


def test_numbers_stage_multiple_issues_before_one_continue_action():
    action, selected, actions = _run("1\x1b[C2a")

    assert action.kind == "SUBMIT_ALL"
    assert selected == {"retention": "retention:a", "access": "access:b"}
    assert actions == [action]


def test_direction_keys_alone_can_navigate_and_stage_out_of_order():
    # Right opens issue 2, Down targets choice 2, and Enter stages it. Left
    # returns to issue 1, whose first choice is staged with Enter.
    action, selected, _actions = _run("\x1b[C\x1b[B\r\x1b[D\ra")

    assert action.kind == "SUBMIT_ALL"
    assert selected == {"access": "access:b", "retention": "retention:a"}


def test_defer_is_available_as_a_single_compact_key():
    action, selected, actions = _run("d")

    assert action.kind == "DEFER"
    assert selected == {}
    assert actions == []


def test_exact_command_review_stays_adjacent_to_compact_decisions():
    selected: dict[str, str] = {}
    action = ResolutionWorkbenchAction(kind="ACCEPT")
    review = ExactCommandReview(
        argv=("mem", "meld", "--accept"),
        effects=("Apply the exact reviewed Meld proposal.",),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("1\x1b[C1a\r")
        result = run_compact_resolution_decisions(
            _view,
            selected_option=selected.get,
            stage_option=selected.__setitem__,
            build_continue_action=lambda _uid: action,
            build_simple_action=lambda kind: ResolutionWorkbenchAction(kind=kind),
            continue_label=lambda: "Apply",
            turn_command_review=lambda _action: review,
            app_input=pipe_input,
            app_output=DummyOutput(),
        )

    assert result is action
    assert selected == {"retention": "retention:a", "access": "access:a"}


def test_compact_decisions_edit_the_exact_save_location_inline():
    selected: dict[str, str] = {}

    def validate(value: str) -> None:
        if not value.startswith("result/"):
            raise ValueError("Use result/ namespace.")

    with create_pipe_input() as pipe_input:
        # The first invalid Enter must retain the editor; the second exact
        # candidate leaves it through a typed destination-change action.
        pipe_input.send_text(
            "l\x15wrong/place\r\x15result/reviewed\r"
        )
        result = run_compact_resolution_decisions(
            _view,
            selected_option=selected.get,
            stage_option=selected.__setitem__,
            build_continue_action=lambda _uid: ResolutionWorkbenchAction(
                kind="ACCEPT"
            ),
            build_simple_action=lambda kind: ResolutionWorkbenchAction(kind=kind),
            continue_label=lambda: "Apply",
            destination=SaveLocationView(
                value="result/draft",
                state="NOT CREATED",
                validate=validate,
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
        )

    assert result.kind == "CHANGE_DESTINATION"
    assert result.destination == "result/reviewed"
    assert selected == {}


def test_compact_destination_backspace_remains_text_deletion():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("l\x7f\r")
        result = run_compact_resolution_decisions(
            _view,
            selected_option=lambda _uid: None,
            stage_option=lambda _uid, _option_uid: None,
            build_continue_action=lambda _uid: None,
            build_simple_action=lambda kind: ResolutionWorkbenchAction(kind=kind),
            continue_label=lambda: "Apply",
            destination=SaveLocationView(value="result/draft"),
            app_input=pipe_input,
            app_output=DummyOutput(),
        )

    assert result.kind == "CHANGE_DESTINATION"
    assert result.destination == "result/draf"


def test_compact_destination_keeps_printable_q_as_name_input():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("lq\r")
        result = run_compact_resolution_decisions(
            _view,
            selected_option=lambda _uid: None,
            stage_option=lambda _uid, _option_uid: None,
            build_continue_action=lambda _uid: None,
            build_simple_action=lambda kind: ResolutionWorkbenchAction(kind=kind),
            continue_label=lambda: "Apply",
            destination=SaveLocationView(value="result/draft"),
            app_input=pipe_input,
            app_output=DummyOutput(),
        )

    assert result.kind == "CHANGE_DESTINATION"
    assert result.destination == "result/draftq"


def test_compact_destination_escape_returns_before_root_close():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("l\x1b\x1b")
        result = run_compact_resolution_decisions(
            _view,
            selected_option=lambda _uid: None,
            stage_option=lambda _uid, _option_uid: None,
            build_continue_action=lambda _uid: None,
            build_simple_action=lambda kind: ResolutionWorkbenchAction(kind=kind),
            continue_label=lambda: "Apply",
            destination=SaveLocationView(value="result/draft"),
            app_input=pipe_input,
            app_output=DummyOutput(),
        )

    assert result.kind == "CLOSE"
