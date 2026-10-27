"""Deduplicate one subtree as a combined, parent-first Memory frame."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
import uuid

from memcommit.application.capabilities.memory_issue_analysis.model import (
    DuplicateFinding,
    DuplicateReport,
    FindingsProvider,
)
from memcommit.application.capabilities.memory_issue_analysis.relation_analysis import (
    analyze_memory_redundancies,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    find_exact_duplicate_groups,
)
from memcommit.application.capabilities.semantic_execution.relations import (
    connected_relation_components,
)
from memcommit.application.operations.duplicates.dedun.application import (
    DedunConflictError,
)
from memcommit.application.operations.duplicates.dedun.runtime import (
    DedunScopeContextReceipt,
    DedunScopeReceipt,
)
from memcommit.persistence.store import ProfileStore
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)


@dataclass(frozen=True)
class DedupScopeAnalysis:
    source: QualityFindSourceFrame
    report: DuplicateReport

    @property
    def memory_count(self) -> int:
        return self.report.memory_count


def run_recursive_dedup(
    store: ProfileStore,
    root_name: str,
    provider_factory: Callable[[], FindingsProvider],
    *,
    literal: bool = False,
    on_progress: Callable[
        [Literal["analyzing", "analyzed"], QualityFindSourceFrame], None
    ] | None = None,
) -> tuple[DedupScopeAnalysis, DedunScopeReceipt]:
    catalog_names = tuple(store.list_context_names())
    context_names = tuple(
        sorted(
            list_context_and_descendant_names((root_name,), catalog_names),
            key=lambda name: (name.count("/"), name),
        )
    )
    source = QualityFindSourceFrame.create(
        tuple(store.load_direct(name) for name in context_names),
        context_names=context_names,
        target_names=(root_name,),
        include_descendants=True,
    )
    combined_context = source.analysis_context()
    ordered_memories = tuple(combined_context.iter_memories())
    memories_by_uid = combined_context.memories
    owner_names = source.memory_context_names
    if on_progress is not None:
        on_progress("analyzing", source)
    if literal:
        report = DuplicateReport(
            memory_count=len(ordered_memories),
            findings=tuple(
                DuplicateFinding(
                    memories_by_uid[group.survivor_uid],
                    memories_by_uid[uid],
                    "EXACT",
                    "Identical stored text.",
                )
                for group in find_exact_duplicate_groups(combined_context)
                for uid in group.absorbed_uids
            ),
        )
    else:
        report = analyze_memory_redundancies(
            combined_context,
            provider_factory,
            context_name_by_uid=owner_names,
        )
    if on_progress is not None:
        on_progress("analyzed", source)
    groups = tuple(
        members
        for members in connected_relation_components(
            tuple(memory.uid for memory in ordered_memories),
            ((finding.left.uid, finding.right.uid) for finding in report.findings),
        )
        if len(members) > 1
    )
    analysis = DedupScopeAnalysis(source, report)
    receipt = _apply_recursive_dedup(
        store, analysis, groups, catalog_names, literal=literal
    )
    return analysis, receipt


def _apply_recursive_dedup(
    store: ProfileStore,
    analysis: DedupScopeAnalysis,
    groups: tuple[tuple[str, ...], ...],
    catalog_names: tuple[str, ...],
    *,
    literal: bool,
) -> DedunScopeReceipt:
    source = analysis.source
    root_name = source.target_names[0]
    context_names = source.context_names
    owner_names = source.memory_context_names
    survivor_uids = {members[0] for members in groups}
    absorbed_uids = {uid for members in groups for uid in members[1:]}

    # Survivors may belong to unchanged Contexts, so recheck the entire frame.
    current_contexts = tuple(store.load_for_update(name) for name in context_names)
    if tuple(store.list_context_names()) != catalog_names or not source.matches(
        current_contexts
    ):
        raise DedunConflictError(
            "The Dedup subtree changed during analysis; nothing was written."
        )
    changed_contexts = tuple(
        context
        for context in current_contexts
        if absorbed_uids.intersection(context.memories)
    )
    changed_names = {context.name for context in changed_contexts}
    operation_uid = str(uuid.uuid4()) if changed_contexts else None
    command = "dedup" if literal else "dedun"
    components = _dedup_component_records(analysis, groups)
    membership = [
        {"uid": context.uid, "name": context.name} for context in changed_contexts
    ]
    entries = []
    for context in changed_contexts:
        for uid in tuple(context.get_ordered_memory_uids()):
            if uid in absorbed_uids:
                context.remove(uid)
        entries.append(
            (
                context,
                AutoCheckpointRequest(
                    command=command,
                    command_details={
                        "contract": f"{command}-combined-subtree-v1",
                        "components": components,
                        "scope_contexts": list(context_names),
                        "survivor_order": "context-depth-name-memory-order",
                        f"{command}_tree": {
                            "version": 1,
                            "operation_uid": operation_uid,
                            "root": root_name,
                            "include_descendants": True,
                        },
                        "command_contexts": membership,
                    },
                ),
            )
        )
    checkpoints = (
        store.save_context_command_batch(
            entries,
            source_bindings=tuple(
                (context.name, context.uid)
                for context in current_contexts
                if context.name not in changed_names
            ),
            expected_context_catalog=catalog_names,
        )
        if entries
        else ()
    )
    checkpoint_by_name = {
        context.name: checkpoint.uid
        for (context, _request), checkpoint in zip(entries, checkpoints, strict=True)
    }
    return DedunScopeReceipt(
        root_name=root_name,
        contexts=tuple(
            DedunScopeContextReceipt(
                context_name=context.name,
                context_uid=context.uid,
                group_count=sum(
                    any(owner_names[uid] == context.name for uid in members)
                    for members in groups
                ),
                checkpoint_uid=checkpoint_by_name.get(context.name),
                survivor_uids=tuple(
                    memory.uid
                    for memory in source_context.iter_memories()
                    if memory.uid in survivor_uids
                ),
                absorbed_uids=tuple(
                    memory.uid
                    for memory in source_context.iter_memories()
                    if memory.uid in absorbed_uids
                ),
            )
            for context, source_context in zip(
                current_contexts, source.contexts, strict=True
            )
        ),
        operation_uid=operation_uid,
    )


def _dedup_component_records(
    analysis: DedupScopeAnalysis, groups: tuple[tuple[str, ...], ...]
) -> list[dict[str, object]]:
    owner_names = analysis.source.memory_context_names
    memories_by_uid = {
        memory.uid: memory
        for context in analysis.source.contexts
        for memory in context.iter_memories()
    }
    report = analysis.report
    return [
        {
            "component_uid": str(uuid.uuid5(uuid.NAMESPACE_URL, ":".join(members))),
            "survivor_uid": members[0],
            "members": [
                {
                    "uid": uid,
                    "content": memories_by_uid[uid].content,
                    "context_name": owner_names[uid],
                    "selected": uid == members[0],
                }
                for uid in members
            ],
            "evidence": [
                {"relation": finding.relation, "reason": finding.reason}
                for finding in report.findings
                if finding.left.uid in members and finding.right.uid in members
            ],
        }
        for members in groups
    ]
