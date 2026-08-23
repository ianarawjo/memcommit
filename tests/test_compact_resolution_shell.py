from __future__ import annotations

from dataclasses import replace

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.interfaces.tui.workbenches.resolution.compact_shell import (
    run_compact_resolution_decisions,
)
from memcommit.interfaces.tui.workbenches.resolution.session_shell import (
    ResolutionGlobalStrategy,
    run_resolution_workbench_shell,
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
            ResolutionOption(
                f"{uid}:recommended",
                "A",
                "Keep records for 30 days.",
            ),
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
            continue_label=lambda: "Continue",
            app_input=pipe_input,
            app_output=DummyOutput(),
        )
    return result, selected, actions


def test_enter_stages_multiple_issues_before_one_apply_action():
    action, selected, actions = _run(
        "\x1b[C\x1b[B\r" + "\x1b[B" * 2 + "\r"
    )

    assert action.kind == "SUBMIT_ALL"
    assert selected == {
        "retention": "retention:recommended",
        "access": "access:b",
    }
    assert actions == [action]


def test_direction_keys_alone_can_navigate_and_stage_out_of_order():
    # Right opens issue 2, Down targets choice 2, and Enter stages it. Left
    # returns to issue 1, whose first choice is staged with Enter.
    action, selected, _actions = _run(
        "\x1b[C\x1b[B\r\x1b[D\r" + "\x1b[B" * 3 + "\r"
    )

    assert action.kind == "SUBMIT_ALL"
    assert selected == {
        "access": "access:b",
        "retention": "retention:recommended",
    }


def test_recommendations_are_defaults_and_apply_has_no_second_confirmation():
    action, selected, actions = _run("\x1b[B" * 3 + "\r")

    assert action.kind == "SUBMIT_ALL"
    assert selected == {
        "retention": "retention:recommended",
        "access": "access:recommended",
    }
    assert actions == [action]


def test_old_choice_and_action_shortcuts_have_no_compact_action():
    action, selected, actions = _run("12adpl\x1b")

    assert action.kind == "CLOSE"
    assert selected == {
        "retention": "retention:recommended",
        "access": "access:recommended",
    }
    assert actions == []


def test_compact_choice_is_discarded_on_close_instead_of_saved_as_a_draft():
    saved: list[tuple[str, str | None, str]] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r\x1b")
        action = run_resolution_workbench_shell(
            _view(),
            compact_decisions=True,
            draft_saver=lambda uid, option_uid, comment: saved.append(
                (uid, option_uid, comment)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert saved == []


def test_compact_response_accepts_direct_multiline_guidance_process_locally():
    item = replace(_item("retention", "Retention period"), commentable=True)
    view = replace(
        _view(),
        items=(item,),
        capabilities=frozenset({"SUBMIT_ITEM"}),
    )
    saved: list[tuple[str, str | None, str]] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[B" * 3
            + "\rKeep 45 days for audit logs.\x0aDelete other copies.\r"
            + "\x1b[B\r"
        )
        action = run_resolution_workbench_shell(
            view,
            compact_decisions=True,
            draft_saver=lambda uid, option_uid, comment: saved.append(
                (uid, option_uid, comment)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ITEM"
    assert action.item_uid == "retention"
    assert action.option_uid == "retention:recommended"
    assert action.comment == (
        "Keep 45 days for audit logs.\nDelete other copies."
    )
    assert saved == []


def test_compact_response_escape_discards_unsaved_text_before_root_close():
    item = replace(_item("retention", "Retention period"), commentable=True)
    view = replace(_view(), items=(item,))
    saved: list[tuple[str, str | None, str]] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B" * 3 + "\rtemporary direction\x1b\x1b")
        action = run_resolution_workbench_shell(
            view,
            compact_decisions=True,
            draft_saver=lambda uid, option_uid, comment: saved.append(
                (uid, option_uid, comment)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert saved == []


def test_compact_response_uses_one_whole_set_revision_turn_when_available():
    item = replace(_item("retention", "Retention period"), commentable=True)
    view = replace(
        _view(),
        items=(item,),
        capabilities=frozenset({"SUBMIT_ALL"}),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[B" * 3
            + "\rPreserve 30 days for audit logs only.\r"
            + "\x1b[B\r"
        )
        action = run_resolution_workbench_shell(
            view,
            compact_decisions=True,
            global_strategies=(
                ResolutionGlobalStrategy(
                    "Keep remaining recommendations",
                    "SUBMIT_ALL",
                    "Keep every other recommendation unchanged.",
                ),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ALL"
    assert "Preserve 30 days for audit logs only." in action.comment


def test_compact_decisions_edit_the_exact_save_location_inline():
    selected: dict[str, str] = {}

    def validate(value: str) -> None:
        if not value.startswith("result/"):
            raise ValueError("Use result/ namespace.")

    with create_pipe_input() as pipe_input:
        # The first invalid Enter must retain the editor; the second exact
        # candidate leaves it through a typed destination-change action.
        pipe_input.send_text(
            "\x1b[B" * 3 + "\r\x15wrong/place\r\x15result/reviewed\r"
        )
        result = run_compact_resolution_decisions(
            _view,
            selected_option=selected.get,
            stage_option=selected.__setitem__,
            build_continue_action=lambda _uid: ResolutionWorkbenchAction(
                kind="ACCEPT"
            ),
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
    assert selected == {
        "retention": "retention:recommended",
        "access": "access:recommended",
    }


def test_compact_destination_backspace_remains_text_deletion():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B" * 3 + "\r\x7f\r")
        result = run_compact_resolution_decisions(
            _view,
            selected_option=lambda _uid: None,
            stage_option=lambda _uid, _option_uid: None,
            build_continue_action=lambda _uid: None,
            continue_label=lambda: "Apply",
            destination=SaveLocationView(value="result/draft"),
            app_input=pipe_input,
            app_output=DummyOutput(),
        )

    assert result.kind == "CHANGE_DESTINATION"
    assert result.destination == "result/draf"


def test_compact_destination_keeps_printable_q_as_name_input():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B" * 3 + "\rq\r")
        result = run_compact_resolution_decisions(
            _view,
            selected_option=lambda _uid: None,
            stage_option=lambda _uid, _option_uid: None,
            build_continue_action=lambda _uid: None,
            continue_label=lambda: "Apply",
            destination=SaveLocationView(value="result/draft"),
            app_input=pipe_input,
            app_output=DummyOutput(),
        )

    assert result.kind == "CHANGE_DESTINATION"
    assert result.destination == "result/draftq"


def test_compact_destination_escape_returns_before_root_close():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B" * 3 + "\r\x1b\x1b")
        result = run_compact_resolution_decisions(
            _view,
            selected_option=lambda _uid: None,
            stage_option=lambda _uid, _option_uid: None,
            build_continue_action=lambda _uid: None,
            continue_label=lambda: "Apply",
            destination=SaveLocationView(value="result/draft"),
            app_input=pipe_input,
            app_output=DummyOutput(),
        )

    assert result.kind == "CLOSE"
