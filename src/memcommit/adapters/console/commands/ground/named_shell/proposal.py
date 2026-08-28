"""Frozen command contracts and effect projection for a named Ground.

Every proposal remains bound to the exact Ground identity and revision supplied
by the application adapter.  Presentation may explain those effects, but the
runtime can apply only this frozen command contract after explicit approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


from memcommit.adapters.console.coordination.command_review.model import CommandReview
from memcommit.adapters.console.terminal.components.exact_command_review.rendering import (
    render_exact_command_blocks,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.application.operations.ground.model import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundItem,
    GroundSession,
)
from memcommit.application.operations.fit.ground_report import FitReport
from memcommit.application.operations.fit.store import GroundFitReceipt
from memcommit.application.operations.ground.turn_dialogue import (
    GroundTurnDraft,
)


class NamedGroundInterpreter(Protocol):
    def __call__(
        self,
        session: GroundSession,
        dialogue_text: str,
        draft_source_text: str,
    ) -> object:
        """Return an ASK object or one frozen command proposal."""


@dataclass(frozen=True)
class GroundCommandProposal:
    """One operation-specific action reduced to a frozen local argv."""

    kind: str
    understanding: str
    question: str
    review: CommandReview
    expected_ground_uid: str
    expected_revision: int
    expected_state_digest: str
    expected_context_versions: tuple[str, ...] = ()


class NamedGroundApplier(Protocol):
    def __call__(
        self,
        session: GroundSession,
        proposal: GroundCommandProposal,
    ) -> tuple[GroundSession, str]:
        """Apply exactly one approved command and reload the Ground."""


class NamedGroundReloader(Protocol):
    def __call__(self, contract_name: str) -> GroundSession:
        """Reload one required named Ground from durable storage."""


class NamedGroundFitRunner(Protocol):
    def __call__(self, session: GroundSession) -> FitReport:
        """Run Fit through the application service, never by shelling out."""


class NamedGroundFitLookup(Protocol):
    def __call__(self, session: GroundSession) -> GroundFitReceipt | None:
        """Return the latest immutable Fit receipt for this Ground identity."""


class NamedGroundDraftPreparer(Protocol):
    def __call__(
        self,
        session: GroundSession,
        draft: GroundTurnDraft,
    ) -> GroundCommandProposal:
        """Reduce one selected READY Rule draft to a frozen command."""


class NamedGroundProposalRetargeter(Protocol):
    def __call__(
        self,
        session: GroundSession,
        proposal: GroundCommandProposal,
        target_name: str,
    ) -> GroundCommandProposal:
        """Replace one proposal's placement with an exact local selection."""


class NamedGroundDirectEditPreparer(Protocol):
    def __call__(
        self,
        session: GroundSession,
        target: Literal["GOAL", "RULE", "MEMORY"],
        selector: str,
        edited: str,
        comment: str,
    ) -> GroundCommandProposal:
        """Freeze one exact pane-local replacement as one reviewed command."""


class NamedGroundUseTogglePreparer(Protocol):
    def __call__(
        self,
        session: GroundSession,
        selector: str,
    ) -> GroundCommandProposal:
        """Freeze one selected Example's next USE value as a reviewed command."""


@dataclass(frozen=True)
class NamedGroundShellResult:
    status: Literal["CLOSED", "BACK_TO_PICKER"]
    session: GroundSession
    applied_argvs: tuple[tuple[str, ...], ...] = ()
    submitted_turns: tuple[str, ...] = ()


def _line(value: str, limit: int = 110) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def _aliased_items(
    session: GroundSession,
    kind: str,
) -> tuple[tuple[str, GroundItem], ...]:
    prefix = "r" if kind == "RULE" else "c"
    return tuple(
        (f"{prefix}{number}", item)
        for number, item in enumerate(
            (item for item in session.items if item.kind == kind),
            start=1,
        )
    )


def _display_ground_compatibility_token(value: str) -> str:
    """Translate persisted Case-era tokens only at the presentation boundary."""
    if value in {"DISTILLED_FROM_GOAL", "INDUCED_FROM_CASES"}:
        return "DISTILLED"
    return value


def _option_values(argv: tuple[str, ...], option: str) -> tuple[str, ...]:
    return tuple(
        argv[index + 1] for index, value in enumerate(argv[:-1]) if value == option
    )


def _option_value(argv: tuple[str, ...], option: str) -> str:
    values = _option_values(argv, option)
    return values[0] if values else ""


def _item_aliases_by_uid(session: GroundSession) -> dict[str, str]:
    return {
        item.uid: alias
        for kind in ("RULE", "CASE")
        for alias, item in _aliased_items(session, kind)
    }


