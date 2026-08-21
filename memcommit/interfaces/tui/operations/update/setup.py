"""Project Update's frozen authority into shared Endpoint Setup."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.interfaces.tui.components.endpoint_setup import (
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.interfaces.tui.components.endpoint_setup.memory_focus import (
    MemoryProjectionLoader,
)
from memcommit.interfaces.tui.operations.update.model import (
    UpdateEndpointSelection,
    UpdateTuiSetup,
)
from memcommit.interactive_command_review import update_start_command_review


def update_endpoint_setup_spec(setup: UpdateTuiSetup) -> EndpointSetupSpec:
    """Build Update's independently scoped Source and Target roles."""

    if not isinstance(setup, UpdateTuiSetup):
        raise TypeError("Update endpoint setup requires an UpdateTuiSetup.")
    selectable = frozenset(setup.names)
    annotations = tuple(setup.annotations)
    height = min(10, max(4, len(setup.names)))
    return EndpointSetupSpec(
        title="NEW UPDATE · A → B",
        subtitle="SETUP ONLY · NO PLAN, PROVIDER, SESSION, OR APPLY",
        modes=(
            EndpointSetupMode(
                "UPDATE",
                "UPDATE · A → B",
                "A supplies evidence; B remains the materialization target.",
            ),
        ),
        initial_mode_uid="UPDATE",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE · ALL READABLE CONTEXTS",
                setup.names,
                selectable,
                setup.source_name,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_descendants=True,
                allow_memory_focus=True,
                memory_height=8,
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET · AUTHORITY CHECKED BEFORE PLANNING",
                setup.names,
                selectable,
                setup.target_name,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_descendants=True,
                allow_memory_focus=True,
                memory_height=8,
            ),
        ),
        action_label="CONTINUE TO UPDATE PLANNING",
    )


def choose_update_endpoint_setup(
    setup: UpdateTuiSetup,
    *,
    memory_loader: MemoryProjectionLoader,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> UpdateEndpointSelection | None:
    """Return one typed Update scope without planning or durable state."""

    draft = run_endpoint_setup(
        update_endpoint_setup_spec(setup),
        memory_loader=memory_loader,
        validate_draft=lambda value: (
            "A and B must be distinct Contexts."
            if value.value("A").context_name == value.value("B").context_name
            else None
        ),
        command_review=lambda value: update_start_command_review(
            source_name=value.value("A").context_name,
            target_name=value.value("B").context_name,
            source_descendants=value.value("A").include_descendants,
            target_descendants=value.value("B").include_descendants,
            source_memory_uid=value.value("A").memory_uid,
            target_memory_uid=value.value("B").memory_uid,
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    if draft.mode_uid != "UPDATE":
        raise ValueError("Update setup returned an unsupported operation shape.")
    source = draft.value("A")
    target = draft.value("B")
    return UpdateEndpointSelection(
        source_name=source.context_name,
        target_name=target.context_name,
        source_descendants=source.include_descendants,
        target_descendants=target.include_descendants,
        source_memory_uid=source.memory_uid,
        target_memory_uid=target.memory_uid,
    )
