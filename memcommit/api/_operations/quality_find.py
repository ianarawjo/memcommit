"""Public application assembly for read-only quality finding operations."""

from __future__ import annotations

from collections.abc import Sequence

import memcommit.ops as ops
from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.semantic import safe_semantic_provider
from memcommit.api.errors import (
    SemanticAuthorityError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.api.quality_find import QualityFindResult
from memcommit.authority.access import GrantedReadStore, resolve_context_access
from memcommit.context_locator import resolve_context_locator
from memcommit.derived_policy import authorize_combination
from memcommit.findings import ConflictReport, FindingsError
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.quality_find_workbench import (
    QualityFindKind,
    QualityFindSourceFrame,
    create_quality_find_workbench,
)
from memcommit.quality_finding_handoff import quality_finding_handoffs


def _current_name(runtime: ClientRuntime) -> str | None:
    try:
        return runtime.store.current_context_name()
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise_public(SemanticStorageError, error)


def _active_registry(runtime: ClientRuntime):
    if runtime.registry is None or runtime.profile is None:
        return None
    try:
        registry = load_profile_registry()
        if (
            registry.active.uid != runtime.profile.uid
            or runtime.store_root != profile_store_dir(registry.active).resolve()
        ):
            return None
        return registry
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
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
    registry = _active_registry(runtime)
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
    if len(accesses) > 1:
        authorize_combination(accesses)
    contexts = tuple(
        (
            GrantedReadStore(access, registry=registry).load_direct(
                access.display_name
            )
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
) -> QualityFindResult:
    """Analyze one frozen readable frame and return typed handoffs."""

    if kind not in {"duplicates", "ambiguities", "conflicts"}:
        raise SemanticInputError("Unsupported quality finder kind.")
    try:
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

    operation = {
        "duplicates": ops.find_redundancies,
        "ambiguities": ops.find_ambiguities,
        "conflicts": ops.find_conflicts,
    }[kind]
    try:
        report = operation(
            source.analysis_context(),
            lambda: safe_semantic_provider(runtime),
            context_name_by_uid=source.memory_context_names,
        )
        session = create_quality_find_workbench(kind, source, report)
        handoffs = quality_finding_handoffs(session)
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
    )


__all__ = ["find_quality"]
