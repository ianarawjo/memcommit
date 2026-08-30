"""Interactive endpoint setup for structural Merge."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.application.capabilities.authority.context_access import resolve_context_access
from memcommit.application.operations.merge.application import MergeReach, MergeRequest
from memcommit.application.operations.merge.runtime import MemoryStoreMergePort
from memcommit.core.context_targeting.readable_catalog import (
    freeze_profile_context_navigation,
)
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class MergeSetup:
    """Frozen readable Source and writable Target choices for one launch."""

    names: tuple[str, ...]
    selectable_names: frozenset[str]
    selected_source: str
    target_names: tuple[str, ...]
    target_selectable_names: frozenset[str]
    target_context: str
    initial_recursive: bool = False
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    target_annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Merge setup requires a distinct visible catalog.")
        if not self.selectable_names or not self.selectable_names <= set(self.names):
            raise ValueError("Merge setup requires one readable Source.")
        if self.selected_source not in self.selectable_names:
            raise ValueError("Initial Merge Source is unavailable.")
        if (
            not self.target_names
            or len(set(self.target_names)) != len(self.target_names)
            or any(not isinstance(name, str) or not name for name in self.target_names)
        ):
            raise ValueError("Merge setup requires a distinct Target catalog.")
        if not self.target_selectable_names or not self.target_selectable_names <= set(
            self.target_names
        ):
            raise ValueError("Merge setup requires one CREATE-authorized Target.")
        if self.target_context not in self.target_selectable_names:
            raise ValueError("Initial Merge Target is unavailable.")
        if type(self.initial_recursive) is not bool:
            raise TypeError("Merge setup recursive state must be a boolean.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Merge setup annotations are outside the catalog.")
        target_labels = dict(self.target_annotations)
        if len(target_labels) != len(self.target_annotations) or set(
            target_labels
        ) - set(self.target_names):
            raise ValueError("Merge setup Target annotations are outside the catalog.")


def build_merge_setup(
    port: MemoryStoreMergePort,
    *,
    initial_recursive: bool,
    requested_target: str | None = None,
) -> MergeSetup:
    """Freeze readable Sources and CREATE-authorized Targets for one launch."""

    target = resolve_context_access(
        port.store,
        requested_target,
        current_name=port.current_context_name,
        required_permission="CREATE",
    )
    # ALL READABLE CONTEXTS is Profile-wide. A granted current Target is only
    # orientation, so anchor discovery at its local attachment and retain each
    # Source name's exact frozen READ binding through the common catalog.
    orientation_name = (
        target.attachment_name if target.is_granted else target.display_name
    )
    orientation = resolve_context_access(
        port.store,
        orientation_name,
        current_name=port.current_context_name,
        required_permission="READ",
    )
    navigation = freeze_profile_context_navigation(port.store, orientation)
    source_names = tuple(
        sorted(
            (*navigation.local_names, *navigation.selectable_virtual_names),
            key=str.casefold,
        )
    )
    source_selectable = set(source_names)
    # Target selection has a narrower authority contract than Source
    # selection. Resolve each visible Grant row for CREATE now so a READ-only
    # Source can never be mistaken for a writable Target by the shared picker.
    target_selectable = set(navigation.local_names)
    for name in navigation.virtual_names:
        try:
            access = resolve_context_access(
                port.store,
                name,
                current_name=port.current_context_name,
                required_permission="CREATE",
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            continue
        target_selectable.add(access.display_name)
    # The explicitly resolved initial Target is authoritative even when its
    # public Grant row was reached through a non-local command-start snapshot.
    target_selectable.add(target.display_name)
    target_names = tuple(sorted(target_selectable, key=str.casefold))
    # Keep the initial draft executable when an alternate exists, but do not
    # turn Source/Target distinctness into a disabled picker row. The reviewed
    # endpoint result and runtime own that semantic rejection.
    selected = next(
        (
            name
            for name in sorted(source_selectable, key=str.casefold)
            if name != target.display_name
        ),
        target.display_name,
    )
    return MergeSetup(
        names=source_names,
        selectable_names=frozenset(source_selectable),
        selected_source=selected,
        target_names=target_names,
        target_selectable_names=frozenset(target_selectable),
        target_context=target.display_name,
        initial_recursive=initial_recursive,
        current_context=port.current_context_name,
        annotations=tuple(
            (name, navigation.virtual_annotations[name])
            for name in source_names
            if name in navigation.virtual_annotations
        ),
        target_annotations=tuple(
            (name, navigation.virtual_annotations[name])
            for name in target_names
            if name in navigation.virtual_annotations
        ),
    )


def merge_setup_spec(setup: MergeSetup) -> EndpointSetupSpec:
    """Project frozen Merge catalogs into the common role-based setup."""

    if not isinstance(setup, MergeSetup):
        raise TypeError("Merge endpoint setup requires a MergeSetup.")
    return EndpointSetupSpec(
        title="NEW MERGE · A → B",
        subtitle="REVIEW REQUIRED CONFLICTS BEFORE APPLY",
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
                "B · TARGET · CAN RECEIVE CHANGES",
                setup.target_names,
                setup.target_selectable_names,
                setup.target_context,
                current_context=setup.current_context,
                annotations=setup.target_annotations,
                height=min(10, max(4, len(setup.target_names))),
            ),
        ),
        action_label="REVIEW MERGE PLAN",
    )


def choose_merge_request(
    setup: MergeSetup,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MergeRequest | None:
    """Return one typed Merge request without freezing or applying it."""

    draft = run_endpoint_setup(
        merge_setup_spec(setup),
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
