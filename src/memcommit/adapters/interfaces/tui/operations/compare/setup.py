"""Project Compare's frozen authority into shared Endpoint Setup."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.interfaces.tui.components.endpoint_setup import (
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.adapters.interfaces.tui.components.endpoint_setup.memory_focus import (
    MemoryProjectionLoader,
)
from memcommit.adapters.interfaces.tui.operations.compare.model import (
    CompareEndpointSelection,
    CompareTuiSetup,
)


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
