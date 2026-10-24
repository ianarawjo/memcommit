"""Freeze owned Context scope using the shared lexical locator and reach rules."""

from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.mem_sync.model import SyncRequest, SyncSelection

from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)
from memcommit.core.context_name_validation import validate_context_name


def select_sync_contexts(request: SyncRequest, *, current_name, contexts):
    by_name = {context.name: context for context in contexts}
    if request.all_contexts and request.source is not None:
        raise ValueError("Use --all without a Context operand.")
    if request.all_contexts:
        names = tuple(sorted(by_name))
        root, scope = None, "all"
    else:
        source = request.source or current_name
        if not source:
            raise ValueError("No current Context; supply a Sync Context or --all.")
        root = resolve_context_locator(source, current=current_name)
        if root not in by_name:
            raise ValueError(f"No local Context named {root!r}.")
        names = (
            list_context_and_descendant_names((root,), by_name)
            if request.recursive
            else (root,)
        )
        scope = "recursive" if request.recursive else "exact"
        if (
            by_name[root].corresponding_document_metadata
            and by_name[root].corresponding_document_metadata.role == "package"
            and not request.recursive
        ):
            raise ValueError("A document package requires -r/--recursive.")
    if not names and not request.discover_documents:
        raise ValueError("No Contexts selected for Sync.")
    selected = set(names)
    for name in names:
        validate_context_name(name)
        if name not in by_name:
            raise ValueError(f"Sync Context disappeared: {name}")
        state = by_name[name].corresponding_document_metadata
        if state and state.role in {"skill_body", "skill_metadata"}:
            body_name = name if state.role == "skill_body" else name.rsplit("/", 1)[0]
            for companion in (body_name, body_name + "/metadata"):
                if companion not in by_name:
                    raise ValueError(f"Incomplete Skill document: {body_name}")
                selected.add(companion)
    return SyncSelection(
        names=tuple(sorted(selected)),
        root_name=root,
        scope=scope,
        inventory=tuple(sorted((c.name, c.uid) for c in contexts)),
    )
