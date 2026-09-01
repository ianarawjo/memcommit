"""Compose Sever's frozen authority with shared Endpoint Setup."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import AbstractSet

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
)
from memcommit.adapters.console.commands.sever import (
    command_codec as sever_command_review,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointCommandBinding,
    EndpointSetupDraft,
    EndpointSetupMemory,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    normalize_source_display_tokens,
)


@dataclass(frozen=True)
class SeverTuiSetup:
    """Frozen readable inputs and local Source namespace supplied by Sever."""

    names: tuple[str, ...]
    local_names: tuple[str, ...]
    selectable_names: frozenset[str]
    source_name: str
    criteria_name: str
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            len(self.names) < 2
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Sever setup requires two distinct readable names.")
        if (
            not self.local_names
            or len(set(self.local_names)) != len(self.local_names)
            or not set(self.local_names) <= set(self.names)
        ):
            raise ValueError("Sever setup requires a valid local Source namespace.")
        if (
            len(self.selectable_names) < 2
            or not self.selectable_names <= set(self.names)
            or not set(self.local_names) <= self.selectable_names
        ):
            raise ValueError("Sever setup requires two selectable readable Contexts.")
        if (
            self.source_name not in self.selectable_names
            or self.criteria_name not in self.selectable_names
            or self.source_name == self.criteria_name
        ):
            raise ValueError("Sever setup requires distinct available defaults.")
        if self.source_name not in self.local_names:
            raise ValueError("Sever setup requires an ordinary local Source default.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Sever setup annotations are outside its catalog.")
        try:
            if any(
                not normalize_source_display_tokens(annotation)
                for annotation in labels.values()
            ):
                raise ValueError
        except (TypeError, ValueError) as error:
            raise ValueError("Sever setup annotations must not be empty.") from error


@dataclass(frozen=True)
class SeverSetupReceipt:
    """One reviewed in-place Sever scope returned without durable work."""

    source_name: str
    criteria_name: str
    source_descendants: bool = True
    criteria_descendants: bool = True

    def __post_init__(self) -> None:
        if (
            not self.source_name
            or not self.criteria_name
            or self.source_name == self.criteria_name
        ):
            raise ValueError("Sever endpoint selection is incomplete or ambiguous.")


# Endpoint selection and the command receipt are the same frozen setup result.
SeverEndpointSelection = SeverSetupReceipt


def sever_endpoint_setup_spec(setup: SeverTuiSetup) -> EndpointSetupSpec:
    """Build Sever's Source and Criteria role pane."""

    if not isinstance(setup, SeverTuiSetup):
        raise TypeError("Sever endpoint setup requires a SeverTuiSetup.")
    annotations = tuple(setup.annotations)
    height = min(9, max(4, len(setup.names)))

    return EndpointSetupSpec(
        title="NEW SEVER · SOURCE × CRITERIA · IN PLACE",
        subtitle="CHOOSE SOURCE AND CRITERIA; EACH SOURCE CONTEXT STAYS IN PLACE",
        modes=(
            EndpointSetupMode(
                "SEVER",
                "SEVER · SOURCE × CRITERIA · IN PLACE",
                "Source and Criteria are read together; Source owners are updated in place.",
            ),
        ),
        initial_mode_uid="SEVER",
        screen_layout="COMPACT_FORM",
        roles=(
            EndpointSetupRole(
                "SOURCE",
                "SOURCE · LOCAL CONTEXTS · UPDATED IN PLACE",
                setup.names,
                frozenset(setup.local_names),
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
        return sever_command_review.build_start_review(
            source_name=source.context_name,
            criteria_name=criteria.context_name,
            source_descendants=source.include_descendants,
            criteria_descendants=criteria.include_descendants,
        )

    draft = run_endpoint_setup(
        sever_endpoint_setup_spec(setup),
        memory_loader=load_memories,
        validate_draft=lambda draft: _validate_sever_draft(setup, draft),
        command_editor=EndpointCommandBinding(
            form=sever_command_review.SEVER_COMMAND_FORM,
            review=command_review,
            parse=sever_command_review.parse_endpoint_argv,
        ),
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
    return SeverEndpointSelection(
        source_name=source.context_name,
        criteria_name=criteria.context_name,
        source_descendants=source.include_descendants,
        criteria_descendants=criteria.include_descendants,
    )


def _validate_sever_draft(
    setup: SeverTuiSetup,
    draft: EndpointSetupDraft,
) -> str | None:
    """Keep in-place authority policy outside shared mechanics."""

    source = draft.value("SOURCE")
    criteria = draft.value("CRITERIA")
    if source.context_name == criteria.context_name:
        return "Source and Criteria must be distinct Contexts."
    if source.context_name not in setup.local_names:
        return "In-place Sever requires an ordinary local Source Context."
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
