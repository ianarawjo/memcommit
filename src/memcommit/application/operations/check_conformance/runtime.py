"""Local Store adapters for the shared Conformance core."""

from __future__ import annotations

from memcommit.application.authorization.context_operation import (
    authorized_context_operation,
)
from memcommit.application.operations.check_conformance.inputs import (
    ConformanceInputError,
    ConformanceInputs,
    capture_conformance_dependency,
    prepare_conformance_inputs,
    revalidate_conformance_inputs,
)
from memcommit.application.context_access.access import resolve_context_access

from dataclasses import dataclass
import hashlib
from typing import Literal, Protocol
import uuid

from memcommit.application.operations.check_conformance.model import (
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
)
from memcommit.application.capabilities.durable_uid_resolution import (
    is_unresolved_uid_selector,
)
from memcommit.application.capabilities.local_target_lookup import (
    DirectMemoryNotFoundError,
    resolve_local_context_memory_target,
)
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectMemoryTarget,
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
    inputs: ConformanceInputs | None = None


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

    try:
        target = resolve_local_context_memory_target(
            store,
            text,
            current=current_name,
        )
    except (FileNotFoundError, DirectMemoryNotFoundError) as error:
        try:
            access = resolve_context_access(
                store,
                text,
                current_name=current_name,
                required_permission="READ",
            )
        except FileNotFoundError:
            if is_relative_context_locator(text):
                raise ConformanceError(
                    f"Conformance Rules Context locator {text!r} does not exist locally."
                ) from error
            if is_unresolved_uid_selector(text):
                raise ConformanceError(str(error)) from error
            rule = _literal_rule(text)
            return FrozenConformanceRulesOperand(
                kind="TEXT", label=f"TEXT {rule.content}", rules=(rule,)
            )
        target = ContextTarget(access.access_name)

    if isinstance(target, DirectMemoryTarget):
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
            inputs=ConformanceInputs(
                context,
                (Memory(memory.uid, memory.content),),
                (capture_conformance_dependency(store, context, memory=memory),),
            ),
        )
    assert isinstance(target, ContextTarget)
    prepared = prepare_conformance_inputs(store, target.context_name)
    context = prepared.root
    memories = prepared.memories
    if not memories:
        raise ConformanceError("The Rules Context contains no readable Memories.")
    return FrozenConformanceRulesOperand(
        kind="CONTEXT",
        label=context.name,
        rules=_rules_from_memories(memories),
        context_name=context.name,
        context_uid=context.uid,
        context_digest=context_record_digest(context),
        inputs=prepared,
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


def execute_context_conformance(
    *,
    store: MemoryStore,
    target_name: str,
    rules_name: str,
    provider_factory: ConformanceProviderFactory,
) -> ConformanceReport:
    """Check two exact readable Contexts with the common directional route."""

    rules_access = resolve_context_access(
        store,
        rules_name,
        current_name=None,
        required_permission="READ",
    )
    return execute_context_conformance_with_rules_operand(
        store=store,
        target_name=target_name,
        rules_operand=rules_access.access_name,
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
    """Check a complete readable Target frame against the selected Rules."""

    try:
        target_inputs = prepare_conformance_inputs(store, target_name)
        target = target_inputs.root
        frozen_rules = freeze_conformance_rules_operand(
            store, rules_operand, current_name=current_name
        )
        if frozen_rules.kind == "CONTEXT" and frozen_rules.context_uid == target.uid:
            raise ConformanceError(
                "Conformance Target and Rules must be distinct Contexts."
            )
        target_memories = target_inputs.memories
        if not target_memories:
            raise ConformanceError("The Target Context contains no readable Memories.")
        rule_uids = tuple(rule.uid for rule in frozen_rules.rules)
        subjects = tuple(
            ConformanceSubject(
                uid=memory.uid,
                alias=f"m{index:06d}",
                content=memory.content,
                linked_rule_uids=rule_uids,
            )
            for index, memory in enumerate(target_memories, 1)
        )
        dependencies = (
            *target_inputs.dependencies,
            *(
                frozen_rules.inputs.dependencies
                if frozen_rules.inputs is not None
                else ()
            ),
        )
        # Recheck after both endpoints are frozen and before disclosing them.
        # The same versions must still hold after the bounded provider turn.
        checks = tuple(
            (item.access, ("READ",)) for item in dependencies if item.access is not None
        )
        with authorized_context_operation(checks) as registry:
            revalidate_conformance_inputs(
                dependencies, active_store=store, registry=registry
            )
        report = check_context_conformance(
            source_label=target.name,
            rules_label=frozen_rules.label,
            rules=frozen_rules.rules,
            subjects=subjects,
            provider=provider_factory(),
        )
        try:
            with authorized_context_operation(checks) as registry:
                revalidate_conformance_inputs(
                    dependencies, active_store=store, registry=registry
                )
        except ConformanceInputError as error:
            raise ConformanceError(
                "The Target or Rules source changed during Conformance; no report was published."
            ) from error
        return report
    except ConformanceInputError as error:
        raise ConformanceError(str(error)) from error
