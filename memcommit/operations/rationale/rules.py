"""Versioned natural-language provenance rules for ``mem rationale``."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from functools import lru_cache
from importlib import resources
import json
from typing import get_args
import unicodedata

from memcommit.provenance import EventKind


RATIONALE_RULESET_VERSION = "rationale-natural-provenance-v5"
RATIONALE_RULESET_FIXTURE = "rationale.json"
DEFAULT_RATIONALE_PROVENANCE_LIMIT = 40
MAX_RATIONALE_PROVENANCE_LIMIT = 100_000


class RationaleRulesError(ValueError):
    """The checked-in Rationale rules or one narrative bound is invalid."""


class RationaleLimitUnit(str, Enum):
    """Supported bounds for the complete natural-language receipt."""

    CHARACTERS = "characters"
    BYTES = "bytes"
    WORDS = "words"


class RationaleNarrativeStatus(str, Enum):
    """Whether a grounded natural-language provenance may be shown."""

    AVAILABLE = "AVAILABLE"
    EMPTY = "EMPTY"
    HIDDEN = "HIDDEN"


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RationaleRulesError(f"Duplicate Rationale ruleset key: {key}.")
        result[key] = value
    return result


def _object(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RationaleRulesError(f"Invalid Rationale ruleset {label}.")
    return value


def _text(value: object, label: str, *, blank: bool = False) -> str:
    if not isinstance(value, str) or (not blank and not value.strip()):
        raise RationaleRulesError(f"Rationale ruleset {label} is invalid text.")
    return value


def _texts(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise RationaleRulesError(f"Rationale ruleset {label} must be an array.")
    result = [_text(item, label) for item in value]
    if len(result) != len(set(result)):
        raise RationaleRulesError(f"Rationale ruleset {label} must not repeat.")
    return result


def measure_rationale_text(value: str, unit: RationaleLimitUnit) -> int:
    """Measure one NFC narrative in the exact public CLI unit."""

    if unit is RationaleLimitUnit.CHARACTERS:
        return len(value)
    if unit is RationaleLimitUnit.BYTES:
        return len(value.encode("utf-8"))
    return len(value.split())


def validate_rationale_limit(
    limit: int,
    unit: RationaleLimitUnit | str | None = None,
) -> RationaleLimitUnit:
    """Validate a positive receipt bound before store or provider access."""

    if type(limit) is not int or not 1 <= limit <= MAX_RATIONALE_PROVENANCE_LIMIT:
        raise RationaleRulesError(
            "Rationale --limit must be between 1 and "
            f"{MAX_RATIONALE_PROVENANCE_LIMIT}."
        )
    try:
        return (
            unit
            if isinstance(unit, RationaleLimitUnit)
            else RationaleLimitUnit(unit or RationaleLimitUnit.WORDS.value)
        )
    except ValueError as error:
        raise RationaleRulesError(
            "Rationale has an unsupported length unit."
        ) from error


def _validate_state(raw: object, *, label: str) -> str:
    state = _object(raw, {"id", "content", "position"}, label)
    state_id = _text(state["id"], f"{label} id")
    _text(state["content"], f"{label} content")
    if type(state["position"]) is not int or state["position"] < 0:
        raise RationaleRulesError(f"Rationale {label} position is invalid.")
    return state_id


def _validate_states(raw: object, *, label: str) -> set[str]:
    if not isinstance(raw, list):
        raise RationaleRulesError(f"Rationale {label} must be an array.")
    ids = {_validate_state(item, label=label) for item in raw}
    if len(ids) != len(raw):
        raise RationaleRulesError(f"Rationale {label} repeats a Memory id.")
    return ids


def _validate_case(raw: object, *, rule_ids: set[str]) -> str:
    case = _object(
        raw,
        {"id", "description", "input", "expected", "known_wrong"},
        "case",
    )
    case_id = _text(case["id"], "case id")
    _text(case["description"], f"case {case_id} description")
    input_value = _object(
        case["input"],
        {
            "selected_memory_id",
            "context_name",
            "history_available",
            "originals",
            "current",
            "events",
            "warnings",
            "limit",
            "unit",
        },
        f"case {case_id} input",
    )
    selected = _text(input_value["selected_memory_id"], "selected Memory id")
    _text(input_value["context_name"], f"case {case_id} Context name")
    if type(input_value["history_available"]) is not bool:
        raise RationaleRulesError(f"Rationale case {case_id} history is invalid.")
    known_ids = _validate_states(input_value["originals"], label="original state")
    known_ids |= _validate_states(input_value["current"], label="current state")
    events = input_value["events"]
    if not isinstance(events, list):
        raise RationaleRulesError(f"Rationale case {case_id} events are invalid.")
    event_kinds = set(get_args(EventKind))
    for raw_event in events:
        event_fields = {
            "kind",
            "command",
            "description",
            "reason",
            "before",
            "after",
        }
        optional_event_fields = {"context_transition", "reason_codes"}
        if (
            not isinstance(raw_event, dict)
            or not event_fields <= set(raw_event)
            or set(raw_event) - event_fields - optional_event_fields
        ):
            raise RationaleRulesError(
                f"Invalid Rationale ruleset case {case_id} event."
            )
        event = raw_event
        if event["kind"] not in event_kinds:
            raise RationaleRulesError(f"Rationale case {case_id} event is unknown.")
        _text(event["command"], f"case {case_id} event command")
        _text(event["description"], f"case {case_id} event description")
        if event["reason"] is not None:
            _text(event["reason"], f"case {case_id} event reason")
        context_transition = event.get("context_transition")
        if context_transition is not None:
            route = _object(
                context_transition,
                {"source", "target"},
                f"case {case_id} event Context transition",
            )
            source = _text(route["source"], f"case {case_id} Source Context")
            target = _text(route["target"], f"case {case_id} target Context")
            if source == target:
                raise RationaleRulesError(
                    f"Rationale case {case_id} Context transition is stationary."
                )
        reason_codes = event.get("reason_codes")
        if reason_codes is not None:
            _texts(reason_codes, f"case {case_id} event reason codes")
        known_ids |= _validate_states(event["before"], label="event before state")
        known_ids |= _validate_states(event["after"], label="event after state")
    _texts(input_value["warnings"], f"case {case_id} warnings")
    if selected not in known_ids:
        raise RationaleRulesError(
            f"Rationale case {case_id} never contains its selected Memory."
        )
    unit = validate_rationale_limit(input_value["limit"], input_value["unit"])

    expected = _object(
        case["expected"],
        {"status", "provenance", "rule_ids"},
        f"case {case_id} expected result",
    )
    try:
        status = RationaleNarrativeStatus(expected["status"])
    except ValueError as error:
        raise RationaleRulesError(
            f"Rationale case {case_id} status is invalid."
        ) from error
    provenance = _text(
        expected["provenance"],
        f"case {case_id} provenance",
        blank=status is not RationaleNarrativeStatus.AVAILABLE,
    )
    if status is RationaleNarrativeStatus.AVAILABLE:
        normalized = unicodedata.normalize("NFC", provenance.strip())
        if provenance != normalized or "\n" in provenance or "\r" in provenance:
            raise RationaleRulesError(
                f"Rationale case {case_id} provenance must be one NFC paragraph."
            )
        if measure_rationale_text(provenance, unit) > input_value["limit"]:
            raise RationaleRulesError(
                f"Rationale case {case_id} exceeds its narrative bound."
            )
    elif provenance:
        raise RationaleRulesError(
            f"Rationale case {case_id} unavailable provenance must be blank."
        )
    linked = _texts(expected["rule_ids"], f"case {case_id} rule ids")
    if not linked or set(linked) - rule_ids:
        raise RationaleRulesError(f"Rationale case {case_id} cites unknown rules.")

    wrong = case["known_wrong"]
    if not isinstance(wrong, list) or not wrong:
        raise RationaleRulesError(
            f"Rationale case {case_id} requires known-wrong narratives."
        )
    for raw_wrong in wrong:
        item = _object(
            raw_wrong,
            {"provenance", "violates", "reason"},
            f"case {case_id} known-wrong narrative",
        )
        _text(item["provenance"], f"case {case_id} known-wrong provenance")
        violations = _texts(item["violates"], f"case {case_id} violations")
        if not violations or set(violations) - rule_ids:
            raise RationaleRulesError(
                f"Rationale case {case_id} known-wrong cites unknown rules."
            )
        _text(item["reason"], f"case {case_id} known-wrong reason")
    return case_id


@lru_cache(maxsize=1)
def _loaded_ruleset() -> dict[str, object]:
    try:
        resource = resources.files("memcommit.eval").joinpath(
            "fixtures", RATIONALE_RULESET_FIXTURE
        )
        raw = json.loads(
            resource.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RationaleRulesError("Could not load the Rationale ruleset.") from error
    data = _object(
        raw,
        {
            "command",
            "schema_version",
            "ruleset_version",
            "description",
            "rules",
            "cases",
        },
        "document",
    )
    if (
        data["command"] != "rationale"
        or data["schema_version"] != 2
        or data["ruleset_version"] != RATIONALE_RULESET_VERSION
    ):
        raise RationaleRulesError("Unsupported Rationale ruleset version.")
    _text(data["description"], "description")
    rules = data["rules"]
    if not isinstance(rules, list) or not rules:
        raise RationaleRulesError("Rationale ruleset requires named rules.")
    rule_ids: set[str] = set()
    for raw_rule in rules:
        rule = _object(raw_rule, {"id", "title", "invariant"}, "rule")
        rule_id = _text(rule["id"], "rule id")
        _text(rule["title"], f"rule {rule_id} title")
        _text(rule["invariant"], f"rule {rule_id} invariant")
        if rule_id in rule_ids:
            raise RationaleRulesError(f"Rationale ruleset repeats {rule_id}.")
        rule_ids.add(rule_id)
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise RationaleRulesError("Rationale ruleset requires canonical cases.")
    case_ids = [_validate_case(case, rule_ids=rule_ids) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise RationaleRulesError("Rationale ruleset repeats a case id.")
    return data


def rationale_ruleset() -> dict[str, object]:
    """Return an isolated copy of every authored rule and exact case."""

    return deepcopy(_loaded_ruleset())


def rationale_ruleset_prompt_payload(
    *,
    include_cases: bool = True,
) -> dict[str, object]:
    """Project rules and optionally authored cases into one provider turn."""

    data = rationale_ruleset()
    return {
        "ruleset_version": data["ruleset_version"],
        "rules": data["rules"],
        # These remain consumed calibration for ordinary Profiles. Study uses
        # the same rules without replaying the examples on every invocation.
        "cases": data["cases"] if include_cases else [],
    }


def rationale_rule_ids() -> tuple[str, ...]:
    """Return rule IDs in their normative prompt order."""

    rules = _loaded_ruleset()["rules"]
    assert isinstance(rules, list)
    return tuple(str(rule["id"]) for rule in rules if isinstance(rule, dict))


__all__ = [
    "DEFAULT_RATIONALE_PROVENANCE_LIMIT",
    "MAX_RATIONALE_PROVENANCE_LIMIT",
    "RATIONALE_RULESET_VERSION",
    "RationaleLimitUnit",
    "RationaleNarrativeStatus",
    "RationaleRulesError",
    "measure_rationale_text",
    "rationale_rule_ids",
    "rationale_ruleset",
    "rationale_ruleset_prompt_payload",
    "validate_rationale_limit",
]
