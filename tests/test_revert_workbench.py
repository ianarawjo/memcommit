"""Exact staging, editable command, and approval contracts owned by Revert."""

from __future__ import annotations

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from tests.history_picker_support import entry
from memcommit.adapters.console.commands.revert.review import (
    REVERT_COMMAND_FORM,
    RevertSelectionReceipt,
    parse_revert_command_argv,
    revert_exact_command_review,
)
from memcommit.adapters.console.commands.revert.workbench import choose_revert_history
from memcommit.adapters.console.terminal.components.history.model import HISTORY_BACK
from memcommit.adapters.console.terminal.components.command_editor import (
    format_exact_command,
)


def test_revert_preview_keeps_the_staged_checkpoint_until_an_explicit_selection():
    candidates = (entry(1), entry(2))
    with create_pipe_input() as pipe_input:
        # Stage the first row, browse the second, then approve the original command.
        pipe_input.send_text("\r\x1b[Z\x1b[Z\x1b[B\t\t\r")
        receipt = choose_revert_history(
            candidates,
            context_name="journal",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert receipt == RevertSelectionReceipt("journal", candidates[0].uid, True)


@pytest.mark.parametrize(
    "arguments",
    [
        "111 --context another --keep",
        "333 --context journal --keep",
        "1 --context journal --keep",
        "111 --context journal",
    ],
)
def test_invalid_edited_revert_cannot_return_an_approval(arguments):
    candidates = (entry(1, uid="11111111"), entry(2, uid="12222222"))
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r\x15" + arguments + "\rq")
        receipt = choose_revert_history(
            candidates,
            context_name="journal",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert receipt is None


@pytest.mark.parametrize("formatted", [False, True])
def test_revert_review_preserves_change_anchors_and_custom_unit_effects(formatted):
    from memcommit.adapters.console.commands.revert.review import append_revert_review
    from memcommit.adapters.console.terminal.components.history.model import (
        HistoryDetailView,
    )

    content = [("class:memory", "first\nsecond")] if formatted else "first\nsecond"
    original = HistoryDetailView(content, (0, 1), "CHANGE")
    review = revert_exact_command_review(
        context_name="journal",
        checkpoint_uid="parent-uid",
        keep_history=False,
        affected_checkpoints=(
            ("journal", "parent-uid"),
            ("journal/child", "child-uid"),
        ),
    )
    detail = append_revert_review(original, review)
    assert isinstance(detail, HistoryDetailView)
    assert detail.unit_start_lines == original.unit_start_lines
    assert detail.unit_label == original.unit_label
    text = (
        detail.content
        if isinstance(detail.content, str)
        else "".join(part[1] for part in detail.content)
    )
    assert "first\nsecond" in text
    assert "restore 2 Contexts" in text
    assert "journal/child" in text
    assert "Newer active checkpoint files are removed" in text
    assert original.content == content


def test_empty_revert_does_not_construct_an_approval_editor(monkeypatch):
    from memcommit.adapters.console.terminal.components.command_editor import (
        CommandEditorControl,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Empty history has no writable approval surface")

    monkeypatch.setattr(CommandEditorControl, "create", forbidden)
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\rq")
        receipt = choose_revert_history(
            (),
            context_name="journal",
            empty_message="No checkpoints yet.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert receipt is None


def test_revert_stages_exact_checkpoint_then_jumps_directly_to_proposed_command():
    candidate = entry(1)
    with create_pipe_input() as pipe_input:
        # Items Enter stages the exact UID and focuses the final editable
        # command; the next Enter applies it without a redundant policy stop.
        pipe_input.send_text("\r\r")
        selected = choose_revert_history(
            (candidate,),
            context_name="test/update/to",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == RevertSelectionReceipt(
        context_name="test/update/to",
        checkpoint_uid=candidate.uid,
        keep_history=True,
    )


def test_revert_arrows_move_and_clamp_before_accepting():
    candidates = (entry(1), entry(2), entry(3))
    with create_pipe_input() as pipe_input:
        # Move to the last row, once up, then choose the second row.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[A\r\r")
        selected = choose_revert_history(
            candidates,
            context_name="journal",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is not None
    assert selected.checkpoint_uid == candidates[1].uid
    assert selected.keep_history is True


def test_revert_arrow_boundary_enters_viewer_then_returns_to_items():
    candidates = (entry(1), entry(2))
    with create_pipe_input() as pipe_input:
        # Up from the first Item crosses into the Viewer. Enter returns to
        # Items, where Down must still select the second exact checkpoint.
        pipe_input.send_text("\x1b[A\r\x1b[B\r\r")
        selected = choose_revert_history(
            candidates,
            context_name="journal",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == RevertSelectionReceipt(
        context_name="journal",
        checkpoint_uid=candidates[1].uid,
        keep_history=True,
    )


def test_revert_tui_can_explicitly_discard_newer_checkpoints():
    candidate = entry(1)
    with create_pipe_input() as pipe_input:
        # Items Enter jumps to the command. Shift-Tab returns to History,
        # Left changes the keep-all default to DISCARD NEWER, and Enter returns
        # to the synchronized command before final approval.
        pipe_input.send_text("\r\x1b[Z\x1b[D\r\r")
        selected = choose_revert_history(
            (candidate,),
            context_name="journal",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == RevertSelectionReceipt(
        context_name="journal",
        checkpoint_uid=candidate.uid,
        keep_history=False,
    )


def test_revert_accepts_a_checkpoint_staged_in_the_context_tree():
    candidates = (entry(1), entry(2))
    with create_pipe_input() as pipe_input:
        # The Context tree's exact-version Enter already performed checkpoint
        # selection. The proposed command therefore starts focused, without a
        # redundant second selection of the same UID in Items.
        pipe_input.send_text("\r")
        selected = choose_revert_history(
            candidates,
            context_name="journal",
            staged_checkpoint_uid=candidates[1].uid,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == RevertSelectionReceipt(
        context_name="journal",
        checkpoint_uid=candidates[1].uid,
        keep_history=True,
    )


def test_revert_discard_flag_initializes_the_tui_policy():
    candidate = entry(1)
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r\r")
        selected = choose_revert_history(
            (candidate,),
            context_name="journal",
            keep_history=False,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is not None
    assert selected.keep_history is False


def test_revert_proposed_command_unique_prefix_updates_controls_and_applies():
    candidates = (
        entry(1, uid="11111111-1111-4111-8111-111111111111"),
        entry(2, uid="22222222-2222-4222-8222-222222222222"),
    )
    selector = candidates[1].uid[:8]
    replacement = f"{selector} --context journal --discard-newer"
    with create_pipe_input() as pipe_input:
        # Stage the first row, then use only a unique prefix for another frozen
        # UID. Validation must move Items/Viewer and History before Apply.
        pipe_input.send_text("\r\x15" + replacement + "\r")
        selected = choose_revert_history(
            candidates,
            context_name="journal",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == RevertSelectionReceipt(
        context_name="journal",
        checkpoint_uid=candidates[1].uid,
        keep_history=False,
    )


def test_revert_proposed_command_is_explicit_and_round_trips_unique_prefix():
    candidates = (
        entry(1, uid="11111111-1111-4111-8111-111111111111"),
        entry(2, uid="22222222-2222-4222-8222-222222222222"),
    )
    selector = candidates[1].uid[:8]
    review = revert_exact_command_review(
        context_name="practice/greetings",
        checkpoint_uid=candidates[1].uid,
        keep_history=True,
    )

    assert format_exact_command(review) == (
        f"mem revert {candidates[1].uid} --context practice/greetings --keep"
    )
    assert parse_revert_command_argv(
        (
            *REVERT_COMMAND_FORM.command,
            selector,
            "--context",
            "practice/greetings",
            "--discard-newer",
        ),
        context_name="practice/greetings",
        entries=candidates,
    ) == (candidates[1].uid, False)


def test_revert_proposed_command_rejects_ambiguous_uid_prefix():
    candidates = (entry(1), entry(2))

    with pytest.raises(ValueError, match="matches 2 visible checkpoints"):
        parse_revert_command_argv(
            (
                *REVERT_COMMAND_FORM.command,
                "00000000",
                "--context",
                "practice/greetings",
                "--keep",
            ),
            context_name="practice/greetings",
            entries=candidates,
        )


def test_empty_revert_stays_read_only_until_back_navigation():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r\x1b[B\x7f")
        selected = choose_revert_history(
            (),
            context_name="empty/context",
            initial_details_open=True,
            empty_message="No checkpoints for this Context yet.",
            back_navigation=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is HISTORY_BACK


@pytest.mark.parametrize("key", ["q", "\x1b", "\x7f", "\x03"])
def test_cancel_keys_return_no_receipt(key: str):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(key)
        selected = choose_revert_history(
            (entry(1),),
            context_name="journal",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None
