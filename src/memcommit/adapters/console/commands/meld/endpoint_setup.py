"""Compose Meld authority with the shared endpoint-selection interface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    context_access_display_facts,
)
from memcommit.adapters.console.commands.meld import command_codec as meld_command_review
from memcommit.adapters.console.terminal.components.context_picker import context_memory_rows
from memcommit.core.context_targeting.readable_catalog import (
    ReadableContextCatalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointCommandBinding,
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
class MeldTuiSetup:
    """Frozen readable Source catalog and eligible local Result targets."""

    names: tuple[str, ...]
    left_name: str
    right_name: str
    eligible_target_names: frozenset[str]
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            len(self.names) < 2
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Meld setup requires two distinct readable names.")
        if (
            self.left_name not in self.names
            or self.right_name not in self.names
            or self.left_name == self.right_name
        ):
            raise ValueError("Meld setup requires distinct available A/B defaults.")
        if not self.eligible_target_names <= set(self.names):
            raise ValueError(
                "One or more Meld Result targets are no longer available. "
                "Reopen Meld and select them again."
            )
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Meld setup annotations are outside its catalog.")


@dataclass(frozen=True)
class MeldEndpointSelection:
    """One reviewed Meld shape returned without planning or durable mutation."""

    mode: str
    left_name: str
    right_name: str
    target_name: str | None = None
    create_target: bool = False
    left_descendants: bool = False
    right_descendants: bool = False
    left_memory_uid: str | None = None
    right_memory_uid: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"symmetric", "directional"}:
            raise ValueError("Meld endpoint selection has an unknown mode.")
        if self.left_name == self.right_name:
            raise ValueError("Meld endpoint selection requires distinct A and B.")
        if self.mode == "symmetric" and self.target_name is None:
            raise ValueError("Symmetric Meld endpoint selection requires C.")
        if self.mode == "directional" and (
            self.target_name is not None or self.create_target
        ):
            raise ValueError("Directional Meld uses B as its result target.")


@dataclass(frozen=True)
class MeldSetupReceipt:
    """Reviewed process-local arguments for one new Meld command."""

    mode: str
    left_name: str
    right_name: str
    target_name: str | None = None
    create_target: bool = False
    left_descendants: bool = False
    right_descendants: bool = False
    left_memory_uid: str | None = None
    right_memory_uid: str | None = None


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
        next(name for name in setup.names if name in setup.eligible_target_names)
        if setup.eligible_target_names
        else setup.left_name
    )
    return EndpointSetupSpec(
        title="NEW MELD",
        subtitle="CHOOSE MODE AND ENDPOINTS",
        modes=(
            EndpointSetupMode(
                "SYMMETRIC",
                "SYMMETRIC · CREATE SEPARATE RESULT",
                (
                    "A and B are equal peers. C is an eligible empty local "
                    "Context or one confirmed new exact name."
                ),
                active_role_uids=("A", "B", "C"),
                role_labels=(
                    ("A", "FROM"),
                    ("B", "WITH"),
                    ("C", "TO"),
                ),
                descendant_role_uids=frozenset({"A", "B"}),
                memory_focus_role_uids=frozenset(),
            ),
            EndpointSetupMode(
                "DIRECTIONAL",
                "DIRECTIONAL · UPDATE EXISTING",
                "A is incoming evidence. B remains authoritative and is the result.",
                active_role_uids=("A", "B"),
                role_labels=(
                    ("A", "FROM"),
                    ("B", "TO"),
                ),
                descendant_role_uids=frozenset({"A", "B"}),
                memory_focus_role_uids=frozenset({"A", "B"}),
            ),
        ),
        initial_mode_uid="SYMMETRIC",
        screen_layout="COMPACT_FORM",
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
                existing_label="EMPTY · EXISTING",
                prefer_new=True,
                new_name_validator=new_name_validator,
            ),
        ),
        action_label="START MELD",
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
        command_editor=EndpointCommandBinding(
            form=meld_command_review.MELD_COMMAND_FORM,
            review=_meld_start_review,
            parse=meld_command_review.parse_endpoint_argv,
        ),
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


def _meld_start_review(draft):
    left = draft.value("A")
    right = draft.value("B")
    target = draft.value("C") if draft.mode_uid == "SYMMETRIC" else None
    return meld_command_review.build_start_review(
        mode=draft.mode_uid,
        left_name=left.context_name,
        right_name=right.context_name,
        target_name=target.context_name if target is not None else None,
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


def choose_meld_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MeldSetupReceipt | None:
    """Freeze readable authority, then collect one shared Meld setup."""

    setup, catalog = _freeze_meld_tui_setup(store)

    def load_memories(role_uid: str, context_name: str):
        if role_uid not in {"A", "B"}:
            raise ValueError("Meld Memory projection received an unknown role.")
        return tuple(
            EndpointSetupMemory(context_name, row.selector, row.content)
            for row in context_memory_rows(catalog.load(context_name))
            if row.selector is not None
        )

    selected = choose_meld_endpoint_setup(
        setup,
        memory_loader=load_memories,
        new_name_validator=store.assert_context_creatable,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if selected is None:
        return None
    return MeldSetupReceipt(
        mode=selected.mode,
        left_name=selected.left_name,
        right_name=selected.right_name,
        target_name=selected.target_name,
        create_target=selected.create_target,
        left_descendants=selected.left_descendants,
        right_descendants=selected.right_descendants,
        left_memory_uid=selected.left_memory_uid,
        right_memory_uid=selected.right_memory_uid,
    )


def build_meld_tui_setup(store: MemoryStore) -> MeldTuiSetup:
    """Return Meld's frozen public setup values without opening a terminal."""

    setup, _catalog = _freeze_meld_tui_setup(store)
    return setup


def _eligible_local_result_targets(store: MemoryStore) -> tuple[str, ...]:
    """Return empty local Contexts without a bound Meld session."""

    result: list[str] = []
    for name in store.list_context_names():
        context = store.load_direct(name)
        if tuple(context.iter_items()):
            continue
        if store.load_meld_session(context.uid) is not None:
            continue
        result.append(name)
    current = store.current_context_name()
    return tuple(
        sorted(
            result,
            key=lambda name: (name != current, name.casefold(), name),
        )
    )


def _freeze_meld_tui_setup(
    store: MemoryStore,
) -> tuple[MeldTuiSetup, ReadableContextCatalog]:
    """Freeze one command-local readable catalog and its typed TUI projection."""

    local_names = tuple(store.list_context_names())
    if not local_names:
        raise ValueError("Starting Meld requires an ordinary local Context.")
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
        raise ValueError("Starting Meld requires two readable Contexts.")
    left_name = current_name if current_name in names else names[0]
    right_name = next(name for name in names if name != left_name)
    annotations = tuple(
        (name, context_access_display_facts(catalog.access_for(name)))
        for name in names
        if catalog.access_for(name).is_granted
    )
    eligible_targets = frozenset(_eligible_local_result_targets(store))

    return (
        MeldTuiSetup(
            names=names,
            left_name=left_name,
            right_name=right_name,
            eligible_target_names=eligible_targets,
            current_context=current_name,
            annotations=annotations,
        ),
        catalog,
    )