def _review_item_effects(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, ...]:
    argv = proposal.review.argv
    selector = _option_value(argv, "--decide")
    action = _option_value(argv, "--action").upper()
    target = next(
        (item for item in session.items if item.uid == selector),
        None,
    )
    if target is None or target.kind not in {"RULE", "CASE"}:
        return ()
    alias = _item_aliases_by_uid(session).get(target.uid, target.uid[:8])
    item_name = "Ground Memory" if target.kind == "CASE" else target.kind.title()
    statement = (
        target.proposition
        if (
            target.kind == "CASE"
            and session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
        )
        else target.content
    )
    details = [
        (f"Selected item: {alias} · {item_name} · {target.status} · {_line(statement)}")
    ]
    if action == "REFINE":
        replacement = _option_value(argv, "--response")
        if target.kind == "RULE":
            details.extend(
                [
                    (
                        f"REFINE: replace {alias} Rule content with "
                        f"'{_line(replacement)}'"
                    ),
                    (f"{alias} remains PROPOSED; provenance becomes JOINTLY_REVISED"),
                ]
            )
        else:
            field_name = (
                "proposition"
                if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                else "expected output"
            )
            details.extend(
                [
                    (
                        f"REFINE: replace {alias} {field_name} with "
                        f"'{_line(replacement)}'"
                    ),
                    (
                        f"{alias} remains PROPOSED; its source, linked Rule, "
                        "role, disposition, and targets remain unchanged"
                    ),
                ]
            )
    elif action in {"ACCEPT", "DEFER", "REJECT"}:
        status = {
            "ACCEPT": "ACCEPTED",
            "DEFER": "DEFERRED",
            "REJECT": "REJECTED",
        }[action]
        unchanged_field = (
            "proposition"
            if (
                target.kind == "CASE"
                and session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
            )
            else "content"
        )
        details.append(
            f"{action}: mark {alias} {status}; its {unchanged_field} remains unchanged"
        )
    details.append("One review Decision record: ADD")
    return tuple(details)


def _proposal_item_effects(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, ...]:
    argv = proposal.review.argv
    if proposal.kind == "BIND":
        placements = _option_values(argv, "--placement-target")
        details = [
            f"Task binding: '{_line(_option_value(argv, '--description'))}'",
            (
                "Frames: raw="
                f"{_option_value(argv, '--raw-context')} · derived="
                f"{_option_value(argv, '--derived-context')}"
            ),
            (f"Publication target: {_option_value(argv, '--publication-target')}"),
        ]
        if placements:
            details.append("Placement targets: " + ", ".join(placements))
        return tuple(details)
    if proposal.kind == "REVISE_GOAL":
        return (
            (f"Replacement Goal: '{_line(_option_value(argv, '--revise-goal'))}'"),
            (f"Reason: {_line(_option_value(argv, '--change-reason'))}"),
        )
    if proposal.kind == "PROPOSE_RULE":
        alias = f"r{len(_aliased_items(session, 'RULE')) + 1}"
        return (
            (
                f"New {alias} · PROPOSED Rule: "
                f"{_line(_option_value(argv, '--propose-rule'))}"
            ),
            (
                "Provenance: "
                f"{_display_ground_compatibility_token(_option_value(argv, '--rule-provenance'))}"
            ),
            f"Rationale: {_line(_option_value(argv, '--rationale'))}",
        )
    if proposal.kind == "PROPOSE_CASE":
        aliases = _item_aliases_by_uid(session)
        native = bool(_option_value(argv, "--propose-example"))
        rule_uid = _option_value(
            argv,
            "--example-rule" if native else "--fit-rule",
        )
        rule = next(
            (item for item in session.items if item.uid == rule_uid),
            None,
        )
        rule_alias = aliases.get(rule_uid, rule_uid[:8])
        alias = f"c{len(_aliased_items(session, 'CASE')) + 1}"
        details = [
            (
                f"New {alias} · PROPOSED "
                f"{_option_value(argv, '--case-role')}/"
                f"{_option_value(argv, '--disposition')} Ground Memory"
            ),
            (
                f"Linked Rule: {rule_alias}"
                + (f" · {_line(rule.content)}" if rule is not None else "")
            ),
            (
                "Targets: "
                + ", ".join(
                    _option_values(
                        argv,
                        "--example-target" if native else "--propose-target",
                    )
                )
            ),
            (
                "Expected output: "
                + (
                    _line(_option_value(argv, "--expected"))
                    or "(none for this disposition)"
                )
            ),
            ("Source: exact Context Memory selected from the bound candidate Context"),
        ]
        if native:
            details.insert(
                1,
                "Proposition: " + _line(_option_value(argv, "--propose-example")),
            )
            exact_input = _option_value(argv, "--example-input")
            exact_expected = _option_value(argv, "--example-expected")
            details[4] = "Exact projection: " + (
                f"{_line(exact_input)} → {_line(exact_expected)}"
                if exact_input and exact_expected
                else "(none)"
            )
        return tuple(details)
    if proposal.kind == "SET_EXAMPLE_USE":
        selector = _option_value(argv, "--set-example-use")
        use = _option_value(argv, "--use")
        aliases = _item_aliases_by_uid(session)
        item = next(
            (candidate for candidate in session.items if candidate.uid == selector),
            None,
        )
        alias = aliases.get(selector, selector[:8])
        before = item.disposition if item is not None else "UNKNOWN"
        return (
            f"Selected Memory: {alias}",
            f"USE: {before} -> {use}",
            "Future Fit and Ground Distill runs use this participation set.",
        )
    if proposal.kind == "REVIEW_ITEM":
        return _review_item_effects(session, proposal)
    return ()


def render_named_ground_proposal_blocks(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, str]:
    """Render one Ground proposal with operation-aware approval context."""
    details = _proposal_item_effects(session, proposal)
    base_effects = proposal.review.effects
    if proposal.kind == "REVIEW_ITEM":
        base_effects = tuple(
            effect
            for effect in base_effects
            if not effect.startswith("Selected Rule/Ground Memory:")
            and not effect.startswith("One review Decision:")
        )
    informed_review = CommandReview(
        argv=proposal.review.argv,
        effects=(*details, *base_effects),
    )
    return render_exact_command_blocks(informed_review)


def _response_kind(response: object) -> str:
    raw = getattr(response, "kind", None)
    if not isinstance(raw, str):
        raise ValueError("Ground turn has no ASK or action kind.")
    return raw


def _response_text(response: object, field_name: str) -> str:
    value = getattr(response, field_name, None)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Ground turn has no {field_name}.")
    return value.strip()
