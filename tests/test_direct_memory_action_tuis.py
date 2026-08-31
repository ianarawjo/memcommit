"""Shared direct-Memory selector flows for Reference and Edit."""

from __future__ import annotations

import shlex

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.terminal.components.context_picker import ContextMemoryRow
from memcommit.application.operations.direct_changes.edit.application import EditRequest, FrozenEditPlan
from memcommit.adapters.console.terminal.components.command_editor import (
    format_exact_command,
)
from memcommit.adapters.console.commands.direct_changes.edit.workbench import (
    EditTuiSetup,
    parse_edit_command_argv,
    run_edit_tui,
)
from memcommit.adapters.console.commands.direct_changes.edit.workbench.screen import (
    edit_exact_command_review,
)
from memcommit.adapters.console.commands.create_copy_connect.reference.workbench import (
    ReferenceTuiSetup,
    run_reference_tui,
)
from memcommit.application.operations.create_copy_connect.reference.application import (
    ContextReferenceRequest,
    FrozenContextReferencePlan,
    FrozenReferencePlan,
    ReferenceRequest,
)


MEMORY_UID = "abcd1234-0000-0000-0000-000000000000"
OTHER_MEMORY_UID = "ef567890-0000-0000-0000-000000000000"


def _memory_rows(name: str):
    if name == "source":
        return (ContextMemoryRow("abcd1234", "old content", selector=MEMORY_UID),)
    if name == "other":
        return (
            ContextMemoryRow(
                "ef567890",
                "other old content",
                selector=OTHER_MEMORY_UID,
            ),
        )
    return ()


