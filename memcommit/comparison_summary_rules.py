"""Versioned compact-relation rules for default ``mem compare``."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from importlib import resources
import json


COMPARISON_SUMMARY_RULESET_VERSION = "compact-peer-relation-v3"
COMPARISON_SUMMARY_RULESET_FIXTURE = "comparison_summary.json"
COMPARISON_SUMMARY_WORD_LIMIT = 80


class ComparisonSummaryRulesError(ValueError):
    """The checked-in compact Compare ruleset is invalid."""


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ComparisonSummaryRulesError(
                f"Duplicate compact Compare ruleset key: {key}."
            )
        result[key] = value
    return result


def _object(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ComparisonSummaryRulesError(
            f"Invalid compact Compare ruleset {label}."
        )
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ComparisonSummaryRulesError(
            f"Compact Compare ruleset {label} is invalid text."
        )
    return value


def _texts(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ComparisonSummaryRulesError(
            f"Compact Compare ruleset {label} must be an array."
        )
    result = [_text(item, label) for item in value]
    if len(result) != len(set(result)):
        raise ComparisonSummaryRulesError(
            f"Compact Compare ruleset {label} must not repeat."
        )
    return result


def measure_comparison_summary_words(value: str) -> int:
    """Measure the exact whitespace-delimited bound used by the decoder."""

    return len(value.split())


def _validate_case(raw: object, *, rule_ids: set[str]) -> str:
    case = _object(
        raw,
        {"id", "description", "frames", "expected", "known_wrong"},
        "case",
    )
    case_id = _text(case["id"], "case id")
    _text(case["description"], f"case {case_id} description")

    frames = case["frames"]
    if not isinstance(frames, list) or len(frames) != 2:
        raise ComparisonSummaryRulesError(
            f"Compact Compare case {case_id} requires two frames."
        )
    known_aliases: set[str] = set()
    primary_by_side: list[set[str]] = []
    for frame_index, raw_frame in enumerate(frames):
        frame = _object(raw_frame, {"side", "memories"}, f"case {case_id} frame")
        expected_side = "REFERENCE" if frame_index == 0 else "COMPARED"
        if frame["side"] != expected_side or not isinstance(frame["memories"], list):
            raise ComparisonSummaryRulesError(
                f"Compact Compare case {case_id} has an invalid frame."
            )
        primary: set[str] = set()
        for raw_memory in frame["memories"]:
            memory = _object(
                raw_memory,
                {"id", "role", "content"},
                f"case {case_id} Memory",
            )
            alias = _text(memory["id"], f"case {case_id} Memory id")
            _text(memory["content"], f"case {case_id} Memory content")
            if memory["role"] not in {"PRIMARY", "CONTEXT"} or alias in known_aliases:
                raise ComparisonSummaryRulesError(
                    f"Compact Compare case {case_id} has an invalid Memory."
                )
            known_aliases.add(alias)
            if memory["role"] == "PRIMARY":
                primary.add(alias)
        if not primary:
            raise ComparisonSummaryRulesError(
                f"Compact Compare case {case_id} requires PRIMARY evidence."
            )
        primary_by_side.append(primary)

    expected = _object(
        case["expected"],
        {"text", "source_ids", "rule_ids"},
        f"case {case_id} expected result",
    )
    narrative = _text(expected["text"], f"case {case_id} expected text")
    if "\n" in narrative or "\r" in narrative:
        raise ComparisonSummaryRulesError(
            f"Compact Compare case {case_id} must use one paragraph."
        )
    if measure_comparison_summary_words(narrative) > COMPARISON_SUMMARY_WORD_LIMIT:
        raise ComparisonSummaryRulesError(
            f"Compact Compare case {case_id} exceeds its word bound."
        )
    source_ids = _texts(expected["source_ids"], f"case {case_id} source ids")
    if (
        not source_ids
        or set(source_ids) - known_aliases
        or not all(set(source_ids) & primary for primary in primary_by_side)
    ):
        raise ComparisonSummaryRulesError(
            f"Compact Compare case {case_id} has invalid source evidence."
        )
    linked = _texts(expected["rule_ids"], f"case {case_id} rule ids")
    if not linked or set(linked) - rule_ids:
        raise ComparisonSummaryRulesError(
            f"Compact Compare case {case_id} cites unknown rules."
        )

    wrong = case["known_wrong"]
    if not isinstance(wrong, list) or not wrong:
        raise ComparisonSummaryRulesError(
            f"Compact Compare case {case_id} requires known-wrong narratives."
        )
    for raw_wrong in wrong:
        item = _object(
            raw_wrong,
            {"text", "violates", "reason"},
            f"case {case_id} known-wrong narrative",
        )
        _text(item["text"], f"case {case_id} known-wrong text")
        violations = _texts(item["violates"], f"case {case_id} violations")
        if not violations or set(violations) - rule_ids:
            raise ComparisonSummaryRulesError(
                f"Compact Compare case {case_id} known-wrong cites unknown rules."
            )
        _text(item["reason"], f"case {case_id} known-wrong reason")
    return case_id


@lru_cache(maxsize=1)
def _loaded_ruleset() -> dict[str, object]:
    try:
        resource = resources.files("memcommit.eval").joinpath(
            "fixtures", COMPARISON_SUMMARY_RULESET_FIXTURE
        )
        raw = json.loads(
            resource.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ComparisonSummaryRulesError(
            "Could not load the compact Compare ruleset."
        ) from error
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
        data["command"] != "compare"
        or data["schema_version"] != 1
        or data["ruleset_version"] != COMPARISON_SUMMARY_RULESET_VERSION
    ):
        raise ComparisonSummaryRulesError(
            "Unsupported compact Compare ruleset version."
        )
    _text(data["description"], "description")
    rules = data["rules"]
    if not isinstance(rules, list) or not rules:
        raise ComparisonSummaryRulesError(
            "Compact Compare ruleset requires named rules."
        )
    rule_ids: set[str] = set()
    for raw_rule in rules:
        rule = _object(raw_rule, {"id", "title", "invariant"}, "rule")
        rule_id = _text(rule["id"], "rule id")
        _text(rule["title"], f"rule {rule_id} title")
        _text(rule["invariant"], f"rule {rule_id} invariant")
        if rule_id in rule_ids:
            raise ComparisonSummaryRulesError(
                f"Compact Compare ruleset repeats {rule_id}."
            )
        rule_ids.add(rule_id)
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise ComparisonSummaryRulesError(
            "Compact Compare ruleset requires canonical cases."
        )
    case_ids = [_validate_case(case, rule_ids=rule_ids) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ComparisonSummaryRulesError(
            "Compact Compare ruleset repeats a case id."
        )
    return data


def comparison_summary_ruleset() -> dict[str, object]:
    """Return an isolated copy of every compact Compare rule and case."""

    return deepcopy(_loaded_ruleset())


def comparison_summary_ruleset_prompt_payload(
    *,
    include_cases: bool = True,
) -> dict[str, object]:
    """Project rules and optionally authored cases into one provider turn."""

    data = comparison_summary_ruleset()
    return {
        "ruleset_version": data["ruleset_version"],
        "rules": data["rules"],
        "cases": data["cases"] if include_cases else [],
    }


__all__ = [
    "COMPARISON_SUMMARY_RULESET_VERSION",
    "COMPARISON_SUMMARY_WORD_LIMIT",
    "ComparisonSummaryRulesError",
    "comparison_summary_ruleset",
    "comparison_summary_ruleset_prompt_payload",
    "measure_comparison_summary_words",
]
