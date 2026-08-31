"""Public application assembly for read-only quality finding operations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.active_profile import (
    active_profile_registry,
)
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api._support.semantic import safe_semantic_provider
from memcommit.adapters.python_api.errors import (
    SemanticAuthorityError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.adapters.python_api.quality_find import (
    QualityFindContextResult,
    QualityFindResult,
)
from memcommit.application.capabilities.authority.context_access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    find_exact_duplicate_groups,
)
from memcommit.application.capabilities.memory_issue_analysis.model import (
    ConflictReport,
    FindingsError,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.capabilities.memory_issue_analysis.workbench import (
    QualityFindKind,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceFrame,
)
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    quality_finding_handoffs,
)
from memcommit.application.capabilities.memory_issue_analysis.redundancy_scope import (
    analyze_independent_redundancy_scope,
    freeze_redundancy_scope,
)
from memcommit.application.operations.find_ambiguities.application import (
    analyze_find_ambiguities,
)
from memcommit.application.operations.find_conflicts.application import (
    analyze_find_conflicts,
)
from memcommit.application.operations.find_redundancies.application import (
    analyze_combined_find_redundancies,
)


def _current_name(runtime: ClientRuntime) -> str | None:
    try:
        return runtime.store.current_context_name()
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise_public(SemanticStorageError, error)


def _source(
    runtime: ClientRuntime,
    context_names: Sequence[str],
) -> QualityFindSourceFrame:
    if isinstance(context_names, (str, bytes)):
        raise TypeError("Quality finder Context names must be a sequence.")
    current_name = _current_name(runtime)
    operands = tuple(context_names)
    if not operands:
        if current_name is None:
            raise FileNotFoundError("No current Context is available.")
        operands = (current_name,)
    if any(not isinstance(name, str) or not name.strip() for name in operands):
        raise TypeError("Quality finder Context names must be nonblank text.")
    canonical = tuple(
        resolve_context_locator(name, current=current_name) for name in operands
    )
    if len(set(canonical)) != len(canonical):
        raise ValueError("Quality finder Context names must not repeat.")
    registry = active_profile_registry(runtime)
    accesses = tuple(
        resolve_context_access(
            runtime.store,
            name,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
        for name in canonical
    )
    contexts = tuple(
        (
            GrantedReadStore(access, registry=registry).load_direct(access.display_name)
            if access.is_granted
            else access.store.load_direct(access.context_name)
        )
        for access in accesses
    )
    display_names = tuple(access.display_name for access in accesses)
    return QualityFindSourceFrame.create(
        contexts,
        context_names=display_names,
        target_names=display_names,
        selection_mode="SINGLE" if len(contexts) == 1 else "MULTIPLE",
    )


def find_quality(
    runtime: ClientRuntime,
    kind: QualityFindKind,
    context_names: Sequence[str] = (),
    *,
    include_descendants: bool = False,
) -> QualityFindResult:
    """Analyze one frozen readable frame and return typed handoffs."""

    if kind not in {"duplicates", "ambiguities", "conflicts"}:
        raise SemanticInputError("Unsupported quality finder kind.")
    try:
        if type(include_descendants) is not bool:
            raise TypeError("Quality finder descendant reach must be a boolean.")
        if include_descendants and kind != "duplicates":
            raise ValueError(
                "Recursive lexical scope is available only for redundancies."
            )
        if include_descendants:
            if isinstance(context_names, (str, bytes)):
                raise TypeError("Quality finder Context names must be a sequence.")
            operands = tuple(context_names)
            if len(operands) > 1:
                raise ValueError(
                    "Recursive Find Redundancies accepts exactly one root Context."
                )
            current_name = _current_name(runtime)
            if not operands:
                if current_name is None:
                    raise FileNotFoundError("No current Context is available.")
                root_name = current_name
            else:
                root_name = operands[0]
                if not isinstance(root_name, str) or not root_name.strip():
                    raise TypeError(
                        "Quality finder Context names must be nonblank text."
                    )
                root_name = resolve_context_locator(root_name, current=current_name)
            registry = active_profile_registry(runtime)
            access = resolve_context_access(
                runtime.store,
                root_name,
                current_name=current_name,
                required_permission="READ",
                registry=registry,
            )
            source = freeze_redundancy_scope(
                runtime.store,
                access,
                include_descendants=True,
                registry=registry,
            )
        else:
            source = _source(runtime, context_names)
    except SemanticAuthorityError:
        raise
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)

    try:
        if include_descendants:
            analysis = analyze_independent_redundancy_scope(
                source,
                lambda: safe_semantic_provider(runtime),
            )
            contexts = tuple(
                QualityFindContextResult(
                    context_name=frame.context_name,
                    source_digest=frame.source.digest,
                    memory_count=frame.report.memory_count,
                    handoffs=frame.handoffs,
                    exact_item_groups=frame.report.exact_item_groups,
                )
                for frame in analysis.contexts
            )
            return QualityFindResult(
                kind="redundancies",
                context_names=source.context_names,
                source_digest=source.digest,
                memory_count=analysis.memory_count,
                pair_count=None,
                handoffs=analysis.handoffs,
                exact_item_groups=analysis.exact_item_groups,
                include_descendants=True,
                contexts=contexts,
            )
        def provider_factory():
            return safe_semantic_provider(runtime)

        if kind == "duplicates":
            result = analyze_combined_find_redundancies(source, provider_factory)
        elif kind == "ambiguities":
            result = analyze_find_ambiguities(source, provider_factory)
        else:
            result = analyze_find_conflicts(source, provider_factory)
        report = result.report
        if kind == "duplicates" and len(source.contexts) == 1:
            report = replace(
                report,
                exact_item_groups=tuple(
                    group
                    for group in find_exact_duplicate_groups(source.contexts[0])
                    if group.item_kind != "MEMORY"
                ),
            )
        handoffs = quality_finding_handoffs(result.session)
    except SemanticProviderFailure:
        raise
    except FindingsError as error:
        raise_public(SemanticExecutionError, error)
    except (TypeError, ValueError, RuntimeError) as error:
        raise_public(SemanticExecutionError, error)
    return QualityFindResult(
        kind="redundancies" if kind == "duplicates" else kind,
        context_names=source.context_names,
        source_digest=source.digest,
        memory_count=report.memory_count,
        pair_count=(report.pair_count if isinstance(report, ConflictReport) else None),
        handoffs=handoffs,
        exact_item_groups=(report.exact_item_groups if kind == "duplicates" else ()),
        contexts=(
            QualityFindContextResult(
                context_name=source.context_names[0],
                source_digest=source.digest,
                memory_count=report.memory_count,
                handoffs=handoffs,
                exact_item_groups=(
                    report.exact_item_groups if kind == "duplicates" else ()
                ),
            ),
        )
        if len(source.context_names) == 1
        else (),
    )


__all__ = ["find_quality"]
