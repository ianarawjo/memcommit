"""Render Merge Setup and pass collected endpoints to application validation."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.endpoint_setup.role import (
    EndpointSetupRole,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.screen import (
    run_endpoint_setup_screen,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.spec import (
    EndpointSetupMode,
    EndpointSetupSpec,
)
from memcommit.application.operations.merge.inputs import (
    MergeRequest,
)
from memcommit.application.operations.merge import setup as merge_setup


def merge_setup_spec(setup: merge_setup.MergeSetup) -> EndpointSetupSpec:
    """Project frozen Merge catalogs into the common role-based setup."""

    if not isinstance(setup, merge_setup.MergeSetup):
        raise TypeError("Merge endpoint setup requires a MergeSetup.")
    return EndpointSetupSpec(
        title="MERGE",
        subtitle="Review changes before applying.",
        mode_label="METHOD",
        modes=(
            EndpointSetupMode("SEMANTIC", "SEMANTIC"),
            EndpointSetupMode("LITERAL", "LITERAL"),
        ),
        initial_mode_uid=setup.method,
        screen_layout="FORM",
        roles=(
            EndpointSetupRole(
                "A",
                "FROM",
                setup.names,
                setup.selectable_names,
                setup.selected_source,
                current_context=setup.current_context,
                annotations=setup.annotations,
            ),
            EndpointSetupRole(
                "B",
                "TO",
                setup.target_names,
                setup.target_selectable_names,
                setup.target_context,
                current_context=setup.current_context,
                annotations=setup.target_annotations,
            ),
        ),
        action_label="Continue",
    )


def choose_merge_request(
    setup: merge_setup.MergeSetup,
    *,
    literal_only: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MergeRequest | None:
    """Collect one request without analysis, provider calls, or publication."""

    def request(draft):
        return setup.request(
            draft.value("A").context_name,
            draft.value("B").context_name,
            method=draft.mode_uid,
            literal_only=literal_only,
        )

    def validate(draft):
        try:
            request(draft)
        except ValueError as error:
            return str(error)
        return None

    draft = run_endpoint_setup_screen(
        merge_setup_spec(setup),
        validate_draft=validate,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    return request(draft)
