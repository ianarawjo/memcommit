"""Editable proposed-command form and identifier display contracts."""

from memcommit.adapters.console.terminal.components.command_editor.model import CommandReview
from memcommit.adapters.console.terminal.components.command_editor import (
    CommandEditorControl,
    CommandDraft,
    CommandForm,
    CommandFormField,
    resolve_displayed_command_value,
    shortest_unique_identifier_prefix,
)


def _form() -> CommandForm:
    return CommandForm(
        command=("mem", "sample"),
        usage="mem sample VALUE --into TARGET",
        fields=(
            CommandFormField("VALUE", "one value"),
            CommandFormField("--into TARGET", "one target"),
        ),
    )


def test_exact_command_draft_round_trips_through_operation_owned_state() -> None:
    state = {"value": "before", "target": "one"}

    def review() -> CommandReview:
        return CommandReview(
            (
                "mem",
                "sample",
                state["value"],
                "--into",
                state["target"],
            ),
            ("No durable action has run.",),
        )

    def apply_argv(argv: tuple[str, ...]) -> None:
        assert argv[:2] == ("mem", "sample")
        assert argv[3] == "--into"
        state["value"], state["target"] = argv[2], argv[4]

    draft = CommandDraft(review=review, apply_argv=apply_argv, form=_form())

    assert draft.accept_review() == "mem sample before --into one"
    assert draft.synchronize("mem sample 'two words' --into second")
    assert state == {"value": "two words", "target": "second"}
    assert draft.valid
    assert not draft.error


def test_exact_command_draft_rejects_cross_operation_edits_without_partial_state() -> None:
    applied = []
    draft = CommandDraft(
        review=lambda: CommandReview(
            ("mem", "sample", "value", "--into", "target"),
            ("No durable action has run.",),
        ),
        apply_argv=lambda argv: applied.append(argv),
        form=_form(),
    )

    assert not draft.synchronize("mem delete target")
    assert "edits only 'mem sample'" in draft.error
    assert not draft.valid
    assert applied == []


def test_editable_command_is_always_visible_and_syncs_in_both_directions() -> None:
    state = {"value": "before", "target": "one"}

    def review() -> CommandReview:
        return CommandReview(
            ("mem", "sample", state["value"], "--into", state["target"]),
            ("No durable action has run.",),
        )

    def apply_argv(argv: tuple[str, ...]) -> None:
        if len(argv) != 5 or argv[3] != "--into":
            raise ValueError("Complete VALUE and --into TARGET are required.")
        state["value"], state["target"] = argv[2], argv[4]

    control = CommandEditorControl.create(
        CommandDraft(review=review, apply_argv=apply_argv, form=_form()),
        action_label="APPLY SAMPLE",
        incomplete_action="FIX SAMPLE COMMAND",
        input_name="sample-proposed-command",
    )

    assert control.command_prefix == "mem sample"
    assert control.input.text == "before --into one"
    assert control.command_line() == "mem sample before --into one"
    assert control.frame_title == "COMMAND · RUNNABLE"
    assert control.frame_style() == "class:memcommit.focused"
    control.input.text = "changed --into two"
    assert state == {"value": "changed", "target": "two"}
    assert control.valid

    state.update(value="upper", target="three")
    assert control.sync_from_review()
    assert control.input.text == "upper --into three"
    assert control.command_line() == "mem sample upper --into three"


def test_editable_command_box_turns_red_while_live_input_is_invalid() -> None:
    applied = []

    def apply_argv(argv: tuple[str, ...]) -> None:
        if len(argv) != 5 or argv[3] != "--into":
            raise ValueError("Complete VALUE and --into TARGET are required.")
        applied.append(argv)

    control = CommandEditorControl.create(
        CommandDraft(
            review=lambda: CommandReview(
                ("mem", "sample", "value", "--into", "target"),
                ("No durable action has run.",),
            ),
            apply_argv=apply_argv,
            form=_form(),
        ),
        action_label="APPLY SAMPLE",
        incomplete_action="FIX SAMPLE COMMAND",
        input_name="invalid-sample-proposed-command",
    )

    control.input.text = "mem delete target"

    assert not control.valid
    assert applied == []
    assert control.command_prefix == "mem sample"
    assert control.command_line() == "mem sample mem delete target"
    assert control.frame_title == "COMMAND · INVALID"
    assert control.frame_style() == "class:impact.remove"
    assert "bg:" not in control._input_style()
    assert "underline" not in control._input_style()
    assert "Complete VALUE and --into TARGET" in control.draft.error


def test_empty_incomplete_command_seed_hides_redundant_error_body() -> None:
    def incomplete_review() -> CommandReview:
        raise ValueError("EXACT MEMORY requires one exact Memory.")

    def require_complete(argv: tuple[str, ...]) -> None:
        if len(argv) != 5 or argv[3] != "--into":
            raise ValueError("Complete VALUE and --into TARGET are required.")

    control = CommandEditorControl.create(
        CommandDraft(
            review=incomplete_review,
            apply_argv=require_complete,
            form=_form(),
        ),
        action_label="APPLY SAMPLE",
        incomplete_action="FIX SAMPLE COMMAND",
        input_name="empty-invalid-sample-proposed-command",
    )

    assert control.input.text == ""
    assert control.frame_title == "COMMAND · INVALID"
    assert not control._shows_error()

    control.input.text = "partial"

    assert control._shows_error()
    assert "Complete VALUE and --into TARGET" in control.draft.error


def test_editor_observes_upper_changes_without_erasing_unrepaired_invalid_text() -> None:
    state = {"value": "before", "target": "one"}

    def review() -> CommandReview:
        return CommandReview(
            ("mem", "sample", state["value"], "--into", state["target"]),
            ("No durable action has run.",),
        )

    def apply_argv(argv: tuple[str, ...]) -> None:
        if len(argv) != 5 or argv[3] != "--into":
            raise ValueError("Complete VALUE and --into TARGET are required.")
        state["value"], state["target"] = argv[2], argv[4]

    control = CommandEditorControl.create(
        CommandDraft(review=review, apply_argv=apply_argv, form=_form()),
        action_label="APPLY SAMPLE",
        incomplete_action="FIX SAMPLE COMMAND",
        input_name="observed-sample-proposed-command",
    )
    control.input.text = "incomplete"

    assert not control.valid
    assert control.sync_if_review_changed() is False
    assert control.input.text == "incomplete"

    state.update(value="upper", target="two")
    assert control.sync_if_review_changed() is True
    assert control.input.text == "upper --into two"


def test_identifier_prefix_uses_seven_characters_until_a_collision_requires_more() -> None:
    first = "61782694-bb0b-4422-9ea5-af9975218df0"
    second = "6178269f-1111-2222-3333-444444444444"
    unrelated = "abcdef00-1111-2222-3333-444444444444"

    assert shortest_unique_identifier_prefix(first, (first, unrelated)) == "6178269"
    assert shortest_unique_identifier_prefix(first, (first, second)) == "61782694"


def test_command_catalog_resolves_the_terminal_escaped_identity() -> None:
    raw = "scope/current\u202e"

    assert resolve_displayed_command_value(
        r"scope/current\u202e",
        (raw, "safe"),
        label="Target",
    ) == raw
