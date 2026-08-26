"""Project Sever's frozen authority into shared Endpoint Setup."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import AbstractSet

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.context_targeting.naming import validate_portable_context_name
from memcommit.context_targeting.tui.picker import ContextMemoryRow
from memcommit.application.interactive_command_review import sever_start_command_review
from memcommit.interfaces.tui.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupMemory,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.source_projection.presentation import SourceDisplayValue
from memcommit.interfaces.tui.operations.sever.model import (
    SeverEndpointSelection,
    SeverSetupReceipt,
    SeverTuiSetup,
)


def _shared_local_output_name(
    source_name: str,
    criteria_name: str,
    *,
    local_names: Sequence[str],
    occupied_names: AbstractSet[str],
) -> str:
    """Choose a fresh result under the deepest shared ordinary ancestor."""

    source_parts = source_name.split("/")
    criteria_parts = criteria_name.split("/")
    shared_parts: list[str] = []
    for source_part, criteria_part in zip(source_parts, criteria_parts):
        if source_part != criteria_part:
            break
        shared_parts.append(source_part)
    local = frozenset(local_names)
    output_base = next(
        (
            "/".join(shared_parts[:depth])
            for depth in range(len(shared_parts), 0, -1)
            if "/".join(shared_parts[:depth]) in local
        ),
        None,
    )
    output_stem = f"{output_base}/severed" if output_base else "severed"
    default_output = output_stem
    suffix = 2
    while default_output in occupied_names:
        default_output = f"{output_stem}-{suffix}"
        suffix += 1
    return default_output


def sever_endpoint_setup_spec(setup: SeverTuiSetup) -> EndpointSetupSpec:
    """Build Sever's Source, Criteria, and save-location role pane."""

    if not isinstance(setup, SeverTuiSetup):
        raise TypeError("Sever endpoint setup requires a SeverTuiSetup.")
    annotations = tuple(setup.annotations)
    height = min(9, max(4, len(setup.names)))

    def suggest_output(values: Mapping[str, str]) -> str:
        return _shared_local_output_name(
            values.get("SOURCE", setup.source_name),
            values.get("CRITERIA", setup.criteria_name),
            local_names=setup.local_names,
            occupied_names=frozenset(setup.names),
        )

    initial_output = suggest_output(
        {"SOURCE": setup.source_name, "CRITERIA": setup.criteria_name}
    )
    return EndpointSetupSpec(
        title="NEW SEVER · SOURCE × CRITERIA → RESULT",
        subtitle="CHOOSE TWO READABLE INPUTS AND ONE LOCAL SAVE LOCATION",
        modes=(
            EndpointSetupMode(
                "SEVER",
                "SEVER · SOURCE × CRITERIA → RESULT",
                "Source and Criteria are read together; Result is reviewed later.",
            ),
        ),
        initial_mode_uid="SEVER",
        screen_layout="COMPACT_FORM",
        roles=(
            EndpointSetupRole(
                "SOURCE",
                "SOURCE · ALL READABLE CONTEXTS",
                setup.names,
                setup.selectable_names,
                setup.source_name,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_descendants=True,
                include_descendants=True,
                allow_memory_focus=True,
                memory_preview_only=True,
                memory_height=7,
            ),
            EndpointSetupRole(
                "CRITERIA",
                "CRITERIA · ALL READABLE CONTEXTS",
                setup.names,
                setup.selectable_names,
                setup.criteria_name,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_descendants=True,
                include_descendants=True,
                allow_memory_focus=True,
                memory_preview_only=True,
                memory_height=7,
            ),
            EndpointSetupRole(
                "OUTPUT",
                "RESULT · SOURCE OR NEW LOCAL CONTEXT",
                setup.local_names,
                frozenset(setup.local_names),
                (
                    setup.source_name
                    if setup.source_name in setup.local_names
                    else setup.local_names[0]
                ),
                current_context=setup.current_context,
                height=min(9, max(3, len(setup.local_names))),
                allow_new=True,
                new_label="CREATE NEW RESULT CONTEXT",
                initial_new_name=initial_output,
                prefer_new=True,
                new_name_validator=validate_portable_context_name,
                new_name_suggester=suggest_output,
            ),
        ),
        action_label="START SEVER",
        command_verb="START",
    )


