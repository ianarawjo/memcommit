"""Compose Compare authority with its interactive console endpoint setup."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    context_access_display_facts,
)
from memcommit.adapters.console.terminal.components.context_picker import context_memory_rows
from memcommit.core.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointSetupMemory,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.memory_focus import (
    MemoryProjectionLoader,
)
from memcommit.persistence.store import MemoryStore
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class CompareTuiSetup:
    """Frozen readable catalog and initial A/B choices supplied by Compare."""

    names: tuple[str, ...]
    reference_name: str
    peer_name: str
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            len(self.names) < 2
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Compare setup requires two distinct readable names.")
        if (
            self.reference_name not in self.names
            or self.peer_name not in self.names
            or self.reference_name == self.peer_name
        ):
            raise ValueError("Compare setup requires distinct available A/B defaults.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Compare setup annotations are outside its catalog.")


@dataclass(frozen=True)
class CompareEndpointSelection:
    """One reviewed Compare scope returned without running the operation."""

    reference_name: str
    peer_name: str
    reference_descendants: bool = False
    peer_descendants: bool = False
    reference_memory_uid: str | None = None
    peer_memory_uid: str | None = None


def compare_endpoint_setup_spec(setup: CompareTuiSetup) -> EndpointSetupSpec:
    """Build Compare's two independent readable endpoint roles."""

    if not isinstance(setup, CompareTuiSetup):
        raise TypeError("Compare endpoint setup requires a CompareTuiSetup.")
    selectable = frozenset(setup.names)
    annotations = tuple(setup.annotations)
    height = min(10, max(4, len(setup.names)))
    return EndpointSetupSpec(
        title="NEW COMPARE · A ↔ B → ANALYSIS",
        subtitle="CHOOSE TWO PEERS · RANGE AND MEMORY FOCUS ARE INDEPENDENT",
        modes=(
            EndpointSetupMode(
                "COMPARE",
                "COMPARE · A ↔ B → ANALYSIS",
                "A and B are peers; REFERENCE sets the report order.",
            ),
        ),
        initial_mode_uid="COMPARE",
        roles=(
            EndpointSetupRole(
                "A",
                "A · REFERENCE · ALL READABLE CONTEXTS",
                setup.names,
                selectable,
                setup.reference_name,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_descendants=True,
                allow_memory_focus=True,
                memory_height=8,
            ),
            EndpointSetupRole(
                "B",
                "B · PEER · ALL READABLE CONTEXTS",
                setup.names,
                selectable,
                setup.peer_name,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_descendants=True,
                allow_memory_focus=True,
                memory_height=8,
            ),
        ),
        action_label="RUN COMPARE",
    )


def choose_compare_endpoint_setup(
    setup: CompareTuiSetup,
    *,
    memory_loader: MemoryProjectionLoader,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> CompareEndpointSelection | None:
    """Return one typed Compare scope without provider or durable work."""

    draft = run_endpoint_setup(
        compare_endpoint_setup_spec(setup),
        memory_loader=memory_loader,
        validate_draft=lambda value: (
            "A and B must be distinct Contexts."
            if value.value("A").context_name == value.value("B").context_name
            else None
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    if draft.mode_uid != "COMPARE":
        raise ValueError("Compare setup returned an unsupported operation shape.")
    reference = draft.value("A")
    peer = draft.value("B")
    return CompareEndpointSelection(
        reference_name=reference.context_name,
        peer_name=peer.context_name,
        reference_descendants=reference.include_descendants,
        peer_descendants=peer.include_descendants,
        reference_memory_uid=reference.memory_uid,
        peer_memory_uid=peer.memory_uid,
    )


@dataclass(frozen=True)
class CompareSetupReceipt:
    """Reviewed process-local arguments for one new Compare command."""

    reference_name: str
    compared_name: str
    reference_descendants: bool = False
    compared_descendants: bool = False
    reference_memory_uid: str | None = None
    compared_memory_uid: str | None = None


def choose_compare_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> CompareSetupReceipt | None:
    """Freeze readable authority, then collect one shared Compare setup."""

    local_names = tuple(store.list_context_names())
    if not local_names:
        raise ValueError("Starting Compare requires an ordinary local Context.")
    current_name = store.current_context_name()
    root_name = current_name if current_name in local_names else local_names[0]
    catalog = freeze_profile_readable_context_catalog(
        store,
        ContextAccess(
            store=store,
            context_name=root_name,
            display_name=root_name,
            attachment_name=None,
            permission="READ",
        ),
        include_query_routes=False,
    )
    names = tuple(catalog.list_context_names())
    if len(names) < 2:
        raise ValueError("Starting Compare requires two readable Contexts.")
    reference_name = current_name if current_name in names else names[0]
    peer_name = next(name for name in names if name != reference_name)
    annotations = tuple(
        (name, context_access_display_facts(catalog.access_for(name)))
        for name in names
        if catalog.access_for(name).is_granted
    )

    def load_memories(role_uid: str, context_name: str):
        if role_uid not in {"A", "B"}:
            raise ValueError("Compare Memory projection received an unknown role.")
        return tuple(
            EndpointSetupMemory(context_name, row.selector, row.content)
            for row in context_memory_rows(catalog.load(context_name))
            if row.selector is not None
        )

    selected = choose_compare_endpoint_setup(
        CompareTuiSetup(
            names=names,
            reference_name=reference_name,
            peer_name=peer_name,
            current_context=current_name,
            annotations=annotations,
        ),
        memory_loader=load_memories,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if selected is None:
        return None
    return CompareSetupReceipt(
        selected.reference_name,
        selected.peer_name,
        reference_descendants=selected.reference_descendants,
        compared_descendants=selected.peer_descendants,
        reference_memory_uid=selected.reference_memory_uid,
        compared_memory_uid=selected.peer_memory_uid,
    )
