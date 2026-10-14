"""Freeze owned Context scope using the shared lexical locator and reach rules."""

from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.mem_sync.model import SyncRequest, SyncSelection
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.core.context_targeting.naming import validate_portable_context_name


def select_sync_contexts(request: SyncRequest, *, current_name, contexts):
    by_name = {context.name: context for context in contexts}
    if request.all_contexts and request.source is not None:
        raise ValueError("Use --all without a Context operand.")
    if request.selected_names is not None:
        names = request.selected_names
        root, scope = None, "selected"
    elif request.all_contexts:
        names = tuple(sorted(by_name))
        root, scope = None, "all"
    else:
        source = request.source or current_name
        if not source:
            raise ValueError("No current Context; supply a Sync Context or --all.")
        root = resolve_context_locator(source, current=current_name)
        if root not in by_name:
            raise ValueError(
                f"No owned Context named {root!r}. Sync does not include Grant routes."
            )
        names = expand_lexical_context_names(
            ContextScope.create((root,), include_descendants=request.recursive), by_name
        )
        scope = "recursive" if request.recursive else "exact"
        if (
            by_name[root].document
            and by_name[root].document.role == "package"
            and not request.recursive
        ):
            raise ValueError("A document package requires -r/--recursive.")
    if not names and not request.automatic and not (request.all_contexts and request.toggle_always):
        raise ValueError("No Contexts selected for Sync.")
    selected = set(names)
    for name in names:
        validate_portable_context_name(name)
        if name not in by_name:
            raise ValueError(f"Sync Context disappeared: {name}")
        state = by_name[name].document
        if state and state.role in {"skill_body", "skill_metadata"}:
            body_name = name if state.role == "skill_body" else name.rsplit("/", 1)[0]
            for companion in (body_name, body_name + "/metadata"):
                if companion not in by_name:
                    raise ValueError(f"Incomplete Skill document: {body_name}")
                selected.add(companion)
    return SyncSelection(
        tuple(sorted(selected)),
        root,
        scope,
        tuple(sorted((c.name, c.uid) for c in contexts)),
    )
