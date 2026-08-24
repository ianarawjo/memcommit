"""Versioned exact Resolve rules and canonical production examples."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from importlib import resources
import json


RESOLVE_RULESET_VERSION = "resolve-exact-cases-v1"
RESOLVE_RULESET_FIXTURE = "resolve.json"


class ResolveRulesError(ValueError):
    """The checked-in Resolve ruleset is absent or internally inconsistent."""


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ResolveRulesError(f"Duplicate Resolve ruleset key: {key}.")
        result[key] = value
    return result


def _object(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ResolveRulesError(f"Invalid Resolve ruleset {label}.")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResolveRulesError(f"Resolve ruleset {label} must be nonblank text.")
    return value


def _text_list(value: object, label: str, *, unique: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ResolveRulesError(f"Resolve ruleset {label} must be an array.")
    result = [_text(item, label) for item in value]
    if unique and len(result) != len(set(result)):
        raise ResolveRulesError(f"Resolve ruleset {label} must not repeat.")
    return result


def _validate_case(raw: object, *, rule_ids: set[str]) -> None:
    case = _object(
        raw,
        {
            "id",
            "description",
            "target",
            "source",
            "expected",
            "known_wrong",
        },
        "case",
    )
    case_id = _text(case["id"], "case id")
    _text(case["description"], f"case {case_id} description")
    if case["target"] not in {"MAY", "YES"}:
        raise ResolveRulesError(f"Resolve case {case_id} has an invalid target.")
    source = case["source"]
    if not isinstance(source, list) or len(source) < 2:
        raise ResolveRulesError(
            f"Resolve case {case_id} requires at least two Source Memories."
        )
    source_by_id: dict[str, dict[str, object]] = {}
    for raw_memory in source:
        memory = _object(raw_memory, {"id", "content", "mutable"}, "source Memory")
        memory_id = _text(memory["id"], f"case {case_id} Memory id")
        _text(memory["content"], f"case {case_id} Memory content")
        if type(memory["mutable"]) is not bool:
            raise ResolveRulesError(
                f"Resolve case {case_id} Memory mutable must be boolean."
            )
        if memory_id in source_by_id:
            raise ResolveRulesError(f"Resolve case {case_id} repeats {memory_id}.")
        source_by_id[memory_id] = memory

    expected = _object(
        case["expected"],
        {
            "classification",
            "outcome",
            "resolution_level",
            "post_fit",
            "effects",
            "result",
            "rule_ids",
            "reason",
        },
        f"case {case_id} expected result",
    )
    if expected["classification"] not in {
        "SAFE_ALTERNATIVE",
        "EXACT_GROUNDING",
        "CHOICE_REQUIRED",
        "ALREADY_ACCEPTABLE",
    }:
        raise ResolveRulesError(
            f"Resolve case {case_id} has an invalid classification."
        )
    if expected["outcome"] not in {"RESOLVE", "STOP", "UNCHANGED"}:
        raise ResolveRulesError(f"Resolve case {case_id} has an invalid outcome.")
    expected_outcome = {
        "SAFE_ALTERNATIVE": "RESOLVE",
        "EXACT_GROUNDING": "RESOLVE",
        "CHOICE_REQUIRED": "STOP",
        "ALREADY_ACCEPTABLE": "UNCHANGED",
    }[str(expected["classification"])]
    if expected["outcome"] != expected_outcome:
        raise ResolveRulesError(
            f"Resolve case {case_id} classification and outcome disagree."
        )
    if expected["resolution_level"] not in {"YES", "MAY", "NO"}:
        raise ResolveRulesError(
            f"Resolve case {case_id} has an invalid resolution level."
        )
    if expected["post_fit"] not in {"YES", "MAY_OR_YES", "NO"}:
        raise ResolveRulesError(f"Resolve case {case_id} has an invalid post-Fit.")
    if (
        expected["outcome"] == "RESOLVE"
        and expected["resolution_level"] not in {"MAY", "YES"}
    ) or (expected["outcome"] == "STOP" and expected["resolution_level"] != "NO"):
        raise ResolveRulesError(
            f"Resolve case {case_id} outcome and resolution level disagree."
        )
    if (
        expected["outcome"] == "RESOLVE"
        and expected["post_fit"] not in {"MAY_OR_YES", "YES"}
    ) or (expected["outcome"] == "STOP" and expected["post_fit"] != "NO"):
        raise ResolveRulesError(
            f"Resolve case {case_id} outcome and post-Fit expectation disagree."
        )
    if (
        case["target"] == "YES"
        and expected["outcome"] == "RESOLVE"
        and (expected["resolution_level"] != "YES" or expected["post_fit"] != "YES")
    ):
        raise ResolveRulesError(
            f"Resolve case {case_id} does not reach its strict YES target."
        )
    linked_rules = _text_list(expected["rule_ids"], f"case {case_id} rule ids")
    if not linked_rules or set(linked_rules) - rule_ids:
        raise ResolveRulesError(f"Resolve case {case_id} cites unknown rules.")
    _text(expected["reason"], f"case {case_id} reason")

    effects = expected["effects"]
    if not isinstance(effects, list):
        raise ResolveRulesError(f"Resolve case {case_id} effects must be an array.")
    result_by_id = {
        memory_id: str(memory["content"]) for memory_id, memory in source_by_id.items()
    }
    seen_targets: set[str] = set()
    for raw_effect in effects:
        effect = _object(
            raw_effect,
            {"kind", "target_id", "before", "after", "source_ids"},
            f"case {case_id} effect",
        )
        if effect["kind"] != "UPDATE":
            raise ResolveRulesError(
                "Resolve exact-case v1 supports only UPDATE calibration effects."
            )
        target_id = _text(effect["target_id"], f"case {case_id} effect target")
        if target_id in seen_targets or target_id not in source_by_id:
            raise ResolveRulesError(f"Resolve case {case_id} has an invalid target.")
        seen_targets.add(target_id)
        if source_by_id[target_id]["mutable"] is not True:
            raise ResolveRulesError(
                f"Resolve case {case_id} updates immutable {target_id}."
            )
        before = _text(effect["before"], f"case {case_id} effect before")
        after = _text(effect["after"], f"case {case_id} effect after")
        if before != source_by_id[target_id]["content"] or before == after:
            raise ResolveRulesError(
                f"Resolve case {case_id} effect does not bind an exact transition."
            )
        source_ids = _text_list(
            effect["source_ids"], f"case {case_id} effect source ids"
        )
        if not source_ids or set(source_ids) - set(source_by_id):
            raise ResolveRulesError(
                f"Resolve case {case_id} effect cites an unknown source."
            )
        result_by_id[target_id] = after

    expected_result = _text_list(
        expected["result"], f"case {case_id} result", unique=False
    )
    derived_result = [result_by_id[memory_id] for memory_id in source_by_id]
    if expected_result != derived_result:
        raise ResolveRulesError(
            f"Resolve case {case_id} result does not match its exact effects."
        )
    if expected["outcome"] == "RESOLVE" and not effects:
        raise ResolveRulesError(f"Resolve case {case_id} must contain an effect.")
    if expected["outcome"] != "RESOLVE" and effects:
        raise ResolveRulesError(
            f"Resolve case {case_id} non-resolution cannot contain effects."
        )

    wrong = case["known_wrong"]
    if not isinstance(wrong, list) or not wrong:
        raise ResolveRulesError(
            f"Resolve case {case_id} requires at least one known-wrong result."
        )
    for raw_wrong in wrong:
        item = _object(
            raw_wrong,
            {"result", "violates", "reason"},
            f"case {case_id} known-wrong result",
        )
        wrong_result = item["result"]
        if not isinstance(wrong_result, list) or not wrong_result:
            raise ResolveRulesError(
                f"Resolve case {case_id} known-wrong result must be nonempty."
            )
        for content in wrong_result:
            _text(content, f"case {case_id} known-wrong content")
        violations = _text_list(
            item["violates"], f"case {case_id} known-wrong rule ids"
        )
        if not violations or set(violations) - rule_ids:
            raise ResolveRulesError(
                f"Resolve case {case_id} known-wrong result cites unknown rules."
            )
        _text(item["reason"], f"case {case_id} known-wrong reason")


@lru_cache(maxsize=1)
def _loaded_ruleset() -> dict[str, object]:
    try:
        resource = resources.files("memcommit.eval").joinpath(
            "fixtures", RESOLVE_RULESET_FIXTURE
        )
        raw = json.loads(
            resource.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ResolveRulesError(
            "Could not load the Resolve exact-case ruleset."
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
        data["command"] != "resolve"
        or data["schema_version"] != 1
        or data["ruleset_version"] != RESOLVE_RULESET_VERSION
    ):
        raise ResolveRulesError("Unsupported Resolve exact-case ruleset version.")
    _text(data["description"], "description")
    rules = data["rules"]
    if not isinstance(rules, list) or not rules:
        raise ResolveRulesError("Resolve ruleset requires named rules.")
    rule_ids: set[str] = set()
    for raw_rule in rules:
        rule = _object(raw_rule, {"id", "title", "invariant"}, "rule")
        rule_id = _text(rule["id"], "rule id")
        _text(rule["title"], f"rule {rule_id} title")
        _text(rule["invariant"], f"rule {rule_id} invariant")
        if rule_id in rule_ids:
            raise ResolveRulesError(f"Resolve ruleset repeats {rule_id}.")
        rule_ids.add(rule_id)
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise ResolveRulesError("Resolve ruleset requires canonical cases.")
    case_ids: set[str] = set()
    for raw_case in cases:
        _validate_case(raw_case, rule_ids=rule_ids)
        assert isinstance(raw_case, dict)
        case_id = str(raw_case["id"])
        if case_id in case_ids:
            raise ResolveRulesError(f"Resolve ruleset repeats case {case_id}.")
        case_ids.add(case_id)
    return data


def resolve_ruleset() -> dict[str, object]:
    """Return an isolated copy of the exact authored rules and all examples."""

    return deepcopy(_loaded_ruleset())


def resolve_ruleset_prompt_payload(
    *,
    include_cases: bool = True,
) -> dict[str, object]:
    """Project rules and optionally authored cases into one semantic turn."""

    data = resolve_ruleset()
    return {
        "ruleset_version": data["ruleset_version"],
        "rules": data["rules"],
        # General Profiles retain the original production calibration. Study
        # Profiles deliberately use the same normative rules without examples
        # so latency and task behavior are not dominated by the fixture corpus.
        "cases": data["cases"] if include_cases else [],
    }


def resolve_rule_ids() -> tuple[str, ...]:
    """Return the authored rule IDs in their normative prompt order."""

    data = _loaded_ruleset()
    rules = data["rules"]
    assert isinstance(rules, list)
    return tuple(str(rule["id"]) for rule in rules if isinstance(rule, dict))


def resolve_ruleset_item_count(*, include_cases: bool = True) -> int:
    """Count prompt-visible rule/case records for the item budget axis."""

    data = _loaded_ruleset()
    rules = data["rules"]
    cases = data["cases"]
    assert isinstance(rules, list) and isinstance(cases, list)
    if not include_cases:
        return len(rules)
    return len(rules) + sum(
        1
        + len(case["source"])
        + len(case["expected"]["effects"])
        + len(case["known_wrong"])
        for case in cases
        if isinstance(case, dict)
    )


__all__ = [
    "RESOLVE_RULESET_VERSION",
    "ResolveRulesError",
    "resolve_rule_ids",
    "resolve_ruleset",
    "resolve_ruleset_item_count",
    "resolve_ruleset_prompt_payload",
]
