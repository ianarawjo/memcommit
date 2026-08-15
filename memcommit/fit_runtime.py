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
from memcommit.ground import GROUND_SCHEMA_VERSION, GroundSession
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
    """Project a version-2 Ground into the first public Fit contract.

    Version 2 stores a concrete input and expected output rather than a native
    proposition.  The one-line proposition is display metadata; exact replay
    remains the authoritative evaluator and never exposes the expected value
    to the provider.
    """

    if session.schema_version != GROUND_SCHEMA_VERSION:
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
        and bool(item.expected.strip())
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
                statement=f"{item.content} -> {item.expected}",
                projection="EXACT_OUTPUT",
                # Exact output can depend on composed Rules beyond the Rule
                # that originally motivated this Example.
                rule_uids=rule_uids,
                input_text=item.content,
                expected_output=item.expected,
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

