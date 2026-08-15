"""Meld-style endpoint setup adapter for deterministic Merge."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.interfaces.tui.components.endpoint_setup import (
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.interfaces.tui.operations.merge.model import MergeTuiSetup
from memcommit.merge_application import MergeReach, MergeRequest


def merge_endpoint_setup_spec(setup: MergeTuiSetup) -> EndpointSetupSpec:
    """Project frozen Merge authority into the common role-based setup."""

    if not isinstance(setup, MergeTuiSetup):
        raise TypeError("Merge endpoint setup requires a MergeTuiSetup.")
    return EndpointSetupSpec(
        title="NEW MERGE · A → B",
        subtitle="DETERMINISTIC UID UNION · SETUP BEFORE FROZEN PLAN REVIEW",
        modes=(
            EndpointSetupMode(
                MergeReach.DIRECT.value,
                "DIRECT · A → B",
                "Merge the two exact Context roots only.",
            ),
            EndpointSetupMode(
                MergeReach.DESCENDANTS.value,
                "RECURSIVE · A/** → B/**",
                "Align lexical descendants by complete relative path.",
            ),
        ),
        initial_mode_uid=(
            MergeReach.DESCENDANTS.value
            if setup.initial_recursive
            else MergeReach.DIRECT.value
        ),
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE · ALL READABLE CONTEXTS",
                setup.names,
                setup.selectable_names,
                setup.selected_source,
                current_context=setup.current_context,
                annotations=setup.annotations,
                height=min(10, max(4, len(setup.names))),
            ),
            EndpointSetupRole(
                "B",
                "B · CURRENT TARGET",
                (setup.target_context,),
                frozenset({setup.target_context}),
                setup.target_context,
                current_context=setup.target_context,
                fixed=True,
                height=2,
            ),
        ),
        action_label="CONTINUE TO FROZEN MERGE PLAN",
    )


def choose_merge_setup(
    setup: MergeTuiSetup,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MergeRequest | None:
    """Return one typed Merge request without freezing or applying it."""

    draft = run_endpoint_setup(
        merge_endpoint_setup_spec(setup),
        validate_draft=lambda value: (
            "Merge Source A and Target B must be distinct."
            if value.value("A").context_name == value.value("B").context_name
            else None
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    return MergeRequest(
        source_locator=draft.value("A").context_name,
        target_locator=draft.value("B").context_name,
        reach=MergeReach(draft.mode_uid),
    )
