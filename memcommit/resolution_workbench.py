"""Operation-neutral projection and actions for interactive resolution.

The common workbench owns presentation identity and navigation only.  Meld,
Atomize, Update, and a future Reconcile adapter remain authoritative for their
semantic artifacts, provider calls, persistence, reanalysis, and mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from memcommit.reviewing.result_workbench import ResultRef


RESOLUTION_TEXT_LIMIT = 20_000
RESOLUTION_LABEL_LIMIT = 500
RESOLUTION_KEY_LIMIT = 500

ResolutionCapability = Literal[
    "SUBMIT_ITEM",
    "SUBMIT_ALL",
    "INCORPORATE_AND_APPLY",
    "PRESERVE_ALL",
    "DEFER",
    "ACCEPT",
]
ResolutionItemRole = Literal["DECISION", "OPTIONAL_REVIEW", "CHANGE"]
ResolutionItemObligation = Literal["REQUIRED", "OPTIONAL", "NONE"]
ResolutionResponseState = Literal["OPEN", "ANSWERED", "NOT_APPLICABLE"]
ResolutionAcceptMode = Literal["CHANGES", "AS_IS"]
ResolutionActionKind = Literal[
    "SUBMIT_ITEM",
    "SUBMIT_ALL",
    "INCORPORATE_AND_APPLY",
    "PRESERVE_ALL",
    "DEFER",
    "ACCEPT",
    "CHANGE_DESTINATION",
    "HANDOFF",
    "CLOSE",
]

_CAPABILITIES = {
    "SUBMIT_ITEM",
    "SUBMIT_ALL",
    "INCORPORATE_AND_APPLY",
    "PRESERVE_ALL",
    "DEFER",
    "ACCEPT",
}
_ACTION_KINDS = {*_CAPABILITIES, "CHANGE_DESTINATION", "HANDOFF", "CLOSE"}


class ResolutionWorkbenchError(ValueError):
    """Invalid common resolution projection, navigation, or action."""


def _text(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = RESOLUTION_TEXT_LIMIT,
    one_line: bool = False,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
        or (one_line and any(character in value for character in "\r\n"))
    ):
        raise ResolutionWorkbenchError(f"Invalid {label}.")
    return value


def _items(value: object, item_type: type, label: str) -> tuple:
    if not isinstance(value, tuple) or any(
        not isinstance(item, item_type) for item in value
    ):
        raise ResolutionWorkbenchError(f"Invalid {label}.")
    return value


@dataclass(frozen=True)
class ResolutionMetric:
    """One adapter-computed orientation value in the compact header."""

    label: str
    value: str

    def __post_init__(self) -> None:
        _text(
            self.label,
            "resolution metric label",
            limit=RESOLUTION_LABEL_LIMIT,
            one_line=True,
        )
        _text(
            self.value,
            "resolution metric value",
            limit=RESOLUTION_LABEL_LIMIT,
            one_line=True,
        )


@dataclass(frozen=True)
class ResolutionContextLocation:
    """One operation-owned Context endpoint shown as report orientation."""

    role: str
    name: str
    state: str = ""

    def __post_init__(self) -> None:
        _text(
            self.role,
            "resolution Context role",
            limit=RESOLUTION_LABEL_LIMIT,
            one_line=True,
        )
        _text(
            self.name,
            "resolution Context name",
            limit=RESOLUTION_KEY_LIMIT,
            one_line=True,
        )
        _text(
            self.state,
            "resolution Context state",
            empty=True,
            limit=RESOLUTION_LABEL_LIMIT,
            one_line=True,
        )


@dataclass(frozen=True)
class ResolutionOverviewSection:
    """One operation-declared semantic stop inside the report overview."""

    uid: str
    heading: str
    text: str
    focus_body: bool = True

    def __post_init__(self) -> None:
        _text(
            self.uid,
            "resolution overview-section uid",
            limit=RESOLUTION_KEY_LIMIT,
            one_line=True,
        )
        _text(
            self.heading,
            "resolution overview-section heading",
            limit=RESOLUTION_LABEL_LIMIT,
            one_line=True,
        )
        # An explicitly declared empty section communicates a bounded absence
        # (for example, no unresolved Atomize issue) and remains navigable.
        _text(self.text, "resolution overview-section text", empty=True)
        if not isinstance(self.focus_body, bool):
            raise ResolutionWorkbenchError(
                "Invalid resolution overview-section focus scope."
            )


def resolution_overview_text(
    sections: tuple[ResolutionOverviewSection, ...],
) -> str:
    """Return the legacy flat report text without rediscovering boundaries."""

    return "\n\n".join(f"{section.heading}\n{section.text}" for section in sections)


@dataclass(frozen=True)
class ResolutionOption:
    """One operation-owned answer option addressed by opaque identity."""

    uid: str
    label: str
    text: str

    def __post_init__(self) -> None:
        _text(
            self.uid,
            "resolution option uid",
            limit=RESOLUTION_KEY_LIMIT,
            one_line=True,
        )
        _text(
            self.label,
            "resolution option label",
            limit=RESOLUTION_LABEL_LIMIT,
            one_line=True,
        )
        _text(self.text, "resolution option text")


@dataclass(frozen=True)
class ResolutionMemoryRow:
    """One visible Memory-shaped row backed by an optional semantic ref."""

    ordinal: int
    content: str
    evidence: tuple[str, ...] = ()
    ref: ResultRef | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal < 1
        ):
            raise ResolutionWorkbenchError("Invalid resolution Memory ordinal.")
        _text(self.content, "resolution Memory row content")
        evidence = _items(self.evidence, str, "resolution Memory row evidence")
        for span in evidence:
            _text(span, "resolution Memory row evidence span")
        if len(set(evidence)) != len(evidence):
            raise ResolutionWorkbenchError(
                "Duplicate resolution Memory row evidence span."
            )
        if self.ref is not None and not isinstance(self.ref, ResultRef):
            raise ResolutionWorkbenchError("Invalid resolution Memory row reference.")


@dataclass(frozen=True)
class ResolutionDetailBlock:
    """One adapter-authored detail block rendered without reinterpretation."""

    heading: str
    text: str
    refs: tuple[ResultRef, ...] = ()
    memory_rows: tuple[ResolutionMemoryRow, ...] = ()

    def __post_init__(self) -> None:
        _text(
            self.heading,
            "resolution detail heading",
            limit=RESOLUTION_LABEL_LIMIT,
            one_line=True,
        )
        rows = _items(
            self.memory_rows,
            ResolutionMemoryRow,
            "resolution detail Memory rows",
        )
        _text(self.text, "resolution detail text", empty=bool(rows))
        if not self.text and not rows:
            raise ResolutionWorkbenchError(
                "A resolution detail block requires text or Memory rows."
            )
        if len({row.ordinal for row in rows}) != len(rows):
            raise ResolutionWorkbenchError(
                "Duplicate resolution detail Memory ordinal."
            )
        refs = _items(self.refs, ResultRef, "resolution detail references")
        if len(set(refs)) != len(refs):
            raise ResolutionWorkbenchError("Duplicate resolution detail reference.")


@dataclass(frozen=True)
class ResolutionIssueSource:
    """One exact Memory shown inside an actionable quality issue."""

    label: str
    context_name: str
    memory_uid: str
    content: str
    ordinal: int | None = None

    def __post_init__(self) -> None:
        _text(self.label, "resolution source label", one_line=True)
        _text(self.context_name, "resolution source Context", one_line=True)
        _text(self.memory_uid, "resolution source Memory uid", one_line=True)
        _text(self.content, "resolution source content", empty=True)
        if self.ordinal is not None and (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal < 1
        ):
            raise ResolutionWorkbenchError("Invalid resolution source ordinal.")


@dataclass(frozen=True)
class ResolutionIssueClaim:
    """One frame-owned claim supported by one or more exact Memories."""

    label: str
    context_name: str
    sources: tuple[ResolutionIssueSource, ...]

    def __post_init__(self) -> None:
        _text(self.label, "resolution claim label", one_line=True)
        _text(self.context_name, "resolution claim Context", one_line=True)
        sources = _items(
            self.sources,
            ResolutionIssueSource,
            "resolution claim sources",
        )
        if not sources:
            raise ResolutionWorkbenchError(
                "A resolution claim requires a source Memory."
            )


@dataclass(frozen=True)
class ResolutionIssueEvidence:
    """One source-linked assessment inside an actionable issue."""

    group_heading: str
    sources_heading: str
    classification: str
    reason_heading: str
    reason: str
    sources: tuple[ResolutionIssueSource, ...] = ()
    claims: tuple[ResolutionIssueClaim, ...] = ()
    criterion_blocks: tuple[ResolutionDetailBlock, ...] = ()

    def __post_init__(self) -> None:
        # A relation/assessment label and the label for its exact source frame
        # are different hierarchy levels. Keeping both typed prevents an
        # adapter from presenting SOURCE MEMORY as if it owned Classification.
        _text(
            self.group_heading,
            "resolution evidence-group heading",
            empty=True,
            one_line=True,
        )
        _text(
            self.sources_heading,
            "resolution evidence-source heading",
            one_line=True,
        )
        sources = _items(
            self.sources,
            ResolutionIssueSource,
            "resolution evidence sources",
        )
        claims = _items(
            self.claims,
            ResolutionIssueClaim,
            "resolution evidence claims",
        )
        if bool(sources) == bool(claims):
            raise ResolutionWorkbenchError(
                "Resolution issue evidence requires either sources or claims."
            )
        _items(
            self.criterion_blocks,
            ResolutionDetailBlock,
            "resolution criterion blocks",
        )
        _text(self.classification, "resolution issue classification")
        _text(self.reason_heading, "resolution issue reason heading", one_line=True)
        _text(self.reason, "resolution issue reason")

    @property
    def source_groups(self) -> tuple[ResolutionIssueClaim, ...]:
        """Return explicit claims or one compact group per ungrouped source."""
        if self.claims:
            return self.claims
        return tuple(
            ResolutionIssueClaim(
                label=source.label,
                context_name=source.context_name,
                sources=(source,),
            )
            for source in self.sources
        )


@dataclass(frozen=True)
class ResolutionIssuePresentation:
    """Adapter-authored labels for the shared actionable-issue Viewer."""

    evidence: tuple[ResolutionIssueEvidence, ...]
    prompt_heading: str
    options_heading: str
    other_option_label: str
    response_heading: str

    def __post_init__(self) -> None:
        evidence = _items(
            self.evidence,
            ResolutionIssueEvidence,
            "resolution issue evidence",
        )
        if not evidence:
            raise ResolutionWorkbenchError(
                "An actionable issue requires source-linked evidence."
            )
        for value, label in (
            (self.prompt_heading, "resolution prompt heading"),
            (self.options_heading, "resolution options heading"),
            (self.other_option_label, "resolution other-option label"),
            (self.response_heading, "resolution response heading"),
        ):
            _text(value, label, one_line=True)


@dataclass(frozen=True)
class ResolutionItem:
    """One navigable issue, finding, conflict, or planned change."""

    uid: str
    kind: str
    status: str
    priority: str
    title: str
    summary: str
    role: ResolutionItemRole = "DECISION"
    obligation: ResolutionItemObligation | None = None
    response_state: ResolutionResponseState = "OPEN"
    response_text: str = ""
    question: str = ""
    options: tuple[ResolutionOption, ...] = ()
    blocks: tuple[ResolutionDetailBlock, ...] = ()
    selected_option_uid: str | None = None
    decision_block_index: int = 0
    evidence_refs: tuple[ResultRef, ...] = ()
    judgment_refs: tuple[ResultRef, ...] = ()
    outcome_refs: tuple[ResultRef, ...] = ()
    unresolved_refs: tuple[ResultRef, ...] = ()
    issue_presentation: ResolutionIssuePresentation | None = None
    kind_label: str | None = None
    compact_row_suffix: str | None = None
    commentable: bool = False
    show_summary_priority: bool = True

    def __post_init__(self) -> None:
        for value, label in (
            (self.uid, "resolution item uid"),
            (self.kind, "resolution item kind"),
            (self.status, "resolution item status"),
            (self.priority, "resolution item priority"),
            (self.title, "resolution item title"),
        ):
            _text(
                value,
                label,
                limit=(
                    RESOLUTION_KEY_LIMIT
                    if label.endswith("uid")
                    else RESOLUTION_TEXT_LIMIT
                    if label.endswith("title")
                    else RESOLUTION_LABEL_LIMIT
                ),
                one_line=True,
            )
        _text(self.summary, "resolution item summary")
        if self.compact_row_suffix is not None:
            _text(
                self.compact_row_suffix,
                "resolution item compact row suffix",
                limit=RESOLUTION_LABEL_LIMIT,
                one_line=True,
            )
        if self.role not in {"DECISION", "OPTIONAL_REVIEW", "CHANGE"}:
            raise ResolutionWorkbenchError("Invalid resolution item role.")
        if self.obligation not in {None, "REQUIRED", "OPTIONAL", "NONE"}:
            raise ResolutionWorkbenchError(
                "Invalid resolution item response obligation."
            )
        if self.response_state not in {"OPEN", "ANSWERED", "NOT_APPLICABLE"}:
            raise ResolutionWorkbenchError("Invalid resolution item response state.")
        _text(
            self.response_text,
            "resolution item response text",
            empty=True,
        )
        if (
            self.response_state == "NOT_APPLICABLE"
            and self.effective_obligation != "NONE"
        ):
            raise ResolutionWorkbenchError(
                "A non-applicable response requires no review obligation."
            )
        _text(self.question, "resolution item question", empty=True)
        options = _items(
            self.options,
            ResolutionOption,
            "resolution item options",
        )
        blocks = _items(
            self.blocks,
            ResolutionDetailBlock,
            "resolution item detail blocks",
        )
        if (
            isinstance(self.decision_block_index, bool)
            or not isinstance(self.decision_block_index, int)
            or not 0 <= self.decision_block_index <= len(blocks)
        ):
            raise ResolutionWorkbenchError("Invalid resolution decision block index.")

        trace_groups = (
            self.evidence_refs,
            self.judgment_refs,
            self.outcome_refs,
            self.unresolved_refs,
        )
        for refs in trace_groups:
            validated_refs = _items(
                refs,
                ResultRef,
                "resolution trace references",
            )
            if len(set(validated_refs)) != len(validated_refs):
                raise ResolutionWorkbenchError("Duplicate resolution trace reference.")
        if any(trace_groups) and not (self.evidence_refs and self.judgment_refs):
            raise ResolutionWorkbenchError(
                "A resolution trace requires evidence and judgment references."
            )
        if self.issue_presentation is not None and not isinstance(
            self.issue_presentation,
            ResolutionIssuePresentation,
        ):
            raise ResolutionWorkbenchError("Invalid resolution issue presentation.")
        if self.kind_label is not None:
            _text(
                self.kind_label,
                "resolution item kind label",
                limit=RESOLUTION_LABEL_LIMIT,
                one_line=True,
            )
        if not isinstance(self.commentable, bool):
            raise ResolutionWorkbenchError("Invalid resolution item commentability.")
        if not isinstance(self.show_summary_priority, bool):
            raise ResolutionWorkbenchError(
                "Invalid resolution item summary-priority visibility."
            )
        if len({option.uid for option in options}) != len(options):
            raise ResolutionWorkbenchError("Duplicate resolution option uid.")
        if self.selected_option_uid is not None and self.selected_option_uid not in {
            option.uid for option in options
        }:
            raise ResolutionWorkbenchError("Selected resolution option is unavailable.")
        if not blocks and not self.question and not options:
            # A compact planned change can still be expanded to its summary.
            object.__setattr__(
                self,
                "blocks",
                (
                    ResolutionDetailBlock(
                        heading="DETAIL",
                        text=self.summary,
                    ),
                ),
            )

    @property
    def effective_obligation(self) -> ResolutionItemObligation:
        """Return explicit review semantics, with a legacy construction fallback.

        Production adapters set ``obligation`` directly.  The fallback keeps
        older callers and small test fixtures compatible while the shared
        shell stops treating every non-REQUIRED row as an optional question.
        """

        if self.obligation is not None:
            return self.obligation
        if self.role == "CHANGE":
            return "NONE"
        return "REQUIRED" if self.priority == "REQUIRED" else "OPTIONAL"

    @property
    def display_kind(self) -> str:
        """Return an operation-owned label without exposing storage tokens."""

        return self.kind_label or self.kind.replace("_", " ")

    def option(self, option_uid: str) -> ResolutionOption:
        matches = [option for option in self.options if option.uid == option_uid]
        if len(matches) != 1:
            raise ResolutionWorkbenchError(
                f"No resolution option matches '{option_uid}'."
            )
        return matches[0]


@dataclass(frozen=True)
class ResolutionResult:
    """One exact proposed or already-applied operation outcome."""

    uid: str
    marker: str
    label: str
    text: str
    reason: str = ""
    rules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(
            self.uid,
            "resolution result uid",
            limit=RESOLUTION_KEY_LIMIT,
            one_line=True,
        )
        _text(
            self.marker,
            "resolution result marker",
            limit=20,
            one_line=True,
        )
        _text(
            self.label,
            "resolution result label",
            limit=RESOLUTION_LABEL_LIMIT,
            one_line=True,
        )
        _text(self.text, "resolution result text")
        _text(self.reason, "resolution result reason", empty=True)
        rules = _items(self.rules, str, "resolution result rules")
        for rule in rules:
            _text(rule, "resolution result rule")


@dataclass(frozen=True)
class ResolutionWorkbenchAction:
    """One UID-bound semantic action emitted by the common shell."""

    kind: ResolutionActionKind
    item_uid: str | None = None
    option_uid: str | None = None
    comment: str = ""
    destination: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _ACTION_KINDS:
            raise ResolutionWorkbenchError("Invalid resolution workbench action.")
        if self.item_uid is not None:
            _text(
                self.item_uid,
                "resolution action item uid",
                limit=RESOLUTION_KEY_LIMIT,
                one_line=True,
            )
        if self.option_uid is not None:
            _text(
                self.option_uid,
                "resolution action option uid",
                limit=RESOLUTION_KEY_LIMIT,
                one_line=True,
            )
        _text(
            self.comment,
            "resolution action comment",
            empty=True,
        )
        if self.destination is not None:
            _text(
                self.destination,
                "resolution action destination",
                limit=RESOLUTION_KEY_LIMIT,
                one_line=True,
            )
        if (self.kind == "CHANGE_DESTINATION") != (self.destination is not None):
            raise ResolutionWorkbenchError(
                "Only a destination-change action may carry a destination."
            )


@dataclass(frozen=True)
class ResolutionWorkbenchView:
    """Complete immutable view supplied by one operation adapter revision."""

    operation: str
    artifact_uid: str
    revision: str
    title: str
    route: str
    status: str
    metrics: tuple[ResolutionMetric, ...]
    overview: str
    list_label: str
    items: tuple[ResolutionItem, ...]
    empty_message: str
    results_label: str
    results: tuple[ResolutionResult, ...]
    capabilities: frozenset[ResolutionCapability] = frozenset()
    accept_enabled: bool = False
    accept_mode: ResolutionAcceptMode = "CHANGES"
    unresolved_at_apply_count: int = 0
    input_locked: bool = False
    report_items_summary: ResolutionDetailBlock | None = None
    context_locations: tuple[ResolutionContextLocation, ...] = ()
    overview_sections: tuple[ResolutionOverviewSection, ...] = ()
    show_results: bool = True

    def __post_init__(self) -> None:
        for value, label, limit in (
            (self.operation, "resolution operation", RESOLUTION_LABEL_LIMIT),
            (self.artifact_uid, "resolution artifact uid", RESOLUTION_KEY_LIMIT),
            (self.revision, "resolution revision", RESOLUTION_KEY_LIMIT),
            (self.title, "resolution title", RESOLUTION_LABEL_LIMIT),
            (self.route, "resolution route", RESOLUTION_TEXT_LIMIT),
            (self.status, "resolution status", RESOLUTION_LABEL_LIMIT),
            (self.list_label, "resolution list label", RESOLUTION_LABEL_LIMIT),
            (self.empty_message, "resolution empty message", RESOLUTION_TEXT_LIMIT),
            (self.results_label, "resolution results label", RESOLUTION_LABEL_LIMIT),
        ):
            _text(value, label, limit=limit, one_line=True)
        _text(self.overview, "resolution overview", empty=True)
        overview_sections = _items(
            self.overview_sections,
            ResolutionOverviewSection,
            "resolution overview sections",
        )
        if len({section.uid for section in overview_sections}) != len(
            overview_sections
        ):
            raise ResolutionWorkbenchError("Duplicate resolution overview-section uid.")
        _items(
            self.metrics,
            ResolutionMetric,
            "resolution metrics",
        )
        locations = _items(
            self.context_locations,
            ResolutionContextLocation,
            "resolution Context locations",
        )
        if len({location.role for location in locations}) != len(locations):
            raise ResolutionWorkbenchError(
                "Duplicate resolution Context-location role."
            )
        items = _items(self.items, ResolutionItem, "resolution items")
        results = _items(
            self.results,
            ResolutionResult,
            "resolution results",
        )
        if self.report_items_summary is not None and not isinstance(
            self.report_items_summary,
            ResolutionDetailBlock,
        ):
            raise ResolutionWorkbenchError("Invalid resolution report-items summary.")
        if len({item.uid for item in items}) != len(items):
            raise ResolutionWorkbenchError("Duplicate resolution item uid.")
        if len({result.uid for result in results}) != len(results):
            raise ResolutionWorkbenchError("Duplicate resolution result uid.")
        if (
            not isinstance(self.capabilities, frozenset)
            or not self.capabilities <= _CAPABILITIES
        ):
            raise ResolutionWorkbenchError("Invalid resolution capabilities.")
        if self.accept_enabled and "ACCEPT" not in self.capabilities:
            raise ResolutionWorkbenchError(
                "Enabled acceptance requires the ACCEPT capability."
            )
        # Readiness belongs to the adapter.  An empty list can be either ready
        # (for example a zero-change directional Meld) or merely unassessed.
        if not isinstance(self.accept_enabled, bool):
            raise ResolutionWorkbenchError("Invalid resolution acceptance state.")
        if self.accept_mode not in {"CHANGES", "AS_IS"}:
            raise ResolutionWorkbenchError("Invalid resolution acceptance mode.")
        if self.accept_mode == "AS_IS" and not self.accept_enabled:
            raise ResolutionWorkbenchError(
                "Apply-as-is mode requires enabled acceptance."
            )
        if (
            isinstance(self.unresolved_at_apply_count, bool)
            or not isinstance(self.unresolved_at_apply_count, int)
            or self.unresolved_at_apply_count < 0
        ):
            raise ResolutionWorkbenchError("Invalid unresolved-at-apply count.")
        if self.accept_mode != "AS_IS" and self.unresolved_at_apply_count:
            raise ResolutionWorkbenchError(
                "Only apply-as-is mode may report unresolved application state."
            )
        if not isinstance(self.input_locked, bool):
            raise ResolutionWorkbenchError("Invalid resolution input-lock state.")
        if not isinstance(self.show_results, bool):
            raise ResolutionWorkbenchError("Invalid resolution results visibility.")

    @property
    def semantic_overview_sections(self) -> tuple[ResolutionOverviewSection, ...]:
        """Return typed stops, with one neutral compatibility overview."""

        if self.overview_sections:
            return self.overview_sections
        if not self.overview:
            return ()
        return (
            ResolutionOverviewSection(
                uid="overview",
                heading="OVERVIEW",
                text=self.overview,
            ),
        )

    def item(self, item_uid: str) -> ResolutionItem:
        matches = [item for item in self.items if item.uid == item_uid]
        if len(matches) != 1:
            raise ResolutionWorkbenchError(f"No resolution item matches '{item_uid}'.")
        return matches[0]

    def validate_action(
        self,
        action: ResolutionWorkbenchAction,
    ) -> ResolutionWorkbenchAction:
        """Reject stale, unavailable, or capability-crossing shell output."""
        if action.kind == "CLOSE":
            if action.item_uid is not None or action.option_uid is not None:
                raise ResolutionWorkbenchError("Close cannot target a resolution item.")
            return action
        if self.input_locked:
            raise ResolutionWorkbenchError(
                "Resolution input is locked while analysis is pending."
            )
        if action.kind not in self.capabilities:
            raise ResolutionWorkbenchError(
                f"Resolution action '{action.kind}' is unavailable."
            )
        if action.kind == "SUBMIT_ITEM":
            if action.item_uid is None:
                raise ResolutionWorkbenchError("An item response requires an item uid.")
            item = self.item(action.item_uid)
            if action.option_uid is not None:
                item.option(action.option_uid)
            if action.option_uid is None and not action.comment.strip():
                raise ResolutionWorkbenchError(
                    "An item response requires an option or comment."
                )
            return action
        if action.item_uid is not None or action.option_uid is not None:
            raise ResolutionWorkbenchError(
                "A whole-workbench action cannot target one item."
            )
        if (
            action.kind in {"SUBMIT_ALL", "INCORPORATE_AND_APPLY"}
            and not action.comment.strip()
        ):
            raise ResolutionWorkbenchError("A whole-set response requires a comment.")
        if action.kind == "ACCEPT" and not self.accept_enabled:
            raise ResolutionWorkbenchError("This resolution is not ready to accept.")
        return action


@dataclass
class ResolutionNavigation:
    """Ephemeral UID-based navigation resilient to full list replacement."""

    selected_item_uid: str | None = None
    expanded_item_uid: str | None = None
    option_cursor_uid: str | None = None
    selected_option_uid: str | None = None
    _selected_index_hint: int = 0
    _revision: str | None = None
    _item_uids: tuple[str, ...] = field(default=(), repr=False)

    def sync(self, view: ResolutionWorkbenchView) -> None:
        """Reconcile navigation after an adapter replaces its complete view."""
        uids = tuple(item.uid for item in view.items)
        previous_revision = self._revision
        if self.selected_item_uid in uids:
            selected_index = uids.index(self.selected_item_uid)
        elif uids:
            selected_index = min(self._selected_index_hint, len(uids) - 1)
            self.selected_item_uid = uids[selected_index]
        else:
            selected_index = 0
            self.selected_item_uid = None
        self._selected_index_hint = selected_index
        self._item_uids = uids

        if self.expanded_item_uid != self.selected_item_uid:
            self.close_detail()
        elif self.expanded_item_uid is not None:
            item = view.item(self.expanded_item_uid)
            option_uids = {option.uid for option in item.options}
            if self.option_cursor_uid not in option_uids:
                self.option_cursor_uid = (
                    item.selected_option_uid
                    if item.selected_option_uid in option_uids
                    else (item.options[0].uid if item.options else None)
                )
            if (
                self.selected_option_uid is not None
                and self.selected_option_uid not in option_uids
            ):
                self.selected_option_uid = None

        if previous_revision is not None and previous_revision != view.revision:
            # Current Meld option identities are derived from visible order.
            # Keeping an option across a complete reassessment could therefore
            # reinterpret an old selection even when the issue UID survives.
            self.option_cursor_uid = None
            self.selected_option_uid = None
            self.expanded_item_uid = None
        self._revision = view.revision

    def current_item(
        self,
        view: ResolutionWorkbenchView,
    ) -> ResolutionItem | None:
        self.sync(view)
        if self.selected_item_uid is None:
            return None
        return view.item(self.selected_item_uid)

    def move_item(self, view: ResolutionWorkbenchView, delta: int) -> None:
        if isinstance(delta, bool) or not isinstance(delta, int):
            raise ResolutionWorkbenchError("Invalid resolution movement.")
        self.sync(view)
        if not view.items:
            return
        index = min(
            max(self._selected_index_hint + delta, 0),
            len(view.items) - 1,
        )
        self._selected_index_hint = index
        self.selected_item_uid = view.items[index].uid
        self.close_detail()

    def toggle_detail(self, view: ResolutionWorkbenchView) -> None:
        item = self.current_item(view)
        if item is None:
            return
        if self.expanded_item_uid == item.uid:
            self.close_detail()
            return
        self.expanded_item_uid = item.uid
        self.selected_option_uid = item.selected_option_uid
        self.option_cursor_uid = (
            item.selected_option_uid
            if item.selected_option_uid is not None
            else (item.options[0].uid if item.options else None)
        )

    def move_option(self, view: ResolutionWorkbenchView, delta: int) -> None:
        item = self.current_item(view)
        if item is None or self.expanded_item_uid != item.uid or not item.options:
            return
        option_uids = tuple(option.uid for option in item.options)
        index = (
            option_uids.index(self.option_cursor_uid)
            if self.option_cursor_uid in option_uids
            else 0
        )
        next_index = min(max(index + delta, 0), len(option_uids) - 1)
        self.option_cursor_uid = option_uids[next_index]

    def toggle_option(self, view: ResolutionWorkbenchView) -> None:
        item = self.current_item(view)
        if (
            item is None
            or self.expanded_item_uid != item.uid
            or self.option_cursor_uid is None
        ):
            return
        item.option(self.option_cursor_uid)
        self.selected_option_uid = (
            None
            if self.selected_option_uid == self.option_cursor_uid
            else self.option_cursor_uid
        )

    def close_detail(self) -> None:
        self.expanded_item_uid = None
        self.option_cursor_uid = None
        self.selected_option_uid = None


class ResolutionWorkbenchAdapter(Protocol):
    """Operation-owned projection boundary for common presentation."""

    def view(self) -> ResolutionWorkbenchView:
        """Return the latest complete immutable workbench revision."""
