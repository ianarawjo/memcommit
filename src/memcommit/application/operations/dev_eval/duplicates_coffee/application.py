"""Create the coffee experiment and evaluate DUP/DUN; only Dedun uses a provider."""

from collections.abc import Callable, Iterable, Sequence

from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsProvider,
)
from memcommit.application.capabilities.semantic_execution.relations import (
    connected_relation_components,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.operations.add.application import AddRequest
from memcommit.application.operations.add.runtime import execute_add
from memcommit.application.operations.dev_eval.duplicates_coffee.data import (
    CONTENTS,
    EXACT_GROUPS,
    NAME,
    REDUNDANCY_GROUPS,
)
from memcommit.application.operations.dev_eval.naming import new_context_names
from memcommit.application.operations.duplicates.dedup.application import (
    apply_exact_dedup_scope,
)
from memcommit.application.operations.duplicates.find_duplicates.application import (
    FindDuplicatesRequest,
    find_duplicates,
)
from memcommit.application.operations.duplicates.find_redundancies.application import (
    FindRedundanciesRequest,
)
from memcommit.application.operations.duplicates.runtime import run_redundancies
from memcommit.application.operations.init.application import ContextInitRequest
from memcommit.application.operations.init.runtime import (
    execute_context_init,
    prepare_context_init,
)
from memcommit.application.operations.list.application import ListRequest
from memcommit.application.operations.list.runtime import execute_list
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore


def _groups(
    seed: Context, edges: Iterable[Sequence[str]]
) -> tuple[tuple[int, ...], ...]:
    uids = tuple(memory.uid for memory in seed.iter_items())
    return tuple(
        tuple(uids.index(uid) for uid in component)
        for component in connected_relation_components(uids, edges)
        if len(component) > 1
    )


def _survivors(
    seed: Context, groups: tuple[tuple[int, ...], ...]
) -> tuple[tuple[str, str], ...]:
    removed = {index for group in groups for index in group[1:]}
    return tuple(
        memory
        for index, memory in enumerate(_memory_values(seed))
        if index not in removed
    )


def _memory_values(context: Context) -> tuple[tuple[str, str], ...]:
    items = tuple(context.iter_items())
    if any(not isinstance(item, Memory) for item in items):
        raise ValueError(
            f"Scenario Context '{context.name}' contains a non-Memory item."
        )
    return tuple((item.uid, item.content) for item in items)


def _list_context(store: MemoryStore, name: str) -> Context:
    return execute_list(
        store, ListRequest(name, store.current_context_name(), recursive=False)
    ).context


def run_scenario(
    *,
    store: MemoryStore,
    provider_factory: Callable[[], FindingsProvider],
) -> list[tuple[str, bool]]:
    """Always create, execute, and verify; retain the original and both results."""
    checks = []
    created_names = []
    try:
        names = new_context_names(store, (NAME, f"{NAME}-dup", f"{NAME}-dun"))
        for variant, name in zip(("original", "dup", "dun"), names, strict=True):
            snapshot = prepare_context_init(store)
            execute_context_init(
                ContextInitRequest(name, False, snapshot.expected_current), store=store
            )
            # Init publishes independently; failed experiments retain completed steps.
            created_names.append(name)
            added = execute_add(AddRequest(CONTENTS, name), store=store)
            seed = _list_context(store, name)
            if _memory_values(seed) != tuple(
                (item.uid, item.content) for item in added.memories
            ):
                raise RuntimeError("List no longer matches the completed Add receipt.")
            if variant == "original":
                source = seed
                source_checkpoints = store.list_checkpoints(source.name)
                continue
            baseline = len(store.list_checkpoints(seed.name))
            if variant == "dup":
                analysis = find_duplicates(
                    store, FindDuplicatesRequest(seed.name), current_name=seed.name
                )
                groups = analysis.contexts[0].report.groups
                checks.extend(
                    (
                        (
                            "DUP groups",
                            _groups(
                                seed,
                                (
                                    (group.survivor_uid, *group.absorbed_uids)
                                    for group in groups
                                ),
                            )
                            == EXACT_GROUPS,
                        ),
                        (
                            "Find DUP preserves Memories",
                            _memory_values(_list_context(store, seed.name))
                            == _memory_values(seed),
                        ),
                        (
                            "Find DUP creates no checkpoint",
                            len(store.list_checkpoints(seed.name)) == baseline,
                        ),
                    )
                )
                access = resolve_existing_context_access(
                    store, seed.name, current_name=seed.name, required_permission="READ"
                ).value
                apply_exact_dedup_scope(store, access, analysis)
                expected_groups = EXACT_GROUPS
            else:
                result = run_redundancies(
                    FindRedundanciesRequest(seed.name),
                    operation="dedun",
                    store=store,
                    provider_factory=provider_factory,
                )
                # Reuse Dedun's discovery; never pay for a second semantic Find
                # solely to grade the first call or to render its evidence.
                report = result.analysis.contexts[0].report
                edges = [
                    (finding.left.uid, finding.right.uid) for finding in report.findings
                ]
                edges.extend(
                    (group.survivor_uid, *group.absorbed_uids)
                    for group in report.exact_item_groups
                )
                expected_groups = REDUNDANCY_GROUPS
                checks.append(("DUN groups", _groups(seed, edges) == expected_groups))
            checks.extend(
                (
                    (
                        f"{variant.upper()} survivors retain UID, content, and order",
                        _memory_values(_list_context(store, seed.name))
                        == _survivors(seed, expected_groups),
                    ),
                    (
                        f"{variant.upper()} adds one checkpoint",
                        len(store.list_checkpoints(seed.name)) == baseline + 1,
                    ),
                )
            )
        checks.extend(
            (
                (
                    "Original scenario Memories preserved",
                    _memory_values(_list_context(store, source.name))
                    == _memory_values(source),
                ),
                (
                    "Original scenario checkpoints preserved",
                    store.list_checkpoints(source.name) == source_checkpoints,
                ),
            )
        )
        return checks
    except Exception as error:
        if not created_names:
            raise
        retained = ", ".join(created_names)
        raise RuntimeError(
            f"Coffee scenario failed. Contexts retained: {retained}. {error}"
        ) from error
