"""Prepare the current Context's ordered Memories and child names."""

from memcommit.models.memory import Memory
from memcommit.persistence.store import ProfileStore
from memcommit.persistence.store.lookup.context_names import list_child_context_names


def prepare_memory_and_child_context_lists(
    store: ProfileStore,
    context_name: str,
) -> tuple[tuple[Memory, ...], tuple[str, ...]]:
    """Prepare ordered Memories, then immediate child Context names."""
    current_context = store.load_direct(context_name)
    ordered_memory_list = tuple(current_context.iter_memories())
    child_context_names = tuple(sorted(
        list_child_context_names(context_name, store.list_context_names())
    ))
    return ordered_memory_list, child_context_names
