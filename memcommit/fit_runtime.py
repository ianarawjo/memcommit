"""MemoryStore adapter for the operation-independent Fit core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.fit import (
    FitError,
    FitExample,
    FitProvider,
    FitReport,
    FitRule,
    fit_ground_examples,
)
from memcommit.fit_application import FitRequest, FitResult
from memcommit.ground import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundItem,
    GroundSession,
    is_bound_ground_schema,
)
from memcommit.fit_store import FitStore
from memcommit.store import MemoryStore, ground_session_record_digest


class FitProviderFactory(Protocol):
    def __call__(self) -> FitProvider:
        """Connect only after the Ground snapshot is locally validated."""


@dataclass(frozen=True)
class FrozenGroundFit:
    ground_uid: str
    ground_name: str
    ground_revision: int
    ground_digest: str
    rules: tuple[FitRule, ...]
    examples: tuple[FitExample, ...]


def freeze_ground_fit(session: GroundSession) -> FrozenGroundFit:
    """Project one immutable Ground revision into the public Fit contract.

    Version 2 preserves its exact-output replay contract. Version 3 evaluates
    each native Example proposition and treats optional I/O, evidence, and
    placement metadata as non-authoritative projections. An unlinked version-3
    Example applies to the complete active Rule set; explicit links narrow the
    judgment to exactly those Rules.
    """

    if not is_bound_ground_schema(session.schema_version):
        raise FitError("Fit currently requires a bound Ground workbench.")
    active_rules = tuple(
        item
        for item in session.items
        if item.kind == "RULE" and item.status in {"PROPOSED", "ACCEPTED"}
    )
    examples = tuple(
        item
        for item in session.items
        if item.kind == "CASE"
        and item.status in {"PROPOSED", "ACCEPTED"}
        and item.disposition == "INCLUDE"
        and (
            bool(item.proposition.strip())
            if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
            else bool(item.expected.strip())
        )
    )
    if not active_rules:
        raise FitError("The Ground contains no active Rules to fit.")
    if not examples:
        raise FitError("The Ground contains no active Examples to fit.")
    rules = tuple(
        FitRule(item.uid, f"r{index}", item.content)
        for index, item in enumerate(active_rules, 1)
    )
    rule_uids = tuple(rule.uid for rule in rules)
    active_rule_uids = set(rule_uids)

    def example_rule_uids(item: GroundItem) -> tuple[str, ...]:
        if session.schema_version != GROUND_PROPOSITION_SCHEMA_VERSION:
            # Exact output can depend on composed Rules beyond the Rule that
            # originally motivated this legacy Example.
            return rule_uids
        if any(uid not in active_rule_uids for uid in item.related_uids):
            raise FitError("A Ground Example links a Rule that is not active.")
        linked = tuple(item.related_uids)
        if linked:
            return linked
        return rule_uids

    proposition_schema = (
        session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
    )
    return FrozenGroundFit(
        ground_uid=session.uid,
        ground_name=session.contract_name,
        ground_revision=session.revision,
        ground_digest=ground_session_record_digest(session),
        rules=rules,
        examples=tuple(
            FitExample(
                uid=item.uid,
                alias=f"e{index}",
                statement=item.proposition or f"{item.content} -> {item.expected}",
                projection=(
                    "PROPOSITION" if proposition_schema else "EXACT_OUTPUT"
                ),
                rule_uids=example_rule_uids(item),
                input_text=None if proposition_schema else item.content,
                expected_output=None if proposition_schema else item.expected,
            )
            for index, item in enumerate(examples, 1)
        ),
    )


def execute_ground_fit(
    *,
    store: MemoryStore,
    ground_name: str,
    provider_factory: FitProviderFactory,
) -> FitReport:
    """Execute Fit over one exact Ground revision and detect a concurrent edit."""

    session = store.load_ground_session(ground_name)
    if session is None:
        raise FitError(f"Ground '{ground_name}' was not found.")
    frozen = freeze_ground_fit(session)
    report = fit_ground_examples(
        ground_uid=frozen.ground_uid,
        ground_name=frozen.ground_name,
        ground_revision=frozen.ground_revision,
        ground_digest=frozen.ground_digest,
        rules=frozen.rules,
        examples=frozen.examples,
        provider=provider_factory(),
    )
    current = store.load_ground_session(ground_name)
    if current is None or ground_session_record_digest(current) != frozen.ground_digest:
        raise FitError("The Ground changed during Fit; no report was published.")
    return report


def execute_and_save_ground_fit(
    *,
    store: MemoryStore,
    ground_name: str,
    provider_factory: FitProviderFactory,
) -> FitReport:
    """Run Fit and publish its immutable receipt at one freshness boundary."""

    report = execute_ground_fit(
        store=store,
        ground_name=ground_name,
        provider_factory=provider_factory,
    )
    FitStore(store).save(report)
    return report


def run_fit_with_store(
    request: FitRequest,
    *,
    store: MemoryStore,
    provider_factory: FitProviderFactory,
) -> FitResult:
    """Execute or reopen Fit behind one interface-independent runtime port."""

    if not isinstance(request, FitRequest):
        raise TypeError("Fit runtime requires a typed request.")
    if request.receipt_uid is None:
        return FitResult(
            execute_and_save_ground_fit(
                store=store,
                ground_name=request.ground_name,
                provider_factory=provider_factory,
            ),
            current=True,
        )

    fit_store = FitStore(store)
    report = fit_store.load(request.receipt_uid)
    if report.ground_name != request.ground_name:
        raise FitError("The Fit receipt belongs to a different Ground.")
    session = store.load_ground_session(request.ground_name)
    if session is None:
        raise FitError(f"Ground '{request.ground_name}' was not found.")
    latest = fit_store.latest_for_ground(session)
    return FitResult(
        report,
        current=(
            latest is not None
            and latest.report.uid == report.uid
            and latest.current
        ),
    )
