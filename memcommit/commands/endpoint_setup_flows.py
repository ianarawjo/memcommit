"""Operation-owned adapters for the common role-based endpoint setup shell."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.authority.access import (
    ContextAccess,
    context_access_display_facts,
)
from memcommit.commands.meld_setup import choose_meld_setup
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.commands.session_endpoint_setup import (
    EndpointModeSpec,
    EndpointRoleSpec,
    EndpointSetupDraft,
    choose_session_endpoints,
)
from memcommit.source_projection.model import SourceDisplayFacts
from memcommit.store import MemoryStore


@dataclass(frozen=True)
class CompareSetupReceipt:
    reference_name: str
    compared_name: str
    reference_descendants: bool = False
    compared_descendants: bool = False


@dataclass(frozen=True)
class AtomizeSetupReceipt:
    input_name: str
    output_name: str
    create_output: bool = False


@dataclass(frozen=True)
class UpdateSetupReceipt:
    source_name: str
    target_name: str
    source_descendants: bool = False
    target_descendants: bool = False


@dataclass(frozen=True)
class MeldSetupReceipt:
    mode: str
    left_name: str
    right_name: str
    target_name: str | None = None
    create_target: bool = False
    left_descendants: bool = False
    right_descendants: bool = False


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
            ),
        ),
        roles=(
            EndpointRoleSpec(
                "A",
                frozenset(names),
                first,
                allow_descendants=True,
            ),
            EndpointRoleSpec(
                "B",
                frozenset(names),
                second,
                allow_descendants=True,
            ),
        ),
        initial_mode_uid="COMPARE",
        annotations=annotations,
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
            ),
        ),
        roles=(
            EndpointRoleSpec("A", frozenset(names), input_name),
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
    )


def choose_update_setup(
    store: MemoryStore,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> UpdateSetupReceipt | None:
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
            ),
        ),
        roles=(
            EndpointRoleSpec(
                "A",
                frozenset(names),
                first,
                allow_descendants=True,
            ),
            EndpointRoleSpec(
                "B",
                frozenset(names),
                second,
                allow_descendants=True,
            ),
        ),
        initial_mode_uid="UPDATE",
        annotations=annotations,
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
    )
