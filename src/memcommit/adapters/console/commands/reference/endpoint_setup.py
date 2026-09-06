"""Exact-Memory input form for interactive Reference."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.reference import command_codec
from memcommit.adapters.console.terminal.components.command_editor import CommandReview
from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointCommandBinding,
    EndpointSetupDraft,
    EndpointSetupMemory,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
    run_endpoint_setup,
)
from memcommit.application.operations.reference.application import (
    ContextReferenceRequest,
    FrozenContextReferencePlan,
    FrozenReferencePlan,
    ReferenceRequest,
)
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class ReferenceTuiSetup:
    """Freeze READ-capable Sources and the narrower local Target catalog."""

    names: tuple[str, ...]
    selected_source: str
    selected_target: str
    current_context: str | None = None
    memory_source_names: tuple[str, ...] = ()
    memory_source_selectable_names: frozenset[str] = frozenset()
    selected_memory_source: str | None = None
    memory_source_annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Reference TUI requires a local Context catalog.")
        if self.selected_target not in self.names:
            raise ValueError("Reference TUI initial Target Context is unavailable.")
        if self.current_context is not None and self.current_context not in self.names:
            raise ValueError("Reference TUI current Context must be local.")

        memory_names = self.memory_source_names or self.names
        selectable = self.memory_source_selectable_names or frozenset(memory_names)
        selected_memory = self.selected_memory_source or self.selected_source
        if (
            not memory_names
            or len(set(memory_names)) != len(memory_names)
            or any(not isinstance(name, str) or not name for name in memory_names)
            or not set(self.names) <= set(memory_names)
            or not set(self.names) <= selectable
            or not selectable <= set(memory_names)
            or selected_memory not in selectable
        ):
            raise ValueError("Reference TUI Memory Source authority is invalid.")
        annotation_names = tuple(name for name, _ in self.memory_source_annotations)
        if len(set(annotation_names)) != len(annotation_names) or not set(
            annotation_names
        ) <= set(memory_names):
            raise ValueError("Reference TUI Memory Source annotations are invalid.")

        object.__setattr__(self, "memory_source_names", memory_names)
        object.__setattr__(self, "memory_source_selectable_names", selectable)
        object.__setattr__(self, "selected_memory_source", selected_memory)

    @property
    def target_names(self) -> tuple[str, ...]:
        return self.names


def reference_endpoint_setup_spec(setup: ReferenceTuiSetup) -> EndpointSetupSpec:
    """Project Reference as Target Context plus one exact Source Memory."""

    if not isinstance(setup, ReferenceTuiSetup):
        raise TypeError("Reference endpoint setup requires a ReferenceTuiSetup.")
    height = min(9, max(4, len(setup.memory_source_names)))
    return EndpointSetupSpec(
        title="NEW REFERENCE",
        subtitle="CHOOSE TARGET CONTEXT AND SOURCE MEMORY",
        modes=(
            EndpointSetupMode(
                "REFERENCE",
                "REFERENCE · SOURCE MEMORY",
                active_role_uids=("TARGET", "SOURCE"),
                descendant_role_uids=frozenset(),
                memory_focus_role_uids=frozenset({"SOURCE"}),
            ),
        ),
        initial_mode_uid="REFERENCE",
        roles=(
            EndpointSetupRole(
                "TARGET",
                "TARGET CONTEXT",
                setup.target_names,
                frozenset(setup.target_names),
                setup.selected_target,
                current_context=setup.current_context,
                height=height,
            ),
            EndpointSetupRole(
                "SOURCE",
                "SOURCE MEMORY",
                setup.memory_source_names,
                setup.memory_source_selectable_names,
                setup.selected_memory_source or setup.selected_source,
                current_context=setup.current_context,
                annotations=setup.memory_source_annotations,
                height=height,
                allow_memory_focus=True,
                memory_required=True,
                memory_unselected_label="CHOOSE MEMORY",
                memory_height=7,
            ),
        ),
        action_label="RETAIN SOURCE MEMORY",
        command_verb="REFERENCE",
        command_ready_hint="ENTER TO PROCEED",
        screen_layout="FORM",
    )


def _validate_reference_draft(draft: EndpointSetupDraft) -> str | None:
    if draft.mode_uid != "REFERENCE":
        return "Reference requires the exact-Memory shape."
    source = draft.value("SOURCE")
    if source.memory_uid is None:
        return "SOURCE MEMORY requires one directly owned Memory."
    if draft.value("TARGET").create or source.create:
        return "Reference requires existing Source and Target Contexts."
    return None


def _endpoint_memories(
    loader: Callable[[str], Sequence[ContextMemoryRow]],
) -> Callable[[str, str], tuple[EndpointSetupMemory, ...]]:
    def load(_role_uid: str, context_name: str) -> tuple[EndpointSetupMemory, ...]:
        rows = tuple(loader(context_name))
        if any(row.selector is None for row in rows):
            raise ValueError("Reference Memory projections require exact selectors.")
        return tuple(
            EndpointSetupMemory(context_name, row.selector, row.content)
            for row in rows
            if row.selector is not None
        )

    return load


def reference_exact_command_review(request: ReferenceRequest) -> CommandReview:
    """Build the established exact-Memory Reference command review."""

    if request.into_locator is None:
        raise ValueError("Reference review requires an exact Target Context.")
    return command_codec.build_review(
        EndpointSetupDraft(
            "REFERENCE",
            (
                EndpointSetupValue("TARGET", request.into_locator),
                EndpointSetupValue(
                    "SOURCE",
                    request.source_locator,
                    memory_uid=request.memory_selector,
                ),
            ),
        )
    )


def context_reference_exact_command_review(
    request: ContextReferenceRequest,
) -> CommandReview:
    """Retain the explicit-CLI Context review outside interactive setup."""

    if request.into_locator is None:
        raise ValueError("Reference review requires an exact Target Context.")
    scope = "--recursive" if request.include_descendants else "--direct"
    scope_text = (
        "lexical descendants and authorized embedded Context contents"
        if request.include_descendants
        else "only the Source Context's direct contents; embedded rows stay opaque"
    )
    return CommandReview(
        argv=(
            "mem",
            "reference",
            request.source_locator,
            "--into",
            request.into_locator,
            scope,
        ),
        effects=(
            f"Only Context '{request.into_locator}' changes.",
            (
                f"Context '{request.source_locator}' remains independently owned; "
                f"the Target retains {scope_text}."
            ),
            "The new snapshot is read-only and does not follow later Source edits.",
        ),
    )


def run_reference_tui(
    setup: ReferenceTuiSetup,
    *,
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]],
    prepare: Callable[[ReferenceRequest], FrozenReferencePlan],
    prepare_context: Callable[[ContextReferenceRequest], FrozenContextReferencePlan]
    | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenReferencePlan | None:
    """Freeze one exact Memory after the shared Endpoint Setup form returns."""

    del prepare_context  # Compatibility only; bare interactive setup is exact-Memory.
    spec = reference_endpoint_setup_spec(setup)
    draft = run_endpoint_setup(
        spec,
        memory_loader=_endpoint_memories(memory_loader),
        validate_draft=_validate_reference_draft,
        command_editor=EndpointCommandBinding(
            form=command_codec.REFERENCE_COMMAND_FORM,
            review=command_codec.build_review,
            parse=command_codec.parse_endpoint_argv,
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    source = draft.value("SOURCE")
    if source.memory_uid is None:  # The validator makes this unreachable.
        raise RuntimeError("Reference endpoint setup lost its exact Memory.")
    return prepare(
        ReferenceRequest(
            source.memory_uid,
            source.context_name,
            draft.value("TARGET").context_name,
        )
    )


__all__ = [
    "ReferenceTuiSetup",
    "context_reference_exact_command_review",
    "reference_endpoint_setup_spec",
    "reference_exact_command_review",
    "run_reference_tui",
]
