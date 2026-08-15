"""Project Meld's frozen authority into shared Endpoint Setup."""

from __future__ import annotations

from collections.abc import Callable

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
from memcommit.interfaces.tui.operations.meld.model import (
    MeldEndpointSelection,
    MeldTuiSetup,
)


def meld_endpoint_setup_spec(
    setup: MeldTuiSetup,
    *,
    new_name_validator: Callable[[str], object] | None = None,
) -> EndpointSetupSpec:
    """Build Meld's mode-dependent A/B/C endpoint roles."""

    if not isinstance(setup, MeldTuiSetup):
        raise TypeError("Meld endpoint setup requires a MeldTuiSetup.")
    selectable = frozenset(setup.names)
    annotations = tuple(setup.annotations)
    height = min(9, max(4, len(setup.names)))
    initial_target = (
        next(
            name for name in setup.names if name in setup.eligible_target_names
        )
        if setup.eligible_target_names
        else setup.left_name
    )
    return EndpointSetupSpec(
        title="NEW MELD",
        subtitle="SETUP ONLY · NO PROVIDER, SESSION, RESULT, OR APPLY",
        modes=(
            EndpointSetupMode(
                "SYMMETRIC",
                "SYMMETRIC · A + B → C",
                (
                    "A and B are equal peers. C is an eligible empty local "
                    "Context or one confirmed new exact name."
                ),
                active_role_uids=("A", "B", "C"),
                role_labels=(
                    ("A", "A · PEER · ALL READABLE CONTEXTS"),
                    ("B", "B · PEER · ALL READABLE CONTEXTS"),
                    ("C", "C · RESULT · EMPTY LOCAL CONTEXTS"),
                ),
                descendant_role_uids=frozenset({"A", "B"}),
                memory_focus_role_uids=frozenset(),
            ),
            EndpointSetupMode(
                "DIRECTIONAL",
                "DIRECTIONAL · A → B",
                "A is incoming evidence. B remains authoritative and is the result.",
                active_role_uids=("A", "B"),
                role_labels=(
                    ("A", "A · INCOMING · ALL READABLE CONTEXTS"),
                    ("B", "B · BASELINE + RESULT · ALL READABLE CONTEXTS"),
                ),
                descendant_role_uids=frozenset({"A", "B"}),
                memory_focus_role_uids=frozenset({"A", "B"}),
            ),
        ),
        initial_mode_uid="SYMMETRIC",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                setup.names,
                selectable,
                setup.left_name,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_descendants=True,
                allow_memory_focus=True,
                memory_height=7,
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET",
                setup.names,
                selectable,
                setup.right_name,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_descendants=True,
                allow_memory_focus=True,
                memory_height=7,
            ),
            EndpointSetupRole(
                "C",
                "C · RESULT",
                setup.names,
                setup.eligible_target_names,
                initial_target,
                current_context=setup.current_context,
                annotations=annotations,
                height=height,
                allow_new=True,
                new_label="CREATE NEW RESULT CONTEXT",
                prefer_new=True,
                new_name_validator=new_name_validator,
            ),
        ),
        action_label="CONTINUE TO MELD PLANNING",
    )


def choose_meld_endpoint_setup(
    setup: MeldTuiSetup,
    *,
    memory_loader: MemoryProjectionLoader,
    new_name_validator: Callable[[str], object] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MeldEndpointSelection | None:
    """Return one typed Meld scope without provider or durable work."""

    draft = run_endpoint_setup(
        meld_endpoint_setup_spec(
            setup,
            new_name_validator=new_name_validator,
        ),
        memory_loader=memory_loader,
        validate_draft=lambda value: _validate_meld_draft(value),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    left = draft.value("A")
    right = draft.value("B")
    target = draft.value("C") if draft.mode_uid == "SYMMETRIC" else None
    return MeldEndpointSelection(
        mode=draft.mode_uid.casefold(),
        left_name=left.context_name,
        right_name=right.context_name,
        target_name=target.context_name if target is not None else None,
        create_target=target.create if target is not None else False,
        left_descendants=left.include_descendants,
        right_descendants=right.include_descendants,
        left_memory_uid=left.memory_uid,
        right_memory_uid=right.memory_uid,
    )


def _validate_meld_draft(draft) -> str | None:
    if draft.value("A").context_name == draft.value("B").context_name:
        return "A and B must be distinct Contexts."
    if draft.mode_uid == "SYMMETRIC":
        target = draft.value("C")
        if target.context_name in {
            draft.value("A").context_name,
            draft.value("B").context_name,
        }:
            return "Symmetric Meld result C must differ from A and B."
    return None
