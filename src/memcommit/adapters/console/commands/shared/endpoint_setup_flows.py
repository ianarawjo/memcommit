"""Operation-owned adapters for the common role-based endpoint setup shell."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.authority.access import (
    ContextAccess,
    GrantedReadStore,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.adapters.console.commands.meld.setup import choose_meld_setup as choose_meld_setup
from memcommit.adapters.console.commands.shared.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.commands.shared.session_endpoint_setup import (
    EndpointModeSpec,
    EndpointRoleSpec,
    EndpointSetupDraft,
    choose_session_endpoints,
)
from memcommit.core.context_targeting.tui.picker import context_memory_rows
from memcommit.context import Memory
from memcommit.source_projection.model import SourceDisplayFacts
from memcommit.persistence.store import MemoryStore


def _readable_memory_loader(store: MemoryStore, *, current_name: str | None):
    """Load one canonical public Context through its effective READ access."""

    def load(name: str):
        access = resolve_context_access(
            store,
            name,
            current_name=current_name,
            required_permission="READ",
        )
        read_store = GrantedReadStore(access) if access.is_granted else store
        return context_memory_rows(read_store.load(access.display_name))

    return load


@dataclass(frozen=True)
class CompareSetupReceipt:
    reference_name: str
    compared_name: str
    reference_descendants: bool = False
    compared_descendants: bool = False
    reference_memory_uid: str | None = None
    compared_memory_uid: str | None = None


@dataclass(frozen=True)
class AtomizeSetupReceipt:
    input_name: str
    output_name: str
    create_output: bool = False
    input_memory_uid: str | None = None


@dataclass(frozen=True)
class UpdateSetupReceipt:
    source_name: str
    target_name: str
    source_descendants: bool = False
    target_descendants: bool = False
    source_memory_uid: str | None = None
    target_memory_uid: str | None = None


@dataclass(frozen=True)
class MeldSetupReceipt:
    """Compatibility receipt; new Meld code imports commands.meld_setup."""

    mode: str
    left_name: str
    right_name: str
    target_name: str | None = None
    create_target: bool = False
    left_descendants: bool = False
    right_descendants: bool = False
    left_memory_uid: str | None = None
    right_memory_uid: str | None = None


def _readable_endpoint_catalog(
    store: MemoryStore,
) -> tuple[tuple[str, ...], str, str, dict[str, SourceDisplayFacts]]:
    """Freeze local and READ-granted names for two-readable-Context setup."""

    local_names = tuple(store.list_context_names())
    if not local_names:
        raise ValueError("Starting this operation requires an ordinary local Context.")
    current = store.current_context_name()
    root_name = current if current in local_names else local_names[0]
    root_access = ContextAccess(
        store=store,
        context_name=root_name,
        display_name=root_name,
        attachment_name=None,
        permission="READ",
    )
    catalog = freeze_profile_readable_context_catalog(
        store,
        root_access,
        include_query_routes=False,
    )
    names = tuple(catalog.list_context_names())
    if len(names) < 2:
        raise ValueError("Starting this operation requires two readable Contexts.")
    first = current if current in names else names[0]
    second = next(name for name in names if name != first)
    annotations: dict[str, SourceDisplayFacts] = {}
    for name in names:
        access = catalog.access_for(name)
        if not access.is_granted:
            continue
        annotations[name] = context_access_display_facts(access)
    return names, first, second, annotations


def _distinct_ab(draft: EndpointSetupDraft) -> str | None:
    return (
        "A and B must be distinct Contexts."
        if draft.value("A").context_name == draft.value("B").context_name
        else None
    )


def choose_compare_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> CompareSetupReceipt | None:
    current_name = store.current_context_name()
    names, first, second, annotations = _readable_endpoint_catalog(store)
    draft = choose_session_endpoints(
        names,
        title="NEW COMPARE · A ↔ B → ANALYSIS",
        modes=(
            EndpointModeSpec(
                "COMPARE",
                "A ↔ B → ANALYSIS",
                ("A", "B"),
                {"A": "A · REFERENCE", "B": "B · PEER"},
                descendant_roles=frozenset({"A", "B"}),
                memory_focus_roles=frozenset({"A", "B"}),
            ),
        ),
        roles=(
            EndpointRoleSpec(
                "A",
                frozenset(names),
                first,
                allow_descendants=True,
                allow_memory_focus=True,
            ),
            EndpointRoleSpec(
                "B",
                frozenset(names),
                second,
                allow_descendants=True,
                allow_memory_focus=True,
            ),
        ),
        initial_mode_uid="COMPARE",
        annotations=annotations,
        memory_loader=_readable_memory_loader(
            store,
            current_name=current_name,
        ),
        validate_draft=_distinct_ab,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    return CompareSetupReceipt(
        draft.value("A").context_name,
        draft.value("B").context_name,
        reference_descendants=draft.value("A").include_descendants,
        compared_descendants=draft.value("B").include_descendants,
        reference_memory_uid=draft.value("A").memory_uid,
        compared_memory_uid=draft.value("B").memory_uid,
    )


def choose_atomize_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> AtomizeSetupReceipt | None:
    """Collect one local Input-to-Output plan for a shared Atomize session."""

    names = tuple(store.list_context_names())
    if not names:
        raise ValueError("Starting Atomize requires an ordinary local Context.")
    current = store.current_context_name()
    input_name = current if current in names else names[0]

    def validate(draft: EndpointSetupDraft) -> str | None:
        source = draft.value("A")
        output = draft.value("B")
        direct_memory_count = sum(
            isinstance(item, Memory)
            for item in store.load_direct(source.context_name).iter_items()
        )
        if direct_memory_count == 0:
            return (
                f"Input '{source.context_name}' has 0 direct Memories. "
                "Choose the exact Context that owns the Memory."
            )
        if not output.create and output.context_name != source.context_name:
            return (
                "Output must be the Input Context for in-place Atomize or "
                "a new exact Context name."
            )
        return None

    draft = choose_session_endpoints(
        names,
        title="NEW ATOMIZE · INPUT A → OUTPUT B",
        modes=(
            EndpointModeSpec(
                "ATOMIZE",
                "INPUT A → OUTPUT B",
                ("A", "B"),
                {"A": "A · INPUT", "B": "B · OUTPUT"},
                (
                    "B may be the same Context for an in-place result or a "
                    "new exact name that preserves A."
                ),
                memory_focus_roles=frozenset({"A"}),
            ),
        ),
        roles=(
            EndpointRoleSpec(
                "A",
                frozenset(names),
                input_name,
                allow_memory_focus=True,
            ),
            EndpointRoleSpec(
                "B",
                frozenset(names),
                input_name,
                allow_new=True,
                new_label="CREATE NEW OUTPUT CONTEXT",
                prefer_new=True,
            ),
        ),
        initial_mode_uid="ATOMIZE",
        memory_loader=lambda name: context_memory_rows(store.load(name)),
        validate_draft=validate,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    output = draft.value("B")
    return AtomizeSetupReceipt(
        input_name=draft.value("A").context_name,
        output_name=output.context_name,
        create_output=output.create,
        input_memory_uid=draft.value("A").memory_uid,
    )


def choose_update_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> UpdateSetupReceipt | None:
    current_name = store.current_context_name()
    names, first, second, annotations = _readable_endpoint_catalog(store)
    draft = choose_session_endpoints(
        names,
        title="NEW UPDATE · A → B",
        modes=(
            EndpointModeSpec(
                "UPDATE",
                "A → B",
                ("A", "B"),
                {"A": "A · SOURCE", "B": "B · TARGET"},
                descendant_roles=frozenset({"A", "B"}),
                memory_focus_roles=frozenset({"A", "B"}),
            ),
        ),
        roles=(
            EndpointRoleSpec(
                "A",
                frozenset(names),
                first,
                allow_descendants=True,
                allow_memory_focus=True,
            ),
            EndpointRoleSpec(
                "B",
                frozenset(names),
                second,
                allow_descendants=True,
                allow_memory_focus=True,
            ),
        ),
        initial_mode_uid="UPDATE",
        annotations=annotations,
        memory_loader=_readable_memory_loader(
            store,
            current_name=current_name,
        ),
        validate_draft=_distinct_ab,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    return UpdateSetupReceipt(
        draft.value("A").context_name,
        draft.value("B").context_name,
        source_descendants=draft.value("A").include_descendants,
        target_descendants=draft.value("B").include_descendants,
        source_memory_uid=draft.value("A").memory_uid,
        target_memory_uid=draft.value("B").memory_uid,
    )
