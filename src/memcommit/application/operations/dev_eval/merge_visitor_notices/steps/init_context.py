"""Execute Init and confirm its selected Context through Pwd."""

from memcommit.application.operations.dev_eval.terminal import ScenarioTerminal
from memcommit.application.operations.pwd.application import NoCurrentContextError
from memcommit.application.operations.pwd.runtime import read_current_context
from memcommit.persistence.store import MemoryStore


def run(terminal: ScenarioTerminal, *, store: MemoryStore, context_name: str) -> bool:
    init_result = terminal.run("init", context_name)
    if init_result.returncode != 0:
        return False
    try:
        current_context = read_current_context(store)
    except NoCurrentContextError:
        return False
    return current_context.context_name == context_name
