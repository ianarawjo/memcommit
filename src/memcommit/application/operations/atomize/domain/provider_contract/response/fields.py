"""Basic JSON and field checks shared by Atomize response sections and examples."""

from __future__ import annotations

from ...model import AtomizeImpactError


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_dict(
    value: object,
    keys: set[str],
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AtomizeImpactError(
            "Codex atomize impact returned invalid structured output."
        )
    return value


def _short_string(
    value: object,
    *,
    label: str,
    limit: int,
) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AtomizeImpactError(f"Codex atomize impact returned an invalid {label}.")
    return value