def test_reference_tui_selects_exact_memory_and_target_before_freeze() -> None:
    requests: list[ReferenceRequest] = []

    def prepare(request: ReferenceRequest) -> FrozenReferencePlan:
        requests.append(request)
        return FrozenReferencePlan(
            request=request,
            source_name=request.source_locator,
            source_uid="source-uid",
            source_digest="source-digest",
            memory_uid=request.memory_selector,
            memory_content="old content",
            memory_content_sha256="memory-digest",
            into_name=request.into_locator or "target",
            into_uid="target-uid",
            into_digest="target-digest",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        # Right selects Memory mode, then the direct-Memory row and Target lead
        # to one reviewed exact command.
        pipe_input.send_text("\x1b[C\t\x1b[B\r\t\t\r")
        result = run_reference_tui(
            ReferenceTuiSetup(
                names=("source", "target"),
                selected_source="source",
                selected_target="target",
            ),
            memory_loader=_memory_rows,
            prepare=prepare,
            prepare_context=lambda _request: (_ for _ in ()).throw(
                AssertionError("Memory mode called Context preparation")
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [ReferenceRequest(MEMORY_UID, "source", "target")]


def test_reference_tui_selects_context_scope_and_target_before_freeze() -> None:
    requests: list[ContextReferenceRequest] = []

    def prepare_context(
        request: ContextReferenceRequest,
    ) -> FrozenContextReferencePlan:
        requests.append(request)
        return FrozenContextReferencePlan(
            request=request,
            source_name=request.source_locator,
            source_uid="source-uid",
            source_bindings=(("source", "source-uid", "source-digest"),),
            snapshot_package={
                "schema_version": 1,
                "root": {"uid": "source-uid", "name": "source"},
                "recursive": True,
                "lexical_context_names": ["source"],
                "contexts": [
                    {
                        "uid": "source-uid",
                        "name": "source",
                        "memories": {},
                        "order": [],
                    }
                ],
            },
            snapshot_content_sha256="snapshot-digest",
            into_name=request.into_locator or "target",
            into_uid="target-uid",
            into_digest="target-digest",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        # Context is the default unit. Tab reaches Source, then scope; Right
        # chooses recursive before Target and exact review.
        pipe_input.send_text("\t\t\x1b[C\t\t\r")
        result = run_reference_tui(
            ReferenceTuiSetup(
                names=("source", "target"),
                selected_source="source",
                selected_target="target",
            ),
            memory_loader=_memory_rows,
            prepare=lambda _request: (_ for _ in ()).throw(
                AssertionError("Context mode called Memory preparation")
            ),
            prepare_context=prepare_context,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [
        ContextReferenceRequest(
            "source",
            "target",
            include_descendants=True,
            follow_embeds=True,
        )
    ]


def test_edit_tui_prefills_selected_memory_and_freezes_replacement() -> None:
    requests: list[EditRequest] = []

    def prepare(request: EditRequest) -> FrozenEditPlan:
        requests.append(request)
        return FrozenEditPlan(
            request=request,
            context_name="source",
            context_uid="context-uid",
            context_digest="context-digest",
            memory_uid=MEMORY_UID,
            original_content="old content",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        # Choose the direct Memory, Tab into the prefilled editor, replace the
        # old value, then Tab to the reviewed exact command and apply.
        pipe_input.send_text("\x1b[B\r\t\x15new content\t\r")
        result = run_edit_tui(
            EditTuiSetup(
                names=("source",),
                selectable_names=frozenset({"source"}),
                selected_context="source",
                current_context="source",
            ),
            memory_loader=_memory_rows,
            content_loader=lambda _target: "old content",
            prepare=prepare,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [EditRequest(MEMORY_UID, "new content", "source")]


def test_edit_review_projects_only_the_exact_proposed_command() -> None:
    request = EditRequest(
        MEMORY_UID,
        "new content\nwith a second line",
        "source",
    )

    rendered = format_exact_command(edit_exact_command_review(request))

    assert rendered == (
        "mem edit abcd1234-0000-0000-0000-000000000000 "
        "'new content\\nwith a second line' --context source"
    )
    assert "EFFECTS" not in rendered
    assert "Approval applies" not in rendered
    assert "TO DO" not in rendered


def test_edit_command_parser_round_trips_multiline_and_literal_escapes() -> None:
    request = EditRequest(
        MEMORY_UID,
        "--context\nactual tab\tand literal \\n plus bidi \u202e",
        "source",
    )
    line = format_exact_command(edit_exact_command_review(request))

    assert parse_edit_command_argv(tuple(shlex.split(line))) == request


def test_edit_proposed_command_updates_memory_and_content_before_freeze() -> None:
    requests: list[EditRequest] = []
    content = "from command\nsecond line"
    command = format_exact_command(
        edit_exact_command_review(EditRequest(OTHER_MEMORY_UID, content, "other"))
    )
    arguments = command.removeprefix("mem edit ")

    def prepare(request: EditRequest) -> FrozenEditPlan:
        requests.append(request)
        return FrozenEditPlan(
            request=request,
            context_name="other",
            context_uid="other-context-uid",
            context_digest="other-context-digest",
            memory_uid=OTHER_MEMORY_UID,
            original_content="other old content",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        # The command is reachable before any Memory is selected. A complete
        # valid line stages both the exact row and multiline replacement, then
        # the same Enter freezes that synchronized request.
        pipe_input.send_text("\t\t\x15" + arguments + "\r")
        result = run_edit_tui(
            EditTuiSetup(
                names=("source", "other"),
                selectable_names=frozenset({"source", "other"}),
                selected_context="source",
                current_context="source",
            ),
            memory_loader=_memory_rows,
            content_loader=lambda _target: "unused",
            prepare=prepare,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [EditRequest(OTHER_MEMORY_UID, content, "other")]


def test_direct_memory_action_tuis_cancel_without_freezing() -> None:
    reference_requests: list[ReferenceRequest] = []
    edit_requests: list[EditRequest] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        reference = run_reference_tui(
            ReferenceTuiSetup(("source",), "source", "source"),
            memory_loader=_memory_rows,
            prepare=lambda request: reference_requests.append(request),  # type: ignore[arg-type,return-value]
            prepare_context=lambda _request: (_ for _ in ()).throw(
                AssertionError("cancel reached Context preparation")
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        edit = run_edit_tui(
            EditTuiSetup(("source",), frozenset({"source"}), "source"),
            memory_loader=_memory_rows,
            content_loader=lambda _target: "old content",
            prepare=lambda request: edit_requests.append(request),  # type: ignore[arg-type,return-value]
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert reference is None
    assert edit is None
    assert reference_requests == []
    assert edit_requests == []


def test_direct_memory_action_tuis_ctrl_c_without_freezing() -> None:
    reference_requests: list[ReferenceRequest] = []
    edit_requests: list[EditRequest] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x03")
        reference = run_reference_tui(
            ReferenceTuiSetup(("source",), "source", "source"),
            memory_loader=_memory_rows,
            prepare=lambda request: reference_requests.append(request),  # type: ignore[arg-type,return-value]
            prepare_context=lambda _request: (_ for _ in ()).throw(
                AssertionError("cancel reached Context preparation")
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r\tUncommitted replacement.\x03")
        edit = run_edit_tui(
            EditTuiSetup(("source",), frozenset({"source"}), "source"),
            memory_loader=_memory_rows,
            content_loader=lambda _target: "old content",
            prepare=lambda request: edit_requests.append(request),  # type: ignore[arg-type,return-value]
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert reference is None
    assert edit is None
    assert reference_requests == []
    assert edit_requests == []
