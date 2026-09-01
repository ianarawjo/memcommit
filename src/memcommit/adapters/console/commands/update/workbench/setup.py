"""Project Update's frozen authority into shared Endpoint Setup."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.update.workbench.model import (
    UpdateEndpointSelection,
    UpdateEndpointSetup,
)
from memcommit.adapters.console.commands.update import (
    command_codec as update_command_review,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointCommandBinding,
    EndpointSetupDraft,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.memory_focus import (
    MemoryProjectionLoader,
)


def update_endpoint_setup_spec(setup: UpdateEndpointSetup) -> EndpointSetupSpec:
    """Build Update's independently scoped Source and Target roles."""

    if not isinstance(setup, UpdateEndpointSetup):
        raise TypeError("Update endpoint setup requires an UpdateEndpointSetup.")
    selectable = frozenset(setup.names)
    annotations = tuple(setup.annotations)
    height = min(10, max(4, len(setup.names)))
    return EndpointSetupSpec(
        title="NEW UPDATE · A → B",
        subtitle="CHOOSE SOURCE AND TARGET",
        modes=(
            EndpointSetupMode(
                "UPDATE",
                "UPDATE · A → B",
                "A supplies evidence; B remains the materialization target.",
            ),
        ),
        initial_mode_uid="UPDATE",
        screen_layout="COMPACT_FORM",
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
                allow_inline_memory=True,
                memory_height=8,
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET · CHANGES APPLY HERE",
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
    setup: UpdateEndpointSetup,
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
        validate_draft=lambda value: _validate_update_draft(setup, value),
        command_editor=EndpointCommandBinding(
            form=update_command_review.UPDATE_COMMAND_FORM,
            review=lambda value: update_command_review.build_start_review(
                source_name=(
                    value.value("A").context_name
                    if value.value("A").inline_memory_content is None
                    else None
                ),
                target_name=value.value("B").context_name,
                source_descendants=value.value("A").include_descendants,
                target_descendants=value.value("B").include_descendants,
                source_memory_uid=value.value("A").memory_uid,
                target_memory_uid=value.value("B").memory_uid,
                inline_source_content=value.value("A").inline_memory_content,
            ),
            parse=update_command_review.parse_endpoint_argv,
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
        source_name=(
            source.context_name if source.inline_memory_content is None else None
        ),
        target_name=target.context_name,
        source_descendants=source.include_descendants,
        target_descendants=target.include_descendants,
        source_memory_uid=source.memory_uid,
        target_memory_uid=target.memory_uid,
        inline_source_content=source.inline_memory_content,
    )


def _validate_update_draft(
    setup: UpdateEndpointSetup,
    draft: EndpointSetupDraft,
) -> str | None:
    source = draft.value("A")
    target = draft.value("B")
    if source.inline_memory_content is not None:
        if not setup.allows_inline_target(target.context_name):
            return "Inline Memory Update requires an ordinary local Target Context."
        return None
    if source.context_name == target.context_name:
        return "A and B must be distinct Contexts."
    return None
