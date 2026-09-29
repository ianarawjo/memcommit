"""Retained structural decision rounds and their serialization invariants."""

from copy import deepcopy
from dataclasses import asdict, dataclass, field

from memcommit.application.capabilities.resolution.workbench import ResolutionOption
from memcommit.core.context import Context

from .analysis.candidate import MergeCandidate, digest
from .analysis.choices import (
    EXACT_DECISIONS,
    MergeConflictAnalysis,
    MergeConflictDecision,
    MergeConflictIssue,
    MergeDecisionSet,
    finalize_merge_decisions,
    merge_item_kind,
)
from .analysis.conflicts import MergeConflictReport, analyze_merge_conflicts


@dataclass(frozen=True, slots=True)
class LiteralMergeRound:
    """Merge-owned evidence; no Audit is fabricated for structural choices."""

    candidate: MergeCandidate
    report: MergeConflictReport
    issues: tuple[MergeConflictIssue, ...]
    decisions: MergeDecisionSet
    _before: Context = field(repr=False)
    _after: Context = field(repr=False)
    input_result_uids: tuple[tuple[str, str], ...]

    def __post_init__(self):
        object.__setattr__(self, "_before", deepcopy(self._before))
        object.__setattr__(self, "_after", deepcopy(self._after))
        if self.decisions.revision != self.candidate.revision:
            raise ValueError("Merge decisions refer to another candidate.")
        if self._before.to_dict() != self.candidate.context().to_dict():
            raise ValueError("Merge round belongs to another candidate.")
        if self.report != analyze_merge_conflicts(self.candidate):
            raise ValueError("Merge findings differ from the frozen candidate.")
        if tuple(issue.uid for issue in self.issues) != tuple(
            finding.uid for finding in self.report.findings
        ):
            raise ValueError("Merge round does not cover its structural findings.")
        for issue, finding in zip(self.issues, self.report.findings, strict=True):
            members = (*finding.target_uids, finding.source_uid)
            kinds = {
                merge_item_kind(self.candidate.original_item(uid)) for uid in members
            }
            if (
                issue.kind != "MERGE_CONFLICT"
                or issue.classification != finding.kind.value
                or issue.item_uids != members
                or issue.item_kind
                != (next(iter(kinds)) if len(kinds) == 1 else "MIXED")
                or issue.reason != finding.reason
                or not issue.choices
                or not {choice.uid for choice in issue.choices} <= EXACT_DECISIONS
            ):
                raise ValueError("Merge issue differs from its structural finding.")
        mappings = dict(self.input_result_uids)
        if len(mappings) != len(self.input_result_uids) or not set(mappings) <= {
            origin.uid for origin in self.candidate.origins
        }:
            raise ValueError(
                "Merge result mapping does not identify unique input items."
            )
        finalize_merge_decisions(
            MergeConflictAnalysis(self.candidate, self.report, self.issues),
            self.decisions.decisions,
        )

    def before(self):
        return deepcopy(self._before)

    def after(self):
        return deepcopy(self._after)

    @property
    def effects(self):
        return ()

    def affected_uids(self, issue_uid):
        return next(issue.item_uids for issue in self.issues if issue.uid == issue_uid)

    def to_dict(self):
        return dict(
            candidate=self.candidate.to_dict(),
            report=asdict(self.report),
            issues=[asdict(issue) for issue in self.issues],
            decisions=[asdict(item) for item in self.decisions.decisions],
            before=self._before.to_dict(),
            after=self._after.to_dict(),
            input_result_uids=list(self.input_result_uids),
        )

    @classmethod
    def from_dict(cls, value):
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "phase",
                "candidate",
                "report",
                "issues",
                "decisions",
                "before",
                "after",
                "input_result_uids",
                "revision",
            }
            or value["phase"] != "LITERAL"
        ):
            raise ValueError("Invalid structural Merge round.")
        candidate = MergeCandidate.from_dict(value["candidate"])
        report = analyze_merge_conflicts(candidate)
        if digest(asdict(report)) != digest(value["report"]):
            raise ValueError("Merge round report differs from its candidate.")
        return cls(
            candidate,
            report,
            tuple(
                MergeConflictIssue(
                    **(
                        item
                        | {
                            "item_uids": tuple(item["item_uids"]),
                            "choices": tuple(
                                ResolutionOption(**c) for c in item["choices"]
                            ),
                        }
                    )
                )
                for item in value["issues"]
            ),
            MergeDecisionSet(
                value["revision"],
                tuple(MergeConflictDecision(**d) for d in value["decisions"]),
            ),
            Context.from_dict(value["before"]),
            Context.from_dict(value["after"]),
            tuple(tuple(pair) for pair in value["input_result_uids"]),
        )
