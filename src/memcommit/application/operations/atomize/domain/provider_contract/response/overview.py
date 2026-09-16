"""Read the source-linked overview sections of an Atomize response."""

from __future__ import annotations

import re

from memcommit.application.capabilities.semantic.understanding import (
    UnderstandingError,
    UnderstandingSummary,
    parse_source_linked_understanding,
)

from ...model import (
    ATOMIZE_OVERVIEW_CHAR_LIMIT,
    AtomizeCandidate,
    AtomizeImpactError,
    AtomizeOverview,
    AtomizeOverviewSection,
)
from .fields import _exact_dict


def _parse_overview(
    value: object,
    candidate_by_id: dict[str, AtomizeCandidate],
) -> AtomizeOverview:
    record = _exact_dict(
        value,
        {"understood", "changed", "unresolved"},
    )

    source_uid_by_id = {
        candidate_id: candidate.memory.uid
        for candidate_id, candidate in candidate_by_id.items()
    }

    def deduplicate_source_ids(raw: object) -> object:
        """Normalize harmless duplicate citations unsupported by the schema."""

        if not isinstance(raw, dict):
            return raw
        source_ids = raw.get("source_ids")
        if not isinstance(source_ids, list) or any(
            not isinstance(candidate_id, str) for candidate_id in source_ids
        ):
            return raw
        normalized = dict(raw)
        normalized["source_ids"] = list(dict.fromkeys(source_ids))
        return normalized

    def parse_understood(raw: object) -> UnderstandingSummary:
        try:
            if (
                isinstance(raw, dict)
                and raw.get("text") == ""
                and raw.get("source_ids") == []
            ):
                return UnderstandingSummary(text="")
            return parse_source_linked_understanding(
                deduplicate_source_ids(raw),
                source_uid_by_id=source_uid_by_id,
                limit=ATOMIZE_OVERVIEW_CHAR_LIMIT,
            )
        except UnderstandingError as error:
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid source-linked "
                "natural-language report paragraph."
            ) from error

    def parse_section(raw: object) -> AtomizeOverviewSection:
        section = _exact_dict(raw, {"text", "source_ids"})
        raw_text = section["text"]
        source_ids = section["source_ids"]
        if (
            not isinstance(raw_text, str)
            or len(raw_text) > ATOMIZE_OVERVIEW_CHAR_LIMIT
            or not isinstance(source_ids, list)
            or any(
                not isinstance(candidate_id, str) or candidate_id not in candidate_by_id
                for candidate_id in source_ids
            )
        ):
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid source-linked overview."
            )
        # The provider's strict schema cannot use uniqueItems. Overview
        # citations have set semantics, so repeated aliases do not weaken the
        # evidence boundary and are retained once in first-seen order.
        source_ids = list(dict.fromkeys(source_ids))
        text = raw_text.strip()
        if text and (
            len(text.splitlines()) != 1
            or re.match(r"(?:[-*•]\s+|\d+[.)]\s+)", text) is not None
        ):
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid natural-language "
                "report paragraph."
            )
        text = " ".join(text.split())
        if text and not source_ids and candidate_by_id:
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid source-linked overview."
            )
        return AtomizeOverviewSection(
            text=text,
            source_uids=tuple(
                candidate_by_id[candidate_id].memory.uid for candidate_id in source_ids
            ),
        )

    return AtomizeOverview(
        understood=parse_understood(record["understood"]),
        changed=parse_section(record["changed"]),
        unresolved=parse_section(record["unresolved"]),
    )
