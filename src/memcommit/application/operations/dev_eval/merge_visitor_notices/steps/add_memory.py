"""Execute CLI Add and compare stored Memory contents through List."""

from collections import Counter

from memcommit.application.operations.dev_eval.terminal import ScenarioTerminal
from memcommit.application.operations.list.runtime import (
    prepare_memory_and_child_context_lists,
)
from memcommit.persistence.store import ProfileStore


def run(
    terminal: ScenarioTerminal,
    *,
    store: ProfileStore,
    context_name: str,
    contents: tuple[str, ...],
) -> bool:
    switch_result = terminal.run("switch", context_name)
    if switch_result.returncode != 0:
        return False
    add_result = terminal.run("add", "--", *contents)
    if add_result.returncode != 0:
        return False
    current_context_name = store.current_context_name()
    if current_context_name != context_name:
        return False
    try:
        ordered_memory_list, _child_context_names = prepare_memory_and_child_context_lists(
            store, current_context_name
        )
    except FileNotFoundError:
        return False
    stored_contents = Counter(memory.content for memory in ordered_memory_list)
    return stored_contents == Counter(contents)
