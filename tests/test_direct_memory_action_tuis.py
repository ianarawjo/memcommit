"""Shared direct-Memory selector flows for Reference and Edit."""

from __future__ import annotations

import shlex

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
)
from memcommit.application.operations.edit.application import (
    EditRequest,
    FrozenEditPlan,
)
from memcommit.adapters.console.terminal.components.command_editor import (
    format_exact_command,
)
from memcommit.adapters.console.commands.edit.workbench import (
    EditTuiSetup,
    parse_edit_command_argv,
    run_edit_tui,
)
from memcommit.adapters.console.commands.edit.workbench.screen import (
    edit_exact_command_review,
)
from memcommit.adapters.console.commands.reference.workbench import (
    ReferenceTuiSetup,
    run_reference_tui,
)
from memcommit.application.operations.reference.application import (
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
        # Target is already local/current. Move to Exact Memory, confirm its
        # Source Context, open the transient list, choose the first Memory,
        # then Enter on the proposed command.
        pipe_input.send_text("\x1b[B\r\r\r\x1b[B\r")
        result = run_reference_tui(
            ReferenceTuiSetup(
                names=("source", "target"),
                selected_source="source",
                selected_target="target",
            ),
            memory_loader=_memory_rows,
            prepare=prepare,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [ReferenceRequest(MEMORY_UID, "source", "target")]


def test_reference_command_reprojects_memory_owner_and_target_before_freeze() -> None:
    requests: list[ReferenceRequest] = []

    def prepare(request: ReferenceRequest) -> FrozenReferencePlan:
        requests.append(request)
        return FrozenReferencePlan(
            request=request,
            source_name=request.source_locator,
            source_uid="other-context-uid",
            source_digest="other-context-digest",
            memory_uid=request.memory_selector,
            memory_content="other old content",
            memory_content_sha256="other-memory-digest",
            into_name=request.into_locator or "source",
            into_uid="source-context-uid",
            into_digest="source-context-digest",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        # Down reaches Exact Memory and then Proposed Command. A complete edit
        # atomically changes Target, owning Context, and exact Memory in the
        # upper form; the same Enter freezes that synchronized request.
        pipe_input.send_text(
            "\x1b[B\x1b[B"
            + f"{OTHER_MEMORY_UID[:8]} --from other --into source"
            + "\r"
        )
        result = run_reference_tui(
            ReferenceTuiSetup(
                names=("source", "other"),
                selected_source="source",
                selected_target="other",
            ),
            memory_loader=_memory_rows,
            prepare=prepare,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [ReferenceRequest(OTHER_MEMORY_UID, "other", "source")]


def test_reference_owner_qualified_memory_input_reprojects_the_command() -> None:
    requests: list[ReferenceRequest] = []

    def prepare(request: ReferenceRequest) -> FrozenReferencePlan:
        requests.append(request)
        return FrozenReferencePlan(
            request=request,
            source_name=request.source_locator,
            source_uid="other-context-uid",
            source_digest="other-context-digest",
            memory_uid=request.memory_selector,
            memory_content="other old content",
            memory_content_sha256="other-memory-digest",
            into_name=request.into_locator or "source",
            into_uid="source-context-uid",
            into_digest="source-context-digest",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        # Enter resolves CONTEXT:UID into the owner and full Memory identity.
        # Down then reaches the reprojected command for exact approval.
        pipe_input.send_text(
            "\x1b[B\x15" + f"other:{OTHER_MEMORY_UID[:8]}" + "\r\x1b[B\r"
        )
        result = run_reference_tui(
            ReferenceTuiSetup(
                names=("source", "other"),
                selected_source="source",
                selected_target="source",
            ),
            memory_loader=_memory_rows,
            prepare=prepare,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [ReferenceRequest(OTHER_MEMORY_UID, "other", "source")]


def test_reference_bare_uid_input_resolves_only_inside_the_retained_owner() -> None:
    requests: list[ReferenceRequest] = []

    def prepare(request: ReferenceRequest) -> FrozenReferencePlan:
        requests.append(request)
        return FrozenReferencePlan(
            request=request,
            source_name=request.source_locator,
            source_uid="other-context-uid",
            source_digest="other-context-digest",
            memory_uid=request.memory_selector,
            memory_content="other old content",
            memory_content_sha256="other-memory-digest",
            into_name=request.into_locator or "source",
            into_uid="source-context-uid",
            into_digest="source-context-digest",
            token=object(),
        )

    with create_pipe_input() as pipe_input:
        # The row already retains "other" as its explicit owner. A bare UID
        # prefix is resolved only inside that owner, then shown canonically as
        # other:FULL_UID before the exact command can run.
        pipe_input.send_text(
            "\x1b[B\x15" + OTHER_MEMORY_UID[:8] + "\r\x1b[B\r"
        )
        result = run_reference_tui(
            ReferenceTuiSetup(
                names=("source", "other"),
                selected_source="other",
                selected_target="source",
            ),
            memory_loader=_memory_rows,
            prepare=prepare,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is not None
    assert requests == [ReferenceRequest(OTHER_MEMORY_UID, "other", "source")]


def test_reference_double_colon_locator_never_freezes() -> None:
    requests: list[ReferenceRequest] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\x1b[B\x15" + f"other::{OTHER_MEMORY_UID[:8]}" + "\r\x1b"
        )
        result = run_reference_tui(
            ReferenceTuiSetup(
                names=("source", "other"),
                selected_source="source",
                selected_target="source",
            ),
            memory_loader=_memory_rows,
            prepare=lambda request: requests.append(request),  # type: ignore[arg-type,return-value]
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is None
    assert requests == []


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
