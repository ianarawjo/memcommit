"""Local Store adapters for the shared Conformance core."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Literal, Protocol
import uuid

from memcommit.application.operations.quality_resolution.validate.check_conformance.model import (
    ConformanceError,
    ConformanceProvider,
    ConformanceReport,
    ConformanceRule,
    ConformanceSubject,
    check_context_conformance,
)
from memcommit.core.context import Context, Memory
from memcommit.application.capabilities.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)
from memcommit.application.capabilities.local_target_lookup import (
    resolve_local_direct_memory_locator,
    try_resolve_short_local_direct_memory_locator,
)
from memcommit.core.context_targeting.model import (
    DirectMemoryLocator,
    ExistingContextOperand,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.application.operations.ground_workbench.ground.workspace_model import GroundWorkspace
from memcommit.application.operations.ground_workbench.ground.workspace_projection import (
    GroundWorkspaceProjectionError,
    project_ordinary_memories,
)
from memcommit.application.operations.ground_workbench.ground.workspace_runtime import (
    load_ground_workspace,
)
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)


class ConformanceProviderFactory(Protocol):
    def __call__(self) -> ConformanceProvider:
        """Open one configured provider after all inputs are frozen."""


@dataclass(frozen=True)
class FrozenContextConformance:
    target_name: str
    rules_name: str
    target_digest: str
    rules_digest: str
    rules: tuple[ConformanceRule, ...]
    subjects: tuple[ConformanceSubject, ...]


@dataclass(frozen=True)
class FrozenGroundConformance:
    ground_name: str
    ground_digest: str
    rules: tuple[ConformanceRule, ...]
    subjects: tuple[ConformanceSubject, ...]


@dataclass(frozen=True)
class FrozenConformanceRulesOperand:
    """One exact Context, direct Memory, or process-local Rule source."""

    kind: Literal["CONTEXT", "MEMORY", "TEXT"]
    label: str
    rules: tuple[ConformanceRule, ...]
    context_name: str | None = None
    context_uid: str | None = None
    context_digest: str | None = None
    memory_uid: str | None = None
    memory_digest: str | None = None


def _direct_memories(ctx: Context) -> tuple[Memory, ...]:
    return tuple(item for item in ctx.iter_items() if isinstance(item, Memory))


def _rules_from_memories(
    memories: tuple[Memory, ...],
) -> tuple[ConformanceRule, ...]:
    return tuple(
        ConformanceRule(memory.uid, f"r{index}", memory.content)
        for index, memory in enumerate(memories, 1)
    )


def _subjects_from_target(
    target: Context,
    rules: tuple[ConformanceRule, ...],
) -> tuple[ConformanceSubject, ...]:
    target_memories = _direct_memories(target)
    if not target_memories:
        raise ConformanceError("The Target Context contains no direct Memories.")
    rule_uids = tuple(rule.uid for rule in rules)
    return tuple(
        ConformanceSubject(
            uid=memory.uid,
            alias=f"m{index:06d}",
            content=memory.content,
            linked_rule_uids=rule_uids,
        )
        for index, memory in enumerate(target_memories, 1)
    )


def _memory_digest(memory: Memory) -> str:
    return hashlib.sha256(memory.content.encode("utf-8")).hexdigest()


def _literal_rule(content: str) -> ConformanceRule:
    normalized = content.strip()
    if not normalized:
        raise ConformanceError(
            "A Conformance text: Rules operand must contain Rule text."
        )
    # Literal Rules have no durable identity. A role-scoped deterministic UUID
    # gives the typed provider frame a stable internal key without pretending
    # that caller-supplied text is a stored Memory.
    uid = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            "memcommit:check-conformance:literal-rule\0" + normalized,
        )
    )
    return ConformanceRule(uid, "r1", normalized)


def freeze_conformance_rules_operand(
    store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
) -> FrozenConformanceRulesOperand:
    """Classify and freeze one Rules Context, Memory selector, or text value.

    The automatic grammar matches general Fit: ``text:`` forces literal text,
    UUID-shaped values are strict direct-Memory selectors, existing Contexts
    retain their Context meaning, and remaining non-relative text is literal.
    Direct Memory lookup delegates to the shared local owner resolver so a
    bare UID never acquires hidden current-Context priority.
    """

    if not isinstance(operand, str) or not operand.strip():
        raise ConformanceError("A Conformance Rules operand must be nonblank.")
    text = operand.strip()
    if text.startswith("text:"):
        rule = _literal_rule(text.removeprefix("text:"))
        return FrozenConformanceRulesOperand(
            kind="TEXT",
            label=f"TEXT {rule.content}",
            rules=(rule,),
        )

    parsed = parse_auto_typed_context_memory_operand(text)
    if isinstance(parsed, DirectMemoryLocator):
        memory_operand = (
            f"{parsed.context_locator}:{parsed.memory_selector.casefold()}"
            if parsed.context_locator is not None
            else parsed.memory_selector.casefold()
        )
        target = resolve_local_direct_memory_locator(
            store,
            memory_operand,
            current=current_name,
        )
        context = store.load_direct(target.context_name)
        memory = context.memories.get(target.memory_uid)
        if not isinstance(memory, Memory):
            raise ConformanceError(
                "The selected Conformance Rule is not a direct ordinary Memory."
            )
        rule = ConformanceRule(memory.uid, "r1", memory.content)
        return FrozenConformanceRulesOperand(
            kind="MEMORY",
            label=f"MEMORY {context.name}:{memory.uid[:8]}",
            rules=(rule,),
            context_name=context.name,
            context_uid=context.uid,
            memory_uid=memory.uid,
            memory_digest=_memory_digest(memory),
        )

    assert isinstance(parsed, ExistingContextOperand)
    canonical_name = resolve_context_locator(parsed.locator, current=current_name)
    if store.context_exists(canonical_name):
        context = store.load_direct(canonical_name)
        memories = _direct_memories(context)
        if not memories:
            raise ConformanceError("The Rules Context contains no direct Memories.")
        return FrozenConformanceRulesOperand(
            kind="CONTEXT",
            label=context.name,
            rules=_rules_from_memories(memories),
            context_name=context.name,
            context_uid=context.uid,
            context_digest=context_record_digest(context),
        )
    short_target = try_resolve_short_local_direct_memory_locator(
        store,
        parsed.locator,
        current=current_name,
    )
    if short_target is not None:
        context = store.load_direct(short_target.context_name)
        memory = context.memories.get(short_target.memory_uid)
        if not isinstance(memory, Memory):  # pragma: no cover - resolver invariant
            raise ConformanceError(
                "The selected Conformance Rule is not a direct ordinary Memory."
            )
        rule = ConformanceRule(memory.uid, "r1", memory.content)
        return FrozenConformanceRulesOperand(
            kind="MEMORY",
            label=f"MEMORY {context.name}:{memory.uid[:8]}",
            rules=(rule,),
            context_name=context.name,
            context_uid=context.uid,
            memory_uid=memory.uid,
            memory_digest=_memory_digest(memory),
        )
    if is_relative_context_locator(parsed.locator):
        raise ConformanceError(
            f"Conformance Rules Context locator {parsed.locator!r} does not "
            "exist locally."
        )

    rule = _literal_rule(parsed.locator)
    return FrozenConformanceRulesOperand(
        kind="TEXT",
        label=f"TEXT {rule.content}",
        rules=(rule,),
    )


def freeze_context_conformance(
    target: Context,
    rules_context: Context,
) -> FrozenContextConformance:
    """Freeze two local direct Contexts without interpreting hierarchy."""

    if target.uid == rules_context.uid:
        raise ConformanceError(
            "Conformance Target and Rules must be distinct Contexts."
        )
    rule_memories = _direct_memories(rules_context)
    if not rule_memories:
        raise ConformanceError("The Rules Context contains no direct Memories.")
    rules = _rules_from_memories(rule_memories)
    subjects = _subjects_from_target(target, rules)
    return FrozenContextConformance(
        target_name=target.name,
        rules_name=rules_context.name,
        target_digest=context_record_digest(target),
        rules_digest=context_record_digest(rules_context),
        rules=rules,
        subjects=subjects,
    )


def freeze_ground_conformance(
    workspace: GroundWorkspace,
) -> FrozenGroundConformance:
    """Freeze physical Rule and Example Memories for Context Conformance."""

    try:
        rule_memories = project_ordinary_memories(
            workspace.rules,
            operation="Ground workspace Conformance",
        )
        example_memories = project_ordinary_memories(
            workspace.examples,
            operation="Ground workspace Conformance",
        )
    except GroundWorkspaceProjectionError as error:
        raise ConformanceError(str(error)) from error
    if not rule_memories:
        raise ConformanceError("The Ground workspace contains no Rules to check.")
    if not example_memories:
        raise ConformanceError("The Ground workspace contains no Examples to check.")
    rules = _rules_from_memories(rule_memories)
    rule_uids = tuple(rule.uid for rule in rules)
    subjects = tuple(
        ConformanceSubject(
            uid=memory.uid,
            alias=f"e{index}",
            content=memory.content,
            role="EXAMPLE",
            linked_rule_uids=rule_uids,
        )
        for index, memory in enumerate(example_memories, 1)
    )
    digest = hashlib.sha256(
        "\0".join(
            (
                workspace.uid,
                context_record_digest(workspace.root),
                context_record_digest(workspace.rules),
                context_record_digest(workspace.examples),
            )
        ).encode("utf-8")
    ).hexdigest()
    return FrozenGroundConformance(
        ground_name=workspace.name,
        ground_digest=digest,
        rules=rules,
        subjects=subjects,
    )


def execute_context_conformance(
    *,
    store: MemoryStore,
    target_name: str,
    rules_name: str,
    provider_factory: ConformanceProviderFactory,
) -> ConformanceReport:
    """Check two exact local Contexts and reject a concurrent input change."""

    if not store.context_exists(target_name) or not store.context_exists(rules_name):
        raise ConformanceError(
            "Context Conformance currently requires local Target and Rules Contexts."
        )
    return execute_context_conformance_with_rules_operand(
        store=store,
        target_name=target_name,
        rules_operand=rules_name,
        current_name=None,
        provider_factory=provider_factory,
    )


def execute_context_conformance_with_rules_operand(
    *,
    store: MemoryStore,
    target_name: str,
    rules_operand: str,
    current_name: str | None,
    provider_factory: ConformanceProviderFactory,
) -> ConformanceReport:
    """Check one local Target against a Context, Memory, or literal Rule.

    Context Conformance still owns one complete Target Context frame. Only its
    Rules endpoint is widened here; Ground and Audit keep their existing typed
    Context contracts.
    """

    if not store.context_exists(target_name):
        raise ConformanceError(
            "Context Conformance currently requires a local Target Context."
        )
    target = store.load_direct(target_name)
    frozen_rules = freeze_conformance_rules_operand(
        store,
        rules_operand,
        current_name=current_name,
    )
    if frozen_rules.kind == "CONTEXT" and frozen_rules.context_uid == target.uid:
        raise ConformanceError(
            "Conformance Target and Rules must be distinct Contexts."
        )
    subjects = _subjects_from_target(target, frozen_rules.rules)
    target_digest = context_record_digest(target)
    report = check_context_conformance(
        source_label=target.name,
        rules_label=frozen_rules.label,
        rules=frozen_rules.rules,
        subjects=subjects,
        provider=provider_factory(),
    )

    if not store.context_exists(target_name) or (
        context_record_digest(store.load_direct(target_name)) != target_digest
    ):
        raise ConformanceError(
            "The Target or Rules source changed during Conformance; "
            "no report was published."
        )
    if frozen_rules.kind == "CONTEXT":
        assert frozen_rules.context_name is not None
        if not store.context_exists(frozen_rules.context_name) or (
            context_record_digest(store.load_direct(frozen_rules.context_name))
            != frozen_rules.context_digest
        ):
            raise ConformanceError(
                "The Target or Rules source changed during Conformance; "
                "no report was published."
            )
    elif frozen_rules.kind == "MEMORY":
        assert frozen_rules.context_name is not None
        assert frozen_rules.context_uid is not None
        assert frozen_rules.memory_uid is not None
        if not store.context_exists(frozen_rules.context_name):
            raise ConformanceError(
                "The Target or Rules source changed during Conformance; "
                "no report was published."
            )
        current_context = store.load_direct(frozen_rules.context_name)
        current_memory = current_context.memories.get(frozen_rules.memory_uid)
        if (
            current_context.uid != frozen_rules.context_uid
            or not isinstance(current_memory, Memory)
            or _memory_digest(current_memory) != frozen_rules.memory_digest
        ):
            raise ConformanceError(
                "The Target or Rules source changed during Conformance; "
                "no report was published."
            )
    return report


def execute_ground_conformance(
    *,
    store: MemoryStore,
    ground_name: str,
    provider_factory: ConformanceProviderFactory,
) -> ConformanceReport:
    """Check one exact physical Ground Example lane against its Rules."""

    frozen = freeze_ground_conformance(load_ground_workspace(store, ground_name))
    report = check_context_conformance(
        source_label=f"GROUND EXAMPLES · {ground_name}",
        rules_label=f"GROUND RULES · {ground_name}",
        rules=frozen.rules,
        subjects=frozen.subjects,
        provider=provider_factory(),
    )
    current = freeze_ground_conformance(load_ground_workspace(store, ground_name))
    if current != frozen:
        raise ConformanceError(
            "The Ground changed during Conformance; no report was published."
        )
    return report
