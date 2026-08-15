"""Local Store adapters for the shared Conformance core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.conformance import (
    ConformanceError,
    ConformanceProvider,
    ConformanceReport,
    ConformanceRule,
    ConformanceSubject,
    check_case_conformance,
    check_context_conformance,
)
from memcommit.context import Context, Memory
from memcommit.ground import GroundSession, is_bound_ground_schema
from memcommit.store import (
    MemoryStore,
    context_record_digest,
    ground_session_record_digest,
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


def _direct_memories(ctx: Context) -> tuple[Memory, ...]:
    return tuple(item for item in ctx.iter_items() if isinstance(item, Memory))


def freeze_context_conformance(
    target: Context,
    rules_context: Context,
) -> FrozenContextConformance:
    """Freeze two local direct Contexts without interpreting hierarchy."""

    if target.uid == rules_context.uid:
        raise ConformanceError("Conformance Target and Rules must be distinct Contexts.")
    rule_memories = _direct_memories(rules_context)
    target_memories = _direct_memories(target)
    if not rule_memories:
        raise ConformanceError("The Rules Context contains no direct Memories.")
    if not target_memories:
        raise ConformanceError("The Target Context contains no direct Memories.")
    rules = tuple(
        ConformanceRule(memory.uid, f"r{index}", memory.content)
        for index, memory in enumerate(rule_memories, 1)
    )
    rule_uids = tuple(rule.uid for rule in rules)
    subjects = tuple(
        ConformanceSubject(
            uid=memory.uid,
            alias=f"m{index:06d}",
            content=memory.content,
            linked_rule_uids=rule_uids,
        )
        for index, memory in enumerate(target_memories, 1)
    )
    return FrozenContextConformance(
        target_name=target.name,
        rules_name=rules_context.name,
        target_digest=context_record_digest(target),
        rules_digest=context_record_digest(rules_context),
        rules=rules,
        subjects=subjects,
    )


def freeze_ground_conformance(session: GroundSession) -> FrozenGroundConformance:
    """Freeze executable Rule/Ground-Memory pairs from one saved Ground."""

    if not is_bound_ground_schema(session.schema_version):
        raise ConformanceError("Case Conformance requires a bound Ground workbench.")
    active_rules = tuple(
        item
        for item in session.items
        if item.kind == "RULE" and item.status in {"PROPOSED", "ACCEPTED"}
    )
    executable_cases = tuple(
        item
        for item in session.items
        if item.kind == "CASE"
        and item.status in {"PROPOSED", "ACCEPTED"}
        and item.disposition == "INCLUDE"
        and bool(item.expected.strip())
    )
    if not active_rules:
        raise ConformanceError("The Ground contains no active Rules to check.")
    if not executable_cases:
        raise ConformanceError(
            "The Ground contains no active INCLUDE Memories with expected outputs."
        )
    rule_alias_by_uid = {
        item.uid: f"r{index}" for index, item in enumerate(active_rules, 1)
    }
    rules = tuple(
        ConformanceRule(item.uid, rule_alias_by_uid[item.uid], item.content)
        for item in active_rules
    )
    active_rule_uids = tuple(rule.uid for rule in rules)
    subjects: list[ConformanceSubject] = []
    for index, item in enumerate(executable_cases, 1):
        primary_links = tuple(
            uid for uid in item.related_uids if uid in rule_alias_by_uid
        )
        if primary_links != item.related_uids:
            raise ConformanceError(
                "An executable Ground Memory links a non-active Rule."
            )
        subjects.append(
            ConformanceSubject(
                uid=item.uid,
                alias=f"c{index}",
                content=item.content,
                expected=item.expected,
                role=item.case_role,
                # A Ground Memory has one provenance link, but an executable
                # outcome may compose several active Rules. Freeze the whole
                # Rule set for prediction instead of pretending the primary
                # provenance link is the complete execution dependency.
                linked_rule_uids=active_rule_uids,
            )
        )
    return FrozenGroundConformance(
        ground_name=session.contract_name,
        ground_digest=ground_session_record_digest(session),
        rules=rules,
        subjects=tuple(subjects),
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
    target = store.load_direct(target_name)
    rules_context = store.load_direct(rules_name)
    frozen = freeze_context_conformance(target, rules_context)
    report = check_context_conformance(
        source_label=frozen.target_name,
        rules_label=frozen.rules_name,
        rules=frozen.rules,
        subjects=frozen.subjects,
        provider=provider_factory(),
    )
    if (
        context_record_digest(store.load_direct(target_name)) != frozen.target_digest
        or context_record_digest(store.load_direct(rules_name)) != frozen.rules_digest
    ):
        raise ConformanceError(
            "The Target or Rules Context changed during Conformance; no report was published."
        )
    return report


def execute_ground_conformance(
    *,
    store: MemoryStore,
    ground_name: str,
    provider_factory: ConformanceProviderFactory,
) -> ConformanceReport:
    """Check one exact saved Ground revision without opening its live Contexts."""

    session = store.load_ground_session(ground_name)
    if session is None:
        raise ConformanceError(f"Ground '{ground_name}' was not found.")
    frozen = freeze_ground_conformance(session)
    report = check_case_conformance(
        source_label=f"GROUND · {ground_name}",
        rules_label=f"GROUND RULES · {ground_name}",
        rules=frozen.rules,
        subjects=frozen.subjects,
        provider=provider_factory(),
    )
    current = store.load_ground_session(ground_name)
    if current is None or ground_session_record_digest(current) != frozen.ground_digest:
        raise ConformanceError(
            "The Ground changed during Conformance; no report was published."
        )
    return report
