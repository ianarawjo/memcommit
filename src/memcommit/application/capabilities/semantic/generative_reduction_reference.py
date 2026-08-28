"""Authored bidirectional examples quoted by every Distill and Elaborate prompt."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
import json


REFERENCE_EXAMPLES_MARKER = "DISTILL / ELABORATE REFERENCE EXAMPLES:\n"
REFERENCE_FIXTURE_PACKAGE = "memcommit.application.capabilities.evaluation"
REFERENCE_FIXTURE_NAME = "fixtures/distill_elaborate.json"
REFERENCE_SCHEMA_VERSION = 2
REFERENCE_RULESET_VERSION = 3
REFERENCE_FAMILY_IDS = ("cafe-order", "lost-property", "cloze")


class DistillElaborateReferenceError(ValueError):
    """The packaged prompt-reference corpus is missing or malformed."""


@dataclass(frozen=True)
class DistillElaborateReferenceFamily:
    """One complete Example-Memory and Rule-Memory correspondence."""

    family_id: str
    rule_memories: tuple[str, ...]
    example_memories: tuple[str, ...]


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DistillElaborateReferenceError(
                f"Duplicate Distill/Elaborate reference key: {key}."
            )
        result[key] = value
    return result


def _texts(value: object, *, label: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise DistillElaborateReferenceError(
            f"Distill/Elaborate reference {label} must be nonempty texts."
        )
    normalized = tuple(item.strip() for item in value)
    if len(normalized) != len(set(normalized)):
        raise DistillElaborateReferenceError(
            f"Distill/Elaborate reference {label} contains duplicates."
        )
    return normalized


@lru_cache(maxsize=1)
def load_distill_elaborate_reference_families(
) -> tuple[DistillElaborateReferenceFamily, ...]:
    """Load and strictly validate the packaged prompt-visible examples once."""

    try:
        raw = (
            resources.files(REFERENCE_FIXTURE_PACKAGE)
            .joinpath(REFERENCE_FIXTURE_NAME)
            .read_text(encoding="utf-8")
        )
        value = json.loads(raw, object_pairs_hook=_strict_object)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise DistillElaborateReferenceError(
            "The packaged Distill/Elaborate reference corpus is invalid."
        ) from error
    expected_keys = {
        "schema_version",
        "ruleset_version",
        "corpus_role",
        "independent_holdout",
        "prompt_reference",
        "operation_rules",
        "reference_families",
        "distill_cases",
        "elaborate_cases",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise DistillElaborateReferenceError(
            "The Distill/Elaborate reference corpus has an invalid field set."
        )
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != REFERENCE_SCHEMA_VERSION
        or type(value["ruleset_version"]) is not int
        or value["ruleset_version"] != REFERENCE_RULESET_VERSION
        or value["corpus_role"] != "CONSUMED_CALIBRATION"
        or value["independent_holdout"] is not False
        or value["prompt_reference"] is not True
    ):
        raise DistillElaborateReferenceError(
            "The Distill/Elaborate reference corpus identity is unsupported."
        )
    raw_families = value["reference_families"]
    if not isinstance(raw_families, list):
        raise DistillElaborateReferenceError(
            "Distill/Elaborate reference families must be an array."
        )
    families: list[DistillElaborateReferenceFamily] = []
    for index, item in enumerate(raw_families, 1):
        if not isinstance(item, dict) or set(item) != {
            "id",
            "rule_memories",
            "example_memories",
        }:
            raise DistillElaborateReferenceError(
                f"Distill/Elaborate reference family {index} is invalid."
            )
        family_id = item["id"]
        if not isinstance(family_id, str) or not family_id.strip():
            raise DistillElaborateReferenceError(
                f"Distill/Elaborate reference family {index} needs an id."
            )
        families.append(
            DistillElaborateReferenceFamily(
                family_id=family_id.strip(),
                rule_memories=_texts(
                    item["rule_memories"],
                    label=f"{family_id} Rules",
                ),
                example_memories=_texts(
                    item["example_memories"],
                    label=f"{family_id} Examples",
                ),
            )
        )
    if tuple(family.family_id for family in families) != REFERENCE_FAMILY_IDS:
        raise DistillElaborateReferenceError(
            "Distill/Elaborate reference families must be cafe-order, "
            "lost-property, and cloze in that order."
        )
    if any(len(family.example_memories) != 3 for family in families):
        raise DistillElaborateReferenceError(
            "Every Distill/Elaborate reference family must contain three Examples."
        )
    return tuple(families)


def distill_elaborate_reference_payload(
    *,
    include_examples: bool = True,
) -> dict[str, object]:
    """Return the authored pairing, or an explicit rules-only projection."""

    return {
        "role": (
            "QUOTED_REFERENCE_EXAMPLES"
            if include_examples
            else "AUTHORED_EXAMPLES_OMITTED"
        ),
        "families": [
            {
                "family_id": family.family_id,
                "example_memories": list(family.example_memories),
                "rule_memories": list(family.rule_memories),
            }
            for family in (
                load_distill_elaborate_reference_families()
                if include_examples
                else ()
            )
        ],
    }


@lru_cache(maxsize=2)
def render_distill_elaborate_reference_examples(
    *,
    include_examples: bool = True,
) -> str:
    """Render authored pairs, or no example block for a rules-only turn."""

    if not include_examples:
        return ""

    return REFERENCE_EXAMPLES_MARKER + json.dumps(
        distill_elaborate_reference_payload(include_examples=True),
        ensure_ascii=False,
        separators=(",", ":"),
    )


__all__ = [
    "DistillElaborateReferenceError",
    "DistillElaborateReferenceFamily",
    "REFERENCE_EXAMPLES_MARKER",
    "REFERENCE_FAMILY_IDS",
    "REFERENCE_RULESET_VERSION",
    "REFERENCE_SCHEMA_VERSION",
    "distill_elaborate_reference_payload",
    "load_distill_elaborate_reference_families",
    "render_distill_elaborate_reference_examples",
]
