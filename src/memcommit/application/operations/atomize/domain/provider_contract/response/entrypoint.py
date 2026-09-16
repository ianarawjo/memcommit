"""Read the complete Atomize response and assemble its three validated sections."""

from __future__ import annotations

import json

from ...model import (
    ATOMIZE_RESPONSE_CHAR_LIMIT,
    AtomizeCandidate,
    AtomizeImpactError,
    AtomizeItem,
    AtomizeOverview,
    AtomizeQualityIssue,
)
from .fields import _exact_dict, _reject_duplicate_json_keys
from .items import parse_items
from .overview import _parse_overview
from .quality_issues import _parse_quality_issues


def parse_response(
    raw: object,
    candidates: list[AtomizeCandidate],
    declared_frames: dict[str, str] | None = None,
) -> tuple[
    tuple[AtomizeItem, ...],
    AtomizeOverview,
    tuple[AtomizeQualityIssue, ...],
]:
    declared_frames = declared_frames or {}
    if (
        not isinstance(raw, str)
        or not raw.strip()
        or len(raw) > ATOMIZE_RESPONSE_CHAR_LIMIT
    ):
        raise AtomizeImpactError(
            "Codex atomize impact returned invalid structured output."
        )
    try:
        data = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise AtomizeImpactError(
            "Codex atomize impact returned invalid structured output."
        ) from error

    envelope = _exact_dict(
        data,
        {"overview", "items", "quality_issues"},
    )
    items = parse_items(envelope["items"], candidates, declared_frames)
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    # Return only after all three sections pass their existing checks; a later
    # invalid section must never expose a partially accepted response.
    return (
        items,
        _parse_overview(envelope["overview"], candidate_by_id),
        _parse_quality_issues(envelope["quality_issues"], candidate_by_id),
    )
