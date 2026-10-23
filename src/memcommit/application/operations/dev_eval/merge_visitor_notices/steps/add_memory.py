"""Execute CLI Add and compare stored Memory contents through List."""

from collections import Counter

from memcommit.application.operations.dev_eval.terminal import ScenarioTerminal
from memcommit.application.operations.list.application import ListRequest
from memcommit.application.operations.list.runtime import execute_list
from memcommit.models.memory import Memory
from memcommit.persistence.store import MemoryStore


def run(
    terminal: ScenarioTerminal,
    *,
    store: MemoryStore,
    context_name: str,
    contents: tuple[str, ...],
) -> bool:
    switch_result = terminal.run("switch", context_name)
    if switch_result.returncode != 0:
        return False
    add_result = terminal.run("add", "--", *contents)
    if add_result.returncode != 0:
        return False
    try:
        listed_context = execute_list(
            store,
            ListRequest(
                context_locator=context_name,
                # Generated names are canonical, independent of current selection.
                current_context_name=None,
                recursive=False,
            ),
        ).context
    except FileNotFoundError:
        return False
    stored_contents = Counter(
        memory.content
        for memory in listed_context.iter_memories()
        if isinstance(memory, Memory)
    )
    return stored_contents == Counter(contents)