def choose_sever_endpoint_setup(
    setup: SeverTuiSetup,
    *,
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SeverEndpointSelection | None:
    """Return one typed Sever scope without provider or durable work."""

    def load_memories(
        role_uid: str,
        context_name: str,
    ) -> tuple[EndpointSetupMemory, ...]:
        if role_uid not in {"SOURCE", "CRITERIA"}:
            raise ValueError("Sever Memory preview received an unknown role.")
        if memory_loader is None:
            return ()
        return tuple(
            EndpointSetupMemory(context_name, row.selector, row.content)
            for row in memory_loader(context_name)
            if row.selector is not None
        )

    def command_review(draft: EndpointSetupDraft):
        source = draft.value("SOURCE")
        criteria = draft.value("CRITERIA")
        output = draft.value("OUTPUT")
        return sever_start_command_review(
            source_name=source.context_name,
            criteria_name=criteria.context_name,
            output_name=output.context_name,
            source_descendants=source.include_descendants,
            criteria_descendants=criteria.include_descendants,
        )

    draft = run_endpoint_setup(
        sever_endpoint_setup_spec(setup),
        memory_loader=load_memories,
        validate_draft=lambda draft: _validate_sever_draft(setup, draft),
        command_review=command_review,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    if draft.mode_uid != "SEVER":
        raise ValueError("Sever setup returned an unsupported operation shape.")
    source = draft.value("SOURCE")
    criteria = draft.value("CRITERIA")
    output = draft.value("OUTPUT")
    return SeverEndpointSelection(
        source_name=source.context_name,
        criteria_name=criteria.context_name,
        output_name=output.context_name,
        source_descendants=source.include_descendants,
        criteria_descendants=criteria.include_descendants,
    )


def _validate_sever_draft(
    setup: SeverTuiSetup,
    draft: EndpointSetupDraft,
) -> str | None:
    """Keep save-mode and readable-role policy outside shared mechanics."""

    source = draft.value("SOURCE")
    criteria = draft.value("CRITERIA")
    output = draft.value("OUTPUT")
    if source.context_name == criteria.context_name:
        return "Source and Criteria must be distinct Contexts."
    try:
        validate_portable_context_name(output.context_name)
    except (TypeError, ValueError) as error:
        return str(error)
    if output.context_name == source.context_name:
        if source.context_name not in setup.local_names:
            return "Self-save requires an ordinary local Source Context."
        if source.include_descendants:
            return "Self-save requires THIS CONTEXT ONLY for Source."
        return None
    if output.context_name in setup.names:
        return "Other-save requires a new Context name; only Source may already exist."
    return None


def choose_sever_setup(
    local_names: Sequence[str],
    *,
    current: str | None,
    virtual_names: Sequence[str] = (),
    selectable_virtual_names: AbstractSet[str] = frozenset(),
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SeverSetupReceipt | None:
    """Compatibility-shaped entry over the operation-owned role-pane setup."""

    local = tuple(local_names)
    virtual = tuple(virtual_names)
    names = (*local, *virtual)
    selectable = frozenset(local) | frozenset(selectable_virtual_names)
    first = current if current in selectable else local[0] if local else ""
    second = next((name for name in names if name in selectable and name != first), "")
    setup = SeverTuiSetup(
        names=names,
        local_names=local,
        selectable_names=selectable,
        source_name=first,
        criteria_name=second,
        current_context=current,
        annotations=tuple((annotations or {}).items()),
    )
    return choose_sever_endpoint_setup(
        setup,
        memory_loader=memory_loader,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
