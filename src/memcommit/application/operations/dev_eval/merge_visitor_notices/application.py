from collections.abc import Callable

from memcommit.application.operations.dev_eval.naming import new_context_names
from memcommit.application.operations.dev_eval.merge_visitor_notices.data import (
    NAME,
    SOURCE_CONTENTS,
    TARGET_CONTENTS,
)
from memcommit.application.operations.dev_eval.merge_visitor_notices.steps import (
    add_memory as add_memory_step,
    init_context as init_context_step,
)
from memcommit.application.operations.dev_eval.terminal import ScenarioTerminal
from memcommit.persistence.store import MemoryStore
from memcommit.providers.types import SemanticProvider


def run_scenario(
    *,
    store: MemoryStore,
    provider_factory: Callable[[], SemanticProvider],
) -> list[tuple[str, bool]]:
    """Run CLI Init/Add and verify both endpoints through application queries."""
    step_verdicts = []
    requested_context_names = []
    try:
        names = new_context_names(store, (f"{NAME}-target", f"{NAME}-source"))
        with ScenarioTerminal(store) as terminal:
            for context_name, (role, contents) in zip(
                names,
                (("target", TARGET_CONTENTS), ("source", SOURCE_CONTENTS)),
                strict=True,
            ):
                requested_context_names.append(context_name)
                init_step_passed = init_context_step.run(
                    terminal, store=store, context_name=context_name
                )
                step_verdicts.append(
                    (f"{role.title()} Init · pwd matches the Context", init_step_passed)
                )
                if not init_step_passed:
                    return step_verdicts
                add_step_passed = add_memory_step.run(
                    terminal, store=store, context_name=context_name, contents=contents
                )
                step_verdicts.append(
                    (f"{role.title()} Add · list matches all Memories", add_step_passed)
                )
                if not add_step_passed:
                    return step_verdicts
        return step_verdicts
    except Exception as error:
        # A published Init/Add remains available even when a later step fails.
        raise RuntimeError(
            f"Merge scenario stopped. Contexts requested: "
            f"{', '.join(requested_context_names) or '(none)'}; "
            f"any completed changes are retained. {error}"
        ) from error
